import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip() if update.message else ""
    parts = text.split()
    current_user = db.get_user(user_id)
    wallet = current_user[2]
    bank = current_user[5]

    # ۱. مدیریت دستورات متنی واریز و برداشت مستقیم
    if len(parts) >= 3 and parts[1] == "واریز":
        amt = wallet if parts[2] == "همه" else int(parts[2])
        if amt <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از ۰ باشد.")
            return
        if wallet < amt:
            await update.message.reply_text(f"❌ موجودی کیف پول شما کافی نیست! ({wallet:,} هاپ)")
            return
        db.update_field(user_id, "points", -amt)
        db.update_field(user_id, "bank_balance", amt)
        await update.message.reply_text(f"✅ مبلغ **{amt:,}** هاپ با موفقیت به بانک واریز شد. 🏦", parse_mode='Markdown')
        return

    elif len(parts) >= 3 and parts[1] == "برداشت":
        amt = bank if parts[2] == "همه" else int(parts[2])
        if amt <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از ۰ باشد.")
            return
        if bank < amt:
            await update.message.reply_text(f"❌ موجودی بانک شما کافی نیست! ({bank:,} هاپ)")
            return
        db.update_field(user_id, "bank_balance", -amt)
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"✅ مبلغ **{amt:,}** هاپ از بانک برداشت شد. 🪙", parse_mode='Markdown')
        return

    # ۲. نمایش پنل تصویری شیشه‌ای بانک (در صورت فرستادن کلمه "بانک")
    acc_num = db.get_or_create_account_number(user_id)
    daily_profit = int(bank * 0.03)

    last_claim_str = current_user[20] if len(current_user) > 20 else None
    profit_ready = True
    if last_claim_str:
        try:
            last_claim = datetime.fromisoformat(last_claim_str)
            if datetime.now() - last_claim < timedelta(hours=24):
                profit_ready = False
        except Exception:
            pass

    status_profit = "✅ سود آماده دریافته!" if profit_ready and daily_profit > 0 else "⏳ سود دریافت شده (یا موجودی صفر)"

    msg = (
        f"🏦 **بانک هاپی**\n\n"
        f"💳 **شماره حساب:** `{acc_num}`\n"
        f"💰 **موجودی بانک:** {bank:,} هاپ پوینت\n"
        f"👛 **موجودی کیف:** {wallet:,} هاپ پوینت\n\n"
        f"📈 **سود روزانه (۳%):** {daily_profit:,}\n"
        f"❇️ {status_profit}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ واریز", callback_data="bank_deposit_help"),
            InlineKeyboardButton("➖ برداشت", callback_data="bank_withdraw_help")
        ],
        [
            InlineKeyboardButton("💸 دریافت سود", callback_data="bank_claim_profit")
        ],
        [
            InlineKeyboardButton("🔄 تغییر شماره حساب", callback_data="bank_change_acc")
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')

async def handle_bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if data == "bank_deposit_help":
        await query.message.reply_text("💡 **راهنمای واریز:**\nعبارت زیر را ارسال کنید:\n`بانک واریز 100` یا `بانک واریز همه`", parse_mode='Markdown')
    
    elif data == "bank_withdraw_help":
        await query.message.reply_text("💡 **راهنمای برداشت:**\nعبارت زیر را ارسال کنید:\n`بانک برداشت 100` یا `بانک برداشت همه`", parse_mode='Markdown')

    elif data == "bank_claim_profit":
        bank_bal = user[5]
        daily_profit = int(bank_bal * 0.03)
        if daily_profit <= 0:
            await query.message.reply_text("❌ موجودی بانک شما برای دریافت سود کافی نیست.")
            return

        last_claim_str = user[20] if len(user) > 20 else None
        if last_claim_str:
            try:
                last_claim = datetime.fromisoformat(last_claim_str)
                if datetime.now() - last_claim < timedelta(hours=24):
                    rem = timedelta(hours=24) - (datetime.now() - last_claim)
                    hours, remainder = divmod(rem.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    await query.message.reply_text(f"⏳ **زمان دریافت سود نرسیده!**\n{hours} ساعت و {minutes} دقیقه دیگر مراجعه کنید.")
                    return
            except Exception:
                pass

        db.update_field(user_id, "bank_balance", daily_profit)
        db.update_field(user_id, "last_profit_claim", datetime.now().isoformat(), relative=False)
        await query.message.reply_text(f"🎉 **مبلغ {daily_profit:,} هاپ (سود ۳٪ روزانه)** اضافه شد!")
        await bank_status(update, context, db.get_user(user_id))

    elif data == "bank_change_acc":
        new_acc = str(random.randint(1000000000, 9999999999))
        db.update_field(user_id, "account_number", new_acc, relative=False)
        await query.message.reply_text(f"✅ شماره حساب جدید شما صادر شد:\n`{new_acc}`", parse_mode='Markdown')
        await bank_status(update, context, db.get_user(user_id))

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
        if risk <= 3:
            jail_time = (datetime.now() + timedelta(minutes=15)).isoformat()
            db.update_field(user_id, "in_jail_until", jail_time, relative=False)
            await update.message.reply_text("🚔 **شرطه هاپویی شما رو گرفت!**\nبه مدت ۱۵ دقیقه افتادید زندان!")
        else:
            profit = random.randint(200, 500)
            db.update_field(user_id, "points", profit)
            await update.message.reply_text(f"✅ قاچاق لباس موفقیت‌آمیز بود! +{profit} هاپ سود کردید.")

    elif type_smuggle == "وسایل":
        risk = random.randint(1, 10)
        if risk <= 6:
            if user[2] >= 20000:
                db.update_field(user_id, "points", -20000)
                await update.message.reply_text("🚨 **لو رفتید!** مبلغ ۲۰,۰۰۰ هاپ جریمه پرداخت کردید!")
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
    user_points = user[2]
    current_factory = user[14]

    msg = (
        f"🏭 **مدیریت کارخانه هاپویی**\n\n"
        f"🏗 **کارخانه فعلی شما:** {current_factory}\n"
        f"💰 **موجودی کیف پول:** {user_points:,} هاپ\n\n"
        f"👇 یکی از کارخانه‌های زیر را برای خرید انتخاب کنید:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👕 کارخانه لباس (۲۰۰ هاپ)", callback_data="buy_factory_لباس")
        ],
        [
            InlineKeyboardButton("🍕 کارخانه غذا (۵۰۰ هاپ)", callback_data="buy_factory_غذا")
        ],
        [
            InlineKeyboardButton("🧸 کارخانه اسباب‌بازی (۱,۰۰۰ هاپ)", callback_data="buy_factory_اسباب‌بازی")
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    user = db.get_user(user_id)
    user_points = user[2]

    # استخراج نوع کارخانه از callback_data
    ftype = data.replace("buy_factory_", "")
    
    factories = {
        "لباس": {"cost": 200, "icon": "👕"},
        "غذا": {"cost": 500, "icon": "🍕"},
        "اسباب‌بازی": {"cost": 1000, "icon": "🧸"}
    }

    if ftype in factories:
        cost = factories[ftype]["cost"]
        icon = factories[ftype]["icon"]

        if user_points < cost:
            await query.message.reply_text(
                f"❌ **موجودی ناکافی!**\n"
                f"برای خرید {icon} **کارخانه {ftype}** به **{cost:,} هاپ** نیاز داری!\n"
                f"💰 موجودی فعلی شما: {user_points:,} هاپ",
                parse_mode='Markdown'
            )
            return

        # کسر هزینه و ثبت کارخانه
        db.update_field(user_id, "points", -cost)
        db.update_field(user_id, "factory_type", f"کارخانه {ftype}", relative=False)

        await query.message.reply_text(
            f"🎉 **تبریک! خرید موفقیت‌آمیز بود!** {icon}\n\n"
            f"🏭 شما صاحب **کارخانه {ftype}** شدید!\n"
            f"💸 مبلغ **{cost:,} هاپ** از حسابتان کسر شد.",
            parse_mode='Markdown'
        )
        
        # به‌روزرسانی منوی کارخانه
        updated_user = db.get_user(user_id)
        await handle_factory(update, context, updated_user)
