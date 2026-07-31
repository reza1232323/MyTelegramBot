from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
import hashlib

router = Router()

# ==================== دیتابیس موقت میزهای بازی ====================

game_tables = {}

# ==================== فیلتر تشخیص پیوی/گروه ====================

def is_private(message: Message) -> bool:
    return message.chat.type == "private"

def is_group(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

# ==================== ثبت‌نام خودکار ====================

def get_or_create_user_silent(user_id, username, first_name):
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        invite_code = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
        hatch_time = (datetime.now().timestamp() + 21600)
        cursor.execute('''
            INSERT INTO users (id, username, first_name, invite_code, hopo_hatch_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, invite_code, hatch_time))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
    
    conn.close()
    return dict(user)

# ==================== شروع (فقط پیوی) ====================

@router.message(Command("start"))
async def start_command(message: Message, bot):
    if is_group(message):
        return
    
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    await message.reply(
        f"🎉 **به میوپی خوش اومدی {user['first_name']}!**\n\n"
        f"🐱 هر ۵ دقیقه با دستور **میو** امتیاز بگیر.\n"
        f"🎰 برای بازی به گروه برو و **کازینو** رو بزن.\n"
        f"📖 راهنما: **راهنما**",
        reply_markup=main_menu()
    )

# ==================== دکمه خانه (فقط پیوی) ====================

@router.message(F.text == "🏠 خانه")
async def home_command(message: Message, bot):
    if is_private(message):
        await start_command(message, bot)

# ==================== دستور میو ====================

@router.message(F.text == "میو")
async def get_hop_command(message: Message, bot):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    if is_admin(message.from_user.id):
        await message.reply("👑 شما ادمین هستید! میو پوینت بینهایت.")
        return
    
    if is_private(message):
        not_joined = await check_channels(bot, message.from_user.id)
        if not_joined:
            await message.reply(
                "⚠️ برای دریافت میو ابتدا در کانال‌های زیر عضو شوید:",
                reply_markup=channel_check_kb(not_joined)
            )
            return
    
    if not can_claim_hop(user):
        remain = int(300 - (time.time() - user["last_hop_claim"]))
        minutes = remain // 60
        seconds = remain % 60
        await message.reply(f"⏳ صبر کن! {minutes} دقیقه و {seconds} ثانیه مونده")
        return
    
    hop_reward = random.randint(150, 350)
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
    
    await message.reply(f"🎉 {hop_reward} میو پوینت گرفتی!{gem_text}{bonus_text}")

# ==================== پروفایل ====================

@router.message(F.text == "هاپوهام")
@router.message(F.text == "🐣 هایوی من")
async def my_profile(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    if user["hopo_stage"] != "egg":
        hunger = max(0, user["hopo_hunger"] - 5)
        happiness = max(0, user["hopo_happiness"] - 2)
        User.update(message.from_user.id, hopo_hunger=hunger, hopo_happiness=happiness)
        user = User.get(message.from_user.id)
    
    admin_text = "\n👑 **ادمین - میو بینهایت**" if is_admin(message.from_user.id) else ""
    
    await message.reply(
        format_profile(user, group_mode=is_group(message)) + admin_text,
        reply_markup=inline_home() if is_private(message) else None
    )

# ==================== مشاهده پروفایل کاربر دیگر ====================

@router.message(F.text == "هاپ هاش")
async def user_profile_reply(message: Message):
    if not message.reply_to_message:
        await message.reply("❌ روی پیام یک کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    
    if not user:
        await message.reply("❌ کاربر در ربات ثبت‌نام نکرده!")
        return
    
    admin_text = "\n👑 **ادمین - میو بینهایت**" if is_admin(target_id) else ""
    
    await message.reply(format_profile(user, group_mode=is_group(message)) + admin_text)

# ==================== لیدربرد ====================

@router.message(F.text == "لیدربرد")
@router.message(F.text == "📊 لیدربرد")
async def leaderboard_command(message: Message):
    if is_group(message):
        users = User.get_group_top_users(message.chat.id, 10)
        await message.reply(format_group_leaderboard(users))
    else:
        users = User.get_top_users(10)
        await message.reply(format_leaderboard(users))

# ==================== گردونه شانس (معمولی) ====================

@router.message(F.text == "گردونه")
@router.message(F.text == "🎡 گردونه شانس")
async def spin_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    prizes = [
        ("🎉 ۵۰ میو!", 50, 0),
        ("🎉 ۲۰ میو!", 20, 0),
        ("🎉 ۱۰۰ میو!", 100, 0),
        ("💎 ۵ جم!", 0, 5),
        ("💎 ۲ جم!", 0, 2),
        ("😞 هیچی!", 0, 0),
        ("⭐ ۵۰۰ میو!", 500, 0),
        ("🥚 تخم طلایی!", 0, 0, "egg")
    ]
    
    if is_admin(message.from_user.id):
        prize = random.choice(prizes)
        if len(prize) > 3:
            result = "🥚 تخم طلایی دریافت کردی!"
        else:
            hop_win, gem_win = prize[1], prize[2]
            if hop_win > 0:
                result = f"{prize[0]} (👑 ادمین - میو بینهایت)"
            elif gem_win > 0:
                User.update(message.from_user.id, hop_gem=user["hop_gem"] + gem_win)
                result = prize[0]
            else:
                result = prize[0]
        await message.reply(f"🎡 **گردونه شانس (👑 ادمین)**\n{result}")
        return
    
    cost = 20
    if user["hop_point"] < cost:
        await message.reply(f"❌ {cost} میو نیاز داری!")
        return
    
    User.update(message.from_user.id, hop_point=user["hop_point"] - cost)
    
    prize = random.choice(prizes)
    
    if len(prize) > 3:
        result = "🥚 تخم طلایی دریافت کردی!"
    else:
        hop_win, gem_win = prize[1], prize[2]
        if hop_win > 0:
            User.update(message.from_user.id, hop_point=user["hop_point"] + hop_win)
            result = f"{prize[0]} (مجموع: {user['hop_point'] - cost + hop_win:.1f} میو)"
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
        "🎮 **بازی‌های میوپی**\n\n"
        "🎲 **تاس** [مبلغ]\n"
        "🎡 **گردونه**\n"
        "♠️ **قمار** [مبلغ]"
    )

# ==================== تاس ====================

@router.message(F.text.startswith("تاس"))
async def dice_game(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: تاس 100")
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    
    if is_admin(message.from_user.id):
        if user_roll > bot_roll:
            result = "🎉 بردی! (👑 ادمین - میو بینهایت)"
        elif user_roll < bot_roll:
            result = "😞 باختی! (👑 ادمین - میو کم نمیشه)"
        else:
            result = "🤝 مساوی شد!"
        await message.reply(
            f"🎲 **تاس (👑 ادمین)**\n"
            f"تو: {user_roll} | ربات: {bot_roll}\n"
            f"{result}"
        )
        return
    
    if user["hop_point"] < bet:
        await message.reply(f"❌ موجودی کافی نیست! داری {user['hop_point']:.1f} میو")
        return
    
    if user_roll > bot_roll:
        win = bet * 1.5
        User.update(message.from_user.id, hop_point=user["hop_point"] + win)
        result = f"🎉 بردی! {win:.1f} میو"
    elif user_roll < bot_roll:
        User.update(message.from_user.id, hop_point=user["hop_point"] - bet)
        result = f"😞 باختی! {bet:.1f} میو"
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
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: قمار 100")
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    cards = ["♠️", "♥️", "♦️", "♣️"]
    user_card = random.choice(cards)
    bot_card = random.choice(cards)
    ranks = {"♠️": 4, "♥️": 3, "♦️": 2, "♣️": 1}
    
    if is_admin(message.from_user.id):
        if ranks[user_card] > ranks[bot_card]:
            result = "🎉 بردی! (👑 ادمین - میو بینهایت)"
        elif ranks[user_card] < ranks[bot_card]:
            result = "😞 باختی! (👑 ادمین - میو کم نمیشه)"
        else:
            result = "🤝 مساوی شد!"
        await message.reply(
            f"♠️ **قمار (👑 ادمین)**\n"
            f"تو: {user_card} | ربات: {bot_card}\n"
            f"{result}"
        )
        return
    
    if user["hop_point"] < bet:
        await message.reply("❌ موجودی کافی نیست!")
        return
    
    if ranks[user_card] > ranks[bot_card]:
        win = bet * 2
        User.update(message.from_user.id, hop_point=user["hop_point"] + win)
        result = f"🎉 بردی! {win:.1f} میو"
    elif ranks[user_card] < ranks[bot_card]:
        User.update(message.from_user.id, hop_point=user["hop_point"] - bet)
        result = f"😞 باختی! {bet:.1f} میو"
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
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT has_dog, dog_level FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    conn.close()
    
    has_dog = result[0] if result else 0
    dog_level = result[1] if result else 0
    
    if is_admin(message.from_user.id):
        if not has_dog:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET has_dog = 1, dog_level = 1 WHERE id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
            await message.reply("🐕 سگ خریداری شد! (👑 ادمین - رایگان)")
        else:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET dog_level = dog_level + 1 WHERE id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
            await message.reply(f"🐕 سگ به سطح {dog_level + 1} ارتقا یافت! (👑 ادمین - رایگان)")
        return
    
    if not has_dog:
        if user["hop_point"] < 100:
            await message.reply("❌ ۱۰۰ میو نیاز داری برای خرید سگ!")
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
            await message.reply(f"❌ {upgrade_cost} میو نیازه برای ارتقا!")
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
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT fishing_rod_level FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    rod_level = result[0] if result else 0
    conn.close()
    
    if is_admin(message.from_user.id):
        if rod_level == 0:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET fishing_rod_level = 1 WHERE id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
            await message.reply("🎣 قلاب خریداری شد! (👑 ادمین - رایگان)")
        else:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET fishing_rod_level = fishing_rod_level + 1 WHERE id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
            await message.reply(f"🎣 قلاب به سطح {rod_level + 1} ارتقا یافت! (👑 ادمین - رایگان)")
        return
    
    if rod_level == 0:
        if user["hop_point"] < 50:
            await message.reply("❌ ۵۰ میو نیاز داری برای خرید قلاب!")
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
            await message.reply(f"❌ {upgrade_cost} میو نیازه!")
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
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT fishing_rod_level, bones FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    conn.close()
    
    rod_level = result[0] if result else 0
    current_bones = result[1] if result else 0
    
    if is_admin(message.from_user.id):
        if rod_level == 0:
            await message.reply("❌ اول قلاب بخر!")
            return
        bone_count = random.randint(5, 15)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET bones = ? WHERE id = ?", (current_bones + bone_count, message.from_user.id))
        conn.commit()
        conn.close()
        await message.reply(f"🦴 {bone_count} استخوان صید کردی! (👑 ادمین - شانس ۱۰۰٪)")
        return
    
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
    get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
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
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    admin_text = "\n👑 **ادمین - میو بینهایت**" if is_admin(message.from_user.id) else ""
    
    await message.reply(
        f"🏦 **بانک میوپی**\n\n"
        f"💰 موجودی: {user['bank_balance']:.1f} میو\n"
        f"📈 سود: {user['bank_interest'] * 100}%\n"
        f"{admin_text}\n\n"
        f"دستورات:\n"
        f"📥 **سپرده** [مبلغ]\n"
        f"📤 **برداشت** [مبلغ]"
    )

@router.message(F.text.startswith("سپرده"))
async def deposit_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: سپرده 100")
        return
    
    try:
        amount = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    if is_admin(message.from_user.id):
        User.update(
            message.from_user.id,
            bank_balance=user["bank_balance"] + amount
        )
        await message.reply(f"✅ {amount:.1f} میو به بانک واریز شد! (👑 ادمین - رایگان)")
        return
    
    if user["hop_point"] < amount:
        await message.reply(f"❌ موجودی کافی نیست! داری {user['hop_point']:.1f} میو")
        return
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] - amount,
        bank_balance=user["bank_balance"] + amount
    )
    
    await message.reply(f"✅ {amount:.1f} میو به بانک واریز شد!")

@router.message(F.text.startswith("برداشت"))
async def withdraw_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: برداشت 100")
        return
    
    try:
        amount = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    if is_admin(message.from_user.id):
        User.update(
            message.from_user.id,
            hop_point=user["hop_point"] + amount,
            bank_balance=user["bank_balance"] - amount
        )
        await message.reply(f"✅ {amount:.1f} میو از بانک برداشت شد! (👑 ادمین - بینهایت)")
        return
    
    if user["bank_balance"] < amount:
        await message.reply(f"❌ موجودی بانک کافی نیست! داری {user['bank_balance']:.1f} میو")
        return
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] + amount,
        bank_balance=user["bank_balance"] - amount
    )
    
    await message.reply(f"✅ {amount:.1f} میو از بانک برداشت شد!")

# ==================== کارخانه ====================

@router.message(F.text == "کارخونه")
@router.message(F.text == "🏭 کارخانه")
async def factory_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    admin_text = "\n👑 **ادمین - ارتقا رایگان**" if is_admin(message.from_user.id) else ""
    
    await message.reply(
        f"🏭 **کارخانه**\n\n"
        f"📊 سطح: {user['factory_level']}\n"
        f"⚡ تولید: {user['factory_production']:.1f} میو در ساعت\n"
        f"{admin_text}\n\n"
        f"دستورات:\n"
        f"📥 **جمع‌کارخانه**\n"
        f"⬆️ **ارتقا‌کارخانه**"
    )

@router.message(F.text == "جمع‌کارخانه")
async def collect_factory_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    if is_admin(message.from_user.id):
        production = 1000
        User.update(
            message.from_user.id,
            hop_point=user["hop_point"] + production,
            factory_last_collect=datetime.now().isoformat()
        )
        await message.reply(f"🏭 {production:.1f} میو از کارخانه جمع کردی! (👑 ادمین - تولید بینهایت)")
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
    
    await message.reply(f"🏭 {production:.1f} میو از کارخانه جمع کردی!")

@router.message(F.text == "ارتقا‌کارخانه")
async def upgrade_factory_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    if is_admin(message.from_user.id):
        User.update(
            message.from_user.id,
            factory_level=user["factory_level"] + 1,
            factory_production=user["factory_production"] + 2
        )
        await message.reply(f"✅ کارخانه به سطح {user['factory_level'] + 1} ارتقا یافت! (👑 ادمین - رایگان)")
        return
    
    cost = (user["factory_level"] + 1) * 100 + 50
    if user["hop_point"] < cost:
        await message.reply(f"❌ {cost} میو نیاز داری!")
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
    items = Shop.get_items()
    
    if is_admin(message.from_user.id):
        await message.reply(format_shop(items) + "\n\n👑 **ادمین - همه آیتم‌ها رایگان**")
    else:
        await message.reply(format_shop(items))

@router.message(F.text.startswith("خرید"))
async def buy_command(message: Message):
    get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
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
    
    if is_admin(message.from_user.id):
        item = Shop.get_item(item_id)
        if not item:
            await message.reply("❌ آیتم پیدا نشد!")
            return
        Inventory.add_item(message.from_user.id, item["name"], quantity)
        await message.reply(f"✅ {quantity} عدد {item['name']} خریداری شد! (👑 ادمین - رایگان)")
        return
    
    result = Shop.buy(message.from_user.id, item_id, quantity)
    await message.reply(result["message"])

# ==================== کیف ====================

@router.message(F.text == "کیف")
@router.message(F.text == "🎒 کیف")
async def inventory_command(message: Message):
    items = Inventory.get_items(message.from_user.id)
    if not items:
        await message.reply("🎒 انبار خالی است!")
        return
    
    text = "🎒 **انبار شما**\n━━━━━━━━━━\n"
    for item in items:
        text += f"{item['item_name']}: {item['quantity']} عدد\n"
    
    if is_admin(message.from_user.id):
        text += "\n👑 **ادمین - همه آیتم‌ها بینهایت**"
    
    await message.reply(text)

# ==================== مأموریت‌ها ====================

@router.message(F.text == "ماموریت")
@router.message(F.text == "🎯 مأموریت‌ها")
async def mission_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
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
        text += f"پاداش: {mission['reward_hop']} میو"
        if mission['reward_gem'] > 0:
            text += f" + {mission['reward_gem']} جم"
        text += f"\nوضعیت: {status}\n━━━━━━━━━━\n"
    
    if is_admin(message.from_user.id):
        text += "\n👑 **ادمین - همه مأموریت‌ها انجام شده**"
    
    text += "\n**دریافت‌ماموریت** - دریافت پاداش"
    await message.reply(text)

@router.message(F.text == "دریافت‌ماموریت")
async def claim_mission_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    if is_admin(message.from_user.id):
        User.update(
            message.from_user.id,
            daily_mission_done=1,
            weekly_mission_done=1,
            hop_point=user["hop_point"] + 1000
        )
        await message.reply("🎁 ۱۰۰۰ میو پاداش مأموریت گرفتی! (👑 ادمین)")
        return
    
    if not user["daily_mission_done"]:
        User.update(
            message.from_user.id,
            daily_mission_done=1,
            hop_point=user["hop_point"] + 50
        )
        await message.reply("🎁 ۵۰ میو پاداش روزانه گرفتی!")
    else:
        await message.reply("❌ امروز پاداش رو گرفتی!")

# ==================== دعوت دوستان ====================

@router.message(F.text == "دعوت")
@router.message(F.text == "🔗 دعوت دوستان")
async def invite_command(message: Message):
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    bot_info = await message.bot.get_me()
    
    admin_text = "\n👑 **ادمین - دعوت‌ها بینهایت**" if is_admin(message.from_user.id) else ""
    
    await message.reply(
        f"🔗 **لینک دعوت اختصاصی**\n\n"
        f"برای هر دعوت ۲۰ میو پاداش می‌گیری!\n"
        f"تعداد دعوت‌ها: {user['invite_count']}{admin_text}\n\n"
        f"https://t.me/{bot_info.username}?start=ref_{user['id']}"
    )

# ==================== راهنما ====================

@router.message(F.text == "راهنما")
@router.message(F.text == "📖 راهنما")
async def help_command(message: Message):
    admin_text = """
👑 **ویژگی‌های ادمین:**
✅ میو بینهایت (هرگز کم نمیشه)
✅ گردونه شانس رایگان
✅ بازی‌ها رایگان
✅ خرید سگ و قلاب رایگان
✅ ارتقای کارخانه رایگان
✅ خرید از فروشگاه رایگان
✅ تولید کارخانه بینهایت
✅ صید استخوان ۱۰۰٪
✅ پاداش مأموریت‌ها ۱۰۰۰ میو
""" if is_admin(message.from_user.id) else ""
    
    help_text = f"""
📖 **راهنمای کامل ربات میوپی**

🐾 **دستورات اصلی (همه جا)**
**میو** ➜ دریافت میو (هر ۵ دقیقه)
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
{admin_text}
    """
    await message.reply(help_text)

# ==================== پنل مدیریت ====================

@router.message(F.text == "پنل")
@router.message(F.text == "🔐 پنل مدیریت")
async def admin_panel(message: Message):
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
    await message.reply(f"✅ {amount:.1f} میو به {user['first_name']} اضافه شد!")

@router.message(F.text.startswith("کاهش پوینت"))
async def remove_points_admin(message: Message):
    if not is_admin(message.from_user.id):
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
    
    if is_admin(target_id):
        await message.reply("⛔ نمی‌توانید پوینت ادمین دیگر را کم کنید!")
        return
    
    User.update(target_id, hop_point=max(0, user["hop_point"] - amount))
    await message.reply(f"✅ {amount:.1f} میو از {user['first_name']} کم شد!")

@router.message(F.text.startswith("افزایش لول"))
async def add_level_admin(message: Message):
    if not is_admin(message.from_user.id):
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
    
    if is_admin(target_id):
        await message.reply("⛔ نمی‌توانید لول ادمین دیگر را کم کنید!")
        return
    
    new_level = max(1, user["level"] - level)
    User.update(target_id, level=new_level)
    await message.reply(f"✅ سطح {user['first_name']} به {new_level} کاهش یافت!")

@router.message(F.text == "افزودن ادمین")
async def add_admin_command(message: Message):
    if not is_admin(message.from_user.id):
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
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    
    if is_admin(target_id):
        await message.reply("⛔ نمی‌توانید ادمین را حذف کنید!")
        return
    
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
    
    user = get_or_create_user_silent(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    if is_admin(callback.from_user.id):
        hunger = min(100, user["hopo_hunger"] + 20)
        happiness = min(100, user["hopo_happiness"] + 5)
        User.update(
            callback.from_user.id,
            hopo_hunger=hunger,
            hopo_happiness=happiness
        )
        await callback.message.edit_text(f"🍖 به هاپو غذا دادی! گرسنگی: {hunger}% (👑 ادمین - بدون نیاز به غذا)")
        await callback.answer()
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
    
    user = get_or_create_user_silent(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    energy = min(100, user["hopo_energy"] + 30)
    User.update(callback.from_user.id, hopo_energy=energy)
    
    await callback.message.edit_text(f"😴 هاپو خوابید! انرژی: {energy}%")
    await callback.answer()

@router.callback_query(F.data == "play_hopo")
async def play_hopo_callback(callback: CallbackQuery):
    if is_group(callback.message):
        await callback.answer("❌ این دکمه فقط در پیوی کار میکنه!", show_alert=True)
        return
    
    user = get_or_create_user_silent(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    energy = max(0, user["hopo_energy"] - 10)
    happiness = min(100, user["hopo_happiness"] + 15)
    
    reward = random.choice([0, 0, 5, 10, 20])
    if reward > 0:
        User.update(callback.from_user.id, hop_point=user["hop_point"] + reward)
    
    User.update(callback.from_user.id, hopo_energy=energy, hopo_happiness=happiness)
    
    reward_text = f" و {reward} میو گرفتی!" if reward > 0 else ""
    await callback.message.edit_text(f"🎮 با هاپو بازی کردی! خوشحالی: {happiness}%{reward_text}")
    await callback.answer()

@router.callback_query(F.data == "hatch_hopo")
async def hatch_hopo_callback(callback: CallbackQuery):
    if is_group(callback.message):
        await callback.answer("❌ این دکمه فقط در پیوی کار میکنه!", show_alert=True)
        return
    
    user = get_or_create_user_silent(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    if is_admin(callback.from_user.id):
        if user["hopo_stage"] != "egg":
            await callback.answer("🐣 هاپوت دیگه تخم نیست!", show_alert=True)
            return
        breeds = ["معمولی", "طلایی", "کریستالی", "افسانه‌ای"]
        breed = random.choice(breeds)
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
            f"🐣 یه هاپوی **{breed}** به دنیا اومد! (👑 ادمین - فوری)"
        )
        await callback.answer()
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

# ======================================================================================
# ============================ بخش کازینو گروهی (گردونه) ==============================
# ======================================================================================

# ==================== کازینو (منوی اصلی) ====================

@router.message(F.text == "کازینو")
@router.message(F.text == "🎰 کازینو")
async def casino_menu(message: Message):
    if is_private(message):
        await message.reply("🎰 کازینو فقط در گروه قابل استفاده است!")
        return
    
    user = get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎡 گردونه شانس", callback_data="casino_spin")],
            [InlineKeyboardButton(text="🎲 تاس", callback_data="casino_dice")],
            [InlineKeyboardButton(text="♠️ قمار میوپی", callback_data="casino_gamble")],
            [InlineKeyboardButton(text="💎 معدن الماس", callback_data="casino_mine")],
            [InlineKeyboardButton(text="📊 میزهای فعال", callback_data="casino_tables")]
        ]
    )
    
    await message.reply(
        f"🎰 **کازینو میوپی**\n\n"
        f"👤 {user['first_name']}\n"
        f"💰 میو پوینت: {user['hop_point']:,}\n\n"
        f"لطفا بازی مورد نظر را انتخاب کنید!",
        reply_markup=keyboard
    )

# ==================== گردونه شانس گروهی (ساخت میز) ====================

@router.callback_query(F.data == "casino_spin")
async def casino_spin_start(callback: CallbackQuery):
    if is_private(callback.message):
        await callback.answer("❌ این بخش فقط در گروه کار میکنه!", show_alert=True)
        return
    
    user = get_or_create_user_silent(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    if user["hop_point"] < 100:
        await callback.answer("❌ حداقل ۱۰۰ میو پوینت نیاز داری!", show_alert=True)
        return
    
    table_id = f"spin_{callback.from_user.id}_{int(time.time())}"
    
    game_tables[table_id] = {
        "creator": callback.from_user.id,
        "creator_name": callback.from_user.first_name,
        "game_type": "spin",
        "bet": 0,
        "max_players": 1,
        "players": [],
        "status": "setting_bet",
        "choices": {},
        "winning_emoji": None,
        "created_at": time.time(),
        "start_time": None,
        "chat_id": callback.message.chat.id,
        "message_id": callback.message.message_id
    }
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 تعیین مبلغ ورودی", callback_data=f"spin_set_bet_{table_id}")],
            [InlineKeyboardButton(text="❌ لغو", callback_data=f"spin_cancel_{table_id}")]
        ]
    )
    
    await callback.message.edit_text(
        f"🎡 **گردونه شانس**\n\n"
        f"لطفا میز قمار را بچینید!\n\n"
        f"💰 مبلغ ورودی: درحال تعیین\n"
        f"👥 تعداد بازیکن: تعیین نشده\n\n"
        f"👤 سازنده: {callback.from_user.first_name}",
        reply_markup=keyboard
    )
    await callback.answer()

# ==================== تعیین مبلغ ورودی ====================

@router.callback_query(F.data.startswith("spin_set_bet_"))
async def spin_set_bet(callback: CallbackQuery):
    table_id = callback.data.replace("spin_set_bet_", "")
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز منقضی شده!", show_alert=True)
        return
    
    if table["creator"] != callback.from_user.id:
        await callback.answer("❌ فقط سازنده میز میتواند این کار را کند!", show_alert=True)
        return
    
    table["status"] = "waiting_bet"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"spin_back_{table_id}")]
        ]
    )
    
    await callback.message.edit_text(
        f"🎡 **گردونه شانس**\n\n"
        f"💰 لطفا مبلغ ورودی را در جواب همین پیام وارد کنید\n"
        f"مثال: 500\n\n"
        f"حداقل: ۱۰۰ | حداکثر: ۱۰۰۰۰۰",
        reply_markup=keyboard
    )
    await callback.answer()

# ==================== دریافت مبلغ ورودی ====================

# این هندلر داخل همان @router.message(F.text) اصلی مدیریت میشه
# باید توی بخش دریافت مبلغ ورودی، چک کنه که کاربر در حال تنظیم میزه

# ==================== تنظیم تعداد بازیکن ====================

@router.callback_query(F.data.startswith("spin_set_players_"))
async def spin_set_players(callback: CallbackQuery):
    table_id = callback.data.replace("spin_set_players_", "")
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز منقضی شده!", show_alert=True)
        return
    
    if table["creator"] != callback.from_user.id:
        await callback.answer("❌ فقط سازنده میز میتواند این کار را کند!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="۱ نفر", callback_data=f"spin_players_{table_id}_1")],
            [InlineKeyboardButton(text="۲ نفر", callback_data=f"spin_players_{table_id}_2")],
            [InlineKeyboardButton(text="۳ نفر", callback_data=f"spin_players_{table_id}_3")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"spin_back_{table_id}")]
        ]
    )
    
    await callback.message.edit_text(
        f"🎡 **گردونه شانس**\n\n"
        f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n\n"
        f"👥 تعداد بازیکن مورد نظر را انتخاب کنید:",
        reply_markup=keyboard
    )
    await callback.answer()

# ==================== تنظیم تعداد بازیکن نهایی ====================

@router.callback_query(F.data.startswith("spin_players_"))
async def spin_set_players_count(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) >= 5:
        table_id = f"{parts[2]}_{parts[3]}_{parts[4]}"
        count = int(parts[5])
    else:
        table_id = f"{parts[2]}_{parts[3]}"
        count = int(parts[4])
    
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز پیدا نشد!", show_alert=True)
        return
    
    if table["creator"] != callback.from_user.id:
        await callback.answer("❌ فقط سازنده میز میتواند این کار را کند!", show_alert=True)
        return
    
    table["max_players"] = count
    table["status"] = "waiting_players"
    table["players"] = [callback.from_user.id]
    
    user = User.get(callback.from_user.id)
    if user:
        User.update(callback.from_user.id, hop_point=user["hop_point"] - table["bet"])
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ دعوت بازیکن", callback_data=f"spin_invite_{table_id}")],
            [InlineKeyboardButton(text="🎯 شروع بازی", callback_data=f"spin_start_{table_id}")],
            [InlineKeyboardButton(text="💰 تغییر مبلغ", callback_data=f"spin_set_bet_{table_id}")],
            [InlineKeyboardButton(text="👥 تغییر تعداد", callback_data=f"spin_set_players_{table_id}")],
            [InlineKeyboardButton(text="❌ لغو", callback_data=f"spin_cancel_{table_id}")]
        ]
    )
    
    await callback.message.edit_text(
        f"🎡 **گردونه شانس**\n\n"
        f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n"
        f"👥 تعداد بازیکن: ۱/{count}\n\n"
        f"👤 بازیکنان:\n"
        f"• {callback.from_user.first_name} ✅\n\n"
        f"برای دعوت بازیکنان یا شروع بازی کلیک کنید!",
        reply_markup=keyboard
    )
    await callback.answer()

# ==================== دعوت بازیکن ====================

@router.callback_query(F.data.startswith("spin_invite_"))
async def spin_invite_player(callback: CallbackQuery):
    table_id = callback.data.replace("spin_invite_", "")
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز منقضی شده!", show_alert=True)
        return
    
    if table["creator"] != callback.from_user.id:
        await callback.answer("❌ فقط سازنده میز میتواند دعوت کند!", show_alert=True)
        return
    
    if len(table["players"]) >= table["max_players"]:
        await callback.answer("❌ تعداد بازیکن کامل شده!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ پیوستن به بازی", callback_data=f"spin_join_{table_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"spin_back_{table_id}")]
        ]
    )
    
    await callback.message.edit_text(
        f"🎡 **گردونه شانس**\n\n"
        f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n"
        f"👥 تعداد بازیکن: {len(table['players'])}/{table['max_players']}\n\n"
        f"برای پیوستن به بازی، روی دکمه **پیوستن** کلیک کنید!",
        reply_markup=keyboard
    )
    await callback.answer()

# ==================== پیوستن به بازی ====================

@router.callback_query(F.data.startswith("spin_join_"))
async def spin_join_game(callback: CallbackQuery):
    table_id = callback.data.replace("spin_join_", "")
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز منقضی شده!", show_alert=True)
        return
    
    if callback.from_user.id in table["players"]:
        await callback.answer("❌ شما قبلاً به این بازی پیوسته‌اید!", show_alert=True)
        return
    
    if len(table["players"]) >= table["max_players"]:
        await callback.answer("❌ تعداد بازیکن کامل شده!", show_alert=True)
        return
    
    user = User.get(callback.from_user.id)
    if not user or user["hop_point"] < table["bet"]:
        await callback.answer(f"❌ موجودی کافی نیست! نیاز به {table['bet']:,} میو پوینت", show_alert=True)
        return
    
    table["players"].append(callback.from_user.id)
    User.update(callback.from_user.id, hop_point=user["hop_point"] - table["bet"])
    
    players_text = ""
    for pid in table["players"]:
        player = User.get(pid)
        if player:
            players_text += f"• {player['first_name']} ✅\n"
    
    if len(table["players"]) >= table["max_players"]:
        table["status"] = "full"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎯 شروع بازی", callback_data=f"spin_start_{table_id}")]
            ]
        )
        
        await callback.message.edit_text(
            f"🎡 **گردونه شانس**\n\n"
            f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n"
            f"👥 تعداد بازیکن: {len(table['players'])}/{table['max_players']} (کامل)\n\n"
            f"👤 بازیکنان:\n{players_text}\n\n"
            f"برای شروع بازی کلیک کنید!",
            reply_markup=keyboard
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"➕ دعوت بازیکن ({len(table['players'])}/{table['max_players']})", callback_data=f"spin_invite_{table_id}")],
                [InlineKeyboardButton(text="🎯 شروع بازی", callback_data=f"spin_start_{table_id}")],
                [InlineKeyboardButton(text="💰 تغییر مبلغ", callback_data=f"spin_set_bet_{table_id}")],
                [InlineKeyboardButton(text="❌ لغو", callback_data=f"spin_cancel_{table_id}")]
            ]
        )
        
        await callback.message.edit_text(
            f"🎡 **گردونه شانس**\n\n"
            f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n"
            f"👥 تعداد بازیکن: {len(table['players'])}/{table['max_players']}\n\n"
            f"👤 بازیکنان:\n{players_text}",
            reply_markup=keyboard
        )
    
    await callback.answer("✅ به بازی پیوستید!")

# ==================== شروع بازی گردونه ====================

@router.callback_query(F.data.startswith("spin_start_"))
async def spin_start_game(callback: CallbackQuery):
    table_id = callback.data.replace("spin_start_", "")
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز منقضی شده!", show_alert=True)
        return
    
    if table["creator"] != callback.from_user.id:
        await callback.answer("❌ فقط سازنده میز میتواند بازی را شروع کند!", show_alert=True)
        return
    
    if len(table["players"]) < 1:
        await callback.answer("❌ حداقل یک بازیکن نیاز است!", show_alert=True)
        return
    
    emojis = ["🐱", "🐶", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🐦", "🐤", "🐣", "🐥", "🦆", "🦅", "🦉"]
    
    winning_emoji = random.choice(emojis)
    table["winning_emoji"] = winning_emoji
    table["status"] = "playing"
    table["choices"] = {}
    table["start_time"] = time.time()
    
    for pid in table["players"]:
        try:
            keyboard = InlineKeyboardMarkup(row_width=6)
            buttons = []
            for emoji in emojis[:24]:
                buttons.append(InlineKeyboardButton(text=emoji, callback_data=f"spin_emoji_{table_id}_{emoji}"))
                if len(buttons) == 6:
                    keyboard.inline_keyboard.append(buttons)
                    buttons = []
            if buttons:
                keyboard.inline_keyboard.append(buttons)
            
            await callback.bot.send_message(
                pid,
                f"🎡 **گردونه شانس**\n\n"
                f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n"
                f"👥 تعداد بازیکن: {len(table['players'])}\n\n"
                f"لطفا ایموجی خود را انتخاب کنید!\n"
                f"⏱️ فقط ۶۰ ثانیه فرصت دارید...",
                reply_markup=keyboard
            )
        except:
            pass
    
    await callback.message.edit_text(
        f"🎡 **گردونه شانس**\n\n"
        f"✅ بازی شروع شد!\n"
        f"💰 مبلغ ورودی: {table['bet']:,} میو پوینت\n"
        f"👥 تعداد بازیکن: {len(table['players'])}\n\n"
        f"⏱️ بازیکنان در حال انتخاب ایموجی هستند..."
    )
    await callback.answer()

# ==================== انتخاب ایموجی ====================

@router.callback_query(F.data.startswith("spin_emoji_"))
async def spin_register_emoji(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) >= 5:
        table_id = f"{parts[2]}_{parts[3]}_{parts[4]}"
        emoji = parts[5]
    else:
        table_id = f"{parts[2]}_{parts[3]}"
        emoji = parts[4]
    
    table = game_tables.get(table_id)
    if not table:
        await callback.answer("❌ میز منقضی شده!", show_alert=True)
        return
    
    if callback.from_user.id not in table["players"]:
        await callback.answer("❌ شما در این بازی نیستید!", show_alert=True)
        return
    
    if table["status"] != "playing":
        await callback.answer("❌ بازی به پایان رسیده!", show_alert=True)
        return
    
    table["choices"][callback.from_user.id] = emoji
    
    await callback.message.edit_text(
        f"✅ ایموجی {emoji} انتخاب شد!\n"
        f"⏱️ منتظر بقیه بازیکنان..."
    )
    await callback.answer(f"✅ ایموجی {emoji} ثبت شد!")

# ==================== میزهای فعال ====================

@router.callback_query(F.data == "casino_tables")
async def show_active_tables(callback: CallbackQuery):
    active_tables = []
    for tid, table in game_tables.items():
        if table["status"] in ["waiting_players", "full"]:
            active_tables.append({
                "id": tid,
                "creator": table["creator_name"],
                "bet": table["bet"],
                "players": len(table["players"]),
                "max_players": table["max_players"],
                "status": table["status"]
            })
    
    if not active_tables:
        await callback.answer("📭 هیچ میز فعالی وجود ندارد!", show_alert=True)
        return
    
    text = "📊 **میزهای فعال**\n\n"
    for t in active_tables[:5]:
        status_text = "🟢 در انتظار" if t["status"] == "waiting_players" else "🔵 کامل"
        text += f"🆔 {t['id'][:10]}...\n"
        text += f"👤 سازنده: {t['creator']}\n"
        text += f"💰 {t['bet']:,} | 👥 {t['players']}/{t['max_players']}\n"
        text += f"وضعیت: {status_text}\n━━━━━━━━━━\n"
    
    await callback.message.edit_text(text)
    await callback.answer()

# ==================== لغو میز ====================

@router.callback_query(F.data.startswith("spin_cancel_"))
async def spin_cancel_table(callback: CallbackQuery):
    table_id = callback.data.replace("spin_cancel_", "")
    table = game_tables.get(table_id)
    
    if not table:
        await callback.answer("❌ میز پیدا نشد!", show_alert=True)
        return
    
    if table["creator"] != callback.from_user.id:
        await callback.answer("❌ فقط سازنده میز میتواند آن را لغو کند!", show_alert=True)
        return
    
    for pid in table["players"]:
        user = User.get(pid)
        if user:
            User.update(pid, hop_point=user["hop_point"] + table["bet"])
    
    del game_tables[table_id]
    
    await callback.message.edit_text("❌ میز لغو شد! پول به بازیکنان برگشت.")
    await callback.answer()

# ==================== بازگشت ====================

@router.callback_query(F.data.startswith("spin_back_"))
async def spin_back(callback: CallbackQuery):
    await casino_menu(callback.message)
    await callback.answer()

# ==================== سایر بخش‌های کازینو ====================

@router.callback_query(F.data == "casino_dice")
async def casino_dice(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎲 **تاس**\n\n"
        "در حال توسعه...\n"
        "به زودی!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino_back")]]
        )
    )
    await callback.answer()

@router.callback_query(F.data == "casino_gamble")
async def casino_gamble(callback: CallbackQuery):
    await callback.message.edit_text(
        "♠️ **قمار میوپی**\n\n"
        "در حال توسعه...\n"
        "به زودی!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino_back")]]
        )
    )
    await callback.answer()

@router.callback_query(F.data == "casino_mine")
async def casino_mine(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 **معدن الماس**\n\n"
        "در حال توسعه...\n"
        "به زودی!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino_back")]]
        )
    )
    await callback.answer()

@router.callback_query(F.data == "casino_back")
async def casino_back(callback: CallbackQuery):
    await casino_menu(callback.message)
    await callback.answer()

# ==================== تایمر پایان بازی ====================

async def check_spin_timer():
    while True:
        await asyncio.sleep(5)
        current_time = time.time()
        
        for table_id, table in list(game_tables.items()):
            if table["status"] == "playing":
                if table.get("start_time") and current_time - table["start_time"] > 60:
                    table["status"] = "finished"
                    winning_emoji = table.get("winning_emoji", "🐱")
                    
                    winners = []
                    for pid, choice in table.get("choices", {}).items():
                        if choice == winning_emoji:
                            winners.append(pid)
                    
                    total_pot = table["bet"] * len(table["players"])
                    
                    for pid in table["players"]:
                        try:
                            if pid in winners:
                                prize = total_pot // len(winners) if winners else 0
                                if prize > 0:
                                    user = User.get(pid)
                                    if user:
                                        User.update(pid, hop_point=user["hop_point"] + prize)
                                result_text = f"🎉 **تبریک! شما برنده شدید!**\n"
                                result_text += f"💰 جایزه: {prize:,} میو پوینت\n"
                                result_text += f"🎯 ایموجی برنده: {winning_emoji}"
                            else:
                                result_text = f"😞 شما برنده نشدید!\n"
                                result_text += f"🎯 ایموجی برنده: {winning_emoji}"
                            
                            await callback.bot.send_message(pid, f"🎡 **نتیجه گردونه شانس**\n\n{result_text}")
                        except:
                            pass
                    
                    if winners:
                        winner_names = []
                        for wid in winners:
                            user = User.get(wid)
                            if user:
                                winner_names.append(user["first_name"])
                        prize_per_winner = total_pot // len(winners) if winners else 0
                        
                        result_text = f"🎡 **نتیجه گردونه شانس**\n\n"
                        result_text += f"🎯 ایموجی برنده: {winning_emoji}\n"
                        result_text += f"👑 برندگان: {', '.join(winner_names)}\n"
                        result_text += f"💰 هر کدام: {prize_per_winner:,} میو پوینت"
                    else:
                        result_text = f"🎡 **نتیجه گردونه شانس**\n\n"
                        result_text += f"😞 هیچکس برنده نشد!\n"
                        result_text += f"🎯 ایموجی برنده: {winning_emoji}"
                    
                    try:
                        await callback.bot.send_message(table["chat_id"], result_text)
                    except:
                        pass
                    
                    del game_tables[table_id]

# ==================== هندلر پیام‌های معمولی ====================

@router.message()
async def handle_group_messages(message: Message, bot):
    if not is_group(message):
        return
    
    get_or_create_user_silent(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    GroupMessage.add(message.from_user.id, message.chat.id, message.text or "")
    
    # چک کردن ورودی مبلغ برای میزهای گردونه
    for tid, table in game_tables.items():
        if table["status"] == "waiting_bet" and table["creator"] == message.from_user.id:
            try:
                bet = int(message.text.strip())
                if 100 <= bet <= 100000:
                    table["bet"] = bet
                    table["status"] = "setting_players"
                    
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="👥 تعیین تعداد بازیکن", callback_data=f"spin_set_players_{tid}")],
                            [InlineKeyboardButton(text="💰 تغییر مبلغ ورودی", callback_data=f"spin_set_bet_{tid}")],
                            [InlineKeyboardButton(text="❌ لغو", callback_data=f"spin_cancel_{tid}")]
                        ]
                    )
                    
                    await message.reply(
                        f"🎡 **گردونه شانس**\n\n"
                        f"✅ مبلغ ورودی: {bet:,} میو پوینت\n"
                        f"👥 تعداد بازیکن: درحال تعیین\n\n"
                        f"لطفا تعداد بازیکن را تعیین کنید!",
                        reply_markup=keyboard
                    )
                else:
                    await message.reply("❌ مبلغ باید بین ۱۰۰ تا ۱۰۰٬۰۰۰ باشد!")
                return
            except:
                await message.reply("❌ لطفا یک عدد معتبر وارد کنید!")
                return
    
    user = User.get(message.from_user.id)
    if user:
        msg_count = GroupMessage.get_user_count(message.from_user.id, message.chat.id)
        if msg_count % 10 == 0:
            User.update(message.from_user.id, hop_point=user["hop_point"] + 1)
            await message.reply(f"🌟 {user['first_name']} به خاطر فعالیت در گروه ۱ میو گرفتی!")
