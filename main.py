import logging
import random
import time
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
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
import slot
from slot import slot_bets, handle_slot_bet, handle_slot_sticker

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


# ----------------- توابع عضویت اجباری -----------------
async def check_user_membership(bot, user_id: int) -> bool:
    """بررسی عضویت کاربر در تمامی کانال‌های اجباری"""
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
    """ساخت کیبورد شیشه‌ای عضویت اجباری با دکمه سبز"""
    buttons = []
    
    # دکمه‌های کانال‌ها
    for ch in REQUIRED_CHANNELS:
        buttons.append(
            [InlineKeyboardButton(f"📢 عضویت در {ch['name']}", url=ch["url"])]
        )
    
    # دکمه سبز رنگ برای بررسی عضویت
    buttons.append(
        [
            InlineKeyboardButton(
                "✅ عضو شدم، بررسی کن! 🟢",
                callback_data="check_join_status"
            )
        ]
    )
    
    return InlineKeyboardMarkup(buttons)


async def send_must_join_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """ارسال بنر و پیام عضویت اجباری"""
    user_first_name = update.effective_user.first_name

    channels_list = "\n".join([
        f"• {ch['name']}" for ch in REQUIRED_CHANNELS
    ])

    text = (
        f"⛔️ عزیز {user_first_name}!\n\n"
        f"برای استفاده از ربات هاپ‌داگ، ابتدا باید عضو این کانال‌ها بشی:\n\n"
        f"{channels_list}\n\n"
        f"👇 روی دکمه‌ها کلیک کن، عضو بشو، بعد «عضو شدم» رو بزن:"
    )

    if update.message:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=get_join_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text, parse_mode="Markdown", reply_markup=get_join_keyboard()
        )


# ----------------- سیستم محاسباتی هاپ -----------------
def hops_needed_for_level(level):
    """تعداد هاپ مورد نیاز برای رسیدن به لول بعدی"""
    return 10 + (level - 1) * 5


def calculate_hop_reward(level):
    """محاسبه سکه پاداش بر اساس لول کاربر"""
    base_min = 10 * (1.5 ** (level - 1))
    base_max = 25 * (1.5 ** (level - 1))
    return random.randint(int(base_min), int(base_max))


# ----------------- دستورات ربات -----------------
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لینک و آمار زیرمجموعه‌گیری کاربر"""
    user_id = update.effective_user.id
    bot_username = context.bot.username

    ref_count = (
        db.get_referral_stats(user_id)
        if hasattr(db, "get_referral_stats")
        else 0
    )
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
        await update.callback_query.message.reply_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "کاربر"

    db.get_user(user_id, username)

    if context.args and context.args[0].isdigit():
        inviter_id = int(context.args[0])

        if hasattr(db, "set_inviter") and db.set_inviter(user_id, inviter_id):
            db.update_field(
                inviter_id, "points", REFERRAL_REWARD, relative=True
            )

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
            ["🎰 اسلات", "📖 راهنما"],
        ],
        resize_keyboard=True,
    )

    inline_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👥 دریافت لینک زیرمجموعه‌گیری",
                callback_data="get_referral_link",
            )
        ]
    ])

    start_text = (
        f"سلام {update.effective_user.first_name} عزیز! 👋\n"
        f"به ربات خوش آمدید.\n\n"
        f"💡 برای گرفتن لینک دعوت می‌توانید از دکمه شیشه‌ای زیر یا دکمه 👥 زیرمجموعه‌گیری در کیبورد استفاده کنید.\n\n"
        f"🎰 برای بازی اسلات از دکمه اسلات استفاده کنید."
    )

    await update.message.reply_text(start_text, reply_markup=main_keyboard)
    await update.message.reply_text(
        "منوی سریع زیرمجموعه‌گیری:", reply_markup=inline_keyboard
    )


async def handle_hop_internal(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user=None
):
    """مدیریت فرایند هاپ در صورتی که در فایل pet.py تابع claim_hop تعریف نشده باشد"""
    user_id = update.effective_user.id
    current_time = int(time.time())

    last_hop_time = db.get_user_field(user_id, "last_hop_time") or 0
    cooldown = 300  # ۵ دقیقه

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
        db.update_field(
            user_id, "level_hops_progress", progress, relative=False
        )

    await update.message.reply_text(
        f"🐕 هاپ! هاپ!\n\n"
        f"💰 پاداش دریافتی: {reward:,} سکه\n"
        f"📊 پیشرفت سطح {level}: [{progress}/{needed}] هاپ{level_up_msg}",
        parse_mode="Markdown",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """ثبت دقیق تمام خطارهای ثبت نشده"""
    logging.error(
        f"خطایی در پردازش رخ داد: {context.error}", exc_info=context.error
    )


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    # بررسی اولویت اول: آیا کاربر در حالت تغییر نام سگ است؟
    if hasattr(pet, "handle_dog_rename_text"):
        is_handled = await pet.handle_dog_rename_text(update, context)
        if is_handled:
            return

    context.args = text.split()[1:]

    if hasattr(economy, "handle_factory_and_smuggle_text"):
        handled = await economy.handle_factory_and_smuggle_text(
            update, context
        )
        if handled:
            return

    username = (
        update.effective_user.username or update.effective_user.first_name
    )
    user = db.get_user(user_id, username)

    clean_text = text.split("@")[0].lower()

    # ۰. اسلات (اولویت بالا)
    if clean_text in ["اسلات", "slot"]:
        await slot.slot_menu(update, context)
        return

    # ۱. عمومی، سگ و زیرمجموعه‌گیری
    if clean_text in ["پروفایل", "هاپوهام", "هاپوهاش", "/profile"]:
        await pet.show_profile(update, context, user)
    elif clean_text in [
        "🐶 پنل سگ",
        "پنل سگ",
        "سگ من",
        "سگ",
        "/dog",
        "/dogpanel",
    ]:
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
    elif clean_text in [
        "👥 زیرمجموعه‌گیری",
        "زیرمجموعه‌گیری",
        "زیرمجموعه",
        "دعوت",
        "رفرال",
        "/referral",
    ]:
        await referral_command(update, context)

    # ۲. اقتصاد، بانک، کارخانه، قاچاق و شهر
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

    # ۳. دستورات ادمین
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


async def callback_router(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "check_join_status":
        is_joined = await check_user_membership(context.bot, user_id)
        if is_joined:
            await query.answer(
                "✅ عضویت شما تایید شد. از ربات استفاده کنید!", show_alert=True
            )
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.answer(
                "❌ هنوز در تمامی کانال‌ها عضو نشده‌اید!", show_alert=True
            )
        return

    # ===== بخش اسلات =====
    if data == "slot_start":
        await slot.slot_start_callback(update, context)
        return

    if data.startswith("slot_send_sticker_"):
        await slot.slot_send_sticker_callback(update, context)
        return

    if data == "slot_cancel":
        await slot.slot_cancel_callback(update, context)
        return

    if ":" in data:
        parts = data.split(":")
        action = parts[0]
        owner_id = int(parts[1]) if parts[1].isdigit() else None

        if owner_id and user_id != owner_id:
            await query.answer(
                "❌ این پنل برای شما نیست! لطفا خودتان دستور را ارسال کنید.",
                show_alert=True,
            )
            return
    else:
        action = data

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await query.answer(
            "❌ ابتدا باید در کانال‌های اجباری عضو شوید!", show_alert=True
        )
        await send_must_join_message(update, context)
        return

    # مدیریت دکمه شیشه‌ای زیرمجموعه‌گیری
    if action == "get_referral_link":
        await referral_command(update, context)
        await query.answer()

    # مدیریت تصمیم‌گیری صید ماهی (فروش طعمه یا غذادادن)
    elif action in ["fish_sell", "fish_feed"]:
        if hasattr(pet, "handle_fish_callback"):
            await pet.handle_fish_callback(update, context)
        else:
            await query.answer()

    # مدیریت کلیک‌های مربوط به پنل سگ
    elif (
        action.startswith("dog_")
        or action.startswith("pet_")
        or action == "dog_panel"
    ):
        if hasattr(pet, "handle_dog_callback"):
            await pet.handle_dog_callback(update, context)
        elif hasattr(pet, "dog_callback"):
            await pet.dog_callback(update, context)
        else:
            await query.answer()

    # مدیریت دکمه‌های بانک
    elif action.startswith("bank_"):
        if hasattr(economy, "handle_bank_callback"):
            await economy.handle_bank_callback(update, context)

    # مدیریت دکمه‌های کارخانه
    elif action.startswith("buy_fac_") or action.startswith("fac_"):
        if hasattr(economy, "factory_callback"):
            await economy.factory_callback(update, context)
        elif hasattr(economy, "handle_factory_callback"):
            await economy.handle_factory_callback(update, context)

    # مدیریت دکمه‌های قاچاق
    elif action.startswith("select_contra_") or action in [
        "start_smuggling",
        "pay_bail",
    ]:
        if hasattr(economy, "handle_smuggle_callback"):
            await economy.handle_smuggle_callback(update, context)

    # مدیریت فروش محصولات
    elif action.startswith("sell_"):
        if hasattr(economy, "sell_callback"):
            await economy.sell_callback(update, context)

    # مدیریت شرکت در قمار
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

    app.add_handler(CommandHandler("start", start_command))
    if hasattr(economy, "bank_status"):
        app.add_handler(CommandHandler("bank", economy.bank_status))
    app.add_handler(CommandHandler(["referral", "sub"], referral_command))

    # هندلر استیکر برای اسلات
    app.add_handler(MessageHandler(filters.Sticker.ALL, slot.handle_slot_sticker))

    # هندلر متن برای اسلات (دریافت مبلغ شرط)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_slot_bet))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🤖 Bot is active...")
    app.run_polling()


if __name__ == "__main__":
    main()
