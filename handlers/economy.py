from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await update.message.reply_text(f"🏦 موجودی شما در بانک: {user[5]} هاپ")

async def factory_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await update.message.reply_text(f"🏭 **کارخانه شما:**\nسطح: {user[13]}\nدرآمد: {user[14]} هاپ در ساعت")

async def transfer_points(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if user[4] < 2:
        await update.message.reply_text("❌ برای انتقال امتیاز باید حداقل **سطح ۲** باشید!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ لطفاً روی پیام فرد موردنظر ریپلای کنید.")
        return

    try:
        parts = update.message.text.split()
        amount = int(parts[1])
        if amount < 50 or amount > 500000:
            await update.message.reply_text("❌ مبلغ باید بین ۵۰ تا ۵۰۰,۰۰۰ هاپ باشد.")
            return

        if user[2] < amount:
            await update.message.reply_text("❌ موجودی هاپ شما کافی نیست!")
            return

        target_user = update.message.reply_to_message.from_user
        db.update_field(user[0], "points", -amount)
        db.update_field(target_user.id, "points", amount)

        await update.message.reply_text(f"✅ مبلغ {amount} هاپ به @{target_user.username or target_user.first_name} منتقل شد.")
    except:
        await update.message.reply_text("❌ فرمت درست: `انتقال 100` (روی پیام ریپلای کنید)", parse_mode='Markdown')

async def show_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏪 **مارکت عمومی:**\nجهت ثبت آگهی به پیوی ربات مراجعه کنید.")

async def register_market_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ درخواست ثبت آگهی شما به ادمین‌ها ارسال شد.")
