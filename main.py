
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========== تنظیمات ==========
TOKEN = "8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI"
CHANNEL_ID = -1004296146485  # ← آیدی عددی درست
CHANNEL_USERNAME = "@starzland_shop"
ADMIN_IDS = [5571951071, 6691993264]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        item_type TEXT,
        quantity INTEGER,
        price INTEGER,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0
    )
''')
conn.commit()

def fmt(n):
    return f"{n:,}"

# ========== تابع چک عضویت (اصلاح شده) ==========
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

def create_order(user_id, item_type, quantity, price):
    cursor.execute('''
        INSERT INTO orders (user_id, item_type, quantity, price, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, item_type, quantity, price, int(datetime.now().timestamp())))
    conn.commit()
    return cursor.lastrowid

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
            "🔒 برای استفاده از ربات، ابتدا در کانال عضو شوید:\n" + CHANNEL_USERNAME,
            reply_markup=InlineKeyboardMarkup(keyboard)
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
        "🛒 به فروشگاه استارز و تون خوش آمدی!\n"
        "💰 تون: 340 تومن\n"
        "⭐ استارز مستقیم: از 165 تومن\n"
        "📝 استارز رو پست: 4000 تومن هر عدد\n"
        "🎁 گیفت استارزی: از 55 تومن\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        [InlineKeyboardButton("💰 ۱ تون - 340 تومن", callback_data="ton_1")],
        [InlineKeyboardButton("💰 ۵ تون - 1,700 تومن", callback_data="ton_5")],
        [InlineKeyboardButton("💰 ۱۰ تون - 3,400 تومن", callback_data="ton_10")],
        [InlineKeyboardButton("💰 ۵۰ تون - 17,000 تومن", callback_data="ton_50")],
        [InlineKeyboardButton("💰 ۱۰۰ تون - 34,000 تومن", callback_data="ton_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text("🪙 خرید تون:\nهر تون = 340 تومن", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== خرید استارز مستقیم ==========
async def buy_stars_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⭐ ۵۰ - 165 تومن", callback_data="stars_direct_50")],
        [InlineKeyboardButton("⭐ ۱۰۰ - 339 تومن", callback_data="stars_direct_100")],
        [InlineKeyboardButton("⭐ ۱۵۰ - 500 تومن", callback_data="stars_direct_150")],
        [InlineKeyboardButton("⭐ ۲۰۰ - 660 تومن", callback_data="stars_direct_200")],
        [InlineKeyboardButton("⭐ ۵۰۰ - 1,600 تومن", callback_data="stars_direct_500")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text("⭐ استارز مستقیم:", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== خرید استارز رو پست ==========
async def buy_stars_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📝 ۱ - 4,000 تومن", callback_data="stars_post_1")],
        [InlineKeyboardButton("📝 ۵ - 20,000 تومن", callback_data="stars_post_5")],
        [InlineKeyboardButton("📝 ۱۰ - 40,000 تومن", callback_data="stars_post_10")],
        [InlineKeyboardButton("📝 ۲۵ - 100,000 تومن", callback_data="stars_post_25")],
        [InlineKeyboardButton("📝 ۵۰ - 200,000 تومن", callback_data="stars_post_50")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text("📝 استارز رو پست:", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== خرید گیفت استارزی ==========
async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎁 ۱۵ - 55 تومن", callback_data="gift_15")],
        [InlineKeyboardButton("🎁 ۲۵ - 85 تومن", callback_data="gift_25")],
        [InlineKeyboardButton("🎁 ۵۰ - 170 تومن", callback_data="gift_50")],
        [InlineKeyboardButton("🎁 ۱۰۰ - 339 تومن", callback_data="gift_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    await query.edit_message_text("🎁 گیفت استارزی:", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== پردازش خرید ==========
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data.split('_')
    item_type = data[0]
    qty = int(data[1])

    if item_type == "ton":
        price = qty * PRICES["ton"]

        item_name = f"تون ({qty})"
    elif item_type == "stars_direct":
        price = PRICES["stars_direct"][str(qty)]
        item_name = f"استارز مستقیم ({qty})"
    elif item_type == "stars_post":
        price = PRICES["stars_post"][str(qty)]
        item_name = f"استارز رو پست ({qty})"
    elif item_type == "gift":
        price = PRICES["gift"][str(qty)]
        item_name = f"گیفت استارزی ({qty})"
    else:
        await query.edit_message_text("❌ خطا!")
        return

    order_id = create_order(user_id, item_type, qty, price)

    keyboard = [
        [InlineKeyboardButton("✅ پرداخت انجام شد", callback_data=f"payment_done_{order_id}")],
        [InlineKeyboardButton("❌ لغو سفارش", callback_data=f"cancel_{order_id}")],
    ]

    await query.edit_message_text(
        f"📋 تایید سفارش:\n\n"
        f"🛒 محصول: {item_name}\n"
        f"💰 مبلغ: {fmt(price)} تومن\n"
        f"🆔 شماره سفارش: {order_id}\n\n"
        f"💳 شماره کارت: 6037-9970-1234-5678\n"
        f"بعد از واریز، دکمه 'پرداخت انجام شد' رو بزن.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 سفارش جدید #{order_id}\n"
                f"👤 کاربر: {user_id}\n"
                f"🛒 محصول: {item_name}\n"
                f"💰 مبلغ: {fmt(price)} تومن"
            )
        except:
            pass

# ========== پرداخت انجام شد ==========
async def payment_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split('_')[2])
    cursor.execute('UPDATE orders SET status = "paid" WHERE id = ?', (order_id,))
    conn.commit()
    await query.edit_message_text(f"✅ سفارش #{order_id} تایید شد! به زودی تحویل داده میشه.")

# ========== لغو سفارش ==========
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split('_')[2])
    cursor.execute('UPDATE orders SET status = "canceled" WHERE id = ?', (order_id,))
    conn.commit()
    await query.edit_message_text(f"❌ سفارش #{order_id} لغو شد.")

# ========== سفارشات من ==========
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cursor.execute('SELECT id, item_type, quantity, price, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (user_id,))
    orders = cursor.fetchall()
    if not orders:
        await query.edit_message_text("📋 هیچ سفارشی نداری.")
        return
    text = "📋 سفارشات شما:\n\n"
    for o in orders:
        status_emoji = "✅" if o[4] == "paid" else "⏳" if o[4] == "pending" else "❌"
        text += f"#{o[0]} - {o[1]} ({o[2]}) - {fmt(o[3])} تومن {status_emoji}\n"
    await query.edit_message_text(text)

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
    await query.edit_message_text("🛒 منوی اصلی:", reply_markup=InlineKeyboardMarkup(keyboard))


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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handler))
    print("🛒 ربات فروش استارز و تون روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
