import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ========== توکن رو مستقیم از کد بخون ==========
TOKEN = "8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات روشن شد! 🎉")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("🤖 ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
