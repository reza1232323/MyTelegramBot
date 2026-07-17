
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ========== تنظیمات ==========
TOKEN = "8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI"
CHANNEL_ID = -1004296146485
CHANNEL_USERNAME = "@starzland_shop"
ADMIN_IDS = [5571951071, 6691993264]
BOT_USERNAME = "starzland_bot"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# ========== حالت‌های مکالمه ==========
WAITING_FOR_WALLET, WAITING_FOR_RECEIVER, WAITING_FOR_POST_LINK = range(3)

# ========== قیمت‌ها ==========
PRICES = {
    "ton": 340,
    "stars_direct": {"50": 165, "100": 339, "150": 500, "200": 660, "500": 1600},
    "stars_post": {"1": 4000, "5": 20000, "10": 40000, "25": 100000, "50": 200000},
    "gift": {"15": 55, "25": 85, "50": 170, "100": 339},
}

# ========== دیتابیس ==========
conn = sqlite3.connect('shop_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        item_type TEXT,
        quantity INTEGER,
        price INTEGER,
        extra_info TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0
    )
''')
conn.commit()

def fmt(n):
    return f"{n:,}"

async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False

def create_user(user_id, username):
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, created_at) VALUES (?, ?, ?)',
                   (user_id, username, int(datetime.now().timestamp())))
    conn.commit()

def create_order(user_id, username, item_type, quantity, price, extra_info=""):
    cursor.execute('''
        INSERT INTO orders (user_id, username, item_type, quantity, price, extra_info, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, item_type, quantity, price, extra_info, int(datetime.now().timestamp())))
    conn.commit()
    return cursor.lastrowid

def update_order_extra(order_id, extra_info):
    cursor.execute('UPDATE orders SET extra_info = ? WHERE id = ?', (extra_info, order_id))
    conn.commit()

# ========== استارت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    if not await is_member(user_id, context):
        keyboard = [
            [InlineKeyboardButton("📢 جوین کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ تایید عضویت", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            "🔒 *برای استفاده از ربات، ابتدا در کانال عضو شوید:*\n\n"
            f"📢 {CHANNEL_USERNAME}\n\n"
            "بعد از عضویت، دکمه تایید رو بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    create_user(user_id, username)

    keyboard = [
        [InlineKeyboardButton("🪙 خرید تون", callback_data="buy_ton")],
        [InlineKeyboardButton("⭐ استارز مستقیم", callback_data="buy_stars_direct")],
        [InlineKeyboardButton("📝 استارز رو پست", callback_data="buy_stars_post")],
        [InlineKeyboardButton("🎁 گیفت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
    ]


    await update.message.reply_text(
        "🌟 *به فروشگاه استارز لند خوش آمدی!* 🌟\n\n"
        "🪙 *تون:* 340 تومن\n"
        "⭐ *استارز مستقیم:* از 165 تومن\n"
        "📝 *استارز رو پست:* 4000 تومن هر عدد\n"
        "🎁 *گیفت استارزی:* از 55 تومن\n\n"
        "👇 یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== تایید عضویت ==========
async def check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if await is_member(user_id, context):
        await query.edit_message_text("✅ عضویت تایید شد! /start رو بزن.")
    else:
        await query.edit_message_text("❌ هنوز عضو کانال نشدی!\nلطفا اول عضو شو.")

# ========== خرید تون ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("💰 ۱ تون = 340 تومن", callback_data="ton_1")],
        [InlineKeyboardButton("💰 ۵ تون = 1,700 تومن", callback_data="ton_5")],
        [InlineKeyboardButton("💰 ۱۰ تون = 3,400 تومن", callback_data="ton_10")],
        [InlineKeyboardButton("💰 ۵۰ تون = 17,000 تومن", callback_data="ton_50")],
        [InlineKeyboardButton("💰 ۱۰۰ تون = 34,000 تومن", callback_data="ton_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text(
        "🪙 *خرید تون (Toncoin)*\n\n"
        "💰 هر تون = 340 تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید استارز مستقیم ==========
async def buy_stars_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⭐ ۵۰ = 165 تومن", callback_data="stars_direct_50")],
        [InlineKeyboardButton("⭐ ۱۰۰ = 339 تومن", callback_data="stars_direct_100")],
        [InlineKeyboardButton("⭐ ۱۵۰ = 500 تومن", callback_data="stars_direct_150")],
        [InlineKeyboardButton("⭐ ۲۰۰ = 660 تومن", callback_data="stars_direct_200")],
        [InlineKeyboardButton("⭐ ۵۰۰ = 1,600 تومن", callback_data="stars_direct_500")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text(
        "⭐ *استارز مستقیم*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۵۰ = 165 تومن\n"
        "• ۱۰۰ = 339 تومن\n"
        "• ۱۵۰ = 500 تومن\n"
        "• ۲۰۰ = 660 تومن\n"
        "• ۵۰۰ = 1,600 تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید استارز رو پست ==========
async def buy_stars_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📝 ۱ = 4,000 تومن", callback_data="stars_post_1")],
        [InlineKeyboardButton("📝 ۵ = 20,000 تومن", callback_data="stars_post_5")],
        [InlineKeyboardButton("📝 ۱۰ = 40,000 تومن", callback_data="stars_post_10")],
        [InlineKeyboardButton("📝 ۲۵ = 100,000 تومن", callback_data="stars_post_25")],
        [InlineKeyboardButton("📝 ۵۰ = 200,000 تومن", callback_data="stars_post_50")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text(
        "📝 *استارز رو پست*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۱ = 4,000 تومن\n"
        "• ۵ = 20,000 تومن\n"
        "• ۱۰ = 40,000 تومن\n"
        "• ۲۵ = 100,000 تومن\n"
        "• ۵۰ = 200,000 تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید گیفت استارزی ==========
async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎁 ۱۵ = 55 تومن", callback_data="gift_15")],
        [InlineKeyboardButton("🎁 ۲۵ = 85 تومن", callback_data="gift_25")],
        [InlineKeyboardButton("🎁 ۵۰ = 170 تومن", callback_data="gift_50")],
        [InlineKeyboardButton("🎁 ۱۰۰ = 339 تومن", callback_data="gift_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text(
        "🎁 *گیفت استارزی*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۱۵ = 55 تومن\n"
        "• ۲۵ = 85 تومن\n"
        "• ۵۰ = 170 تومن\n"
        "• ۱۰۰ = 339 تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== پردازش خرید با دریافت اطلاعات تکمیلی ==========
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    data = query.data.split('_')
    item_type = data[0]
    qty = int(data[1])

    # تعیین قیمت و نام محصول
    if item_type == "ton":
        price = qty * PRICES["ton"]
        item_name = f"تون ({qty})"
        extra_prompt = "🪙 لطفاً آدرس ولت (Wallet) خود را برای دریافت تون وارد کن:"
        next_state = WAITING_FOR_WALLET
    elif item_type == "stars_direct":
        price = PRICES["stars_direct"][str(qty)]
        item_name = f"استارز مستقیم ({qty})"
        extra_prompt = "⭐ لطفاً آیدی تلگرام (یوزرنیم) فردی که استارز رو دریافت میکنه رو وارد کن:"
        next_state = WAITING_FOR_RECEIVER
    elif item_type == "stars_post":
        price = PRICES["stars_post"][str(qty)]
        item_name = f"استارز رو پست ({qty})"
        extra_prompt = "📝 لطفاً لینک پست مورد نظر رو بفرست:"
        next_state = WAITING_FOR_POST_LINK
    elif item_type == "gift":
        price = PRICES["gift"][str(qty)]
        item_name = f"گیفت استارزی ({qty})"
        # گیفت نیاز به اطلاعات اضافی نداره
        order_id = create_order(user_id, username, item_type, qty, price)
        await show_payment(update, context, order_id, item_name, price)
        return
    else:
        await query.edit_message_text("❌ خطا!")
        return

    # ذخیره سفارش با وضعیت pending (اطلاعات اضافی بعداً تکمیل میشه)
    order_id = create_order(user_id, username, item_type, qty, price, "")
    context.user_data['temp_order_id'] = order_id
    context.user_data['temp_item_name'] = item_name
    context.user_data['temp_price'] = price

    # درخواست اطلاعات اضافی
    await query.edit_message_text(
        f"📋 *{item_name}*\n\n"
        f"💰 مبلغ: {fmt(price)} تومن\n\n"
        f"{extra_prompt}\n\n"
        f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
        parse_mode="Markdown"
    )
    return next_state

# ========== دریافت اطلاعات اضافی ==========
async def get_extra_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    order_id = context.user_data.get('temp_order_id')
    if not order_id:
        await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
        return ConversationHandler.END
    
    # ذخیره اطلاعات اضافی
    update_order_extra(order_id, text)
    
    item_name = context.user_data.get('temp_item_name')
    price = context.user_data.get('temp_price')
    
    await show_payment(update, context, order_id, item_name, price)
    return ConversationHandler.END

# ========== نمایش اطلاعات پرداخت ==========
async def show_payment(update, context, order_id, item_name, price):

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # دریافت اطلاعات اضافی
    cursor.execute('SELECT extra_info FROM orders WHERE id = ?', (order_id,))
    extra = cursor.fetchone()
    extra_info = extra[0] if extra else ""
    
    keyboard = [
        [InlineKeyboardButton("✅ پرداخت انجام شد", callback_data=f"payment_done_{order_id}")],
        [InlineKeyboardButton("❌ لغو سفارش", callback_data=f"cancel_{order_id}")],
    ]
    
    extra_text = ""
    if extra_info:
        extra_text = f"\n📝 اطلاعات تکمیلی:\n{extra_info}\n"
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            f"📋 *تایید سفارش*\n\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_name}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"{extra_text}\n"
            f"💳 *شماره کارت:*\n"
            f"6037-9970-1234-5678\n"
            f"🏦 بانک ملی\n\n"
            f"💰 *مبلغ واریز:* {fmt(price)} تومن\n"
            f"🆔 *شماره سفارش:* {order_id}\n\n"
            f"⚠️ بعد از واریز، دکمه 'پرداخت انجام شد' رو بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"📋 *تایید سفارش*\n\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_name}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"{extra_text}\n"
            f"💳 *شماره کارت:*\n"
            f"6037-9970-1234-5678\n"
            f"🏦 بانک ملی\n\n"
            f"💰 *مبلغ واریز:* {fmt(price)} تومن\n"
            f"🆔 *شماره سفارش:* {order_id}\n\n"
            f"⚠️ بعد از واریز، دکمه 'پرداخت انجام شد' رو بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    # اطلاع به ادمین با اطلاعات کامل
    for admin_id in ADMIN_IDS:
        try:
            msg = f"🆕 *سفارش جدید*\n\n"
            msg += f"👤 کاربر: @{username}\n"
            msg += f"🆔 آیدی: {user_id}\n"
            msg += f"🛒 محصول: {item_name}\n"
            msg += f"💰 مبلغ: {fmt(price)} تومن\n"
            msg += f"🆔 شماره سفارش: {order_id}\n"
            if extra_info:
                msg += f"📝 اطلاعات تکمیلی: {extra_info}\n"
            msg += f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
            
            await context.bot.send_message(admin_id, msg, parse_mode="Markdown")
        except:
            pass

# ========== پرداخت انجام شد ==========
async def payment_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    order_id = int(query.data.split('_')[2])
    
    cursor.execute('UPDATE orders SET status = "paid" WHERE id = ?', (order_id,))
    conn.commit()
    
    cursor.execute('SELECT username, item_type, quantity, price, extra_info FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if order:
        username, item_type, qty, price, extra_info = order
        
        extra_text = ""
        if extra_info:
            extra_text = f"\n📝 اطلاعات: {extra_info}\n"
        
        await query.edit_message_text(
            f"✅ *سفارش شما ثبت شد!*\n\n"
            f"🌟 *خدمات استارز لند آنی هست!*\n"
            f"⚡️ سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_type} ({qty})\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"{extra_text}\n"
            f"⏳ لطفاً چند دقیقه صبر کنید...\n"

f"🔜 به زودی تحویل داده میشه!\n\n"
            f"🙏 از اعتماد شما سپاسگزاریم!",
            parse_mode="Markdown"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                msg = f"✅ *پرداخت تایید شد!*\n\n"
                msg += f"👤 کاربر: @{username}\n"
                msg += f"🆔 آیدی: {user_id}\n"
                msg += f"🆔 شماره سفارش: {order_id}\n"
                msg += f"🛒 محصول: {item_type} ({qty})\n"
                msg += f"💰 مبلغ: {fmt(price)} تومن\n"
                if extra_info:
                    msg += f"📝 اطلاعات تکمیلی: {extra_info}\n"
                msg += f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
                
                await context.bot.send_message(admin_id, msg, parse_mode="Markdown")
            except:
                pass

# ========== لغو سفارش ==========
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split('_')[2])
    
    cursor.execute('UPDATE orders SET status = "canceled" WHERE id = ?', (order_id,))
    conn.commit()
    
    await query.edit_message_text(
        f"❌ *سفارش لغو شد!*\n\n"
        f"🆔 شماره سفارش: {order_id}\n\n"
        f"میتونی دوباره سفارش بدی. 🛒",
        parse_mode="Markdown"
    )

# ========== سفارشات من ==========
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    cursor.execute('''
        SELECT id, item_type, quantity, price, status, extra_info, created_at 
        FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    ''', (user_id,))
    orders = cursor.fetchall()
    
    if not orders:
        await query.edit_message_text(
            "📋 *سفارشات شما*\n\n"
            "❌ هیچ سفارشی ثبت نکردی!",
            parse_mode="Markdown"
        )
        return
    
    text = "📋 *سفارشات اخیر شما*\n\n"
    for o in orders:
        id, item_type, qty, price, status, extra_info, created_at = o
        status_emoji = "✅" if status == "paid" else "⏳" if status == "pending" else "❌"
        date = datetime.fromtimestamp(created_at).strftime("%Y/%m/%d %H:%M")
        text += f"🆔 #{id} - {item_type} ({qty}) - {fmt(price)} تومن {status_emoji}\n"
        if extra_info:
            text += f"   📝 {extra_info}\n"
        text += f"   📅 {date}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== برگشت به منو ==========
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    if not await is_member(user_id, context):
        await query.edit_message_text("❌ ابتدا در کانال عضو شوید!")
        return
    
    create_user(user_id, username)
    
    keyboard = [
        [InlineKeyboardButton("🪙 خرید تون", callback_data="buy_ton")],
        [InlineKeyboardButton("⭐ استارز مستقیم", callback_data="buy_stars_direct")],
        [InlineKeyboardButton("📝 استارز رو پست", callback_data="buy_stars_post")],
        [InlineKeyboardButton("🎁 گیفت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
    ]
    
    await query.edit_message_text(
        "🛒 *منوی اصلی*\n\n"
        "💰 تون: 340 تومن\n"
        "⭐ استارز مستقیم: از 165 تومن\n"
        "📝 استارز رو پست: 4000 تومن هر عدد\n"
        "🎁 گیفت استارزی: از 55 تومن\n\n"
        "👇 یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== مدیریت ==========
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "check_sub":
        await check_sub(update, context)
    elif data == "back_to_menu":
        await back_to_menu(update, context)
    elif data == "buy_ton":
        await buy_ton(update, context)
    elif data.startswith("ton_"):
        await process_purchase(update, context)
    elif data == "buy_stars_direct":
        await buy_stars_direct(update, context)
    elif data.startswith("stars_direct_"):
        await process_purchase(update, context)
    elif data == "buy_stars_post":
        await buy_stars_post(update, context)
    elif data.startswith("stars_post_"):
        await process_purchase(update, context)
    elif data == "buy_gift":
        await buy_gift(update, context)
    elif data.startswith("gift_"):
        await process_purchase(update, context)
    elif data.startswith("payment_done_"):
        await payment_done(update, context)
    elif data.startswith("cancel_"):
        await cancel_order(update, context)
    elif data == "my_orders":
        await my_orders(update, context)

# ========== اجرا ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    # کانورسیشن هندلر برای دریافت اطلاعات اضافی
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(process_purchase, pattern="^(ton_|stars_direct_|stars_post_|gift_)")
        ],
        states={
            WAITING_FOR_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_info)
            ],
            WAITING_FOR_RECEIVER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_info)
            ],
            WAITING_FOR_POST_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_info)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))
    app.add_handler(conv_handler)
    
    print("🌟 ربات فروش استارز لند روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
