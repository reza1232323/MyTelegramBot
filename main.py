import os
import time
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ========== تنظیمات ==========
# نکته امنیتی: توکن رو از متغیر محیطی بخون. اگه ست نکردی، مقدار پیش‌فرض زیر رو موقتاً بذار.
# قبل از هر چیز از BotFather یه توکن جدید بگیر چون توکن قبلی لو رفته بود.
TOKEN = "8947364142:AAFF55PYXIQrA_PrTH6ABb85bP2JLH4fPuI"
CHANNEL_ID = -1004296146485
CHANNEL_USERNAME = "@starzland_shop"
ADMIN_IDS = [5571951071, 6691993264]
BOT_USERNAME = "starzland_bot"
CARD_NUMBER = "-"
BANK_NAME = "بانک -"

# ========== لاگ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("starzland_bot")
# کم کردن نویز لاگ‌های کتابخونه‌های داخلی
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ========== قیمت‌ها ==========
PRICES = {
    "ton": 340000,
    "stars_post": 4000,
}

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


def esc_md(text):
    """
    فرار دادن کاراکترهای خاص Markdown (legacy) تا متن آزاد کاربر
    (یوزرنیم، آدرس ولت، لینک پست و ...) پیام رو خراب نکنه و باعث
    BadRequest / کرش هندلر نشه.
    """
    if text is None:
        return ""
    text = str(text)
    for ch in ['_', '*', '`', '[']:
        text = text.replace(ch, '\\' + ch)
    return text


def db_execute(query, params=(), fetch=None):
    """
    اجرای امن کوئری‌های دیتابیس با لاگ خطا، به جای پخش‌شدن exception
    خام تو کل برنامه.
    """
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
        logger.error(f"DB error | query={query} | params={params} | err={e}", exc_info=True)
        raise


async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logger.warning(f"is_member check failed for user {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in is_member for user {user_id}: {e}", exc_info=True)
        return False


def create_user(user_id, username):
    db_execute(
        'INSERT OR IGNORE INTO users (user_id, username, created_at) VALUES (?, ?, ?)',
        (user_id, username, int(datetime.now().timestamp()))
    )


def create_order(user_id, username, item_type, quantity, price, extra_info=""):
    return db_execute(
        '''INSERT INTO orders (user_id, username, item_type, quantity, price, extra_info, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, username, item_type, quantity, price, extra_info, int(datetime.now().timestamp())),
        fetch="lastrowid"
    )


def update_order_extra(order_id, extra_info):
    db_execute('UPDATE orders SET extra_info = ? WHERE id = ?', (extra_info, order_id))


def update_order_receipt(order_id, file_id):
    db_execute('UPDATE orders SET receipt_file_id = ?, status = "waiting_confirm" WHERE id = ?', (file_id, order_id))


def confirm_order(order_id):
    db_execute('UPDATE orders SET status = "confirmed" WHERE id = ?', (order_id,))


async def notify_user_error(update: Update):
    """پیام خطای عمومی و امن به کاربر، مستقل از parse_mode."""
    try:
        target = update.effective_message
        if target:
            await target.reply_text("⚠️ یه مشکلی پیش اومد. لطفاً دوباره تلاش کن یا /start رو بزن.")
    except Exception:
        pass


# ========== استارت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"/start از کاربر {user_id} (@{username})")

    try:
        # بررسی عضویت با try/except جداگانه
        try:
            is_member_flag = await is_member(user_id, context)
        except Exception as e:
            logger.error(f"خطا در بررسی عضویت کاربر {user_id}: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ ربات به کانال دسترسی ندارد! لطفاً به ادمین اطلاع دهید."
            )
            return

        if not is_member_flag:
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

        # ثبت کاربر در دیتابیس با مدیریت خطا
        try:
            create_user(user_id, username)
        except Exception as e:
            logger.error(f"خطا در ثبت کاربر {user_id} در دیتابیس: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ خطا در ثبت اطلاعات شما. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
            return

        keyboard = [
            [InlineKeyboardButton("🪙 خرید تون", callback_data="buy_ton")],
            [InlineKeyboardButton("⭐ خرید استارز", callback_data="buy_stars")],
            [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
        ]

        await update.message.reply_text(
            "🌟 *به فروشگاه استارز لند خوش آمدی!* 🌟\n\n"
            "🪙 *تون:* 340,000 تومن\n"
            "⭐ *استارز رو پست:* 4,000 تومن هر عدد\n\n"
            "👇 یکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"خطای غیرمنتظره در start برای کاربر {user_id}: {e}", exc_info=True)
        # ارسال پیام خطای اختصاصی‌تر
        await update.message.reply_text(
            "❌ خطای داخلی رخ داد. لطفاً بعداً تلاش کنید یا با پشتیبانی تماس بگیرید."
        )
# ========== تایید عضویت ==========
async def check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"چک عضویت برای کاربر {user_id}")

    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            await query.edit_message_text("✅ عضویت تایید شد! حالا /start رو بزن.")
        else:
            await query.edit_message_text(
                "❌ هنوز عضو کانال نشدی!\n\n"
                f"📢 اول در {CHANNEL_USERNAME} عضو شو، سپس دکمه تایید رو بزن."
            )
    except TelegramError as e:
        logger.error(f"خطا در check_sub: {e}")
        await query.edit_message_text(
            "❌ خطا در بررسی عضویت!\n"
            "لطفاً مطمئن شوید ربات در کانال ادمین است."
        )
    except Exception as e:
        logger.error(f"خطای غیرمنتظره در check_sub: {e}", exc_info=True)
        await query.edit_message_text("⚠️ خطایی رخ داد. لطفاً دوباره /start رو بزن.")

# ========== خرید تون ==========
async def buy_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"buy_ton توسط کاربر {user_id}")
    try:
        context.user_data['product_type'] = 'ton'
        await query.edit_message_text(
            "🪙 *خرید تون (Toncoin)*\n\n"
            "💰 هر تون = 340,000 تومن\n\n"
            "🔢 لطفاً تعداد تون مورد نظر خود را وارد کن:\n"
            "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
            "مثال: 5 یا ۵",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در buy_ton برای کاربر {user_id}: {e}", exc_info=True)


# ========== خرید استارز ==========
async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"buy_stars توسط کاربر {user_id}")
    try:
        context.user_data['product_type'] = 'stars_post'
        await query.edit_message_text(
            "⭐ *خرید استارز رو پست*\n\n"
            "💰 هر استارز = 4,000 تومن\n\n"
            "🔢 لطفاً تعداد استارز مورد نظر خود را وارد کن:\n"
            "(عدد را به فارسی یا انگلیسی وارد کن)\n\n"
            "مثال: 1 یا ۱",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در buy_stars برای کاربر {user_id}: {e}", exc_info=True)


# ========== دریافت مقدار و محاسبه قیمت ==========
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.strip()
    logger.info(f"get_amount از کاربر {user_id}: '{text}'")

    try:
        persian_to_english = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        for persian, english in persian_to_english.items():
            text = text.replace(persian, english)

        try:
            qty = float(text)
        except ValueError:
            await update.message.reply_text("❌ لطفاً فقط عدد وارد کن!")
            return

        if qty <= 0:
            await update.message.reply_text("❌ لطفاً یک عدد بزرگتر از 0 وارد کن!")
            return
        if qty > 1_000_000:
            await update.message.reply_text("❌ عدد وارد شده خیلی بزرگه، با پشتیبانی تماس بگیر.")
            return

        item_type = context.user_data.get('product_type', '')

        if item_type == "ton":
            price = int(qty * PRICES["ton"])
            item_name = f"تون ({qty})"
            extra_prompt = "🪙 لطفاً آدرس ولت (Wallet) خود را برای دریافت تون وارد کن:"
            next_step = "wallet"
        elif item_type == "stars_post":
            price = int(qty * PRICES["stars_post"])
            item_name = f"استارز رو پست ({qty})"
            extra_prompt = "📝 لطفاً لینک پست مورد نظر رو بفرست:"
            next_step = "post_link"
        else:
            await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
            return

        order_id = create_order(user_id, username, item_type, qty, price)
        context.user_data['order_id'] = order_id
        context.user_data['item_name'] = item_name
        context.user_data['price'] = price
        context.user_data['waiting_for'] = next_step

        await update.message.reply_text(
            f"📋 *{esc_md(item_name)}*\n\n"
            f"💰 مبلغ: {fmt(price)} تومن\n\n"
            f"{extra_prompt}\n\n"
            f"⚠️ این اطلاعات برای انجام سفارش ضروری است.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در get_amount برای کاربر {user_id}: {e}", exc_info=True)
        await notify_user_error(update)


# ========== دریافت اطلاعات اضافی ==========
async def get_extra_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text.strip()
    logger.info(f"get_extra_info از کاربر {user_id}: '{text}'")

    try:
        order_id = context.user_data.get('order_id')
        item_name = context.user_data.get('item_name')
        price = context.user_data.get('price')
        waiting_for = context.user_data.get('waiting_for')

        if not order_id:
            await update.message.reply_text("❌ خطا! لطفا دوباره /start رو بزن.")
            return

        if waiting_for == "wallet":
            update_order_extra(order_id, f"آدرس ولت: {text}")
        elif waiting_for == "post_link":
            update_order_extra(order_id, f"لینک پست: {text}")
        else:
            await update.message.reply_text("❌ خطا! لطفا دوباره تلاش کن.")
            return

        keyboard = [
            [InlineKeyboardButton("📋 کپی شماره کارت", callback_data="copy_card")],
            [InlineKeyboardButton("📸 ارسال رسید", callback_data=f"send_receipt_{order_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")],
        ]

        await update.message.reply_text(
            f"📋 *فاکتور شما*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 کاربر: @{esc_md(username)}\n"
            f"🛒 محصول: {esc_md(item_name)}\n"
            f"💰 مبلغ: {fmt(price)} تومن\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"📝 {esc_md(text)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💳 *شماره کارت:*\n"
            f"`{CARD_NUMBER}`\n"
            f"🏦 {BANK_NAME}\n\n"
            f"⚠️ بعد از واریز، روی 'ارسال رسید' کلیک کن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🆕 *سفارش جدید*\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 کاربر: @{esc_md(username)}\n"
                    f"🆔 آیدی: {user_id}\n"
                    f"🛒 محصول: {esc_md(item_name)}\n"
                    f"💰 مبلغ: {fmt(price)} تومن\n"
                    f"🆔 شماره سفارش: {order_id}\n"
                    f"📝 {esc_md(text)}\n"
                    f"━━━━━━━━━━━━━━━━━━━━",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"ارسال پیام سفارش جدید به ادمین {admin_id} ناموفق بود: {e}", exc_info=True)

        context.user_data['waiting_for'] = 'receipt'
    except Exception as e:
        logger.error(f"خطا در get_extra_info برای کاربر {user_id}: {e}", exc_info=True)
        await notify_user_error(update)


# ========== کپی شماره کارت ==========
async def copy_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text(
            "📋 *شماره کارت:*\n"
            f"`{CARD_NUMBER}`\n\n"
            f"🏦 {BANK_NAME}\n\n"
            "✅ کپی شد!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در copy_card: {e}", exc_info=True)


# ========== ارسال رسید ==========
async def send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        order_id = int(query.data.split('_')[2])
        context.user_data['order_id'] = order_id
        context.user_data['waiting_for'] = 'receipt'
        await query.edit_message_text(
            "📸 *ارسال رسید*\n\n"
            "💰 لطفاً عکس رسید واریزی خود را بفرستید.",
            parse_mode="Markdown"
        )
    except (IndexError, ValueError) as e:
        logger.error(f"callback_data نامعتبر در send_receipt: {query.data} | {e}")
    except Exception as e:
        logger.error(f"خطا در send_receipt: {e}", exc_info=True)


# ========== دریافت عکس رسید ==========
async def get_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"get_receipt از کاربر {user_id}")

    try:
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
                f"✅ *رسید شما دریافت شد!*\n\n"
                f"🌟 سفارش شما در چند دقیقه انجام خواهد شد.\n\n"
                f"🆔 شماره سفارش: {order_id}\n"
                f"👤 کاربر: @{esc_md(username)}\n"
                f"🛒 محصول: {esc_md(item_name)}\n"
                f"💰 مبلغ: {fmt(price)} تومن\n\n"
                f"⏳ لطفاً صبر کنید...\n"
                f"🔜 به زودی تحویل داده میشه!",
                parse_mode="Markdown"
            )

            for admin_id in ADMIN_IDS:
                try:
                    extra = db_execute(
                        'SELECT extra_info FROM orders WHERE id = ?', (order_id,), fetch="one"
                    )
                    extra_info = extra[0] if extra else ""

                    await context.bot.send_photo(
                        admin_id,
                        photo=file_id,
                        caption=f"📸 *رسید جدید*\n\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"👤 کاربر: @{esc_md(username)}\n"
                                f"🆔 آیدی: {user_id}\n"
                                f"🛒 محصول: {esc_md(item_name)}\n"
                                f"💰 مبلغ: {fmt(price)} تومن\n"
                                f"🆔 شماره سفارش: {order_id}\n"
                                f"📝 {esc_md(extra_info) if extra_info else 'ندارد'}\n"
                                f"📅 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"⬅️ بعد از انجام سفارش کلیک کن:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ انجام سفارش", callback_data=f"confirm_{order_id}")],
                            [InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject_{order_id}")]
                        ]),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error sending receipt to admin {admin_id}: {e}", exc_info=True)

            context.user_data['waiting_for'] = ''
        else:
            await update.message.reply_text("❌ لطفاً یک عکس از رسید خود بفرستید.")
    except Exception as e:
        logger.error(f"خطا در get_receipt برای کاربر {user_id}: {e}", exc_info=True)
        await notify_user_error(update)


# ========== انجام سفارش توسط ادمین ==========
async def confirm_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    logger.info(f"confirm_receipt توسط ادمین {admin_id}: {query.data}")

    try:
        if admin_id not in ADMIN_IDS:
            await query.edit_message_text("❌ شما دسترسی ندارید!", reply_markup=None)
            return

        try:
            order_id = int(query.data.split('_')[1])
        except (IndexError, ValueError):
            await query.edit_message_text("❌ داده نامعتبر!", reply_markup=None)
            return

        # حذف دکمه‌ها قبل از ادامه
        await query.edit_message_reply_markup(reply_markup=None)

        confirm_order(order_id)

        order = db_execute(
            'SELECT user_id, username, item_type, quantity, price, extra_info FROM orders WHERE id = ?',
            (order_id,), fetch="one"
        )

        if not order:
            await query.edit_message_text("❌ سفارش پیدا نشد!")
            return

        user_id, username, item_type, qty, price, extra_info = order

        try:
            await context.bot.send_message(
                user_id,
                f"✅ *سفارش شما انجام شد!*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌟 سفارش شما با موفقیت انجام شد.\n\n"
                f"🆔 شماره سفارش: {order_id}\n"
                f"🛒 محصول: {esc_md(item_type)} ({qty})\n"
                f"💰 مبلغ: {fmt(price)} تومن\n"
                f"📝 {esc_md(extra_info) if extra_info else ''}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🙏 از اعتماد شما سپاسگزاریم! 🌟",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"اطلاع‌رسانی تایید سفارش به کاربر {user_id} ناموفق بود: {e}", exc_info=True)

        # ویرایش پیام اصلی با کیبورد خالی (دکمه‌ها حذف می‌شن)
        await query.edit_message_text(
            f"✅ سفارش {order_id} انجام شد!\n\n"
            f"👤 کاربر: @{username}\n"
            f"🛒 محصول: {item_type} ({qty})\n"
            f"💰 مبلغ: {fmt(price)} تومن",
            reply_markup=None  # <--- مهم: حذف دکمه‌ها
        )
    except Exception as e:
        logger.error(f"خطا در confirm_receipt: {e}", exc_info=True)


# ========== رد سفارش توسط ادمین ==========
async def reject_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id
    logger.info(f"reject_receipt توسط ادمین {admin_id}: {query.data}")

    try:
        if admin_id not in ADMIN_IDS:
            await query.edit_message_text("❌ شما دسترسی ندارید!", reply_markup=None)
            return

        try:
            order_id = int(query.data.split('_')[1])
        except (IndexError, ValueError):
            await query.edit_message_text("❌ داده نامعتبر!", reply_markup=None)
            return

        # حذف دکمه‌ها
        await query.edit_message_reply_markup(reply_markup=None)

        order = db_execute(
            'SELECT user_id, username, item_type, quantity, price FROM orders WHERE id = ?',
            (order_id,), fetch="one"
        )

        if not order:
            await query.edit_message_text("❌ سفارش پیدا نشد!")
            return

        user_id, username, item_type, qty, price = order

        try:
            await context.bot.send_message(
                user_id,
                f"❌ * سفارش شما رد شد با پشتیبانی تماس بگیرید و در کامنت های کانال پیگیری کنید!*\n\n"
                f"🆔 شماره سفارش: {order_id}\n"
                f"🛒 محصول: {esc_md(item_type)} ({qty})\n"
                f"💰 مبلغ: {fmt(price)} تومن\n\n"
                f"⚠️ رسید ارسالی مورد تایید قرار نگرفت.\n"
                f"📸 لطفاً دوباره تلاش کنید.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"اطلاع‌رسانی رد سفارش به کاربر {user_id} ناموفق بود: {e}", exc_info=True)

        await query.edit_message_text(
            f"❌ سفارش {order_id} رد شد!",
            reply_markup=None  # <--- مهم: حذف دکمه‌ها
        )
    except Exception as e:
        logger.error(f"خطا در reject_receipt: {e}", exc_info=True)


# ========== سفارشات من ==========
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"my_orders برای کاربر {user_id}")

    try:
        orders = db_execute(
            '''SELECT id, item_type, quantity, price, status, extra_info, created_at
               FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10''',
            (user_id,), fetch="all"
        )

        if not orders:
            await query.edit_message_text("📋 هیچ سفارشی نداری!")
            return

        text = "📋 *سفارشات شما*\n\n"
        for o in orders:
            order_id, item_type, qty, price, status, extra_info, created_at = o
            if status == "confirmed":
                status_emoji = "✅"
            elif status == "waiting_confirm":
                status_emoji = "⏳"
            elif status == "pending":
                status_emoji = "🆕"
            else:
                status_emoji = "❌"
            date = datetime.fromtimestamp(created_at).strftime("%Y/%m/%d %H:%M")
            text += f"🆔 #{order_id} - {esc_md(item_type)} ({qty}) - {fmt(price)} تومن {status_emoji}\n"
            if extra_info:
                text += f"   📝 {esc_md(extra_info)}\n"
            text += f"   📅 {date}\n\n"

        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"خطا در my_orders برای کاربر {user_id}: {e}", exc_info=True)


# ========== برگشت به منو ==========
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    logger.info(f"back_to_menu برای کاربر {user_id}")

    try:
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
            "🛒 *منوی اصلی*\n\n"
            "🪙 تون: 340,000 تومن\n"
            "⭐ استارز: 4,000 تومن هر عدد\n\n"
            "👇 یکی رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در back_to_menu برای کاربر {user_id}: {e}", exc_info=True)


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
    else:
        # کاربر بدون هیچ سفارش فعالی متن فرستاده - راهنماییش کن
        await update.message.reply_text("برای شروع /start رو بزن. 🙂")


# ========== هندلر خطای سراسری ==========
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    این هندلر جلوی کرش کل ربات رو می‌گیره: هر exception ای که تو هیچ‌کدوم
    از هندلرهای بالا catch نشده باشه، اینجا لاگ میشه و به جای خاموش شدن
    ربات، فقط همون یک درخواست fail میشه.
    """
    logger.error("Exception در پردازش یک update:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ یه خطای غیرمنتظره پیش اومد. لطفاً /start رو بزن و دوباره تلاش کن."
            )
    except Exception:
        pass


# ========== اجرا ==========
def build_app():
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
    app.add_error_handler(error_handler)

    return app


def main():
    if not TOKEN or TOKEN == "PUT_YOUR_NEW_TOKEN_HERE":
        logger.error("توکن ربات ست نشده! متغیر محیطی BOT_TOKEN رو ست کن یا مقدار TOKEN رو تو کد بذار.")
        return

    # اگه ربات به هر دلیلی (قطعی شبکه، ارور غیرمنتظره و ...) کرش کنه،
    # به جای خاموش موندن، بعد از چند ثانیه دوباره بالا میاد.
    retry_delay = 5
    while True:
        try:
            app = build_app()
            logger.info("🌟 ربات استارز لند روشن شد...")
            app.run_polling(drop_pending_updates=True, close_loop=False)
            # اگه run_polling عادی (بدون خطا) برگشت، یعنی خودمون متوقفش کردیم
            break
        except Exception as e:
            logger.error(f"ربات با خطا متوقف شد: {e}", exc_info=True)
            logger.info(f"راه‌اندازی مجدد در {retry_delay} ثانیه...")
            time.sleep(retry_delay)


if __name__ == "__main__":
    main()
