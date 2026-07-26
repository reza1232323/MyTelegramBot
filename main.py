# bot.py
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== تنظیمات ====================
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"
REQUIRED_CHANNEL = "@YourChannel"  # 🔴 یوزرنیم کانال خودت رو بذار
ADMIN_ID = 123456789  # 🔴 آیدی عددی خودت رو بذار
WITHDRAW_AMOUNTS = [120000, 240000, 360000, 490000, 620000, 750000]
REFERRAL_BONUS = 30000

# ==================== دیتابیس ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_name = "bot.db"
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.c = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
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

    def get_balance(self, user_id):
        self.c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def get_transactions(self, user_id):
        self.c.execute('SELECT amount, description, date FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 20',
                       (user_id,))
        return self.c.fetchall()

    def get_all_users(self):
        self.c.execute('SELECT user_id, username, first_name, balance, referral_count FROM users')
        return self.c.fetchall()

db = Database()

# ==================== عضویت اجباری ====================
async def check_membership(user_id, context):
    if not REQUIRED_CHANNEL:
        return True
    channel = REQUIRED_CHANNEL.replace('@', '').strip()
    try:
        await context.bot.get_chat(f"@{channel}")
        member = await context.bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت: {e}")
        return True

async def show_join_message(update, context):
    channel = REQUIRED_CHANNEL.replace('@', '').strip()
    keyboard = [
        [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{channel}")],
        [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")]
    ]
    text = "❌ برای استفاده از ربات باید در کانال عضو شوید!\n\n"
    try:
        chat = await context.bot.get_chat(f"@{channel}")
        text += f"🔹 {chat.title}\n"
    except:
        text += f"🔹 {REQUIRED_CHANNEL}\n"
    text += "\nپس از عضویت، دکمه بررسی عضویت را بزنید."

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== منوی اصلی ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"🚀 کاربر: {user.first_name}")
    
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
        db.add_user(user_id, user.username, user.first_name, referred_by)
    
    # اگر ادمین بود، منوی ادمین رو نشون بده
    if user_id == ADMIN_ID:
        await admin_menu(update, context)
    else:
        await user_menu(update, context)

async def user_menu(update, context):
    """منوی کاربر عادی"""
    user_id = update.effective_user.id
    
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
    
    text = f"🌟 به ربات خفن خوش آمدی!\n\n"
    text += f"👤 {user['first_name']}\n"
    if user['username']:
        text += f"🆔 @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: {user['balance']:,} میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== پنل ادمین ====================
async def admin_menu(update, context):
    """پنل مدیریت"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("❌ شما ادمین نیستید!")
        else:
            await update.callback_query.answer("❌ شما ادمین نیستید!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 انتقال اعتبار", callback_data="admin_transfer")],
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 منوی کاربر", callback_data="user_menu")],
    ]
    
    text = "👑 **پنل مدیریت**\n\nیک گزینه را انتخاب کنید:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== انتقال اعتبار ====================
async def admin_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال اعتبار به کاربر"""
    q = update.callback_query
    await q.answer()
    
    await q.edit_message_text(
        "💰 **انتقال اعتبار**\n\n"
        "فرمت: `/transfer [آیدی] [مبلغ]`\n"
        "مثال: `/transfer 123456789 50000`\n\n"
        "برای لغو: /cancel"
    )
    context.user_data['admin_mode'] = 'transfer'

async def handle_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش انتقال"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ شما ادمین نیستید!")
        return
    
    try:
        parts = update.message.text.split()
        if len(parts) != 3:
            await update.message.reply_text("❌ فرمت اشتباه!\nمثال: `/transfer 123456789 50000`")
            return
        
        target_id = int(parts[1])
        amount = int(parts[2])
        
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید مثبت باشد!")
            return
        
        user = db.get_user(target_id)
        if not user:
            await update.message.reply_text(f"❌ کاربر با آیدی {target_id} پیدا نشد!")
            return
        
        db.update_balance(target_id, amount, f'انتقال از ادمین: {amount:,} میوپوینت')
        
        await update.message.reply_text(
            f"✅ انتقال انجام شد!\n"
            f"👤 {user['first_name']}\n"
            f"💰 {amount:,} میوپوینت\n"
            f"💎 موجودی جدید: {db.get_balance(target_id):,}"
        )
        
        try:
            await context.bot.send_message(
                target_id,
                f"💰 {amount:,} میوپوینت به حساب شما واریز شد!\n"
                f"💎 موجودی: {db.get_balance(target_id):,}"
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ لطفاً اعداد را درست وارد کنید!")
    
    context.user_data.pop('admin_mode', None)

# ==================== آمار کاربران ====================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار"""
    q = update.callback_query
    await q.answer()
    
    users = db.get_all_users()
    total = len(users)
    total_balance = sum(u[3] for u in users)
    total_referrals = sum(u[4] for u in users)
    
    text = f"📊 **آمار کلی**\n\n"
    text += f"👥 کل کاربران: {total} نفر\n"
    text += f"💰 کل موجودی: {total_balance:,} میوپوینت\n"
    text += f"👥 کل زیرمجموعه‌ها: {total_referrals} نفر\n\n"
    
    # برترین‌ها
    sorted_users = sorted(users, key=lambda x: x[3], reverse=True)[:5]
    if sorted_users:
        text += "🏆 **۵ کاربر برتر**\n"
        for i, u in enumerate(sorted_users, 1):
            text += f"{i}. {u[2]} - {u[3]:,}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== ارسال پیام همگانی ====================
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام همگانی"""
    q = update.callback_query
    await q.answer()
    
    await q.edit_message_text(
        "📢 **ارسال پیام همگانی**\n\n"
        "پیام خود را بنویسید.\n"
        "برای لغو: /cancel"
    )
    context.user_data['admin_mode'] = 'broadcast'

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام همگانی"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ شما ادمین نیستید!")
        return
    
    if update.message.text == "/cancel":
        await update.message.reply_text("❌ لغو شد!")
        context.user_data.pop('admin_mode', None)
        await admin_menu(update, context)
        return
    
    users = db.get_all_users()
    await update.message.reply_text(f"📤 ارسال به {len(users)} کاربر...")
    
    success = 0
    for user in users:
        try:
            await context.bot.send_message(user[0], update.message.text)
            success += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ پیام به {success} کاربر ارسال شد!")
    context.user_data.pop('admin_mode', None)

# ==================== بخش‌های کاربری ====================
async def referral_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={q.from_user.id}"
    
    text = f"👥 زیرمجموعه‌گیری\n\n"
    text += f"🎁 هر دعوت = {REFERRAL_BONUS:,} میوپوینت\n\n"
    text += f"🔗 لینک دعوتت:\n{link}\n\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"💰 پاداش: {user['referral_count'] * REFERRAL_BONUS:,} میوپوینت"
    
    keyboard = [
        [InlineKeyboardButton("📋 کپی لینک", callback_data="copy_link")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="user_menu")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={q.from_user.id}"
    text = f"🔗 لینک دعوتت:\n{link}\n\n✅ کپی کن!"
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="referral")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def wallet_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"💰 کیف پول\n\n"
    text += f"👤 {user['first_name']}\n"
    if user['username']:
        text += f"🆔 @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💎 موجودی: {user['balance']:,} میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 عضویت: {user['join_date']}"
    
    keyboard = [
        [InlineKeyboardButton("📊 تراکنش‌ها", callback_data="transactions")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="user_menu")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def transactions_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txs = db.get_transactions(q.from_user.id)
    
    if not txs:
        text = "📊 هنوز تراکنشی نداری!"
    else:
        text = "📊 آخرین تراکنش‌ها\n\n"
        for t in txs:
            emoji = "➕" if t[0] > 0 else "➖"
            text += f"{emoji} {t[0]:+,} - {t[1]}\n   📅 {t[2]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="wallet")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def withdraw_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"💳 برداشت\n\n💰 موجودی: {user['balance']:,} میوپوینت\n\nمبلغ رو انتخاب کن:\n"
    
    keyboard = []
    for amount in WITHDRAW_AMOUNTS:
        if user['balance'] >= amount:
            keyboard.append([InlineKeyboardButton(f"✅ {amount:,}", callback_data=f"withdraw_{amount}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {amount:,}", callback_data="no_balance")])
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="user_menu")])
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    amount = int(q.data.split('_')[1])
    user = db.get_user(q.from_user.id)
    
    if user['balance'] < amount:
        await q.edit_message_text("❌ موجودی کافی نیست!")
        return
    
    db.update_balance(q.from_user.id, -amount, f'برداشت {amount:,} میوپوینت')
    
    text = f"✅ برداشت موفق!\n\n"
    text += f"💰 {amount:,} میوپوینت برداشت شد.\n"
    text += f"💎 موجودی جدید: {db.get_user(q.from_user.id)['balance']:,}"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="user_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    await context.bot.send_message(
        ADMIN_ID,
        f"🆕 برداشت:\n👤 {user['first_name']}\n💰 {amount:,}"
    )

async def no_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("❌ موجودی کافی نیست!", show_alert=True)

async def profile_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"📊 اطلاعات من\n\n"
    text += f"🆔 آیدی: {q.from_user.id}\n"
    text += f"👤 نام: {user['first_name']}\n"
    if user['username']:
        text += f"🆔 یوزرنیم: @{user['username']}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 موجودی: {user['balance']:,} میوپوینت\n"
    text += f"👥 زیرمجموعه: {user['referral_count']} نفر\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📅 عضویت: {user['join_date']}"
    if user['referred_by']:
        text += f"\n🔗 دعوت‌کننده: {user['referred_by']}"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="user_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== بررسی عضویت ====================
async def check_membership_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if await check_membership(q.from_user.id, context):
        await q.edit_message_text("✅ عضویت تایید شد!")
        if not db.get_user(q.from_user.id):
            db.add_user(q.from_user.id, q.from_user.username, q.from_user.first_name)
        await user_menu(update, context)
    else:
        await q.answer("❌ عضو نشدی!", show_alert=True)

# ==================== مدیریت دکمه‌ها ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
    if data == "user_menu":
        await user_menu(update, context)
    elif data == "admin_panel":
        await admin_menu(update, context)
    elif data == "admin_transfer":
        await admin_transfer(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_broadcast":
        await admin_broadcast(update, context)
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

# ==================== پیام‌ها ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # حالت ادمین
    if context.user_data.get('admin_mode') == 'transfer' and user_id == ADMIN_ID:
        await handle_transfer(update, context)
        return
    
    if context.user_data.get('admin_mode') == 'broadcast' and user_id == ADMIN_ID:
        await handle_broadcast(update, context)
        return
    
    if text == "/start":
        await start(update, context)
    elif text == "/cancel":
        context.user_data.pop('admin_mode', None)
        await update.message.reply_text("✅ لغو شد!")
        if user_id == ADMIN_ID:
            await admin_menu(update, context)
        else:
            await user_menu(update, context)
    else:
        await update.message.reply_text("❌ از دکمه‌ها استفاده کن!")

# ==================== اجرا ====================
def main():
    print("=" * 50)
    print("🌟 ربات خفن با پنل ادمین")
    print("=" * 50)
    print(f"👑 ادمین: {ADMIN_ID}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("✅ ربات روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
