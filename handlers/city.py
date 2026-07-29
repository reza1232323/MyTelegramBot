from telegram import Update
from telegram.ext import ContextTypes
import database as db

def get_progress_bar(current, total):
    ratio = min(current / total, 1.0)
    filled = int(ratio * 5)
    return "▰" * filled + "▱" * (5 - filled)

async def show_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_title = update.effective_chat.title or "شهر هاپو"
    city_data = db.get_city() # treasury, total_hops, total_dogs, total_bones, total_fish

    treasury, hops, dogs, bones, fish = city_data[0], city_data[1], city_data[2], city_data[3], city_data[4]

    msg = (
        f"╮──「  **شهر هاپو**  」\n\n"
        f"┐─  نام : **{chat_title}**\n"
        f"┐─  رتبه جهانی : #1\n"
        f"└─ \n\n"
        f" 📊 **آمار شهر:**\n"
        f"┐─  سطح : 3 / 10\n"
        f"┐─  خزانه : {treasury:,} هاپ\n"
        f"┐─  کل هاپ : {hops:,}\n"
        f"┐─  کل سگ : {dogs:,}\n"
        f"┐─  کل استخوان : {bones:,}\n"
        f"└─  کل ماهی : {fish:,}\n\n"
        f" 📈 **پیشرفت به سطح بعدی:**\n"
        f"┐─  خزانه : {treasury:,} / 60,000  {get_progress_bar(treasury, 60000)}\n"
        f"┐─  هاپ‌های کل : {hops:,} / 400  {get_progress_bar(hops, 400)}\n"
        f"┐─  سگ‌های خریداری شده : {dogs:,} / 35  {get_progress_bar(dogs, 35)}\n"
        f"┐─  استخوان‌ها : {bones:,} / 80  {get_progress_bar(bones, 80)}\n"
        f"└─  ماهی‌ها : {fish:,} / 40  {get_progress_bar(fish, 40)}\n\n"
        f"💡 برای کمک به خزانه بنویسید: `اهدا [مقدار]`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def donate_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    try:
        amt = int(update.message.text.split()[1])
        if user[2] < amt or amt <= 0:
            await update.message.reply_text("❌ موجودی هاپ شما کافی نیست.")
            return
        db.update_field(user[0], "points", -amt)
        db.update_city("treasury", amt)
        await update.message.reply_text(f"🏛️ با تشکر! مبلغ {amt} هاپ به خزانه شهر اهدا شد.")
    except Exception:
        await update.message.reply_text("❌ فرمت درست: `اهدا 100`", parse_mode='Markdown')
