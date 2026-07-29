from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید.")
        return
    try:
        val = int(update.message.text.split()[2])
        target_id = update.message.reply_to_message.from_user.id
        db.update_field(target_id, "points", val)
        await update.message.reply_text(f"👑 مقدار {val} پوینت به کاربر اضافه شد.")
    except:
        await update.message.reply_text("❌ مثال: `افزایش پوینت 100`", parse_mode='Markdown')

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید.")
        return
    try:
        val = int(update.message.text.split()[2])
        target_id = update.message.reply_to_message.from_user.id
        db.update_field(target_id, "points", -val)
        await update.message.reply_text(f"👑 مقدار {val} پوینت از کاربر کم شد.")
    except:
        await update.message.reply_text("❌ مثال: `کاهش پوینت 100`", parse_mode='Markdown')