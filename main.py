import os
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ========== تنظیمات ==========
TOKEN = "8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI"
CHANNEL_ID = -1004296146485  # آیدی کانال خود را وارد کنید
CHANNEL_USERNAME = "@starzland_shop"  # یوزرنیم کانال
ADMIN_IDS = [6691993264]  # آیدی ادمین‌ها
BOT_USERNAME = "starzland_bot"
REFERRAL_POINTS = 10000  # پاداش هر زیرمجموعه
MIN_WITHDRAW_DAYS = 7  # هر چند روز یک بار می‌تواند برداشت کند

# ========== لاگ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("meowearn_bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ========== دیتابیس ==========
conn = sqlite3.connect('meowearn.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        referrer_id INTEGER DEFAULT 0,
        join_date INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        wallet_address TEXT,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0,
        confirmed_at INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS last_withdraw (
        user_id INTEGER PRIMARY KEY,
        last_withdraw_date INTEGER DEFAULT 0
    )
''')
conn.commit()

# ========== توابع کمکی ==========
def fmt(n):
    return f"{n:,}"

def esc_md(text):
    if text is None:
        return ""
    text = str(text)
    for ch in ['_', '*', '`', '[']:
        text = text.replace(ch, '\\' + ch)
    return text

def db_execute(query, params=(), fetch=None):
    try:
        cursor.execute(query, params)
        conn.commit()
        if fetch == "one":
            return cursor.fetchone()
        if fetch == "all":
            return cursor.fetchall()
        if fetch == "lastrowid":
            return cursor.lastrowid
        return None
    except sqlite3.Error as e:
        logger.error(f"DB error: {e}", exc_info=True)
        raise

def get_user(user_id):
    return db_execute('SELECT * FROM users WHERE user_id = ?', (user_id,), fetch="one")

def create_user(user_id, username, first_name, referrer_id=0):
    db_execute(
        '''INSERT OR IGNORE INTO users (user_id, username, first_name, referrer_id, join_date, points)
           VALUES (?, ?, ?, ?, ?, 0)''',
        (user_id, username, first_name, referrer_id, int(datetime.now().timestamp()))
    )
    # اگر کاربر جدید از طریق لینک دعوت آمده بود، پاداش بده
    if referrer_id != 0:
        db_execute('UPDATE users SET points = points + ? WHERE user_id = ?', (REFERRAL_POINTS, referrer_id))

def add_points(user_id, amount):
    db_execute('UPDATE users SET points = points + ? WHERE user_id = ?', (amount, user_id))

def get_points(user_id):
    result = db_execute('SELECT points FROM users WHERE user_id = ?', (user_id,), fetch="one")
    return result[0] if result else 0

def get_referrals(user_id):
    result = db_execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,), fetch="one")
    return result[0] if result else 0

def get_referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start={user_id}"

def can_withdraw(user_id):
    """بررسی می‌کند که آیا کاربر می‌تواند برداشت کند (هر ۷ روز یک بار)"""
    result = db_execute('SELECT last_withdraw_date FROM last_withdraw WHERE user_id = ?', (user_id,), fetch="one")
    if not result:
        return True, 0
    last_date = result[0]
    days_passed = (datetime.now().timestamp() - last_date) / 86400
    if days_passed >= MIN_WITHDRAW_DAYS:
        return True, 0
    remaining_days = int(MIN_WITHDRAW_DAYS - days_passed) + 1
    return False, remaining_days

def update_last_withdraw(user_id):
    db_execute(
        '''INSERT OR REPLACE INTO last_withdraw (user_id, last_withdraw_date)
           VALUES (?, ?)''',
        (user_id, int(datetime.now().timestamp()))
    )

# ========== بررسی عضویت ==========
async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logger.warning(f"is_member check failed for user {user_id}: {e}")
        return False

# ========== استارت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    logger.info(f"/start از کاربر {user_id} (@{username})")

    # بررسی عضویت در کانال
    if not await is_member(user_id, context):
        keyboard = [
            [InlineKeyboardButton("📢 جوین کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ تایید عضویت", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            f"🔒 *برای استفاده از ربات، ابتدا در کانال عضو شوید:*\n\n"
            f"📢 {CHANNEL_USERNAME}\n\n"
            "بعد از عضویت، دکمه تایید رو بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # پردازش لینک دعوت (اگر کاربر از طریق لینک آمده باشد)
    referrer_id = 0
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id == user_id:
            referrer_id = 0  # نمی‌تواند خودش را دعوت کند

    # ثبت کاربر در دیتابیس
    existing_user = get_user(user_id)
    if not existing_user:
        create_user(user_id, username, first_name, referrer_id)
        if referrer_id != 0:
            logger.info(f"کاربر {user_id} توسط {referrer_id} دعوت شد")
            # اطلاع‌رسانی به دعوت‌کننده
            try:
                await context.bot.send_message(
                    referrer_id,
                    f"🎉 *یک کاربر جدید از طریق لینک دعوت شما وارد شد!*\n\n"
                    f"👤 {first_name}\n"
                    f"💰 {fmt(REFERRAL_POINTS)} میوپوینت به حساب شما اضافه شد.\n"
                    f"📊 امتیاز فعلی شما: {fmt(get_points(referrer_id))}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"خطا در ارسال پیام به {referrer_id}: {e}")

    # نمایش منوی اصلی
    points = get_points(user_id)
    referrals = get_referrals(user_id)
    join_date = datetime.fromtimestamp(existing_user[4] if existing_user else int(datetime.now().timestamp())).strftime("%Y/%m/%d")

    keyboard = [
        [InlineKeyboardButton("💰 دریافت میوپوینت رایگان", callback_data="get_points")],
        [InlineKeyboardButton("📊 اطلاعات حساب", callback_data="my_profile")],
        [InlineKeyboardButton("🔗 لینک دعوت", callback_data="referral_link")],
        [InlineKeyboardButton("💳 برداشت پوینت", callback_data="withdraw")],
    ]

    await update.message.reply_text(
        f"🌟 *به ربات میوپوینت خوش آمدید!* 🌟\n\n"
        f"👤 کاربر: @{esc_md(username) if username else first_name}\n"
        f"💰 امتیاز شما: {fmt(points)} میوپوینت\n"
        f"👥 زیرمجموعه‌ها: {referrals} نفر\n"
        f"📅 تاریخ عضویت: {join_date}\n\n"
        f"📌 با دعوت از دوستان، به ازای هر نفر {fmt(REFERRAL_POINTS)} میوپوینت دریافت کنید!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== تایید عضویت ==========
async def check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await is_member(user_id, context):
        await query.edit_message_text("✅ عضویت تایید شد! لطفاً دوباره /start رو بزن.")
    else:
        await query.edit_message_text("❌ هنوز عضو کانال نشدی!\nلطفاً اول عضو شو.")

# ========== نمایش پروفایل ==========
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if not user:
        await query.edit_message_text("❌ کاربر پیدا نشد! لطفاً /start رو بزن.")
        return

    points = get_points(user_id)
    referrals = get_referrals(user_id)
    join_date = datetime.fromtimestamp(user[4]).strftime("%Y/%m/%d %H:%M")

    text = (
        f"📊 *اطلاعات حساب کاربری*\n\n"
        f"👤 نام کاربری: @{esc_md(user[1]) if user[1] else 'ندارد'}\n"
        f"🆔 آیدی عددی: {user[0]}\n"
        f"👥 تعداد زیرمجموعه: {referrals} نفر\n"
        f"💰 امتیاز حساب: {fmt(points)} میوپوینت\n"
        f"📅 تاریخ عضویت: {join_date}"
    )

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== لینک دعوت ==========
async def referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    link = get_referral_link(user_id)
    points = get_points(user_id)
    referrals = get_referrals(user_id)

    text = (
        f"🔗 *لینک دعوت شما:*\n\n"
        f"`{link}`\n\n"
        f"📌 این لینک را برای دوستان خود بفرستید.\n"
        f"💰 به ازای هر نفر {fmt(REFERRAL_POINTS)} میوپوینت دریافت کنید!\n\n"
        f"👥 زیرمجموعه‌ها: {referrals} نفر\n"
        f"💰 امتیاز: {fmt(points)} میوپوینت"
    )

    keyboard = [
        [InlineKeyboardButton("📤 اشتراک‌گذاری لینک", url=f"https://t.me/share/url?url={link}&text=🎁 به ربات میوپوینت بپیوندید و پوینت رایگان دریافت کنید!")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== دریافت پوینت رایگان ==========
async def get_free_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # لیست مقادیر قابل انتخاب
    amounts = [120000, 150000, 180000, 210000, 240000, 270000, 300000]
    buttons = []
    for amount in amounts:
        buttons.append([InlineKeyboardButton(f"{fmt(amount)} میوپوینت", callback_data=f"select_{amount}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")])

    text = (
        "💰 *دریافت میوپوینت رایگان*\n\n"
        "از منوی زیر، مقدار میوپوینت موردنظر خود را انتخاب کنید.\n\n"
        "⚠️ لطفاً فقط یکی از گزینه‌های موجود را انتخاب کنید."
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    context.user_data['waiting_for'] = 'select_amount'

# ========== انتخاب مقدار ==========
async def select_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    try:
        amount = int(query.data.split('_')[1])
    except:
        await query.edit_message_text("❌ خطا! لطفاً دوباره تلاش کنید.")
        return

    # ذخیره مقدار انتخاب‌شده در حافظه موقت
    context.user_data['selected_amount'] = amount
    context.user_data['waiting_for'] = 'wallet_address'

    await query.edit_message_text(
        f"✅ مقدار {fmt(amount)} میوپوینت انتخاب شد.\n\n"
        f"💳 لطفاً آدرس ولت (Wallet) یا شماره کارت خود را برای دریافت پوینت وارد کنید:\n\n"
        f"⚠️ این اطلاعات برای انجام برداشت ضروری است.",
        parse_mode="Markdown"
    )

# ========== دریافت آدرس ولت و ثبت درخواست برداشت ==========
async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.strip()

    amount = context.user_data.get('selected_amount')
    if not amount:
        await update.message.reply_text("❌ خطا! لطفاً دوباره /start رو بزن.")
        return

    # بررسی اینکه آیا کاربر می‌تواند برداشت کند (هر ۷ روز یک بار)
    can_wd, days_left = can_withdraw(user_id)
    if not can_wd:
        await update.message.reply_text(
            f"⏳ شما هر {MIN_WITHDRAW_DAYS} روز یک بار می‌توانید برداشت کنید.\n"
            f"📅 {days_left} روز دیگر می‌توانید درخواست دهید."
        )
        return

    # ثبت درخواست در دیتابیس
    db_execute(
        '''INSERT INTO withdraw_requests (user_id, amount, wallet_address, created_at)
           VALUES (?, ?, ?, ?)''',
        (user_id, amount, text, int(datetime.now().timestamp()))
    )

    # به‌روزرسانی تاریخ آخرین برداشت
    update_last_withdraw(user_id)

    # ارسال پیام به کاربر
    await update.message.reply_text(
        f"✅ *درخواست برداشت شما ثبت شد!*\n\n"
        f"💰 مبلغ: {fmt(amount)} میوپوینت\n"
        f"💳 آدرس: {esc_md(text)}\n\n"
        f"⏳ درخواست شما برای بررسی به ادمین ارسال شد.\n"
        f"🔜 به زودی تأیید یا رد می‌شود.",
        parse_mode="Markdown"
    )

    # ===== ارسال به ادمین‌ها =====
    for admin_id in ADMIN_IDS:
        try:
            keyboard = [
                [InlineKeyboardButton("✅ تأیید برداشت", callback_data=f"confirm_withdraw_{user_id}_{amount}")],
                [InlineKeyboardButton("❌ رد برداشت", callback_data=f"reject_withdraw_{user_id}_{amount}")]
            ]
            await context.bot.send_message(
                admin_id,
                f"💳 *درخواست برداشت جدید*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 کاربر: @{esc_md(username)}\n"
                f"🆔 آیدی: {user_id}\n"
                f"💰 مبلغ: {fmt(amount)} میوپوینت\n"
                f"💳 آدرس: {esc_md(text)}\n"
                f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"ارسال به ادمین {admin_id} ناموفق: {e}")

    # ===== ارسال به کانال =====
    try:
        await context.bot.send_message(
            CHANNEL_ID,
            f"💳 *درخواست برداشت جدید*\n\n"
            f"👤 کاربر: @{esc_md(username)}\n"
            f"💰 مبلغ: {fmt(amount)} میوپوینت\n"
            f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"ارسال به کانال ناموفق: {e}")

    context.user_data['waiting_for'] = ''

# ========== تأیید برداشت توسط ادمین ==========
async def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی ندارید!")
        return

    try:
        _, _, user_id, amount = query.data.split('_')
        user_id = int(user_id)
        amount = int(amount)
    except:
        await query.edit_message_text("❌ داده نامعتبر!")
        return

    # کم کردن پوینت از حساب کاربر
    current_points = get_points(user_id)
    if current_points < amount:
        await query.edit_message_text(f"❌ کاربر به اندازه کافی پوینت ندارد!\nموجودی: {fmt(current_points)}")
        return

    db_execute('UPDATE users SET points = points - ? WHERE user_id = ?', (amount, user_id))

    # به‌روزرسانی وضعیت درخواست
    db_execute(
        '''UPDATE withdraw_requests SET status = 'confirmed', confirmed_at = ?
           WHERE user_id = ? AND amount = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1''',
        (int(datetime.now().timestamp()), user_id, amount)
    )

    # اطلاع‌رسانی به کاربر
    try:
        await context.bot.send_message(
            user_id,
            f"✅ *برداشت شما تأیید شد!*\n\n"
            f"💰 مبلغ: {fmt(amount)} میوپوینت\n\n"
            f"🙏 از اعتماد شما سپاسگزاریم!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"اطلاع‌رسانی به کاربر {user_id} ناموفق: {e}")

    await query.edit_message_text(f"✅ برداشت {fmt(amount)} میوپوینت برای کاربر {user_id} تأیید شد!")

# ========== رد برداشت توسط ادمین ==========
async def reject_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("❌ شما دسترسی ندارید!")
        return

    try:
        _, _, user_id, amount = query.data.split('_')
        user_id = int(user_id)
        amount = int(amount)
    except:
        await query.edit_message_text("❌ داده نامعتبر!")
        return

    # به‌روزرسانی وضعیت درخواست
    db_execute(
        '''UPDATE withdraw_requests SET status = 'rejected'
           WHERE user_id = ? AND amount = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1''',
        (user_id, amount)
    )

    # اطلاع‌رسانی به کاربر
    try:
        await context.bot.send_message(
            user_id,
            f"❌ *درخواست برداشت شما رد شد!*\n\n"
            f"💰 مبلغ: {fmt(amount)} میوپوینت\n\n"
            f"⚠️ لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"اطلاع‌رسانی به کاربر {user_id} ناموفق: {e}")

    await query.edit_message_text(f"❌ برداشت {fmt(amount)} میوپوینت برای کاربر {user_id} رد شد!")

# ========== برگشت به منو ==========
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not await is_member(user_id, context):
        await query.edit_message_text("❌ ابتدا در کانال عضو شوید!")
        return

    points = get_points(user_id)
    referrals = get_referrals(user_id)

    keyboard = [
        [InlineKeyboardButton("💰 دریافت میوپوینت رایگان", callback_data="get_points")],
        [InlineKeyboardButton("📊 اطلاعات حساب", callback_data="my_profile")],
        [InlineKeyboardButton("🔗 لینک دعوت", callback_data="referral_link")],
        [InlineKeyboardButton("💳 برداشت پوینت", callback_data="withdraw")],
    ]

    await query.edit_message_text(
        f"🌟 *منوی اصلی*\n\n"
        f"💰 امتیاز شما: {fmt(points)} میوپوینت\n"
        f"👥 زیرمجموعه‌ها: {referrals} نفر\n\n"
        f"📌 یکی از گزینه‌ها رو انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== مدیریت پیام‌ها ==========
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for = context.user_data.get('waiting_for', '')

    if waiting_for == 'wallet_address':
        await handle_wallet_address(update, context)
    else:
        await update.message.reply_text("برای شروع /start رو بزن. 🙂")

# ========== خطایاب ==========
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ یه خطای غیرمنتظره پیش اومد. لطفاً /start رو بزن."
            )
    except Exception:
        pass

# ========== اجرا ==========
def build_app():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(my_profile, pattern="^my_profile$"))
    app.add_handler(CallbackQueryHandler(referral_link, pattern="^referral_link$"))
    app.add_handler(CallbackQueryHandler(get_free_points, pattern="^get_points$"))
    app.add_handler(CallbackQueryHandler(select_amount, pattern="^select_\\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(confirm_withdraw, pattern="^confirm_withdraw_"))
    app.add_handler(CallbackQueryHandler(reject_withdraw, pattern="^reject_withdraw_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_error_handler(error_handler)

    return app

def main():
    if not TOKEN or TOKEN == "PUT_YOUR_TOKEN_HERE":
        logger.error("توکن ربات ست نشده!")
        return

    while True:
        try:
            app = build_app()
            logger.info("🌟 ربات میوپوینت روشن شد...")
            app.run_polling(drop_pending_updates=True, close_loop=False)
            break
        except Exception as e:
            logger.error(f"ربات با خطا متوقف شد: {e}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
