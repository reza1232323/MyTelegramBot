# bot.py
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ==================== تنظیمات ====================
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"

# ⚠️ یوزرنیم کانال رو اینجا بذار (با @)
REQUIRED_CHANNEL = "@meowpoint_news"  # ← مثلاً @khafan_channel

# آیدی عددی خودت برای دریافت اعلان
ADMIN_ID = 6691993264  # ← با ربات @userinfobot پیدا کن

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
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            balance INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            join_date TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            description TEXT,
            date TEXT
        )''')
        conn.commit()
        conn.close()

    def add_user(self, user_id, username, first_name, last_name, referred_by=None):
        conn = self.get_connection()
        c = conn.cursor()
        if c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone():
            conn.close()
            return False
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO users VALUES (?,?,?,?,0,0,?,?)',
                  (user_id, username, first_name, last_name, referred_by, join_date))
        if referred_by:
            c.execute('UPDATE users SET balance = balance + ?, referral_count = referral_count + 1 WHERE user_id = ?',
                      (REFERRAL_BONUS, referred_by))
            c.execute('INSERT INTO transactions (user_id, amount, description, date) VALUES (?,?,?,?)',
                      (referred_by, REFERRAL_BONUS, f'پاداش دعوت از {user_id}', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True

    def get_user(self, user_id):
        conn = self.get_connection()
        c = conn.cursor()
        user = c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        if user:
            return {'user_id': user[0], 'username': user[1], 'first_name': user[2],
                    'last_name': user[3], 'balance': user[4], 'referral_count': user[5],
                    'referred_by': user[6], 'join_date': user[7]}
        return None

    def update_balance(self, user_id, amount, description):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        c.execute('INSERT INTO transactions (user_id, amount, description, date) VALUES (?,?,?,?)',
                  (user_id, amount, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    def get_balance(self, user_id):
        conn = self.get_connection()
        result = conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return result[0] if result else 0

    def get_transactions(self, user_id):
        conn = self.get_connection()
        txs = conn.execute('SELECT amount, description, date FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 20',
                           (user_id,)).fetchall()
        conn.close()
        return txs

db = Database()

# ==================== عضویت اجباری (رفع شده) ====================
async def check_membership(user_id, context):
    """بررسی عضویت کاربر در کانال"""
    if not REQUIRED_CHANNEL:
        return True
    
    try:
        # حذف @ از ابتدا
        channel = REQUIRED_CHANNEL.replace('@', '').strip()
        
        # دریافت اطلاعات کانال
        try:
            chat = await context.bot.get_chat(f"@{channel}")
            logger.info(f"✅ کانال پیدا شد: {chat.title}")
        except Exception as e:
            logger.error(f"❌ کانال پیدا نشد: {e}")
            # اگر کانال پیدا نشد، اجازه بده وارد بشه
            return True
        
        # بررسی عضویت کاربر
        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status in ['member', 'administrator', 'creator']:
                logger.info(f"✅ کاربر {user_id} عضو است")
                return True
            else:
                logger.info(f"❌ کاربر {user_id} عضو نیست")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در بررسی عضویت: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطا: {e}")
        return True  # در صورت خطا، اجازه بده وارد بشه

async def show_join_message(update, context):
    """نمایش پیام عضویت اجباری"""
    channel = REQUIRED_CHANNEL.replace('@', '').strip()
    
    keyboard = [
        [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{channel}")],
        [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")]
    ]
    
    text = f"❌ **برای استفاده از ربات باید در کانال عضو شوید!**\n\n"
    
    try:
        chat = await context.bot.get_chat(f"@{channel}")
        text += f"🔹 {chat.title}\n"
    except:
        text += f"🔹 {REQUIRED_CHANNEL}\n"
    
    text += "\nپس از عضویت، دکمه **بررسی عضویت** را بزنید."
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== منوی اصلی ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"🚀 کاربر جدید: {user.first_name} (ID: {user_id})")
    
    # بررسی عضویت
    if not await check_membership(user_id, context):
        await show_join_message(update, context)
        return
    
    # بررسی ریفرال
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user_id:
                referred_by = None
        except:
            pass
    
    # ثبت کاربر
    if not db.get_user(user_id):
        db.add_user(user_id, user.username, user.first_name, user.last_name, referred_by)
        logger.info(f"✅ کاربر ثبت شد: {user_id}")
    
    await main_menu(update, context)

async def main_menu(update, context):
    user_id = update.effective_user.id
    
    # بررسی عضویت
    if not await check_membership(user_id, context):
        await show_join_message(update, context)
        return
    
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ خطا! دوباره /start بزن.")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="referral")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="wallet")],
        [InlineKeyboardButton("💳 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("📊 اطلاعات من", callback_data="profile")],
    ]
    
    text = f"🌟 **به ربات خفن خوش آمدی!**\n\n"
    text += f"👤 {user['first_name']}\n"
    if user['username']:
        text += f"🆔 @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: {user['balance']:,} میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== زیرمجموعه ====================
async def referral_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={q.from_user.id}"
    
    text = f"👥 **زیرمجموعه‌گیری**\n\n"
    text += f"🎁 هر دعوت = {REFERRAL_BONUS:,} میوپوینت\n\n"
    text += f"🔗 لینک دعوتت:\n`{link}`\n\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"💰 پاداش: {user['referral_count'] * REFERRAL_BONUS:,} میوپوینت"
    
    keyboard = [
        [InlineKeyboardButton("📋 کپی لینک", callback_data="copy_link")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={q.from_user.id}"
    text = f"🔗 لینک دعوتت:\n`{link}`\n\n✅ کپی کن!"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="referral")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== کیف پول ====================
async def wallet_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"💰 **کیف پول**\n\n"
    text += f"👤 {user['first_name']}\n"
    if user['username']:
        text += f"🆔 @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💎 موجودی: **{user['balance']:,}** میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 عضویت: {user['join_date']}"
    
    keyboard = [
        [InlineKeyboardButton("📊 تراکنش‌ها", callback_data="transactions")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def transactions_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txs = db.get_transactions(q.from_user.id)
    
    if not txs:
        text = "📊 هنوز تراکنشی نداری!"
    else:
        text = "📊 **آخرین تراکنش‌ها**\n\n"
        for t in txs:
            emoji = "➕" if t[0] > 0 else "➖"
            text += f"{emoji} {t[0]:+,} - {t[1]}\n   📅 {t[2]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="wallet")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== برداشت ====================
async def withdraw_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"💳 **برداشت**\n\n💰 موجودی: **{user['balance']:,}** میوپوینت\n\nمبلغ رو انتخاب کن:\n"
    
    keyboard = []
    for amount in WITHDRAW_AMOUNTS:
        if user['balance'] >= amount:
            keyboard.append([InlineKeyboardButton(f"✅ {amount:,}", callback_data=f"withdraw_{amount}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {amount:,}", callback_data="no_balance")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")])
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    amount = int(q.data.split('_')[1])
    user = db.get_user(q.from_user.id)
    
    if user['balance'] < amount:
        await q.edit_message_text("❌ موجودی کافی نیست!")
        return
    
    db.update_balance(q.from_user.id, -amount, f'برداشت {amount:,} میوپوینت')
    
    text = f"✅ **برداشت موفق!**\n\n"
    text += f"💰 {amount:,} میوپوینت برداشت شد.\n"
    text += f"💎 موجودی جدید: {db.get_user(q.from_user.id)['balance']:,}"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    # اطلاع به ادمین
    await context.bot.send_message(
        ADMIN_ID,
        f"🆕 درخواست برداشت:\n👤 {user['first_name']}\n💰 {amount:,} میوپوینت"
    )

async def no_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("❌ موجودی کافی نیست!", show_alert=True)

# ==================== اطلاعات کاربری ====================
async def profile_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"📊 **اطلاعات من**\n\n"
    text += f"🆔 آیدی: `{q.from_user.id}`\n"
    text += f"👤 نام: {user['first_name']}\n"
    if user['username']:
        text += f"🆔 یوزرنیم: @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: **{user['balance']:,}** میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 عضویت: {user['join_date']}"
    if user['referred_by']:
        text += f"\n🔗 دعوت‌کننده: {user['referred_by']}"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ==================== بررسی عضویت با دکمه ====================
async def check_membership_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    
    if await check_membership(user_id, context):
        await q.edit_message_text("✅ عضویت شما تایید شد!")
        if not db.get_user(user_id):
            db.add_user(user_id, q.from_user.username, q.from_user.first_name, q.from_user.last_name)
        await main_menu(update, context)
    else:
        await q.answer("❌ هنوز در کانال عضو نشدی!", show_alert=True)

# ==================== مدیریت دکمه‌ها ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
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
    print("=" * 50)
    print("🌟 ربات خفن - نسخه نهایی")
    print("=" * 50)
    print(f"📢 کانال: {REQUIRED_CHANNEL}")
    print(f"👑 ادمین: {ADMIN_ID}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ ربات روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
