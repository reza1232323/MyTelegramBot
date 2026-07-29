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
        await update.message.reply_text(f"👑 مقدار **{val}** پوینت به کاربر اضافه شد.", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ فرمت درست: `افزایش پوینت 100` (روی ریپلای)", parse_mode='Markdown')

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید.")
        return
    try:
        val = int(update.message.text.split()[2])
        target_id = update.message.reply_to_message.from_user.id
        db.update_field(target_id, "points", -val)
        await update.message.reply_text(f"👑 مقدار **{val}** پوینت از کاربر کم شد.", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ فرمت درست: `کاهش پوینت 100` (روی ریپلای)", parse_mode='Markdown')

async def add_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید.")
        return
    try:
        val = int(update.message.text.split()[2])
        target_id = update.message.reply_to_message.from_user.id
        db.update_field(target_id, "level", val)
        await update.message.reply_text(f"👑 **{val}** سطح (لول) به کاربر اضافه شد.", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ فرمت درست: `افزایش لول 1` (روی ریپلای)", parse_mode='Markdown')

async def remove_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید.")
        return
    try:
        val = int(update.message.text.split()[2])
        target_id = update.message.reply_to_message.from_user.id
        db.update_field(target_id, "level", -val)
        await update.message.reply_text(f"👑 **{val}** سطح (لول) از کاربر کم شد.", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text("❌ فرمت درست: `کاهش لول 1` (روی ریپلای)", parse_mode='Markdown')

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("همگانی", "").strip()
    if not text:
        await update.message.reply_text("❌ لطفاً متن پیام همگانی را بنویسید.\nمثال: `همگانی سلام به همه!`", parse_mode='Markdown')
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
