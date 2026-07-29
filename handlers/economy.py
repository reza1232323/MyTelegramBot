import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# ==================== 🏦 بخش بانک ====================

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

    # ۲. نمایش پنل تصویری شیشه‌ای بانک (اختصاصی برای هر کاربر)
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
            InlineKeyboardButton("➕ واریز", callback_data=f"bank_deposit_help_{user_id}"),
            InlineKeyboardButton("➖ برداشت", callback_data=f"bank_withdraw_help_{user_id}")
        ],
        [
            InlineKeyboardButton("💸 دریافت سود", callback_data=f"bank_claim_profit_{user_id}")
        ],
        [
            InlineKeyboardButton("🔄 تغییر شماره حساب", callback_data=f"bank_change_acc_{user_id}")
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    data = query.data

    data_clean = data.replace("bank_", "")
    parts = data_clean.split("_")
    
    if len(parts) >= 3 and parts[0] in ["deposit", "withdraw", "claim", "change"]:
        action = f"{parts[0]}_{parts[1]}"
        owner_id = int(parts[2])
    else:
        action = parts[0]
        owner_id = int(parts[1]) if len(parts) > 1 else clicker_id

    # 🔒 بررسی اختصاصی بودن پنل بانک
    if clicker_id != owner_id:
        await query.answer("❌ این پنل بانک متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()
    user = db.get_user(clicker_id)

    if action == "deposit_help":
        await query.message.reply_text("💡 **راهنمای واریز:**\nعبارت زیر را ارسال کنید:\n`بانک واریز 100` یا `بانک واریز همه`", parse_mode='Markdown')
        
    elif action == "withdraw_help":
        await query.message.reply_text("💡 **راهنمای برداشت:**\nعبارت زیر را ارسال کنید:\n`بانک برداشت 100` یا `بانک برداشت همه`", parse_mode='Markdown')

    elif action == "claim_profit":
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

        db.update_field(clicker_id, "bank_balance", daily_profit)
        db.update_field(clicker_id, "last_profit_claim", datetime.now().isoformat(), relative=False)
        await query.message.reply_text(f"🎉 **مبلغ {daily_profit:,} هاپ (سود ۳٪ روزانه)** اضافه شد!")
        await bank_status(update, context, db.get_user(clicker_id))

    elif action == "change_acc":
        new_acc = str(random.randint(1000000000, 9999999999))
        db.update_field(clicker_id, "account_number", new_acc, relative=False)
        await query.message.reply_text(f"✅ شماره حساب جدید شما صادر شد:\n`{new_acc}`", parse_mode='Markdown')
        await bank_status(update, context, db.get_user(clicker_id))


# ==================== 🏭 بخش کارخانه ====================

async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    user_points = user[2]

    msg = (
        f"🏭 **بازار ساخت کارخانه**\n\n"
        f"💰 **موجودی شما:** {user_points:,} هاپ\n\n"
        f"نوع خط تولید کارخانه‌ای که می‌خواهید احداث کنید را انتخاب کنید:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 کارخانه الماس (سود: ۵۰۰ | ریسک: ۶۰٪)", callback_data=f"buy_factory_diamond_{user_id}")],
        [InlineKeyboardButton("📦 کارخانه سیگار (سود: ۲۰۰ | ریسک: ۳۰٪)", callback_data=f"buy_factory_cig_{user_id}")],
        [InlineKeyboardButton("🍫 کارخانه شکلات (سود: ۱۰۰ | ریسک: ۱۰٪)", callback_data=f"buy_factory_choco_{user_id}")],
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id

    data = query.data.replace("buy_factory_", "")
    parts = data.split("_")
    fac_type = parts[0]
    owner_id = int(parts[1]) if len(parts) > 1 else clicker_id

    if clicker_id != owner_id:
        await query.answer("❌ این پنل کارخانه متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()

    items = {
        "diamond": {"name": "الماس 💎", "profit": 500, "risk_percent": 60},
        "cig": {"name": "سیگار 📦", "profit": 200, "risk_percent": 30},
        "choco": {"name": "شکلات 🍫", "profit": 100, "risk_percent": 10},
    }

    if fac_type not in items:
        return

    selected = items[fac_type]
    profit = selected["profit"]
    risk = selected["risk_percent"]
    item_name = selected["name"]

    chance = random.randint(1, 100)

    if chance <= risk:
        await query.message.edit_text(
            f"💥 **خرابی خط تولید!** 🏭\n\n"
            f"😱 خط تولید **{item_name}** با مشکل مواجه شد و خسارت دیدید!",
            parse_mode='Markdown'
        )
    else:
        db.update_field(clicker_id, "points", profit)
        updated_user = db.get_user(clicker_id)

        await query.message.edit_text(
            f"🎉 **تولید موفقیت‌آمیز بود!** 🏭\n\n"
            f"✅ محصول **{item_name}** با موفقیت تولید و فروخته شد.\n"
            f"💵 **سود تولید:** +{profit:,} هاپ\n"
            f"💰 **موجودی جدید:** {updated_user[2]:,} هاپ",
            parse_mode='Markdown'
        )


# ==================== 🕵️‍♂️ بخش قاچاق ====================

async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    user_points = user[2]

    msg = (
        f"🕵️‍♂️ **بازار سیاه قاچاق هاپویی**\n\n"
        f"💰 **موجودی فعلی شما:** {user_points:,} هاپ\n\n"
        f"⚠️ **هشدار:** در صورت لورفتن، به **زندان** می‌افتید!\n\n"
        f"👇 جنس مورد نظر برای قاچاق را انتخاب کنید:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 قاچاق الماس (سود: ۵۰۰ | ریسک: ۶۰٪)", callback_data=f"smuggle_diamond_{user_id}")],
        [InlineKeyboardButton("📦 قاچاق سیگار (سود: ۲۰۰ | ریسک: ۳۰٪)", callback_data=f"smuggle_cig_{user_id}")],
        [InlineKeyboardButton("🍫 قاچاق شکلات (سود: ۱۰۰ | ریسک: ۱۰٪)", callback_data=f"smuggle_choco_{user_id}")],
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_smuggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id

    data = query.data.replace("smuggle_", "")
    parts = data.split("_")
    item_type = parts[0]
    owner_id = int(parts[1]) if len(parts) > 1 else clicker_id

    if clicker_id != owner_id:
        await query.answer("❌ این پنل قاچاق متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()

    items = {
        "diamond": {"name": "الماس 💎", "profit": 500, "risk_percent": 60},
        "cig": {"name": "سیگار 📦", "profit": 200, "risk_percent": 30},
        "choco": {"name": "شکلات 🍫", "profit": 100, "risk_percent": 10},
    }

    if item_type not in items:
        return

    selected = items[item_type]
    profit = selected["profit"]
    risk = selected["risk_percent"]
    item_name = selected["name"]

    chance = random.randint(1, 100)

    if chance <= risk:
        await query.message.edit_text(
            f"🚨 **آژیر پلیس!** 🚓\n\n"
            f"😱 شما هنگام قاچاق **{item_name}** دستگیر شدید!",
            parse_mode='Markdown'
        )
    else:
        db.update_field(clicker_id, "points", profit)
        updated_user = db.get_user(clicker_id)

        await query.message.edit_text(
            f"🎉 **رد مال موفقیت‌آمیز بود!** 🕵️‍♂️\n\n"
            f"✅ محموله **{item_name}** با موفقیت رد شد.\n"
            f"💵 **سود خالص:** +{profit:,} هاپ\n"
            f"💰 **موجودی جدید:** {updated_user[2]:,} هاپ",
            parse_mode='Markdown'
        )
