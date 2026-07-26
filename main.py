# bot.py - نسخه کامل با پنل ادمین
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== تنظیمات ====================
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"
REQUIRED_CHANNEL = "@meowpoint_news"  # 🔴 یوزرنیم کانال خودت رو بذار
ADMIN_ID = 6691993264  # 🔴 آیدی عددی خودت رو بذار
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
        self.c.execute('''CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
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

    def get_withdraw_requests(self, status='pending'):
        self.c.execute('SELECT id, user_id, amount, date FROM withdraw_requests WHERE status = ? ORDER BY id DESC', (status,))
        return self.c.fetchall()

    def add_withdraw_request(self, user_id, amount):
        self.c.execute('INSERT INTO withdraw_requests (user_id, amount, date) VALUES (?,?,?)',
                       (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return True

    def update_withdraw_status(self, request_id, status):
        self.c.execute('UPDATE withdraw_requests SET status = ? WHERE id = ?', (status, request_id))
        self.conn.commit()

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

# ==================== منوی اصلی کاربر ====================
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
        db.add_user(user_id, user.username, user.first_name, referred_by)
    
    # اگر ادمین بود، منوی ادمین رو نشون بده
    if user_id == ADMIN_ID:
        await admin_menu(update, context)
    else:
        await main_menu(update, context)

async def main_menu(update, context):
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
    """منوی ادمین"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ شما ادمین نیستید!")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 انتقال اعتبار", callback_data="admin_transfer")],
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 درخواست‌های برداشت", callback_data="admin_withdraws")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 برگشت به منوی کاربر", callback_data="main_menu")],
    ]
    
    text = "👑 **پنل مدیریت**\n\n"
    text += "یک گزینه را انتخاب کنید:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== انتقال اعتبار (ادمین) ====================
async def admin_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند انتقال اعتبار"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    await q.edit_message_text(
        "💰 **انتقال اعتبار**\n\n"
        "لطفاً به این فرمت پیام بفرستید:\n"
        "`/transfer [آیدی کاربر] [مبلغ]`\n\n"
        "مثال: `/transfer 123456789 50000`\n\n"
        "برای لغو، /cancel را بزنید."
    )
    
    # ذخیره وضعیت در context
    context.user_data['admin_action'] = 'transfer'

async def handle_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش انتقال اعتبار"""
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
        
        # بررسی وجود کاربر
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text(f"❌ کاربر با آیدی {target_id} پیدا نشد!")
            return
        
        # انتقال اعتبار
        db.update_balance(target_id, amount, f'انتقال از ادمین: {amount:,} میوپوینت')
        
        text = f"✅ انتقال اعتبار انجام شد!\n\n"
        text += f"👤 کاربر: {target_user['first_name']}\n"
        text += f"🆔 آیدی: {target_id}\n"
        text += f"💰 مبلغ: {amount:,} میوپوینت\n"
        text += f"💎 موجودی جدید: {db.get_balance(target_id):,} میوپوینت"
        
        await update.message.reply_text(text)
        
        # اطلاع به کاربر
        try:
            await context.bot.send_message(
                target_id,
                f"💰 {amount:,} میوپوینت به حساب شما واریز شد!\n"
                f"💎 موجودی جدید: {db.get_balance(target_id):,}"
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ لطفاً اعداد را درست وارد کنید!")

# ==================== آمار کاربران ====================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    users = db.get_all_users()
    total_users = len(users)
    total_balance = sum(user[3] for user in users)
    
    # محاسبه کل زیرمجموعه‌ها
    total_referrals = sum(user[4] for user in users)
    
    # درخواست‌های برداشت pending
    pending_withdraws = db.get_withdraw_requests('pending')
    
    text = f"📊 **آمار کلی**\n\n"
    text += f"👥 تعداد کل کاربران: {total_users} نفر\n"
    text += f"💰 کل موجودی: {total_balance:,} میوپوینت\n"
    text += f"👥 کل زیرمجموعه‌ها: {total_referrals} نفر\n"
    text += f"📋 درخواست‌های برداشت: {len(pending_withdraws)} مورد\n\n"
    
    # نمایش ۱۰ کاربر برتر
    sorted_users = sorted(users, key=lambda x: x[3], reverse=True)[:10]
    if sorted_users:
        text += "🏆 **۱۰ کاربر برتر**\n"
        for i, user in enumerate(sorted_users, 1):
            text += f"{i}. {user[2]} - {user[3]:,} میوپوینت\n"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت به پنل", callback_data="admin_panel")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== مدیریت درخواست‌های برداشت ====================
async def admin_withdraws(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش درخواست‌های برداشت"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    pending = db.get_withdraw_requests('pending')
    
    if not pending:
        text = "📋 هیچ درخواست برداشتی در انتظار نیست!"
        keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    text = f"📋 **درخواست‌های برداشت** ({len(pending)} مورد)\n\n"
    
    keyboard = []
    for req in pending:
        req_id, user_id, amount, date = req
        user = db.get_user(user_id)
        name = user['first_name'] if user else f"کاربر {user_id}"
        keyboard.append([
            InlineKeyboardButton(
                f"✅ {name} - {amount:,}",
                callback_data=f"approve_withdraw_{req_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def approve_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید درخواست برداشت"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    req_id = int(q.data.split('_')[2])
    
    # دریافت اطلاعات درخواست
    pending = db.get_withdraw_requests('pending')
    req = next((r for r in pending if r[0] == req_id), None)
    
    if not req:
        await q.edit_message_text("❌ این درخواست قبلاً پردازش شده!")
        return
    
    req_id, user_id, amount, date = req
    
    # تایید درخواست
    db.update_withdraw_status(req_id, 'approved')
    
    user = db.get_user(user_id)
    name = user['first_name'] if user else f"کاربر {user_id}"
    
    text = f"✅ درخواست برداشت تایید شد!\n\n"
    text += f"👤 {name}\n"
    text += f"💰 {amount:,} میوپوینت\n"
    
    await q.edit_message_text(text)
    
    # اطلاع به کاربر
    try:
        await context.bot.send_message(
            user_id,
            f"✅ درخواست برداشت {amount:,} میوپوینت شما تایید شد!\n"
            f"به زودی پرداخت خواهد شد."
        )
    except:
        pass
    
    # بازگشت به لیست درخواست‌ها
    await admin_withdraws(update, context)

# ==================== ارسال پیام همگانی ====================
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند ارسال پیام همگانی"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    await q.edit_message_text(
        "📢 **ارسال پیام همگانی**\n\n"
        "لطفاً پیام خود را بنویسید.\n"
        "این پیام برای تمام کاربران ارسال خواهد شد.\n\n"
        "برای لغو، /cancel را بزنید."
    )
    
    context.user_data['admin_action'] = 'broadcast'

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش ارسال پیام همگانی"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ شما ادمین نیستید!")
        return
    
    message_text = update.message.text
    
    if message_text == "/cancel":
        await update.message.reply_text("❌ عملیات لغو شد!")
        context.user_data.pop('admin_action', None)
        await admin_menu(update, context)
        return
    
    # دریافت لیست همه کاربران
    users = db.get_all_users()
    total = len(users)
    
    await update.message.reply_text(f"📤 در حال ارسال پیام به {total} کاربر...")
    
    success = 0
    fail = 0
    
    for user in users:
        try:
            await context.bot.send_message(user[0], message_text)
            success += 1
        except:
            fail += 1
        
        # تاخیر برای جلوگیری از محدودیت
        if success % 30 == 0:
            await asyncio.sleep(1)
    
    await update.message.reply_text(
        f"✅ پیام همگانی ارسال شد!\n\n"
        f"✅ موفق: {success}\n"
        f"❌ ناموفق: {fail}"
    )
    
    context.user_data.pop('admin_action', None)

# ==================== بخش‌های کاربری ====================
# (همون بخش‌های قبلی: referral, wallet, withdraw, profile)

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
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]
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
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]
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
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")])
    
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
    db.add_withdraw_request(q.from_user.id, amount)
    
    text = f"✅ برداشت موفق!\n\n"
    text += f"💰 {amount:,} میوپوینت برداشت شد.\n"
    text += f"💎 موجودی جدید: {db.get_user(q.from_user.id)['balance']:,}\n\n"
    text += "📝 درخواست شما ثبت شد و پس از تایید ادمین پرداخت می‌شود."
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # اطلاع به ادمین
    await context.bot.send_message(
        ADMIN_ID,
        f"🆕 درخواست برداشت جدید:\n👤 {user['first_name']}\n💰 {amount:,} میوپوینت"
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
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== بررسی عضویت با دکمه ====================
async def check_membership_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    
    if await check_membership(user_id, context):
        await q.edit_message_text("✅ عضویت شما تایید شد!")
        if not db.get_user(user_id):
            db.add_user(user_id, q.from_user.username, q.from_user.first_name)
        await main_menu(update, context)
    else:
        await q.answer("❌ هنوز در کانال عضو نشدی!", show_alert=True)

# ==================== مدیریت دکمه‌ها ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
    if data == "main_menu":
        await main_menu(update, context)
    elif data == "admin_panel":
        await admin_menu(update, context)
    elif data == "admin_transfer":
        await admin_transfer(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_withdraws":
        await admin_withdraws(update, context)
    elif data == "admin_broadcast":
        await admin_broadcast(update, context)
    elif data.startswith("approve_withdraw_"):
        await approve_withdraw(update, context)
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

# ==================== پیام‌های متنی ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی (برای دستورات ادمین)"""
    user_id = update.effective_user.id
    
    # اگر کاربر در حالت انتقال اعتبار است
    if context.user_data.get('admin_action') == 'transfer' and user_id == ADMIN_ID:
        await handle_transfer(update, context)
        return
    
    # اگر کاربر در حالت ارسال پیام همگانی است
    if context.user_data.get('admin_action') == 'broadcast' and user_id == ADMIN_ID:
        await handle_broadcast(update, context)
        return
    
    # دستورات معمولی
    if update.message.text == "/start":
        await start(update, context)
    elif update.message.text == "/cancel":
        context.user_data.pop('admin_action', None)
        await update.message.reply_text("✅ عملیات لغو شد!")
        await admin_menu(update, context)
    else:
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید.")

# ==================== اجرا ====================
def main():
    print("=" * 50)
    print("🌟 ربات خفن - نسخه نهایی با پنل ادمین")
    print("=" * 50)
    print(f"📢 کانال: {REQUIRED_CHANNEL}")
    print(f"👑 ادمین: {ADMIN_ID}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("✅ ربات روشن شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import asyncio
    main()
