import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# ==================== دیکشنری‌های اسلات ====================

EMOJI_VALUES = {
    "BAR": 0,
    "🍇": 1,
    "🍋": 2,
    "7️⃣": 3
}

ROW_MULTIPLIERS = {0: 1, 1: 4, 2: 16}

PRIZE_MULTIPLIERS = {
    (1, 9): 0,
    (10, 19): 0,
    (20, 29): 0.5,
    (30, 39): 1.0,
    (40, 49): 1.5,
    (50, 59): 2.0,
    (60, 63): 2.5,
    (64, 64): 3.0
}

slot_bets = {}

# ==================== توابع کمکی ====================

def format_balance(amount):
    try:
        from handlers.pet import format_balance as fb
        return fb(amount)
    except Exception:
        amount = int(amount or 0)
        if amount < 1000:
            return f"{amount:,}"
        elif amount < 1_000_000:
            return f"{amount:,}"
        elif amount < 1_000_000_000:
            millions = amount / 1_000_000
            if millions.is_integer():
                return f"{int(millions)}M"
            else:
                return f"{millions:.1f}M"
        else:
            billions = amount / 1_000_000_000
            if billions.is_integer():
                return f"{int(billions)}B"
            else:
                return f"{billions:.1f}B"

# ==================== توابع اسلات ====================

def calculate_slot_score(emojis):
    score = 1
    for i, emoji in enumerate(emojis):
        value = EMOJI_VALUES.get(emoji, 0)
        multiplier = ROW_MULTIPLIERS.get(i, 1)
        score += value * multiplier
    return score

def get_prize_multiplier(score):
    for (low, high), multiplier in PRIZE_MULTIPLIERS.items():
        if low <= score <= high:
            return multiplier
    return 0

def generate_random_slot():
    return [random.choice(["🍇", "🍋", "7️⃣"]) for _ in range(3)]

def get_slot_number(emojis):
    values = [EMOJI_VALUES.get(e, 0) for e in emojis]
    return (values[0] * 16) + (values[1] * 4) + values[2] + 1

# ==================== دستورات اسلات ====================

async def slot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اسلات - فقط در گروه"""
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("🎰 اسلات فقط در گروه قابل استفاده است!")
        return
    
    user_id = update.effective_user.id
    points = db.get_user_field(user_id, "points") or 0
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 شروع اسلات", callback_data="slot_start")]
    ])
    
    text = (
        f"🎰 **اسلات ماشین هاپو**\n\n"
        f"👤 کاربر: {update.effective_user.first_name}\n"
        f"💰 هاپو پوینت: {format_balance(points)}\n\n"
        f"برای شروع بازی روی دکمه زیر کلیک کن!\n\n"
        f"📊 **ضریب‌های جایزه:**\n"
        f"امتیاز ۱-۱۹: ×۰\n"
        f"امتیاز ۲۰-۲۹: ×۰.۵\n"
        f"امتیاز ۳۰-۳۹: ×۱.۰\n"
        f"امتیاز ۴۰-۴۹: ×۱.۵\n"
        f"امتیاز ۵۰-۵۹: ×۲.۰\n"
        f"امتیاز ۶۰-۶۳: ×۲.۵\n"
        f"امتیاز ۶۴ (جکپات): ×۳.۰"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def slot_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع بازی اسلات"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    points = db.get_user_field(user_id, "points") or 0
    
    if points < 100:
        await query.message.reply_text("❌ حداقل ۱۰۰ هاپو پوینت برای شروع اسلات نیاز داری!")
        return
    
    slot_bets[user_id] = "waiting"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ لغو", callback_data="slot_cancel")]
    ])
    
    await query.message.edit_text(
        f"🎰 **اسلات ماشین**\n\n"
        f"💰 مبلغ شرط خود را وارد کن (۱۰۰ تا ۱۰۰٬۰۰۰)\n"
        f"مثال: 500\n\n"
        f"📊 **ضریب‌های جایزه:**\n"
        f"امتیاز ۱-۱۹: ×۰\n"
        f"امتیاز ۲۰-۲۹: ×۰.۵\n"
        f"امتیاز ۳۰-۳۹: ×۱.۰\n"
        f"امتیاز ۴۰-۴۹: ×۱.۵\n"
        f"امتیاز ۵۰-۵۹: ×۲.۰\n"
        f"امتیاز ۶۰-۶۳: ×۲.۵\n"
        f"امتیاز ۶۴ (جکپات): ×۳.۰\n\n"
        f"🎯 بعد از وارد کردن مبلغ، استیکر **🎰** بفرستید!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_slot_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مبلغ شرط اسلات"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in slot_bets or slot_bets[user_id] != "waiting":
        return False
    
    try:
        bet = int(text)
        if bet < 100:
            await update.message.reply_text("❌ حداقل مبلغ ۱۰۰ هاپو پوینت است!")
            return True
        if bet > 100000:
            await update.message.reply_text("❌ حداکثر مبلغ ۱۰۰٬۰۰۰ هاپو پوینت است!")
            return True
    except ValueError:
        await update.message.reply_text("❌ لطفا یک عدد معتبر وارد کنید!")
        return True
    
    points = db.get_user_field(user_id, "points") or 0
    if points < bet:
        await update.message.reply_text(f"❌ موجودی کافی نیست! داری {format_balance(points)} هاپو پوینت")
        return True
    
    slot_bets[user_id] = bet
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 ارسال استیکر", callback_data=f"slot_send_sticker_{user_id}")]
    ])
    
    await update.message.reply_text(
        f"✅ مبلغ شرط: {format_balance(bet)} هاپو پوینت\n\n"
        f"🎰 حالا استیکر **🎰** رو بفرستید یا روی دکمه زیر کلیک کنید!\n"
        f"⏱️ فقط ۱۲۰ ثانیه فرصت دارید...",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    # تایمر ۱۲۰ ثانیه
    await asyncio.sleep(120)
    
    if user_id in slot_bets and slot_bets[user_id] != "waiting":
        del slot_bets[user_id]
        await update.message.reply_text("⏱️ زمان شما به پایان رسید! شرط لغو شد.")
    
    return True

async def slot_send_sticker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال استیکر 🎰 با دکمه"""
    query = update.callback_query
    parts = query.data.split("_")
    user_id = int(parts[3])
    
    if query.from_user.id != user_id:
        await query.answer("❌ این دکمه مال شما نیست!", show_alert=True)
        return
    
    await query.answer()
    
    # ارسال استیکر 🎰
    await query.message.reply_sticker(
        sticker="CAACAgIAAxkBAAENwWZk4H7YhMZ8eLPlH7nWc3nYpZvK"
    )
    
    await query.message.reply_text("🎰 استیکر ارسال شد! حالا برای اجرای اسلات، استیکر رو بفرستید.")

async def handle_slot_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت استیکر و اجرای اسلات"""
    user_id = update.effective_user.id
    
    # اگه کاربر در حال بازی اسلات نیست، کاری نکن
    if user_id not in slot_bets or slot_bets[user_id] == "waiting":
        return False
    
    # چک کردن استیکر 🎰
    if update.message.sticker.emoji != "🎰":
        await update.message.reply_text("❌ لطفا استیکر **🎰** رو بفرستید!")
        return True
    
    bet = slot_bets[user_id]
    del slot_bets[user_id]
    
    points = db.get_user_field(user_id, "points") or 0
    
    # تولید اسلات تصادفی
    result = generate_random_slot()
    score = calculate_slot_score(result)
    multiplier = get_prize_multiplier(score)
    slot_number = get_slot_number(result)
    combo = f"{result[0]} {result[1]} {result[2]}"
    
    win = int(bet * multiplier)
    
    text = f"🎰 **گردونه شانس**\n\n"
    text += f"💰 مبلغ ورودی: {format_balance(bet)}\n"
    text += f"📊 ({multiplier}x)\n"
    text += f"🎯 مبلغ دریافت: {format_balance(win)}\n"
    text += f"👤 بازیکن: {update.effective_user.first_name}\n"
    text += f"⭐ امتیاز: {score}\n\n"
    text += f"🎰 {combo}\n"
    text += f"🔢 #{slot_number} از ۶۴"
    
    if win > 0:
        db.update_field(user_id, "points", win, relative=True)
        if score == 64:
            text += f"\n\n🌟 **جکپات!** 🌟"
    else:
        text += f"\n\n😞 متاسفانه برنده نشدید!"
    
    await update.message.reply_text(text, parse_mode="Markdown")
    return True

async def slot_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو بازی اسلات"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id in slot_bets:
        del slot_bets[user_id]
    
    await query.answer()
    await query.message.edit_text("❌ بازی اسلات لغو شد!")
