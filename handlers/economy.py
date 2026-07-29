from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip()
    
    # گرفتن آخرین وضعیت کاربر
    current_user = db.get_user(user_id)
    wallet = current_user[2] # موجودی کیف پول (هاپ)
    bank = current_user[5]   # موجودی بانک

    parts = text.split()
    
    # اگر فقط کلمه "بانک" فرستاده شد
    if text == "بانک":
        msg = (
            f"🏦 **حساب بانکی شما**\n\n"
            f"🪙 **موجودی کیف پول:** {wallet} هاپ\n"
            f"💳 **موجودی در بانک:** {bank} هاپ\n\n"
            f"👇 **راهنمای استفاده:**\n"
            f"• جهت واریز: `بانک واریز 100`\n"
            f"• جهت برداشت: `بانک برداشت 100`\n"
            f"• واریز همه موجودی: `بانک واریز همه`"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    # واریز به بانک
    if len(parts) >= 3 and parts[1] == "واریز":
        if parts[2] == "همه":
            amount = wallet
        else:
            try:
                amount = int(parts[2])
            except ValueError:
                await update.message.reply_text("❌ لطفاً مبلغ را به عدد وارد کنید. مثال: `بانک واریز 100`", parse_mode='Markdown')
                return

        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از ۰ باشد.")
            return

        if wallet < amount:
            await update.message.reply_text(f"❌ موجودی کیف پول شما کافی نیست! (موجودی فعلی: {wallet} هاپ)")
            return

        # کسر از کیف پول و اضافه به بانک
        db.update_field(user_id, "points", -amount)
        db.update_field(user_id, "bank_balance", amount)
        await update.message.reply_text(f"✅ مبلغ **{amount}** هاپ با موفقیت به حساب بانکی شما واریز شد. 🏦", parse_mode='Markdown')

    # برداشت از بانک
    elif len(parts) >= 3 and parts[1] == "برداشت":
        if parts[2] == "همه":
            amount = bank
        else:
            try:
                amount = int(parts[2])
            except ValueError:
                await update.message.reply_text("❌ لطفاً مبلغ را به عدد وارد کنید. مثال: `بانک برداشت 100`", parse_mode='Markdown')
                return

        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از ۰ باشد.")
            return

        if bank < amount:
            await update.message.reply_text(f"❌ موجودی بانک شما کافی نیست! (موجودی بانک: {bank} هاپ)")
            return

        # کسر از بانک و اضافه به کیف پول
        db.update_field(user_id, "bank_balance", -amount)
        db.update_field(user_id, "points", amount)
        await update.message.reply_text(f"✅ مبلغ **{amount}** هاپ از بانک برداشت و به کیف پول شما منتقل شد. 🪙", parse_mode='Markdown')


async def factory_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await update.message.reply_text(f"🏭 **کارخانه شما:**\nسطح: {user[13]}\nدرآمد: {user[14]} هاپ در ساعت", parse_mode='Markdown')

async def transfer_points(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if user[4] < 2:
        await update.message.reply_text("❌ برای انتقال امتیاز باید حداقل **سطح ۲** باشید!", parse_mode='Markdown')
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
    except Exception:
        await update.message.reply_text("❌ فرمت درست: `انتقال 100` (روی پیام ریپلای کنید)", parse_mode='Markdown')

async def show_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏪 **مارکت عمومی:**\nجهت ثبت آگهی به پیوی ربات مراجعه کنید.", parse_mode='Markdown')

async def register_market_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ درخواست ثبت آگهی شما به ادمین‌ها ارسال شد.")
