import asyncio
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db

COOLDOWN_SECONDS = 300  # ۵ دقیقه

# لیست جوایز به همراه وزن (شانس دریافت)
PRIZES = [
    {
        "id": "points_small",
        "name": "💰 ۱۰۰ سکه",
        "type": "points",
        "val": 100,
        "weight": 35,
    },
    {
        "id": "points_med",
        "name": "💰 ۵۰۰ سکه",
        "type": "points",
        "val": 500,
        "weight": 25,
    },
    {
        "id": "points_big",
        "name": "💎 ۲,۰۰۰ سکه",
        "type": "points",
        "val": 2000,
        "weight": 10,
    },
    {
        "id": "points_jackpot",
        "name": "👑 ۱۰,۰۰۰ سکه (جک‌پات!)",
        "type": "points",
        "val": 10000,
        "weight": 2,
    },
    {
        "id": "food_1",
        "name": "🍖 ۱ عدد غذا",
        "type": "inventory_food",
        "val": 1,
        "weight": 15,
    },
    {
        "id": "food_3",
        "name": "🍖 ۳ عدد غذا",
        "type": "inventory_food",
        "val": 3,
        "weight": 8,
    },
    {
        "id": "diamond_1",
        "name": "💎 ۱ عدد الماس",
        "type": "inventory_diamond",
        "val": 1,
        "weight": 5,
    },
]


def pick_prize():
    weights = [p["weight"] for p in PRIZES]
    return random.choices(PRIZES, weights=weights, k=1)[0]


async def show_wheel_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل اصلی گردونه شانس"""
    user_id = update.effective_user.id
    last_spin = db.get_user_field(user_id, "last_spin_time") or 0
    spin_count = db.get_user_field(user_id, "spin_count") or 0
    now = int(time.time())

    diff = now - last_spin
    if diff < COOLDOWN_SECONDS:
        rem = COOLDOWN_SECONDS - diff
        m, s = divmod(rem, 60)
        status_str = f"⏳ **آماده‌سازی:** {m} دقیقه و {s} ثانیه دیگر"
        btn_text = f"⏳ صبر کنید ({m}:{s:02d})"
        btn_data = "wheel_cooldown"
    else:
        status_str = "✅ **آماده برای چرخش!**"
        btn_text = "🎡 چرخاندن گردونه"
        btn_data = "spin_wheel"

    prizes_text = "\n".join([f"• {p['name']}" for p in PRIZES])

    text = (
        f"🎡 **گردونه شانس هاپو**\n\n"
        f"هر ۵ دقیقه یک‌بار شانس خودت رو امتحان کن و جوایز خفن ببر!\n\n"
        f"📊 **تعداد چرخش‌های شما:** {spin_count} بار\n"
        f"وضعیت: {status_str}\n\n"
        f"🎁 **لیست جوایز گردونه:**\n"
        f"{prizes_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=btn_data)],
        [
            InlineKeyboardButton(
                "🔄 به‌روزرسانی", callback_data="refresh_wheel"
            )
        ],
    ])

    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )
        except Exception:
            pass
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )


async def handle_wheel_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """مدیریت دکمه‌های گردونه شانس"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "wheel_cooldown":
        last_spin = db.get_user_field(user_id, "last_spin_time") or 0
        rem = COOLDOWN_SECONDS - (int(time.time()) - last_spin)
        if rem > 0:
            m, s = divmod(rem, 60)
            await query.answer(
                f"⏳ هنوز {m} دقیقه و {s} ثانیه زمان باقی مانده!",
                show_alert=True,
            )
        else:
            await show_wheel_panel(update, context)
        return

    elif data == "refresh_wheel":
        await query.answer("🔄 به‌روزرسانی شد")
        await show_wheel_panel(update, context)
        return

    elif data == "spin_wheel":
        now = int(time.time())
        last_spin = db.get_user_field(user_id, "last_spin_time") or 0

        if now - last_spin < COOLDOWN_SECONDS:
            await query.answer(
                "❌ زمان انتظار هنوز تمام نشده است!", show_alert=True
            )
            await show_wheel_panel(update, context)
            return

        # ثبت زمان و تعداد چرخش
        db.update_field(user_id, "last_spin_time", now, relative=False)
        db.update_field(user_id, "spin_count", 1, relative=True)

        # انیمیشن چرخش گردونه 🎡
        frames = [
            "🌀 گردونه در حال چرخش است...\n\n[ 🔴 | 🟡 | 🟢 | 🔵 ]",
            "🌀 گردونه در حال چرخش است...\n\n[ 🟡 | 🟢 | 🔵 | 🟣 ]",
            "🌀 گردونه در حال چرخش است...\n\n[ 🟢 | 🔵 | 🟣 | 🔴 ]",
            "🎯 گردونه در حال ایستادن است...",
        ]

        for frame in frames:
            try:
                await query.message.edit_text(
                    f"🎡 **گردونه شانس هاپو**\n\n{frame}",
                    parse_mode="Markdown",
                )
                await asyncio.sleep(0.6)
            except Exception:
                pass

        # انتخاب جایزه
        prize = pick_prize()
        db.update_field(user_id, prize["type"], prize["val"], relative=True)

        res_text = (
            f"🎉 **تبریک! شما برنده شدید!** 🎉\n\n"
            f"🎁 **جایزه شما:** {prize['name']}\n\n"
            f"به حساب/انبار شما اضافه شد! 5 دقیقه دیگر می‌توانید دوباره شانس خود را امتحان کنید."
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔙 بازگشت به گردونه", callback_data="refresh_wheel"
                )
            ]
        ])

        await query.message.edit_text(
            res_text, parse_mode="Markdown", reply_markup=keyboard
        )
