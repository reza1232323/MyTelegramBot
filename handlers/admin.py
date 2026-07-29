from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("همگانی", "").strip()
    if not text:
        await update.message.reply_text("❌ لطفاً متن پیام همگانی را بنویسید.\nمثال: `همگانی سلام به همه بازیکنان!`", parse_mode='Markdown')
        return

    all_users = db.get_all_user_ids()
    sent = 0
    failed = 0

    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **پیام مدیریت:**\n\n{text}", parse_mode='Markdown')
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"✅ **ارسال همگانی به پایان رسید.**\nموفق: {sent} کاربر\nناموفق (بلاک ربات): {failed} کاربر")
