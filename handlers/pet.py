from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    target_user = user
    if update.message and update.message.reply_to_message:
        reply_user = update.message.reply_to_message.from_user
        target_user = db.get_user(reply_user.id, reply_user.username or reply_user.first_name)

    user_id = target_user[0]
    username = target_user[1] or "کاربر"
    points = target_user[2]
    bank_balance = target_user[5] if len(target_user) > 5 else 0

    dog_status = db.get_user_field(user_id, "dog_status") or "بدون سگ"
    dog_health = db.get_user_field(user_id, "dog_health") or 0
    acc_num = db.get_or_create_account_number(user_id)

    msg = (
        f"🐶 **پروفایل و مشخصات هاپو**\n\n"
        f"👤 **کاربر:** `{username}`\n"
        f"🆔 **شناسه:** `{user_id}`\n"
        f"💳 **شماره حساب:** `{acc_num}`\n\n"
        f"💰 **موجودی کیف پول:** {points:,} هاپ\n"
        f"🏦 **موجودی بانک:** {bank_balance:,} هاپ\n\n"
        f"🐕 **وضعیت سگ:** {dog_status}\n"
        f"❤️ **سلامت سگ:** %{dog_health}\n"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    # چک کردن زمان ۵ دقیقه در دیتابیس (نمونه ساده)
    reward = 50
    db.update_field(user_id, "points", reward)
    await update.message.reply_text(f"🎉 شما **{reward}** هاپ پوینت دریافت کردید! (۵ دقیقه بعد دوباره امتحان کنید)")

async def buy_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    points = user[2]
    cost = 500

    if points < cost:
        await update.message.reply_text(f"❌ برای خرید سگ به **{cost}** هاپ نیاز دارید!")
        return

    db.update_field(user_id, "points", -cost)
    db.update_field(user_id, "dog_status", "هاپو اصیل 🐕", relative=False)
    db.update_field(user_id, "dog_health", 100, relative=False)
    await update.message.reply_text("🎉 مبارکه! سگ جدید خریدی.")

async def feed_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    dog_status = db.get_user_field(user_id, "dog_status")
    if not dog_status or dog_status == "بدون سگ":
        await update.message.reply_text("❌ شما سگ ندارید! اول با دستور `خرید سگ` یک سگ بخرید.")
        return

    db.update_field(user_id, "dog_health", 20)
    await update.message.reply_text("🍖 به سگت غذا دادی و سلامتش افزایش پیدا کرد!")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📜 **راهنمای کامل ربات هاپو مگا**\n\n"
        "📌 **دستورات اصلی:**\n"
        "• `هاپ` : دریافت پوینت رایگان (هر ۵ دقیقه)\n"
        "• `پروفایل` یا `هاپوهام` : مشاهده وضعیت حساب و سگ\n\n"
        "🏦 **سیستم بانک و سود ۳%:**\n"
        "• `بانک` : مشاهده پنل شیشه‌ای بانک و شماره حساب\n"
        "• `بانک واریز [مقدار/همه]` : واریز پوینت به بانک\n"
        "• `بانک برداشت [مقدار/همه]` : برداشت پوینت از بانک\n"
        "• *(دکمه دریافت سود در پنل بانک هر ۲۴ ساعت ۳% سود می‌دهد)*\n\n"
        "🐕 **سگ و نگهداری:**\n"
        "• `خرید سگ` : خرید سگ جدید\n"
        "• `غذا` : غذا دادن و افزایش سلامت سگ\n\n"
        "💼 **کسب درآمد و اقتصاد:**\n"
        "• `کارخونه` : مشاهده و خرید کارخانه‌های مختلف\n"
        "• `کارخونه من` : مدیریت، برداشت سود و فروش کارخانه\n"
        "• `قاچاق` : کسب سود سریع با ریسک زندان/جریمه\n"
        "• `زندان` : مشاهده وضعیت زندان و پرداخت جریمه\n"
        "• `قمار [مبلغ]` : قمار آنلاین با سایر اعضای گروه\n"
        "• `شهر` : مشاهده پیشرفت و صندوق مالی شهر\n"
        "• `اهدا [مبلغ]` : کمک به صندوق توسعه شهر\n\n"
        "👑 **دستورات ادمین (روی ریپلای):**\n"
        "• `افزایش پوینت [مقدار]`\n"
        "• `کاهش پوینت [مقدار]`\n"
        "• `افزایش لول [مقدار]`\n"
        "• `کاهش لول [مقدار]`\n"
        "• `همگانی [متن]` : ارسال پیام به تمام اعضا"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
