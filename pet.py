import random
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    db.update_field(user[0], "points", 25)
    await update.message.reply_text(f"🐾 +۲۵ هاپ دریافت کردید!\nموجودی جدید: {user[2] + 25}")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    msg = (
        f"👤 **پروفایل {user[1]}**\n\n"
        f"🪙 **هاپ:** {user[2]} | 💎 **جم:** {user[3]}\n"
        f"⭐ **لول:** {user[4]} | 🏦 **بانک:** {user[5]}\n"
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
    caught = random.randint(1, 4) * user[11] # لول قلاب
    db.update_field(user[0], "bones", caught)
    await update.message.reply_text(f"🎣 شما با قلاب لول {user[11]} موفق به صید {caught} استخوان شدید!")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 **راهنمای جامع ربات هاپو**\n\n"
        "🔹 **دستورات اصلی:**\n"
        "`هاپ` - دریافت امتیاز رایگان\n"
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