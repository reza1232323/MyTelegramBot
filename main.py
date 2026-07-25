# test.py
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# 🔑 توکن خودت رو اینجا بذار
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ ربات کار می‌کند! به ربات خفن خوش آمدید!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 یک ربات ساده برای تست")

def main():
    print("🚀 ربات در حال اجرا...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    print("✅ ربات روشن شد! به ربات پیام بدید...")
    app.run_polling()

if __name__ == "__main__":
    main()
