# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
import sqlite3
from datetime import datetime

# ========== تنظیمات ==========
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"
ADMIN_ID = 6691993264  # ← آیدی عددی خودت رو بذار
WITHDRAW_AMOUNTS = [120000, 240000, 360000, 490000, 620000, 750000]
REFERRAL_BONUS = 30000

# ========== دیتابیس ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("bot.db", check_same_thread=False)
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            join_date TEXT
        )''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            description TEXT,
            date TEXT
        )''')
        self.conn.commit()

    def add_user(self, user_id, username, first_name, referred_by=None):
        if self.get_user(user_id):
            return False
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.c.execute('INSERT INTO users VALUES (?,?,?,0,0,?,?)',
                       (user_id, username, first_name, referred_by, date))
        if referred_by:
            self.c.execute('UPDATE users SET balance = balance + ?, referral_count = referral_count + 1 WHERE user_id = ?',
                           (REFERRAL_BONUS, referred_by))
            self.c.execute('INSERT INTO transactions (user_id, amount, description, date) VALUES (?,?,?,?)',
                           (referred_by, REFERRAL_BONUS, f'پاداش دعوت از {user_id}', date))
        self.conn.commit()
        return True

    def get_user(self, user_id):
        self.c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = self.c.fetchone()
        if user:
            return {'user_id': user[0], 'username': user[1], 'first_name': user[2],
                    'balance': user[3], 'referral_count': user[4], 'referred_by': user[5], 'join_date': user[6]}
        return None

    def update_balance(self, user_id, amount, description):
        self.c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        self.c.execute('INSERT INTO transactions (user_id, amount, description, date) VALUES (?,?,?,?)',
                       (user_id, amount, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()

    def get_transactions(self, user_id):
        self.c.execute('SELECT amount, description, date FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 20',
                       (user_id,))
        return self.c.fetchall()

db = Database()

# ========== منوی اصلی ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id:
                referred_by = None
        except:
            pass
    db.add_user(user.id, user.username, user.first_name, referred_by)
    await main_menu(update, context)

async def main_menu(update, context):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="referral")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="wallet")],
        [InlineKeyboardButton("💳 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("📊 اطلاعات من", callback_data="profile")],
    ]
    
    text = f"🌟 **به ربات خفن خوش اومدی!**\n\n"
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

# ========== زیرمجموعه ==========
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

# ========== کیف پول ==========
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

# ========== برداشت ==========
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

# ========== اطلاعات کاربری ==========
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

# ========== مدیریت دکمه‌ها ==========
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

# ========== اجرا ==========
def main():
    print("=" * 50)
    print("🌟 ربات خفن - نسخه نهایی")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ ربات روشن شد!")
    print("📱 به ربات برو و /start بزن")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
