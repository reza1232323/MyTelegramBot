# bot.py
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== تنظیمات ====================
BOT_TOKEN = "8666500631:AAFGa6fM4jnUYlYBiBLYl1vDmgGM8PSQpa8"

# 📢 لیست کانال‌های اجباری (هر تعداد که دوست داری)
REQUIRED_CHANNELS = [
    "@meowpoint_news",  # ← کانال اول
    "@meowpoint_buy",  # ← کانال دوم
    # "@YourChannel3",  # ← کانال سوم (اختیاری)
]

ADMIN_ID = 123456789  # ← آیدی عددی خودت (با @userinfobot پیدا کن)
WITHDRAW_AMOUNTS = [120000, 240000, 360000, 490000, 620000, 750000]
REFERRAL_BONUS = 30000

# ==================== دیتابیس (سازگار با قبلی) ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_name = "bot.db"
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.c = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # جدول کاربران (همون قبلی)
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            join_date TEXT
        )''')
        
        # جدول تراکنش‌ها (همون قبلی)
        self.c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            description TEXT,
            date TEXT
        )''')
        
        # جدول درخواست‌های برداشت (همون قبلی)
        self.c.execute('''CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            date TEXT
        )''')
        
        # ✅ جدول جدید برای تنظیمات (اختیاری)
        self.c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        self.conn.commit()
        logger.info("✅ دیتابیس آماده است (سازگار با نسخه قبلی)")

    def add_user(self, user_id, username, first_name, referred_by=None):
        if self.get_user(user_id):
            return False
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.c.execute('INSERT INTO users (user_id, username, first_name, referred_by, join_date) VALUES (?,?,?,?,?)',
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
            return {
                'user_id': user[0],
                'username': user[1],
                'first_name': user[2],
                'balance': user[3],
                'referral_count': user[4],
                'referred_by': user[5],
                'join_date': user[6]
            }
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

    def add_withdraw_request(self, user_id, amount):
        self.c.execute('INSERT INTO withdraw_requests (user_id, amount, date) VALUES (?,?,?)',
                       (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return True

    def get_withdraw_requests(self, status='pending'):
        self.c.execute('SELECT id, user_id, amount, date FROM withdraw_requests WHERE status = ? ORDER BY id DESC', (status,))
        return self.c.fetchall()

    def update_withdraw_status(self, request_id, status):
        self.c.execute('UPDATE withdraw_requests SET status = ? WHERE id = ?', (status, request_id))
        self.conn.commit()

db = Database()

# ==================== عضویت اجباری (چند کانال) ====================
async def check_membership(user_id, context):
    """بررسی عضویت در چند کانال"""
    if not REQUIRED_CHANNELS:
        return True
    
    for channel in REQUIRED_CHANNELS:
        try:
            ch = channel.replace('@', '').strip()
            # بررسی وجود کانال
            await context.bot.get_chat(f"@{ch}")
            # بررسی عضویت کاربر
            member = await context.bot.get_chat_member(chat_id=f"@{ch}", user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                logger.info(f"❌ کاربر {user_id} در کانال {channel} عضو نیست")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در بررسی کانال {channel}: {e}")
            return False
    
    logger.info(f"✅ کاربر {user_id} در همه کانال‌ها عضو است")
    return True

async def show_join_message(update, context):
    """نمایش پیام عضویت در چند کانال"""
    keyboard = []
    text = "❌ **برای استفاده از ربات باید در کانال‌های زیر عضو شوید:**\n\n"
    
    for channel in REQUIRED_CHANNELS:
        ch = channel.replace('@', '').strip()
        link = f"https://t.me/{ch}"
        
        try:
            chat = await context.bot.get_chat(f"@{ch}")
            channel_name = chat.title or channel
            text += f"🔹 {channel_name}\n"
        except:
            text += f"🔹 {channel}\n"
        
        keyboard.append([InlineKeyboardButton(f"📢 عضویت در کانال", url=link)])
    
    keyboard.append([InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")])
    text += "\nپس از عضویت در همه کانال‌ها، دکمه **بررسی عضویت** را بزنید."
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== منوی اصلی ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"🚀 کاربر: {user.first_name} (ID: {user_id})")
    
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
        logger.info(f"✅ کاربر جدید ثبت شد: {user_id}")
    
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
        [InlineKeyboardButton("📋 درخواست‌های برداشت", callback_data="admin_withdraws")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 منوی کاربر", callback_data="user_menu")],
    ]
    
    text = "👑 **پنل مدیریت**\n\nیک گزینه را انتخاب کنید:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== انتقال اعتبار (دکمه‌ای) ====================
async def admin_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست کاربران برای انتقال"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    users = db.get_all_users()
    
    if not users:
        await q.edit_message_text("❌ هیچ کاربری در دیتابیس وجود ندارد!")
        return
    
    text = "💰 **انتقال اعتبار**\n\nکاربر مورد نظر را انتخاب کنید:\n"
    
    keyboard = []
    for user in users[:10]:
        user_id, username, first_name, balance, _ = user
        name = first_name if first_name else f"کاربر {user_id}"
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {name} - {balance:,}",
                callback_data=f"transfer_user_{user_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش دکمه‌های مبلغ برای انتقال"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    target_id = int(q.data.split('_')[2])
    context.user_data['transfer_target'] = target_id
    
    target_user = db.get_user(target_id)
    if not target_user:
        await q.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    text = f"💰 **انتقال به {target_user['first_name']}**\n\n"
    text += f"👤 کاربر: {target_user['first_name']}\n"
    text += f"💰 موجودی فعلی: {target_user['balance']:,}\n\n"
    text += "مبلغ را انتخاب کنید:\n"
    
    keyboard = [
        [InlineKeyboardButton("💰 50,000", callback_data="transfer_amount_50000")],
        [InlineKeyboardButton("💰 100,000", callback_data="transfer_amount_100000")],
        [InlineKeyboardButton("💰 200,000", callback_data="transfer_amount_200000")],
        [InlineKeyboardButton("💰 500,000", callback_data="transfer_amount_500000")],
        [InlineKeyboardButton("💰 1,000,000", callback_data="transfer_amount_1000000")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="admin_transfer")],
    ]
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def process_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش انتقال اعتبار"""
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    target_id = context.user_data.get('transfer_target')
    if not target_id:
        await q.edit_message_text("❌ خطا! دوباره تلاش کنید.")
        return
    
    amount = int(q.data.split('_')[2])
    target_user = db.get_user(target_id)
    
    if not target_user:
        await q.edit_message_text("❌ کاربر یافت نشد!")
        return
    
    db.update_balance(target_id, amount, f'انتقال از ادمین: {amount:,} میوپوینت')
    
    text = f"✅ **انتقال اعتبار انجام شد!**\n\n"
    text += f"👤 کاربر: {target_user['first_name']}\n"
    text += f"💰 مبلغ: {amount:,} میوپوینت\n"
    text += f"💎 موجودی جدید: {db.get_balance(target_id):,}"
    
    await q.edit_message_text(text)
    
    try:
        await context.bot.send_message(
            target_id,
            f"💰 {amount:,} میوپوینت به حساب شما واریز شد!\n"
            f"💎 موجودی جدید: {db.get_balance(target_id):,}"
        )
    except:
        pass
    
    context.user_data.pop('transfer_target', None)

# ==================== آمار کاربران ====================
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    users = db.get_all_users()
    total_users = len(users)
    total_balance = sum(user[3] for user in users)
    total_referrals = sum(user[4] for user in users)
    
    text = f"📊 **آمار کلی**\n\n"
    text += f"👥 تعداد کل کاربران: {total_users} نفر\n"
    text += f"💰 کل موجودی: {total_balance:,} میوپوینت\n"
    text += f"👥 کل زیرمجموعه‌ها: {total_referrals} نفر\n\n"
    
    sorted_users = sorted(users, key=lambda x: x[3], reverse=True)[:5]
    if sorted_users:
        text += "🏆 **۵ کاربر برتر**\n"
        for i, user in enumerate(sorted_users, 1):
            text += f"{i}. {user[2]} - {user[3]:,} میوپوینت\n"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت به پنل", callback_data="admin_panel")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== درخواست‌های برداشت ====================
async def admin_withdraws(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    q = update.callback_query
    await q.answer()
    
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("❌ شما ادمین نیستید!")
        return
    
    req_id = int(q.data.split('_')[2])
    
    pending = db.get_withdraw_requests('pending')
    req = next((r for r in pending if r[0] == req_id), None)
    
    if not req:
        await q.edit_message_text("❌ این درخواست قبلاً پردازش شده!")
        return
    
    req_id, user_id, amount, date = req
    
    db.update_withdraw_status(req_id, 'approved')
    
    user = db.get_user(user_id)
    name = user['first_name'] if user else f"کاربر {user_id}"
    
    text = f"✅ درخواست برداشت تایید شد!\n\n"
    text += f"👤 {name}\n"
    text += f"💰 {amount:,} میوپوینت\n"
    
    await q.edit_message_text(text)
    
    try:
        await context.bot.send_message(
            user_id,
            f"✅ درخواست برداشت {amount:,} میوپوینت شما تایید شد!\nبه زودی پرداخت خواهد شد."
        )
    except:
        pass

# ==================== پیام همگانی ====================
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    await q.edit_message_text(
        "📢 **ارسال پیام همگانی**\n\n"
        "پیام خود را بنویسید.\n"
        "برای لغو: /cancel"
    )
    context.user_data['admin_mode'] = 'broadcast'

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ شما ادمین نیستید!")
        return
    
    if update.message.text == "/cancel":
        await update.message.reply_text("❌ عملیات لغو شد!")
        context.user_data.pop('admin_mode', None)
        await admin_menu(update, context)
        return
    
    users = db.get_all_users()
    await update.message.reply_text(f"📤 در حال ارسال پیام به {len(users)} کاربر...")
    
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
    
    text = f"👥 **زیرمجموعه‌گیری**\n\n"
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
    
    text = f"💰 **کیف پول**\n\n"
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
        text = "📊 **آخرین تراکنش‌ها**\n\n"
        for t in txs:
            emoji = "➕" if t[0] > 0 else "➖"
            text += f"{emoji} {t[0]:+,} - {t[1]}\n   📅 {t[2]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="wallet")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def withdraw_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = db.get_user(q.from_user.id)
    
    text = f"💳 **برداشت**\n\n💰 موجودی: {user['balance']:,} میوپوینت\n\nمبلغ رو انتخاب کن:\n"
    
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
    db.add_withdraw_request(q.from_user.id, amount)
    
    text = f"✅ **برداشت موفق!**\n\n"
    text += f"💰 {amount:,} میوپوینت برداشت شد.\n"
    text += f"💎 موجودی جدید: {db.get_user(q.from_user.id)['balance']:,}\n\n"
    text += "📝 درخواست شما ثبت شد و پس از تایید ادمین پرداخت می‌شود."
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data="user_menu")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
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
    
    text = f"📊 **اطلاعات من**\n\n"
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

# ==================== بررسی عضویت با دکمه ====================
async def check_membership_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    
    if await check_membership(user_id, context):
        await q.edit_message_text("✅ عضویت شما در همه کانال‌ها تایید شد!")
        if not db.get_user(user_id):
            db.add_user(user_id, q.from_user.username, q.from_user.first_name)
        await user_menu(update, context)
    else:
        await q.answer("❌ هنوز در همه کانال‌ها عضو نشدی!", show_alert=True)

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
    elif data.startswith("transfer_user_"):
        await transfer_amount(update, context)
    elif data.startswith("transfer_amount_"):
        await process_transfer(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_withdraws":
        await admin_withdraws(update, context)
    elif data.startswith("approve_withdraw_"):
        await approve_withdraw(update, context)
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

# ==================== مدیریت پیام‌ها ====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('admin_mode') == 'broadcast' and user_id == ADMIN_ID:
        await handle_broadcast(update, context)
        return
    
    if text == "/start":
        await start(update, context)
    elif text == "/cancel":
        context.user_data.pop('admin_mode', None)
        await update.message.reply_text("✅ عملیات لغو شد!")
        if user_id == ADMIN_ID:
            await admin_menu(update, context)
        else:
            await user_menu(update, context)
    else:
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید.")

# ==================== اجرا ====================
def main():
    print("=" * 60)
    print("🌟 ربات خفن - نسخه حرفه‌ای با چند کانال")
    print("=" * 60)
    print(f"📢 کانال‌ها: {REQUIRED_CHANNELS}")
    print(f"👑 آیدی ادمین: {ADMIN_ID}")
    print("=" * 60)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("✅ ربات با موفقیت روشن شد!")
    print("📱 به ربات خود بروید و /start بزنید")
    print("=" * 60)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
