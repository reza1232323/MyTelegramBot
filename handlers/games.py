import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# ذخیره وضعیت بازی‌های فعال در حافظه
ACTIVE_GAMES = {}

async def start_gambling(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    text = update.message.text.strip().split()
    
    if len(text) < 3:
        await update.message.reply_text("🎲 **فرمت قمار چندنفره:**\n`قمار [مبلغ] [تعداد نفرات]`\n\nمثال: `قمار 100 2`", parse_mode='Markdown')
        return

    try:
        amount = int(text[1])
        players_count = int(text[2])
    except ValueError:
        await update.message.reply_text("❌ مبلغ و تعداد نفرات باید عدد باشند.")
        return

    if amount < 10 or players_count < 2:
        await update.message.reply_text("❌ حداقل مبلغ ۱۰ هاپ و حداقل نفرات ۲ نفر است.")
        return

    if user[2] < amount:
        await update.message.reply_text("❌ موجودی هاپ شما کافی نیست!")
        return

    game_id = f"{update.effective_chat.id}_{update.message.message_id}"
    ACTIVE_GAMES[game_id] = {
        "creator": user[0],
        "amount": amount,
        "max_players": players_count,
        "players": [user[0]],
        "player_names": [update.effective_user.first_name]
    }

    db.update_field(user[0], "points", -amount)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ شرکت در قمار", callback_data=f"join_gamble:{game_id}")]
    ])

    msg = (
        f"🎲 **اتاق قمار جدید ساخته شد!**\n\n"
        f"💰 **ورودی:** {amount} هاپ\n"
        f"👥 **ظرفیت:** ۱/{players_count} نفر\n"
        f"مشارکت‌کنندگان: {update.effective_user.first_name}"
    )
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')

async def handle_gamble_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":")[1]
    if game_id not in ACTIVE_GAMES:
        await query.edit_message_text("❌ این قمار منقضی شده یا به پایان رسیده است.")
        return

    game = ACTIVE_GAMES[game_id]
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if user_id in game["players"]:
        return

    if user[2] < game["amount"]:
        return

    db.update_field(user_id, "points", -game["amount"])
    game["players"].append(user_id)
    game["player_names"].append(query.from_user.first_name)

    current_len = len(game["players"])
    max_len = game["max_players"]

    if current_len < max_len:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➕ شرکت در قمار", callback_data=f"join_gamble:{game_id}")]])
        players_str = ", ".join(game["player_names"])
        await query.edit_message_text(
            f"🎲 **اتاق قمار!**\n💰 **ورودی:** {game['amount']} هاپ\n👥 **ظرفیت:** {current_len}/{max_len} نفر\nشرکت کنندگان: {players_str}",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    else:
        # قرعه‌کشی و انتخاب برنده
        winner_id = random.choice(game["players"])
        winner_name = game["player_names"][game["players"].index(winner_id)]
        total_prize = game["amount"] * max_len

        db.update_field(winner_id, "points", total_prize)
        del ACTIVE_GAMES[game_id]

        await query.edit_message_text(
            f"🎉 **قمار به پایان رسید!**\n\n🏆 **برنده خوش‌شانس:** {winner_name}\n🪙 **مبلغ جایزه:** {total_prize} هاپ!",
            parse_mode='Markdown'
        )