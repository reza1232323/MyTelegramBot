# test.py
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ ربات کار میکنه! عشقم 😍")

def main():
    print("🚀 ربات تست در حال اجرا...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ ربات روشن شد!")
    app.run_polling()

if __name__ == "__main__":
    main()
