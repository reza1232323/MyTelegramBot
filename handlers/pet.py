import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def check_jail(update: Update, user) -> bool:
    jail_until_str = user[16] # ستون in_jail_until
    if jail_until_str:
        jail_until = datetime.fromisoformat(jail_until_str)
        if datetime.now() < jail_until:
            rem = int((jail_until - datetime.now()).total_seconds() / 60)
            await update.message.reply_text(f"🚨 **شما در زندان هاپویی هستید!**\nتا {rem} دقیقه دیگر به هیچ ویژگی دسترسی ندارید.", parse_mode='Markdown')
            return True
    return False

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if await check_jail(update, user): return

    user_id = user[0]
    current_user = db.get_user(user_id)
    last_hop_str = current_user[17]

    if last_hop_str:
        try:
            last_hop_time = datetime.fromisoformat(last_hop_str)
            time_passed = datetime.now() - last_hop_time
            if time_passed < timedelta(minutes=5):
                rem_sec = int((timedelta(minutes=5) - time_passed).total_seconds())
                await update.message.reply_text(f"⏳ **صبر کنید!** {rem_sec // 60} دقیقه و {rem_sec % 60} ثانیه باقی مانده.")
                return
        except Exception: pass

    random_points = random.randint(10, 50)
    db.update_field(user_id, "points", random_points)
    db.update_last_hop(user_id)
    db.update_city("total_hops", 1)

    # محاسبه درآمد خودکار سگ از آخرین دریافت
    dog_level = current_user[6]
    bonus_msg = ""
    if dog_level > 0:
        income = dog_level * 10
        db.update_field(user_id, "points", income)
        bonus_msg = f"\n🐕 **درآمد سگ شما (سطح {dog_level}):** +{income} هاپ!"

    await update.message.reply_text(f"🐾 **+{random_points} هاپ** دریافت کردی!{bonus_msg}\n🪙 **موجودی:** {db.get_user(user_id)[2]} هاپ")

async def buy_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if await check_jail(update, user): return
    user_id = user[0]
    cost = (user[6] + 1) * 300

    if user[2] < cost:
        await update.message.reply_text(f"❌ موجودی کافی نیست! هزینه ارتقا/خرید سگ: {cost} هاپ")
        return

    db.update_field(user_id, "points", -cost)
    db.update_field(user_id, "dog_level", 1)
    db.update_city("total_dogs", 1)
    await update.message.reply_text(f"🎉 سگ شما با موفقیت به سطح **{user[6] + 1}** ارتقا یافت!\nتولید خودکار: +{(user[6] + 1) * 10} هاپ در هر هاپ‌گیری.", parse_mode='Markdown')

async def feed_dog(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if await check_jail(update, user): return
    user_id = user[0]
    if user[6] == 0:
        await update.message.reply_text("❌ شما هنوز سگ ندارید! برای خرید ارسال کنید: `خرید سگ`", parse_mode='Markdown')
        return

    if user[2] < 200:
        await update.message.reply_text("❌ هزینه غذای سگ ۲۰۰ هاپ پوینت است.")
        return

    db.update_field(user_id, "points", -200)
    db.update_field(user_id, "dog_hunger", 100, relative=False)
    db.update_field(user_id, "dog_health", 100, relative=False)
    await update.message.reply_text("🍖 به سگ خود غذا دادید! گرسنگی رفع شد و سلامتی به ۱۰۰٪ رسید.")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    msg = (
        f"👤 **پروفایل {user[1] or 'کاربر'}**\n\n"
        f"🪙 **هاپ:** {user[2]} | 💎 **جم:** {user[3]}\n"
        f"⭐ **سطح:** {user[4]} | 🏦 **بانک:** {user[5]}\n"
        f"🐕 **سطح سگ:** {user[6]} (تولید: {user[6]*10} هاپ/نوبت)\n"
        f"❤️ **سلامتی سگ:** {user[7]}% | 🍖 **سیر بودن:** {user[8]}%"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')
