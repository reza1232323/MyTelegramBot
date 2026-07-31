from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 خانه")],
            [KeyboardButton(text="🐣 هایوی من"), KeyboardButton(text="🎯 مأموریت‌ها")],
            [KeyboardButton(text="🏦 بانک"), KeyboardButton(text="🏭 کارخانه")],
            [KeyboardButton(text="🛒 فروشگاه"), KeyboardButton(text="🎒 کیف")],
            [KeyboardButton(text="🎡 گردونه شانس"), KeyboardButton(text="🎲 بازی‌ها")],
            [KeyboardButton(text="📊 لیدربرد"), KeyboardButton(text="🔗 دعوت دوستان")],
            [KeyboardButton(text="📖 راهنما")]
        ],
        resize_keyboard=True
    )

def group_menu():
    """منوی مخصوص گروه (با دکمه‌های محدودتر)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🐣 هایوی من"), KeyboardButton(text="📊 لیدربرد")],
            [KeyboardButton(text="🎡 گردونه شانس"), KeyboardButton(text="📖 راهنما")],
            [KeyboardButton(text="🏠 خانه")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 پنل مدیریت")],
            [KeyboardButton(text="📦 مدیریت مارکت")],
            [KeyboardButton(text="👥 لیست کاربران")],
            [KeyboardButton(text="🏠 خانه")]
        ],
        resize_keyboard=True
    )

def inline_home():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🐣 تغذیه هاپو", callback_data="feed_hopo")],
            [InlineKeyboardButton(text="😴 خواب هاپو", callback_data="sleep_hopo")],
            [InlineKeyboardButton(text="🎮 بازی با هاپو", callback_data="play_hopo")],
            [InlineKeyboardButton(text="🥚 باز کردن تخم", callback_data="hatch_hopo")]
        ]
    )

def inline_group_actions():
    """دکمه‌های مخصوص گروه"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🐣 پروفایل من", callback_data="group_profile")],
            [InlineKeyboardButton(text="🎡 گردونه", callback_data="group_spin")],
            [InlineKeyboardButton(text="📊 لیدربرد گروه", callback_data="group_leaderboard")]
        ]
    )

def inline_games():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 تاس", callback_data="game_dice")],
            [InlineKeyboardButton(text="🎡 گردونه", callback_data="game_spin")],
            [InlineKeyboardButton(text="🎰 کازینو", callback_data="game_casino")],
            [InlineKeyboardButton(text="♠️ قمار", callback_data="game_gamble")]
        ]
    )

def channel_check_kb(channels):
    keyboard = InlineKeyboardMarkup()
    for channel in channels:
        keyboard.add(InlineKeyboardButton(
            text=f"📢 عضویت در {channel['name']}",
            url=channel["url"]
        ))
    keyboard.add(InlineKeyboardButton(text="✅ عضویت رو تأیید کن", callback_data="check_channels"))
    return keyboard

def inline_reply_profile(target_id):
    """دکمه برای مشاهده پروفایل با ریپلای"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🐣 مشاهده پروفایل", callback_data=f"profile_{target_id}")]
        ]
    )
