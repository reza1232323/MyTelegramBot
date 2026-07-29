import random
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def spin_wheel(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    prizes = [-100, -50, 0, 50, 100, 250, 500, 1000]
    win = random.choice(prizes)
    db.update_field(user[0], "points", win)
    
    if win > 0:
        await update.message.reply_text(f"🎡 گردونه چرخید و شما **+{win}** هاپ برنده شدید! 🎉", parse_mode='Markdown')
    elif win < 0:
        await update.message.reply_text(f"🎡 گردونه چرخید و شما **{win}** هاپ باختید! ❌", parse_mode='Markdown')
    else:
        await update.message.reply_text("🎡 گردونه روی پوچ ایستاد!")

async def roll_dice(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    dice = await update.message.reply_dice()
    val = dice.dice.value
    reward = val * 15
    db.update_field(user[0], "points", reward)
    await update.message.reply_text(f"🎲 عدد تاس {val} آمد! جایزه: {reward} هاپ")