import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import config
import database as db
from handlers import pet, economy, admin

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    db.get_user(user_id, username)
    await update.message.reply_text("👋 سلام! به ربات هاپویی خوش آمدید. برای استفاده، ربات را به گروه اضافه کنید.")

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # ثبت کاربر در دیتابیس
    user = db.get_user(user_id, username)

    # عدم پاسخ‌دهی به دستورات در پیوی (به جز استارت)
    if chat_type == 'private':
        await update.message.reply_text("❌ برای استفاده از امکانات، ربات را به گروه اضافه کنید!")
        return

    # 🎮 ۱. دستورات عمومی (قابل اجرا برای همه اعضا)
    if text in ["هاپوهام", "هاپو هام", "پروفایل", "profile"]:
        await pet.show_profile(update, context, user)
        return
    elif text in ["هاپ", "hop"]:
        await pet.claim_hop(update, context, user)
        return
    elif text in ["راهنما", "help"]:
        await pet.show_help(update, context)
        return

    # 💼 ۲. اقتصاد و بازار (عمومی)
    if text.startswith("بانک"):
        await economy.bank_status(update, context, user)
        return
    elif text.startswith("کارخونه") or text.startswith("کارخانه"):
        await economy.handle_factory(update, context, user)
        return
    elif text.startswith("قاچاق"):
        await economy.handle_smuggle(update, context, user)
        return

    # 👑 ۳. دستورات ادمین (مخصوص ادمین‌های تنظیم شده در کانفیگ)
    if user_id in config.ADMIN_IDS:
        if text.startswith("افزایش پوینت"):
            await admin.add_points(update, context)
            return
        elif text.startswith("کاهش پوینت"):
            await admin.remove_points(update, context)
            return

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("bank_"):
        await economy.handle_bank_callback(update, context)
    elif data.startswith("buy_factory_"):
        await economy.handle_factory_callback(update, context)
    elif data.startswith("action_"):
        await economy.handle_action_callback(update, context)

def main():
    db.init_db()
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
