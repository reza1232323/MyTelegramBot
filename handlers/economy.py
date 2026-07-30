import asyncio
import random
import database as db
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# تابع کمکی برای فرمت‌دهی به موجودی
def format_balance(amount):
    try:
        from handlers.pet import format_balance as fb
        return fb(amount)
    except Exception:
        amount = int(amount or 0)
        return f"{amount:,}"

# ----------------- لیست محصولات -----------------

FACTORY_PRODUCTS = {
    "clothes": {"name": "👕 لباس هاپویی", "price": 50, "db_field": "inventory_clothes"},
    "food": {"name": "🦴 غذای ویژه", "price": 100, "db_field": "inventory_food"},
    "toy": {"name": "🎾 توپ بازی", "price": 30, "db_field": "inventory_toy"},
    "house": {"name": "🏠 لانه شیک", "price": 1000, "db_field": "inventory_house"},
}

CONTRABAND_PRODUCTS = {
    "cig": {"name": "🚬 سیگار قاچاق", "cost": 500, "profit": 1500, "db_field": "inventory_cig"},
    "diamond": {"name": "💎 الماس سیاه", "cost": 2000, "profit": 6000, "db_field": "inventory_diamond"},
    "gold": {"name": "🪙 شمش طلا", "cost": 5000, "profit": 15000, "db_field": "inventory_gold"},
    "car": {"name": "🏎 خودروی قاچاق", "cost": 10000, "profit": 35000, "db_field": "inventory_car"},
}

active_gambles = {}

# ----------------- ۰. بخش بانک -----------------

def _ensure_user_dict(user, user_id: int) -> dict:
    """تبدیل ورودی کاربر به دیکشنری و استخراج مقادیر از دیتابیس"""
    account_number = db.get_user_field(user_id, "account_number") if hasattr(db, "get_user_field") else None
    bank = db.get_user_field(user_id, "bank_balance") if hasattr(db, "get_user_field") else 0
    points = db.get_user_field(user_id, "points") if hasattr(db, "get_user_field") else 0
    
    return {
        "user_id": user_id,
        "account_number": account_number or f"278{user_id}",
        "bank": int(bank or 0),
        "points": int(points or 0),
    }

async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    """نمایش وضعیت بانک هاپی"""
    user_id = update.effective_user.id
    user_data = _ensure_user_dict(user, user_id)

    account_number = user_data.get("account_number") or f"278{user_id}"
    bank_balance = user_data.get("bank", 0)
    wallet_balance = user_data.get("points", 0)

    daily_profit = int(bank_balance * 0.03)
    profit_ready = user_data.get("profit_ready", True)
    profit_text = "✅ سود آماده دریافته!" if profit_ready else "⏳ سود امروز دریافت شده."

    text = (
        f"🏦 **بانک هاپی**\n\n"
        f"💳 **شماره حساب:** `{account_number}`\n"
        f"💰 **موجودی بانک:** {format_balance(bank_balance)} هاپ پوینت\n"
        f"👛 **موجودی کیف:** {format_balance(wallet_balance)} هاپ پوینت\n\n"
        f"📈 **سود روزانه (۳%):** {format_balance(daily_profit)} هاپ پوینت\n"
        f"{profit_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("+ واریز", callback_data=f"bank_deposit:{user_id}"),
            InlineKeyboardButton("- برداشت", callback_data=f"bank_withdraw:{user_id}"),
        ],
        [
            InlineKeyboardButton("💸 دریافت سود", callback_data=f"bank_claim_profit:{user_id}")
        ],
        [
            InlineKeyboardButton("🔄 تغییر شماره حساب", callback_data=f"bank_change_account:{user_id}")
        ],
    ])

    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def handle_bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌های مربوط به بانک"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split(":")[0]
    await query.answer()

    if data == "bank_deposit":
        context.user_data['state'] = "WAITING_FOR_BANK_DEPOSIT"
        await query.message.reply_text("💵 لطفاً مبلغی که می‌خواهید به بانک واریز کنید را وارد کنید (یا بنویسید `همه`):")
    
    elif data == "bank_withdraw":
        context.user_data['state'] = "WAITING_FOR_BANK_WITHDRAW"
        await query.message.reply_text("🏧 لطفاً مبلغی که می‌خواهید از بانک برداشت کنید را وارد کنید (یا بنویسید `همه`):")
        
    elif data == "bank_claim_profit":
        bank_balance = int(db.get_user_field(user_id, "bank_balance") or 0)
        if bank_balance <= 0:
            await query.message.reply_text("❌ موجودی بانک شما صفر است و سودی تعلق نمی‌گیرد.")
            return
            
        profit = int(bank_balance * 0.03)
        db.update_field(user_id, "points", profit, relative=True)
        await query.message.reply_text(f"🎉 مبلغ **{format_balance(profit)}** هاپ پوینت به عنوان سود روزانه به کیف پول شما اضافه شد!")

    elif data == "bank_change_account":
        context.user_data['state'] = "WAITING_FOR_NEW_ACCOUNT_NUM"
        await query.message.reply_text("💳 لطفاً شماره حساب جدید خود را وارد کنید:")

# ----------------- ۱. بخش کارخانه -----------------

async def show_factory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    in_jail = db.is_in_jail(user_id)[0] if hasattr(db, "is_in_jail") else False
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید و به کارخانه دسترسی ندارید!")
        return

    keyboard = []
    for code, item in FACTORY_PRODUCTS.items():
        price_str = format_balance(item['price'])
        keyboard.append([InlineKeyboardButton(f"{item['name']} - {price_str}", callback_data=f"buy_fac_{code}:{user_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏭 **به کارخانه خوش آمدید!**\nمحصول مورد نظر برای خرید را انتخاب کنید:", reply_markup=reply_markup, parse_mode="Markdown")

async def factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")[0]
    if data.startswith("buy_fac_"):
        product_code = data.replace("buy_fac_", "")
        context.user_data['buy_product'] = product_code
        product = FACTORY_PRODUCTS[product_code]
        
        await query.message.reply_text(
            f"🛒 شما **{product['name']}** را انتخاب کردید.\n"
            f"💵 قیمت هر عدد: {format_balance(product['price'])}\n\n"
            f"لطفاً **تعداد** درخواستی خود را ارسال کنید:"
        )
        context.user_data['state'] = "WAITING_FOR_FACTORY_QTY"

# ----------------- ۲. بخش قاچاق -----------------

async def show_contraband(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    in_jail, jail_until = db.is_in_jail(user_id) if hasattr(db, "is_in_jail") else (False, None)
    if in_jail:
        keyboard = [[InlineKeyboardButton("🔓 آزادی فوری (۲۰,۰۰۰ میو/هاپ)", callback_data=f"pay_bail:{user_id}")]]
        time_str = jail_until.strftime('%H:%M') if jail_until else "۱۵ دقیقه"
        await update.message.reply_text(
            f"🚨 **شما در زندان هستید!**\n"
            f"⏱ زمان آزادی: تا {time_str}\n"
            f"می‌توانید ۱۵ دقیقه صبر کنید یا با پرداخت ۲۰,۰۰۰ وثیقه فوراً آزاد شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keyboard = []
    for code, item in CONTRABAND_PRODUCTS.items():
        cost_str = format_balance(item['cost'])
        profit_str = format_balance(item['profit'])
        keyboard.append([InlineKeyboardButton(f"{item['name']} (هزینه: {cost_str} | سود: {profit_str})", callback_data=f"select_contra_{code}:{user_id}")])
    
    keyboard.append([InlineKeyboardButton("🚀 شروع عملیات قاچاق", callback_data=f"start_smuggling:{user_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🕵️‍♂️ **پنل قاچاقچیان**\n"
        "جنس‌های مورد نظر خود را انتخاب کرده و تعداد را مشخص کنید.\n"
        "⚠️ **هشدار:** ریسک گیر افتادن و ۱۵ دقیقه زندان وجود دارد!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_smuggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split(":")[0]
    await query.answer()

    if data == "pay_bail":
        points = int(db.get_user_field(user_id, "points") or 0)
        if points < 20000:
            await query.message.reply_text("❌ شما ۲۰,۰۰۰ موجودی برای وثیقه ندارید!")
            return
        
        db.update_field(user_id, "points", -20000, relative=True)
        if hasattr(db, "release_from_jail"):
            db.release_from_jail(user_id)
        await query.message.reply_text("🔓 شما با پرداخت ۲۰,۰۰۰ وثیقه از زندان آزاد شدید!")
        return

    if data.startswith("select_contra_"):
        code = data.replace("select_contra_", "")
        context.user_data['contra_item'] = code
        context.user_data['state'] = "WAITING_FOR_CONTRA_QTY"
        await query.message.reply_text(f"تعداد مورد نظر برای **{CONTRABAND_PRODUCTS[code]['name']}** را وارد کنید:")
        return

    if data == "start_smuggling":
        cart = context.user_data.get('contra_cart', {})
        if not cart:
            await query.message.reply_text("❌ سبد قاچاق شما خالی است!")
            return

        if context.user_data.get('is_smuggling_active', False):
            await query.message.reply_text("⏳ شما از قبل یک قاچاق در انتظار دارید! صبر کنید تا محموله قبلی برسد.")
            return

        total_cost = sum(CONTRABAND_PRODUCTS[code]['cost'] * qty for code, qty in cart.items())
        points = int(db.get_user_field(user_id, "points") or 0)

        if points < total_cost:
            await query.message.reply_text(f"❌ موجودی کافی نیست! هزینه کل: {format_balance(total_cost)}")
            return

        db.update_field(user_id, "points", -total_cost, relative=True)
        context.user_data['contra_cart'] = {}
        context.user_data['is_smuggling_active'] = True
        
        await query.message.reply_text("🚚 **عملیات قاچاق آغاز شد!**\nمحموله ارسال شد. نتیجه تا ۳۰ دقیقه دیگر مشخص می‌شود...")

        asyncio.create_task(process_smuggling_result(context, user_id, total_cost, cart))

async def process_smuggling_result(context, user_id, total_cost, cart):
    await asyncio.sleep(1800)
    
    context.user_data['is_smuggling_active'] = False
    is_busted = random.random() < 0.35

    if is_busted:
        if hasattr(db, "set_jail"):
            db.set_jail(user_id, minutes=15)
        await context.bot.send_message(
            chat_id=user_id,
            text="🚨 **خبر بد!** محموله قاچاق شما توسط پلیس لو رفت!\nشما به مدت ۱۵ دقیقه وارد **زندان** شدید یا می‌توانید ۲۰,۰۰۰ جریمه بپردازید."
        )
    else:
        total_profit = sum(CONTRABAND_PRODUCTS[code]['profit'] * qty for code, qty in cart.items())
        db.update_field(user_id, "points", total_profit, relative=True)
        
        for code, qty in cart.items():
            field_name = CONTRABAND_PRODUCTS[code]['db_field']
            db.update_field(user_id, field_name, qty, relative=True)

        profit_str = format_balance(total_profit)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 **موفقیت!** عملیات قاچاق انجام شد.\nسود خالص: **{profit_str}** به کیف پول شما اضافه شد!"
        )

# ----------------- ۳. سیستم قمار چندنفره -----------------

async def start_gamble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    args = context.args or update.message.text.split()[1:]
    
    if len(args) < 2:
        await update.message.reply_text("❌ فرمت صحیح: `قمار [مبلغ] [تعداد نفرات]`\nمثال: `قمار 100 3`", parse_mode="Markdown")
        return

    try:
        amount = int(args[0])
        max_players = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ مبلغ و تعداد افراد باید عدد معتبر باشند.")
        return

    if amount <= 0 or max_players < 2:
        await update.message.reply_text("❌ حداقل مبلغ ۱ و حداقل تعداد شرکت‌کنندگان ۲ نفر است.")
        return

    user_points = int(db.get_user_field(user.id, "points") or 0)
    if user_points < amount:
        await update.message.reply_text("❌ کافی نمی‌باشد تعداد هاپ پوینت‌های شما.")
        return

    db.update_field(user.id, "points", -amount, relative=True)

    gamble_id = f"{chat.id}_{update.message.message_id}"
    active_gambles[gamble_id] = {
        "creator_id": user.id,
        "amount": amount,
        "max_players": max_players,
        "players": [(user.id, user.full_name)],
        "chat_id": chat.id
    }

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 شرکت در قمار", callback_data=f"join_gamble:{gamble_id}")]
    ])

    text = (
        f"🎲 **قمار جدید ایجاد شد!**\n\n"
        f"👤 سازنده: {user.full_name}\n"
        f"💰 ورودی هر نفر: {format_balance(amount)} هاپ\n"
        f"👥 ظرفیت: ۱ / {max_players} نفر\n"
        f"🏆 مجموع جایزه فعلی: {format_balance(amount)} هاپ\n\n"
        f"برای شرکت روی دکمه زیر کلیک کنید!"
    )

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def join_gamble_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data_parts = query.data.split(":")
    gamble_id = data_parts[1]

    if gamble_id not in active_gambles:
        await query.answer("❌ این قمار پایان یافته یا منقضی شده است.", show_alert=True)
        return

    gamble = active_gambles[gamble_id]

    player_ids = [p[0] for p in gamble["players"]]
    if user.id in player_ids:
        await query.answer("❌ شما قبلاً در این قمار شرکت کرده‌اید!", show_alert=True)
        return

    user_points = int(db.get_user_field(user.id, "points") or 0)
    if user_points < gamble["amount"]:
        await query.answer("❌ برای شرکت در این قمار موجودی کافی ندارید.", show_alert=True)
        return

    db.update_field(user.id, "points", -gamble["amount"], relative=True)
    gamble["players"].append((user.id, user.full_name))

    current_count = len(gamble["players"])
    total_prize = gamble["amount"] * current_count

    if current_count >= gamble["max_players"]:
        winner_id, winner_name = random.choice(gamble["players"])
        db.update_field(winner_id, "points", total_prize, relative=True)

        players_list = "\n".join([f"▫️ {p[1]}" for p in gamble["players"]])
        result_text = (
            f"🎰 **قمار تکمیل شد و به پایان رسید!**\n\n"
            f"👥 شرکت‌کنندگان:\n{players_list}\n\n"
            f"💰 مجموع کل جایزه: {format_balance(total_prize)} هاپ\n"
            f"🎉 **برنده خوش‌شانس:** {winner_name}"
        )
        
        del active_gambles[gamble_id]
        await query.edit_message_text(result_text, parse_mode="Markdown")
        await query.answer("🎉 قمار تمام شد! برنده مشخص گردید.")
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 شرکت در قمار", callback_data=f"join_gamble:{gamble_id}")]
        ])
        
        updated_text = (
            f"🎲 **قمار در جریان است...**\n\n"
            f"💰 ورودی هر نفر: {format_balance(gamble['amount'])} هاپ\n"
            f"👥 ظرفیت: {current_count} / {gamble['max_players']} نفر\n"
            f"🏆 مجموع جایزه فعلی: {format_balance(total_prize)} هاپ\n\n"
            f"برای شرکت روی دکمه زیر کلیک کنید!"
        )
        
        await query.edit_message_text(updated_text, reply_markup=keyboard, parse_mode="Markdown")
        await query.answer("✅ شما با موفقیت وارد قمار شدید!")

# ----------------- ۴. دریافت ورودی‌های متنی -----------------

async def handle_factory_and_smuggle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message and update.message.text else ""

    # ۵.۱ مدیریت واریز و برداشت بانک
    if state == "WAITING_FOR_BANK_DEPOSIT":
        points = int(db.get_user_field(user_id, "points") or 0)
        
        if text in ["همه", "all"]:
            amount = points
        elif text.isdigit():
            amount = int(text)
        else:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر یا کلمه `همه` را وارد کنید.")
            return True

        if amount <= 0:
            await update.message.reply_text("❌ مقدار واریز باید بیشتر از صفر باشد.")
            return True

        if points < amount:
            await update.message.reply_text(f"❌ موجودی کیف پول شما کافی نیست!\n💰 موجودی کیف: {format_balance(points)}")
        else:
            db.update_field(user_id, "points", -amount, relative=True)
            db.update_field(user_id, "bank_balance", amount, relative=True)
            await update.message.reply_text(f"✅ مبلغ **{format_balance(amount)}** هاپ به بانک واریز شد.")
            
        context.user_data['state'] = None
        return True

    if state == "WAITING_FOR_BANK_WITHDRAW":
        bank_bal = int(db.get_user_field(user_id, "bank_balance") or 0)
        
        if text in ["همه", "all"]:
            amount = bank_bal
        elif text.isdigit():
            amount = int(text)
        else:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر یا کلمه `همه` را وارد کنید.")
            return True

        if amount <= 0:
            await update.message.reply_text("❌ مقدار برداشت باید بیشتر از صفر باشد.")
            return True

        if bank_bal < amount:
            await update.message.reply_text(f"❌ موجودی بانک شما کافی نیست!\n🏦 موجودی بانک: {format_balance(bank_bal)}")
        else:
            db.update_field(user_id, "bank_balance", -amount, relative=True)
            db.update_field(user_id, "points", amount, relative=True)
            await update.message.reply_text(f"✅ مبلغ **{format_balance(amount)}** هاپ از بانک برداشت شد.")
            
        context.user_data['state'] = None
        return True

    if state == "WAITING_FOR_NEW_ACCOUNT_NUM":
        db.update_field(user_id, "account_number", text)
        await update.message.reply_text(f"✅ شماره حساب شما با موفقیت به `{text}` تغییر یافت.")
        context.user_data['state'] = None
        return True

    if state == "WAITING_FOR_FACTORY_QTY":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر و بزرگتر از صفر وارد کنید.")
            return True
        
        qty = int(text)
        product_code = context.user_data.get('buy_product')
        product = FACTORY_PRODUCTS[product_code]
        total_price = product['price'] * qty
        
        points = int(db.get_user_field(user_id, "points") or 0)
        if points < total_price:
            await update.message.reply_text(f"❌ موجودی کافی نیست! هزینه {qty} عدد: {format_balance(total_price)}")
        else:
            db.update_field(user_id, "points", -total_price, relative=True)
            db.update_field(user_id, product['db_field'], qty, relative=True)
            await update.message.reply_text(f"✅ تعداد {qty} عدد **{product['name']}** با موفقیت خریداری شد!")
        
        context.user_data['state'] = None
        return True

    if state == "WAITING_FOR_CONTRA_QTY":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر و بزرگتر از صفر وارد کنید.")
            return True
        
        qty = int(text)
        code = context.user_data.get('contra_item')
        
        if 'contra_cart' not in context.user_data:
            context.user_data['contra_cart'] = {}
            
        context.user_data['contra_cart'][code] = qty
        item_name = CONTRABAND_PRODUCTS[code]['name']
        await update.message.reply_text(f"🛒 تعداد {qty} عدد **{item_name}** به سبد قاچاق اضافه شد.")
        context.user_data['state'] = None
        return True

    return False

# ----------------- ۵. نمایش کارخونه من -----------------

async def show_my_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    
    clothes = db.get_user_field(user_id, "inventory_clothes") or 0
    food = db.get_user_field(user_id, "inventory_food") or 0
    toy = db.get_user_field(user_id, "inventory_toy") or 0
    house = db.get_user_field(user_id, "inventory_house") or 0
    
    cig = db.get_user_field(user_id, "inventory_cig") or 0
    diamond = db.get_user_field(user_id, "inventory_diamond") or 0
    gold = db.get_user_field(user_id, "inventory_gold") or 0
    car = db.get_user_field(user_id, "inventory_car") or 0

    text = (
        "🏭 **کارخانه و انبار محصولات شما:**\n\n"
        f"👕 لباس هاپویی: `{clothes}` عدد\n"
        f"🦴 غذای ویژه: `{food}` عدد\n"
        f"🎾 توپ بازی: `{toy}` عدد\n"
        f"🏠 لانه شیک: `{house}` عدد\n\n"
        "🕵️‍♂️ **اجناس قاچاق انبار شده:**\n"
        f"🚬 سیگار قاچاق: `{cig}` عدد\n"
        f"💎 الماس سیاه: `{diamond}` عدد\n"
        f"🪙 شمش طلا: `{gold}` عدد\n"
        f"🏎 خودروی قاچاق: `{car}` عدد"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ----------------- ۶. بخش فروش محصولات انبار -----------------

async def show_sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("👕 فروش لباس (هر عدد ۴۰)", callback_data=f"sell_clothes:{user_id}")],
        [InlineKeyboardButton("🦴 فروش غذا (هر عدد ۸۰)", callback_data=f"sell_food:{user_id}")],
        [InlineKeyboardButton("🎾 فروش توپ (هر عدد ۲۵)", callback_data=f"sell_toy:{user_id}")],
        [InlineKeyboardButton("🏠 فروش لانه (هر عدد ۸۰۰)", callback_data=f"sell_house:{user_id}")],
        [InlineKeyboardButton("🚬 فروش سیگار قاچاق (هر عدد ۱,۲۰۰)", callback_data=f"sell_cig:{user_id}")],
        [InlineKeyboardButton("💎 فروش الماس سیاه (هر عدد ۵,۰۰۰)", callback_data=f"sell_diamond:{user_id}")],
    ]
    
    await update.message.reply_text(
        "💰 **بازار سیاه و فروش محصولات**\n"
        "محصولی که می‌خواهید بفروشید را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split(":")[0]
    await query.answer()
    
    prices = {
        "sell_clothes": {"field": "inventory_clothes", "price": 40, "name": "لباس هاپویی"},
        "sell_food": {"field": "inventory_food", "price": 80, "name": "غذای ویژه"},
        "sell_toy": {"field": "inventory_toy", "price": 25, "name": "توپ بازی"},
        "sell_house": {"field": "inventory_house", "price": 800, "name": "لانه شیک"},
        "sell_cig": {"field": "inventory_cig", "price": 1200, "name": "سیگار قاچاق"},
        "sell_diamond": {"field": "inventory_diamond", "price": 5000, "name": "الماس سیاه"},
    }
    
    if data in prices:
        item = prices[data]
        current_count = db.get_user_field(user_id, item["field"]) or 0
        
        if current_count <= 0:
            await query.message.reply_text(f"❌ شما هیچ عددی از **{item['name']}** در انبار ندارید که بفروشید!")
            return
            
        db.update_field(user_id, item["field"], -1, relative=True)
        db.update_field(user_id, "points", item["price"], relative=True)
        
        await query.message.reply_text(
            f"✅ ۱ عدد **{item['name']}** با موفقیت فروخته شد!\n"
            f"💵 مبلغ **{item['price']}** به کیف پول شما اضافه شد."
        )

# ----------------- ۷. بخش شهر و اهدا -----------------

CITY_LEVEL_REQUIREMENTS = {
    1: {"treasury": 10000, "hops": 100, "dogs": 5},
    2: {"treasury": 50000, "hops": 500, "dogs": 15},
    3: {"treasury": 60000, "hops": 400, "dogs": 35},
    4: {"treasury": 500000, "hops": 2000, "dogs": 100},
    5: {"treasury": 2000000, "hops": 5000, "dogs": 250},
}

def make_progress_bar(current, target):
    if target <= 0:
        percent = 1.0
    else:
        percent = min(1.0, current / target)
    
    filled = int(round(percent * 5))
    empty = 5 - filled
    return "▰" * filled + "▱" * empty

def safe_db_call(func_name, *args):
    if not hasattr(db, func_name):
        return None
    func = getattr(db, func_name)
    try:
        return func(*args)
    except TypeError:
        try:
            return func()
        except TypeError:
            if len(args) > 1:
                return func(args[0])
            return None

async def city_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    chat = update.effective_chat
    chat_id = chat.id if chat else None
    chat_title = chat.title if chat and chat.title else "شهر هاپویی"
    
    treasury = safe_db_call("get_city_treasury", chat_id) or 0
    total_hops = safe_db_call("get_group_total_hops", chat_id) or safe_db_call("get_total_hops", chat_id) or 0
    total_dogs = safe_db_call("get_group_total_dogs", chat_id) or safe_db_call("get_total_dogs", chat_id) or 0
    current_level = safe_db_call("get_city_level", chat_id) or 1

    next_req = CITY_LEVEL_REQUIREMENTS.get(current_level, CITY_LEVEL_REQUIREMENTS[5])
    
    if (treasury >= next_req["treasury"] and 
        total_hops >= next_req["hops"] and 
        total_dogs >= next_req["dogs"] and current_level < 5):
        
        current_level += 1
        safe_db_call("set_city_level", current_level)
            
        await update.message.reply_text(f"🎉 **تبریک! شهر هاپویی شما به سطح {current_level} ارتقا یافت!** 🎉", parse_mode="Markdown")
        next_req = CITY_LEVEL_REQUIREMENTS.get(current_level, CITY_LEVEL_REQUIREMENTS[5])

    bar_treasury = make_progress_bar(treasury, next_req["treasury"])
    bar_hops = make_progress_bar(total_hops, next_req["hops"])
    bar_dogs = make_progress_bar(total_dogs, next_req["dogs"])

    treasury_str = format_balance(treasury)
    target_treasury_str = format_balance(next_req["treasury"])

    next_level_text = f"سطح {current_level + 1}" if current_level < 5 else "حداکثر سطح"

    text = (
        f"╮──「  شهر هاپو  」\n\n"
        f"┐─  نام : {chat_title}\n"
        f"┐─  رتبه جهانی : #1\n"
        f"└─  \n\n"
        f"  آمار شهر:\n"
        f"┐─  سطح : {current_level} / 5\n"
        f"┐─  خزانه : {treasury_str}\n"
        f"┐─  کل هاپ : {total_hops:,}\n"
        f"┐─  کل سگ : {total_dogs:,}\n\n"
        f"  باف‌های فعال (سطح {current_level}):\n"
        f"┐─  کولداون هاپ : {max(300 - current_level * 5, 200)}s (اصلی 300s)\n\n"
        f"  پیشرفت به {next_level_text}:\n"
        f"┐─  خزانه : {treasury_str} / {target_treasury_str}  {bar_treasury}\n"
        f"┐─  هاپ‌های کل : {total_hops:,} / {next_req['hops']:,}  {bar_hops}\n"
        f"┐─  سگ‌های خریداری شده : {total_dogs:,} / {next_req['dogs']:,}  {bar_dogs}\n\n"
        f"📌 برای کمک به خزانه بنویس: `اهدا [مقدار]`"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def donate_city(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    args = context.args or update.message.text.split()[1:]

    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ لطفاً مبلغ اهدا را به عدد مشخص کنید.\nمثال: `اهدا 1000`", parse_mode="Markdown")
        return

    amount = int(args[0])
    if amount <= 0:
        await update.message.reply_text("❌ مبلغ اهدا باید بیشتر از 0 باشد.")
        return

    user_points = int(db.get_user_field(user_id, "points") or 0)
    if user_points < amount:
        await update.message.reply_text("❌ شما سکه کافی در کیف پول خود ندارید!")
        return

    db.update_field(user_id, "points", -amount, relative=True)
    
    if hasattr(db, "add_city_donation"):
        db.add_city_donation(user_id, amount)
    elif hasattr(db, "add_city_treasury"):
        db.add_city_treasury(amount)
    elif hasattr(db, "update_global_field"):
        db.update_global_field("city_treasury", amount)

    await update.message.reply_text(f"✨ با موفقیت مبلغ **{format_balance(amount)}** به خزانه شهر اهدا شد! 🏛", parse_mode="Markdown")

async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    return await show_factory(update, context)

async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    return await show_contraband(update, context)

handle_sell = show_sell_menu
