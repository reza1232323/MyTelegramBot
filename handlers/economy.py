import asyncio
import random
import database as db
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.pet import format_balance

# ----------------- لیست محصولات -----------------

# محصولات کارخانه
FACTORY_PRODUCTS = {
    "clothes": {"name": "👕 لباس هاپویی", "price": 50, "db_field": "inventory_clothes"},
    "food": {"name": "🦴 غذای ویژه", "price": 100, "db_field": "inventory_food"},
    "toy": {"name": "🎾 توپ بازی", "price": 30, "db_field": "inventory_toy"},
    "house": {"name": "🏠 لانه شیک", "price": 1000, "db_field": "inventory_house"},
}

# اجناس قاچاق
CONTRABAND_PRODUCTS = {
    "cig": {"name": "🚬 سیگار قاچاق", "cost": 500, "profit": 1500, "db_field": "inventory_cig"},
    "diamond": {"name": "💎 الماس سیاه", "cost": 2000, "profit": 6000, "db_field": "inventory_diamond"},
    "gold": {"name": "🪙 شمش طلا", "cost": 5000, "profit": 15000, "db_field": "inventory_gold"},
    "car": {"name": "🏎 خودروی قاچاق", "cost": 10000, "profit": 35000, "db_field": "inventory_car"},
}

# ----------------- ذخیره‌سازی قمارهای فعال -----------------
active_gambles = {}

# ----------------- ۱. بخش کارخانه -----------------

async def show_factory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    in_jail, _ = db.is_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید و به کارخانه دسترسی ندارید!")
        return

    keyboard = []
    for code, item in FACTORY_PRODUCTS.items():
        price_str = format_balance(item['price'])
        keyboard.append([InlineKeyboardButton(f"{item['name']} - {price_str}", callback_data=f"buy_fac_{code}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏭 **به کارخانه خوش آمدید!**\nمحصول مورد نظر برای خرید را انتخاب کنید:", reply_markup=reply_markup, parse_mode="Markdown")

async def factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
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
    
    in_jail, jail_until = db.is_in_jail(user_id)
    if in_jail:
        keyboard = [[InlineKeyboardButton("🔓 آزادی فوری (۲۰,۰۰۰ میو/هاپ)", callback_data="pay_bail")]]
        await update.message.reply_text(
            f"🚨 **شما در زندان هستید!**\n"
            f"⏱ زمان آزادی: تا {jail_until.strftime('%H:%M')}\n"
            f"می‌توانید ۱۵ دقیقه صبر کنید یا با پرداخت ۲۰,۰۰۰ وثیقه فوراً آزاد شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keyboard = []
    for code, item in CONTRABAND_PRODUCTS.items():
        cost_str = format_balance(item['cost'])
        profit_str = format_balance(item['profit'])
        keyboard.append([InlineKeyboardButton(f"{item['name']} (هزینه: {cost_str} | سود: {profit_str})", callback_data=f"select_contra_{code}")])
    
    keyboard.append([InlineKeyboardButton("🚀 شروع عملیات قاچاق", callback_data="start_smuggling")])
    
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
    data = query.data
    await query.answer()

    if data == "pay_bail":
        points = db.get_user_field(user_id, "points") or 0
        if points < 20000:
            await query.message.reply_text("❌ شما ۲۰,۰۰۰ موجودی برای وثیقه ندارید!")
            return
        
        db.update_field(user_id, "points", -20000, relative=True)
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

        # جلوگیری از قاچاق همزمان
        if context.user_data.get('is_smuggling_active', False):
            await query.message.reply_text("⏳ شما از قبل یک قاچاق در انتظار دارید! صبر کنید تا محموله قبلی برسد.")
            return

        total_cost = sum(CONTRABAND_PRODUCTS[code]['cost'] * qty for code, qty in cart.items())
        points = db.get_user_field(user_id, "points") or 0

        if points < total_cost:
            await query.message.reply_text(f"❌ موجودی کافی نیست! هزینه کل: {format_balance(total_cost)}")
            return

        db.update_field(user_id, "points", -total_cost, relative=True)
        context.user_data['contra_cart'] = {}
        
        # فعال کردن قاچاق
        context.user_data['is_smuggling_active'] = True
        
        await query.message.reply_text("🚚 **عملیات قاچاق آغاز شد!**\nمحموله ارسال شد. نتیجه تا ۳۰ دقیقه دیگر مشخص می‌شود...")

        asyncio.create_task(process_smuggling_result(context, user_id, total_cost, cart))

async def process_smuggling_result(context, user_id, total_cost, cart):
    await asyncio.sleep(1800) # ۳۰ دقیقه انتظار
    
    # آزاد کردن وضعیت قاچاق
    context.user_data['is_smuggling_active'] = False
    
    is_busted = random.random() < 0.35 # ۳۵٪ شانس گیر افتادن

    if is_busted:
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
    """ایجاد قمار جدید با فرمت: قمار [مبلغ] [تعداد افراد]"""
    user = update.effective_user
    chat = update.effective_chat
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ فرمت صحیح: `قمار [مبلغ] [تعداد نفرات]`\nمثال: `قمار 100 3`", parse_mode="Markdown")
        return

    try:
        amount = int(context.args[0])
        max_players = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ مبلغ و تعداد افراد باید عدد معتبر باشند.")
        return

    if amount <= 0 or max_players < 2:
        await update.message.reply_text("❌ حداقل مبلغ ۱ و حداقل تعداد شرکت‌کنندگان ۲ نفر است.")
        return

    # بررسی موجودی سازنده قمار
    user_points = db.get_user_field(user.id, "points") or 0
    if user_points < amount:
        await update.message.reply_text("❌ کافی نمی‌باشد تعداد هاپ پوینت‌های شما.")
        return

    # کسر مبلغ ورودی از سازنده
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
    """مدیریت کلیک روی دکمه شرکت در قمار"""
    query = update.callback_query
    user = query.from_user
    data_parts = query.data.split(":")
    gamble_id = data_parts[1]

    if gamble_id not in active_gambles:
        await query.answer("❌ این قمار پایان یافته یا منقضی شده است.", show_alert=True)
        return

    gamble = active_gambles[gamble_id]

    # بررسی ثبت‌نام تکراری
    player_ids = [p[0] for p in gamble["players"]]
    if user.id in player_ids:
        await query.answer("❌ شما قبلاً در این قمار شرکت کرده‌اید!", show_alert=True)
        return

    # بررسی موجودی شرکت‌کننده
    user_points = db.get_user_field(user.id, "points") or 0
    if user_points < gamble["amount"]:
        await query.answer("❌ برای شرکت در این قمار موجودی کافی ندارید.", show_alert=True)
        return

    # کسر ورودی و اضافه کردن به لیست
    db.update_field(user.id, "points", -gamble["amount"], relative=True)
    gamble["players"].append((user.id, user.full_name))

    current_count = len(gamble["players"])
    total_prize = gamble["amount"] * current_count

    # اگر ظرفیت تکمیل شد
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
        # بروزرسانی تعداد افراد در پنل قمار
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

# ----------------- ۴. دریافت تعداد از پیام متنی -----------------

async def handle_factory_and_smuggle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    
    if state not in ["WAITING_FOR_FACTORY_QTY", "WAITING_FOR_CONTRA_QTY"]:
        return False

    text = update.message.text
    user_id = update.effective_user.id

    if state == "WAITING_FOR_FACTORY_QTY":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر و بزرگتر از صفر وارد کنید.")
            return True
        
        qty = int(text)
        product_code = context.user_data.get('buy_product')
        product = FACTORY_PRODUCTS[product_code]
        total_price = product['price'] * qty
        
        points = db.get_user_field(user_id, "points") or 0
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

# ----------------- ۵. نمایش کارخونه من (انبار محصولات) -----------------

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
    keyboard = [
        [InlineKeyboardButton("👕 فروش لباس (هر عدد ۴۰)", callback_data="sell_clothes")],
        [InlineKeyboardButton("🦴 فروش غذا (هر عدد ۸۰)", callback_data="sell_food")],
        [InlineKeyboardButton("🎾 فروش توپ (هر عدد ۲۵)", callback_data="sell_toy")],
        [InlineKeyboardButton("🏠 فروش لانه (هر عدد ۸۰۰)", callback_data="sell_house")],
        [InlineKeyboardButton("🚬 فروش سیگار قاچاق (هر عدد ۱,۲۰۰)", callback_data="sell_cig")],
        [InlineKeyboardButton("💎 فروش الماس سیاه (هر عدد ۵,۰۰۰)", callback_data="sell_diamond")],
    ]
    
    await update.message.reply_text(
        "💰 **بازار سیاه و فروش محصولات**\n"
        "محصولی که می‌خواهید بفروشید را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
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
    1: {"treasury": 10000, "hops": 100, "dogs": 5, "bones": 10, "fish": 10},
    2: {"treasury": 50000, "hops": 500, "dogs": 15, "bones": 30, "fish": 30},
    3: {"treasury": 60000, "hops": 400, "dogs": 35, "bones": 80, "fish": 40},
    4: {"treasury": 500000, "hops": 2000, "dogs": 100, "bones": 200, "fish": 200},
    5: {"treasury": 2000000, "hops": 5000, "dogs": 250, "bones": 500, "fish": 500},
}

def make_progress_bar(current, target):
    """ساخت نوار پیشرفت ۵ تایی با مربعات پر و خالی"""
    if target <= 0:
        percent = 1.0
    else:
        percent = min(1.0, current / target)
    
    filled = int(round(percent * 5))
    empty = 5 - filled
    return "▰" * filled + "▱" * empty

async def city_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    chat = update.effective_chat
    chat_title = chat.title if chat and chat.title else "شهر هاپویی"
    
    treasury = db.get_city_treasury() if hasattr(db, "get_city_treasury") else 0
    total_hops = db.get_total_hops() if hasattr(db, "get_total_hops") else 0
    total_dogs = db.get_total_dogs() if hasattr(db, "get_total_dogs") else 0
    total_bones = db.get_total_item("inventory_food") if hasattr(db, "get_total_item") else 0
    total_fish = db.get_total_item("inventory_toy") if hasattr(db, "get_total_item") else 0
    
    current_level = db.get_city_level() if hasattr(db, "get_city_level") else 1
    next_req = CITY_LEVEL_REQUIREMENTS.get(current_level, CITY_LEVEL_REQUIREMENTS[5])
    
    if (treasury >= next_req["treasury"] and 
        total_hops >= next_req["hops"] and 
        total_dogs >= next_req["dogs"] and 
        total_bones >= next_req["bones"] and 
        total_fish >= next_req["fish"] and current_level < 10):
        
        current_level += 1
        if hasattr(db, "set_city_level"):
            db.set_city_level(current_level)
            
        await update.message.reply_text(f"🎉 **تبریک! شهر هاپویی شما به سطح {current_level} ارتقا یافت!** 🎉")
        next_req = CITY_LEVEL_REQUIREMENTS.get(current_level, CITY_LEVEL_REQUIREMENTS[5])

    bar_treasury = make_progress_bar(treasury, next_req["treasury"])
    bar_hops = make_progress_bar(total_hops, next_req["hops"])
    bar_dogs = make_progress_bar(total_dogs, next_req["dogs"])
    bar_bones = make_progress_bar(total_bones, next_req["bones"])
    bar_fish = make_progress_bar(total_fish, next_req["fish"])

    treasury_str = format_balance(treasury)
    target_treasury_str = format_balance(next_req["treasury"])

    text = (
        f"╮──「  شهر هاپو  」\n\n"
        f"┐─  نام : {chat_title}\n"
        f"┐─  رتبه جهانی : #1\n"
        f"└─  \n\n"
        f"  آمار شهر:\n"
        f"┐─  سطح : {current_level} / 10\n"
        f"┐─  خزانه : {treasury_str}\n"
        f"┐─  کل هاپ : {total_hops:,}\n"
        f"┐─  کل سگ : {total_dogs:,}\n"
        f"  باف‌های فعال (سطح {current_level}):\n"
        f"┐─  کولداون هاپ : {max(300 - current_level * 5, 200)}s (اصلی 300s)\n"
        f"  پیشرفت به سطح {current_level + 1}:\n"
        f"┐─  خزانه : {treasury_str} / {target_treasury_str}  {bar_treasury}\n"
        f"┐─  هاپ‌های کل : {total_hops:,} / {next_req['hops']:,}  {bar_hops}\n"
        f"┐─  سگ‌های خریداری شده : {total_dogs:,} / {next_req['dogs']:,}  {bar_dogs}\n"
        f"  برای کمک به خزانه بنویس: اهدا [مقدار]"
    )
    
    await update.message.reply_text(text)

# توابع کمکی برای سازگاری با main.py
async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    return await show_factory(update, context)

async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    return await show_contraband(update, context)

handle_sell = show_sell_menu
