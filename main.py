# bot.py
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ============ تنظیمات ============
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"

# ⚠️ فقط این ۲ تا رو عوض کن:
REQUIRED_CHANNELS = ["@meowpoint_news"]  # یوزرنیم کانالت
ADMIN_ID = 6691993264  # آیدی عددی خودت

WITHDRAW_AMOUNTS = [120000, 240000, 360000, 490000, 620000, 750000]
REFERRAL_BONUS = 30000

# ============ دیتابیس ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_name = "bot.db"
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
        c.execute('INSERT INTO users (user_id, username, first_name, last_name, referred_by, join_date) VALUES (?,?,?,?,?,?)',
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

# ============ عضویت اجباری ============
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
    text = "❌ **برای استفاده از ربات عضو کانال شوید!**\n\n"
    for channel in REQUIRED_CHANNELS:
        ch = channel.replace('@', '').strip()
        try:
            chat = await context.bot.get_chat(f"@{ch}")
            text += f"🔹 {chat.title}\n"
        except:
            text += f"🔹 {channel}\n"
    text += "\nپس از عضویت دکمه رو بزنید."
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ============ منوی اصلی ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_membership(user.id, context):
        await show_join_message(update, context)
        return
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id:
                referred_by = None
        except:
            pass
    if not db.get_user(user.id):
        db.add_user(user.id, user.username, user.first_name, user.last_name, referred_by)
    await main_menu(update, context)

async def main_menu(update, context):
    user_id = update.effective_user.id
    if not await check_membership(user_id, context):
        await show_join_message(update, context)
        return
    user = db.get_user(user_id)
    keyboard = [
        [InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="referral")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="wallet")],
        [InlineKeyboardButton("💳 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("📊 اطلاعات من", callback_data="profile")],
    ]
    text = f"🌟 **به ربات خوش آمدی!**\n\n"
    text += f"👤 {update.effective_user.first_name}\n"
    if update.effective_user.username:
        text += f"🆔 @{update.effective_user.username}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: {user['balance']:,} میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ============ زیرمجموعه ============
async def referral_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={q.from_user.id}"
    text = f"👥 **زیرمجموعه‌گیری**\n\n"
    text += f"🎁 هر دعوت = {REFERRAL_BONUS:,} میوپوینت\n\n"
    text += f"🔗 لینک دعوت:\n`{link}`\n\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"💰 پاداش: {user['referral_count'] * REFERRAL_BONUS:,} میوپوینت"
    keyboard = [
        [InlineKeyboardButton("📋 کپی لینک", callback_data="copy_link")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={q.from_user.id}"
    text = f"🔗 لینک دعوت:\n`{link}`\n\n✅ کپی کن!"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="referral")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ============ کیف پول ============
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
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def transactions_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txs = db.get_transactions(q.from_user.id)
    if not txs:
        text = "📊 تراکنشی پیدا نشد."
    else:
        text = "📊 **آخرین تراکنش‌ها**\n\n"
        for t in txs:
            emoji = "➕" if t[0] > 0 else "➖"
            text += f"{emoji} {t[0]:+,} - {t[1]}\n   📅 {t[2]}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="wallet")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ============ برداشت ============
async def withdraw_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    text = f"💳 **برداشت**\n\n💰 موجودی: **{user['balance']:,}**\n\nمبلغ رو انتخاب کن:\n"
    keyboard = []
    for amount in WITHDRAW_AMOUNTS:
        if user['balance'] >= amount:
            keyboard.append([InlineKeyboardButton(f"✅ {amount:,}", callback_data=f"withdraw_{amount}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {amount:,}", callback_data="no_balance")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
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
    text = f"✅ **برداشت موفق!**\n\n💰 {amount:,} میوپوینت برداشت شد.\n💎 موجودی جدید: {db.get_balance(q.from_user.id):,}"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    # اطلاع به ادمین
    admin_text = f"🆕 درخواست برداشت:\n👤 {user['first_name']}\n💰 {amount:,} میوپوینت"
    await context.bot.send_message(ADMIN_ID, admin_text)

async def no_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("❌ موجودی کافی نیست!", show_alert=True)

# ============ اطلاعات کاربری ============
async def profile_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    text = f"📊 **اطلاعات من**\n\n"
    text += f"🆔 آیدی: `{q.from_user.id}`\n"
    text += f"👤 نام: {user['first_name']}\n"
    if user['username']:
        text += f"🆔 @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: **{user['balance']:,}**\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 عضویت: {user['join_date']}"
    if user['referred_by']:
        text += f"\n🔗 دعوت‌کننده: {user['referred_by']}"
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# ============ بررسی عضویت ============
async def check_membership_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await check_membership(q.from_user.id, context):
        await q.edit_message_text("✅ عضویت تایید شد!")
        if not db.get_user(q.from_user.id):
            db.add_user(q.from_user.id, q.from_user.username, q.from_user.first_name, q.from_user.last_name)
        await main_menu(update, context)
    else:
        await q.answer("❌ عضو نشدی!", show_alert=True)

# ============ دکمه‌ها ============
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

# ============ اجرا ============
def main():
    print("=" * 50)
    print("🌟 ربات خفن در حال اجرا...")
    print("=" * 50)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ ربات روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
