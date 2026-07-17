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

# ========== قیمت‌ها (بر اساس عکس‌ها) ==========
PRICES = {
    "gift_15": {"price": 50000, "value": "15★"},
    "gift_25": {"price": 83000, "value": "25★"},
    "gift_50": {"price": 167000, "value": "50★"},
    "gift_100": {"price": 333000, "value": "100★"},
    "ton": 334670,  # هر تون طبق عکس 33,467 تومان
    "premium_month": 0,  # قیمت پرمیوم رو مشخص کن
    "boost": 0,  # قیمت بوست رو مشخص کن
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

# ========== منوی اصلی ==========
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
        [InlineKeyboardButton("🎁 خرید گیت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("🪙 خرید تون (GRAM)", callback_data="buy_ton")],
        [InlineKeyboardButton("💎 خرید تلگرام پرمیوم", callback_data="buy_premium")],
        [InlineKeyboardButton("🚀 خرید بوست", callback_data="buy_boost")],
        [InlineKeyboardButton("👥 زیرمجموعه‌ها", callback_data="referrals")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]

    await update.message.reply_text(
        "🌟 *به فروشگاه ایران گیت خوش آمدی!* 🌟\n\n"
        "🎁 *گیت استارزی:* از 50,000 تومن\n"
        "🪙 *تون (GRAM):* قیمت لحظه‌ای\n"
        "💎 *پرمیوم تلگرام:* بهترین قیمت\n"
        "🚀 *بوست:* افزایش رتبه کانال\n\n"
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

# ========== خرید گیت استارزی ==========
async def buy_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🎁 15★ - 50,000 تومن", callback_data="gift_15")],
        [InlineKeyboardButton("🎁 25★ - 83,000 تومن", callback_data="gift_25")],
        [InlineKeyboardButton("🎁 50★ - 167,000 تومن", callback_data="gift_50")],
        [InlineKeyboardButton("🎁 100★ - 333,000 تومن", callback_data="gift_100")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "🎁 *خرید گیت استارزی*\n\n"
        "🌟 گیت‌های استارزی با بهترین قیمت:\n\n"
        "• 15★ = 50,000 تومن\n"
        "• 25★ = 83,000 تومن\n"
        "• 50★ = 167,000 تومن\n"
        "• 100★ = 333,000 تومن\n\n"
        "⚠️ امکان شخصی‌سازی با کامنت و حالت ارسال مخفی\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید تون (GRAM) ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'ton'
    await query.edit_message_text(
        "🪙 *خرید تون (GRAM)*\n\n"
        "💰 هر تون = 33,467 تومن (قیمت لحظه‌ای)\n\n"
        "🔢 لطفاً تعداد تون مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 0.1 یا ۵",
        parse_mode="Markdown"
    )

# ========== خرید پرمیوم ==========
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💎 ۱ ماه - بهترین قیمت", callback_data="premium_1")],
        [InlineKeyboardButton("💎 ۳ ماه - تخفیف ویژه", callback_data="premium_3")],
        [InlineKeyboardButton("💎 ۶ ماه - تخفیف ویژه", callback_data="premium_6")],
        [InlineKeyboardButton("💎 ۱۲ ماه - بهترین ارزش", callback_data="premium_12")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "💎 *خرید تلگرام پرمیوم*\n\n"
        "🌟 پرمیوم با بهترین قیمت ایران:\n\n"
        "• ۱ ماه =  XXX تومن\n"
        "• ۳ ماه =  XXX تومن\n"
        "• ۶ ماه =  XXX تومن\n"
        "• ۱۲ ماه = XXX تومن\n\n"
        "⚠️ اعتماد هزاران کاربر به ما\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید بوست ==========
async def buy_boost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🚀 ۱ بوست - XXX تومن", callback_data="boost_1")],
        [InlineKeyboardButton("🚀 ۵ بوست - XXX تومن", callback_data="boost_5")],
        [InlineKeyboardButton("🚀 ۱۰ بوست - XXX تومن", callback_data="boost_10")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "🚀 *خرید بوست تلگرام*\n\n"
        "🌟 افزایش رتبه کانال و گروه:\n\n"
        "• ۱ بوست = XXX تومن\n"
        "• ۵ بوست = XXX تومن\n"
        "• ۱۰ بوست = XXX تومن\n\n"
        "⚠️ تحویل آنی و تضمینی\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== زیرمجموعه‌ها ==========
async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    cursor.execute('SELECT total_referrals, referral_link FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        await query.edit_message_text("❌ خطا! لطفا /start رو بزن.")
        return
    
    link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    await query.edit_message_text(
        f"👥 *زیرمجموعه‌های شما*\n\n"
        f"🔗 لینک دعوت:\n`{link}`\n\n"
        f"👥 تعداد زیرمجموعه‌ها: {user[0] if user else 0}\n"
        f"💰 پاداش هر دعوت: ۵,۰۰۰ تومن\n\n"
        f"هر کس با لینک شما عضو بشه، ۵,۰۰۰ تومن پاداش می‌گیری! 🎉",
        parse_mode="Markdown"
    )

# ========== راهنما ==========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📖 *راهنمای فروشگاه ایران گیت*\n\n"
        "🎁 **گیت استارزی**\n"
        "• 15★ = 50,000 تومن\n"
        "• 25★ = 83,000 تومن\n"
        "• 50★ = 167,000 تومن\n"
        "• 100★ = 333,000 تومن\n\n"
        "🪙 **تون (GRAM)**\n"
        "• قیمت لحظه‌ای از صرافی\n"
        "• امکان خرید 0.1 تا 100 تون\n\n"
        "💎 **پرمیوم تلگرام**\n"
        "• ۱ ماهه با بهترین قیمت\n"
        "• تحویل آنی\n\n"
        "🚀 **بوست تلگرام**\n"
        "• افزایش رتبه کانال\n"
        "• تحویل آنی\n\n"
        "📌 **نحوه خرید:**\n"
        "۱. محصول رو انتخاب کن\n"
        "۲. مبلغ رو به شماره کارت واریز کن\n"
        "۳. عکس رسید رو بفرست\n"
        "۴. منتظر تایید ادمین باش\n\n"
        "⏰ *زمان خدمات:* ۱۰ صبح تا ۱ شب\n"
        "🙏 *مورد اعتماد هزاران کاربر*",
        parse_mode="Markdown"
    )

# ========== پردازش خرید ==========
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    data = query.data
    
    # گیت استارزی
    if data in ["gift_15", "gift_25", "gift_50", "gift_100"]:
        price = PRICES[data]["price"]
        value = PRICES[data]["value"]
        item_name = f"گیت استارزی ({value})"
        extra_prompt = f"🎁 لطفاً آیدی (یوزرنیم) گیرنده گیت {value} رو وارد کن:"
        next_step = "receiver"
        
        order_id = create_order(user_id, username, data, 1, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        
        await query.edit_message_text(
            f"📋 *{item_name}*\n\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"{extra_prompt}\n\n"
            f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
            parse_mode="Markdown"
        )
        context.user_data['waiting_for'] = next_step
        return
    
    # پرمیوم
    elif data.startswith("premium_"):
        months = data.split('_')[1]
        # قیمت رو مشخص کن
        price = 0  # قیمت پرمیوم رو اینجا بذار
        item_name = f"پرمیوم ({months} ماه)"
        
        order_id = create_order(user_id, username, data, months, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        
        await show_payment(update, context, order_id, item_name, price)
        return
    
    # بوست
    elif data.startswith("boost_"):
        count = data.split('_')[1]
        # قیمت رو مشخص کن
        price = 0  # قیمت بوست رو اینجا بذار
        item_name = f"بوست ({count})"
        
        order_id = create_order(user_id, username, data, count, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        
        await show_payment(update, context, order_id, item_name, price)
        return

# ========== نمایش اطلاعات پرداخت ==========
async def show_payment(update, context, order_id, item_name, price):
    username = update.effective_user.username or update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("📋 کپی شماره کارت", callback_data="copy_card")],
        [InlineKeyboardButton("✅ نهایی کردن خرید | ارسال رسید", callback_data=f"send_receipt_{order_id}")],
        [InlineKeyboardButton("🔙 بازگشت به صفحه اصلی", callback_data="back_to_menu")],
    ]
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            f"📋 *فاکتور شما آماده است*\n\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_name}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"🆔 شماره سفارش: {order_id}\n\n"
            f"💳 *اطلاعات پرداخت:*\n"
            f"`6219-8618-8369-7301`\n"
            f"🏦 مانی جعفریور - بلوپانک\n\n"
            f"⚠️ اگر با محدودیت تراکنش مواجه شدید، از همراه بانک استفاده کنید.\n\n"
            f"✅ این قیمت از صرافی نمایش داده شده است و کارمزد شبکه اعمال شده.\n"
            f"✅ تهیه این محصول نیازمند احراز هویت میباشد.\n\n"
            f"🔹 از پنل زیر سفارش و خرید خود را نهایی کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"📋 *فاکتور شما آماده است*\n\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_name}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"🆔 شماره سفارش: {order_id}\n\n"
            f"💳 *اطلاعات پرداخت:*\n"
            f"`6219-8618-8369-7301`\n"
            f"🏦 مانی جعفریور - بلوپانک\n\n"
            f"⚠️ اگر با محدودیت تراکنش مواجه شدید، از همراه بانک استفاده کنید.\n\n"
            f"✅ این قیمت از صرافی نمایش داده شده است و کارمزد شبکه اعمال شده.\n"
            f"✅ تهیه این محصول نیازمند احراز هویت میباشد.\n\n"
            f"🔹 از پنل زیر سفارش و خرید خود را نهایی کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ========== کپی شماره کارت ==========
async def copy_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📋 *شماره کارت:*\n"
        "`6219861883697301`\n\n"
        "🏦 مانی جعفریور - بلوپانک\n\n"
        "✅ شماره کارت کپی شد!",
        parse_mode="Markdown"
    )

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
    
    if waiting_for == "receiver":
        update_order_extra(order_id, f"گیرنده: {text}")
    else:
        await update.message.reply_text("❌ خطا! لطفا دوباره تلاش کن.")
        return
    
    await show_payment(update, context, order_id, item_name, price)

# ========== ارسال رسید ==========
async def send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split('_')[2])
    
    context.user_data['order_id'] = order_id
    context.user_data['waiting_for'] = 'receipt'
    
    await query.edit_message_text(
        "📸 *ارسال رسید واریزی*\n\n"
        "💰 لطفاً عکس رسید واریزی خود را بفرستید.\n\n"
        "⚠️ فقط عکس (تصویر) مورد قبول است.\n"
        "📱 از همراه بانک خود استفاده کنید.",
        parse_mode="Markdown"
    )

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
            f"🌟 *خدمات ایران گیت آنی هست!*\n"
            f"⚡️ سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
            f"🆔 شماره سفارش: {order_id}\n\n"
            f"⏳ لطفاً چند دقیقه صبر کنید...\n"
            f"🔜 به زودی تحویل داده میشه!\n\n"
            f"🙏 از اعتماد شما سپاسگزاریم! 🌟",
            parse_mode="Markdown"
        )
        
        # ارسال به ادمین‌ها با اطلاعات کامل
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
            f"🌟 *خدمات ایران گیت آنی هست!*\n"
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
        [InlineKeyboardButton("🎁 خرید گیت استارزی", callback_data="buy_gift")],
        [InlineKeyboardButton("🪙 خرید تون (GRAM)", callback_data="buy_ton")],
        [InlineKeyboardButton("💎 خرید تلگرام پرمیوم", callback_data="buy_premium")],
        [InlineKeyboardButton("🚀 خرید بوست", callback_data="buy_boost")],
        [InlineKeyboardButton("👥 زیرمجموعه‌ها", callback_data="referrals")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]
    
    await query.edit_message_text(
        "🛒 *منوی اصلی*\n\n"
        "🌟 *ایران گیت استور*\n"
        "خدمات ما بر مبنای تحویل سریع و آنی سفارشات شماست.\n\n"
        "👇 یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== مدیریت پیام‌ها ==========
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for = context.user_data.get('waiting_for', '')
    
    if waiting_for in ['receiver']:
        await get_extra_info(update, context)
    elif waiting_for == 'receipt':
        await get_receipt(update, context)
    else:
        # اگر کاربر عددی وارد کرد (برای تون)
        await get_ton_amount(update, context)

# ========== دریافت مقدار تون ==========
async def get_ton_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    price = int(qty * PRICES["ton"])
    item_name = f"تون ({qty})"
    
    order_id = create_order(user_id, username, "ton", qty, price)
    context.user_data['order_id'] = order_id
    context.user_data['item_name'] = item_name
    context.user_data['price'] = price
    
    await show_payment(update, context, order_id, item_name, price)

# ========== اجرا ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(buy_gift, pattern="^buy_gift$"))
    app.add_handler(CallbackQueryHandler(buy_ton, pattern="^buy_ton$"))
    app.add_handler(CallbackQueryHandler(buy_premium, pattern="^buy_premium$"))
    app.add_handler(CallbackQueryHandler(buy_boost, pattern="^buy_boost$"))
    app.add_handler(CallbackQueryHandler(referrals, pattern="^referrals$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(copy_card, pattern="^copy_card$"))
    app.add_handler(CallbackQueryHandler(send_receipt, pattern="^send_receipt_"))
    app.add_handler(CallbackQueryHandler(process_purchase, pattern="^(gift_|premium_|boost_)"))
    app.add_handler(CallbackQueryHandler(confirm_receipt, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(reject_receipt, pattern="^reject_"))
    app.add_handler(MessageHandler(filters.PHOTO, get_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    print("🌟 ربات ایران گیت استور روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
