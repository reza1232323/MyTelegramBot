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

# ========== دیتابیس ==========
conn = sqlite3.connect('shop_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at INTEGER DEFAULT 0,
        total_referrals INTEGER DEFAULT 0
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

# ========== دکمه‌های رنگی (با ایموجی‌های خاص) ==========
def colored_buttons():
    return {
        "primary": "🔵",
        "success": "🟢",
        "danger": "🔴",
        "warning": "🟡",
        "purple": "🟣",
        "gold": "🌟",
        "gift": "🎁",
        "star": "⭐",
        "fire": "🔥",
        "rocket": "🚀",
        "diamond": "💎",
        "coin": "🪙",
    }

# ========== منوی اصلی با دکمه‌های رنگی ==========
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
        [InlineKeyboardButton("🟢 خرید استارز", callback_data="buy_stars")],
        [InlineKeyboardButton("🔵 خرید تون (GRAM)", callback_data="buy_ton")],
        [InlineKeyboardButton("🌟 خرید پرمیوم", callback_data="buy_premium")],
        [InlineKeyboardButton("🚀 خرید بوست", callback_data="buy_boost")],
        [InlineKeyboardButton("🎁 گیت‌های کلکسیونی", callback_data="buy_nft")],
        [InlineKeyboardButton("🟣 حساب کاربری", callback_data="profile")],
        [InlineKeyboardButton("👥 زیرمجموعه‌ها", callback_data="referrals")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
        [InlineKeyboardButton("💬 پشتیبانی", callback_data="support")],
    ]

    await update.message.reply_text(
        "🔥 *به فروشگاه شاهین خوش آمدی!* 🔥\n\n"
        "⚡️ *خدمات آنی و مطمئن*\n"
        "⭐ *مورد اعتماد هزاران کاربر*\n"
        "💰 *بهترین قیمت‌های ایران*\n\n"
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

# ========== خرید استارز (با دکمه‌های رنگی) ==========
async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🟢 50★ - 165,000 تومن", callback_data="stars_50")],
        [InlineKeyboardButton("🔵 100★ - 339,000 تومن", callback_data="stars_100")],
        [InlineKeyboardButton("🟣 200★ - 660,000 تومن", callback_data="stars_200")],
        [InlineKeyboardButton("🌟 500★ - 1,600,000 تومن", callback_data="stars_500")],
        [InlineKeyboardButton("⭐ 1000★ - 3,200,000 تومن", callback_data="stars_1000")],
        [InlineKeyboardButton("🔴 مقدار دلخواه", callback_data="stars_custom")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "⭐ *خرید استارز تلگرام*\n\n"
        "🌟 بهترین قیمت استارز در ایران:\n\n"
        "• 🟢 50★ = 165,000 تومن\n"
        "• 🔵 100★ = 339,000 تومن\n"
        "• 🟣 200★ = 660,000 تومن\n"
        "• 🌟 500★ = 1,600,000 تومن\n"
        "• ⭐ 1000★ = 3,200,000 تومن\n\n"
        "⚡️ تحویل آنی | 💎 تضمینی | 🔥 مطمئن\n\n"
        "مقدار مورد نظر رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید تون ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'ton'
    await query.edit_message_text(
        "🪙 *خرید تون (GRAM)*\n\n"
        "💰 هر تون = 33,467 تومن (قیمت لحظه‌ای)\n\n"
        "🔢 لطفاً تعداد تون مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 0.1 یا ۵\n\n"
        "⚡️ تحویل آنی | 🔥 مطمئن",
        parse_mode="Markdown"
    )

# ========== خرید پرمیوم ==========
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💎 ۱ ماه - 199,000 تومن", callback_data="premium_1")],
        [InlineKeyboardButton("🌟 ۳ ماه - 549,000 تومن", callback_data="premium_3")],
        [InlineKeyboardButton("🔥 ۶ ماه - 999,000 تومن", callback_data="premium_6")],
        [InlineKeyboardButton("⭐ ۱۲ ماه - 1,890,000 تومن", callback_data="premium_12")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "💎 *خرید تلگرام پرمیوم*\n\n"
        "🌟 بهترین قیمت پرمیوم در ایران:\n\n"
        "• 💎 ۱ ماه = 199,000 تومن\n"
        "• 🌟 ۳ ماه = 549,000 تومن\n"
        "• 🔥 ۶ ماه = 999,000 تومن\n"
        "• ⭐ ۱۲ ماه = 1,890,000 تومن\n\n"
        "⚡️ تحویل آنی | 💎 تضمینی | 🔥 مطمئن\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== خرید بوست ==========
async def buy_boost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🚀 ۱ بوست - 50,000 تومن", callback_data="boost_1")],
        [InlineKeyboardButton("🔥 ۵ بوست - 230,000 تومن", callback_data="boost_5")],
        [InlineKeyboardButton("🌟 ۱۰ بوست - 450,000 تومن", callback_data="boost_10")],
        [InlineKeyboardButton("⭐ ۲۰ بوست - 850,000 تومن", callback_data="boost_20")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "🚀 *خرید بوست تلگرام*\n\n"
        "🌟 افزایش رتبه کانال و گروه:\n\n"
        "• 🚀 ۱ بوست = 50,000 تومن\n"
        "• 🔥 ۵ بوست = 230,000 تومن\n"
        "• 🌟 ۱۰ بوست = 450,000 تومن\n"
        "• ⭐ ۲۰ بوست = 850,000 تومن\n\n"
        "⚡️ تحویل آنی | 💎 تضمینی | 🔥 مطمئن\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== گیت‌های کلکسیونی (NFT) ==========
async def buy_nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🟣 کیت ستاره 🌟", callback_data="nft_1")],
        [InlineKeyboardButton("🔵 کیت الماس 💎", callback_data="nft_2")],
        [InlineKeyboardButton("🟢 کیت طلایی 👑", callback_data="nft_3")],
        [InlineKeyboardButton("🔴 کیت ویژه 🔥", callback_data="nft_4")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await query.edit_message_text(
        "🎨 *گیت‌های کلکسیونی (NFT)*\n\n"
        "🌟 مجموعه‌های ویژه و نایاب:\n\n"
        "• 🟣 کیت ستاره = 250,000 تومن\n"
        "• 🔵 کیت الماس = 450,000 تومن\n"
        "• 🟢 کیت طلایی = 650,000 تومن\n"
        "• 🔴 کیت ویژه = 850,000 تومن\n\n"
        "⚡️ تحویل آنی | 💎 تضمینی | 🔥 مطمئن\n\n"
        "یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== حساب کاربری ==========
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    cursor.execute('SELECT created_at, total_referrals FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        await query.edit_message_text("❌ خطا! لطفا /start رو بزن.")
        return
    
    join_date = datetime.fromtimestamp(user[0]).strftime("%Y/%m/%d")
    
    await query.edit_message_text(
        "👤 *حساب کاربری شما*\n\n"
        f"🔹 نام کاربری: @{username}\n"
        f"🔹 آیدی: {user_id}\n"
        f"🔹 تاریخ عضویت: {join_date}\n"
        f"🔹 زیرمجموعه‌ها: {user[1]}\n\n"
        "🌟 *امتیازات ویژه:*\n"
        "• ۵+ زیرمجموعه = ۵٪ تخفیف\n"
        "• ۲۰+ زیرمجموعه = ۱۰٪ تخفیف\n"
        "• ۵۰+ زیرمجموعه = ۱۵٪ تخفیف\n\n"
        "🔥 هرچه زیرمجموعه بیشتر، تخفیف بیشتر!",
        parse_mode="Markdown"
    )

# ========== زیرمجموعه‌ها ==========
async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    cursor.execute('SELECT total_referrals FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    await query.edit_message_text(
        "👥 *سیستم زیرمجموعه‌گیری*\n\n"
        f"🔗 لینک دعوت اختصاصی شما:\n`{link}`\n\n"
        f"👥 تعداد زیرمجموعه‌ها: {user[0] if user else 0}\n"
        f"💰 پاداش هر دعوت: ۵,۰۰۰ تومن\n\n"
        "🎁 *پاداش‌های ویژه:*\n"
        "• ۵ دعوت = ۲۵,۰۰۰ تومن پاداش اضافه\n"
        "• ۲۰ دعوت = ۱۰۰,۰۰۰ تومن پاداش اضافه\n"
        "• ۵۰ دعوت = ۳۰۰,۰۰۰ تومن پاداش اضافه\n\n"
        "🔥 هر کس با لینک شما عضو بشه، پاداش می‌گیری!",
        parse_mode="Markdown"
    )

# ========== پشتیبانی ==========
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💬 *پشتیبانی ایران گیت*\n\n"
        "📞 *راه‌های ارتباطی:*\n\n"
        "👤 پشتیبان: @IRGiFT_Support\n"
        "📧 ایمیل: support@irangift.com\n\n"
        "⏰ *ساعات پاسخگویی:*\n"
        "• ۱۰ صبح تا ۱ شب\n"
        "• ۷ روز هفته\n\n"
        "💎 *ما همیشه در کنار شما هستیم!*",
        parse_mode="Markdown"
    )

# ========== راهنما ==========
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📖 *راهنمای کامل فروشگاه شاهین*\n\n"
        "⭐ *محصولات ما:*\n"
        "• استارز تلگرام (مستقیم و رو پست)\n"
        "• تون (GRAM) با قیمت لحظه‌ای\n"
        "• تلگرام پرمیوم (۱ تا ۱۲ ماه)\n"
        "• بوست تلگرام (افزایش رتبه)\n"
        "• گیت‌های کلکسیونی (NFT)\n\n"
        "📌 *نحوه خرید:*\n"
        "۱. محصول رو انتخاب کن\n"
        "۲. مبلغ رو به شماره کارت واریز کن\n"
        "۳. عکس رسید رو بفرست\n"
        "۴. منتظر تایید ادمین باش\n\n"
        "💰 *شماره کارت:*\n"
        "`6219-8618-8369-7301`\n"
        "🏦 مانی جعفریور - بلوپانک\n\n"
        "⏰ *زمان خدمات:* ۱۰ صبح تا ۱ شب\n"
        "🔥 *مورد اعتماد هزاران کاربر*",
        parse_mode="Markdown"
    )

# ========== پردازش خرید ==========
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    data = query.data
    
    # استارز
    if data.startswith("stars_"):
        qty = int(data.split('_')[1])
        price = qty * 3300
        item_name = f"استارز ({qty}★)"
        extra_prompt = "⭐ لطفاً آیدی (یوزرنیم) گیرنده استارز رو وارد کن:"
        next_step = "receiver"
        
        order_id = create_order(user_id, username, "stars", qty, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        context.user_data['waiting_for'] = next_step
        
        await query.edit_message_text(
            f"📋 *{item_name}*\n\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"{extra_prompt}\n\n"
            f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
            parse_mode="Markdown"
        )
        return
    
    # پرمیوم
    elif data.startswith("premium_"):
        months = data.split('_')[1]
        prices = {"1": 199000, "3": 549000, "6": 999000, "12": 1890000}
        price = prices.get(months, 0)
        item_name = f"پرمیوم ({months} ماه)"
        extra_prompt = "💎 لطفاً آیدی (یوزرنیم) خود را برای فعال‌سازی پرمیوم وارد کن:"
        next_step = "receiver"
        
        order_id = create_order(user_id, username, "premium", months, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        context.user_data['waiting_for'] = next_step
        
        await query.edit_message_text(
            f"📋 *{item_name}*\n\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"{extra_prompt}\n\n"
            f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
            parse_mode="Markdown"
        )
        return
    
    # بوست
    elif data.startswith("boost_"):
        count = data.split('_')[1]
        prices = {"1": 50000, "5": 230000, "10": 450000, "20": 850000}
        price = prices.get(count, 0)
        item_name = f"بوست ({count})"
        extra_prompt = "🚀 لطفاً لینک کانال یا گروه مورد نظر برای بوست رو وارد کن:"
        next_step = "post_link"
        
        order_id = create_order(user_id, username, "boost", count, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        context.user_data['waiting_for'] = next_step
        
        await query.edit_message_text(
            f"📋 *{item_name}*\n\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"{extra_prompt}\n\n"
            f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
            parse_mode="Markdown"
        )
        return
    
    # NFT
    elif data.startswith("nft_"):
        nft_prices = {"1": 250000, "2": 450000, "3": 650000, "4": 850000}
        price = nft_prices.get(data.split('_')[1], 0)
        item_name = f"گیت کلکسیونی"
        extra_prompt = "🎨 لطفاً آیدی (یوزرنیم) گیرنده گیت رو وارد کن:"
        next_step = "receiver"
        
        order_id = create_order(user_id, username, "nft", 1, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        context.user_data['waiting_for'] = next_step
        
        await query.edit_message_text(
            f"📋 *{item_name}*\n\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"{extra_prompt}\n\n"
            f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
            parse_mode="Markdown"
        )
        return

# ========== نمایش پرداخت ==========
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
            f"✅ این قیمت از صرافی نمایش داده شده است.\n"
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
            f"✅ این قیمت از صرافی نمایش داده شده است.\n"
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
    elif waiting_for == "post_link":
        update_order_extra(order_id, f"لینک: {text}")
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
            f"🌟 *خدمات شاهین آنی هست!*\n"
            f"⚡️ سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
            f"🆔 شماره سفارش: {order_id}\n\n"
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
            f"🌟 *خدمات شاهین آنی هست!*\n"
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

# ========== دریافت مقدار تون ==========
async def get_ton_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.strip()
    
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
    
    price = int(qty * 33467)
    item_name = f"تون ({qty})"
    
    order_id = create_order(user_id, username, "ton", qty, price)
    context.user_data['order_id'] = order_id
    context.user_data['item_name'] = item_name
    context.user_data['price'] = price
    
    await show_payment(update, context, order_id, item_name, price)

# ========== استارز دلخواه ==========
async def stars_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product_type'] = 'stars_custom'
    await query.edit_message_text(
        "⭐ *استارز دلخواه*\n\n"
        "🔢 لطفاً تعداد استارز مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "💰 هر استارز = 3,300 تومن\n\n"
        "مثال: 75 یا ۷۵",
        parse_mode="Markdown"
    )

# ========== دریافت استارز دلخواه ==========
async def get_custom_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.strip()
    
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
    
    price = qty * 3300
    item_name = f"استارز ({qty}★)"
    extra_prompt = "⭐ لطفاً آیدی (یوزرنیم) گیرنده استارز رو وارد کن:"
    next_step = "receiver"
    
    order_id = create_order(user_id, username, "stars", qty, price)
    context.user_data['order_id'] = order_id
    context.user_data['item_name'] = item_name
    context.user_data['price'] = price
    context.user_data['waiting_for'] = next_step
    
    await update.message.reply_text(
        f"📋 *{item_name}*\n\n"
        f"💰 مبلغ: {fmt(price)} تومن\n\n"
        f"{extra_prompt}\n\n"
        f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
        parse_mode="Markdown"
    )

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
        [InlineKeyboardButton("🟢 خرید استارز", callback_data="buy_stars")],
        [InlineKeyboardButton("🔵 خرید تون (GRAM)", callback_data="buy_ton")],
        [InlineKeyboardButton("🌟 خرید پرمیوم", callback_data="buy_premium")],
        [InlineKeyboardButton("🚀 خرید بوست", callback_data="buy_boost")],
        [InlineKeyboardButton("🎁 گیت‌های کلکسیونی", callback_data="buy_nft")],
        [InlineKeyboardButton("🟣 حساب کاربری", callback_data="profile")],
        [InlineKeyboardButton("👥 زیرمجموعه‌ها", callback_data="referrals")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
        [InlineKeyboardButton("💬 پشتیبانی", callback_data="support")],
    ]
    
    await query.edit_message_text(
        "🛒 *منوی اصلی*\n\n"
        "🔥 *فروشگاه شاهین*\n"
        "⚡️ تحویل آنی و مطمئن\n"
        "⭐ مورد اعتماد هزاران کاربر\n\n"
        "👇 یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== مدیریت پیام‌ها ==========
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for = context.user_data.get('waiting_for', '')
    product_type = context.user_data.get('product_type', '')
    
    if waiting_for in ['receiver', 'post_link']:
        await get_extra_info(update, context)
    elif waiting_for == 'receipt':
        await get_receipt(update, context)
    elif product_type == 'ton':
        await get_ton_amount(update, context)
    elif product_type == 'stars_custom':
        await get_custom_stars(update, context)

# ========== اجرا ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(buy_stars, pattern="^buy_stars$"))
    app.add_handler(CallbackQueryHandler(buy_ton, pattern="^buy_ton$"))
    app.add_handler(CallbackQueryHandler(buy_premium, pattern="^buy_premium$"))
    app.add_handler(CallbackQueryHandler(buy_boost, pattern="^buy_boost$"))
    app.add_handler(CallbackQueryHandler(buy_nft, pattern="^buy_nft$"))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(referrals, pattern="^referrals$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(copy_card, pattern="^copy_card$"))
    app.add_handler(CallbackQueryHandler(send_receipt, pattern="^send_receipt_"))
    app.add_handler(CallbackQueryHandler(stars_custom, pattern="^stars_custom$"))
    app.add_handler(CallbackQueryHandler(process_purchase, pattern="^(stars_|premium_|boost_|nft_)"))
    app.add_handler(CallbackQueryHandler(confirm_receipt, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(reject_receipt, pattern="^reject_"))
    app.add_handler(MessageHandler(filters.PHOTO, get_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    print("🔥 ربات شاهین استور روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
