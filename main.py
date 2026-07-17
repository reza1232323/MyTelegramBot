import logging
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ========== تنظیمات ==========
TOKEN = "8896536456:AAGA8c2DxVjJxZpW8U85aDHVxRCweWf83TE"
CHANNEL_ID = "@starzland_shop"  # آیدی کانال (با @)
ADMIN_IDS = [5571951071, 6691993264]  # آیدی عددی ادمین‌ها
BOT_USERNAME = "ghorghoryanbot"  # یوزرنیم ربات (بدون @)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# ========== قیمت‌ها ==========
PRICES = {
    "ton": 340,  # هر تون ۳۴۰ تومن
    "stars_direct": {
        "50": 165,
        "100": 339,
        "150": 500,
        "200": 660,
        "500": 1600,
    },
    "stars_post": {
        "1": 4000,  # هر استارز رو پست ۴۰۰۰ تومن
        "5": 20000,
        "10": 40000,
        "25": 100000,
        "50": 200000,
    },
    "gift": {
        "15": 55,
        "25": 85,
        "50": 170,
        "100": 339,
    }
}

# ========== دیتابیس ==========
conn = sqlite3.connect('shop_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at INTEGER DEFAULT 0,
        total_purchases INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_type TEXT,
        quantity INTEGER,
        price INTEGER,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0,
        payment_method TEXT,
        payment_info TEXT
    )
''')
conn.commit()

# ========== توابع کمکی ==========
async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [ChatMember.OWNER, ChatMember.ADMINISTRATOR, ChatMember.MEMBER]
    except:
        return False

def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def create_user(user_id, username):
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, created_at)
        VALUES (?, ?, ?)
    ''', (user_id, username, int(datetime.now().timestamp())))
    conn.commit()

def create_order(user_id, item_type, quantity, price, payment_method="", payment_info=""):
    cursor.execute('''
        INSERT INTO orders (user_id, item_type, quantity, price, created_at, payment_method, payment_info)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, item_type, quantity, price, int(datetime.now().timestamp()), payment_method, payment_info))
    conn.commit()
    return cursor.lastrowid

def fmt(n):
    return f"{n:,}"

# ========== دکمه‌های منو ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # بررسی عضویت در کانال
    if not await is_member(user_id, context):
        keyboard = [
            [InlineKeyboardButton("📢 جوین کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton("✅ تایید عضویت", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            "🔒 *برای استفاده از ربات، ابتدا در کانال زیر عضو شوید:*\n\n"
            f"📢 {CHANNEL_ID}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    create_user(user_id, username)
    
    keyboard = [
        [InlineKeyboardButton("🪙 خرید تون (Toncoin)", callback_data="buy_ton")],
        [InlineKeyboardButton("⭐ خرید استارز مستقیم", callback_data="buy_stars_direct")],

        [InlineKeyboardButton("📝 خرید استارز رو پست", callback_data="buy_stars_post")],
        [InlineKeyboardButton("🎁 خرید گیفت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("📊 وضعیت سفارشات", callback_data="my_orders")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]
    
    await update.message.reply_text(
        "🛒 *به فروشگاه استارز و تون خوش آمدی!*\n\n"
        "💰 قیمت تون: ۳۴۰ تومن\n"
        "⭐ استارز مستقیم: از ۱۶۵ تومن\n"
        "📝 استارز رو پست: ۴۰۰۰ تومن هر عدد\n"
        "🎁 گیفت استارزی: از ۵۵ تومن\n\n"
        "یکی از گزینه‌ها رو انتخاب کن 👇",
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
        await query.edit_message_text(f"❌ هنوز عضو کانال نشدی!\nلطفا اول در {CHANNEL_ID} عضو شو.")

# ========== خرید تون ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("💰 ۱ تون - ۳۴۰ تومن", callback_data="ton_1")],
        [InlineKeyboardButton("💰 ۵ تون - ۱,۷۰۰ تومن", callback_data="ton_5")],
        [InlineKeyboardButton("💰 ۱۰ تون - ۳,۴۰۰ تومن", callback_data="ton_10")],
        [InlineKeyboardButton("💰 ۵۰ تون - ۱۷,۰۰۰ تومن", callback_data="ton_50")],
        [InlineKeyboardButton("💰 ۱۰۰ تون - ۳۴,۰۰۰ تومن", callback_data="ton_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "🪙 *خرید تون (Toncoin)*\n\n"
        "💰 هر تون = ۳۴۰ تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید استارز مستقیم ==========
async def buy_stars_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⭐ ۵۰ استارز - ۱۶۵ تومن", callback_data="stars_direct_50")],
        [InlineKeyboardButton("⭐ ۱۰۰ استارز - ۳۳۹ تومن", callback_data="stars_direct_100")],
        [InlineKeyboardButton("⭐ ۱۵۰ استارز - ۵۰۰ تومن", callback_data="stars_direct_150")],
        [InlineKeyboardButton("⭐ ۲۰۰ استارز - ۶۶۰ تومن", callback_data="stars_direct_200")],
        [InlineKeyboardButton("⭐ ۵۰۰ استارز - ۱,۶۰۰ تومن", callback_data="stars_direct_500")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "⭐ *خرید استارز مستقیم*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۵۰ استارز = ۱۶۵ تومن\n"
        "• ۱۰۰ استارز = ۳۳۹ تومن\n"
        "• ۱۵۰ استارز = ۵۰۰ تومن\n"
        "• ۲۰۰ استارز = ۶۶۰ تومن\n"
        "• ۵۰۰ استارز = ۱,۶۰۰ تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید استارز رو پست ==========
async def buy_stars_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 ۱ استارز - ۴,۰۰۰ تومن", callback_data="stars_post_1")],
        [InlineKeyboardButton("📝 ۵ استارز - ۲۰,۰۰۰ تومن", callback_data="stars_post_5")],
        [InlineKeyboardButton("📝 ۱۰ استارز - ۴۰,۰۰۰ تومن", callback_data="stars_post_10")],
        [InlineKeyboardButton("📝 ۲۵ استارز - ۱۰۰,۰۰۰ تومن", callback_data="stars_post_25")],
        [InlineKeyboardButton("📝 ۵۰ استارز - ۲۰۰,۰۰۰ تومن", callback_data="stars_post_50")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "📝 *خرید استارز رو پست*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۱ استارز = ۴,۰۰۰ تومن\n"
        "• ۵ استارز = ۲۰,۰۰۰ تومن\n"
        "• ۱۰ استارز = ۴۰,۰۰۰ تومن\n"
        "• ۲۵ استارز = ۱۰۰,۰۰۰ تومن\n"
        "• ۵۰ استارز = ۲۰۰,۰۰۰ تومن\n\n"
        "⚠️ استارز رو پست برای تنظیمات پست‌ها استفاده میشه.\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید گیفت استارزی ==========
async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🎁 ۱۵ استارز - ۵۵ تومن", callback_data="gift_15")],
        [InlineKeyboardButton("🎁 ۲۵ استارز - ۸۵ تومن", callback_data="gift_25")],
        [InlineKeyboardButton("🎁 ۵۰ استارز - ۱۷۰ تومن", callback_data="gift_50")],
        [InlineKeyboardButton("🎁 ۱۰۰ استارز - ۳۳۹ تومن", callback_data="gift_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "🎁 *خرید گیفت استارزی*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۱۵ استارز = ۵۵ تومن\n"
        "• ۲۵ استارز = ۸۵ تومن\n"
        "• ۵۰ استارز = ۱۷۰ تومن\n"
        "• ۱۰۰ استارز = ۳۳۹ تومن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== پردازش خرید ==========
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    # تشخیص نوع خرید
    parts = data.split('_')
    item_type = parts[0]
    quantity = int(parts[1])
    
    # قیمت‌ها
    if item_type == "ton":
        price = quantity * PRICES["ton"]
        item_name = f"تون ({quantity})"
    elif item_type == "stars_direct":
        price = PRICES["stars_direct"][str(quantity)]
        item_name = f"استارز مستقیم ({quantity})"
    elif item_type == "stars_post":
        price = PRICES["stars_post"][str(quantity)]
        item_name = f"استارز رو پست ({quantity})"
    elif item_type == "gift":
        price = PRICES["gift"][str(quantity)]
        item_name = f"گیفت استارزی ({quantity})"
    else:
        await query.edit_message_text("❌ خطا! لطفا دوباره تلاش کن.")
        return
    
    # ذخیره سفارش
    order_id = create_order(user_id, item_type, quantity, price)
    
    # نمایش اطلاعات پرداخت
    keyboard = [
        [InlineKeyboardButton("✅ پرداخت انجام شد", callback_data=f"payment_done_{order_id}")],
        [InlineKeyboardButton("❌ لغو سفارش", callback_data=f"cancel_order_{order_id}")],
    ]
    
    user = get_user(user_id)
    username = user[1] if user else "کاربر"
    
    await query.edit_message_text(
        f"📋 *تایید سفارش*\n\n"
        f"🛒 محصول: {item_name}\n"
        f"💰 مبلغ: {fmt(price)} تومن\n"
        f"🆔 شماره سفارش: {order_id}\n\n"
        f"💳 لطفاً مبلغ {fmt(price)} تومن رو به شماره کارت زیر واریز کن:\n"
        f"6037-9970-1234-5678 (بانک ملی)\n\n"
        f"بعد از واریز، دکمه 'پرداخت انجام شد' رو بزن.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    # ارسال به ادمین
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 *سفارش جدید*\n\n"
                f"👤 کاربر: {username}\n"
                f"🆔 آیدی: {user_id}\n"
                f"🛒 محصول: {item_name}\n"
                f"💰 مبلغ: {fmt(price)} تومن\n"
                f"🆔 شماره سفارش: {order_id}\n"
                f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                parse_mode="Markdown"
            )
        except:
            pass
# ========== پرداخت انجام شد ==========
async def payment_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    order_id = int(query.data.split('_')[2])
    
    # به‌روزرسانی وضعیت سفارش
    cursor.execute('UPDATE orders SET status = "paid" WHERE id = ?', (order_id,))
    conn.commit()
    
    # دریافت اطلاعات سفارش
    cursor.execute('SELECT item_type, quantity, price FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if order:
        item_type, quantity, price = order
        await query.edit_message_text(
            f"✅ *سفارش شما تایید شد!*\n\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"🛒 محصول: {item_type} ({quantity})\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"📦 سفارش شما در حال پردازشه.\n"
            f"به زودی محصول تحویل داده میشه. ⏳"
        )
        
        # ارسال به ادمین
        user = get_user(user_id)
        username = user[1] if user else "کاربر"
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"✅ *پرداخت تایید شد!*\n\n"
                    f"👤 کاربر: {username}\n"
                    f"🆔 آیدی: {user_id}\n"
                    f"🆔 شماره سفارش: {order_id}\n"
                    f"🛒 محصول: {item_type} ({quantity})",
                    parse_mode="Markdown"
                )
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
        f"میتونی دوباره سفارش بدی. 🛒"
    )

# ========== سفارشات من ==========
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    cursor.execute('''
        SELECT id, item_type, quantity, price, status, created_at
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
    for order in orders:
        id, item_type, qty, price, status, created_at = order
        status_emoji = "✅" if status == "paid" else "⏳" if status == "pending" else "❌"
        date = datetime.fromtimestamp(created_at).strftime("%Y/%m/%d %H:%M")
        text += f"🆔 #{id} - {item_type} ({qty}) - {fmt(price)} تومن {status_emoji}\n   📅 {date}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== راهنما ==========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "📖 *راهنمای فروشگاه*\n\n"
        "🪙 تون (Toncoin)\n"
        "• قیمت هر تون: ۳۴۰ تومن\n"
        "• حداقل خرید: ۱ تون\n\n"
        "⭐ استارز مستقیم\n"
        "• ۵۰ استارز = ۱۶۵ تومن\n"
        "• ۱۰۰ استارز = ۳۳۹ تومن\n"
        "• ۱۵۰ استارز = ۵۰۰ تومن\n"
        "• ۲۰۰ استارز = ۶۶۰ تومن\n"
        "• ۵۰۰ استارز = ۱,۶۰۰ تومن\n\n"
        "📝 استارز رو پست\n"
        "• ۱ استارز = ۴,۰۰۰ تومن\n"
        "• ۵ استارز = ۲۰,۰۰۰ تومن\n"
        "• ۱۰ استارز = ۴۰,۰۰۰ تومن\n"
        "• ۲۵ استارز = ۱۰۰,۰۰۰ تومن\n"
        "• ۵۰ استارز = ۲۰۰,۰۰۰ تومن\n\n"
        "🎁 گیفت استارزی\n"
        "• ۱۵ استارز = ۵۵ تومن\n"
        "• ۲۵ استارز = ۸۵ تومن\n"
        "• ۵۰ استارز = ۱۷۰ تومن\n"
        "• ۱۰۰ استارز = ۳۳۹ تومن\n\n"
        "📌 نحوه خرید:\n"
        "۱. محصول رو انتخاب کن\n"
        "۲. مبلغ رو به شماره کارت واریز کن\n"
        "۳. دکمه 'پرداخت انجام شد' رو بزن\n"
        "۴. منتظر تایید ادمین باش\n\n"
        "👥 پشتیبانی:\n"
        "برای ارتباط با پشتیبانی، با ادمین تماس بگیر."
    )
    
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
        [InlineKeyboardButton("🪙 خرید تون (Toncoin)", callback_data="buy_ton")],
        [InlineKeyboardButton("⭐ خرید استارز مستقیم", callback_data="buy_stars_direct")],
        [InlineKeyboardButton("📝 خرید استارز رو پست", callback_data="buy_stars_post")],
        [InlineKeyboardButton("🎁 خرید گیفت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("📊 وضعیت سفارشات", callback_data="my_orders")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]
    
    await query.edit_message_text(
        "🛒 *منوی اصلی*\n\n"
        "💰 قیمت تون: ۳۴۰ تومن\n"
        "⭐ استارز مستقیم: از ۱۶۵ تومن\n"
        "📝 استارز رو پست: ۴۰۰۰ تومن هر عدد\n"
        "🎁 گیفت استارزی: از ۵۵ تومن\n\n"
        "یکی از گزینه‌ها رو انتخاب کن 👇",
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
    elif data.startswith("cancel_order_"):
        await cancel_order(update, context)
    elif data == "my_orders":
        await my_orders(update, context)
    elif data == "help":
        await help_command(update, context)

# ========== اجرا ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))
    
    print("🛒 ربات فروش استارز و تون روشن شد...")
    app.run_polling()

if name == "main":
    main()
