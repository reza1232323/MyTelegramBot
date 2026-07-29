from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def city_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏙️ **اطلاعات شهر:**\nشهردار: تعیین نشده\nبحران فعال: ندارد\nوضعیت: پایدار", parse_mode='Markdown')

async def smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if user[4] < 4:
        await update.message.reply_text("❌ ورود به قاچاق نیاز به **سطح ۴** دارد!")
        return
    await update.message.reply_text("🕵️ عملیات قاچاق با موفقیت انجام شد! +۱۵۰ هاپ دریافت کردید.")
    db.update_field(user[0], "points", 150)