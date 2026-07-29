import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip()
    parts = text.split()

    if text == "قاچاق":
        msg = (
            "🕵️ **منوی قاچاق هاپویی**\n\n"
            "۱. `قاچاق لباس` (سود: ۲۰۰ تا ۵۰۰ | ریسک: کم)\n"
            "۲. `قاچاق وسایل` (سود: ۸۰۰ تا ۲۰۰۰ | ریسک: بالا)\n\n"
            "⚠️ در صورت گیر افتادن، ۱۵ دقیقه به **زندان** می‌افتید یا ۲۰,۰۰۰ هاپ جریمه می‌شوید!"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    type_smuggle = parts[1] if len(parts) > 1 else ""
    
    if type_smuggle == "لباس":
        risk = random.randint(1, 10)
        if risk <= 3: # ۳۰ درصد احتمال گیر افتادن
            jail_time = (datetime.now() + timedelta(minutes=15)).isoformat()
            db.update_field(user_id, "in_jail_until", jail_time, relative=False)
            await update.message.reply_text("🚔 **شرطه هاپویی شما رو گرفت!**\nبه مدت ۱۵ دقیقه افتادید زندان و هیچ دستوری براتون کار نمی‌کنه!")
        else:
            profit = random.randint(200, 500)
            db.update_field(user_id, "points", profit)
            await update.message.reply_text(f"✅ قاچاق لباس موفقیت‌آمیز بود! +{profit} هاپ سود کردید.")

    elif type_smuggle == "وسایل":
        risk = random.randint(1, 10)
        if risk <= 6: # ۶۰ درصد احتمال گیر افتادن
            if user[2] >= 20000:
                db.update_field(user_id, "points", -20000)
                await update.message.reply_text("🚨 **لو رفتید!** مبلغ ۲۰,۰۰۰ هاپ جریمه پرداخت کردید تا به زندان نروید!")
            else:
                jail_time = (datetime.now() + timedelta(minutes=15)).isoformat()
                db.update_field(user_id, "in_jail_until", jail_time, relative=False)
                await update.message.reply_text("🚔 **جریمه رو نداشتید و ۱۵ دقیقه افتادید زندان!**")
        else:
            profit = random.randint(800, 2000)
            db.update_field(user_id, "points", profit)
            await update.message.reply_text(f"🤑 **قاچاق وسایل سنگین موفق بود!** +{profit} هاپ سود کردید!")

async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip()

    if text == "کارخونه":
        msg = (
            f"🏭 **کارخانه شما:** {user[14]}\n\n"
            "👇 **انواع کارخانه‌های قابل خرید:**\n"
            "• `خرید کارخونه لباس` (هزینه: ۲۰۰ هاپ | سود روزانه شانسی)\n"
            "• `خرید کارخونه غذا` (هزینه: ۵۰۰ هاپ | سود روزانه عالی)\n"
            "• `خرید کارخونه اسباب‌بازی` (هزینه: ۱۰۰۰ هاپ | سود فوق‌العاده)"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if text.startswith("خرید کارخونه"):
        ftype = text.replace("خرید کارخونه", "").strip()
        costs = {"لباس": 200, "غذا": 500, "اسباب‌بازی": 1000}
        
        if ftype in costs:
            cost = costs[ftype]
            if user[2] < cost:
                await update.message.reply_text(f"❌ برای خرید این کارخانه به {cost} هاپ نیاز دارید.")
                return
            db.update_field(user_id, "points", -cost)
            db.update_field(user_id, "factory_type", f"کارخانه {ftype}", relative=False)
            await update.message.reply_text(f"🎉 **کارخانه {ftype} خریداری شد!** سود روزانه به صورت خودکار اعمال می‌شود.")

async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    current_user = db.get_user(user[0])
    text = update.message.text.strip()
    parts = text.split()
    
    if text == "بانک":
        await update.message.reply_text(f"🏦 **موجودی کیف پول:** {current_user[2]}\n💳 **موجودی بانک:** {current_user[5]}\n\nراهنما:\n`بانک واریز 100`\n`بانک برداشت 100`", parse_mode='Markdown')
        return

    if len(parts) >= 3 and parts[1] == "واریز":
        amt = current_user[2] if parts[2] == "همه" else int(parts[2])
        if current_user[2] >= amt and amt > 0:
            db.update_field(user[0], "points", -amt)
            db.update_field(user[0], "bank_balance", amt)
            await update.message.reply_text(f"✅ {amt} هاپ به بانک واریز شد.")
    elif len(parts) >= 3 and parts[1] == "برداشت":
        amt = current_user[5] if parts[2] == "همه" else int(parts[2])
        if current_user[5] >= amt and amt > 0:
            db.update_field(user[0], "bank_balance", -amt)
            db.update_field(user[0], "points", amt)
            await update.message.reply_text(f"✅ {amt} هاپ از بانک برداشت شد.")
