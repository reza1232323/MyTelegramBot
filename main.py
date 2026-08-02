import logging
import random
import time
import asyncio
from datetime import datetime, timedelta
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
    CallbackQuery,
)
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import config
import database as db
from handlers import admin, economy, pet

# مقدار پاداش دعوت (سکه/پوینت)
REFERRAL_REWARD = 500

# ----------------- تنظیمات کانال‌های عضویت اجباری -----------------
REQUIRED_CHANNELS = [
    {
        "name": "کانال اصلی",
        "username": "@CODMSAOPZX",
        "url": "https://t.me/CODMSAOPZX",
    },
    {
        "name": "کانال دوم",
        "username": "@esmok_shop_poy",
        "url": "https://t.me/esmok_shop_poy",
    },
]

logging.basicConfig(level=logging.INFO)

# ==================== دیکشنری گردونه شانس ====================
user_last_spin = {}
SPIN_COOLDOWN = 12 * 3600

SPIN_PRIZES = [
    {"amount": 100, "weight": 35},
    {"amount": 200, "weight": 30},
    {"amount": 300, "weight": 25},
    {"amount": 500, "weight": 15},
    {"amount": 1000, "weight": 10},
    {"amount": 2000, "weight": 7},
    {"amount": 5000, "weight": 4},
    {"amount": 10000, "weight": 2},
    {"amount": 50000, "weight": 1},
    {"amount": 100000, "weight": 0.5},
    {"gem": 1, "weight": 0.01},
]

# ==================== دیکشنری انتقال‌های در انتظار ====================
pending_transfers = {}

# ==================== دیکشنری اسپم هاپ ====================
hop_spam = {}

# ==================== قیمت‌های بازار ====================
market_prices = {
    "clothes": {
        "base_price": 50,
        "min_price": 40,
        "max_price": 60,
        "buy_price": 50,
        "last_update": 0,
        "sales_count": 0
    },
    "food": {
        "base_price": 95,
        "min_price": 70,
        "max_price": 120,
        "buy_price": 100,
        "last_update": 0,
        "sales_count": 0
    },
    "toy": {
        "base_price": 32,
        "min_price": 25,
        "max_price": 40,
        "buy_price": 30,
        "last_update": 0,
        "sales_count": 0
    },
    "house": {
        "base_price": 1100,
        "min_price": 800,
        "max_price": 1500,
        "buy_price": 1000,
        "last_update": 0,
        "sales_count": 0
    },
}

def get_spin_prize():
    weights = [p["weight"] for p in SPIN_PRIZES]
    selected = random.choices(SPIN_PRIZES, weights=weights, k=1)[0]
    
    if "gem" in selected:
        return {"type": "gem", "amount": selected["gem"]}
    else:
        return {"type": "point", "amount": selected["amount"]}

def update_market_prices():
    current_time = time.time()
    for product, data in market_prices.items():
        if current_time - data["last_update"] >= 3600:
            sales = data["sales_count"]
            if sales > 10:
                price_change = -data["buy_price"] * 0.08
            elif sales > 5:
                price_change = -data["buy_price"] * 0.04
            elif sales == 0:
                price_change = data["buy_price"] * 0.08
            else:
                price_change = data["buy_price"] * 0.02
            new_price = data["base_price"] + price_change
            new_price = max(data["min_price"], min(data["max_price"], new_price))
            data["base_price"] = round(new_price)
            data["sales_count"] = 0
            data["last_update"] = current_time

def get_product_price(product_code):
    update_market_prices()
    return market_prices.get(product_code, {}).get("base_price", 0)

def record_sale(product_code):
    if product_code in market_prices:
        market_prices[product_code]["sales_count"] += 1


# ==================== سیستم زندان ====================
def is_user_in_jail(user_id):
    jail_until = db.get_user_field(user_id, "jail_until")
    if jail_until:
        try:
            jail_time = datetime.strptime(jail_until, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < jail_time:
                return True, jail_time
        except:
            pass
    db.update_field(user_id, "in_jail", 0, relative=False)
    db.update_field(user_id, "jail_until", None, relative=False)
    db.update_field(user_id, "jail_reason", None, relative=False)
    return False, None

def put_user_in_jail(user_id, minutes=15, reason="قاچاق"):
    jail_until = datetime.now() + timedelta(minutes=minutes)
    db.update_field(user_id, "in_jail", 1, relative=False)
    db.update_field(user_id, "jail_until", jail_until.strftime("%Y-%m-%d %H:%M:%S"), relative=False)
    db.update_field(user_id, "jail_reason", reason, relative=False)
    return jail_until

def release_from_jail(user_id):
    db.update_field(user_id, "in_jail", 0, relative=False)
    db.update_field(user_id, "jail_until", None, relative=False)
    db.update_field(user_id, "jail_reason", None, relative=False)

def check_hop_spam(user_id):
    now = time.time()
    if user_id not in hop_spam:
        hop_spam[user_id] = []
    
    hop_spam[user_id].append(now)
    hop_spam[user_id] = [t for t in hop_spam[user_id] if now - t <= 10]
    
    if len(hop_spam[user_id]) >= 6:
        hop_spam[user_id] = []
        return True
    return False


# ==================== دستور زندان ====================
async def jail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    in_jail, jail_until = is_user_in_jail(user_id)
    
    if not in_jail:
        await update.message.reply_text(
            "🔓 **شما در زندان نیستید!**\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ وضعیت شما: آزاد\n"
            "📍 میتوانید از تمام بخش‌های ربات استفاده کنید.\n\n"
            "⚠️ هشدار: قاچاق و اسپم کردن باعث زندان میشود!"
        )
        return
    
    remaining = jail_until - datetime.now()
    minutes = remaining.seconds // 60
    seconds = remaining.seconds % 60
    
    reason = db.get_user_field(user_id, "jail_reason") or "نامشخص"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💰 پرداخت ۲۰,۰۰۰ جریمه و آزادی",
                callback_data=f"jail_pay_{user_id}",
                style="success"
            ),
        ],
        [
            InlineKeyboardButton(
                "⏳ ماندن در زندان",
                callback_data=f"jail_stay_{user_id}",
                style="danger"
            )
        ]
    ])
    
    text = (
        f"🔒 **شما در زندان هستید!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ دلیل: {reason}\n"
        f"⏱ زمان باقیمانده: {minutes} دقیقه و {seconds} ثانیه\n\n"
        f"برای آزادی، یکی از گزینه‌های زیر را انتخاب کنید:\n"
        f"💰 پرداخت ۲۰,۰۰۰ هاپ و آزادی فوری\n"
        f"⏳ صبر کردن تا پایان زمان زندان"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def jail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    parts = data.split("_")
    owner_id = int(parts[2])
    
    if user_id != owner_id:
        await query.answer("❌ این پنل برای شما نیست!", show_alert=True)
        await query.message.reply_text(
            f"⛔️ **دسترسی غیرمجاز!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"این پنل مخصوص {query.message.chat.first_name} است.\n"
            f"شما نمی‌توانید از این پنل استفاده کنید."
        )
        return
    
    if data.startswith("jail_pay_"):
        user_points = db.get_user_field(user_id, "points") or 0
        
        if user_points < 20000:
            await query.message.reply_text(
                f"❌ **موجودی کافی نیست!**\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 موجودی شما: {user_points:,} هاپ\n"
                f"💰 جریمه: ۲۰,۰۰۰ هاپ\n\n"
                f"برای آزادی باید ۲۰,۰۰۰ هاپ داشته باشید."
            )
            return
        
        db.update_field(user_id, "points", -20000, relative=True)
        release_from_jail(user_id)
        
        await query.message.edit_text(
            f"✅ **شما آزاد شدید!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 جریمه پرداخت شده: ۲۰,۰۰۰ هاپ\n"
            f"🔓 وضعیت: آزاد\n\n"
            f"دیگر در زندان نیستید. از ربات استفاده کنید!"
        )
        
    elif data.startswith("jail_stay_"):
        in_jail, jail_until = is_user_in_jail(user_id)
        if not in_jail:
            await query.message.edit_text("✅ شما قبلاً آزاد شده‌اید!")
            return
        
        remaining = jail_until - datetime.now()
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        
        await query.message.edit_text(
            f"⏳ **شما تصمیم به ماندن در زندان گرفتید.**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏱ زمان باقیمانده: {minutes} دقیقه و {seconds} ثانیه\n\n"
            f"پس از پایان زمان، به طور خودکار آزاد خواهید شد.\n"
            f"برای اطلاع از وضعیت، دوباره `زندان` را وارد کنید."
        )


# ----------------- توابع عضویت اجباری -----------------
async def check_user_membership(bot, user_id: int) -> bool:
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(
                chat_id=ch["username"], user_id=user_id
            )
            if member.status in ["left", "kicked"]:
                return False
        except BadRequest:
            continue
        except Exception as e:
            logging.error(f"خطا در بررسی عضویت کانال {ch['username']}: {e}")
            return False
    return True


def get_join_keyboard():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append(
            [
                InlineKeyboardButton(
                    f"عضویت در {ch['name']}",
                    callback_data=f"channel_{ch['username']}",
                    style="danger"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                "عضو شدم، بررسی کن!",
                callback_data="check_join_status",
                style="success"
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def send_must_join_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    channels_list = "\n".join([f"• {ch['name']}" for ch in REQUIRED_CHANNELS])

    text = (
        f"⛔️ عزیز {user_first_name}!\n\n"
        f"برای استفاده از ربات هاپ‌داگ، ابتدا باید عضو این کانال‌ها بشی:\n\n"
        f"{channels_list}\n\n"
        f"👇 روی دکمه‌ها کلیک کن، عضو بشو، بعد «عضو شدم» رو بزن:"
    )

    if update.message:
        await update.message.reply_text(text, parse_mode=None, reply_markup=get_join_keyboard())
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=None, reply_markup=get_join_keyboard())


# ----------------- سیستم محاسباتی هاپ -----------------
def hops_needed_for_level(level):
    return 10 + (level - 1) * 5


def calculate_hop_reward(level):
    base_min = 10 * (1.5 ** (level - 1))
    base_max = 25 * (1.5 ** (level - 1))
    return random.randint(int(base_min), int(base_max))


# ==================== لیدربرد ====================
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id, username, points, level 
        FROM users 
        ORDER BY points DESC 
        LIMIT 10
    """)
    top_users = cursor.fetchall()
    
    cursor.execute("""
        SELECT COUNT(*) + 1 
        FROM users 
        WHERE points > (SELECT COALESCE(points, 0) FROM users WHERE user_id = ?)
    """, (user_id,))
    rank_result = cursor.fetchone()
    user_rank = rank_result[0] if rank_result and rank_result[0] else 1
    
    cursor.execute("""
        SELECT user_id, username, points, level 
        FROM users 
        WHERE user_id = ?
    """, (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if not top_users:
        await update.message.reply_text("📊 هنوز کاربری در سیستم ثبت‌نام نکرده است!")
        return

    text = "🏆 لیدربرد برترین های هاپو 🏆\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"

    medals = ["🥇", "🥈", "🥉"]

    for i, user in enumerate(top_users, 1):
        user_id_db, username, points, level = user
        medal = medals[i-1] if i <= 3 else f"{i}."
        name = username or f"کاربر {user_id_db}"
        text += f"{medal} {name}\n"
        text += f"   💰 {points:,} هاپو | سطح {level}\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"

    if user_data:
        user_points = user_data[2] if user_data[2] else 0
        user_level = user_data[3] if user_data[3] else 1
        text += f"\n📊 رتبه شما: #{user_rank}\n"
        text += f"   💰 {user_points:,} هاپو | سطح {user_level}"

    await update.message.reply_text(text, parse_mode=None)


# ==================== انبار ====================
async def warehouse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            inventory_clothes, inventory_food, inventory_toy, inventory_house,
            inventory_cig, inventory_diamond, inventory_gold, inventory_car,
            points, level
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ کاربر پیدا نشد!")
        return
    
    clothes, food, toy, house, cig, diamond, gold, car, points, level = result
    
    text = (
        f"📦 انبار شما\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 هاپو پوینت: {points:,} | سطح {level}\n\n"
        f"محصولات کارخانه:\n"
        f"👕 لباس هاپویی: {clothes} عدد\n"
        f"🦴 غذای ویژه: {food} عدد\n"
        f"🎾 توپ بازی: {toy} عدد\n"
        f"🏠 لانه شیک: {house} عدد\n\n"
        f"محصولات قاچاق:\n"
        f"🚬 سیگار قاچاق: {cig} عدد\n"
        f"💎 الماس سیاه: {diamond} عدد\n"
        f"🪙 شمش طلا: {gold} عدد\n"
        f"🏎 خودروی قاچاق: {car} عدد"
    )
    
    await update.message.reply_text(text, parse_mode=None)


# ==================== فروش محصولات ====================
async def sell_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT inventory_clothes, inventory_food, inventory_toy, inventory_house 
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ کاربر پیدا نشد!")
        return
    
    clothes, food, toy, house = result
    
    update_market_prices()
    
    price_clothes = get_product_price("clothes")
    price_food = get_product_price("food")
    price_toy = get_product_price("toy")
    price_house = get_product_price("house")
    
    buy_clothes = market_prices["clothes"]["buy_price"]
    buy_food = market_prices["food"]["buy_price"]
    buy_toy = market_prices["toy"]["buy_price"]
    buy_house = market_prices["house"]["buy_price"]
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"لباس ({clothes} عدد) - {price_clothes} هاپ", 
            callback_data=f"sell_clothes_flex"
        )],
        [InlineKeyboardButton(
            f"غذا ({food} عدد) - {price_food} هاپ", 
            callback_data=f"sell_food_flex"
        )],
        [InlineKeyboardButton(
            f"توپ ({toy} عدد) - {price_toy} هاپ", 
            callback_data=f"sell_toy_flex"
        )],
        [InlineKeyboardButton(
            f"لانه ({house} عدد) - {price_house} هاپ", 
            callback_data=f"sell_house_flex"
        )],
        [InlineKeyboardButton("بازگشت", callback_data="back_from_sell")]
    ])
    
    text = (
        f"💰 بازار فروش محصولات\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"قیمت‌های لحظه‌ای:\n"
        f"👕 لباس: {price_clothes} هاپ (خرید: {buy_clothes} هاپ)\n"
        f"🦴 غذا: {price_food} هاپ (خرید: {buy_food} هاپ)\n"
        f"🎾 توپ: {price_toy} هاپ (خرید: {buy_toy} هاپ)\n"
        f"🏠 لانه: {price_house} هاپ (خرید: {buy_house} هاپ)\n\n"
        f"موجودی انبار شما:\n"
        f"👕 لباس: {clothes} عدد\n"
        f"🦴 غذا: {food} عدد\n"
        f"🎾 توپ: {toy} عدد\n"
        f"🏠 لانه: {house} عدد\n\n"
        f"نکته: قیمت‌ها هر ساعت بر اساس میزان فروش تغییر میکنند!"
    )
    
    await update.message.reply_text(text, parse_mode=None, reply_markup=keyboard)


async def sell_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    product_type = data.replace("sell_", "").replace("_flex", "")
    
    field_name = f"inventory_{product_type}"
    current_count = db.get_user_field(user_id, field_name) or 0
    
    if current_count <= 0:
        await query.message.reply_text("❌ شما هیچ محصولی برای فروش ندارید!")
        return
    
    price = get_product_price(product_type)
    record_sale(product_type)
    
    db.update_field(user_id, field_name, -1, relative=True)
    db.update_field(user_id, "points", price, relative=True)
    
    new_count = db.get_user_field(user_id, field_name) or 0
    new_points = db.get_user_field(user_id, "points") or 0
    
    product_names = {
        "clothes": "لباس",
        "food": "غذا",
        "toy": "توپ",
        "house": "لانه"
    }
    
    await query.message.reply_text(
        f"✅ فروش موفق!\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"محصول: {product_names.get(product_type, product_type)}\n"
        f"💰 قیمت فروش: {price} هاپ\n"
        f"📊 موجودی باقی‌مانده: {new_count} عدد\n"
        f"💰 موجودی کیف: {new_points:,} هاپ"
    )


# ==================== گردونه شانس ====================
async def spin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    now = time.time()

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    last_spin = user_last_spin.get(user_id, 0)
    if now - last_spin < SPIN_COOLDOWN:
        remaining = int(SPIN_COOLDOWN - (now - last_spin))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ هنوز {hours} ساعت و {minutes} دقیقه مونده تا گردونه بعدی!"
        )
        return

    user_last_spin[user_id] = now

    msg = await update.message.reply_text(
        "🎡 گردونه در حال چرخش...",
        reply_to_message_id=update.message.message_id
    )

    steps = [
        "🎡 گردونه در حال چرخش...",
        "🎡 چرخش ادامه داره...",
        "🎡 تقریباً ایستاد...",
        "🎡 لحظاتی دیگر...",
    ]

    for step in steps:
        await asyncio.sleep(0.8)
        try:
            await msg.edit_text(step)
        except:
            pass

    prize = get_spin_prize()
    
    if prize["type"] == "gem":
        db.update_field(user_id, "hop_gem", prize["amount"], relative=True)
        new_gem = db.get_user_field(user_id, "hop_gem") or 0
        final_text = (
            f"🎉 **تبریک!**\n"
            f"💎 شما **{prize['amount']}** جم برنده شدید!\n"
            f"✨ این یک جایزه نادر است!\n\n"
            f"📊 جم شما: {new_gem:,}\n"
            f"⏳ گردونه بعدی: ۱۲ ساعت دیگر"
        )
    else:
        db.update_field(user_id, "points", prize["amount"], relative=True)
        new_points = db.get_user_field(user_id, "points") or 0
        final_text = (
            f"🎉 **تبریک!**\n"
            f"💰 شما **{prize['amount']:,}** هاپ پوینت برنده شدید!\n\n"
            f"📊 هاپ پوینت شما: {new_points:,}\n"
            f"⏳ گردونه بعدی: ۱۲ ساعت دیگر"
        )
    
    await msg.edit_text(final_text, parse_mode=None)


# ==================== تبدیل جم به هاپ پوینت ====================
async def convert_gem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبدیل جم به هاپ پوینت (هر ۱ جم = ۱۰,۰۰۰,۰۰۰ هاپ پوینت)"""
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ **فرمت اشتباه!**\n\n"
            "فرمت صحیح:\n"
            "`تبدیل جم [تعداد]`\n\n"
            "مثال: `تبدیل جم 5`\n\n"
            "📊 هر ۱ جم = ۱۰,۰۰۰,۰۰۰ هاپ پوینت"
        )
        return
    
    amount_str = parts[2]
    
    persian_to_english = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    
    for persian, english in persian_to_english.items():
        amount_str = amount_str.replace(persian, english)
    
    amount_str = amount_str.replace(",", "").replace(" ", "").replace("٬", "")
    
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text(
            f"❌ **تعداد جم باید عدد باشد!**\n\n"
            f"مثال: `تبدیل جم 5`\n"
            f"یا `تبدیل جم ۱۰` (اعداد فارسی)"
        )
        return
    
    if amount <= 0:
        await update.message.reply_text("❌ تعداد جم باید بیشتر از صفر باشد!")
        return
    
    user_gem = db.get_user_field(user_id, "hop_gem") or 0
    
    if user_gem < amount:
        await update.message.reply_text(
            f"❌ **جم کافی ندارید!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💎 جم شما: {user_gem:,}\n"
            f"💎 جم مورد نیاز: {amount:,}"
        )
        return
    
    hop_amount = amount * 10_000_000
    
    db.update_field(user_id, "hop_gem", -amount, relative=True)
    db.update_field(user_id, "points", hop_amount, relative=True)
    
    new_gem = db.get_user_field(user_id, "hop_gem") or 0
    new_points = db.get_user_field(user_id, "points") or 0
    
    await update.message.reply_text(
        f"✅ **تبدیل انجام شد!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 جم تبدیل شده: {amount:,}\n"
        f"💰 هاپ پوینت دریافت شده: {hop_amount:,}\n\n"
        f"📊 موجودی جدید:\n"
        f"💎 جم: {new_gem:,}\n"
        f"💰 هاپ پوینت: {new_points:,}"
    )


# ==================== انتقال هاپ پوینت ====================
async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ فرمت اشتباه!\n\n"
            "برای انتقال هاپ پوینت، روی پیام کاربر ریپلای کنید و بنویسید:\n"
            "انتقال هاپ پوینت [مبلغ]\n\n"
            "مثال: انتقال هاپ پوینت 100"
        )
        return
    
    parts = update.message.text.split()
    if len(parts) < 4:
        await update.message.reply_text(
            "❌ فرمت اشتباه!\n\n"
            "فرمت صحیح:\n"
            "انتقال هاپ پوینت [مبلغ]\n\n"
            "مثال: انتقال هاپ پوینت 100"
        )
        return
    
    if parts[0] != "انتقال" or parts[1] != "هاپ" or parts[2] != "پوینت":
        await update.message.reply_text(
            "❌ فرمت اشتباه!\n\n"
            "فرمت صحیح:\n"
            "انتقال هاپ پوینت [مبلغ]\n\n"
            "مثال: انتقال هاپ پوینت 100"
        )
        return
    
    amount_str = parts[3]
    
    persian_to_english = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
    }
    
    for persian, english in persian_to_english.items():
        amount_str = amount_str.replace(persian, english)
    
    amount_str = amount_str.replace(",", "").replace(" ", "")
    
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text(
            "❌ مبلغ باید عدد باشد!\n\n"
            "مثال: انتقال هاپ پوینت 100\n"
            "یا انتقال هاپ پوینت ۱,۰۰۰"
        )
        return
    
    if amount <= 0:
        await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد!")
        return
    
    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name
    target_username = update.message.reply_to_message.from_user.username
    
    if target_id == user_id:
        await update.message.reply_text("❌ نمی‌توانید به خودتان انتقال دهید!")
        return
    
    sender_data = db.get_user(user_id)
    sender_points = sender_data[2] if sender_data[2] else 0
    sender_name = update.effective_user.first_name
    
    if sender_points < amount:
        await update.message.reply_text(
            f"❌ موجودی کافی نیست!\n"
            f"💰 موجودی شما: {sender_points:,} هاپ پوینت"
        )
        return
    
    target_data = db.get_user(target_id)
    if not target_data:
        await update.message.reply_text("❌ کاربر مورد نظر در ربات ثبت‌نام نکرده است!")
        return
    
    transfer_id = f"{user_id}_{target_id}_{int(time.time())}"
    
    pending_transfers[transfer_id] = {
        "sender_id": user_id,
        "target_id": target_id,
        "amount": amount,
        "sender_name": sender_name,
        "target_name": target_name,
        "target_username": target_username,
        "sender_points": sender_points,
        "target_points": target_data[2] if target_data[2] else 0,
        "status": "pending"
    }
    
    target_display = f"@{target_username}" if target_username else target_name
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "تایید و ارسال",
                callback_data=f"transfer_accept_{transfer_id}",
                style="success"
            ),
            InlineKeyboardButton(
                "لغو",
                callback_data=f"transfer_reject_{transfer_id}",
                style="danger"
            )
        ]
    ])
    
    await update.message.reply_text(
        f"📨 تایید انتقال هاپ پوینت\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: {amount:,} هاپ پوینت\n"
        f"👤 به: {target_display}\n"
        f"📊 موجودی شما: {sender_points:,} هاپ پوینت\n"
        f"📊 موجودی پس از انتقال: {sender_points - amount:,} هاپ پوینت\n\n"
        f"⚠️ لطفا تایید یا لغو کنید:",
        parse_mode=None,
        reply_markup=keyboard,
        reply_to_message_id=update.message.message_id
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"📨 درخواست دریافت هاپ پوینت\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 از طرف: {sender_name}\n"
                f"💰 مبلغ: {amount:,} هاپ پوینت\n\n"
                f"⏳ در انتظار تایید فرستنده..."
            ),
            parse_mode=None
        )
    except Exception:
        pass


async def transfer_accept(callback: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    transfer_id = callback.data.replace("transfer_accept_", "")
    transfer = pending_transfers.get(transfer_id)
    
    if not transfer:
        await callback.answer("❌ درخواست منقضی شده است!", show_alert=True)
        await callback.message.edit_text("❌ این درخواست انتقال منقضی شده است.")
        return
    
    if transfer["status"] != "pending":
        await callback.answer("❌ این درخواست قبلاً پردازش شده!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if user_id != transfer["sender_id"]:
        await callback.answer("❌ فقط فرستنده می‌تواند تایید کند!", show_alert=True)
        return
    
    sender_data = db.get_user(transfer["sender_id"])
    if sender_data[2] < transfer["amount"]:
        await callback.answer("❌ موجودی شما کافی نیست!", show_alert=True)
        await callback.message.edit_text(
            f"❌ انتقال ناموفق!\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 موجودی شما کافی نیست!\n"
            f"📊 موجودی: {sender_data[2]:,} هاپ پوینت"
        )
        del pending_transfers[transfer_id]
        return
    
    transfer["status"] = "completed"
    
    db.update_field(transfer["sender_id"], "points", -transfer["amount"], relative=True)
    db.update_field(transfer["target_id"], "points", transfer["amount"], relative=True)
    
    new_sender_points = transfer["sender_points"] - transfer["amount"]
    new_target_points = transfer["target_points"] + transfer["amount"]
    
    target_display = f"@{transfer['target_username']}" if transfer['target_username'] else transfer['target_name']
    
    await callback.message.edit_text(
        f"✅ انتقال با موفقیت انجام شد!\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: {transfer['amount']:,} هاپ پوینت\n"
        f"👤 به: {target_display}\n"
        f"📊 موجودی جدید شما: {new_sender_points:,} هاپ پوینت"
    )
    
    try:
        await context.bot.send_message(
            chat_id=transfer["target_id"],
            text=(
                f"✅ دریافت هاپ پوینت!\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 از طرف: {transfer['sender_name']}\n"
                f"💰 مبلغ: {transfer['amount']:,} هاپ پوینت\n"
                f"📊 موجودی جدید شما: {new_target_points:,} هاپ پوینت"
            )
        )
    except Exception:
        pass
    
    del pending_transfers[transfer_id]
    await callback.answer("✅ انتقال با موفقیت انجام شد!")


async def transfer_reject(callback: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    transfer_id = callback.data.replace("transfer_reject_", "")
    transfer = pending_transfers.get(transfer_id)
    
    if not transfer:
        await callback.answer("❌ درخواست منقضی شده است!", show_alert=True)
        await callback.message.edit_text("❌ این درخواست انتقال منقضی شده است.")
        return
    
    if transfer["status"] != "pending":
        await callback.answer("❌ این درخواست قبلاً پردازش شده!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if user_id != transfer["sender_id"]:
        await callback.answer("❌ فقط فرستنده می‌تواند لغو کند!", show_alert=True)
        return
    
    transfer["status"] = "rejected"
    
    target_display = f"@{transfer['target_username']}" if transfer['target_username'] else transfer['target_name']
    
    await callback.message.edit_text(
        f"❌ انتقال لغو شد!\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: {transfer['amount']:,} هاپ پوینت\n"
        f"👤 به: {target_display}\n\n"
        f"شما این درخواست را لغو کردید."
    )
    
    try:
        await context.bot.send_message(
            chat_id=transfer["target_id"],
            text=(
                f"❌ درخواست انتقال لغو شد!\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 از طرف: {transfer['sender_name']}\n"
                f"💰 مبلغ: {transfer['amount']:,} هاپ پوینت\n\n"
                f"فرستنده درخواست را لغو کرد."
            )
        )
    except Exception:
        pass
    
    del pending_transfers[transfer_id]
    await callback.answer("❌ انتقال لغو شد!")


# ----------------- دستورات ربات -----------------
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    bot_username = context.bot.username

    ref_count = db.get_referral_stats(user_id) if hasattr(db, "get_referral_stats") else 0
    total_earned = ref_count * REFERRAL_REWARD
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    text = (
        f"👥 سیستم دعوت و زیرمجموعه‌گیری\n\n"
        f"با دعوت دوستان خود به ربات، پاداش دریافت کنید!\n\n"
        f"🎁 پاداش هر دعوت: {REFERRAL_REWARD:,} سکه\n"
        f"📊 تعداد دعوت‌های شما: {ref_count} نفر\n"
        f"💰 مجموع درآمد از دعوت: {total_earned:,} سکه\n\n"
        f"🔗 لینک اختصاصی شما:\n"
        f"{referral_link}"
    )

    share_url = f"https://t.me/share/url?url={referral_link}&text=بیا%20تو%20این%20ربات%20باهم%20بازی%20کنیم!"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("اشتراک‌گذاری لینک", url=share_url)]
    ])

    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=None, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode=None, reply_markup=keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "کاربر"

    db.get_user(user_id, username)

    if context.args and context.args[0].isdigit():
        inviter_id = int(context.args[0])
        if hasattr(db, "set_inviter") and db.set_inviter(user_id, inviter_id):
            db.update_field(inviter_id, "points", REFERRAL_REWARD, relative=True)
            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=f"🎉 یک کاربر جدید با لینک شما وارد ربات شد!\n🎁 مبلغ {REFERRAL_REWARD:,} سکه به حساب شما اضافه شد.",
                    parse_mode=None,
                )
            except Exception:
                pass

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    main_keyboard = ReplyKeyboardMarkup(
        [
            ["پروفایل", "هاپ"],
            ["پنل سگ", "خرید سگ", "غذا"],
            ["کارخونه", "شهر"],
            ["بانک", "زیرمجموعه‌گیری"],
            ["فروش محصولات", "انبار"],
            ["تبدیل جم", "گردونه"],
            ["لیدربرد", "زندان"],
            ["راهنما"],
        ],
        resize_keyboard=True,
    )

    inline_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("دریافت لینک زیرمجموعه‌گیری", callback_data="get_referral_link")]
    ])

    start_text = (
        f"سلام {update.effective_user.first_name} عزیز!\n"
        f"به ربات خوش آمدید.\n\n"
        f"برای گرفتن لینک دعوت می‌توانید از دکمه شیشه‌ای زیر یا دکمه زیرمجموعه‌گیری در کیبورد استفاده کنید.\n\n"
        f"💎 هر ۱ جم = ۱۰,۰۰۰,۰۰۰ هاپ پوینت\n"
        f"🎡 گردونه شانس: هر ۱۲ ساعت یک بار\n"
        f"🏆 لیدربرد: مشاهده برترین‌ها\n\n"
        f"⚠️ هشدار: قاچاق و اسپم باعث زندان میشود!\n"
        f"برای انتقال هاپ پوینت، روی پیام کاربر ریپلای کنید و بنویسید:\n"
        f"انتقال هاپ پوینت [مبلغ]"
    )

    await update.message.reply_text(start_text, reply_markup=main_keyboard, parse_mode=None)
    await update.message.reply_text("منوی سریع زیرمجموعه‌گیری:", reply_markup=inline_keyboard)


# ==================== هاپ ====================
async def handle_hop_internal(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    if check_hop_spam(user_id):
        put_user_in_jail(user_id, minutes=15, reason="اسپم در هاپ (۶ بار در ۱۰ ثانیه)")
        await update.message.reply_text(
            f"🚨 **شما به دلیل اسپم به زندان افتادید!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ دلیل: اسپم در دستور هاپ\n"
            f"⏱ مدت: ۱۵ دقیقه\n\n"
            f"برای اطلاع از وضعیت، دستور `زندان` را وارد کنید."
        )
        return
    
    current_time = int(time.time())

    last_hop_time = db.get_user_field(user_id, "last_hop_time") or 0
    cooldown = 300

    if current_time - last_hop_time < cooldown:
        remaining = cooldown - (current_time - last_hop_time)
        minutes = remaining // 60
        seconds = remaining % 60
        await update.message.reply_text(
            f"⏳ سگ شما خسته است! لطفا {minutes} دقیقه و {seconds} ثانیه صبر کنید."
        )
        return

    level = db.get_user_field(user_id, "level") or 1
    progress = db.get_user_field(user_id, "level_hops_progress") or 0

    reward = calculate_hop_reward(level)
    needed = hops_needed_for_level(level)
    progress += 1

    db.update_field(user_id, "points", reward, relative=True)
    db.update_field(user_id, "hops", 1, relative=True)
    db.update_field(user_id, "last_hop_time", current_time, relative=False)

    level_up_msg = ""
    if progress >= needed:
        level += 1
        progress = 0
        db.update_field(user_id, "level", 1, relative=True)
        db.update_field(user_id, "level_hops_progress", 0, relative=False)
        level_up_msg = f"\n🎉 تبریک! شما به سطح {level} ارتقا یافتید!"
    else:
        db.update_field(user_id, "level_hops_progress", progress, relative=False)

    current_points = db.get_user_field(user_id, "points") or 0

    await update.message.reply_text(
        f"🐾 **هاپ با موفقیت انجام شد!**\n\n"
        f"👤 کاربر: {update.effective_user.first_name}\n"
        f"🎁 پاداش دریافتی: +{reward:,} دونه\n"
        f"💰 موجودی کل: {current_points:,} دونه\n"
        f"📊 پیشرفت سطح {level}: [{progress}/{needed}] هاپ{level_up_msg}\n\n"
        f"_۵ دقیقه دیگر می‌توانید دوباره هاپ بزنید._",
        parse_mode='Markdown'
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"خطایی در پردازش رخ داد: {context.error}", exc_info=context.error)


async def router_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return

    # ===== اول چک کن که کاربر در حالت تغییر نام سگ هست یا نه =====
    if hasattr(pet, "handle_dog_rename_text"):
        is_handled = await pet.handle_dog_rename_text(update, context)
        if is_handled:
            return

    context.args = text.split()[1:]

    if hasattr(economy, "handle_factory_and_smuggle_text"):
        handled = await economy.handle_factory_and_smuggle_text(update, context)
        if handled:
            return

    username = update.effective_user.username or update.effective_user.first_name
    user = db.get_user(user_id, username)
    clean_text = text.split("@")[0].lower()

    # ===== زندان =====
    if clean_text in ["زندان", "jail"]:
        await jail_command(update, context)
        return

    # ===== بررسی زندان =====
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return

    # ===== تبدیل جم =====
    if clean_text.startswith("تبدیل جم") or clean_text == "تبدیل":
        await convert_gem_command(update, context)
        return

    # ===== فروش محصولات =====
    if clean_text in ["فروش محصولات", "فروش", "بازار"]:
        await sell_products_command(update, context)
        return

    # ===== انبار =====
    if clean_text in ["انبار", "warehouse"]:
        await warehouse_command(update, context)
        return

    # ===== انتقال هاپ پوینت =====
    if clean_text.startswith("انتقال هاپ پوینت") or clean_text.startswith("انتقال"):
        await transfer_command(update, context)
        return

    # ===== گردونه شانس =====
    if clean_text in ["گردونه", "چرخونه", "گلدونه"]:
        await spin_command(update, context)
        return

    # ===== لیدربرد =====
    if clean_text in ["لیدربرد", "leaderboard"]:
        await leaderboard_command(update, context)
        return

    # ===== هاپ =====
    if clean_text in ["هاپ", "hop"]:
        await handle_hop_internal(update, context, user)
        return

    # ===== سگ (با نام) =====
    # اگه کاربر اسم سگش رو گفت، پنل سگ باز بشه
    dog_name = db.get_user_field(user_id, "dog_name")
    if dog_name and clean_text == dog_name.lower():
        await pet.show_dog_panel(update, context, user)
        return

    # ===== بقیه دستورات =====
    if clean_text in ["پروفایل", "هاپوهام", "هاپوهاش"]:
        await pet.show_profile(update, context, user)
    elif clean_text in ["پنل سگ", "سگ من", "سگ"]:
        if hasattr(pet, "show_dog_panel"):
            await pet.show_dog_panel(update, context, user)
        elif hasattr(pet, "show_profile"):
            await pet.show_profile(update, context, user)
    elif clean_text in ["راهنما", "help"]:
        await pet.show_help(update, context)
    elif clean_text in ["خرید سگ"]:
        await pet.buy_dog(update, context, user)
    elif clean_text in ["غذا"]:
        await pet.feed_dog(update, context, user)
    elif clean_text in ["زیرمجموعه‌گیری", "زیرمجموعه", "دعوت", "رفرال"]:
        await referral_command(update, context)
    elif clean_text in ["بانک"]:
        if hasattr(economy, "bank_status"):
            await economy.bank_status(update, context, user)
    elif clean_text in ["کارخونه"]:
        await economy.show_factory(update, context)
    elif clean_text in ["قاچاق", "قاچاقچی"]:
        await economy.show_contraband(update, context)
    elif clean_text.startswith("زندان"):
        if hasattr(economy, "jail_status"):
            await economy.jail_status(update, context, user)
    elif clean_text.startswith("قمار"):
        await economy.start_gamble(update, context)
    elif clean_text in ["شهر"]:
        await economy.city_status(update, context, user)
    elif clean_text.startswith("اهدا"):
        await economy.donate_city(update, context, user)
    elif user_id in config.ADMIN_IDS:
        if text.startswith("افزایش پوینت"):
            await admin.add_points(update, context)
        elif text.startswith("کاهش پوینت"):
            await admin.remove_points(update, context)
        elif text.startswith("افزایش لول"):
            await admin.add_level(update, context)
        elif text.startswith("کاهش لول"):
            await admin.remove_level(update, context)
        elif text.startswith("همگانی"):
            await admin.broadcast(update, context)
        elif text.startswith("افزایش جم"):
            await admin.add_gem(update, context)
        elif text.startswith("کاهش جم"):
            await admin.remove_gem(update, context)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # ===== زندان =====
    if data.startswith("jail_pay_") or data.startswith("jail_stay_"):
        await jail_callback(update, context)
        return

    # ===== فروش محصولات =====
    if data in ["sell_clothes_flex", "sell_food_flex", "sell_toy_flex", "sell_house_flex"]:
        await sell_product_callback(update, context)
        return

    if data == "back_from_sell":
        await query.message.delete()
        await query.answer()
        return

    # ===== انتقال =====
    if data.startswith("transfer_accept_"):
        await transfer_accept(query, context)
        return
    
    if data.startswith("transfer_reject_"):
        await transfer_reject(query, context)
        return

    # ===== کانال‌ها =====
    if data.startswith("channel_"):
        username = data.replace("channel_", "")
        for ch in REQUIRED_CHANNELS:
            if ch["username"] == username:
                try:
                    await query.message.delete()
                except Exception:
                    pass
                await query.message.reply_text(
                    f"برای عضویت در {ch['name']} روی لینک زیر کلیک کنید:\n{ch['url']}"
                )
                await query.answer()
                return
        return

    if data == "check_join_status":
        is_joined = await check_user_membership(context.bot, user_id)
        if is_joined:
            await query.answer("عضویت شما تایید شد.", show_alert=True)
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.answer("هنوز عضو نشده‌اید!", show_alert=True)
        return

    if ":" in data:
        parts = data.split(":")
        action = parts[0]
        owner_id = int(parts[1]) if parts[1].isdigit() else None
        if owner_id and user_id != owner_id:
            await query.answer("این پنل برای شما نیست!", show_alert=True)
            return
    else:
        action = data

    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await query.answer("ابتدا عضو کانال‌ها شوید!", show_alert=True)
        await send_must_join_message(update, context)
        return

    if action == "get_referral_link":
        await referral_command(update, context)
        await query.answer()
    elif action in ["fish_sell", "fish_feed"]:
        if hasattr(pet, "handle_fish_callback"):
            await pet.handle_fish_callback(update, context)
        else:
            await query.answer()
    elif action.startswith("dog_") or action.startswith("pet_") or action == "dog_panel":
        if hasattr(pet, "handle_dog_callback"):
            await pet.handle_dog_callback(update, context)
        elif hasattr(pet, "dog_callback"):
            await pet.dog_callback(update, context)
        else:
            await query.answer()
    elif action.startswith("bank_"):
        if hasattr(economy, "handle_bank_callback"):
            await economy.handle_bank_callback(update, context)
    elif action.startswith("buy_fac_") or action.startswith("fac_"):
        if hasattr(economy, "factory_callback"):
            await economy.factory_callback(update, context)
        elif hasattr(economy, "handle_factory_callback"):
            await economy.handle_factory_callback(update, context)
    elif action.startswith("select_contra_") or action in ["start_smuggling", "pay_bail"]:
        if hasattr(economy, "handle_smuggle_callback"):
            await economy.handle_smuggle_callback(update, context)
    elif action.startswith("sell_"):
        if hasattr(economy, "sell_callback"):
            await economy.sell_callback(update, context)
    elif action.startswith("join_gamble"):
        if hasattr(economy, "join_gamble_callback"):
            await economy.join_gamble_callback(update, context)


def main():
    db.init_db()

    request_config = HTTPXRequest(
        connection_pool_size=8, read_timeout=60.0, write_timeout=60.0
    )

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request_config)
        .build()
    )

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start_command))
    if hasattr(economy, "bank_status"):
        app.add_handler(CommandHandler("bank", economy.bank_status))
    app.add_handler(CommandHandler(["referral", "sub"], referral_command))
    app.add_handler(CommandHandler(["leaderboard", "liderboard"], leaderboard_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router_message))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("🤖 Bot is active...")
    app.run_polling()


if __name__ == "__main__":
    main()
