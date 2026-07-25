# bot.py - نسخه نهایی با توکن شما
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
import sqlite3
import logging
from datetime import datetime

# ==================== تنظیمات ====================
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"
REQUIRED_CHANNELS = ["@meowpoint_news"]  # ← یوزرنیم کانالت رو بذار
ADMIN_ID = 6691993264  # ← آیدی عددی خودت رو بذار
WITHDRAW_AMOUNTS = [120000, 240000, 360000, 490000, 620000, 750000]
REFERRAL_BONUS = 30000

# ==================== دیتابیس ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_name = "khafan_bot.db"
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
                join_date TEXT
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                date TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_user(self, user_id, username, first_name, last_name, referred_by=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone():
            conn.close()
            return False
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, referred_by, join_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, referred_by, join_date))
        if referred_by:
            cursor.execute('''
                UPDATE users SET balance = balance + ?, referral_count = referral_count + 1
                WHERE user_id = ?
            ''', (REFERRAL_BONUS, referred_by))
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (referred_by, REFERRAL_BONUS, 'referral', f'پاداش دعوت از کاربر {user_id}', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True

    def get_user(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        user = cursor.execute('''
            SELECT user_id, username, first_name, last_name, balance, referral_count, referred_by, join_date
            FROM users WHERE user_id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        if user:
            return {
                'user_id': user[0], 'username': user[1], 'first_name': user[2],
                'last_name': user[3], 'balance': user[4], 'referral_count': user[5],
                'referred_by': user[6], 'join_date': user[7]
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
        result = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        return result[0] if result else 0

    def get_transactions(self, user_id, limit=20):
        conn = self.get_connection()
        transactions = conn.execute('''
            SELECT amount, transaction_type, description, date
            FROM transactions WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
        ''', (user_id, limit)).fetchall()
        conn.close()
        return transactions

    def add_withdraw_request(self, user_id, amount):
        conn = self.get_connection()
        conn.execute('''
            INSERT INTO withdraw_requests (user_id, amount, date)
            VALUES (?, ?, ?)
        ''', (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True

db = Database()

# ==================== توابع عضویت ====================
async def check_membership(user_id, context):
    if not REQUIRED_CHANNELS:
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            ch = channel.replace('@', '').strip()
            member = await context.bot.get_chat_member(chat_id=f"@{ch}", user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

async def show_join_message(update, context):
    keyboard = []
    for channel in REQUIRED_CHANNELS:
        ch = channel.replace('@', '').strip()
        keyboard.append([InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{ch}")])
    keyboard.append([InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")])
    text = "❌ **برای استفاده از ربات باید در کانال عضو شوید!**\n\n"
    for channel in REQUIRED_CHANNELS:
        ch = channel.replace('@', '').strip()
        try:
            chat = await context.bot.get_chat(f"@{ch}")
            text += f"🔹 {chat.title}\n"
        except:
            text += f"🔹 {channel}\n"
    text += "\nپس از عضویت، دکمه **بررسی عضویت** را بزنید."
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== منوی اصلی ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    logger.info(f"🚀 کاربر جدید: {user.first_name}")
    if not await check_membership(user_id, context):
        await show_join_message(update, context)
        return
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user_id:
                referred_by = None
        except:
            pass
    if not db.get_user(user_id):
        db.add_user(user_id, user.username, user.first_name, user.last_name, referred_by)
    await main_menu(update, context)

async def main_menu(update, context):
    user_id = update.effective_user.id
    if not await check_membership(user_id, context):
        await show_join_message(update, context)
        return
    user_data = db.get_user(user_id)
    keyboard = [
        [InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="referral")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="wallet")],
        [InlineKeyboardButton("💳 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("📊 اطلاعات کاربری", callback_data="profile")],
    ]
    text = f"🌟 **به ربات خفن خوش آمدید!**\n\n"
    text += f"👤 {update.effective_user.first_name}\n"
    if update.effective_user.username:
        text += f"🆔 @{update.effective_user.username}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: {user_data['balance']:,} میوپوینت\n"
    text += f"👥 زیرمجموعه: {user_data['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n\n"
    text += "📌 یکی از گزینه‌ها را انتخاب کنید:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== زیرمجموعه ====================
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
    text = f"👥 **سیستم زیرمجموعه‌گیری**\n\n"
    text += f"🎁 به ازای هر دعوت **{REFERRAL_BONUS:,}** میوپوینت دریافت کن!\n\n"
    text += f"🔗 **لینک دعوت شما:**\n`{referral_link}`\n\n"
    text += f"👥 زیرمجموعه: {user_data['referral_count']} نفر\n"
    text += f"💰 پاداش: {user_data['referral_count'] * REFERRAL_BONUS:,} میوپوینت"
    keyboard = [
        [InlineKeyboardButton("📋 کپی لینک", callback_data="copy_link")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    text = f"🔗 **لینک دعوت شما:**\n`{referral_link}`\n\n✅ لینک آماده کپی است!"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="referral")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== کیف پول ====================
async def wallet_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    text = f"💰 **کیف پول شما**\n\n"
    text += f"👤 {user_data['first_name']}\n"
    if user_data['username']:
        text += f"🆔 @{user_data['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💎 موجودی: **{user_data['balance']:,}** میوپوینت\n"
    text += f"👥 زیرمجموعه: {user_data['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 عضویت: {user_data['join_date']}\n\n"
    text += f"💡 هر زیرمجموعه = {REFERRAL_BONUS:,} میوپوینت"
    keyboard = [
        [InlineKeyboardButton("📊 تاریخچه تراکنش‌ها", callback_data="transactions")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def transactions_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    transactions = db.get_transactions(user_id)
    if not transactions:
        text = "📊 **تاریخچه تراکنش‌ها**\n\nهیچ تراکنشی یافت نشد."
    else:
        text = f"📊 **آخرین {len(transactions)} تراکنش**\n\n"
        for t in transactions:
            amount = t[0]
            emoji = "➕" if amount > 0 else "➖"
            text += f"{emoji} {amount:+,} - {t[2]}\n   📅 {t[3]}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="wallet")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== برداشت ====================
async def withdraw_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    text = f"💳 **برداشت میوپوینت**\n\n💰 موجودی: **{user_data['balance']:,}** میوپوینت\n\nمبلغ مورد نظر را انتخاب کنید:\n"
    keyboard = []
    for amount in WITHDRAW_AMOUNTS:
        if user_data['balance'] >= amount:
            keyboard.append([InlineKeyboardButton(f"✅ {amount:,}", callback_data=f"withdraw_{amount}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {amount:,}", callback_data="no_balance")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    amount = int(query.data.split('_')[1])
    user_data = db.get_user(user_id)
    if not user_data or user_data['balance'] < amount:
        await query.edit_message_text("❌ موجودی کافی نیست!")
        return
    db.update_balance(user_id, -amount, 'withdraw', f'برداشت {amount:,} میوپوینت')
    db.add_withdraw_request(user_id, amount)
    text = f"✅ **برداشت موفق!**\n\n💰 مبلغ: {amount:,} میوپوینت\n💎 موجودی جدید: {db.get_balance(user_id):,} میوپوینت\n\n📝 درخواست شما ثبت شد."
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    admin_text = f"🆕 **درخواست برداشت جدید**\n\n👤 {user_data['first_name']}\n"
    if user_data['username']:
        admin_text += f"🆔 @{user_data['username']}\n"
    admin_text += f"💰 مبلغ: {amount:,} میوپوینت\n🆔 آیدی: `{user_id}`"
    await context.bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.MARKDOWN)

async def no_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ موجودی کافی نیست!", show_alert=True)

# ==================== اطلاعات کاربری ====================
async def profile_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    if not user_data:
        await query.edit_message_text("❌ کاربر یافت نشد!")
        return
    text = f"📊 **اطلاعات کاربری**\n\n🆔 آیدی: `{user_id}`\n👤 نام: {user_data['first_name']}\n"
    if user_data['last_name']:
        text += f"👤 نام خانوادگی: {user_data['last_name']}\n"
    if user_data['username']:
        text += f"🆔 یوزرنیم: @{user_data['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n💰 موجودی: **{user_data['balance']:,}** میوپوینت\n👥 زیرمجموعه: {user_data['referral_count']} نفر\n━━━━━━━━━━━━━━━━━━\n📅 تاریخ عضویت: {user_data['join_date']}\n"
    if user_data['referred_by']:
        text += f"🔗 دعوت‌کننده: {user_data['referred_by']}"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def check_membership_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if await check_membership(user_id, context):
        await query.edit_message_text("✅ عضویت شما تایید شد!")
        if not db.get_user(user_id):
            db.add_user(user_id, query.from_user.username, query.from_user.first_name, query.from_user.last_name)
        await main_menu(update, context)
    else:
        await query.answer("❌ هنوز در کانال عضو نشدید!", show_alert=True)

# ==================== دکمه‌ها ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "main_menu":
        await main_menu(update, context)
    elif data == "referral":
        await referral_section(update, context)
    elif data == "copy_link":
        await copy_link(update, context)
    elif data == "wallet":
        await wallet_section(update, context)
    elif data == "transactions":
        await transactions_section(update, context)
    elif data == "withdraw":
        await withdraw_section(update, context)
    elif data.startswith("withdraw_"):
        await process_withdraw(update, context)
    elif data == "no_balance":
        await no_balance(update, context)
    elif data == "profile":
        await profile_section(update, context)
    elif data == "check_membership":
        await check_membership_button(update, context)

# ==================== اجرا ====================
def main():
    print("=" * 60)
    print("🌟 ربات خفن - نسخه حرفه‌ای")
    print("=" * 60)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ ربات با موفقیت اجرا شد!")
    print("📱 به ربات برو و /start بزن")
    print("=" * 60)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
