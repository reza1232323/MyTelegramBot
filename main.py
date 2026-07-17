import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! به فروشگاه استارز و تون خوش آمدی!\n\n"
        "💰 قیمت تون: 340 تومن\n"
        "⭐ استارز مستقیم: از 165 تومن\n"
        "📝 استارز رو پست: 4000 تومن هر عدد\n"
        "🎁 گیفت استارزی: از 55 تومن\n\n"
        "برای مشاهده منو، /start رو بزن."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("🤖 ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
