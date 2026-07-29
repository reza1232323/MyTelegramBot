import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# --- اصلاح قمار ساده (مشکل عدم تشخیص عدد) ---
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

# --- منوی بازی‌های استیکری (دستور: بازی 100) ---
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

# --- پردازش کلیک دکمه بازی ---
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
    
    # ثبت آیدی پیام در حافظه برای چک کردن ریپلای
    context.bot_data[f"game_{sent_msg.message_id}"] = {
        "user_id": owner_id,
        "amt": amt,
        "emoji": target_emoji
    }

# --- پردازش استیکر ریپلای شده توسط کاربر ---
async def process_dice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
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

    # شرط برنده شدن (امتیاز ۴ به بالا)
    if val >= 4:
        db.update_field(user_id, "points", amt)
        await update.message.reply_text(f"🎉 **برنده شدی!**\nامتیاز استیکر: **{val}**\nمبلغ **+{amt:,}** هاپ دریافت کردی.", parse_mode='Markdown')
    else:
        db.update_field(user_id, "points", -amt)
        await update.message.reply_text(f"💥 **باختی!**\nامتیاز استیکر: **{val}**\nمبلغ **-{amt:,}** هاپ کسر شد.", parse_mode='Markdown')

    del context.bot_data[f"game_{reply_id}"]
