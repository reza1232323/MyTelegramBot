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

# ----------------- ۴. نمایش کارخونه من (انبار محصولات کاربر) -----------------

async def show_my_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    
    # گرفتن تعداد محصولات کارخانه و قاچاق از دیتابیس کاربر
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

        total_cost = sum(CONTRABAND_PRODUCTS[code]['cost'] * qty for code, qty in cart.items())
        points = db.get_user_field(user_id, "points") or 0

        if points < total_cost:
            await query.message.reply_text(f"❌ موجودی کافی نیست! هزینه کل: {format_balance(total_cost)}")
            return

        db.update_field(user_id, "points", -total_cost, relative=True)
        context.user_data['contra_cart'] = {}
        
        await query.message.reply_text("🚚 **عملیات قاچاق آغاز شد!**\nمحموله ارسال شد. نتیجه تا ۱ ساعت دیگر مشخص می‌شود...")

        asyncio.create_task(process_smuggling_result(context, user_id, total_cost, cart))

async def process_smuggling_result(context, user_id, total_cost, cart):
    await asyncio.sleep(3600) # ۱ ساعت انتظار
    
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

# ----------------- ۳. دریافت تعداد از پیام متنی -----------------

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
    # این دو تابع را به انتهای فایل handlers/economy.py اضافه کن:

async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    return await show_factory(update, context)

async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    return await show_contraband(update, context)
