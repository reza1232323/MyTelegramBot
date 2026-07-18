import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ========== تنظیمات ==========
TOKEN = "8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI"
CHANNEL_ID = -1004296146485
CHANNEL_USERNAME = "@starzland_shop"
ADMIN_IDS = [5571951071, 6691993264]
BOT_USERNAME = "starzland_bot"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== قیمت‌ها (با سه صفر اضافه) ==========
PRICES = {
    "ton": 340000,  # هر تون 340,000 تومان
    "stars_direct_50": 165000,  # 50 استارز مستقیم = 165,000 تومان
    "stars_direct_100": 330000,  # 100 استارز مستقیم = 330,000 تومان
    "stars_direct_200": 660000,  # 200 استارز مستقیم = 660,000 تومان
    "stars_direct_500": 1650000,  # 500 استارز مستقیم = 1,650,000 تومان
    "stars_post": 4000,  # هر استارز رو پست = 4,000 تومان
    "gift_15": 55000,  # 15 استارز = 55,000 تومان
    "gift_25": 85000,  # 25 استارز = 85,000 تومان
    "gift_50": 170000,  # 50 استارز = 170,000 تومان
    "gift_100": 339000,  # 100 استارز = 339,000 تومان
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
        quantity REAL,
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
    except:
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
        [InlineKeyboardButton("⭐ استارز", callback_data="buy_stars")],
        [InlineKeyboardButton("🎁 گیفت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
    ]

    await update.message.reply_text(
        "🌟 *به فروشگاه استارز لند خوش آمدی!* 🌟\n\n"
        "🪙 *تون:* 340,000 تومن\n"
        "⭐ *استارز:* از 165,000 تومن\n"
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

# ========== خرید تون ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'ton'
    await query.edit_message_text(
        "🪙 *خرید تون (Toncoin)*\n\n"
        "💰 هر تون = 340,000 تومن\n\n"
        "🔢 لطفاً تعداد تون مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 5 یا ۵",
        parse_mode="Markdown"
    )

# ========== خرید استارز ==========
async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⭐ استارز مستقیم", callback_data="buy_stars_direct")],
        [InlineKeyboardButton("📝 استارز رو پست", callback_data="buy_stars_post")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "⭐ *خرید استارز*\n\n"
        "🌟 لطفاً نوع استارز مورد نظر خود را انتخاب کن:\n\n"
        "• ⭐ استارز مستقیم: برای ارسال به کاربران\n"
        "• 📝 استارز رو پست: برای استارز دادن به پست‌ها\n\n"
        "👇 یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید استارز مستقیم ==========
async def buy_stars_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'stars_direct'
    await query.edit_message_text(
        "⭐ *استارز مستقیم*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۵۰ استارز = 165,000 تومن\n"
        "• ۱۰۰ استارز = 330,000 تومن\n"
        "• ۲۰۰ استارز = 660,000 تومن\n"
        "• ۵۰۰ استارز = 1,650,000 تومن\n\n"
        "🔢 لطفاً تعداد استارز مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 50 یا ۵۰",
        parse_mode="Markdown"
    )

# ========== خرید استارز رو پست ==========
async def buy_stars_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'stars_post'
    await query.edit_message_text(
        "📝 *استارز رو پست*\n\n"
        "💰 هر استارز رو پست = 4,000 تومن\n\n"
        "🔢 لطفاً تعداد استارز رو پست مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 1 یا ۱",
        parse_mode="Markdown"
    )

# ========== خرید گیفت استارزی ==========
async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'gift'
    await query.edit_message_text(
        "🎁 *گیفت استارزی*\n\n"
        "💰 قیمت‌ها:\n"
        "• ۱۵ استارز = 55,000 تومن\n"
        "• ۲۵ استارز = 85,000 تومن\n"
        "• ۵۰ استارز = 170,000 تومن\n"
        "• ۱۰۰ استارز = 339,000 تومن\n\n"
        "🔢 لطفاً تعداد گیفت استارز مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 15 یا ۱۵",
        parse_mode="Markdown"
    )

# ========== دریافت مقدار ==========
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        qty = float(text)
        if qty <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد بزرگتر از 0 وارد کن!")
            return
    except ValueError:
        await update.message.reply_text("❌ لطفاً فقط عدد وارد کن!")
        return
    
    item_type = context.user_data.get('product_type', 'ton')
    
    # محاسبه قیمت بر اساس نوع محصول
    if item_type == "ton":
        price = int(qty * PRICES["ton"])
        item_name = f"تون ({qty})"
        extra_prompt = "🪙 لطفاً آدرس ولت (Wallet) خود را برای دریافت تون وارد کن:"
        next_step = "wallet"
    elif item_type == "stars_direct":
        if qty <= 50:
            price = PRICES["stars_direct_50"]
            qty = 50
        elif qty <= 100:
            price = PRICES["stars_direct_100"]
            qty = 100
        elif qty <= 200:
            price = PRICES["stars_direct_200"]
            qty = 200
        elif qty <= 500:
            price = PRICES["stars_direct_500"]
            qty = 500
        else:
            price = int(qty * 3300)
        item_name = f"استارز مستقیم ({qty}★)"
        extra_prompt = "⭐ لطفاً آیدی تلگرام (یوزرنیم) فردی که استارز رو دریافت میکنه رو وارد کن:"
        next_step = "receiver"
    elif item_type == "stars_post":
        price = int(qty * PRICES["stars_post"])
        item_name = f"استارز رو پست ({qty})"
        extra_prompt = "📝 لطفاً لینک پست مورد نظر رو بفرست:"
        next_step = "post_link"
    elif item_type == "gift":
        if qty <= 15:
            price = PRICES["gift_15"]
            qty = 15
        elif qty <= 25:
            price = PRICES["gift_25"]
            qty = 25
        elif qty <= 50:
            price = PRICES["gift_50"]
            qty = 50
        elif qty <= 100:
            price = PRICES["gift_100"]
            qty = 100
        else:
            price = int(qty * 3390)
        item_name = f"گیفت استارزی ({qty}★)"
        extra_prompt = "🎁 لطفاً آیدی تلگرام (یوزرنیم) فردی که گیفت رو دریافت میکنه رو وارد کن:"
        next_step = "receiver"
    else:
        await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
        return

    order_id = create_order(user_id, username, item_type, qty, price)
    context.user_data['order_id'] = order_id
    context.user_data['item_name'] = item_name
    context.user_data['price'] = price

    await update.message.reply_text(
        f"📋 *{item_name}*\n\n"
        f"💰 مبلغ: {fmt(price)} تومن\n\n"
        f"{extra_prompt}\n\n"
        f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
        parse_mode="Markdown"
    )
    context.user_data['waiting_for'] = next_step

# ========== دریافت اطلاعات اضافی ==========
async def get_extra_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    order_id = context.user_data.get('order_id')
    item_name = context.user_data.get('item_name')
    price = context.user_data.get('price')
    waiting_for = context.user_data.get('waiting_for')
    
    if not order_id:
        await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
        return
    
    if waiting_for == "wallet":
        update_order_extra(order_id, f"آدرس ولت: {text}")
    elif waiting_for == "receiver":
        update_order_extra(order_id, f"گیرنده: {text}")
    elif waiting_for == "post_link":
        update_order_extra(order_id, f"لینک پست: {text}")
    else:
        await update.message.reply_text("❌ خطا! لطفا دوباره تلاش کن.")
        return
    
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
    
    context.user_data['waiting_for'] = 'receipt'

# ========== دریافت عکس رسید ==========
async def get_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    order_id = context.user_data.get('order_id')
    item_name = context.user_data.get('item_name')
    price = context.user_data.get('price')
    
    if not order_id:
        await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
        return
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        update_order_receipt(order_id, file_id)
        
        await update.message.reply_text(
            f"✅ *عکس رسید شما دریافت شد!*\n\n"
            f"🌟 *خدمات استارز لند آنی هست!*\n"
            f"⚡️ سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_name}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"⏳ لطفاً چند دقیقه صبر کنید...\n"
            f"🔜 به زودی تحویل داده میشه!\n\n"
            f"🙏 از اعتماد شما سپاسگزاریم! 🌟",
            parse_mode="Markdown"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                cursor.execute('SELECT extra_info FROM orders WHERE id = ?', (order_id,))
                extra = cursor.fetchone()
                extra_info = extra[0] if extra else ""
                
                await context.bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=f"📸 *رسید جدید برای تایید*\n\n"
                            f"👤 کاربر: @{username}\n"
                            f"🆔 آیدی: {user_id}\n"
                            f"🛒 محصول: {item_name}\n"
                            f"💰 مبلغ: {fmt(price)} تومن\n"
                            f"🆔 شماره سفارش: {order_id}\n"
                            f"📝 اطلاعات: {extra_info if extra_info else 'ندارد'}\n"
                            f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
                            f"⬅️ برای تایید، روی دکمه زیر کلیک کن:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ تایید واریز", callback_data=f"confirm_{order_id}")],
                        [InlineKeyboardButton("❌ رد واریز", callback_data=f"reject_{order_id}")]
                    ]),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending receipt to admin: {e}")
        
        context.user_data['waiting_for'] = ''
    else:
        await update.message.reply_text(
            "❌ لطفاً یک عکس از رسید واریز خود بفرستید.\n"
            "⚠️ فقط عکس (تصویر) مورد قبول است."
        )

# ========== تایید توسط ادمین ==========
async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی به این بخش ندارید!")
        return
    
    order_id = int(query.data.split('_')[1])
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

# ========== رد توسط ادمین ==========
async def reject_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی به این بخش ندارید!")
        return
    
    order_id = int(query.data.split('_')[1])
    
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
        order_id, item_type, qty, price, status, extra_info, created_at = o
        if status == "confirmed":
            status_emoji = "✅"
        elif status == "waiting_confirm":
            status_emoji = "⏳"
        elif status == "pending":
            status_emoji = "🆕"
        else:
            status_emoji = "❌"
        date = datetime.fromtimestamp(created_at).strftime("%Y/%m/%d %H:%M")
        text += f"🆔 #{order_id} - {item_type} ({qty}) - {fmt(price)} تومن {status_emoji}\n"
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
        [InlineKeyboardButton("⭐ استارز", callback_data="buy_stars")],
        [InlineKeyboardButton("🎁 گیفت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
    ]
    
    await query.edit_message_text(
        "🛒 *منوی اصلی*\n\n"
        "💰 تون: 340,000 تومن\n"
        "⭐ استارز: از 165,000 تومن\n"
        "🎁 گیفت استارزی: از 55,000 تومن\n\n"
        "👇 یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== مدیریت پیام‌ها ==========
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for = context.user_data.get('waiting_for', '')
    product_type = context.user_data.get('product_type', '')
    
    if waiting_for in ['wallet', 'receiver', 'post_link']:
        await get_extra_info(update, context)
    elif waiting_for == 'receipt':
        await get_receipt(update, context)
    elif product_type:
        await get_amount(update, context)

# ========== اجرا ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(buy_ton, pattern="^buy_ton$"))
    app.add_handler(CallbackQueryHandler(buy_stars, pattern="^buy_stars$"))
    app.add_handler(CallbackQueryHandler(buy_stars_direct, pattern="^buy_stars_direct$"))
    app.add_handler(CallbackQueryHandler(buy_stars_post, pattern="^buy_stars_post$"))
    app.add_handler(CallbackQueryHandler(buy_gift, pattern="^buy_gift$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(confirm_receipt, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(reject_receipt, pattern="^reject_"))
    app.add_handler(MessageHandler(filters.PHOTO, get_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    print("🌟 ربات استارز لند روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
