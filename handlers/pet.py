from datetime import datetime, timedelta
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
    points = db.get_user_field(user_id, "points") or 0
    level = db.get_user_field(user_id, "level") or 1
    bank_balance = db.get_user_field(user_id, "bank_balance") or 0

    dog_status = db.get_user_field(user_id, "dog_status") or "بدون سگ"
    dog_health = db.get_user_field(user_id, "dog_health") or 0
    acc_num = db.get_or_create_account_number(user_id)

    msg = (
        f"🐶 **پروفایل و مشخصات هاپو**\n\n"
        f"👤 **کاربر:** `{username}`\n"
        f"🆔 **شناسه:** `{user_id}`\n"
        f"⭐️ **سطح (لول):** {level}\n"
        f"💳 **شماره حساب:** `{acc_num}`\n\n"
        f"💰 **موجودی کیف پول:** {points:,} هاپ\n"
        f"🏦 **موجودی بانک:** {bank_balance:,} هاپ\n\n"
        f"🐕 **وضعیت سگ:** {dog_status}\n"
        f"❤️ **سلامت سگ:** %{dog_health}\n"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
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
    base_reward = 50
    reward = user_level * base_reward

    db.update_field(user_id, "points", reward)
    db.update_field(user_id, "last_hop", now.strftime("%Y-%m-%d %H:%M:%S"), relative=False)

    current_points = db.get_user_field(user_id, "points") or 0

    msg = (
        f"🎉 **هاپ با موفقیت انجام شد!**\n\n"
        f"👤 کاربر: {update.effective_user.mention_markdown()}\n"
        f"⭐️ **سطح (لول) شما:** {user_level}\n"
        f"🎁 **پاداش سطح:** +{reward:,} هاپ\n"
        f"💰 **موجودی کل:** {current_points:,} هاپ\n\n"
        f"⏱ _۵ دقیقه دیگر می‌توانید دوباره هاپ بزنید._"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def buy_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    points = db.get_user_field(user_id, "points") or 0
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
        "• `هاپ` : دریافت پوینت رایگان (بر اساس لول - هر ۵ دقیقه)\n"
        "• `پروفایل` یا `هاپوهام` : مشاهده وضعیت حساب و سگ\n\n"
        "🏦 **سیستم بانک و سود ۳%:**\n"
        "• `بانک` : مشاهده پنل شیشه‌ای بانک و شماره حساب\n"
        "• `بانک واریز [مقدار/همه]` : واریز پوینت به بانک\n"
        "• `بانک برداشت [مقدار/همه]` : برداشت پوینت از بانک\n\n"
        "🐕 **سگ و نگهداری:**\n"
        "• `خرید سگ` : خرید سگ جدید\n"
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
