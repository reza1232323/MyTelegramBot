import logging
import random
import time
import asyncio
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
    CallbackQuery,
)
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import config
import database as db
from handlers import admin, economy, pet

# مقدار پاداش دعوت (سکه/پوینت)
REFERRAL_REWARD = 500

# ----------------- تنظیمات کانال‌های عضویت اجباری -----------------
REQUIRED_CHANNELS = [
    {
        "name": "کانال اصلی",
        "username": "@CODMSAOPZX",
        "url": "https://t.me/CODMSAOPZX",
    },
    {
        "name": "کانال دوم",
        "username": "@esmok_shop_poy",
        "url": "https://t.me/esmok_shop_poy",
    },
]

logging.basicConfig(level=logging.INFO)

# ==================== دیکشنری گردونه شانس ====================
user_last_spin = {}  # {user_id: timestamp}
SPIN_COOLDOWN = 12 * 3600  # ۱۲ ساعت

SPIN_PRIZES = [
    {"amount": 100, "weight": 35},
    {"amount": 200, "weight": 30},
    {"amount": 300, "weight": 25},
    {"amount": 500, "weight": 15},
    {"amount": 1000, "weight": 10},
    {"amount": 2000, "weight": 7},
    {"amount": 5000, "weight": 4},
    {"amount": 10000, "weight": 2},
    {"amount": 50000, "weight": 1},
    {"amount": 100000, "weight": 0.5},
]

# ==================== دیکشنری انتقال‌های در انتظار ====================
pending_transfers = {}  # {transfer_id: {sender_id, target_id, amount, sender_name, target_name, ...}}

def get_spin_prize():
    weights = [p["weight"] for p in SPIN_PRIZES]
    return random.choices(SPIN_PRIZES, weights=weights, k=1)[0]["amount"]


# ----------------- توابع عضویت اجباری -----------------
async def check_user_membership(bot, user_id: int) -> bool:
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(
                chat_id=ch["username"], user_id=user_id
            )
            if member.status in ["left", "kicked"]:
                return False
        except BadRequest:
            continue
        except Exception as e:
            logging.error(f"خطا در بررسی عضویت کانال {ch['username']}: {e}")
            return False
    return True


def get_join_keyboard():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append(
            [
                InlineKeyboardButton(
                    f"🔴 عضویت در {ch['name']}",
                    callback_data=f"channel_{ch['username']}",
                    style="danger"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                "✅ عضو شدم، بررسی کن!",
                callback_data="check_join_status",
                style="success"
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def send_must_join_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    channels_list = "\n".join([f"• {ch['name']}" for ch in REQUIRED_CHANNELS])

    text = (
        f"⛔️ عزیز {user_first_name}!\n\n"
        f"برای استفاده از ربات هاپ‌داگ، ابتدا باید عضو این کانال‌ها بشی:\n\n"
        f"{channels_list}\n\n"
        f"👇 روی دکمه‌ها کلیک کن، عضو بشو، بعد «عضو شدم» رو بزن:"
    )

    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_join_keyboard())
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_join_keyboard())


# ----------------- سیستم محاسباتی هاپ -----------------
def hops_needed_for_level(level):
    return 10 + (level - 1) * 5


def calculate_hop_reward(level):
    base_min = 10 * (1.5 ** (level - 1))
    base_max = 25 * (1.5 ** (level - 1))
    return random.randint(int(base_min), int(base_max))


# ==================== لیدربرد ====================
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, points, level 
        FROM users 
        ORDER BY points DESC 
        LIMIT 10
    """)
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await update.message.reply_text("📊 هنوز کاربری در سیستم ثبت‌نام نکرده است!")
        return

    text = "🏆 **لیدربرد برترین های هاپو** 🏆\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"

    medals = ["🥇", "🥈", "🥉"]

    for i, user in enumerate(top_users, 1):
        user_id_db, username, points, level = user
        medal = medals[i-1] if i <= 3 else f"{i}."
        name = username or f"کاربر {user_id_db}"
        if len(name) > 15:
            name = name[:15] + "..."
        text += f"{medal} `{name}`\n"
        text += f"   💰 {points:,} هاپو | 🎯 سطح {level}\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"

    user_data = db.get_user(user_id)
    if user_data:
        user_points = user_data[2]
        user_level = user_data[3]
        text += f"\n📊 **رتبه شما:**\n"
        text += f"   💰 {user_points:,} هاپو | 🎯 سطح {user_level}"

    await update.message.reply_text(text, parse_mode="Markdown")


# ==================== گردونه شانس ====================
async def spin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    last_spin = user_last_spin.get(user_id, 0)
    if now - last_spin < SPIN_COOLDOWN:
        remaining = int(SPIN_COOLDOWN - (now - last_spin))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ هنوز {hours} ساعت و {minutes} دقیقه مونده تا گردونه بعدی!"
        )
        return

    user_last_spin[user_id] = now

    msg = await update.message.reply_text(
        "🎡 گردونه در حال چرخش...",
        reply_to_message_id=update.message.message_id
    )

    steps = [
        "🎡 گردونه در حال چرخش...",
        "🎡 چرخش ادامه داره...",
        "🎡 تقریباً ایستاد...",
        "🎡 لحظاتی دیگر...",
    ]

    for step in steps:
        await asyncio.sleep(0.8)
        try:
            await msg.edit_text(step)
        except:
            pass

    prize = get_spin_prize()
    db.update_field(user_id, "points", prize, relative=True)

    final_text = (
        f"🎉 **تبریک!**\n"
        f"💰 شما **{prize:,}** هاپ پوینت برنده شدید!\n\n"
        f"⏳ گردونه بعدی: ۱۲ ساعت دیگر"
    )
    await msg.edit_text(final_text, parse_mode="Markdown")


# ==================== انتقال هاپ پوینت (با دکمه‌های رنگی) ====================
async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال هاپ پوینت به کاربر دیگر با ریپلای و دکمه‌های رنگی"""
    user_id = update.effective_user.id
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ **فرمت اشتباه!**\n\n"
            "برای انتقال هاپ پوینت، روی پیام کاربر مورد نظر **ریپلای** کنید و بنویسید:\n"
            "`انتقال هاپ پوینت [مبلغ]`\n\n"
            "مثال: `انتقال هاپ پوینت 100`",
            parse_mode="Markdown"
        )
        return
    
    parts = update.message.text.split()
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ **فرمت اشتباه!**\n\n"
            "فرمت صحیح:\n"
            "`انتقال هاپ پوینت [مبلغ]`\n\n"
            "مثال: `انتقال هاپ پوینت 100`",
            parse_mode="Markdown"
        )
        return
    
    if parts[0] != "انتقال" or parts[1] != "هاپ" or parts[2] != "پوینت":
        await update.message.reply_text(
            "❌ **فرمت اشتباه!**\n\n"
            "فرمت صحیح:\n"
            "`انتقال هاپ پوینت [مبلغ]`\n\n"
            "مثال: `انتقال هاپ پوینت 100`",
            parse_mode="Markdown"
        )
        return
    
    if len(parts) < 4:
        await update.message.reply_text(
            "❌ **مبلغ را وارد کنید!**\n\n"
            "مثال: `انتقال هاپ پوینت 100`",
            parse_mode="Markdown"
        )
        return
    
    amount_str = parts[3]
    
    persian_to_english = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    
    for persian, english in persian_to_english.items():
        amount_str = amount_str.replace(persian, english)
    
    amount_str = amount_str.replace(",", "").replace(" ", "")
    
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text(
            "❌ **مبلغ باید عدد باشد!**\n\n"
            "مثال: `انتقال هاپ پوینت 100`\n"
            "یا `انتقال هاپ پوینت ۱,۰۰۰`",
            parse_mode="Markdown"
        )
        return
    
    if amount <= 0:
        await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد!")
        return
    
    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name
    target_username = update.message.reply_to_message.from_user.username
    
    if target_id == user_id:
        await update.message.reply_text("❌ نمی‌توانید به خودتان انتقال دهید!")
        return
    
    sender_data = db.get_user(user_id)
    sender_points = sender_data[2]
    sender_name = update.effective_user.first_name
    
    if sender_points < amount:
        await update.message.reply_text(
            f"❌ موجودی کافی نیست!\n"
            f"💰 موجودی شما: {sender_points:,} هاپ پوینت"
        )
        return
    
    target_data = db.get_user(target_id)
    if not target_data:
        await update.message.reply_text("❌ کاربر مورد نظر در ربات ثبت‌نام نکرده است!")
        return
    
    transfer_id = f"{user_id}_{target_id}_{int(time.time())}"
    
    pending_transfers[transfer_id] = {
        "sender_id": user_id,
        "target_id": target_id,
        "amount": amount,
        "sender_name": sender_name,
        "target_name": target_name,
        "target_username": target_username,
        "sender_points": sender_points,
        "target_points": target_data[2],
        "status": "pending"
    }
    
    target_display = f"@{target_username}" if target_username else target_name
    
    # ===== دکمه‌های رنگی =====
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تایید",
                callback_data=f"transfer_accept_{transfer_id}",
                style="success"  # 🟢 سبز
            ),
            InlineKeyboardButton(
                "❌ لغو",
                callback_data=f"transfer_reject_{transfer_id}",
                style="danger"  # 🔴 قرمز
            )
        ]
    ])
    
    # ===== ارسال پیام به گیرنده با try/except =====
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"📨 **درخواست انتقال هاپ پوینت**\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 از طرف: **{sender_name}**\n"
                f"💰 مبلغ: **{amount:,}** هاپ پوینت\n\n"
                f"لطفا تایید یا لغو کنید:"
            ),
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        # اگر کاربر ربات رو بلاک کرده باشه
        await update.message.reply_text(
            f"❌ ارسال پیام به {target_display} امکان‌پذیر نیست!\n"
            f"کاربر مورد نظر ربات را بلاک کرده است."
        )
        # حذف از pending_transfers
        del pending_transfers[transfer_id]
        return
    
    await update.message.reply_text(
        f"📤 **درخواست انتقال ارسال شد!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: **{amount:,}** هاپ پوینت\n"
        f"👤 به: {target_display}\n\n"
        f"⏳ در انتظار تایید گیرنده...",
        parse_mode="Markdown"
    )


# ==================== دکمه تایید انتقال (سبز) ====================
async def transfer_accept(callback: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    transfer_id = callback.data.replace("transfer_accept_", "")
    transfer = pending_transfers.get(transfer_id)
    
    if not transfer:
        await callback.answer("❌ درخواست منقضی شده است!", show_alert=True)
        await callback.message.edit_text("❌ این درخواست انتقال منقضی شده است.")
        return
    
    if transfer["status"] != "pending":
        await callback.answer("❌ این درخواست قبلاً پردازش شده!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if user_id != transfer["target_id"]:
        await callback.answer("❌ این درخواست برای شما نیست!", show_alert=True)
        return
    
    transfer["status"] = "completed"
    
    db.update_field(transfer["sender_id"], "points", -transfer["amount"], relative=True)
    db.update_field(transfer["target_id"], "points", transfer["amount"], relative=True)
    
    new_sender_points = transfer["sender_points"] - transfer["amount"]
    new_target_points = transfer["target_points"] + transfer["amount"]
    
    target_display = f"@{transfer['target_username']}" if transfer['target_username'] else transfer['target_name']
    
    await callback.message.edit_text(
        f"✅ **انتقال تایید شد!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: **{transfer['amount']:,}** هاپ پوینت\n"
        f"👤 از: **{transfer['sender_name']}**\n\n"
        f"📊 موجودی جدید شما: **{new_target_points:,}** هاپ پوینت",
        parse_mode="Markdown"
    )
    
    # ===== ارسال پیام به فرستنده با try/except =====
    try:
        await context.bot.send_message(
            chat_id=transfer["sender_id"],
            text=(
                f"✅ **انتقال با موفقیت انجام شد!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 مبلغ: **{transfer['amount']:,}** هاپ پوینت\n"
                f"👤 به: {target_display}\n\n"
                f"📊 موجودی جدید شما: **{new_sender_points:,}** هاپ پوینت"
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    del pending_transfers[transfer_id]
    await callback.answer("✅ انتقال با موفقیت انجام شد!")


# ==================== دکمه لغو انتقال (قرمز) ====================
async def transfer_reject(callback: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    transfer_id = callback.data.replace("transfer_reject_", "")
    transfer = pending_transfers.get(transfer_id)
    
    if not transfer:
        await callback.answer("❌ درخواست منقضی شده است!", show_alert=True)
        await callback.message.edit_text("❌ این درخواست انتقال منقضی شده است.")
        return
    
    if transfer["status"] != "pending":
        await callback.answer("❌ این درخواست قبلاً پردازش شده!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if user_id != transfer["target_id"]:
        await callback.answer("❌ این درخواست برای شما نیست!", show_alert=True)
        return
    
    transfer["status"] = "rejected"
    
    target_display = f"@{transfer['target_username']}" if transfer['target_username'] else transfer['target_name']
    
    await callback.message.edit_text(
        f"❌ **انتقال لغو شد!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: **{transfer['amount']:,}** هاپ پوینت\n"
        f"👤 از: **{transfer['sender_name']}**\n\n"
        f"شما این درخواست را لغو کردید.",
        parse_mode="Markdown"
    )
    
    # ===== ارسال پیام به فرستنده با try/except =====
    try:
        await context.bot.send_message(
            chat_id=transfer["sender_id"],
            text=(
                f"❌ **درخواست انتقال لغو شد!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 مبلغ: **{transfer['amount']:,}** هاپ پوینت\n"
                f"👤 به: {target_display}\n\n"
                f"گیرنده درخواست را لغو کرد."
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    del pending_transfers[transfer_id]
    await callback.answer("❌ انتقال لغو شد!")


# ----------------- دستورات ربات -----------------
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = context.bot.username

    ref_count = db.get_referral_stats(user_id) if hasattr(db, "get_referral_stats") else 0
    total_earned = ref_count * REFERRAL_REWARD
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    text = (
        f"👥 سیستم دعوت و زیرمجموعه‌گیری\n\n"
        f"با دعوت دوستان خود به ربات، پاداش دریافت کنید!\n\n"
        f"🎁 پاداش هر دعوت: {REFERRAL_REWARD:,} سکه\n"
        f"📊 تعداد دعوت‌های شما: {ref_count} نفر\n"
        f"💰 مجموع درآمد از دعوت: {total_earned:,} سکه\n\n"
        f"🔗 لینک اختصاصی شما:\n"
        f"`{referral_link}`"
    )

    share_url = f"https://t.me/share/url?url={referral_link}&text=بیا%20تو%20این%20ربات%20باهم%20بازی%20کنیم!"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 اشتراک‌گذاری لینک", url=share_url)]
    ])

    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "کاربر"

    db.get_user(user_id, username)

    if context.args and context.args[0].isdigit():
        inviter_id = int(context.args[0])
        if hasattr(db, "set_inviter") and db.set_inviter(user_id, inviter_id):
            db.update_field(inviter_id, "points", REFERRAL_REWARD, relative=True)
            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=f"🎉 یک کاربر جدید با لینک شما وارد ربات شد!\n🎁 مبلغ {REFERRAL_REWARD:,} سکه به حساب شما اضافه شد.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    main_keyboard = ReplyKeyboardMarkup(
        [
            ["📊 پروفایل", "🎯 هاپ"],
            ["🐶 پنل سگ", "🛒 خرید سگ", "🍖 غذا"],
            ["🏭 کارخونه", "🌆 شهر"],
            ["🏦 بانک", "👥 زیرمجموعه‌گیری"],
            ["🎡 گردونه", "🏆 لیدربرد"],
            ["💰 انتقال هاپ پوینت", "📖 راهنما"],
        ],
        resize_keyboard=True,
    )

    inline_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 دریافت لینک زیرمجموعه‌گیری", callback_data="get_referral_link")]
    ])

    start_text = (
        f"سلام {update.effective_user.first_name} عزیز! 👋\n"
        f"به ربات خوش آمدید.\n\n"
        f"💡 برای گرفتن لینک دعوت می‌توانید از دکمه شیشه‌ای زیر یا دکمه 👥 زیرمجموعه‌گیری در کیبورد استفاده کنید.\n\n"
        f"🎡 برای گردونه شانس از دکمه گردونه استفاده کنید.\n"
        f"🏆 برای مشاهده لیدربرد از دکمه لیدربرد استفاده کنید.\n\n"
        f"💰 برای انتقال هاپ پوینت، روی پیام کاربر ریپلای کنید و بنویسید:\n"
        f"`انتقال هاپ پوینت [مبلغ]`"
    )

    await update.message.reply_text(start_text, reply_markup=main_keyboard, parse_mode="Markdown")
    await update.message.reply_text("منوی سریع زیرمجموعه‌گیری:", reply_markup=inline_keyboard)


async def handle_hop_internal(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    current_time = int(time.time())

    last_hop_time = db.get_user_field(user_id, "last_hop_time") or 0
    cooldown = 300

    if current_time - last_hop_time < cooldown:
        remaining = cooldown - (current_time - last_hop_time)
        minutes = remaining // 60
        seconds = remaining % 60
        await update.message.reply_text(
            f"⏳ سگ شما خسته است! لطفا {minutes} دقیقه و {seconds} ثانیه صبر کنید."
        )
        return

    level = db.get_user_field(user_id, "level") or 1
    progress = db.get_user_field(user_id, "level_hops_progress") or 0

    reward = calculate_hop_reward(level)
    needed = hops_needed_for_level(level)
    progress += 1

    db.update_field(user_id, "points", reward, relative=True)
    db.update_field(user_id, "hops", 1, relative=True)
    db.update_field(user_id, "last_hop_time", current_time, relative=False)

    level_up_msg = ""
    if progress >= needed:
        level += 1
        progress = 0
        db.update_field(user_id, "level", 1, relative=True)
        db.update_field(user_id, "level_hops_progress", 0, relative=False)
        level_up_msg = f"\n🎉 تبریک! شما به سطح {level} ارتقا یافتید! 🚀"
    else:
        db.update_field(user_id, "level_hops_progress", progress, relative=False)

    await update.message.reply_text(
        f"🐕 هاپ! هاپ!\n\n"
        f"💰 پاداش دریافتی: {reward:,} سکه\n"
        f"📊 پیشرفت سطح {level}: [{progress}/{needed}] هاپ{level_up_msg}",
        parse_mode="Markdown",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"خطایی در پردازش رخ داد: {context.error}", exc_info=context.error)


async def router_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    if hasattr(pet, "handle_dog_rename_text"):
        is_handled = await pet.handle_dog_rename_text(update, context)
        if is_handled:
            return

    context.args = text.split()[1:]

    if hasattr(economy, "handle_factory_and_smuggle_text"):
        handled = await economy.handle_factory_and_smuggle_text(update, context)
        if handled:
            return

    username = update.effective_user.username or update.effective_user.first_name
    user = db.get_user(user_id, username)
    clean_text = text.split("@")[0].lower()

    # ===== انتقال هاپ پوینت (اولویت بالا) =====
    if clean_text.startswith("انتقال هاپ پوینت") or clean_text.startswith("انتقال"):
        await transfer_command(update, context)
        return

    # ===== گردونه شانس =====
    if clean_text in ["گردونه", "🎡 گردونه", "چرخونه", "گلدونه"]:
        await spin_command(update, context)
        return

    # ===== لیدربرد =====
    if clean_text in ["لیدربرد", "🏆 لیدربرد", "leaderboard", "/leaderboard"]:
        await leaderboard_command(update, context)
        return

    # ===== بقیه دستورات =====
    if clean_text in ["پروفایل", "هاپوهام", "هاپوهاش", "/profile"]:
        await pet.show_profile(update, context, user)
    elif clean_text in ["🐶 پنل سگ", "پنل سگ", "سگ من", "سگ", "/dog", "/dogpanel"]:
        if hasattr(pet, "show_dog_panel"):
            await pet.show_dog_panel(update, context, user)
        elif hasattr(pet, "show_profile"):
            await pet.show_profile(update, context, user)
    elif clean_text in ["هاپ", "hop", "/hop"]:
        if hasattr(pet, "claim_hop"):
            await pet.claim_hop(update, context, user)
        else:
            await handle_hop_internal(update, context, user)
    elif clean_text in ["راهنما", "help", "/help"]:
        await pet.show_help(update, context)
    elif clean_text in ["خرید سگ", "/buydog"]:
        await pet.buy_dog(update, context, user)
    elif clean_text in ["غذا", "/feed"]:
        await pet.feed_dog(update, context, user)
    elif clean_text in ["👥 زیرمجموعه‌گیری", "زیرمجموعه‌گیری", "زیرمجموعه", "دعوت", "رفرال", "/referral"]:
        await referral_command(update, context)
    elif clean_text in ["🏦 بانک", "بانک", "bank", "/bank"]:
        if hasattr(economy, "bank_status"):
            await economy.bank_status(update, context, user)
    elif clean_text in ["کارخونه", "/factory"]:
        await economy.show_factory(update, context)
    elif clean_text in ["کارخونه من", "/myfactory"]:
        await economy.show_my_factory(update, context, user)
    elif clean_text in ["فروش", "بازار", "/sell"]:
        await economy.show_sell_menu(update, context, user)
    elif clean_text in ["قاچاق", "قاچاقچی", "/smuggle"]:
        await economy.show_contraband(update, context)
    elif clean_text.startswith("زندان") or clean_text.startswith("/jail"):
        if hasattr(economy, "jail_status"):
            await economy.jail_status(update, context, user)
    elif clean_text.startswith("قمار") or clean_text.startswith("/gamble"):
        await economy.start_gamble(update, context)
    elif clean_text in ["شهر", "/city"]:
        await economy.city_status(update, context, user)
    elif clean_text.startswith("اهدا") or clean_text.startswith("/donate"):
        await economy.donate_city(update, context, user)
    elif user_id in config.ADMIN_IDS:
        if text.startswith("افزایش پوینت"):
            await admin.add_points(update, context)
        elif text.startswith("کاهش پوینت"):
            await admin.remove_points(update, context)
        elif text.startswith("افزایش لول"):
            await admin.add_level(update, context)
        elif text.startswith("کاهش لول"):
            await admin.remove_level(update, context)
        elif text.startswith("همگانی"):
            await admin.broadcast(update, context)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # ===== دکمه تایید انتقال (سبز) =====
    if data.startswith("transfer_accept_"):
        await transfer_accept(query, context)
        return
    
    # ===== دکمه لغو انتقال (قرمز) =====
    if data.startswith("transfer_reject_"):
        await transfer_reject(query, context)
        return

    if data.startswith("channel_"):
        username = data.replace("channel_", "")
        for ch in REQUIRED_CHANNELS:
            if ch["username"] == username:
                try:
                    await query.message.delete()
                except Exception:
                    pass
                await query.message.reply_text(
                    f"🔗 برای عضویت در {ch['name']} روی لینک زیر کلیک کنید:\n{ch['url']}"
                )
                await query.answer()
                return
        return

    if data == "check_join_status":
        is_joined = await check_user_membership(context.bot, user_id)
        if is_joined:
            await query.answer("✅ عضویت شما تایید شد. از ربات استفاده کنید!", show_alert=True)
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.answer("❌ هنوز در تمامی کانال‌ها عضو نشده‌اید!", show_alert=True)
        return

    if ":" in data:
        parts = data.split(":")
        action = parts[0]
        owner_id = int(parts[1]) if parts[1].isdigit() else None
        if owner_id and user_id != owner_id:
            await query.answer("❌ این پنل برای شما نیست!", show_alert=True)
            return
    else:
        action = data

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await query.answer("❌ ابتدا باید در کانال‌های اجباری عضو شوید!", show_alert=True)
        await send_must_join_message(update, context)
        return

    if action == "get_referral_link":
        await referral_command(update, context)
        await query.answer()
    elif action in ["fish_sell", "fish_feed"]:
        if hasattr(pet, "handle_fish_callback"):
            await pet.handle_fish_callback(update, context)
        else:
            await query.answer()
    elif action.startswith("dog_") or action.startswith("pet_") or action == "dog_panel":
        if hasattr(pet, "handle_dog_callback"):
            await pet.handle_dog_callback(update, context)
        elif hasattr(pet, "dog_callback"):
            await pet.dog_callback(update, context)
        else:
            await query.answer()
    elif action.startswith("bank_"):
        if hasattr(economy, "handle_bank_callback"):
            await economy.handle_bank_callback(update, context)
    elif action.startswith("buy_fac_") or action.startswith("fac_"):
        if hasattr(economy, "factory_callback"):
            await economy.factory_callback(update, context)
        elif hasattr(economy, "handle_factory_callback"):
            await economy.handle_factory_callback(update, context)
    elif action.startswith("select_contra_") or action in ["start_smuggling", "pay_bail"]:
        if hasattr(economy, "handle_smuggle_callback"):
            await economy.handle_smuggle_callback(update, context)
    elif action.startswith("sell_"):
        if hasattr(economy, "sell_callback"):
            await economy.sell_callback(update, context)
    elif action.startswith("join_gamble"):
        if hasattr(economy, "join_gamble_callback"):
            await economy.join_gamble_callback(update, context)


def main():
    db.init_db()

    request_config = HTTPXRequest(
        connection_pool_size=8, read_timeout=60.0, write_timeout=60.0
    )

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request_config)
        .build()
    )

    app.add_error_handler(error_handler)

    # ===== اضافه کردن هندلرها =====
    app.add_handler(CommandHandler("start", start_command))
    if hasattr(economy, "bank_status"):
        app.add_handler(CommandHandler("bank", economy.bank_status))
    app.add_handler(CommandHandler(["referral", "sub"], referral_command))
    app.add_handler(CommandHandler(["leaderboard", "liderboard"], leaderboard_command))

    # ===== هندلرهای اصلی =====
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router_message))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🤖 Bot is active...")
    app.run_polling()


if __name__ == "__main__":
    main()
