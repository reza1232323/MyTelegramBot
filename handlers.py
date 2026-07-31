from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from models import User, Inventory, Shop, GroupMessage
from utils import *
from keyboards import *
from config import config
import random
import asyncio
from datetime import datetime, timedelta
import time
import re

router = Router()

# ==================== فیلتر تشخیص پیوی/گروه ====================

def is_private(message: Message) -> bool:
    return message.chat.type == "private"

def is_group(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]

# ==================== شروع و ثبت‌نام ====================

@router.message(F.text == "شروع")
@router.message(Command("start"))
async def start_command(message: Message, bot):
    """ثبت‌نام و شروع - هم در پیوی هم گروه"""
    
    user = User.get_or_create(message.from_user)
    
    if is_private(message) and " " in message.text:
        ref_code = message.text.split()[1]
        if ref_code.startswith("ref_"):
            referrer_id = int(ref_code.split("_")[1])
            if referrer_id != message.from_user.id:
                referrer = User.get(referrer_id)
                if referrer:
                    User.update(referrer_id, invite_count=referrer["invite_count"] + 1)
                    User.update(referrer_id, hop_point=referrer["hop_point"] + 20)
                    try:
                        await bot.send_message(referrer_id, f"🎉 {message.from_user.first_name} با لینک شما ثبت‌نام کرد! +۲۰ هاپ")
                    except:
                        pass
    
    await message.reply(
        f"🎉 **به هاپو خوش اومدی {user['first_name']}!**\n\n"
        f"🐣 یه تخم هاپو داری که تا ۶ ساعت دیگه باز میشه!\n"
        f"💡 هر ۵ دقیقه با دستور **هاپ** امتیاز بگیر.\n"
        f"📖 راهنما: **راهنما**\n\n"
        f"✨ {user['hop_point']:.1f} هاپ اولیه بهت داده شد!",
        reply_markup=main_menu() if is_private(message) else None
    )

# ==================== دکمه خانه (فقط پیوی) ====================

@router.message(F.text == "🏠 خانه")
async def home_command(message: Message, bot):
    if is_private(message):
        await start_command(message, bot)

# ==================== دستور هاپ ====================

@router.message(F.text == "هاپ")
async def get_hop_command(message: Message, bot):
    """دریافت هاپ هر ۵ دقیقه - هم در پیوی هم گروه"""
    
    if is_private(message):
        not_joined = await check_channels(bot, message.from_user.id)
        if not_joined:
            await message.reply(
                "⚠️ برای دریافت هاپ ابتدا در کانال‌های زیر عضو شوید:",
                reply_markup=channel_check_kb(not_joined)
            )
            return
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ابتدا ثبت‌نام کنید: شروع")
        return
    
    if not can_claim_hop(user):
        remain = int(300 - (time.time() - user["last_hop_claim"]))
        minutes = remain // 60
        seconds = remain % 60
        await message.reply(f"⏳ صبر کن! {minutes} دقیقه و {seconds} ثانیه مونده")
        return
    
    hop_reward = calculate_hop_reward(user)
    gem_reward = 0
    
    if has_gem_chance():
        gem_reward = get_random_gem()
        User.update(message.from_user.id, hop_gem=user["hop_gem"] + gem_reward)
    
    bonus = 0
    if is_group(message):
        bonus = 5
        hop_reward += bonus
        GroupMessage.add(message.from_user.id, message.chat.id, message.text or "")
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] + hop_reward,
        last_hop_claim=time.time()
    )
    
    gem_text = f" و 💎 {gem_reward} جم" if gem_reward > 0 else ""
    bonus_text = f" (🌟 {bonus} پاداش گروهی)" if bonus > 0 else ""
    
    await message.reply(f"🎉 {hop_reward:.1f} هاپ دریافت کردی!{gem_text}{bonus_text}")

# ==================== پروفایل ====================

@router.message(F.text == "هاپوهام")
@router.message(F.text == "🐣 هایوی من")
async def my_profile(message: Message):
    """مشاهده پروفایل - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ابتدا ثبت‌نام کنید: شروع")
        return
    
    if user["hopo_stage"] != "egg":
        hunger = max(0, user["hopo_hunger"] - 5)
        happiness = max(0, user["hopo_happiness"] - 2)
        User.update(message.from_user.id, hopo_hunger=hunger, hopo_happiness=happiness)
        user = User.get(message.from_user.id)
    
    await message.reply(
        format_profile(user, group_mode=is_group(message)),
        reply_markup=inline_home() if is_private(message) else None
    )

# ==================== مشاهده پروفایل کاربر دیگر (با ریپلای) ====================

@router.message(F.text == "هاپ هاش")
async def user_profile_reply(message: Message):
    """مشاهده پروفایل کاربری که رویش ریپلای شده - هم در پیوی هم گروه"""
    if not message.reply_to_message:
        await message.reply("❌ روی پیام یک کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    
    if not user:
        await message.reply("❌ کاربر در ربات ثبت‌نام نکرده!")
        return
    
    await message.reply(format_profile(user, group_mode=is_group(message)))

# ==================== لیدربرد ====================

@router.message(F.text == "لیدربرد")
@router.message(F.text == "📊 لیدربرد")
async def leaderboard_command(message: Message):
    """نمایش لیدربرد - هم در پیوی هم گروه"""
    
    if is_group(message):
        users = User.get_group_top_users(message.chat.id, 10)
        await message.reply(format_group_leaderboard(users))
    else:
        users = User.get_top_users(10)
        await message.reply(format_leaderboard(users))

# ==================== گردونه شانس ====================

@router.message(F.text == "گردونه")
@router.message(F.text == "🎡 گردونه شانس")
async def spin_command(message: Message):
    """گردونه شانس - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    cost = 20
    if user["hop_point"] < cost:
        await message.reply(f"❌ {cost} هاپ نیاز داری!")
        return
    
    User.update(message.from_user.id, hop_point=user["hop_point"] - cost)
    
    prizes = [
        ("🎉 ۵۰ هاپ!", 50, 0),
        ("🎉 ۲۰ هاپ!", 20, 0),
        ("🎉 ۱۰۰ هاپ!", 100, 0),
        ("💎 ۵ جم!", 0, 5),
        ("💎 ۲ جم!", 0, 2),
        ("😞 هیچی!", 0, 0),
        ("⭐ ۵۰۰ هاپ!", 500, 0),
        ("🥚 تخم طلایی!", 0, 0, "egg")
    ]
    
    prize = random.choice(prizes)
    
    if len(prize) > 3:
        result = "🥚 تخم طلایی دریافت کردی!"
    else:
        hop_win, gem_win = prize[1], prize[2]
        if hop_win > 0:
            User.update(message.from_user.id, hop_point=user["hop_point"] + hop_win)
            result = f"{prize[0]} (مجموع: {user['hop_point'] - cost + hop_win:.1f} هاپ)"
        elif gem_win > 0:
            User.update(message.from_user.id, hop_gem=user["hop_gem"] + gem_win)
            result = prize[0]
        else:
            result = prize[0]
    
    await message.reply(f"🎡 **گردونه شانس**\n{result}")

# ==================== بازی‌ها ====================

@router.message(F.text == "بازی")
@router.message(F.text == "🎲 بازی‌ها")
async def games_menu(message: Message):
    await message.reply(
        "🎮 **بازی‌های هاپو**\n\n"
        "🎲 **تاس** [مبلغ]\n"
        "🎡 **گردونه**\n"
        "♠️ **قمار** [مبلغ]"
    )

# ==================== تاس ====================

@router.message(F.text.startswith("تاس"))
async def dice_game(message: Message):
    """بازی تاس - هم در پیوی هم گروه"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: تاس 100")
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    if user["hop_point"] < bet:
        await message.reply(f"❌ موجودی کافی نیست! داری {user['hop_point']:.1f} هاپ")
        return
    
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    
    if user_roll > bot_roll:
        win = bet * 1.5
        User.update(message.from_user.id, hop_point=user["hop_point"] + win)
        result = f"🎉 بردی! {win:.1f} هاپ"
    elif user_roll < bot_roll:
        User.update(message.from_user.id, hop_point=user["hop_point"] - bet)
        result = f"😞 باختی! {bet:.1f} هاپ"
    else:
        result = "🤝 مساوی شد!"
    
    await message.reply(
        f"🎲 **تاس**\n"
        f"تو: {user_roll} | ربات: {bot_roll}\n"
        f"{result}"
    )

# ==================== قمار ====================

@router.message(F.text.startswith("قمار"))
async def gamble_game(message: Message):
    """بازی قمار - هم در پیوی هم گروه"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: قمار 100")
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user = User.get(message.from_user.id)
    if not user or user["hop_point"] < bet:
        await message.reply("❌ موجودی کافی نیست!")
        return
    
    cards = ["♠️", "♥️", "♦️", "♣️"]
    user_card = random.choice(cards)
    bot_card = random.choice(cards)
    
    ranks = {"♠️": 4, "♥️": 3, "♦️": 2, "♣️": 1}
    
    if ranks[user_card] > ranks[bot_card]:
        win = bet * 2
        User.update(message.from_user.id, hop_point=user["hop_point"] + win)
        result = f"🎉 بردی! {win:.1f} هاپ"
    elif ranks[user_card] < ranks[bot_card]:
        User.update(message.from_user.id, hop_point=user["hop_point"] - bet)
        result = f"😞 باختی! {bet:.1f} هاپ"
    else:
        result = "🤝 مساوی شد!"
    
    await message.reply(
        f"♠️ **قمار**\n"
        f"تو: {user_card} | ربات: {bot_card}\n"
        f"{result}"
    )

# ==================== سگ ====================

@router.message(F.text == "سگ")
async def dog_command(message: Message):
    """خرید و مدیریت سگ - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT has_dog, dog_level FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    conn.close()
    
    has_dog = result[0] if result else 0
    dog_level = result[1] if result else 0
    
    if not has_dog:
        if user["hop_point"] < 100:
            await message.reply("❌ ۱۰۰ هاپ نیاز داری برای خرید سگ!")
            return
        User.update(message.from_user.id, hop_point=user["hop_point"] - 100)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET has_dog = 1, dog_level = 1 WHERE id = ?", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.reply("🐕 سگ خریدی! حالا می‌تونه برات استخوان پیدا کنه.")
    else:
        upgrade_cost = dog_level * 50
        if user["hop_point"] < upgrade_cost:
            await message.reply(f"❌ {upgrade_cost} هاپ نیازه برای ارتقا!")
            return
        User.update(message.from_user.id, hop_point=user["hop_point"] - upgrade_cost)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET dog_level = dog_level + 1 WHERE id = ?", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.reply(f"🐕 سگ به سطح {dog_level + 1} ارتقا یافت!")

# ==================== قلاب ====================

@router.message(F.text == "قلاب")
async def fishing_rod_command(message: Message):
    """خرید و ارتقای قلاب - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT fishing_rod_level FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    rod_level = result[0] if result else 0
    conn.close()
    
    if rod_level == 0:
        if user["hop_point"] < 50:
            await message.reply("❌ ۵۰ هاپ نیاز داری برای خرید قلاب!")
            return
        User.update(message.from_user.id, hop_point=user["hop_point"] - 50)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET fishing_rod_level = 1 WHERE id = ?", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.reply("🎣 قلاب خریداری شد! حالا می‌تونی استخوان صید کنی.")
    else:
        upgrade_cost = rod_level * 30
        if user["hop_point"] < upgrade_cost:
            await message.reply(f"❌ {upgrade_cost} هاپ نیازه!")
            return
        User.update(message.from_user.id, hop_point=user["hop_point"] - upgrade_cost)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET fishing_rod_level = fishing_rod_level + 1 WHERE id = ?", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.reply(f"🎣 قلاب به سطح {rod_level + 1} ارتقا یافت!")

# ==================== استخوان ====================

@router.message(F.text == "استخوان")
async def bone_fishing(message: Message):
    """صید استخوان با قلاب - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT fishing_rod_level, bones FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    conn.close()
    
    rod_level = result[0] if result else 0
    current_bones = result[1] if result else 0
    
    if rod_level == 0:
        await message.reply("❌ اول قلاب بخر!")
        return
    
    chance = 20 + (rod_level * 5)
    if random.randint(1, 100) > chance:
        await message.reply("😞 چیزی صید نشد! دوباره امتحان کن.")
        return
    
    bone_count = random.randint(1, rod_level)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bones = ? WHERE id = ?", (current_bones + bone_count, message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.reply(f"🦴 {bone_count} استخوان صید کردی! (مجموع: {current_bones + bone_count})")

# ==================== اسم گذاری ====================

@router.message(F.text.startswith("اسم"))
async def set_name_command(message: Message):
    """اسم گذاری هاپو - هم در پیوی هم گروه"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ فرمت: اسم نام")
        return
    
    name = parts[1]
    User.update(message.from_user.id, hopo_name=name)
    await message.reply(f"✅ هاپو اسمش شد: {name}")

# ==================== بانک ====================

@router.message(F.text == "بانک")
@router.message(F.text == "🏦 بانک")
async def bank_command(message: Message):
    """مدیریت بانک - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    await message.reply(
        f"🏦 **بانک هاپو**\n\n"
        f"💰 موجودی: {user['bank_balance']:.1f} هاپ\n"
        f"📈 سود: {user['bank_interest'] * 100}%\n\n"
        f"دستورات:\n"
        f"📥 **سپرده** [مبلغ]\n"
        f"📤 **برداشت** [مبلغ]"
    )

@router.message(F.text.startswith("سپرده"))
async def deposit_command(message: Message):
    """سپرده‌گذاری - هم در پیوی هم گروه"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: سپرده 100")
        return
    
    try:
        amount = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    if user["hop_point"] < amount:
        await message.reply(f"❌ موجودی کافی نیست! داری {user['hop_point']:.1f} هاپ")
        return
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] - amount,
        bank_balance=user["bank_balance"] + amount
    )
    
    await message.reply(f"✅ {amount:.1f} هاپ به بانک واریز شد!")

@router.message(F.text.startswith("برداشت"))
async def withdraw_command(message: Message):
    """برداشت از بانک - هم در پیوی هم گروه"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: برداشت 100")
        return
    
    try:
        amount = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    if user["bank_balance"] < amount:
        await message.reply(f"❌ موجودی بانک کافی نیست! داری {user['bank_balance']:.1f} هاپ")
        return
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] + amount,
        bank_balance=user["bank_balance"] - amount
    )
    
    await message.reply(f"✅ {amount:.1f} هاپ از بانک برداشت شد!")

# ==================== کارخانه ====================

@router.message(F.text == "کارخونه")
@router.message(F.text == "🏭 کارخانه")
async def factory_command(message: Message):
    """مدیریت کارخانه - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    await message.reply(
        f"🏭 **کارخانه**\n\n"
        f"📊 سطح: {user['factory_level']}\n"
        f"⚡ تولید: {user['factory_production']:.1f} هاپ در ساعت\n\n"
        f"دستورات:\n"
        f"📥 **جمع‌کارخانه**\n"
        f"⬆️ **ارتقا‌کارخانه**"
    )

@router.message(F.text == "جمع‌کارخانه")
async def collect_factory_command(message: Message):
    """جمع‌آوری تولید کارخانه - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    last_collect = datetime.fromisoformat(user["factory_last_collect"]) if user["factory_last_collect"] else datetime.now()
    hours = (datetime.now() - last_collect).seconds / 3600
    production = hours * user["factory_production"] * (user["factory_level"] + 1)
    
    if production < 0.1:
        await message.reply("⏳ هنوز چیزی تولید نشده!")
        return
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] + production,
        factory_last_collect=datetime.now().isoformat()
    )
    
    await message.reply(f"🏭 {production:.1f} هاپ از کارخانه جمع کردی!")

@router.message(F.text == "ارتقا‌کارخانه")
async def upgrade_factory_command(message: Message):
    """ارتقای کارخانه - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    cost = (user["factory_level"] + 1) * 100 + 50
    if user["hop_point"] < cost:
        await message.reply(f"❌ {cost} هاپ نیاز داری!")
        return
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] - cost,
        factory_level=user["factory_level"] + 1,
        factory_production=user["factory_production"] + 0.5
    )
    
    await message.reply(f"✅ کارخانه به سطح {user['factory_level'] + 1} ارتقا یافت!")

# ==================== فروشگاه ====================

@router.message(F.text == "فروشگاه")
@router.message(F.text == "🛒 فروشگاه")
async def shop_command(message: Message):
    """مشاهده فروشگاه - هم در پیوی هم گروه"""
    items = Shop.get_items()
    await message.reply(format_shop(items))

@router.message(F.text.startswith("خرید"))
async def buy_command(message: Message):
    """خرید از فروشگاه - هم در پیوی هم گروه"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: خرید [آیدی] [تعداد]")
        return
    
    try:
        item_id = int(parts[1])
        quantity = int(parts[2]) if len(parts) > 2 else 1
    except:
        await message.reply("❌ خطا در ورودی!")
        return
    
    result = Shop.buy(message.from_user.id, item_id, quantity)
    await message.reply(result["message"])

# ==================== کیف ====================

@router.message(F.text == "کیف")
@router.message(F.text == "🎒 کیف")
async def inventory_command(message: Message):
    """مشاهده انبار - هم در پیوی هم گروه"""
    items = Inventory.get_items(message.from_user.id)
    if not items:
        await message.reply("🎒 انبار خالی است!")
        return
    
    text = "🎒 **انبار شما**\n━━━━━━━━━━\n"
    for item in items:
        text += f"{item['item_name']}: {item['quantity']} عدد\n"
    
    await message.reply(text)

# ==================== مأموریت‌ها ====================

@router.message(F.text == "ماموریت")
@router.message(F.text == "🎯 مأموریت‌ها")
async def mission_command(message: Message):
    """مشاهده مأموریت‌ها - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM missions")
    missions = cursor.fetchall()
    conn.close()
    
    text = "🎯 **مأموریت‌ها**\n━━━━━━━━━━\n"
    for mission in missions:
        status = "✅" if (mission["type"] == "daily" and user["daily_mission_done"]) or (mission["type"] == "weekly" and user["weekly_mission_done"]) else "❌"
        text += f"{mission['emoji']} {mission['name']}\n"
        text += f"{mission['description']}\n"
        text += f"پاداش: {mission['reward_hop']} هاپ"
        if mission['reward_gem'] > 0:
            text += f" + {mission['reward_gem']} جم"
        text += f"\nوضعیت: {status}\n━━━━━━━━━━\n"
    
    text += "\n**دریافت‌ماموریت** - دریافت پاداش"
    await message.reply(text)

@router.message(F.text == "دریافت‌ماموریت")
async def claim_mission_command(message: Message):
    """دریافت پاداش مأموریت - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    if not user["daily_mission_done"]:
        User.update(
            message.from_user.id,
            daily_mission_done=1,
            hop_point=user["hop_point"] + 50
        )
        await message.reply("🎁 ۵۰ هاپ پاداش روزانه گرفتی!")
    else:
        await message.reply("❌ امروز پاداش رو گرفتی!")

# ==================== دعوت دوستان ====================

@router.message(F.text == "دعوت")
@router.message(F.text == "🔗 دعوت دوستان")
async def invite_command(message: Message):
    """دریافت لینک دعوت - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    bot_info = await message.bot.get_me()
    await message.reply(
        f"🔗 **لینک دعوت اختصاصی**\n\n"
        f"برای هر دعوت ۲۰ هاپ پاداش می‌گیری!\n"
        f"تعداد دعوت‌ها: {user['invite_count']}\n\n"
        f"https://t.me/{bot_info.username}?start=ref_{user['id']}"
    )

# ==================== راهنما ====================

@router.message(F.text == "راهنما")
@router.message(F.text == "📖 راهنما")
async def help_command(message: Message):
    """راهنمای کامل - هم در پیوی هم گروه"""
    help_text = """
📖 **راهنمای کامل ربات هاپو**

🐾 **دستورات اصلی (همه جا)**
**هاپ** ➜ دریافت هاپ (هر ۵ دقیقه)
**هاپوهام** ➜ مشاهده پروفایل
**هاپ‌هاش** ➜ پروفایل کاربر ریپلای شده
**لیدربرد** ➜ جدول برترین‌ها
**راهنما** ➜ نمایش راهنما

🐕 **سگ و ماهیگیری (همه جا)**
**سگ** ➜ خرید و مدیریت سگ
**قلاب** ➜ خرید و ارتقای قلاب
**استخوان** ➜ صید استخوان

🏦 **اقتصاد (همه جا)**
**بانک** ➜ مدیریت بانک
**سپرده** [مبلغ] ➜ واریز به بانک
**برداشت** [مبلغ] ➜ برداشت از بانک
**کارخونه** ➜ مدیریت کارخانه
**جمع‌کارخانه** ➜ جمع‌آوری تولید
**ارتقا‌کارخانه** ➜ ارتقای کارخانه

🛒 **فروشگاه (همه جا)**
**فروشگاه** ➜ مشاهده آیتم‌ها
**خرید** [آیدی] [تعداد] ➜ خرید آیتم
**کیف** ➜ مشاهده انبار

🎮 **بازی‌ها (همه جا)**
**بازی** ➜ منوی بازی‌ها
**تاس** [مبلغ] ➜ بازی تاس
**گردونه** ➜ گردونه شانس
**قمار** [مبلغ] ➜ بازی قمار

🎯 **مأموریت‌ها (همه جا)**
**ماموریت** ➜ مشاهده مأموریت‌ها
**دریافت‌ماموریت** ➜ دریافت پاداش

🔗 **دعوت (همه جا)**
**دعوت** ➜ دریافت لینک دعوت

🐣 **هاپو (همه جا)**
**اسم** [نام] ➜ اسم گذاری هاپو

👑 **دستورات ادمین (روی ریپلای - همه جا):**
**افزایش پوینت** [مقدار] ➕
**کاهش پوینت** [مقدار] ➖
**افزایش لول** [مقدار] ⬆️
**کاهش لول** [مقدار] ⬇️
**همگانی** [متن] : ارسال پیام به تمام اعضا 📢
**افزودن ادمین** ➜ ادمین کردن کاربر
**حذف ادمین** ➜ حذف ادمین
**حذف کاربر** ➜ حذف کاربر
    """
    await message.reply(help_text)

# ==================== پنل مدیریت ====================

@router.message(F.text == "پنل")
@router.message(F.text == "🔐 پنل مدیریت")
async def admin_panel(message: Message):
    """پنل مدیریت - هم در پیوی هم گروه"""
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    await message.reply(
        "🔐 **پنل مدیریت**\n\n"
        "👑 **دستورات ادمین (روی ریپلای - همه جا):**\n\n"
        "**افزایش پوینت** [مقدار] ➕\n"
        "**کاهش پوینت** [مقدار] ➖\n"
        "**افزایش لول** [مقدار] ⬆️\n"
        "**کاهش لول** [مقدار] ⬇️\n"
        "**همگانی** [متن] : ارسال پیام به تمام اعضا 📢\n\n"
        "**افزودن ادمین** ➜ ادمین کردن کاربر\n"
        "**حذف ادمین** ➜ حذف ادمین\n"
        "**حذف کاربر** ➜ حذف کاربر",
        reply_markup=admin_menu() if is_private(message) else None
    )

# ==================== دستورات ادمین ====================

@router.message(F.text.startswith("افزایش پوینت"))
async def add_points_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ فرمت: افزایش پوینت 100")
        return
    
    try:
        amount = float(parts[2])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    if not user:
        await message.reply("❌ کاربر پیدا نشد!")
        return
    
    User.update(target_id, hop_point=user["hop_point"] + amount)
    await message.reply(f"✅ {amount:.1f} هاپ به {user['first_name']} اضافه شد!")

@router.message(F.text.startswith("کاهش پوینت"))
async def remove_points_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ فرمت: کاهش پوینت 100")
        return
    
    try:
        amount = float(parts[2])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    if not user:
        await message.reply("❌ کاربر پیدا نشد!")
        return
    
    User.update(target_id, hop_point=max(0, user["hop_point"] - amount))
    await message.reply(f"✅ {amount:.1f} هاپ از {user['first_name']} کم شد!")

@router.message(F.text.startswith("افزایش لول"))
async def add_level_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ فرمت: افزایش لول 5")
        return
    
    try:
        level = int(parts[2])
    except:
        await message.reply("❌ عدد نامعتبر!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    if not user:
        await message.reply("❌ کاربر پیدا نشد!")
        return
    
    User.update(target_id, level=user["level"] + level)
    await message.reply(f"✅ سطح {user['first_name']} به {user['level'] + level} افزایش یافت!")

@router.message(F.text.startswith("کاهش لول"))
async def remove_level_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ فرمت: کاهش لول 5")
        return
    
    try:
        level = int(parts[2])
    except:
        await message.reply("❌ عدد نامعتبر!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    if not user:
        await message.reply("❌ کاربر پیدا نشد!")
        return
    
    new_level = max(1, user["level"] - level)
    User.update(target_id, level=new_level)
    await message.reply(f"✅ سطح {user['first_name']} به {new_level} کاهش یافت!")

@router.message(F.text == "افزودن ادمین")
async def add_admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    User.update(target_id, is_admin=1)
    await message.reply(f"✅ کاربر ادمین شد!")

@router.message(F.text == "حذف ادمین")
async def remove_admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    User.update(target_id, is_admin=0)
    await message.reply(f"✅ دسترسی ادمین برداشته شد!")

@router.message(F.text == "حذف کاربر")
async def delete_user_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (target_id,))
    conn.commit()
    conn.close()
    await message.reply(f"✅ کاربر حذف شد!")

# ==================== ارسال همگانی ====================

@router.message(F.text.startswith("همگانی"))
async def broadcast_command(message: Message, bot):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ فرمت: همگانی [متن]")
        return
    
    broadcast_text = parts[1]
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    sent = 0
    failed = 0
    
    await message.reply(f"📢 در حال ارسال پیام به {len(users)} کاربر...")
    
    for user in users:
        try:
            await bot.send_message(user["id"], f"📢 **پیام همگانی**\n\n{broadcast_text}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await message.reply(f"✅ پیام به {sent} کاربر ارسال شد!\n❌ {failed} کاربر دریافت نکردند.")

# ==================== دکمه‌های هاپو (فقط پیوی) ====================

@router.callback_query(F.data == "feed_hopo")
async def feed_hopo_callback(callback: CallbackQuery):
    if is_group(callback.message):
        await callback.answer("❌ این دکمه فقط در پیوی کار میکنه!", show_alert=True)
        return
    
    user = User.get(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ ثبت‌نام کن!")
        return
    
    has_food = Inventory.use_item(callback.from_user.id, "غذا")
    if not has_food:
        await callback.answer("❌ غذایی نداری! از فروشگاه بخر.", show_alert=True)
        return
    
    hunger = min(100, user["hopo_hunger"] + 20)
    happiness = min(100, user["hopo_happiness"] + 5)
    exp = user["exp"] + 5
    
    level = user["level"]
    if exp >= level * 20:
        level += 1
        exp = 0
        await callback.message.answer(f"🎉 **سطح {level}** شدی!")
    
    User.update(
        callback.from_user.id,
        hopo_hunger=hunger,
        hopo_happiness=happiness,
        exp=exp,
        level=level
    )
    
    await callback.message.edit_text(f"🍖 به هاپو غذا دادی! گرسنگی: {hunger}%")
    await callback.answer()

@router.callback_query(F.data == "sleep_hopo")
async def sleep_hopo_callback(callback: CallbackQuery):
    if is_group(callback.message):
        await callback.answer("❌ این دکمه فقط در پیوی کار میکنه!", show_alert=True)
        return
    
    user = User.get(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ ثبت‌نام کن!")
        return
    
    energy = min(100, user["hopo_energy"] + 30)
    User.update(callback.from_user.id, hopo_energy=energy)
    
    await callback.message.edit_text(f"😴 هاپو خوابید! انرژی: {energy}%")
    await callback.answer()

@router.callback_query(F.data == "play_hopo")
async def play_hopo_callback(callback: CallbackQuery):
    if is_group(callback.message):
        await callback.answer("❌ این دکمه فقط در پیوی کار میکنه!", show_alert=True)
        return
    
    user = User.get(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ ثبت‌نام کن!")
        return
    
    energy = max(0, user["hopo_energy"] - 10)
    happiness = min(100, user["hopo_happiness"] + 15)
    
    reward = random.choice([0, 0, 5, 10, 20])
    if reward > 0:
        User.update(callback.from_user.id, hop_point=user["hop_point"] + reward)
    
    User.update(callback.from_user.id, hopo_energy=energy, hopo_happiness=happiness)
    
    reward_text = f" و {reward} هاپ گرفتی!" if reward > 0 else ""
    await callback.message.edit_text(f"🎮 با هاپو بازی کردی! خوشحالی: {happiness}%{reward_text}")
    await callback.answer()

@router.callback_query(F.data == "hatch_hopo")
async def hatch_hopo_callback(callback: CallbackQuery):
    if is_group(callback.message):
        await callback.answer("❌ این دکمه فقط در پیوی کار میکنه!", show_alert=True)
        return
    
    user = User.get(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ ثبت‌نام کن!")
        return
    
    if user["hopo_stage"] != "egg":
        await callback.answer("🐣 هاپوت دیگه تخم نیست!", show_alert=True)
        return
    
    if not user["hopo_hatch_time"]:
        await callback.answer("❌ تخمی نداری!", show_alert=True)
        return
    
    hatch_time = datetime.fromtimestamp(user["hopo_hatch_time"])
    if datetime.now() < hatch_time:
        remain = hatch_time - datetime.now()
        hours = remain.seconds // 3600
        minutes = (remain.seconds % 3600) // 60
        await callback.answer(f"⏳ {hours} ساعت و {minutes} دقیقه مونده!", show_alert=True)
        return
    
    breeds = ["معمولی", "طلایی", "کریستالی", "افسانه‌ای"]
    weights = [70, 15, 10, 5]
    breed = random.choices(breeds, weights=weights)[0]
    
    User.update(
        callback.from_user.id,
        hopo_stage="baby",
        hopo_breed=breed,
        hopo_health=100,
        hopo_happiness=100,
        hopo_energy=100,
        hopo_hunger=100
    )
    
    await callback.message.edit_text(
        f"🥚 **تخم باز شد!**\n\n"
        f"🐣 یه هاپوی **{breed}** به دنیا اومد!\n"
        f"📛 اسمش رو بذار: **اسم** [نام]"
    )
    await callback.answer()

# ==================== بررسی عضویت در کانال ====================

@router.callback_query(F.data == "check_channels")
async def check_channels_callback(callback: CallbackQuery, bot):
    not_joined = await check_channels(bot, callback.from_user.id)
    if not_joined:
        await callback.answer("❌ هنوز عضو همه کانال‌ها نشدی!", show_alert=True)
    else:
        await callback.message.edit_text("✅ عضویت شما تأیید شد! حالا می‌تونی از ربات استفاده کنی.")
        await callback.answer()

# ==================== هندلر پیام‌های معمولی در گروه ====================

@router.message()
async def handle_group_messages(message: Message, bot):
    """هندلر پیام‌های معمولی در گروه - فقط برای ثبت آمار"""
    
    if not is_group(message):
        return
    
    GroupMessage.add(message.from_user.id, message.chat.id, message.text or "")
    
    user = User.get(message.from_user.id)
    if user:
        msg_count = GroupMessage.get_user_count(message.from_user.id, message.chat.id)
        if msg_count % 10 == 0:
            User.update(message.from_user.id, hop_point=user["hop_point"] + 1)
            await message.reply(f"🌟 {user['first_name']} به خاطر فعالیت در گروه ۱ هاپ گرفتی!")
