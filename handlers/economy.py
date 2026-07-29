import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# ==================== 🏦 بخش بانک ====================

async def bank_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    text = update.message.text.strip() if update.message else ""
    parts = text.split()
    current_user = db.get_user(user_id)
    wallet = current_user[2]
    bank = current_user[5]

    # واریز و برداشت متنی
    if len(parts) >= 3 and parts[1] == "واریز":
        amt = wallet if parts[2] == "همه" else int(parts[2])
        if amt <= 0 or wallet < amt:
            await update.message.reply_text("❌ موجودی کیف پول کافی نیست!")
            return
        db.update_field(user_id, "points", -amt)
        db.update_field(user_id, "bank_balance", amt)
        await update.message.reply_text(f"✅ مبلغ **{amt:,}** هاپ به بانک واریز شد.")
        return

    elif len(parts) >= 3 and parts[1] == "برداشت":
        amt = bank if parts[2] == "همه" else int(parts[2])
        if amt <= 0 or bank < amt:
            await update.message.reply_text("❌ موجودی بانک کافی نیست!")
            return
        db.update_field(user_id, "bank_balance", -amt)
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"✅ مبلغ **{amt:,}** هاپ برداشت شد.")
        return

    acc_num = db.get_or_create_account_number(user_id)
    daily_profit = int(bank * 0.03)

    msg = (
        f"🏦 **بانک هاپی**\n\n"
        f"💳 **شماره حساب:** `{acc_num}`\n"
        f"💰 **موجودی بانک:** {bank:,} هاپ\n"
        f"👛 **موجودی کیف:** {wallet:,} هاپ\n\n"
        f"📈 **سود روزانه (۳%):** {daily_profit:,} هاپ"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ واریز", callback_data=f"bank_deposit_help_{user_id}"),
            InlineKeyboardButton("➖ برداشت", callback_data=f"bank_withdraw_help_{user_id}")
        ],
        [
            InlineKeyboardButton("💸 دریافت سود", callback_data=f"bank_claim_profit_{user_id}")
        ],
        [
            InlineKeyboardButton("🔄 تغییر شماره حساب", callback_data=f"bank_change_acc_{user_id}")
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    parts = query.data.replace("bank_", "").split("_")
    
    action = parts[0]
    if len(parts) >= 3 and parts[0] in ["deposit", "withdraw", "claim", "change"]:
        action = f"{parts[0]}_{parts[1]}"
        owner_id = int(parts[2])
    else:
        owner_id = int(parts[-1])

    if clicker_id != owner_id:
        await query.answer("❌ این پنل بانک متعلق به شما نیست!", show_alert=True)
        return

    await query.answer()

    if action in ["deposit_help", "deposit"]:
        await query.message.reply_text("💡 **راهنمای واریز:**\n`بانک واریز 100` یا `بانک واریز همه`", parse_mode='Markdown')
    elif action in ["withdraw_help", "withdraw"]:
        await query.message.reply_text("💡 **راهنمای برداشت:**\n`بانک برداشت 100` یا `بانک برداشت همه`", parse_mode='Markdown')
    elif action in ["claim_profit", "claim"]:
        user = db.get_user(clicker_id)
        profit = int(user[5] * 0.03)
        if profit > 0:
            db.update_field(clicker_id, "points", profit)
            await query.message.reply_text(f"🎉 مبلغ **{profit:,}** هاپ سود دریافت شد.")
        else:
            await query.message.reply_text("❌ موجودی بانک شما سود فعال ندارد.")
    elif action in ["change_acc", "change"]:
        new_acc = str(random.randint(1000000000, 9999999999))
        db.update_field(clicker_id, "account_number", new_acc, relative=False)
        await query.message.reply_text(f"✅ شماره حساب جدید شما:\n`{new_acc}`", parse_mode='Markdown')
        await bank_status(update, context, db.get_user(clicker_id))


# ==================== 🏭 ساخت محصول (کارخونه) ====================

async def handle_factory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]
    user_points = user[2]

    msg = (
        f"🏭 **خط تولید کارخانه**\n\n"
        f"💰 **موجودی:** {user_points:,} هاپ\n\n"
        f"محصول مورد نظر را جهت تولید انتخاب کنید (محصول در انبار ذخیره می‌شود):"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 تولید الماس (هزینه: ۳۰۰)", callback_data=f"buy_factory_diamond_{user_id}")],
        [InlineKeyboardButton("📦 تولید سیگار (هزینه: ۱۰۰)", callback_data=f"buy_factory_cig_{user_id}")],
        [InlineKeyboardButton("🍫 تولید شکلات (هزینه: ۵۰)", callback_data=f"buy_factory_choco_{user_id}")],
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


async def handle_factory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    parts = query.data.replace("buy_factory_", "").split("_")
    fac_type = parts[0]
    owner_id = int(parts[1])

    if clicker_id != owner_id:
        await query.answer("❌ این پنل متعلق به شما نیست!", show_alert=True)
        return

    costs = {"diamond": 300, "cig": 100, "choco": 50}
    names = {"diamond": "الماس 💎", "cig": "سیگار 📦", "choco": "شکلات 🍫"}
    
    cost = costs.get(fac_type, 0)
    user = db.get_user(clicker_id)

    if user[2] < cost:
        await query.answer("❌ موجودی کافی نیست!", show_alert=True)
        return

    await query.answer()

    db.update_field(clicker_id, "points", -cost)
    db.update_field(clicker_id, f"inventory_{fac_type}", 1)

    await query.message.edit_text(
        f"🎉 **تولید با موفقیت انجام شد!**\n\n"
        f"✅ ۱ عدد **{names[fac_type]}** وارد انبار شد.\n"
        f"جهت مدیریت اجناس دستور `کارخونه من` را ارسال کنید.",
        parse_mode='Markdown'
    )


# ==================== 📦 انبار محصولات (کارخونه من) ====================

async def my_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    user_id = user[0]

    diamond = db.get_user_field(user_id, "inventory_diamond") or 0
    cig = db.get_user_field(user_id, "inventory_cig") or 0
    choco = db.get_user_field(user_id, "inventory_choco") or 0

    msg = (
        f"📦 **انبار اجناس شما**\n\n"
        f"🔹 **الماس:** {diamond} عدد\n"
        f"🔹 **سیگار:** {cig} عدد\n"
        f"🔹 **شکلات:** {choco} عدد\n\n"
        f"عملیات مورد نظر روی اجناس را انتخاب کنید:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 فروش الماس", callback_data=f"action_sell_diamond_{user_id}"),
            InlineKeyboardButton("🕵️‍♂️ قاچاق الماس", callback_data=f"action_smuggle_diamond_{user_id}")
        ],
        [
            InlineKeyboardButton("📦 فروش سیگار", callback_data=f"action_sell_cig_{user_id}"),
            InlineKeyboardButton("🕵️‍♂️ قاچاق سیگار", callback_data=f"action_smuggle_cig_{user_id}")
        ],
        [
            InlineKeyboardButton("🍫 فروش شکلات", callback_data=f"action_sell_choco_{user_id}"),
            InlineKeyboardButton("🕵️‍♂️ قاچاق شکلات", callback_data=f"action_smuggle_choco_{user_id}")
        ],
    ])

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')


# ==================== 🛒 اقدام فروش / قاچاق ====================

async def handle_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    parts = query.data.split("_")
    
    act_type = parts[1]
    item_type = parts[2]
    owner_id = int(parts[3])

    if clicker_id != owner_id:
        await query.answer("❌ این پنل برای شما نیست!", show_alert=True)
        return

    inv_count = db.get_user_field(clicker_id, f"inventory_{item_type}") or 0
    if inv_count <= 0:
        await query.answer("❌ این جنس در انبار شما موجود نیست!", show_alert=True)
        return

    await query.answer()

    items_info = {
        "diamond": {"name": "الماس 💎", "sell": 450, "smuggle": 800, "risk": 60},
        "cig": {"name": "سیگار 📦", "sell": 150, "smuggle": 300, "risk": 30},
        "choco": {"name": "شکلات 🍫", "sell": 75, "smuggle": 150, "risk": 10},
    }
    info = items_info[item_type]

    db.update_field(clicker_id, f"inventory_{item_type}", -1)

    if act_type == "sell":
        db.update_field(clicker_id, "points", info["sell"])
        await query.message.edit_text(
            f"💰 **فروش موفق!**\n\n۱ عدد {info['name']} به مبلغ **{info['sell']:,}** هاپ فروخته شد.",
            parse_mode='Markdown'
        )
    elif act_type == "smuggle":
        if random.randint(1, 100) <= info["risk"]:
            await query.message.edit_text(
                f"🚨 **بار شما لو رفت!**\n\nمحموله {info['name']} توسط پلیس ضبط شد!",
                parse_mode='Markdown'
            )
        else:
            db.update_field(clicker_id, "points", info["smuggle"])
            await query.message.edit_text(
                f"🎉 **قاچاق موفق!**\n\n{info['name']} فروخته شد و **{info['smuggle']:,}** هاپ دریافت کردید.",
                parse_mode='Markdown'
            )

async def handle_smuggle(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await my_inventory(update, context, user)
