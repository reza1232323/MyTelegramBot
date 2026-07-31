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

# ==================== اسلات ماشین با استیکر 🎰 ====================

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

# ==================== دستور کازینو ====================

@router.message(F.text == "کازینو")
async def casino_menu(message: Message):
    if is_private(message):
        await message.reply("🎰 کازینو فقط در گروه قابل استفاده است!")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 اسلات", callback_data="slot_start")],
        ]
    )
    
    await message.reply(
        f"🎰 **کازینو**\n\n"
        f"برای بازی اسلات، روی دکمه زیر کلیک کن\n"
        f"سپس مبلغ شرط رو وارد کن و استیکر 🎰 بفرست",
        reply_markup=keyboard
    )

# ==================== شروع اسلات ====================

@router.callback_query(F.data == "slot_start")
async def slot_start(callback: CallbackQuery):
    if is_private(callback.message):
        await callback.answer("❌ فقط در گروه!", show_alert=True)
        return
    
    user = get_or_create_user_silent(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    if user["hop_point"] < 100:
        await callback.answer("❌ حداقل ۱۰۰ میو پوینت نیاز داری!", show_alert=True)
        return
    
    slot_bets[callback.from_user.id] = "waiting"
    
    await callback.message.edit_text(
        f"🎰 **اسلات ماشین**\n\n"
        f"💰 مبلغ شرط خود را وارد کن (۱۰۰ تا ۱۰۰٬۰۰۰)\n"
        f"مثال: 500\n\n"
        f"📊 ضریب‌ها:\n"
        f"۱-۱۹: ×۰ | ۲۰-۲۹: ×۰.۵\n"
        f"۳۰-۳۹: ×۱.۰ | ۴۰-۴۹: ×۱.۵\n"
        f"۵۰-۵۹: ×۲.۰ | ۶۰-۶۳: ×۲.۵\n"
        f"۶۴ (جکپات): ×۳.۰\n\n"
        f"بعدش استیکر 🎰 بفرست",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ لغو", callback_data="slot_cancel")]]
        )
    )
    await callback.answer()

# ==================== دریافت مبلغ شرط ====================

# این رو به @router.message(F.text) اضافه کن:

if message.from_user.id in slot_bets and slot_bets[message.from_user.id] == "waiting":
    try:
        bet = int(message.text.strip())
        if bet < 100:
            await message.reply("❌ حداقل ۱۰۰")
            return
        if bet > 100000:
            await message.reply("❌ حداکثر ۱۰۰٬۰۰۰")
            return
    except:
        await message.reply("❌ عدد وارد کن!")
        return
    
    user = User.get(message.from_user.id)
    if not user or user["hop_point"] < bet:
        await message.reply(f"❌ موجودی کافی نیست! داری {user['hop_point']:,} میو")
        return
    
    slot_bets[message.from_user.id] = bet
    await message.reply(f"✅ مبلغ: {bet:,} میو\n\n🎰 حالا استیکر 🎰 بفرست (۶۰ ثانیه وقت داری)")

# ==================== دریافت استیکر و اجرا ====================

@router.message(F.sticker)
async def slot_sticker(message: Message):
    if is_private(message):
        return
    
    if message.from_user.id not in slot_bets or slot_bets[message.from_user.id] == "waiting":
        return
    
    if message.sticker.emoji != "🎰":
        await message.reply("❌ فقط استیکر 🎰")
        return
    
    bet = slot_bets[message.from_user.id]
    del slot_bets[message.from_user.id]
    
    user = User.get(message.from_user.id)
    if not user:
        return
    
    result = generate_random_slot()
    score = calculate_slot_score(result)
    multiplier = get_prize_multiplier(score)
    slot_number = get_slot_number(result)
    combo = f"{result[0]} {result[1]} {result[2]}"
    
    win = int(bet * multiplier)
    
    # ===== فرمت خروجی مثل عکس =====
    text = f"🎰 **گردونه شانس**\n\n"
    text += f"💰 مبلغ ورودی: {bet:,}\n"
    text += f"📊 ({multiplier}x)\n"
    text += f"🎯 مبلغ دریافت: {win:,}\n"
    text += f"👤 بازیکن: {message.from_user.first_name}\n"
    text += f"⭐ امتیاز: {score}\n\n"
    text += f"🎰 {combo}\n"
    text += f"🔢 #{slot_number} از ۶۴"
    
    if win > 0:
        User.update(message.from_user.id, hop_point=user["hop_point"] + win)
        if score == 64:
            text += f"\n\n🌟 **جکپات!** 🌟"
    else:
        text += f"\n\n😞 باختی!"
    
    await message.reply(text)

# ==================== لغو ====================

@router.callback_query(F.data == "slot_cancel")
async def slot_cancel(callback: CallbackQuery):
    if callback.from_user.id in slot_bets:
        del slot_bets[callback.from_user.id]
    await callback.message.edit_text("❌ لغو شد")
    await callback.answer()
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
        "♠️ **قمار** [مبلغ]\n"
        "🎰 **کازینو**"
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
**کازینو** ➜ منوی کازینو (فقط گروه)

🎰 **کازینو اسلات (فقط گروه)**
1. **کازینو** رو بزن
2. **اسلات** رو انتخاب کن
3. مبلغ شرط رو وارد کن (۱۰۰ تا ۱۰۰٬۰۰۰)
4. استیکر **🎰** رو بفرست
5. ربات ۳ ردیف رو چک میکنه
6. امتیاز و جایزه محاسبه میشه

📊 **ضریب‌های جایزه اسلات:**
امتیاز ۱-۱۹: ×۰
امتیاز ۲۰-۲۹: ×۰.۵
امتیاز ۳۰-۳۹: ×۱.۰
امتیاز ۴۰-۴۹: ×۱.۵
امتیاز ۵۰-۵۹: ×۲.۰
امتیاز ۶۰-۶۳: ×۲.۵
امتیاز ۶۴ (جکپات): ×۳.۰

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
# ============================ بخش کازینو (اسلات + گردونه) =============================
# ======================================================================================

# ==================== منوی کازینو ====================

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
            [InlineKeyboardButton(text="🎰 اسلات", callback_data="casino_slot")],
            [InlineKeyboardButton(text="🎡 گردونه شانس", callback_data="casino_spin_group")],
            [InlineKeyboardButton(text="📊 میزهای فعال", callback_data="casino_tables")]
        ]
    )
    
    await message.reply(
        f"🎰 **کازینو میوپی**\n\n"
        f"👤 {user['first_name']}\n"
        f"💰 میو پوینت: {user['hop_point']:,}\n\n"
        f"لطفا بازی مورد نظر را انتخاب کنید!\n\n"
        f"🎰 **اسلات**: استیکر 🎰 بفرستید تا شانس خود را امتحان کنید!\n"
        f"📊 ضریب‌های جایزه:\n"
        f"امتیاز ۱-۱۹: ×۰ | ۲۰-۲۹: ×۰.۵\n"
        f"۳۰-۳۹: ×۱.۰ | ۴۰-۴۹: ×۱.۵\n"
        f"۵۰-۵۹: ×۲.۰ | ۶۰-۶۳: ×۲.۵\n"
        f"۶۴ (جکپات): ×۳.۰",
        reply_markup=keyboard
    )

# ==================== اسلات ====================

@router.callback_query(F.data == "casino_slot")
async def casino_slot_start(callback: CallbackQuery):
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
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ لغو", callback_data="slot_cancel")]
        ]
    )
    
    await callback.message.edit_text(
        f"🎰 **اسلات ماشین**\n\n"
        f"💰 لطفا مبلغ شرط خود را وارد کنید\n"
        f"مثال: 500\n\n"
        f"حداقل: ۱۰۰ | حداکثر: ۱۰۰۰۰۰\n\n"
        f"📊 **ضریب‌های جایزه:**\n"
        f"امتیاز ۱-۱۹: ×۰\n"
        f"امتیاز ۲۰-۲۹: ×۰.۵\n"
        f"امتیاز ۳۰-۳۹: ×۱.۰\n"
        f"امتیاز ۴۰-۴۹: ×۱.۵\n"
        f"امتیاز ۵۰-۵۹: ×۲.۰\n"
        f"امتیاز ۶۰-۶۳: ×۲.۵\n"
        f"امتیاز ۶۴ (جکپات): ×۳.۰\n\n"
        f"🎯 بعد از تعیین مبلغ، استیکر **🎰** بفرستید!",
        reply_markup=keyboard
    )
    await callback.answer()

# ==================== دریافت مبلغ شرط اسلات ====================

@router.message(F.text)
async def handle_slot_bet(message: Message):
    if is_private(message):
        return
    
    # چک کردن اینکه کاربر در حال تنظیم شرط اسلات هست یا نه
    if message.from_user.id not in slot_bets or slot_bets[message.from_user.id] != "waiting":
        return
    
    try:
        bet = int(message.text.strip())
        if bet < 100:
            await message.reply("❌ حداقل مبلغ ۱۰۰ میو پوینت است!")
            return
        if bet > 100000:
            await message.reply("❌ حداکثر مبلغ ۱۰۰٬۰۰۰ میو پوینت است!")
            return
    except:
        await message.reply("❌ لطفا یک عدد معتبر وارد کنید!")
        return
    
    user = User.get(message.from_user.id)
    if not user or user["hop_point"] < bet:
        await message.reply(f"❌ موجودی کافی نیست! داری {user['hop_point']:,} میو پوینت")
        return
    
    # ذخیره مبلغ شرط
    slot_bets[message.from_user.id] = bet
    
    await message.reply(
        f"✅ مبلغ شرط: {bet:,} میو پوینت\n\n"
        f"🎰 حالا استیکر **🎰** رو بفرستید تا شانس خود را امتحان کنید!\n"
        f"⏱️ فقط ۶۰ ثانیه فرصت دارید..."
    )
    
    # تایمر ۶۰ ثانیه
    await asyncio.sleep(60)
    
    # اگر کاربر هنوز استیکر نفرستاده، شرط رو لغو کن
    if message.from_user.id in slot_bets and slot_bets[message.from_user.id] != "waiting":
        del slot_bets[message.from_user.id]
        await message.reply("⏱️ زمان شما به پایان رسید! شرط لغو شد.")

# ==================== دریافت استیکر و اجرای اسلات ====================

@router.message(F.sticker)
async def handle_slot_sticker(message: Message):
    if is_private(message):
        return
    
    # چک کردن اینکه کاربر در حال بازی اسلات هست یا نه
    if message.from_user.id not in slot_bets or slot_bets[message.from_user.id] == "waiting":
        return
    
    # چک کردن اینکه استیکر 🎰 هست یا نه
    if message.sticker.emoji != "🎰":
        await message.reply("❌ لطفا استیکر **🎰** رو بفرستید!")
        return
    
    bet = slot_bets[message.from_user.id]
    del slot_bets[message.from_user.id]
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    # تولید اسلات تصادفی
    result = generate_random_slot()
    score = calculate_slot_score(result)
    multiplier = get_prize_multiplier(score)
    slot_number = get_slot_number(result)
    combination_name = get_slot_combination_name(result)
    
    # محاسبه جایزه
    win_amount = int(bet * multiplier)
    
    result_text = f"🎰 **نتیجه اسلات**\n\n"
    result_text += f"🎯 ترکیب: **{combination_name}**\n"
    result_text += f"🔢 شماره: {slot_number} از ۶۴\n"
    result_text += f"⭐ امتیاز: **{score}**\n"
    result_text += f"📊 ضریب: **×{multiplier}**\n\n"
    
    if multiplier > 0 and win_amount > 0:
        User.update(message.from_user.id, hop_point=user["hop_point"] + win_amount)
        result_text += f"🎉 **تبریک!**\n"
        result_text += f"💰 شما **{win_amount:,}** میو پوینت برنده شدید!\n"
        
        if score == 64:
            result_text += f"🌟 **جکپات!** 🌟\n"
            result_text += f"👑 شما برنده بزرگ شدید!"
    else:
        result_text += f"😞 متاسفانه برنده نشدید!\n"
        result_text += f"💸 {bet:,} میو پوینت از دست رفت."
    
    await message.reply(result_text)

# ==================== لغو اسلات ====================

@router.callback_query(F.data == "slot_cancel")
async def slot_cancel(callback: CallbackQuery):
    if callback.from_user.id in slot_bets:
        del slot_bets[callback.from_user.id]
    
    await callback.message.edit_text("❌ بازی اسلات لغو شد!")
    await callback.answer()

# ==================== اسلات برای ادمین (رایگان) ====================

@router.message(F.sticker)
async def handle_admin_slot(message: Message):
    if is_private(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    if message.sticker.emoji != "🎰":
        return
    
    result = generate_random_slot()
    score = calculate_slot_score(result)
    multiplier = get_prize_multiplier(score)
    slot_number = get_slot_number(result)
    combination_name = get_slot_combination_name(result)
    
    result_text = f"🎰 **نتیجه اسلات (👑 ادمین)**\n\n"
    result_text += f"🎯 ترکیب: **{combination_name}**\n"
    result_text += f"🔢 شماره: {slot_number} از ۶۴\n"
    result_text += f"⭐ امتیاز: **{score}**\n"
    result_text += f"📊 ضریب: **×{multiplier}**\n\n"
    result_text += f"👑 ادمین - این یک نمایش است!"
    
    await message.reply(result_text)

# ==================== گردونه شانس گروهی ====================

@router.callback_query(F.data == "casino_spin_group")
async def casino_spin_start(callback: CallbackQuery):
    # اینجا کد گردونه گروهی که قبلا نوشته بودیم
    # برای جلوگیری از طولانی شدن، فعلاً پیام میده
    await callback.message.edit_text(
        "🎡 **گردونه شانس گروهی**\n\n"
        "در حال توسعه...\n"
        "به زودی!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino_back")]]
        )
    )
    await callback.answer()

# ==================== میزهای فعال ====================

@router.callback_query(F.data == "casino_tables")
async def show_active_tables(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 **میزهای فعال**\n\n"
        "هیچ میز فعالی وجود ندارد!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="casino_back")]]
        )
    )
    await callback.answer()

# ==================== بازگشت ====================

@router.callback_query(F.data == "casino_back")
async def casino_back(callback: CallbackQuery):
    await casino_menu(callback.message)
    await callback.answer()

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
    
    # اگر کاربر در حال تنظیم شرط اسلات نیست، اینجا رو چک کن
    if message.from_user.id not in slot_bets:
        # ثبت شرط برای اسلات
        if message.text and message.text.isdigit():
            # فقط اگه کاربر قبلاً اسلات رو انتخاب کرده باشه
            pass
    
    user = User.get(message.from_user.id)
    if user:
        msg_count = GroupMessage.get_user_count(message.from_user.id, message.chat.id)
        if msg_count % 10 == 0:
            User.update(message.from_user.id, hop_point=user["hop_point"] + 1)
            await message.reply(f"🌟 {user['first_name']} به خاطر فعالیت در گروه ۱ میو گرفتی!")
