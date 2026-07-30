import random
import time
import math
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
import database as db

# ----------------- تنظیمات و جدول ۳۰ سطحی سگ -----------------
DOG_LEVELS = {
    1:  {"upgrade_cost": 0,       "rate": 0.1,  "capacity": 50},
    2:  {"upgrade_cost": 150,     "rate": 0.2,  "capacity": 150},
    3:  {"upgrade_cost": 450,     "rate": 0.3,  "capacity": 500},
    4:  {"upgrade_cost": 1250,    "rate": 0.5,  "capacity": 1500},
    5:  {"upgrade_cost": 3000,    "rate": 0.75, "capacity": 5000},
    6:  {"upgrade_cost": 5250,    "rate": 1.0,  "capacity": 8250},
    7:  {"upgrade_cost": 8750,    "rate": 1.25, "capacity": 11500},
    8:  {"upgrade_cost": 13250,   "rate": 1.5,  "capacity": 14500},
    9:  {"upgrade_cost": 23250,   "rate": 1.75, "capacity": 22500},
    10: {"upgrade_cost": 36750,   "rate": 2.0,  "capacity": 31250},
    11: {"upgrade_cost": 52500,   "rate": 2.5,  "capacity": 48500},
    12: {"upgrade_cost": 76250,   "rate": 3.0,  "capacity": 65000},
    13: {"upgrade_cost": 98000,   "rate": 3.5,  "capacity": 82750},
    14: {"upgrade_cost": 125000,  "rate": 4.0,  "capacity": 115000},
    15: {"upgrade_cost": 192500,  "rate": 4.5,  "capacity": 145250},
    16: {"upgrade_cost": 275000,  "rate": 5.0,  "capacity": 195000},
    17: {"upgrade_cost": 382500,  "rate": 5.75, "capacity": 250000},
    18: {"upgrade_cost": 538500,  "rate": 6.5,  "capacity": 315000},
    19: {"upgrade_cost": 826000,  "rate": 7.25, "capacity": 362500},
    20: {"upgrade_cost": 1125000, "rate": 8.0,  "capacity": 410100},
    21: {"upgrade_cost": 1725000, "rate": 9.0,  "capacity": 487500},
    22: {"upgrade_cost": 2145000, "rate": 10.0, "capacity": 527500},
    23: {"upgrade_cost": 2525000, "rate": 11.0, "capacity": 578000},
    24: {"upgrade_cost": 2950000, "rate": 12.0, "capacity": 645750},
    25: {"upgrade_cost": 3400000, "rate": 13.0, "capacity": 715000},
    26: {"upgrade_cost": 5000000, "rate": 14.25,"capacity": 800000},
    27: {"upgrade_cost": 6125000, "rate": 15.5, "capacity": 910000},
    28: {"upgrade_cost": 7345000, "rate": 16.75,"capacity": 1050000},
    29: {"upgrade_cost": 8532250, "rate": 18.0, "capacity": 1185000},
    30: {"upgrade_cost": 9875000, "rate": 19.25,"capacity": 1345000},
}

RANK_UPGRADE_COSTS = {
    5: 50000,
    10: 250000,
    15: 1500000,
    20: 4250000,
    25: 10000000
}

RANK_NAMES = {
    1: "هاپوی تازه‌کار",
    5: "هاپوی زبل",
    10: "هاپوی زرنگ",
    15: "هاپوی آلفا",
    20: "امپراتور هاپو",
    25: "افسانه هاپویی"
}

def get_rank_name(level: int) -> str:
    current_rank = "هاپوی تازه‌کار"
    for lvl in sorted(RANK_NAMES.keys()):
        if level >= lvl:
            current_rank = RANK_NAMES[lvl]
    return current_rank

# ----------------- توابع کمکی -----------------

def format_balance(amount: int) -> str:
    if amount < 1000:
        return f"{amount} دونه"
    elif amount < 1_000_000:
        return f"{amount} کا"
    elif amount < 1_000_000_000:
        millions = amount / 1_000_000
        if millions.is_integer():
            return f"{int(millions)} میلیون"
        else:
            return f"{millions:.1f} میلیون"
    else:
        billions = amount / 1_000_000_000
        if billions.is_integer():
            return f"{int(billions)} میلیارد"
        else:
            return f"{billions:.1f} میلیارد"

def hops_needed_for_level(level: int) -> int:
    return 10 + (level - 1) * 5

def calculate_hop_reward(level: int) -> int:
    base_min = 10 * (1.5 ** (level - 1))
    base_max = 25 * (1.5 ** (level - 1))
    return random.randint(int(base_min), int(base_max))

# ----------------- توابع اصلی سیستم -----------------

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    target_user = user
    if update.message and update.message.reply_to_message:
        reply_user = update.message.reply_to_message.from_user
        target_user = db.get_user(reply_user.id, reply_user.username or reply_user.first_name)

    user_id = target_user[0]
    username = target_user[1] or "کاربر"
    points = db.get_user_field(user_id, "points") or 0
    level = db.get_user_field(user_id, "level") or 1
    bank_balance = db.get_user_field(user_id, "bank_balance") or 0

    has_dog = db.get_user_field(user_id, "has_dog")
    dog_status = "دارای سگ 🐕" if has_dog else "بدون سگ"
    dog_health = db.get_user_field(user_id, "dog_hunger") or 0
    acc_num = db.get_or_create_account_number(user_id)

    formatted_points = format_balance(points)
    formatted_bank = format_balance(bank_balance)

    msg = (
        f"🐶 **پروفایل و مشخصات هاپو**\n\n"
        f"👤 **کاربر:** `{username}`\n"
        f"🆔 **شناسه:** `{user_id}`\n"
        f"⭐️ **سطح (لول):** {level}\n"
        f"💳 **شماره حساب:** `{acc_num}`\n\n"
        f"💰 **موجودی کیف پول:** {formatted_points}\n"
        f"🏦 **موجودی بانک:** {formatted_bank}\n\n"
        f"🐕 **وضعیت سگ:** {dog_status}\n"
        f"❤️ **سلامت سگ:** %{dog_health * 10}\n"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id if not user else user[0]
    username = update.effective_user.first_name
    
    last_hop_str = db.get_user_field(user_id, "last_hop")
    now = datetime.now()
    COOLDOWN_MINUTES = 5
    
    if last_hop_str:
        try:
            last_hop_time = datetime.strptime(last_hop_str, "%Y-%m-%d %H:%M:%S")
            time_passed = now - last_hop_time
            
            if time_passed < timedelta(minutes=COOLDOWN_MINUTES):
                remaining = timedelta(minutes=COOLDOWN_MINUTES) - time_passed
                minutes, seconds = divmod(remaining.seconds, 60)
                
                await update.message.reply_text(
                    f"⏳ **صبر کن {username} جان!**\n\n"
                    f"شما تازگی هاپ زدید. برای هاپ بعدی باید **{minutes} دقیقه و {seconds} ثانیه** صبر کنید.",
                    parse_mode='Markdown'
                )
                return
        except Exception:
            pass

    user_level = db.get_user_field(user_id, "level") or 1
    progress = db.get_user_field(user_id, "level_hops_progress") or 0

    reward = calculate_hop_reward(user_level)
    needed = hops_needed_for_level(user_level)
    progress += 1

    db.update_field(user_id, "points", reward, relative=True)
    db.update_field(user_id, "hops", 1, relative=True)
    db.update_field(user_id, "last_hop", now.strftime("%Y-%m-%d %H:%M:%S"), relative=False)

    level_up_msg = ""
    if progress >= needed:
        user_level += 1
        progress = 0
        db.update_field(user_id, "level", 1, relative=True)
        db.update_field(user_id, "level_hops_progress", 0, relative=False)
        level_up_msg = f"\n\n🎉 **تبریک! شما به سطح {user_level} ارتقا یافتید!** 🚀"
    else:
        db.update_field(user_id, "level_hops_progress", progress, relative=False)

    current_points = db.get_user_field(user_id, "points") or 0

    msg = (
        f"🐕 **هاپ با موفقیت انجام شد!**\n\n"
        f"👤 کاربر: {update.effective_user.mention_markdown()}\n"
        f"💰 **پاداش دریافتی:** +{format_balance(reward)}\n"
        f"💳 **موجودی کل:** {format_balance(current_points)}\n"
        f"📊 **پیشرفت سطح {user_level}:** [{progress}/{needed}] هاپ{level_up_msg}\n\n"
        f"⏱ _۵ دقیقه دیگر می‌توانید دوباره هاپ بزنید._"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

# ----------------- بخش اختصاصی سگ -----------------

async def buy_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    
    has_dog = db.get_user_field(user_id, "has_dog")
    if has_dog:
        await update.message.reply_text(
            "قبلا سگ خریداری شده برای دیدن سگ دستور سگ را تایپ کنید."
        )
        return

    cost = 500
    points = db.get_user_field(user_id, "points") or 0

    if points < cost:
        await update.message.reply_text(f"❌ برای خرید سگ به **{cost}** هاپ نیاز دارید!")
        return

    db.update_field(user_id, "points", -cost, relative=True)
    db.update_field(user_id, "has_dog", True, relative=False)
    db.update_field(user_id, "dog_name", "انتخاب نشده ❌", relative=False)
    db.update_field(user_id, "dog_level", 1, relative=False)
    db.update_field(user_id, "dog_hunger", 2, relative=False)
    db.update_field(user_id, "dog_last_claim", int(time.time()), relative=False)
    db.update_field(user_id, "dog_unclaimed_points", 0, relative=False)

    await update.message.reply_text("سگ با موفقیت خریداری شد.")

async def show_dog_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    """نمایش یا به‌روزرسانی پنل اصلی سگ"""
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name
    has_dog = db.get_user_field(user_id, "has_dog")

    if not has_dog:
        await update.message.reply_text("❌ شما هنوز سگ ندارید! با ارسال دستور `خرید سگ` یک سگ بخرید.")
        return

    dog_name = db.get_user_field(user_id, "dog_name") or "انتخاب نشده ❌"
    level = int(db.get_user_field(user_id, "dog_level") or 1)
    hunger = int(db.get_user_field(user_id, "dog_hunger") or 2)
    last_claim = int(db.get_user_field(user_id, "dog_last_claim") or time.time())
    stored_points = float(db.get_user_field(user_id, "dog_unclaimed_points") or 0)

    level_data = DOG_LEVELS.get(level, DOG_LEVELS[30])
    rate = level_data["rate"]
    capacity = level_data["capacity"]

    now = time.time()
    elapsed = now - last_claim
    generated = elapsed * rate
    total_unclaimed = min(capacity, stored_points + generated)

    rank_cost = RANK_UPGRADE_COSTS.get(level, level_data["upgrade_cost"])
    rank_title = get_rank_name(level)

    text = (
        f"🐕 **هاپوی {user_first_name}** 🐕\n\n"
        f"💖 **نام :** {dog_name}\n"
        f"🍖 **شکم :** 😿 من گشنمه.. ({hunger} / 10)\n\n"
        f"⭐️ **مقام :** {rank_title} ({level // 5 + 1})\n"
        f"⭐ **سطح :** {level} / 30\n\n"
        f"🪙 **هاپ پوینت‌های تولید شده :** {int(total_unclaimed):,}\n\n"
        f"💫 **تولید هاپ پوینت در ثانیه :** {rate}\n"
        f"💼 **ظرفیت سگ :** {capacity:,}\n\n"
        f"💰 **هزینه ارتقا مقام :** {rank_cost:,}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌀 برداشت هاپ پوینت‌ها", callback_data=f"dog_claim:{user_id}")],
        [InlineKeyboardButton("⭐ ارتقا مقام", callback_data=f"dog_upgrade:{user_id}")],
        [InlineKeyboardButton("❤️ انتخاب اسم سگ", callback_data=f"dog_rename:{user_id}")]
    ])

    try:
        if update.callback_query:
            await update.callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    except RetryAfter:
        pass
    except Exception:
        pass

async def handle_dog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌های پنل سگ"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split(":")[0]

    level = int(db.get_user_field(user_id, "dog_level") or 1)
    last_claim = int(db.get_user_field(user_id, "dog_last_claim") or time.time())
    stored_points = float(db.get_user_field(user_id, "dog_unclaimed_points") or 0)

    level_data = DOG_LEVELS.get(level, DOG_LEVELS[30])
    rate = level_data["rate"]
    capacity = level_data["capacity"]

    # 1. برداشت پوینت‌ها
    if data == "dog_claim":
        now = time.time()
        elapsed = now - last_claim
        generated = elapsed * rate
        total_unclaimed = min(capacity, stored_points + generated)

        if total_unclaimed < 1:
            await query.answer("❌ هنوز پوینتی برای برداشت آماده نشده است!", show_alert=True)
            return

        db.update_field(user_id, "points", int(total_unclaimed), relative=True)
        db.update_field(user_id, "dog_last_claim", int(now), relative=False)
        db.update_field(user_id, "dog_unclaimed_points", 0, relative=False)

        await query.answer(f"✅ مقدار {int(total_unclaimed):,} هاپ پوینت با موفقیت برداشت شد.", show_alert=True)
        await show_dog_panel(update, context)

    # 2. ارتقا مقام (با پیام تبریک ۳ ثانیه‌ای)
    elif data == "dog_upgrade":
        if level >= 30:
            await query.answer("🏆 سگ شما در حداکثر سطح قرار دارد!", show_alert=True)
            return

        cost = RANK_UPGRADE_COSTS.get(level, level_data["upgrade_cost"])
        user_points = int(db.get_user_field(user_id, "points") or 0)

        if user_points < cost:
            await query.answer(f"❌ موجودی کافی نیست! هزینه ارتقا: {cost:,} هاپ پوینت", show_alert=True)
            return

        db.update_field(user_id, "points", -cost, relative=True)
        db.update_field(user_id, "dog_level", level + 1, relative=False)

        await query.answer()

        # ۱. ویرایش پیام به تبریک
        try:
            await query.message.edit_text(
                f"🎉 **تبریک! سگ شما به سطح {level + 1} ارتقا پیدا کرد!**", 
                parse_mode="Markdown"
            )
        except Exception:
            pass

        # ۲. ۳ ثانیه مکث
        await asyncio.sleep(3)

        # ۳. بازگشت به پنل سگ
        await show_dog_panel(update, context)

    # 3. انتخاب اسم سگ
    elif data == "dog_rename":
        await query.answer()
        context.user_data['state'] = "WAITING_FOR_DOG_NAME"
        await query.message.reply_text("🏷 لطفاً نام جدید سگ خود را تایپ و ارسال کنید:")

async def handle_dog_rename_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام جدید، ذخیره آن و باز کردن مجدد پنل سگ"""
    if context.user_data.get('state') == "WAITING_FOR_DOG_NAME":
        new_name = update.message.text.strip()
        user_id = update.effective_user.id
        
        db.update_field(user_id, "dog_name", new_name, relative=False)
        context.user_data['state'] = None
        
        await update.message.reply_text(f"✅ نام سگ با موفقیت به **{new_name}** تغییر یافت.")
        await show_dog_panel(update, context)
        return True
    return False

# ----------------- سایر دستورات -----------------

async def feed_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id if not user else user[0]
    has_dog = db.get_user_field(user_id, "has_dog")
    if not has_dog:
        await update.message.reply_text("❌ شما سگ ندارید! اول با دستور `خرید سگ` یک سگ بخرید.")
        return

    current_hunger = int(db.get_user_field(user_id, "dog_hunger") or 0)
    new_hunger = min(10, current_hunger + 2)
    db.update_field(user_id, "dog_hunger", new_hunger, relative=False)
    await update.message.reply_text("🍖 به سگت غذا دادی و سیرتر شد!")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📜 **راهنمای کامل ربات هاپو مگا**\n\n"
        "📌 **دستورات اصلی:**\n"
        "• `هاپ` : دریافت پوینت رایگان (بر اساس لول - هر ۵ دقیقه)\n"
        "• `پروفایل` یا `هاپوهام` : مشاهده وضعیت حساب و سگ\n\n"
        "🏦 **سیستم بانک و سود ۳%:**\n"
        "• `بانک` : مشاهده پنل شیشه‌ای بانک و شماره حساب\n"
        "• `بانک واریز [مقدار/همه]` : واریز پوینت به بانک\n"
        "• `بانک برداشت [مقدار/همه]` : برداشت پوینت از بانک\n\n"
        "🐕 **سگ و نگهداری:**\n"
        "• `خرید سگ` : خرید سگ جدید\n"
        "• `سگ` : باز کردن پنل اختصاصی سگ و تولید سود\n"
        "• `غذا` : غذا دادن و افزایش سلامت سگ\n\n"
        "💼 **کسب درآمد و اقتصاد:**\n"
        "• `کارخونه` : مشاهده و خرید کارخانه‌ها\n"
        "• `کارخونه من` : مدیریت، برداشت سود و فروش کارخانه\n"
        "• `قاچاق` : کسب سود سریع با ریسک زندان/جریمه\n"
        "• `زندان` : مشاهده وضعیت زندان و پرداخت جریمه\n"
        "• `قمار [مبلغ]` : قمار آنلاین\n"
        "• `شهر` : مشاهده پیشرفت و صندوق توسعه شهر\n"
        "• `اهدا [مبلغ]` : کمک به صندوق شهر\n\n"
        "👑 **دستورات ادمین (روی ریپلای):**\n"
        "• `افزایش پوینت [مقدار]`\n"
        "• `کاهش پوینت [مقدار]`\n"
        "• `افزایش لول [مقدار]`\n"
        "• `کاهش لول [مقدار]`\n"
        "• `همگانی [متن]` : ارسال پیام به تمام اعضا"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
