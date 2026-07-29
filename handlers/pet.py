import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    
    # گرفتن آخرین اطلاعات کاربر مستقیم از دیتابیس
    current_user = db.get_user(user_id)
    last_hop_str = current_user[18] # ستون درست last_hop

    # ۱. بررسی تایمر ۵ دقیقه‌ای
    if last_hop_str:
        try:
            last_hop_time = datetime.fromisoformat(last_hop_str)
            time_passed = datetime.now() - last_hop_time
            five_minutes = timedelta(minutes=5)

            if time_passed < five_minutes:
                remaining_seconds = int((five_minutes - time_passed).total_seconds())
                mins = remaining_seconds // 60
                secs = remaining_seconds % 60
                await update.message.reply_text(
                    f"⏳ **هنوز زوده!**\nلطفاً **{mins} دقیقه و {secs} ثانیه** دیگر صبر کنید.",
                    parse_mode='Markdown'
                )
                return
        except Exception:
            pass

    # ۲. محاسبه پاداش رندوم (بین ۱۰ تا ۵۰ هاپ)
    random_points = random.randint(10, 50)
    
    # شانس دریافت جم (۱۰٪ شانس)
    bonus_gem = 0
    gem_msg = ""
    if random.randint(1, 10) == 1:
        bonus_gem = 1
        db.update_field(user_id, "gems", 1)
        gem_msg = "\n💎 **شانس آوردی! ۱ عدد جم هم پیدا کردی!**"

    # بروزرسانی امتیاز و زمان دریافت
    db.update_field(user_id, "points", random_points)
    db.update_last_hop(user_id)

    # ۳. بررسی ارتقای لول
    leveled_up, new_level = db.check_level_up(user_id)
    
    level_msg = ""
    if leveled_up:
        level_msg = f"\n🎉 **تبریک! شما به سطح {new_level} ارتقا یافتید!** 🌟"

    # گرفتن موجودی جدید
    updated_user = db.get_user(user_id)

    msg = (
        f"🐾 **+ {random_points} هاپ** دریافت کردی!{gem_msg}{level_msg}\n\n"
        f"🪙 **موجودی کل:** {updated_user[2]} هاپ\n"
        f"⭐ **سطح فعلی:** {updated_user[4]}"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    msg = (
        f"👤 **پروفایل {user[1] or 'کاربر'}**\n\n"
        f"🪙 **هاپ:** {user[2]} | 💎 **جم:** {user[3]}\n"
        f"⭐ **سطح (لول):** {user[4]} | 🏦 **بانک:** {user[5]}\n"
        f"🐕 **نژاد هاپو:** {user[10]} (سطح {user[6]})\n"
        f"❤️ **سلامتی:** {user[7]}% | 😊 **خوشحالی:** {user[8]}%"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_target_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر مورد نظر ریپلای کنید!")
        return
    
    target = update.message.reply_to_message.from_user
    t_user = db.get_user(target.id, target.username)
    await show_profile(update, context, t_user)

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = db.get_top_players()
    res = "🏆 **جدول برترین‌های هاپو:**\n\n"
    for idx, row in enumerate(top, 1):
        res += f"{idx}. @{row[0] or 'کاربر'} - 🪙 {row[1]} هاپ (سطح {row[2]})\n"
    await update.message.reply_text(res, parse_mode='Markdown')

async def dog_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await update.message.reply_text(
        f"🐕 **وضعیت هاپو شما:**\n"
        f"سلامتی: {user[7]}%\nخوشحالی: {user[8]}%\nگرسنگی: {user[9]}%\n"
        f"برای غذا دادن کلمه `غذا` را ارسال کنید."
    )

async def fish_bone(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    caught = random.randint(1, 4) * user[11]
    db.update_field(user[0], "bones", caught)
    await update.message.reply_text(f"🎣 شما با قلاب لول {user[11]} موفق به صید {caught} استخوان شدید!")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 **راهنمای جامع ربات هاپو**\n\n"
        "🔹 **دستورات اصلی:**\n"
        "`هاپ` - دریافت امتیاز رندوم (هر ۵ دقیقه)\n"
        "`هاپوهام` - مشاهده پروفایل خود\n"
        "`هاپ هاش` - مشاهده پروفایل کاربر (با ریپلای)\n"
        "`لیدربرد` - لیست ۱۰ بازیکن برتر\n\n"
        "🔹 **اقتصاد و شهر:**\n"
        "`بانک` - حساب بانکی | `کارخونه` - مدیریت تولید\n"
        "`انتقال [مبلغ]` (روی ریپلای) - انتقال هاپ\n"
        "`مارکت` - بازار خرید و فروش\n"
        "`شهر` - وضعیت شهر | `قاچاق` - انجام قاچاق\n\n"
        "🔹 **سرگرمی:**\n"
        "`گردونه` - گردونه شانس | `تاس` - انداختن تاس"
    )
    await update.message.reply_text(text, parse_mode='Markdown')
