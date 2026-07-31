from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# پاداش دعوت (مثلاً ۵۰۰ سکه/نقطه برای هر دعوت)
REFERRAL_REWARD = 500

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    """نمایش لینک و آمار زیرمجموعه‌گیری"""
    user_id = update.effective_user.id
    bot_username = context.bot.username
    
    # ساخت لینک اختصاصی کاربر
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # دریافت تعداد زیرمجموعه‌ها از دیتابیس
    ref_count = db.get_referral_stats(user_id) if hasattr(db, "get_referral_stats") else 0
    total_earned = ref_count * REFERRAL_REWARD

    text = (
        f"👥 **سیستم دعوت و زیرمجموعه‌گیری**\n\n"
        f"با دعوت دوستان خود به ربات، پاداش دریافت کنید!\n\n"
        f"🎁 **پاداش هر دعوت:** {REFERRAL_REWARD:,} سکه\n"
        f"📊 **تعداد دعوت‌های شما:** {ref_count} نفر\n"
        f"💰 **مجموع درآمد از دعوت:** {total_earned:,} سکه\n\n"
        f"🔗 **لینک اختصاصی شما:**\n"
        f"`{referral_link}`"
    )

    # دکمه اشتراک‌گذاری سریع در تلگرام
    share_url = f"https://t.me/share/url?url={referral_link}&text=بیا%20تو%20این%20ربات%20باهم%20بازی%20کنیم!"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 اشتراک‌گذاری لینک", url=share_url)]
    ])

    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)