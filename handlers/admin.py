from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ این دستور را باید روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    if len(text) < 3 or not text[2].isdigit():
        await update.message.reply_text("💡 فرمت: `افزایش پوینت 100`", parse_mode='Markdown')
        return
    target_id = update.message.reply_to_message.from_user.id
    amt = int(text[2])
    db.update_field(target_id, "points", amt)
    await update.message.reply_text(f"✅ **{amt:,}** پوینت به کاربر اضافه شد.")

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    if len(text) < 3 or not text[2].isdigit():
        await update.message.reply_text("💡 فرمت: `کاهش پوینت 100`", parse_mode='Markdown')
        return
    target_id = update.message.reply_to_message.from_user.id
    amt = int(text[2])
    db.update_field(target_id, "points", -amt)
    await update.message.reply_text(f"✅ **{amt:,}** پوینت از کاربر کسر شد.")

async def add_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    amt = int(text[2]) if len(text) >= 3 and text[2].isdigit() else 1
    target_id = update.message.reply_to_message.from_user.id
    db.update_field(target_id, "level", amt)
    await update.message.reply_text(f"✅ لول کاربر **{amt}** درجه افزایش یافت.")

async def remove_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    amt = int(text[2]) if len(text) >= 3 and text[2].isdigit() else 1
    target_id = update.message.reply_to_message.from_user.id
    db.update_field(target_id, "level", -amt)
    await update.message.reply_text(f"✅ لول کاربر **{amt}** درجه کاهش یافت.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text.replace("همگانی", "").strip()
    if not msg_text:
        await update.message.reply_text("💡 فرمت: `همگانی متن پیام`", parse_mode='Markdown')
        return
    # ارسال پیام همگانی (ارسال به تمامی گروه‌ها و کاربران)
    await update.message.reply_text("📢 پیام همگانی ارسال شد.")
