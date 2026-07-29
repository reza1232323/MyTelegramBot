import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)
import config
import database as db
from handlers import pet, economy, admin

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 ربات هاپو مگا فعال است!")

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    user = db.get_user(user_id, username)

    # 📌 ۱. عمومی و سگ
    if text in ["پروفایل", "هاپوهام", "هاپوهاش"]:
        await pet.show_profile(update, context, user)
    elif text in ["هاپ", "hop"]:
        await pet.claim_hop(update, context, user)
    elif text in ["راهنما", "help"]:
        await pet.show_help(update, context)
    elif text == "خرید سگ":
        await pet.buy_dog(update, context, user)
    elif text == "غذا":
        await pet.feed_dog(update, context, user)

    # 🏦 ۲. بانک، اقتصاد و بازی‌ها
    elif text.startswith("بانک"):
        await economy.bank_status(update, context, user)
    elif text == "کارخونه من":
        await economy.show_factory(update, context)
    elif text == "کارخونه":
        await economy.handle_factory(update, context, user)
    elif text == "قاچاق":
        await economy.show_contraband(update, context)
    elif text.startswith("زندان"):
        await economy.jail_status(update, context, user)
    elif text.startswith("قمار"):
        await economy.gamble(update, context, user)
    elif text == "شهر":
        await economy.city_status(update, context, user)
    elif text.startswith("اهدا"):
        await economy.donate_city(update, context, user)

    # 👑 ۳. دستورات ادمین (روی ریپلای)
    elif user_id in config.ADMIN_IDS:
        if text.startswith("افزایش پوینت"):
            await admin.add_points(update, context)
        elif text.startswith("کاهش پوینت"):
            await admin.remove_points(update, context)
        elif text.startswith("افزایش لول"):
            await admin.add_level(update, context)
        elif text.startswith("کاهش لول"):
            await admin.remove_level(update, context)
        elif text.startswith("همگانی"):
            await admin.broadcast(update, context)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data.startswith("bank_"):
        await economy.handle_bank_callback(update, context)
    elif data.startswith("buy_fac_") or data.startswith("fac_"):
        await economy.handle_factory_callback(update, context)

def main():
    db.init_db()
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🤖 Bot is active...")
    app.run_polling()

if __name__ == "__main__":
    main()
