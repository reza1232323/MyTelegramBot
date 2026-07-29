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

    # 👑 دستورات ادمین
    if user_id in config.ADMIN_IDS:
        if text.startswith("افزایش پوینت"):
            await admin.add_points(update, context); return
        elif text.startswith("کاهش پوینت"):
            await admin.remove_points(update, context); return
        elif text.startswith("افزایش لول"):
            await admin.add_level(update, context); return
        elif text.startswith("کاهش لول"):
            await admin.remove_level(update, context); return
        elif text.startswith("همگانی"):
            await admin.broadcast_message(update, context); return

    # 🎮 دستورات عمومی و سگ
    if text in ["هاپ", "hop"]: 
        await pet.claim_hop(update, context, user)
    elif text in ["هاپوهام", "پروفایل", "profile"]: 
        await pet.show_profile(update, context, user)
    elif text in ["راهنما", "help"]: 
        await pet.show_help(update, context)
    elif text in ["خرید سگ", "ارتقا سگ"]: 
        await pet.buy_dog(update, context, user)
    elif text in ["غذا", "غذا دادن"]: 
        await pet.feed_dog(update, context, user)

    # 💼 دستورات اقتصادی، بازی و شهر
    elif text.startswith("بانک"): 
        await economy.bank_status(update, context, user)
    elif text.startswith("کارخونه"): 
        await economy.handle_factory(update, context, user)
    elif text.startswith("قاچاق"): 
        await economy.handle_smuggle(update, context, user)
    elif text.startswith("قمار"): 
        await games.start_gambling(update, context, user)
    elif text == "شهر": 
        await city.show_city(update, context)
    elif text.startswith("اهدا"): 
        await city.donate_to_city(update, context, user)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("join_gamble:"):
        await games.handle_gamble_callback(update, context)
    elif data.startswith("bank_"):
        await economy.handle_bank_callback(update, context)
    elif data.startswith("buy_factory_"):
        await economy.handle_factory_callback(update, context)
    elif data.startswith("smuggle_"):
        await economy.handle_smuggle_callback(update, context)

def main():
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, router))
    app.add_handler(CallbackQueryHandler(callback_router))
    print("🤖 Hapo Mega Bot Started...")
    app.run_polling()

if __name__ == '__main__':
    main()
