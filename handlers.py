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
        ("🎉 ۱۰۰ هاپ!", 100, 0),
        ("💎 ۵ جم!", 0, 5),
        ("💎 ۲ جم!", 0, 2),
        ("😞 هیچی!", 0, 0),
        ("⭐ ۵۰۰ هاپ!", 500, 0),
    ]
    
    prize = random.choice(prizes)
    hop_win, gem_win = prize[1], prize[2]
    
    if hop_win > 0:
        User.update(callback.from_user.id, hop_point=user["hop_point"] + hop_win)
        result = f"{prize[0]} (مجموع: {user['hop_point'] - cost + hop_win:.1f} هاپ)"
    elif gem_win > 0:
        User.update(callback.from_user.id, hop_gem=user["hop_gem"] + gem_win)
        result = prize[0]
    else:
        result = prize[0]
    
    await callback.message.edit_text(f"🎡 **گردونه شانس**\n{result}")
    await callback.answer()

# ==================== پروفایل با دکمه در گروه ====================

@router.callback_query(F.data == "group_profile")
async def group_profile_callback(callback: CallbackQuery):
    """مشاهده پروفایل با دکمه در گروه"""
    user = User.get(callback.from_user.id)
    if not user:
        await callback.answer("❌ ثبت‌نام کن!", show_alert=True)
        return
    
    await callback.message.edit_text(
        format_profile(user, group_mode=True),
        reply_markup=inline_group_actions()
    )
    await callback.answer()

# ==================== تغذیه هاپو (با دکمه) ====================

@router.callback_query(F.data == "feed_hopo")
async def feed_hopo_callback(callback: CallbackQuery):
    """غذا دادن به هاپو"""
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

# ==================== خواب هاپو ====================

@router.callback_query(F.data == "sleep_hopo")
async def sleep_hopo_callback(callback: CallbackQuery):
    user = User.get(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ ثبت‌نام کن!")
        return
    
    energy = min(100, user["hopo_energy"] + 30)
    User.update(callback.from_user.id, hopo_energy=energy)
    
    await callback.message.edit_text(f"😴 هاپو خوابید! انرژی: {energy}%")
    await callback.answer()

# ==================== بازی با هاپو ====================

@router.callback_query(F.data == "play_hopo")
async def play_hopo_callback(callback: CallbackQuery):
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

# ==================== باز کردن تخم ====================

@router.callback_query(F.data == "hatch_hopo")
async def hatch_hopo_callback(callback: CallbackQuery):
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
    
    # باز شدن تخم
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
        f"📛 اسمش رو بذار: /اسم [نام]"
    )
    await callback.answer()

# ==================== اسم گذاری ====================

@router.message(Command("اسم"))
async def set_name_command(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ فرمت: /اسم نام")
        return
    
    name = parts[1]
    User.update(message.from_user.id, hopo_name=name)
    await message.reply(f"✅ هاپو اسمش شد: {name}")

# ==================== بانک ====================

@router.message(Command("بانک"))
@router.message(F.text == "🏦 بانک")
async def bank_command(message: Message):
    if is_group(message):
        await message.reply("🏦 برای مدیریت بانک به پیوی ربات برو.")
        return
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    await message.reply(
        f"🏦 **بانک هاپو**\n\n"
        f"💰 موجودی: {user['bank_balance']:.1f} هاپ\n"
        f"📈 سود: {user['bank_interest'] * 100}%\n\n"
        f"دستورات:\n"
        f"📥 /سپرده [مبلغ]\n"
        f"📤 /برداشت [مبلغ]"
    )

@router.message(Command("سپرده"))
async def deposit_command(message: Message):
    if is_group(message):
        await message.reply("🏦 این دستور فقط در پیوی قابل استفاده است.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: /سپرده 100")
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

@router.message(Command("برداشت"))
async def withdraw_command(message: Message):
    if is_group(message):
        await message.reply("🏦 این دستور فقط در پیوی قابل استفاده است.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: /برداشت 100")
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

@router.message(Command("کارخونه"))
@router.message(F.text == "🏭 کارخانه")
async def factory_command(message: Message):
    if is_group(message):
        await message.reply("🏭 برای مدیریت کارخانه به پیوی ربات برو.")
        return
    
    user = User.get(message.from_user.id)
    if not user:
        await message.reply("❌ ثبت‌نام کن!")
        return
    
    await message.reply(
        f"🏭 **کارخانه**\n\n"
        f"📊 سطح: {user['factory_level']}\n"
        f"⚡ تولید: {user['factory_production']:.1f} هاپ در ساعت\n\n"
        f"دستورات:\n"
        f"📥 /جمع_کارخانه\n"
        f"⬆️ /ارتقا_کارخانه"
    )

@router.message(Command("جمع_کارخانه"))
async def collect_factory_command(message: Message):
    if is_group(message):
        await message.reply("🏭 این دستور فقط در پیوی قابل استفاده است.")
        return
    
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

@router.message(Command("ارتقا_کارخانه"))
async def upgrade_factory_command(message: Message):
    if is_group(message):
        await message.reply("🏭 این دستور فقط در پیوی قابل استفاده است.")
        return
    
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

@router.message(Command("فروشگاه"))
@router.message(F.text == "🛒 فروشگاه")
async def shop_command(message: Message):
    if is_group(message):
        await message.reply("🛒 برای خرید به پیوی ربات برو.")
        return
    
    items = Shop.get_items()
    await message.reply(format_shop(items))

@router.message(Command("خرید"))
async def buy_command(message: Message):
    if is_group(message):
        await message.reply("🛒 این دستور فقط در پیوی قابل استفاده است.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: /خرید [آیدی] [تعداد]")
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

@router.message(Command("کیف"))
@router.message(F.text == "🎒 کیف")
async def inventory_command(message: Message):
    if is_group(message):
        await message.reply("🎒 برای مشاهده کیف به پیوی ربات برو.")
        return
    
    items = Inventory.get_items(message.from_user.id)
    if not items:
        await message.reply("🎒 انبار خالی است!")
        return
    
    text = "🎒 **انبار شما**\n━━━━━━━━━━\n"
    for item in items:
        text += f"{item['item_name']}: {item['quantity']} عدد\n"
    
    await message.reply(text)

# ==================== بازی‌ها ====================

@router.message(Command("بازی"))
@router.message(F.text == "🎲 بازی‌ها")
async def games_menu(message: Message):
    await message.reply(
        "🎮 **بازی‌های هاپو**\n\n"
        "🎲 /تاس [مبلغ]\n"
        "🎡 /گردونه\n"
        "♠️ /قمار [مبلغ]",
        reply_markup=inline_games()
    )

@router.message(Command("تاس"))
@router.callback_query(F.data == "game_dice")
async def dice_game(message_or_callback):
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
        user_id = message_or_callback.from_user.id
        await message_or_callback.answer()
    else:
        message = message_or_callback
        user_id = message.from_user.id
    
    parts = message.text.split() if hasattr(message, 'text') else []
    if len(parts) < 2:
        await message.reply("❌ فرمت: /تاس 100")
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user = User.get(user_id)
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
        User.update(user_id, hop_point=user["hop_point"] + win)
        result = f"🎉 بردی! {win:.1f} هاپ"
    elif user_roll < bot_roll:
        User.update(user_id, hop_point=user["hop_point"] - bet)
        result = f"😞 باختی! {bet:.1f} هاپ"
    else:
        result = "🤝 مساوی شد!"
    
    await message.reply(
        f"🎲 **تاس**\n"
        f"تو: {user_roll} | ربات: {bot_roll}\n"
        f"{result}"
    )

@router.message(Command("قمار"))
@router.callback_query(F.data == "game_gamble")
async def gamble_game(message_or_callback):
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
        user_id = message_or_callback.from_user.id
        await message_or_callback.answer()
    else:
        message = message_or_callback
        user_id = message.from_user.id
    
    parts = message.text.split() if hasattr(message, 'text') else []
    if len(parts) < 2:
        await message.reply("❌ فرمت: /قمار 100")
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.reply("❌ مبلغ نامعتبر!")
        return
    
    user = User.get(user_id)
    if not user or user["hop_point"] < bet:
        await message.reply("❌ موجودی کافی نیست!")
        return
    
    cards = ["♠️", "♥️", "♦️", "♣️"]
    user_card = random.choice(cards)
    bot_card = random.choice(cards)
    
    ranks = {"♠️": 4, "♥️": 3, "♦️": 2, "♣️": 1}
    
    if ranks[user_card] > ranks[bot_card]:
        win = bet * 2
        User.update(user_id, hop_point=user["hop_point"] + win)
        result = f"🎉 بردی! {win:.1f} هاپ"
    elif ranks[user_card] < ranks[bot_card]:
        User.update(user_id, hop_point=user["hop_point"] - bet)
        result = f"😞 باختی! {bet:.1f} هاپ"
    else:
        result = "🤝 مساوی شد!"
    
    await message.reply(
        f"♠️ **قمار**\n"
        f"تو: {user_card} | ربات: {bot_card}\n"
        f"{result}"
    )

# ==================== مأموریت‌ها ====================

@router.message(Command("ماموریت"))
@router.message(F.text == "🎯 مأموریت‌ها")
async def mission_command(message: Message):
    if is_group(message):
        await message.reply("🎯 برای مشاهده مأموریت‌ها به پیوی ربات برو.")
        return
    
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
    
    text += "\n/دریافت_ماموریت - دریافت پاداش"
    await message.reply(text)

@router.message(Command("دریافت_ماموریت"))
async def claim_mission_command(message: Message):
    if is_group(message):
        await message.reply("🎯 این دستور فقط در پیوی قابل استفاده است.")
        return
    
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

@router.message(Command("دعوت"))
@router.message(F.text == "🔗 دعوت دوستان")
async def invite_command(message: Message):
    if is_group(message):
        await message.reply("🔗 برای دریافت لینک دعوت به پیوی ربات برو.")
        return
    
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

@router.message(Command("راهنما"))
@router.message(F.text == "📖 راهنما")
async def help_command(message: Message):
    help_text = """
📖 **راهنمای کامل ربات هاپو**

🐾 **دستورات اصلی (همه جا)**
/هاپ ➜ دریافت هاپ (هر ۵ دقیقه)
/هاپوهام ➜ مشاهده پروفایل
/هاپ‌هاش ➜ پروفایل کاربر ریپلای شده
/لیدربرد ➜ جدول برترین‌ها
/راهنما ➜ نمایش راهنما

🐾 **دستورات مخصوص گروه**
- هر پیام در گروه امتیاز داره
- با ریپلای روی پیام کاربر و /هاپ‌هاش پروفایلش رو ببین

🏦 **اقتصاد (فقط پیوی)**
/بانک ➜ مدیریت بانک
/سپرده [مبلغ] ➜ واریز به بانک
/برداشت [مبلغ] ➜ برداشت از بانک
/کارخونه ➜ مدیریت کارخانه
/جمع_کارخانه ➜ جمع‌آوری تولید
/ارتقا_کارخانه ➜ ارتقای کارخانه

🛒 **فروشگاه (فقط پیوی)**
/فروشگاه ➜ مشاهده آیتم‌ها
/خرید [آیدی] [تعداد] ➜ خرید آیتم
/کیف ➜ مشاهده انبار

🎮 **بازی‌ها (همه جا)**
/بازی ➜ منوی بازی‌ها
/تاس [مبلغ] ➜ بازی تاس
/گردونه ➜ گردونه شانس
/قمار [مبلغ] ➜ بازی قمار

🎯 **مأموریت‌ها (فقط پیوی)**
/ماموریت ➜ مشاهده مأموریت‌ها
/دریافت_ماموریت ➜ دریافت پاداش

🔗 **دعوت (فقط پیوی)**
/دعوت ➜ دریافت لینک دعوت

🐣 **هاپو (همه جا)**
/اسم [نام] ➜ اسم گذاری هاپو
    """
    await message.reply(help_text)

# ==================== پنل مدیریت ====================

@router.message(Command("پنل"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    await message.reply(
        "🔐 **پنل مدیریت**\n\n"
        "👤 /افزایش_پوینت [مبلغ] - ریپلای روی کاربر\n"
        "👤 /کاهش_پوینت [مبلغ] - ریپلای روی کاربر\n"
        "👤 /افزایش_لول [عدد] - ریپلای روی کاربر\n"
        "👤 /کاهش_لول [عدد] - ریپلای روی کاربر\n"
        "👤 /افزودن_ادمین - ریپلای روی کاربر\n"
        "👤 /حذف_ادمین - ریپلای روی کاربر\n"
        "👤 /حذف_کاربر - ریپلای روی کاربر",
        reply_markup=admin_menu()
    )

@router.message(Command("افزایش_پوینت"))
async def add_points_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: /افزایش_پوینت 100")
        return
    
    try:
        amount = float(parts[1])
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

@router.message(Command("کاهش_پوینت"))
async def remove_points_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: /کاهش_پوینت 100")
        return
    
    try:
        amount = float(parts[1])
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

@router.message(Command("افزایش_لول"))
async def add_level_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ دسترسی ندارید!")
        return
    
    if not message.reply_to_message:
        await message.reply("❌ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ فرمت: /افزایش_لول 5")
        return
    
    try:
        level = int(parts[1])
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

@router.message(Command("افزودن_ادمین"))
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

@router.message(Command("حذف_ادمین"))
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
    """هندلر پیام‌های معمولی در گروه"""
    
    # فقط در گروه اجرا کن
    if not is_group(message):
        return
    
    # ثبت پیام گروه
    GroupMessage.add(message.from_user.id, message.chat.id, message.text or "")
    
    # هر ۱۰ پیام ۱ هاپ پاداش
    user = User.get(message.from_user.id)
    if user:
        msg_count = GroupMessage.get_user_count(message.from_user.id, message.chat.id)
        if msg_count % 10 == 0:
            User.update(message.from_user.id, hop_point=user["hop_point"] + 1)
            await message.reply(f"🌟 {user['first_name']} به خاطر فعالیت در گروه ۱ هاپ گرفتی!")
