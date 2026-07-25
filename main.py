
# bot_simple.py
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ==================== تنظیمات ====================
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"  # ← توکن خودت رو بذار
ADMIN_ID = 6691993264  # ← آیدی خودت رو بذار
WITHDRAW_AMOUNTS = [120000, 240000, 360000, 490000, 620000, 750000]

# ==================== دیتابیس ====================
class Database:
    def __init__(self):
        self.db_name = "bot_database.db"
        self.create_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def create_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                join_date TEXT,
                last_active TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                transaction_type TEXT,
                description TEXT,
                date TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_user(self, user_id, username, first_name, last_name, referred_by=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.close()
            return False
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, referred_by, join_date, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, referred_by, join_date, join_date))
        if referred_by:
            cursor.execute('''
                UPDATE users SET balance = balance + 30000, referral_count = referral_count + 1
                WHERE user_id = ?
            ''', (referred_by,))
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (referred_by, 30000, 'referral', f'جذب کاربر جدید: {user_id}', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True

    def get_user(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, balance, 
                   referral_count, referred_by, join_date, last_active
            FROM users WHERE user_id = ?
        ''', (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return {
                'user_id': user[0],
                'username': user[1],
                'first_name': user[2],
                'last_name': user[3],
                'balance': user[4],
                'referral_count': user[5],
                'referred_by': user[6],
                'join_date': user[7],
                'last_active': user[8]
            }
        return None

    def update_balance(self, user_id, amount, transaction_type, description):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, transaction_type, description, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, transaction_type, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True

    def get_balance(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    def get_transactions(self, user_id, limit=20):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT amount, transaction_type, description, date
            FROM transactions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        ''', (user_id, limit))
        transactions = cursor.fetchall()
        conn.close()
        return transactions

# ==================== تنظیمات لاگ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
db = Database()

# ==================== هندلرهای اصلی ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"🚀 کاربر جدید: {user_id} - {user.first_name}")
    
    # بررسی ریفرال
    referred_by = None
    if context.args and len(context.args) > 0:
        try:
            referred_by = int(context.args[0])
            if referred_by == user_id:
                referred_by = None
        except:
            referred_by = None
    
    # افزودن کاربر به دیتابیس
    user_data = db.get_user(user_id)
    if not user_data:
        db.add_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            referred_by=referred_by
        )
        logger.info(f"✅ کاربر {user_id} به دیتابیس اضافه شد")
    
    # نمایش منوی اصلی
    await main_menu(update, context)

async def main_menu(update, context):
    """منوی اصلی ربات"""
    user_id = None
    
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        await update.callback_query.answer()
    
    if not user_id:
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="referral")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="wallet")],
        [InlineKeyboardButton("💳 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("📊 اطلاعات کاربری", callback_data="profile")],
    ]
    
    text = f"**🤖 به ربات خفن خوش آمدید!**\n\n"
    text += f"👤 کاربر: {update.effective_user.first_name}\n"
    
    if update.effective_user.username:
        text += f"🆔 @{update.effective_user.username}\n"
    
    user_data = db.get_user(user_id)
    if user_data:
        text += f"💰 موجودی: {user_data['balance']:,} میوپوینت\n"
        text += f"👥 زیرمجموعه: {user_data['referral_count']} نفر\n"
    
    text += "\nیکی از گزینه‌های زیر را انتخاب کنید:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== بخش زیرمجموعه‌گیری ====================
async def referral_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    text = f"**👥 سیستم زیرمجموعه‌گیری**\n\n"
    text += f"با دعوت از دوستان خود، به ازای هر نفر **30,000 میوپوینت** دریافت کنید!\n\n"
    text += f"🔗 **لینک دعوت شما:**\n`{referral_link}`\n\n"
    text += f"👥 تعداد زیرمجموعه: {user_data['referral_count']} نفر\n"
    text += f"💰 پاداش دریافتی: {user_data['referral_count'] * 30000:,} میوپوینت\n\n"
    text += "📋 **راهنمایی:** لینک را کپی کنید و برای دوستان خود بفرستید."
    
    keyboard = [
        [InlineKeyboardButton("📋 کپی لینک", callback_data="copy_link")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    await query.edit_message_text(
        f"🔗 **لینک دعوت شما:**\n`{referral_link}`\n\n"
        f"✅ لینک کپی شد!\n"
        f"📋 برای کپی کردن، روی لینک بالا کلیک کرده و کپی کنید.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="referral")]])
    )

# ==================== بخش کیف پول ====================
async def wallet_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    text = f"**💰 کیف پول شما**\n\n"
    text += f"👤 کاربر: {user_data['first_name']}\n"
    if user_data['username']:
        text += f"🆔 @{user_data['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💎 موجودی: **{user_data['balance']:,}** میوپوینت\n"
    text += f"👥 زیرمجموعه: {user_data['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 تاریخ عضویت: {user_data['join_date']}\n\n"
    text += f"💡 هر زیرمجموعه = 30,000 میوپوینت"
    
    keyboard = [
        [InlineKeyboardButton("📊 تاریخچه تراکنش‌ها", callback_data="transactions")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def transactions_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    transactions = db.get_transactions(user_id)
    
    if not transactions:
        text = "📊 **تاریخچه تراکنش‌ها**\n\n"
        text += "هیچ تراکنشی یافت نشد."
    else:
        text = f"📊 **آخرین {len(transactions)} تراکنش**\n\n"
        for t in transactions:
            amount = t[0]
            type_emoji = "➕" if amount > 0 else "➖"
            text += f"{type_emoji} {amount:+,} - {t[2]}\n"
            text += f"   📅 {t[3]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به کیف پول", callback_data="wallet")]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== بخش برداشت ====================
async def withdraw_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    text = f"**💳 برداشت میوپوینت**\n\n"
    text += f"موجودی فعلی: **{user_data['balance']:,}** میوپوینت\n\n"
    text += f"مبلغ قابل برداشت را انتخاب کنید:\n"
    
    keyboard = []
    for amount in WITHDRAW_AMOUNTS:
        if user_data['balance'] >= amount:
            keyboard.append([InlineKeyboardButton(f"💵 {amount:,} میوپوینت", callback_data=f"withdraw_{amount}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {amount:,} (موجودی ناکافی)", callback_data="no_balance")])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    amount = int(query.data.split('_')[1])
    
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    if user_data['balance'] < amount:
        await query.edit_message_text("❌ موجودی کافی نیست!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="withdraw")]]))
        return
    
    db.update_balance(user_id, -amount, 'withdraw', f'برداشت مبلغ {amount:,} میوپوینت')
    
    text = f"✅ **برداشت با موفقیت انجام شد!**\n\n"
    text += f"💰 مبلغ: {amount:,} میوپوینت\n"
    text += f"💎 موجودی جدید: {db.get_balance(user_id):,} میوپوینت\n\n"
    text += "📝 درخواست شما ثبت شد و به زودی پرداخت خواهد شد."
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    # اطلاع به ادمین
    admin_text = f"🆕 **درخواست برداشت جدید**\n\n"
    admin_text += f"👤 کاربر: {user_data['first_name']}\n"
    if user_data['username']:
        admin_text += f"🆔 @{user_data['username']}\n"
    admin_text += f"🆔 آیدی: `{user_id}`\n"
    admin_text += f"💰 مبلغ: {amount:,} میوپوینت\n"
    admin_text += f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await context.bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.MARKDOWN)

async def no_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ موجودی کافی نیست!", show_alert=True)

# ==================== بخش اطلاعات کاربری ====================
async def profile_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    text = f"**📊 اطلاعات کاربری**\n\n"
    text += f"🆔 آیدی: `{user_id}`\n"
    text += f"👤 نام: {user_data['first_name']}\n"
    if user_data['last_name']:
        text += f"👤 نام خانوادگی: {user_data['last_name']}\n"
    if user_data['username']:
        text += f"🆔 یوزرنیم: @{user_data['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: **{user_data['balance']:,}** میوپوینت\n"
    text += f"👥 زیرمجموعه: {user_data['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 تاریخ عضویت: {user_data['join_date']}\n"
    
    if user_data['referred_by']:
        text += f"🔗 دعوت‌کننده: {user_data['referred_by']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== هندلر دکمه‌ها ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        await main_menu(update, context)
    elif data == "referral":
        await referral_section(update, context)
    elif data == "wallet":
        await wallet_section(update, context)
    elif data == "withdraw":
        await withdraw_section(update, context)
    elif data == "profile":
        await profile_section(update, context)
    elif data == "copy_link":
        await copy_link(update, context)
    elif data == "transactions":
        await transactions_section(update, context)
    elif data == "no_balance":
        await no_balance(update, context)
    elif data.startswith("withdraw_"):
        await process_withdraw(update, context)

# ==================== تابع اصلی ====================
def main():
    print("="*50)
    print("🤖 ربات خفن در حال راه‌اندازی...")
    print("="*50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ ربات با موفقیت اجرا شد!")
    print("📱 برای شروع به ربات خود در تلگرام پیام دهید")
    print("="*50)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
