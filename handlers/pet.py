from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    username = user[1] or "کاربر"
    points = user[2]
    
    # دریافت موجودی انبار از دیتابیس (در صورت وجود)
    diamond = db.get_user_field(user_id, "inventory_diamond") or 0
    cig = db.get_user_field(user_id, "inventory_cig") or 0
    choco = db.get_user_field(user_id, "inventory_choco") or 0
    bank_balance = user[5] if len(user) > 5 else 0

    msg = (
        f"🐶 **پروفایل و مشخصات هاپو:**\n\n"
        f"👤 **صاحب:** {update.effective_user.mention_markdown()}\n"
        f"💰 **موجودی کیف پول:** {points:,} هاپ\n"
        f"🏦 **موجودی بانک:** {bank_balance:,} هاپ\n\n"
        f"📦 **موجودی انبار کارخانه:**\n"
        f"🔹 الماس: {diamond:,} عدد\n"
        f"🔹 سیگار: {cig:,} عدد\n"
        f"🔹 شکلات: {choco:,} عدد\n"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

async def claim_hop(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    reward = 10
    db.update_field(user_id, "points", reward)
    await update.message.reply_text(f"🎉 شما **{reward}** هاپ پوینت دریافت کردید!")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📜 **راهنمای ربات:**\n\n"
        "🔹 `هاپوهام` : مشاهده پروفایل و انبار\n"
        "🔹 `هاپ` : دریافت هاپ روزانه\n"
        "🔹 `کارخونه` : ساخت محصول جدید\n"
        "🔹 `کارخونه من` : مشاهده و مدیریت محصولات انبار\n"
        "🔹 `بانک` : واریز و برداشت پول\n"
        "🔹 `قاچاق` : بازار سیاه قاچاق\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
