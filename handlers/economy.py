import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# --- 🎰 سیستم قمار ساده (عدد مشخص) ---
async def gamble(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    
    # دریافت موجودی لحظه‌ای از دیتابیس
    wallet = db.get_user_field(user_id, "points") or 0

    if len(text) < 2:
        await update.message.reply_text("💡 **روش استفاده:**\n`قمار 100` یا `قمار همه`", parse_mode='Markdown')
        return

    # تشخیص مقدار شرط‌بندی
    amount_str = text[1]
    if amount_str == "همه":
        amt = wallet
    elif amount_str.isdigit():
        amt = int(amount_str)
    else:
        await update.message.reply_text("❌ لطفاً یک مبلغ معتبر وارد کنید!")
        return

    if amt <= 0:
        await update.message.reply_text("❌ مبلغ قمار باید بیشتر از صفر باشد!")
        return

    if wallet < amt:
        await update.message.reply_text(f"❌ موجودی کافی نیست! موجودی شما: **{wallet:,}** هاپ", parse_mode='Markdown')
        return

    # انجام قمار (۵۰/۵۰)
    if random.choice([True, False]):
        db.update_field(user_id, "points", amt)
        new_balance = wallet + amt
        await update.message.reply_text(f"🎉 **برنده شدی!**\nمبلغ **{amt:,}** هاپ اضافه شد.\n💰 موجودی جدید: **{new_balance:,}** هاپ", parse_mode='Markdown')
    else:
        db.update_field(user_id, "points", -amt)
        new_balance = wallet - amt
        await update.message.reply_text(f"💥 **باختی!**\nمبلغ **{amt:,}** هاپ از دست رفتی.\n💰 موجودی جدید: **{new_balance:,}** هاپ", parse_mode='Markdown')


# --- 🎯 بازی‌های استیکری (دارت، تاس، بولینگ و...) ---
async def dice_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    wallet = db.get_user_field(user_id, "points") or 0

    if len(text) < 2:
        await update.message.reply_text("💡 **روش استفاده:**\n`بازی 100` یا `بازی همه`", parse_mode='Markdown')
        return

    amount_str = text[1]
    if amount_str == "همه":
        amt = wallet
    elif amount_str.isdigit():
        amt = int(amount_str)
    else:
        await update.message.reply_text("❌ مبلغ معتبر وارد کنید!")
        return

    if amt <= 0 or wallet < amt:
        await update.message.reply_text(f"❌ موجودی کافی نیست! موجودی: **{wallet:,}** هاپ", parse_mode='Markdown')
        return

    msg = (
        f"🎯 **منوی بازی‌های استیکری**\n\n"
        f"💰 مبلغ شرط‌بندی: **{amt:,}** هاپ\n"
        f"یکی از بازی‌های زیر را انتخاب کنید:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 دارت", callback_data=f"game_dart_{amt}_{user_id}"),
            InlineKeyboardButton("🎲 تاس", callback_data=f"game_dice_{amt}_{user_id}")
        ],
        [
            InlineKeyboardButton("🎳 بولینگ", callback_data=f"game_bowling_{amt}_{user_id}"),
            InlineKeyboardButton("🏀 بسکتبال", callback_data=f"game_basketball_{amt}_{user_id}")
        ],
        [
            InlineKeyboardButton("🎰 اسلات (کازینو)", callback_data=f"game_slots_{amt}_{user_id}")
        ]
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    game_type = data[1]
    amt = int(data[2])
    owner_id = int(data[3])

    if query.from_user.id != owner_id:
        await query.answer("❌ این بازی برای شخص دیگری است!", show_alert=True)
        return

    await query.answer()

    emoji_map = {
        "dart": "🎯",
        "dice": "🎲",
        "bowling": "🎳",
        "basketball": "🏀",
        "slots": "🎰"
    }
    target_emoji = emoji_map.get(game_type, "🎲")

    msg = (
        f"🕹 **بازی {target_emoji} آماده است!**\n\n"
        f"مبلغ شرط: **{amt:,}** هاپ\n\n"
        f"👇 **راهنما:**\n"
        f"همین حالا استیکر {target_emoji} رو روی **همین پیام** ریپلای کن تا نتیجه ثبت بشه!"
    )

    # ذخیره اطلاعات بازی در bot_data مربوط به پیام جهت پردازش ریپلای
    sent_msg = await query.message.edit_text(msg, parse_mode='Markdown')
    context.bot_data[f"game_{sent_msg.message_id}"] = {
        "user_id": owner_id,
        "amt": amt,
        "game_type": game_type,
        "emoji": target_emoji
    }


async def process_dice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message:
        return

    reply_to_id = update.message.reply_to_message.message_id
    game_data = context.bot_data.get(f"game_{reply_to_id}")

    if not game_data:
        return

    user_id = update.effective_user.id
    if user_id != game_data["user_id"]:
        return

    # بررسی اینکه کاربر حتماً تاس/استیکر فرستاده باشه
    if not update.message.dice:
        await update.message.reply_text("❌ لطفاً دقیقا همان استیکر بازی (تاس/دارت/...) را ریپلای کنید!")
        return

    dice_val = update.message.dice.value
    expected_emoji = game_data["emoji"]

    if update.message.dice.emoji != expected_emoji:
        await update.message.reply_text(f"❌ لطفاً استیکر {expected_emoji} را بفرستید!")
        return

    amt = game_data["amt"]
    wallet = db.get_user_field(user_id, "points") or 0

    if wallet < amt:
        await update.message.reply_text("❌ موجودی شما کافی نیست!")
        del context.bot_data[f"game_{reply_to_id}"]
        return

    # محاسبه برنده/بازنده بر اساس امتیاز استیکر تلگرام
    win = False
    multiplier = 2

    if expected_emoji in ["🎯", "🏀", "🎳"]:
        # امتیاز بالا (مثلاً ۵ یا ۶ در دارت/بسکتبال/بولینگ) برنده است
        if dice_val >= 5:
            win = True
    elif expected_emoji == "🎲":
        # ۴ و ۵ و ۶ برنده
        if dice_val >= 4:
            win = True
    elif expected_emoji == "🎰":
        # ۶۴ یعنی سه تا شکل یکسان در اسلات
        if dice_val == 64:
            win = True
            multiplier = 5  # ضریب ۵ برای کازینو

    if win:
        profit = amt * (multiplier - 1)
        db.update_field(user_id, "points", profit)
        new_wallet = wallet + profit
        await update.message.reply_text(
            f"🎉 **تبریک! برنده شدی!**\n"
            f"امتیاز استیکر: **{dice_val}**\n"
            f"🎁 پاداش: **+{profit:,}** هاپ\n"
            f"💰 موجودی جدید: **{new_wallet:,}** هاپ",
            parse_mode='Markdown'
        )
    else:
        db.update_field(user_id, "points", -amt)
        new_wallet = wallet - amt
        await update.message.reply_text(
            f"💥 **متأسفانه باختی!**\n"
            f"امتیاز استیکر: **{dice_val}**\n"
            f"🔻 کسر شد: **-{amt:,}** هاپ\n"
            f"💰 موجودی جدید: **{new_wallet:,}** هاپ",
            parse_mode='Markdown'
        )

    # پاک کردن بازی از حافظه
    del context.bot_data[f"game_{reply_to_id}"]


# --- 🏦 بانک ---
async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip() if update.message else ""
    parts = text.split()
    wallet = db.get_user_field(user_id, "points") or 0
    bank = db.get_user_field(user_id, "bank_balance") or 0

    if len(parts) >= 3 and parts[1] == "واریز":
        amt = wallet if parts[2] == "همه" else int(parts[2]) if parts[2].isdigit() else 0
        if amt <= 0 or wallet < amt:
            await update.message.reply_text("❌ موجودی کافی نیست!")
            return
        db.update_field(user_id, "points", -amt)
        db.update_field(user_id, "bank_balance", amt)
        await update.message.reply_text(f"✅ **{amt:,}** هاپ واریز شد.")
        return

    elif len(parts) >= 3 and parts[1] == "برداشت":
        amt = bank if parts[2] == "همه" else int(parts[2]) if parts[2].isdigit() else 0
        if amt <= 0 or bank < amt:
            await update.message.reply_text("❌ موجودی بانک کافی نیست!")
            return
        db.update_field(user_id, "bank_balance", -amt)
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"✅ **{amt:,}** هاپ برداشت شد.")
        return

    acc_num = db.get_or_create_account_number(user_id)
    daily_profit = int(bank * 0.03)

    msg = (
        f"🏦 **پنل شیشه‌ای بانک**\n\n"
        f"💳 **شماره حساب:** `{acc_num}`\n"
        f"💰 **موجودی بانک:** {bank:,} هاپ\n"
        f"👛 **موجودی کیف:** {wallet:,} هاپ\n\n"
        f"📈 **سود ۲۴ ساعته (۳%):** {daily_profit:,} هاپ"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ واریز", callback_data=f"bank_deposit_{user_id}"),
            InlineKeyboardButton("➖ برداشت", callback_data=f"bank_withdraw_{user_id}")
        ],
        [
            InlineKeyboardButton("💸 دریافت سود ۳٪", callback_data=f"bank_claim_{user_id}")
        ],
        [
            InlineKeyboardButton("🔄 تغییر شماره حساب", callback_data=f"bank_change_{user_id}")
        ]
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')

async def handle_bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    parts = query.data.split("_")
    action, owner_id = parts[1], int(parts[2])

    if clicker_id != owner_id:
        await query.answer("❌ این پنل متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()

    if action == "deposit":
        await query.message.reply_text("💡 دستور: `بانک واریز 100` یا `بانک واریز همه`", parse_mode='Markdown')
    elif action == "withdraw":
        await query.message.reply_text("💡 دستور: `بانک برداشت 100` یا `بانک برداشت همه`", parse_mode='Markdown')
    elif action == "claim":
        user = db.get_user(clicker_id)
        profit = int(user[5] * 0.03)
        if profit > 0:
            db.update_field(clicker_id, "points", profit)
            await query.message.reply_text(f"🎉 سود **{profit:,}** هاپ دریافت شد!")
        else:
            await query.message.reply_text("❌ موجودی بانک کافی نیست.")
    elif action == "change":
        import random
        new_acc = str(random.randint(1000000000, 9999999999))
        db.update_field(clicker_id, "account_number", new_acc, relative=False)
        await query.message.reply_text(f"✅ شماره حساب جدید:\n`{new_acc}`", parse_mode='Markdown')

# --- 🏭 کارخانه و کارخانه من ---
async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    msg = "🏭 **فروشگاه خرید کارخانه**\n\nیک کارخانه برای خرید انتخاب کنید:"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏭 کارخانه الماس (قیمت: ۱۰۰۰)", callback_data=f"buy_fac_diamond_{user_id}")],
        [InlineKeyboardButton("🏭 کارخانه سیگار (قیمت: ۵۰۰)", callback_data=f"buy_fac_cig_{user_id}")],
    ])
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')

async def my_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    fac_count = db.get_user_field(user_id, "factory_count") or 0
    fac_profit = fac_count * 200

    msg = (
        f"🏗 **کارخانه من**\n\n"
        f"🏭 تعداد کارخانه‌ها: {fac_count}\n"
        f"💰 سود آماده برداشت: {fac_profit:,} هاپ"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 برداشت سود کارخانه", callback_data=f"fac_claim_{user_id}")],
        [InlineKeyboardButton("🔥 فروش کارخانه", callback_data=f"fac_sell_{user_id}")]
    ])
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')

async def handle_factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    parts = query.data.split("_")
    action, owner_id = parts[1], int(parts[-1])

    if clicker_id != owner_id:
        await query.answer("❌ این پنل مال شما نیست!", show_alert=True)
        return

    await query.answer()

    if action == "buy":
        fac_type = parts[2]
        cost = 1000 if fac_type == "diamond" else 500
        user = db.get_user(clicker_id)
        if user[2] < cost:
            await query.message.reply_text("❌ موجودی کافی نیست!")
            return
        db.update_field(clicker_id, "points", -cost)
        db.update_field(clicker_id, "factory_count", 1)
        await query.message.edit_text("🎉 کارخانه با موفقیت خریداری شد!")
    elif action == "claim":
        fac_count = db.get_user_field(clicker_id, "factory_count") or 0
        profit = fac_count * 200
        if profit > 0:
            db.update_field(clicker_id, "points", profit)
            await query.message.reply_text(f"💰 سود **{profit:,}** برداشت شد!")
        else:
            await query.message.reply_text("❌ سودی برای برداشت وجود ندارد.")
    elif action == "sell":
        fac_count = db.get_user_field(clicker_id, "factory_count") or 0
        if fac_count > 0:
            db.update_field(clicker_id, "factory_count", -1)
            db.update_field(clicker_id, "points", 400)
            await query.message.reply_text("✅ ۱ کارخانه فروخته شد.")

# --- 🕵️‍♂️ قاچاق و 🚓 زندان ---
async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    is_jail = db.get_user_field(user_id, "in_jail") or 0
    if is_jail:
        await update.message.reply_text("🚓 شما در زندان هستید! ابتدا جریمه را پرداخت کنید.")
        return

    if random.randint(1, 100) <= 40:
        db.update_field(user_id, "in_jail", 1, relative=False)
        await update.message.reply_text("🚨 **لو رفتی!** دستگیر شدی و به زندان افتادی. با دستور `زندان` جریمه بده.")
    else:
        profit = random.randint(300, 800)
        db.update_field(user_id, "points", profit)
        await update.message.reply_text(f"🎉 **قاچاق موفق!** مبلغ **{profit:,}** هاپ سود کردی.")

async def jail_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    is_jail = db.get_user_field(user_id, "in_jail") or 0
    text = update.message.text.strip() if update.message else ""

    if "پرداخت" in text or "جریمه" in text:
        if not is_jail:
            await update.message.reply_text("شما آزاد هستید!")
            return
        user_points = db.get_user_field(user_id, "points") or 0
        bail = 200
        if user_points < bail:
            await update.message.reply_text(f"❌ برای آزادی نیاز به {bail} هاپ دارید.")
            return
        db.update_field(user_id, "points", -bail)
        db.update_field(user_id, "in_jail", 0, relative=False)
        await update.message.reply_text("✅ جریمه پرداخت شد و از زندان آزاد شدید!")
        return

    status = "🔴 در زندان" if is_jail else "🟢 آزاد"
    await update.message.reply_text(f"🚓 **وضعیت زندان:** {status}\nبرای آزادی از دستور `زندان پرداخت` استفاده کنید (جریمه: ۲۰۰ هاپ).")

# --- 🏙 شهر و اهدا ---
async def city_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    fund = db.get_global_field("city_fund") or 0
    await update.message.reply_text(f"🏙 **وضعیت شهر هاپو**\n\n🏦 صندوق توسعه شهر: **{fund:,}** هاپ\nبرای کمک: `اهدا [مبلغ]`")

async def donate_city(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("💡 روش استفاده: `اهدا 100`", parse_mode='Markdown')
        return

    amt = int(text[1])
    wallet = db.get_user_field(user_id, "points") or 0
    if amt <= 0 or wallet < amt:
        await update.message.reply_text("❌ موجودی کافی نیست!")
        return

    db.update_field(user_id, "points", -amt)
    db.update_global_field("city_fund", amt)
    await update.message.reply_text(f"❤️ با تشکر! مبلغ **{amt:,}** هاپ به صندوق شهر اهدا شد.")
