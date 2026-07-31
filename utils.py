from aiogram.types import Message
from config import config
from models import User
import time
from datetime import datetime, timedelta

async def check_channels(bot, user_id):
    """بررسی عضویت در کانال‌ها"""
    not_joined = []
    for channel in config.REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel["username"], user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    return not_joined

def is_admin(user_id):
    """بررسی ادمین بودن"""
    return user_id in config.ADMIN_IDS

def can_claim_hop(user):
    """بررسی امکان دریافت هاپ (هر ۵ دقیقه)"""
    last_claim = user.get("last_hop_claim", 0)
    return time.time() - last_claim >= 300

def calculate_hop_reward(user):
    """محاسبه هاپ دریافتی بر اساس سطح"""
    base = 10
    level_bonus = user["level"] * 1.5
    return base + level_bonus

def has_gem_chance():
    """شانس دریافت جم"""
    return random.random() < 0.05

def get_random_gem():
    """دریافت جم تصادفی"""
    return random.randint(1, 3)

def format_profile(user):
    """فرمت کردن پروفایل"""
    return f"""
🐾 **پروفایل {user['first_name']}**
━━━━━━━━━━━━━━━
🎯 هاپ: {user['hop_point']:.1f}
💎 جم: {user['hop_gem']:.1f}
📊 سطح: {user['level']}
⭐ تجربه: {user['exp']}

🐣 هاپو: {user['hopo_name']}
🧬 نژاد: {user['hopo_breed']}
📈 مرحله: {user['hopo_stage']}
❤️ سلامتی: {user['hopo_health']}%
😊 خوشحالی: {user['hopo_happiness']}%
⚡ انرژی: {user['hopo_energy']}%
🍖 گرسنگی: {user['hopo_hunger']}%

🏭 کارخانه: سطح {user['factory_level']}
🏦 بانک: {user['bank_balance']:.1f} هاپ
📊 دعوت‌ها: {user['invite_count']} نفر
    """

def format_leaderboard(users):
    """فرمت کردن لیدربرد"""
    if not users:
        return "📊 هنوز کسی تو لیست نیست!"
    
    text = "🏆 **لیدربرد هاپ**\n━━━━━━━━━━\n"
    for i, user in enumerate(users, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        text += f"{medal} {user['first_name']} — {user['hop_point']:.1f} هاپ (سطح {user['level']})\n"
    return text

def format_shop(items):
    """فرمت کردن فروشگاه"""
    if not items:
        return "🛒 فروشگاه خالی است!"
    
    text = "🛒 **فروشگاه هاپو**\n━━━━━━━━━━\n"
    for item in items[:10]:
        text += f"{item['emoji']} **{item['name']}**\n"
        text += f"{item['description']}\n"
        if item['price_hop'] > 0:
            text += f"💰 {item['price_hop']:.1f} هاپ"
        if item['price_gem'] > 0:
            text += f" 💎 {item['price_gem']:.1f} جم"
        text += f"\n🆔 {item['id']}\n━━━━━━━━━━\n"
    
    text += "\nخرید: /خرید [آیدی] [تعداد]"
    return text
