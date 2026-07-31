from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, ReplyParameters
from aiogram.filters import Command
from models import User, Inventory, Shop, GroupMessage
from utils import *
from keyboards import *
from config import config
import random
import asyncio
from datetime import datetime, timedelta
import time

router = Router()

# ==================== فیلتر تشخیص پیوی/گروه ====================

def is_private(message: Message) -> bool:
    return message.chat.type == "private"

def is_group(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"]

# ==================== شروع و ثبت‌نام ====================

@router.message(Command("start"))
async def start_command(message: Message, bot):
    """ثبت‌نام و شروع - هم در پیوی هم گروه"""
    
    # ثبت‌نام کاربر
    user = User.get_or_create(message.from_user)
    
    # بررسی ریفرال (فقط در پیوی)
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
    
    # پیام خصوصی
    if is_private(message):
        await message.reply(
            f"🎉 **به هاپو خوش اومدی {user['first_name']}!**\n\n"
            f"🐣 یه تخم هاپو داری که تا ۶ ساعت دیگه باز میشه!\n"
            f"💡 هر ۵ دقیقه با دستور /هاپ امتیاز بگیر.\n"
            f"📖 راهنما: /راهنما\n\n"
            f"✨ {user['hop_point']:.1f} هاپ اولیه بهت داده شد!",
            reply_markup=main_menu()
        )
    else:
        # پیام گروه
        await message.reply(
            f"🎉 **{user['first_name']} به هاپو خوش اومدی!**\n"
            f"برای مشاهده پروفایل از دکمه‌ها استفاده کن.",
            reply_markup=group_menu()
        )

# ==================== دکمه خانه (پیوی) ====================

@router.message(F.text == "🏠 خانه")
async def home_command(message: Message, bot):
    if is_private(message):
        await start_command(message, bot)
    else:
        await message.reply("🏠 برای منوی اصلی به پیوی ربات برو.")

# ==================== دستور هاپ (دریافت امتیاز - پیوی و گروه) ====================

@router.message(Command("هاپ"))
async def get_hop_command(message: Message, bot):
    """دریافت هاپ هر ۵ دقیقه - هم در پیوی هم گروه"""
    
    # بررسی عضویت در کانال (فقط برای پیوی)
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
        await message.reply("❌ ابتدا ثبت‌نام کنید: /start")
        return
    
    if not can_claim_hop(user):
        remain = int(300 - (time.time() - user["last_hop_claim"]))
        minutes = remain // 60
        seconds = remain % 60
        await message.reply(f"⏳ صبر کن! {minutes} دقیقه و {seconds} ثانیه مونده")
        return
    
    # محاسبه هاپ
    hop_reward = calculate_hop_reward(user)
    gem_reward = 0
    
    if has_gem_chance():
        gem_reward = get_random_gem()
        User.update(message.from_user.id, hop_gem=user["hop_gem"] + gem_reward)
    
    # پاداش گروهی (اگر در گروه باشد)
    bonus = 0
    if is_group(message):
        bonus = 5  # پاداش گروهی
        hop_reward += bonus
        # ثبت پیام گروه
        GroupMessage.add(message.from_user.id, message.chat.id, message.text or "")
    
    User.update(
        message.from_user.id,
        hop_point=user["hop_point"] + hop_reward,
        last_hop_claim=time.time()
    )
    
    gem_text = f" و 💎 {gem_reward} جم" if gem_reward > 0 else ""
    bonus_text = f" (🌟 {bonus} پاداش گروهی)" if bonus > 0 else ""
    
    await message.reply(
        f"🎉 {hop_reward:.1f} هاپ دریافت کردی!{gem_text}{bonus_text}",
        reply_markup=inline_group_actions() if is_group(message) else None
    )

# ==================== پروفایل (پیوی و گروه) ====================

@router.message(Command("هاپوهام"))
@router.message(F.text == "🐣 هایوی من")
async def my_profile(message: Message):
    """مشاهده پروفایل - هم در پیوی هم گروه"""
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ابتدا ثبت‌نام کنید: /start")
        return
    
    # به‌روزرسانی خودکار وضعیت هاپو
    if user["hopo_stage"] != "egg":
        hunger = max(0, user["hopo_hunger"] - 5)
        happiness = max(0, user["hopo_happiness"] - 2)
        User.update(message.from_user.id, hopo_hunger=hunger, hopo_happiness=happiness)
        user = User.get(message.from_user.id)
    
    # پیام خصوصی
    if is_private(message):
        await message.reply(
            format_profile(user),
            reply_markup=inline_home()
        )
    else:
        # پیام گروه (خلاصه)
        await message.reply(
            format_profile(user, group_mode=True),
            reply_markup=inline_group_actions()
        )

# ==================== مشاهده پروفایل کاربر دیگر (با ریپلای) ====================

@router.message(Command("هاپ هاش"))
async def user_profile_reply(message: Message):
    """مشاهده پروفایل کاربری که رویش ریپلای شده"""
    if not message.reply_to_message:
        await message.reply("❌ روی پیام یک کاربر ریپلای کن!")
        return
    
    target_id = message.reply_to_message.from_user.id
    user = User.get(target_id)
    
    if not user:
        await message.reply("❌ کاربر در ربات ثبت‌نام نکرده!")
        return
    
    if is_private(message):
        await message.reply(format_profile(user))
    else:
        await message.reply(
            format_profile(user, group_mode=True),
            reply_markup=inline_reply_profile(target_id)
        )

# ==================== مشاهده پروفایل با کلیک روی دکمه ====================

@router.callback_query(F.data.startswith("profile_"))
async def profile_callback(callback: CallbackQuery):
    """مشاهده پروفایل کاربر با کلیک روی دکمه"""
    target_id = int(callback.data.split("_")[1])
    user = User.get(target_id)
    
    if not user:
        await callback.answer("❌ کاربر پیدا نشد!", show_alert=True)
        return
    
    await callback.message.edit_text(
        format_profile(user, group_mode=True),
        reply_markup=inline_group_actions()
    )
    await callback.answer()

# ==================== لیدربرد (پیوی و گروه) ====================

@router.message(Command("لیدربرد"))
@router.message(F.text == "📊 لیدربرد")
async def leaderboard_command(message: Message):
    """نمایش لیدربرد - هم در پیوی هم گروه"""
    
    if is_group(message):
        # لیدربرد مخصوص گروه (بر اساس تعداد پیام)
        users = User.get_group_top_users(message.chat.id, 10)
        await message.reply(format_group_leaderboard(users))
    else:
        users = User.get_top_users(10)
        await message.reply(format_leaderboard(users))

# ==================== دکمه لیدربرد گروه ====================

@router.callback_query(F.data == "group_leaderboard")
async def group_leaderboard_callback(callback: CallbackQuery):
    """لیدربرد گروه با دکمه"""
    users = User.get_group_top_users(callback.message.chat.id, 10)
    await callback.message.edit_text(format_group_leaderboard(users))
    await callback.answer()

# ==================== گردونه شانس (پیوی و گروه) ====================

@router.message(Command("گردونه"))
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

# ==================== گردونه شانس با دکمه ====================

@router.callback_query(F.data == "group_spin")
async def group_spin_callback(callback: CallbackQuery):
    """گردونه شانس با دکمه در گروه"""
    user = User.get(callback.from_user.id)
    if not user:
        await callback.answer("❌ ثبت‌نام کن!", show_alert=True)
        return
    
    cost = 20
    if user["hop_point"] < cost:
        await callback.answer(f"❌ {cost} هاپ نیاز داری!", show_alert=True)
        return
    
    User.update(callback.from_user.id, hop_point=user["hop_point"] - cost)
    
    prizes = [
        ("🎉 ۵۰ هاپ!", 50, 0),
        ("🎉 ۲۰ هاپ!", 20, 0),
        ("🎉 ۱۰۰ هاپ!", 
