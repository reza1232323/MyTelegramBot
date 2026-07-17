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
WAITING_FOR_WALLET, WAITING_FOR_RECEIVER, WAITING_FOR_POST_LINK, WAITING_FOR_RECEIPT_PHOTO, WAITING_FOR_CUSTOM_AMOUNT = range(5)

# ========== قیمت‌ها ==========
PRICES = {
    "ton": 340,
    "stars_direct": {"50": 165000, "100": 339000, "150": 500000, "200": 660000, "500": 1600000},
    "stars_post": {"1": 4000, "5": 20000, "10": 40000, "25": 100000, "50": 200000},
    "gift": {"15": 55000, "25": 85000, "50": 170000, "100": 339000},
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
        receipt_file_id TEXT DEFAULT '',
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

def update_order_receipt(order_id, file_id):
    cursor.execute('UPDATE orders SET receipt_file_id = ?, status = "waiting_confirm" WHERE id = ?', (file_id, order_id))
    conn.commit()

def confirm_order(order_id):
    cursor.execute('UPDATE orders SET status = "confirmed" WHERE id = ?', (order_id,))
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
        "⭐ *استارز مستقیم:* از 165,000 تومن\n"
        "📝 *استارز رو پست:* 4,000 تومن هر عدد\n"
        "🎁 *گیفت استارزی:* از 55,000 تومن\n\n"
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

# ========== خرید تون با مقدار دلخواه ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🪙 *خرید تون (Toncoin)*\n\n"
        "💰 هر تون = 340 تومن\n\n"
        "🔢 لطفاً تعداد تون مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 5 یا ۵",
        parse_mode="Markdown"
    )
    return WAITING_FOR_CUSTOM_AMOUNT

# ========== خرید استارز مستقیم با مقدار دلخواه ==========
async def buy_stars_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⭐ *استارز مستقیم*\n\n"
        "💰 هر استارز = 3,300 تومن\n\n"
        "🔢 لطفاً تعداد استارز مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 50 یا ۵۰",
        parse_mode="Markdown"
    )
    return WAITING_FOR_CUSTOM_AMOUNT

# ========== خرید استارز رو پست ==========
async def buy_stars_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *استارز رو پست*\n\n"
        "💰 هر استارز رو پست = 4,000 تومن\n\n"
        "🔢 لطفاً تعداد استارز رو پست مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 1 یا ۱",
        parse_mode="Markdown"
    )
    return WAITING_FOR_CUSTOM_AMOUNT

# ========== خرید گیفت استارزی ==========
async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎁 *گیفت استارزی*\n\n"
        "💰 هر گیفت استارز = 3,390 تومن\n\n"
        "🔢 لطفاً تعداد گیفت استارز مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 15 یا ۱۵",
        parse_mode="Markdown"
    )
    return WAITING_FOR_CUSTOM_AMOUNT

# ========== دریافت مقدار دلخواه ==========
async def get_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.strip()
    
    # تبدیل اعداد فارسی به انگلیسی
    persian_to_english = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    for persian, english in persian_to_english.items():
        text = text.replace(persian, english)
    
    try:
        qty = int(text)
        if qty <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد بزرگتر از 0 وارد کن!")
            return
    except ValueError:
        await update.message.reply_text("❌ لطفاً فقط عدد وارد کن!")
        return
    
    # تشخیص نوع محصول از context
    data = context.user_data.get('last_callback', 'ton')
    item_type = data.split('_')[0]
    
    # محاسبه قیمت
    if item_type == "ton":
        price = qty * PRICES["ton"]
        item_name = f"تون ({qty})"
        extra_prompt = "🪙 لطفاً آدرس ولت (Wallet) خود را برای دریافت تون وارد کن:"
        next_state = WAITING_FOR_WALLET
    elif item_type == "stars_direct":
        price = qty * 3300
        item_name = f"استارز مستقیم ({qty})"
        extra_prompt = "⭐ لطفاً آیدی تلگرام (یوزرنیم) فردی که استارز رو دریافت میکنه رو وارد کن:"
        next_state = WAITING_FOR_RECEIVER
    elif item_type == "stars_post":
        price = qty * 4000
        item_name = f"استارز رو پست ({qty})"
        extra_prompt = "📝 لطفاً لینک پست مورد نظر رو بفرست:"
        next_state = WAITING_FOR_POST_LINK
    elif item_type == "gift":
        price = qty * 3390
        item_name = f"گیفت استارزی ({qty})"
        order_id = create_order(user_id, username, item_type, qty, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        await update.message.reply_text(
            f"📋 *تایید سفارش*\n\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_name}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"🆔 شماره سفارش: {order_id}\n\n"
            f"💳 *شماره کارت:*\n"
            f"`6037-9970-1234-5678`\n"
            f"🏦 بانک ملی\n\n"
            f"⚠️ بعد از واریز، عکس رسید رو بفرست.",
            parse_mode="Markdown"
        )
        return WAITING_FOR_RECEIPT_PHOTO

    # ذخیره سفارش
    order_id = create_order(user_id, username, item_type, qty, price)
    context.user_data['order_id'] = order_id
    context.user_data['item_name'] = item_name
    context.user_data['price'] = price
    context.user_data['next_state'] = next_state

    # درخواست اطلاعات اضافی
    await update.message.reply_text(
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
    
    order_id = context.user_data.get('order_id')
    item_name = context.user_data.get('item_name')
    price = context.user_data.get('price')
    
    if not order_id:
        await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
        return ConversationHandler.END
    
    # ذخیره اطلاعات اضافی
    update_order_extra(order_id, text)
    
    await update.message.reply_text(
        f"📋 *تایید سفارش*\n\n"
        f"👤 کاربر: @{update.effective_user.username or update.effective_user.first_name}\n"
        f"🛒 محصول: {item_name}\n"
        f"💰 مبلغ: {fmt(price)} تومن\n"
        f"🆔 شماره سفارش: {order_id}\n"
        f"📝 اطلاعات: `{text}`\n\n"
        f"💳 *شماره کارت:*\n"
        f"`6037-9970-1234-5678`\n"
        f"🏦 بانک ملی\n\n"
        f"⚠️ بعد از واریز، عکس رسید رو بفرست.",
        parse_mode="Markdown"
    )
    
    # اطلاع به ادمین
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 *سفارش جدید*\n\n"
                f"👤 کاربر: @{update.effective_user.username or update.effective_user.first_name}\n"
                f"🆔 آیدی: {user_id}\n"
                f"🛒 محصول: {item_name}\n"
                f"💰 مبلغ: {fmt(price)} تومن\n"
                f"🆔 شماره سفارش: {order_id}\n"
                f"📝 اطلاعات: {text}",
                parse_mode="Markdown"
            )
        except:
            pass
    
    return WAITING_FOR_RECEIPT_PHOTO

# ========== دریافت عکس رسید ==========
async def get_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    order_id = context.user_data.get('order_id')
    item_name = context.user_data.get('item_name')
    price = context.user_data.get('price')
    
    if not order_id:
        await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
        return ConversationHandler.END
    
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        file_id = update.message.photo[-1].file_id
        
        update_order_receipt(order_id, file_id)
        
        await update.message.reply_text(
            f"✅ *عکس رسید شما دریافت شد!*\n\n"
            f"🌟 *خدمات استارز لند آنی هست!*\n"
            f"⚡️ سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
            f"🆔 شماره سفارش: {order_id}\n\n"
            f"⏳ لطفاً چند دقیقه صبر کنید...\n"
            f"🔜 به زودی تحویل داده میشه!\n\n"
            f"🙏 از اعتماد شما سپاسگزاریم! 🌟",
            parse_mode="Markdown"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=f"📸 *رسید جدید برای تایید*\n\n"
                            f"👤 کاربر: @{update.effective_user.username or update.effective_user.first_name}\n"
                            f"🆔 آیدی: {user_id}\n"
                            f"🛒 محصول: {item_name}\n"
                            f"💰 مبلغ: {fmt(price)} تومن\n"
                            f"🆔 شماره سفارش: {order_id}\n\n"
                            f"⬅️ برای تایید، روی دکمه زیر کلیک کن:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ تایید واریز", callback_data=f"confirm_order_{order_id}")],
                        [InlineKeyboardButton("❌ رد واریز", callback_data=f"reject_order_{order_id}")]
                    ]),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending receipt to admin: {e}")
        
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ لطفاً یک عکس از رسید واریز خود بفرستید.\n"
            "⚠️ فقط عکس (تصویر) مورد قبول است."
        )
        return WAITING_FOR_RECEIPT_PHOTO

# ========== تایید سفارش توسط ادمین ==========
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی به این بخش ندارید!")
        return
    
    order_id = int(query.data.split('_')[2])
    confirm_order(order_id)
    
    cursor.execute('SELECT user_id, username, item_type, quantity, price, extra_info FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        await query.edit_message_text("❌ سفارش پیدا نشد!")
        return
    
    user_id, username, item_type, qty, price, extra_info = order
    
    try:
        extra_text = f"\n📝 اطلاعات: {extra_info}" if extra_info else ""
        await context.bot.send_message(
            user_id,
            f"✅ *سفارش شما تایید شد!*\n\n"
            f"🌟 *خدمات استارز لند آنی هست!*\n"
            f"⚡️ سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"🛒 محصول: {item_type} ({qty})\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"{extra_text}\n\n"
            f"⏳ لطفاً چند دقیقه صبر کنید...\n"
            f"🔜 به زودی تحویل داده میشه!\n\n"
            f"🙏 از اعتماد شما سپاسگزاریم! 🌟",
            parse_mode="Markdown"
        )
    except:
        pass
    
    await query.edit_message_text(
        f"✅ *سفارش {order_id} تایید شد!*\n\n"
        f"👤 کاربر: @{username}\n"
        f"🛒 محصول: {item_type} ({qty})\n"
        f"💰 مبلغ: {fmt(price)} تومن\n"
        f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )

# ========== رد سفارش توسط ادمین ==========
async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی به این بخش ندارید!")
        return
    
    order_id = int(query.data.split('_')[2])
    
    cursor.execute('SELECT user_id, username, item_type, quantity, price FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if not order:
        await query.edit_message_text("❌ سفارش پیدا نشد!")
        return
    
    user_id, username, item_type, qty, price = order
    
    try:
        await context.bot.send_message(
            user_id,
            f"❌ *سفارش شما رد شد!*\n\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"🛒 محصول: {item_type} ({qty})\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"⚠️ رسید ارسالی مورد تایید قرار نگرفت.\n"
            f"📸 لطفاً دوباره عکس رسید رو بفرستید.\n\n"
            f"🙏 از صبر شما سپاسگزاریم.",
            parse_mode="Markdown"
        )
    except:
        pass
    
    await query.edit_message_text(
        f"❌ *سفارش {order_id} رد شد!*\n\n"
        f"👤 کاربر: @{username}\n"
        f"🛒 محصول: {item_type} ({qty})\n"
        f"💰 مبلغ: {fmt(price)} تومن"
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
        if status == "confirmed":
            status_emoji = "✅"
        elif status == "waiting_confirm":
            status_emoji = "⏳"
        elif status == "pending":
            status_emoji = "🆕"
        else:
            status_emoji = "❌"
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
        "⭐ استارز مستقیم: از 165,000 تومن\n"
        "📝 استارز رو پست: 4,000 تومن هر عدد\n"
        "🎁 گیفت استارزی: از 55,000 تومن\n\n"
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
        context.user_data['last_callback'] = "ton"
        await buy_ton(update, context)
    elif data == "buy_stars_direct":
        context.user_data['last_callback'] = "stars_direct"
        await buy_stars_direct(update, context)
    elif data == "buy_stars_post":
        context.user_data['last_callback'] = "stars_post"
        await buy_stars_post(update, context)
    elif data == "buy_gift":
        context.user_data['last_callback'] = "gift"
        await buy_gift(update, context)
    elif data.startswith("confirm_order_"):
        await confirm_order(update, context)
    elif data.startswith("reject_order_"):
        await reject_order(update, context)
    elif data == "my_orders":
        await my_orders(update, context)

# ========== اجرا ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handler)
        ],
        states={
            WAITING_FOR_CUSTOM_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_custom_amount)
            ],
            WAITING_FOR_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_info)
            ],
            WAITING_FOR_RECEIVER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_info)
            ],
            WAITING_FOR_POST_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_info)
            ],
            WAITING_FOR_RECEIPT_PHOTO: [
                MessageHandler(filters.PHOTO, get_receipt_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_receipt_photo)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    print("🌟 ربات فروش استارز لند روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
