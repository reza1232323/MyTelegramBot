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

# ========== قیمت‌ها ==========
TON_PRICE = 340000
STAR_PRICE = 4000

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
        [InlineKeyboardButton("⭐ خرید استارز", callback_data="buy_stars")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
    ]

    await update.message.reply_text(
        "🌟 *به فروشگاه استارز لند خوش آمدی!* 🌟\n\n"
        "🪙 *تون:* 340,000 تومن\n"
        "⭐ *استارز:* 4,000 تومن هر عدد\n\n"
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
    context.user_data['product_type'] = 'stars'
    await query.edit_message_text(
        "⭐ *خرید استارز*\n\n"
        "💰 هر استارز = 4,000 تومن\n\n"
        "🔢 لطفاً تعداد استارز مورد نظر خود را وارد کن:\n"
        "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
        "مثال: 1 یا ۱",
        parse_mode="Markdown"
    )

# ========== دریافت مقدار و محاسبه قیمت ==========
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    item_type = context.user_data.get('product_type', 'ton')
    
    if item_type == "ton":
        price = int(qty * TON_PRICE)
        item_name = f"تون ({qty})"
        extra_prompt = "🪙 لطفاً آدرس ولت (Wallet) خود را برای دریافت تون وارد کن:"
        next_step = "wallet"
    else:
        price = int(qty * STAR_PRICE)
        item_name = f"استارز ({qty})"
        extra_prompt = "⭐ لطفاً لینک پست مورد نظر رو بفرست:"
        next_step = "post_link"

    order_id = create_order(user_id, username, item_type, qty, price)
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

# ========== دریافت اطلاعات تکمیلی ==========
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
        update_order_extra(order_id, text)
    elif waiting_for == "post_link":
        update_order_extra(order_id, text)
    else:
        await update.message.reply_text("❌ خطا!")
        return
    
    # فاکتور نهایی
    keyboard = [
        [InlineKeyboardButton("📋 کپی شماره کارت", callback_data="copy_card")],
        [InlineKeyboardButton("📸 ارسال رسید", callback_data=f"send_receipt_{order_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
    ]
    
    await update.message.reply_text(
        f"📋 *فاکتور شما*\n\n"
        f"👤 کاربر: @{update.effective_user.username or update.effective_user.first_name}\n"
        f"🛒 محصول: {item_name}\n"
        f"💰 مبلغ: {fmt(price)} تومن\n"
        f"🆔 شماره سفارش: {order_id}\n"
        f"📝 اطلاعات: {text}\n\n"
        f"💳 شماره کارت:\n"
        f"`6037-9970-1234-5678`\n"
        f"بانک ملی\n\n"
        f"بعد از واریز، روی 'ارسال رسید' کلیک کن.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    context.user_data['waiting_for'] = 'receipt'

# ========== کپی شماره کارت ==========
async def copy_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 شماره کارت:\n`6037-9970-1234-5678`\nبانک ملی",
        parse_mode="Markdown"
    )

# ========== ارسال رسید ==========
async def send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split('_')[2])
    context.user_data['order_id'] = order_id
    context.user_data['waiting_for'] = 'receipt'
    await query.edit_message_text("📸 لطفاً عکس رسید واریزی خود را بفرستید.")

# ========== دریافت رسید و ارسال به ادمین ==========
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
            f"✅ رسید شما دریافت شد!\n"
            f"سفارش #{order_id} در حال بررسی است.",
            parse_mode="Markdown"
        )
        
        cursor.execute('SELECT extra_info FROM orders WHERE id = ?', (order_id,))
        extra = cursor.fetchone()
        extra_info = extra[0] if extra else ""
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=f"📸 رسید جدید\n"
                            f"کاربر: @{username}\n"
                            f"آیدی: {user_id}\n"
                            f"محصول: {item_name}\n"
                            f"مبلغ: {fmt(price)} تومن\n"
                            f"شماره سفارش: {order_id}\n"
                            f"اطلاعات: {extra_info}\n"
                            f"زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ انجام شد", callback_data=f"confirm_{order_id}")],
                        [InlineKeyboardButton("❌ رد", callback_data=f"reject_{order_id}")]
                    ])
                )
            except Exception as e:
                logger.error(f"Error: {e}")
        
        context.user_data['waiting_for'] = ''
    else:
        await update.message.reply_text("❌ لطفاً یک عکس بفرستید.")

# ========== تایید ادمین ==========
async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی ندارید!")
        return
    
    order_id = int(query.data.split('_')[1])
    confirm_order(order_id)
    
    cursor.execute('SELECT user_id, username, item_type, quantity, price, extra_info FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if order:
        user_id, username, item_type, qty, price, extra_info = order
        
        try:
            await context.bot.send_message(
                user_id,
                f"✅ سفارش #{order_id} انجام شد!\n"
                f"محصول: {item_type} ({qty})\n"
                f"مبلغ: {fmt(price)} تومن\n\n"
                f"🙏 از اعتماد شما سپاسگزاریم!",
                parse_mode="Markdown"
            )
        except:
            pass
        
        await query.edit_message_text(f"✅ سفارش {order_id} انجام شد!")
    else:
        await query.edit_message_text("❌ سفارش پیدا نشد!")

# ========== رد ادمین ==========
async def reject_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی ندارید!")
        return
    
    order_id = int(query.data.split('_')[1])
    
    cursor.execute('SELECT user_id FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    if order:
        try:
            await context.bot.send_message(
                order[0],
                f"❌ سفارش #{order_id} رد شد!\n"
                f"لطفاً دوباره تلاش کنید."
            )
        except:
            pass
        
        await query.edit_message_text(f"❌ سفارش {order_id} رد شد!")
    else:
        await query.edit_message_text("❌ سفارش پیدا نشد!")

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
        await query.edit_message_text("📋 هیچ سفارشی ندارید.")
        return
    
    text = "📋 سفارشات شما:\n\n"
    for o in orders:
        status_emoji = "✅" if o[4] == "confirmed" else "⏳" if o[4] == "waiting_confirm" else "🆕"
        text += f"#{o[0]} - {o[1]} ({o[2]}) - {fmt(o[3])} تومن {status_emoji}\n"
        if o[5]:
            text += f"   {o[5]}\n"
    
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
        [InlineKeyboardButton("⭐ خرید استارز", callback_data="buy_stars")],
        [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
    ]
    
    await query.edit_message_text(
        "🛒 منوی اصلی\n\n"
        "🪙 تون: 340,000 تومن\n"
        "⭐ استارز: 4,000 تومن هر عدد\n\n"
        "👇 یکی رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== مدیریت پیام‌ها ==========
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for = context.user_data.get('waiting_for', '')
    product_type = context.user_data.get('product_type', '')
    
    if waiting_for in ['wallet', 'post_link']:
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
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(copy_card, pattern="^copy_card$"))
    app.add_handler(CallbackQueryHandler(send_receipt, pattern="^send_receipt_"))
    app.add_handler(CallbackQueryHandler(confirm_receipt, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(reject_receipt, pattern="^reject_"))
    app.add_handler(MessageHandler(filters.PHOTO, get_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    print("🌟 ربات استارز لند روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
