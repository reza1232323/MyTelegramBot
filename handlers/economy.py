import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# --- 🎯 اهداف و نیازمندی‌های هر سطح برای ارتقا به سطح بعدی ---
CITY_LEVEL_REQUIREMENTS = {
    1: {"treasury": 10000, "hops": 100, "dogs": 5, "bones": 20, "fish": 10},
    2: {"treasury": 30000, "hops": 200, "dogs": 15, "bones": 40, "fish": 20},
    3: {"treasury": 60000, "hops": 400, "dogs": 35, "bones": 80, "fish": 40},
    4: {"treasury": 120000, "hops": 800, "dogs": 50, "bones": 150, "fish": 80},
    5: {"treasury": 250000, "hops": 1500, "dogs": 80, "bones": 300, "fish": 150},
    # برای سطوح بالاتر هم به همین ترتیب افزوده می‌شود
}

# --- 🎯 تابع محاسبه نوار پیشرفت (۵ خانه‌ای) ---
def get_progress_bar(current, total):
    if total <= 0:
        return "▱▱▱▱▱"
    ratio = min(max(current / total, 0.0), 1.0)
    filled = int(round(ratio * 5))
    return "▰" * filled + "▱" * (5 - filled)

# --- 🏦 بانک ---
async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip() if update.message else ""
    parts = text.split()
    current_user = db.get_user(user_id)
    wallet, bank = current_user[2], current_user[5]

    if len(parts) >= 3 and parts[1] == "واریز":
        amt = wallet if parts[2] == "همه" else int(parts[2])
        if amt <= 0 or wallet < amt:
            await update.message.reply_text("❌ موجودی کافی نیست!")
            return
        db.update_field(user_id, "points", -amt)
        db.update_field(user_id, "bank_balance", amt)
        await update.message.reply_text(f"✅ **{amt:,}** هاپ واریز شد.")
        return

    elif len(parts) >= 3 and parts[1] == "برداشت":
        amt = bank if parts[2] == "همه" else int(parts[2])
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
        user_points = user[2]
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

# --- 🎰 قمار ---
async def gamble(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("💡 روش استفاده: `قمار 100`", parse_mode='Markdown')
        return

    amt = int(text[1])
    wallet = user[2]
    if amt <= 0 or wallet < amt:
        await update.message.reply_text("❌ موجودی کافی نیست!")
        return

    if random.choice([True, False]):
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"🎉 **برنده شدی!** مبلغ **{amt:,}** هاپ اضافه شد.")
    else:
        db.update_field(user_id, "points", -amt)
        await update.message.reply_text(f"💥 **باختی!** مبلغ **{amt:,}** هاپ از دست رفتی.")

# --- 🏙 شهر و اهدا ---
async def city_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    chat_title = update.effective_chat.title or "شهر هاپو"
    
    # دریافت آمار شهر از دیتابیس
    if hasattr(db, 'get_city'):
        city_data = db.get_city()
        treasury = city_data[0]
        hops = city_data[1]
        dogs = city_data[2]
        bones = city_data[3]
        fish = city_data[4]
        level = city_data[5] if len(city_data) > 5 else (db.get_global_field("city_level") or 1)
    else:
        treasury = db.get_global_field("city_fund") or 0
        hops = db.get_global_field("city_hops") or 0
        dogs = db.get_global_field("city_dogs") or 0
        bones = db.get_global_field("city_bones") or 0
        fish = db.get_global_field("city_fish") or 0
        level = db.get_global_field("city_level") or 1

    # دریافت نیازمندی‌های سطح جاری برای ارتقا به سطح بعدی
    reqs = CITY_LEVEL_REQUIREMENTS.get(level, CITY_LEVEL_REQUIREMENTS[3])
    req_treasury = reqs["treasury"]
    req_hops = reqs["hops"]
    req_dogs = reqs["dogs"]
    req_bones = reqs["bones"]
    req_fish = reqs["fish"]

    # بررسی شرط ارتقای سطح (Level Up)
    if (treasury >= req_treasury and 
        hops >= req_hops and 
        dogs >= req_dogs and 
        bones >= req_bones and 
        fish >= req_fish and 
        level < 10):
        
        level += 1
        if hasattr(db, 'update_city_level'):
            db.update_city_level(level)
        else:
            db.update_global_field("city_level", level, relative=False)
            
        await update.message.reply_text(f"🎉 **تبریک! شهر هاپو شما به سطح {level} ارتقا یافت!** 🥳\nامکانات و باف‌های جدید فعال شدند.")
        
        # به‌روزرسانی نیازمندی‌ها برای سطح جدید
        reqs = CITY_LEVEL_REQUIREMENTS.get(level, CITY_LEVEL_REQUIREMENTS[min(level, 5)])
        req_treasury = reqs["treasury"]
        req_hops = reqs["hops"]
        req_dogs = reqs["dogs"]
        req_bones = reqs["bones"]
        req_fish = reqs["fish"]

    next_level = min(level + 1, 10)

    msg = (
        "╮──「  شهر هاپو  」\n\n"
        f"┐─  نام : {chat_title}\n"
        "┐─  رتبه جهانی : #1\n"
        "└─ \n\n"
        " آمار شهر:\n"
        f"┐─  سطح : {level} / 10\n"
        f"┐─  خزانه : {treasury:,}\n"
        f"┐─  کل هاپ : {hops:,}\n"
        f"┐─  کل سگ : {dogs:,}\n"
        f"┐─  کل استخوان : {bones:,}\n"
        f"└─  کل ماهی : {fish:,}\n\n"
        f" باف‌های فعال (سطح {level}):\n"
        f"┐─  کولداون هاپ : {300 - (level * 3.33):.0f}s (اصلی 300s)\n"
        f"┐─  کاهش کولداون ماهیگیری : {level * 20}s\n"
        f"└─  کاهش آستانه پیشی خیابونی : {level * 3.33:.0f}%\n\n"
        f" پیشرفت به سطح {next_level}:\n"
        f"┐─  خزانه : {treasury:,} / {req_treasury:,}  {get_progress_bar(treasury, req_treasury)}\n"
        f"┐─  هاپ‌های کل : {hops:,} / {req_hops:,}  {get_progress_bar(hops, req_hops)}\n"
        f"┐─  سگ‌های خریداری شده : {dogs:,} / {req_dogs:,}  {get_progress_bar(dogs, req_dogs)}\n"
        f"┐─  استخوان‌ها : {bones:,} / {req_bones:,}  {get_progress_bar(bones, req_bones)}\n"
        f"└─  ماهی‌ها : {fish:,} / {req_fish:,}  {get_progress_bar(fish, req_fish)}\n\n"
        " برای کمک به خزانه بنویس: اهدا [مقدار]"
    )
    await update.message.reply_text(msg)

async def donate_city(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("💡 روش استفاده: `اهدا 100`", parse_mode='Markdown')
        return

    amt = int(text[1])
    wallet = user[2]
    if amt <= 0 or wallet < amt:
        await update.message.reply_text("❌ موجودی کافی نیست!")
        return

    db.update_field(user_id, "points", -amt)
    if hasattr(db, 'update_city'):
        db.update_city("treasury", amt)
    else:
        db.update_global_field("city_fund", amt)
        
    await update.message.reply_text(f"🏛️ با تشکر! مبلغ {amt:,} هاپ به خزانه شهر اهدا شد.")
    
    # بررسی بلافاصله ارتقای سطح پس از اهدا
    await city_status(update, context, user)
