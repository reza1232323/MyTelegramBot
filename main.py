import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import config
import database as db
from handlers import economy, games, pet, city, admin

logging.basicConfig(level=logging.INFO)
db.init_db()

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return

    text = update.message.text.strip()
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    user = db.get_user(user_id, username)

    if chat_type == 'private':
        await update.message.reply_text("❌ برای استفاده از من، من را وارد یک گپ کنید!")
        return

    # دستورات
    if text == "هاپ": await pet.claim_hop(update, context, user)
    elif text in ["هاپوهام", "پروفایل"]: await pet.show_profile(update, context, user)
    elif text in ["خرید سگ", "ارتقا سگ"]: await pet.buy_dog(update, context, user)
    elif text in ["غذا", "غذا دادن"]: await pet.feed_dog(update, context, user)
    elif text.startswith("بانک"): await economy.bank_status(update, context, user)
    elif text.startswith("کارخونه"): await economy.handle_factory(update, context, user)
    elif text.startswith("قاچاق"): await economy.handle_smuggle(update, context, user)
    elif text.startswith("قمار"): await games.start_gambling(update, context, user)
    elif text == "شهر": await city.show_city(update, context)
    elif text.startswith("اهدا"): await city.donate_to_city(update, context, user)

    # ادمین
    elif user_id in config.ADMIN_IDS:
        if text.startswith("همگانی"):
            await admin.broadcast_message(update, context)

def main():
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, router))
    app.add_handler(CallbackQueryHandler(games.handle_gamble_callback, pattern="^join_gamble:"))
    print("🤖 Hapo Mega Bot Started...")
    app.run_polling()

if __name__ == '__main__':
    main()
