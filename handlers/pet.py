import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    last_hop_str = user[18]

    # بررسی تایمر ۱ دقیقه‌ای
    if last_hop_str:
        last_hop = datetime.fromisoformat(last_hop_str)
        if datetime.now() - last_hop < timedelta(minutes=1):
            rem = timedelta(minutes=1) - (datetime.now() - last_hop)
            await update.message.reply_text(f"⏳ **صبر کن هاپو!** {rem.seconds} ثانیه دیگر دوباره بزن.")
            return

    reward = random.randint(10, 50)
    db.update_field(user_id, "points", reward)
    db.update_last_hop(user_id)
    db.update_city("total_hops", 1)

    leveled_up, new_lvl = db.check_level_up(user_id)
    
    # دریافت آخرین اطلاعات به‌روزرسانی‌شده کاربر
    current_user = db.get_user(user_id)
    total_points = current_user[2]
    current_level = current_user[4]

    # قالب‌بندی جدید
    msg = (
        f"➕ **{reward:,} هاپ دریافت کردی!**\n"
        f"💰 **موجودی کل:** {total_points:,} هاپ\n"
        f"⭐ **سطح فعلی:** {current_level}"
    )

    if leveled_up:
        msg += f"\n\n🎉 **تبریک!** شما به لول {new_lvl} ارتقا یافتید!"

    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    acc_num = db.get_or_create_account_number(user[0])
    msg = (
        f"👤 **پروفایل کاربر:** {user[1]}\n\n"
        f"🪙 **موجودی کیف:** {user[2]:,} هاپ پوینت\n"
        f"🏦 **موجودی بانک:** {user[5]:,} هاپ پوینت\n"
        f"💳 **شماره حساب:** `{acc_num}`\n"
        f"⭐ **سطح (لول):** {user[4]}\n\n"
        f"🐶 **سگ:** لول {user[6]} ({user[10]})\n"
        f"🍗 **غذا:** {user[9]}% | ❤️ **سلامت:** {user[7]}%\n"
        f"🏭 **کارخانه:** {user[14]}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def buy_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    cost = (user[6] + 1) * 100
    if user[2] < cost:
        await update.message.reply_text(f"❌ شما به {cost} هاپ پوینت برای ارتقا سگ نیاز دارید.")
        return

    db.update_field(user_id, "points", -cost)
    db.update_field(user_id, "dog_level", 1)
    db.update_city("total_dogs", 1)
    await update.message.reply_text(f"🎉 سگ شما ارتقا یافت به لول {user[6] + 1}!")

async def feed_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    if user[2] < 20:
        await update.message.reply_text("❌ برای غذا دادن به ۲۰ هاپ پوینت نیاز دارید.")
        return

    db.update_field(user_id, "points", -20)
    db.update_field(user_id, "dog_hunger", 30)
    db.update_field(user_id, "dog_health", 10)
    await update.message.reply_text("🍖 به سگتون غذا دادید! سیرتر و شاداب‌تر شد.")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 **راهنمای کامل ربات هاپو مگا**\n\n"
        "🎮 **دستورات اصلی:**\n"
        "• `هاپ` 👈 دریافت پوینت رایگان (هر ۱ دقیقه)\n"
        "• `پروفایل` یا `هاپوهام` 👈 مشاهده وضعیت حساب و سگ\n\n"
        "🏦 **سیستم بانک و سود ۳٪:**\n"
        "• `بانک` 👈 مشاهده پنل شیشه‌ای بانک و شماره حساب\n"
        "• `بانک واریز [مقدار/همه]` 👈 واریز پوینت به بانک\n"
        "• `بانک برداشت [مقدار/همه]` 👈 برداشت پوینت از بانک\n"
        "• (دکمه **دریافت سود** در پنل بانک هر ۲۴ ساعت ۳٪ سود می‌دهد)\n\n"
        "🐕 **سگ و نگهداری:**\n"
        "• `ارتقا سگ` 👈 افزایش لول سگ\n"
        "• `غذا` 👈 غذا دادن و افزایش سلامت سگ\n\n"
        "💼 **کسب درآمد و اقتصاد:**\n"
        "• `کارخونه` 👈 مشاهده و خرید کارخانه‌های مختلف\n"
        "• `قاچاق` 👈 کسب سود سریع با ریسک زندان/جریمه\n"
        "• `قمار [مبلغ]` 👈 قمار آنلاین با سایر اعضای گروه\n"
        "• `شهر` 👈 مشاهده پیشرفت و صندوق مالی شهر\n"
        "• `اهدا [مبلغ]` 👈 کمک به صندوق توسعه شهر\n\n"
        "👑 **دستورات ادمین (روی ریپلای):**\n"
        "• `افزایش پوینت [مقدار]`\n"
        "• `کاهش پوینت [مقدار]`\n"
        "• `افزایش لول [مقدار]`\n"
        "• `کاهش لول [مقدار]`\n"
        "• `همگانی [متن]` 👈 ارسال پیام به تمام اعضا"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')
