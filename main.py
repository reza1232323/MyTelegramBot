import logging
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
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

logging.basicConfig(level=logging.INFO)


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لینک و آمار زیرمجموعه‌گیری کاربر"""
    user_id = update.effective_user.id
    bot_username = context.bot.username

    # دریافت آمار زیرمجموعه‌ها از دیتابیس
    ref_count = (
        db.get_referral_stats(user_id)
        if hasattr(db, "get_referral_stats")
        else 0
    )
    total_earned = ref_count * REFERRAL_REWARD
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    text = (
        f"👥 **سیستم دعوت و زیرمجموعه‌گیری**\n\n"
        f"با دعوت دوستان خود به ربات، پاداش دریافت کنید!\n\n"
        f"🎁 **پاداش هر دعوت:** {REFERRAL_REWARD:,} سکه\n"
        f"📊 **تعداد دعوت‌های شما:** {ref_count} نفر\n"
        f"💰 **مجموع درآمد از دعوت:** {total_earned:,} سکه\n\n"
        f"🔗 **لینک اختصاصی شما:**\n"
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

    # دریافت یا ثبت کاربر در دیتابیس
    db.get_user(user_id, username)

    # بررسی اگر کاربر با لینک رفرال آمده باشد
    if context.args and context.args[0].isdigit():
        inviter_id = int(context.args[0])

        # ثبت معرف در دیتابیس (جلوگیری از عضویت تکراری یا خود-دعوتی)
        if hasattr(db, "set_inviter") and db.set_inviter(user_id, inviter_id):
            # واریز پاداش به حساب معرف
            db.update_field(
                inviter_id, "points", REFERRAL_REWARD, relative=True
            )

            # اطلاع‌رسانی به معرف
            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=f"🎉 یک کاربر جدید با لینک شما وارد ربات شد!\n🎁 مبلغ **{REFERRAL_REWARD:,} سکه** به حساب شما اضافه شد.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    # 📌 ساخت کیبورد متنی اصلی ربات (بدون بانک)
    main_keyboard = ReplyKeyboardMarkup(
        [
            ["پروفایل", "هاپ"],
            ["خرید سگ", "غذا"],
            ["کارخونه", "شهر"],
            ["👥 زیرمجموعه‌گیری", "راهنما"],
        ],
        resize_keyboard=True,
    )

    # 📌 ساخت دکمه شیشه‌ای میان‌بر زیر پیام
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
        f"💡 برای گرفتن لینک دعوت می‌توانید از دکمه شیشه‌ای زیر یا دکمه **👥 زیرمجموعه‌گیری** در کیبورد استفاده کنید."
    )

    await update.message.reply_text(
        start_text, reply_markup=main_keyboard
    )
    await update.message.reply_text(
        "منوی سریع زیرمجموعه‌گیری:", reply_markup=inline_keyboard
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """ثبت دقیق تمام خطارهای ثبت نشده برای جلوگیری از کرش"""
    logging.error(
        f"خطایی در پردازش رخ داد: {context.error}", exc_info=context.error
    )


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # 📌 استخراج آرگومان‌ها از متن برای جلوگیری از خطای NoneType در توابع
    context.args = text.split()[1:]

    # بررسی اینکه آیا کاربر در حال ارسال تعداد برای خرید یا قاچاق است
    if hasattr(economy, "handle_factory_and_smuggle_text"):
        handled = await economy.handle_factory_and_smuggle_text(
            update, context
        )
        if handled:
            return

    user_id = update.effective_user.id
    username = (
        update.effective_user.username or update.effective_user.first_name
    )
    user = db.get_user(user_id, username)

    # 📌 ۱. عمومی، سگ و زیرمجموعه‌گیری
    if text in ["پروفایل", "هاپوهام", "هاپوهاش"]:
        await pet.show_profile(update, context, user)
    elif text in ["هاپ", "hop"]:
        await pet.claim_hop(update, context, user)
    elif text in ["راهنما", "help"]:
        await pet.show_help(update, context)
    elif text == "خرید سگ":
        await pet.buy_dog(update, context, user)
    elif text == "غذا":
        await pet.feed_dog(update, context, user)
    elif text in [
        "👥 زیرمجموعه‌گیری",
        "زیرمجموعه‌گیری",
        "زیرمجموعه",
        "دعوت",
        "رفرال",
    ]:
        await referral_command(update, context)

    # 🏦 ۲. اقتصاد، کارخانه، قاچاق و شهر (بدون بانک)
    elif text == "کارخونه":
        await economy.show_factory(update, context)
    elif text == "کارخونه من":
        await economy.show_my_factory(update, context, user)
    elif text in ["فروش", "بازار"]:
        await economy.show_sell_menu(update, context, user)
    elif text in ["قاچاق", "قاچاقچی"]:
        await economy.show_contraband(update, context)
    elif text.startswith("زندان"):
        await economy.jail_status(update, context, user)
    elif text.startswith("قمار"):
        await economy.start_gamble(update, context)
    elif text == "شهر":
        await economy.city_status(update, context, user)
    elif text.startswith("اهدا"):
        await economy.donate_city(update, context, user)

    # 👑 ۳. دستورات ادمین (روی ریپلای)
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
    data = query.data

    # مدیریت دکمه شیشه‌ای زیرمجموعه‌گیری
    if data == "get_referral_link":
        await referral_command(update, context)
        await query.answer()

    elif data.startswith("buy_fac_") or data.startswith("fac_"):
        if hasattr(economy, "factory_callback"):
            await economy.factory_callback(update, context)
        elif hasattr(economy, "handle_factory_callback"):
            await economy.handle_factory_callback(update, context)
    elif data.startswith("select_contra_") or data in [
        "start_smuggling",
        "pay_bail",
    ]:
        if hasattr(economy, "handle_smuggle_callback"):
            await economy.handle_smuggle_callback(update, context)
    elif data.startswith("sell_"):
        if hasattr(economy, "sell_callback"):
            await economy.sell_callback(update, context)


def main():
    db.init_db()

    # افزایش مهلت زمانی درخواست‌ها جهت جلوگیری از خطای TimedOut
    request_config = HTTPXRequest(
        connection_pool_size=8, read_timeout=60.0, write_timeout=60.0
    )

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request_config)
        .build()
    )

    # ثبت Error Handler برای جلوگیری از کرش
    app.add_error_handler(error_handler)

    # ثبت دستگیره‌های ربات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler(["referral", "sub"], referral_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🤖 Bot is active...")
    app.run_polling()


if __name__ == "__main__":
    main()
