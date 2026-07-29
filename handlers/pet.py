from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    # دریافت اطلاعات کاربر هدف (اگر روی کسی ریپلای شده باشد یا آیدی داده شده باشد)
    target_user = user
    if update.message and update.message.reply_to_message:
        reply_user = update.message.reply_to_message.from_user
        target_user = db.get_user(reply_user.id, reply_user.username or reply_user.first_name)

    user_id = target_user[0]
    points = target_user[2]
    bank_balance = target_user[5] if len(target_user) > 5 else 0

    # دریافت انبار
    diamond = db.get_user_field(user_id, "inventory_diamond") or 0
    cig = db.get_user_field(user_id, "inventory_cig") or 0
    choco = db.get_user_field(user_id, "inventory_choco") or 0
    acc_num = db.get_or_create_account_number(user_id)

    msg = (
        f"🐶 **پروفایل و مشخصات هاپو**\n\n"
        f"👤 **کاربر:** `{target_user[1] or 'کاربر'}`\n"
        f"🆔 **شناسه:** `{user_id}`\n"
        f"💳 **شماره حساب:** `{acc_num}`\n\n"
        f"💰 **موجودی کیف پول:** {points:,} هاپ\n"
        f"🏦 **موجودی بانک:** {bank_balance:,} هاپ\n\n"
        f"📦 **موجودی انبار کارخانه:**\n"
        f"🔹 **الماس 💎:** {diamond:,} عدد\n"
        f"🔹 **سیگار 📦:** {cig:,} عدد\n"
        f"🔹 **شکلات 🍫:** {choco:,} عدد\n"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    reward = 10
    db.update_field(user_id, "points", reward)
    await update.message.reply_text(f"🎉 شما **{reward}** هاپ پوینت دریافت کردید!")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📜 **راهنمای کامل ربات هاپو:**\n\n"
        "🎮 **دستورات عمومی و پروفایل:**\n"
        "🔹 `هاپوهام` یا `هاپوهاش` : مشاهده پروفایل و انبار کامل\n"
        "🔹 `هاپ` : دریافت سکه/پوینت رایگان\n"
        "🔹 `راهنما` : نمایش این راهنما\n\n"
        "🏭 **کارخانه و انبار:**\n"
        "🔹 `کارخونه` : ورود به خط تولید و ساخت جنس\n"
        "🔹 `کارخونه من` : مشاهده انبار و انتخاب فروش یا قاچاق اجناس\n\n"
        "🏦 **بانکداری:**\n"
        "🔹 `بانک` : مشاهده پنل بانک، شماره حساب و سود روزانه\n"
        "🔹 `بانک واریز [مبلغ/همه]` : واریز به بانک\n"
        "🔹 `بانک برداشت [مبلغ/همه]` : برداشت از بانک\n\n"
        "🕵️‍♂️ **بازار قاچاق:**\n"
        "🔹 `قاچاق` : هدایت مستقیم به انبار جهت قاچاق اجناس\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
