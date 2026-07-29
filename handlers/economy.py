import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# --- 🎰 قمار ساده (دستور: قمار 100) ---
async def gamble(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    wallet = db.get_user_field(user_id, "points") or 0

    if len(text) < 2:
        await update.message.reply_text("💡 روش استفاده:\n`قمار 100` یا `قمار همه`", parse_mode='Markdown')
        return

    amount_str = text[1]
    if amount_str == "همه":
        amt = wallet
    elif amount_str.isdigit():
        amt = int(amount_str)
    else:
        await update.message.reply_text("❌ مبلغ معتبر وارد کنید!")
        return

    if amt <= 0 or wallet < amt:
        await update.message.reply_text(f"❌ موجودی کافی نیست! موجودی شما: **{wallet:,}** هاپ", parse_mode='Markdown')
        return

    if random.choice([True, False]):
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"🎉 **برنده شدی!**\nمبلغ **{amt:,}** هاپ اضافه شد.", parse_mode='Markdown')
    else:
        db.update_field(user_id, "points", -amt)
        await update.message.reply_text(f"💥 **باختی!**\nمبلغ **{amt:,}** هاپ کسر شد.", parse_mode='Markdown')


# --- 🎯 بازی‌های استیکری (دستور: بازی 100) ---
async def dice_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    wallet = db.get_user_field(user_id, "points") or 0

    if len(text) < 2:
        await update.message.reply_text("💡 روش استفاده:\n`بازی 100` یا `بازی همه`", parse_mode='Markdown')
        return

    amount_str = text[1]
    amt = wallet if amount_str == "همه" else (int(amount_str) if amount_str.isdigit() else 0)

    if amt <= 0 or wallet < amt:
        await update.message.reply_text(f"❌ موجودی کافی نیست! موجودی: **{wallet:,}** هاپ", parse_mode='Markdown')
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 دارت", callback_data=f"game_dart_{amt}_{user_id}"),
            InlineKeyboardButton("🎲 تاس", callback_data=f"game_dice_{amt}_{user_id}")
        ],
        [
            InlineKeyboardButton("🎳 بولینگ", callback_data=f"game_bowling_{amt}_{user_id}"),
            InlineKeyboardButton("🏀 بسکتبال", callback_data=f"game_basketball_{amt}_{user_id}")
        ]
    ])
    await update.message.reply_text(f"🎯 **انتخاب بازی استیکری**\nمبلغ شرط: **{amt:,}** هاپ", reply_markup=keyboard, parse_mode='Markdown')


async def handle_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, game_type, amt, owner_id = query.data.split("_")
    amt, owner_id = int(amt), int(owner_id)

    if query.from_user.id != owner_id:
        await query.answer("❌ این بازی متعلق به شخص دیگری است!", show_alert=True)
        return

    await query.answer()
    emoji_map = {"dart": "🎯", "dice": "🎲", "bowling": "🎳", "basketball": "🏀"}
    target_emoji = emoji_map.get(game_type, "🎲")

    sent_msg = await query.message.edit_text(
        f"🕹 **بازی {target_emoji} آماده است!**\n\n"
        f"استیکر {target_emoji} را رو همین پیام **ریپلای** کن تا نتیجه مشخص بشه!",
        parse_mode='Markdown'
    )
    
    context.bot_data[f"game_{sent_msg.message_id}"] = {
        "user_id": owner_id,
        "amt": amt,
        "emoji": target_emoji
    }


async def process_dice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message:
        return

    reply_id = update.message.reply_to_message.message_id
    game_data = context.bot_data.get(f"game_{reply_id}")

    if not game_data or update.effective_user.id != game_data["user_id"]:
        return

    if not update.message.dice or update.message.dice.emoji != game_data["emoji"]:
        await update.message.reply_text(f"❌ لطفاً دقیقا استیکر {game_data['emoji']} را رو همان پیام ریپلای کنید!")
        return

    val = update.message.dice.value
    amt = game_data["amt"]
    user_id = game_data["user_id"]
    wallet = db.get_user_field(user_id, "points") or 0

    if wallet < amt:
        await update.message.reply_text("❌ موجودی شما کافی نیست!")
        del context.bot_data[f"game_{reply_id}"]
        return

    if val >= 4:
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"🎉 **برنده شدی!**\nامتیاز استیکر: **{val}**\nمبلغ **+{amt:,}** هاپ دریافت کردی.", parse_mode='Markdown')
    else:
        db.update_field(user_id, "points", -amt)
        await update.message.reply_text(f"💥 **باختی!**\nامتیاز استیکر: **{val}**\nمبلغ **-{amt:,}** هاپ کسر شد.", parse_mode='Markdown')

    del context.bot_data[f"game_{reply_id}"]


# --- 🏦 بانک ---
async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip() if update.message else ""
    parts = text.split()
    wallet = db.get_user_field(user_id, "points") or 0
    bank = db.get_user_field(user_id, "bank_balance") or 0

    if len(parts) >= 3 and parts[1] == "واریز":
        amt = wallet if parts[2] == "همه" else (int(parts[2]) if parts[2].isdigit() else 0)
        if amt <= 0 or wallet < amt:
            await update.message.reply_text("❌ موجودی کافی نیست!")
            return
        db.update_field(user_id, "points", -amt)
        db.update_field(user_id, "bank_balance", amt)
        await update.message.reply_text(f"✅ **{amt:,}** هاپ واریز شد.")
        return

    elif len(parts) >= 3 and parts[1] == "برداشت":
        amt = bank if parts[2] == "همه" else (int(parts[2]) if parts[2].isdigit() else 0)
        if amt <= 0 or bank < amt:
            await update.message.reply_text("❌ موجودی بانک کافی نیست!")
            return
        db.update_field(user_id, "bank_balance", -amt)
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"✅ **{amt:,}** هاپ برداشت شد.")
        return

    acc_num = db.get_or_create_account_number(user_id)
    daily_profit = int(bank * 0.03)

    msg = (
        f"🏦 **پنل بانک**\n\n"
        f"💳 **شماره حساب:** `{acc_num}`\n"
        f"💰 **موجودی بانک:** {bank:,} هاپ\n"
        f"👛 **موجودی کیف:** {wallet:,} هاپ\n\n"
        f"📈 **سود ۲۴ ساعته:** {daily_profit:,} هاپ"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ واریز", callback_data=f"bank_deposit_{user_id}"),
            InlineKeyboardButton("➖ برداشت", callback_data=f"bank_withdraw_{user_id}")
        ]
    ])
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    parts = query.data.split("_")
    action, owner_id = parts[1], int(parts[2])

    if clicker_id != owner_id:
        await query.answer("❌ این پنل متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()
    if action == "deposit":
        await query.message.reply_text("💡 دستور: `بانک واریز 100` یا `بانک واریز همه`", parse_mode='Markdown')
    elif action == "withdraw":
        await query.message.reply_text("💡 دستور: `بانک برداشت 100` یا `بانک برداشت همه`", parse_mode='Markdown')


# --- 🏭 کارخانه ---
async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    msg = "🏭 **فروشگاه خرید کارخانه**"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏭 خرید کارخانه (قیمت: ۱۰۰۰)", callback_data=f"buy_fac_main_{user_id}")]
    ])
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def my_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    fac_count = db.get_user_field(user_id, "factory_count") or 0
    await update.message.reply_text(f"🏗 **کارخانه من**\n\n🏭 تعداد کارخانه‌ها: {fac_count}")


async def handle_factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()


# --- 🕵️‍♂️ قاچاق و 🚓 زندان ---
async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    is_jail = db.get_user_field(user_id, "in_jail") or 0
    if is_jail:
        await update.message.reply_text("🚓 شما در زندان هستید! ابتدا جریمه را پرداخت کنید.")
        return

    if random.randint(1, 100) <= 40:
        db.update_field(user_id, "in_jail", 1, relative=False)
        await update.message.reply_text("🚨 **لو رفتی!** دستگیر شدی و به زندان افتادی.")
    else:
        profit = random.randint(300, 800)
        db.update_field(user_id, "points", profit)
        await update.message.reply_text(f"🎉 **قاچاق موفق!** مبلغ **{profit:,}** هاپ سود کردی.")


async def jail_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    is_jail = db.get_user_field(user_id, "in_jail") or 0
    text = update.message.text.strip() if update.message else ""

    if "پرداخت" in text or "جریمه" in text:
        if not is_jail:
            await update.message.reply_text("شما آزاد هستید!")
            return
        user_points = db.get_user_field(user_id, "points") or 0
        bail = 200
        if user_points < bail:
            await update.message.reply_text(f"❌ برای آزادی نیاز به {bail} هاپ دارید.")
            return
        db.update_field(user_id, "points", -bail)
        db.update_field(user_id, "in_jail", 0, relative=False)
        await update.message.reply_text("✅ جریمه پرداخت شد و از زندان آزاد شدید!")
        return

    status = "🔴 در زندان" if is_jail else "🟢 آزاد"
    await update.message.reply_text(f"🚓 **وضعیت زندان:** {status}\nدستور آزادی: `زندان پرداخت`")


# --- 🏙 شهر و اهدا ---
async def city_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    fund = db.get_global_field("city_fund") or 0
    await update.message.reply_text(f"🏙 **وضعیت شهر هاپو**\n\n🏦 صندوق شهر: **{fund:,}** هاپ")


async def donate_city(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip().split()
    if len(text) < 2 or not text[1].isdigit():
        await update.message.reply_text("💡 روش استفاده: `اهدا 100`", parse_mode='Markdown')
        return

    amt = int(text[1])
    wallet = db.get_user_field(user_id, "points") or 0
    if amt <= 0 or wallet < amt:
        await update.message.reply_text("❌ موجودی کافی نیست!")
        return

    db.update_field(user_id, "points", -amt)
    db.update_global_field("city_fund", amt)
    await update.message.reply_text(f"❤️ مبلغ **{amt:,}** هاپ اهدا شد.")
