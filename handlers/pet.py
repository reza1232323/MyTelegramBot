import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    
    # دریافت اطلاعات تازه‌ی کاربر از دیتابیس
    current_user = db.get_user(user_id)
    last_hop_str = current_user[17]  # 👈 اصلاح اندیس از ۱۸ به ۱۷ (ستون اصلی last_hop)

    # بررسی تایمر ۵ دقیقه‌ای (۳۰۰ ثانیه)
    if last_hop_str:
        try:
            last_hop = datetime.fromisoformat(last_hop_str)
            time_passed = datetime.now() - last_hop
            
            if time_passed < timedelta(minutes=5):
                rem_seconds = int((timedelta(minutes=5) - time_passed).total_seconds())
                mins, secs = divmod(rem_seconds, 60)
                
                if mins > 0:
                    time_msg = f"{mins} دقیقه و {secs} ثانیه"
                else:
                    time_msg = f"{secs} ثانیه"
                    
                await update.message.reply_text(f"⏳ **صبر کن هاپو!** {time_msg} دیگر دوباره بزن.")
                return
        except Exception as e:
            print(f"Error checking hop timer: {e}")

    # اضافه کردن پوینت و ثبت زمان جدید
    reward = random.randint(10, 50)
    db.update_field(user_id, "points", reward)
    db.update_last_hop(user_id)  # ذخیره زمان فعلی در ستون last_hop
    db.update_city("total_hops", 1)

    leveled_up, new_lvl = db.check_level_up(user_id)
    
    # دریافت موجودی به‌روزرسانی‌شده
    updated_user = db.get_user(user_id)
    total_points = updated_user[2]
    current_level = updated_user[4]

    # قالب‌بندی پیام خروجی
    msg = (
        f"➕ **{reward:,} هاپ دریافت کردی!**\n"
        f"💰 **موجودی کل:** {total_points:,} هاپ\n"
        f"⭐ **سطح فعلی:** {current_level}"
    )

    if leveled_up:
        msg += f"\n\n🎉 **تبریک!** شما به لول {new_lvl} ارتقا یافتید!"

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
