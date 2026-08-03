from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from datetime import datetime, timedelta
import random

# ==================== دیکشنری ماموریت‌ها ====================

DAILY_MISSIONS = [
    {"id": "daily_hop", "name": "🔥 هاپ زدن", "description": "۱۰ بار هاپ بزن", "target": 10, "reward_gem": 0, "reward_point": 500, "emoji": "🔥"},
    {"id": "daily_spin", "name": "🎡 گردونه شانس", "description": "۱ بار گردونه بچرخون", "target": 1, "reward_gem": 0, "reward_point": 200, "emoji": "🎡"},
    {"id": "daily_sell", "name": "💰 فروش محصول", "description": "۱ محصول بفروش", "target": 1, "reward_gem": 0, "reward_point": 300, "emoji": "💰"},
    {"id": "daily_feed", "name": "🍖 غذا دادن", "description": "۱ بار به سگت غذا بده", "target": 1, "reward_gem": 0, "reward_point": 200, "emoji": "🍖"},
]

WEEKLY_MISSIONS = [
    {"id": "weekly_hop", "name": "⚡ هاپ زدن", "description": "۵۰ بار هاپ بزن", "target": 50, "reward_gem": 1, "reward_point": 2000, "emoji": "⚡"},
    {"id": "weekly_invite", "name": "👥 دعوت دوستان", "description": "۱۰ نفر را با لینک خود دعوت کن", "target": 10, "reward_gem": 2, "reward_point": 5000, "emoji": "👥"},
    {"id": "weekly_spin", "name": "🎡 گردونه شانس", "description": "۵ بار گردونه بچرخون", "target": 5, "reward_gem": 1, "reward_point": 1000, "emoji": "🎡"},
    {"id": "weekly_factory", "name": "🏭 خرید کارخانه", "description": "۵ محصول از کارخانه بخر", "target": 5, "reward_gem": 1, "reward_point": 1500, "emoji": "🏭"},
]

# ==================== توابع ماموریت ====================

def get_user_missions(user_id):
    """دریافت وضعیت ماموریت‌های کاربر"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # ایجاد جدول ماموریت‌ها اگر وجود نداشت
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mission_id TEXT,
            mission_type TEXT,
            progress INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            claimed INTEGER DEFAULT 0,
            date TEXT,
            UNIQUE(user_id, mission_id, date)
        )
    """)
    conn.commit()
    
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    
    # دریافت ماموریت‌های روزانه
    daily_missions = []
    for mission in DAILY_MISSIONS:
        cursor.execute("""
            SELECT progress, completed, claimed FROM user_missions 
            WHERE user_id = ? AND mission_id = ? AND mission_type = 'daily' AND date = ?
        """, (user_id, mission["id"], today))
        result = cursor.fetchone()
        
        if result:
            progress, completed, claimed = result
        else:
            progress, completed, claimed = 0, 0, 0
            cursor.execute("""
                INSERT INTO user_missions (user_id, mission_id, mission_type, progress, completed, claimed, date)
                VALUES (?, ?, 'daily', 0, 0, 0, ?)
            """, (user_id, mission["id"], today))
            conn.commit()
        
        daily_missions.append({
            **mission,
            "progress": progress,
            "completed": completed,
            "claimed": claimed,
            "type": "daily"
        })
    
    # دریافت ماموریت‌های هفتگی
    weekly_missions = []
    for mission in WEEKLY_MISSIONS:
        cursor.execute("""
            SELECT progress, completed, claimed FROM user_missions 
            WHERE user_id = ? AND mission_id = ? AND mission_type = 'weekly' AND date >= ?
        """, (user_id, mission["id"], week_start))
        result = cursor.fetchone()
        
        if result:
            progress, completed, claimed = result
        else:
            progress, completed, claimed = 0, 0, 0
            cursor.execute("""
                INSERT INTO user_missions (user_id, mission_id, mission_type, progress, completed, claimed, date)
                VALUES (?, ?, 'weekly', 0, 0, 0, ?)
            """, (user_id, mission["id"], week_start))
            conn.commit()
        
        weekly_missions.append({
            **mission,
            "progress": progress,
            "completed": completed,
            "claimed": claimed,
            "type": "weekly"
        })
    
    conn.close()
    return daily_missions, weekly_missions


def update_mission_progress(user_id, mission_id, progress_increment=1):
    """به‌روزرسانی پیشرفت ماموریت"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    
    # بررسی روزانه
    cursor.execute("""
        SELECT progress, target FROM user_missions 
        JOIN (SELECT target, id FROM daily_missions) ON mission_id = id
        WHERE user_id = ? AND mission_id = ? AND mission_type = 'daily' AND date = ?
    """, (user_id, mission_id, today))
    result = cursor.fetchone()
    
    if result:
        progress, target = result
        new_progress = min(progress + progress_increment, target)
        completed = 1 if new_progress >= target else 0
        cursor.execute("""
            UPDATE user_missions SET progress = ?, completed = ? 
            WHERE user_id = ? AND mission_id = ? AND mission_type = 'daily' AND date = ?
        """, (new_progress, completed, user_id, mission_id, today))
        conn.commit()
        conn.close()
        return new_progress >= target
    
    # بررسی هفتگی
    cursor.execute("""
        SELECT progress, target FROM user_missions 
        JOIN (SELECT target, id FROM weekly_missions) ON mission_id = id
        WHERE user_id = ? AND mission_id = ? AND mission_type = 'weekly' AND date >= ?
    """, (user_id, mission_id, week_start))
    result = cursor.fetchone()
    
    if result:
        progress, target = result
        new_progress = min(progress + progress_increment, target)
        completed = 1 if new_progress >= target else 0
        cursor.execute("""
            UPDATE user_missions SET progress = ?, completed = ? 
            WHERE user_id = ? AND mission_id = ? AND mission_type = 'weekly' AND date >= ?
        """, (new_progress, completed, user_id, mission_id, week_start))
        conn.commit()
        conn.close()
        return new_progress >= target
    
    conn.close()
    return False


def claim_mission_reward(user_id, mission_id, mission_type):
    """دریافت پاداش ماموریت"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    
    if mission_type == "daily":
        cursor.execute("""
            SELECT completed, claimed, reward_gem, reward_point FROM user_missions 
            JOIN (SELECT reward_gem, reward_point, id FROM daily_missions) ON mission_id = id
            WHERE user_id = ? AND mission_id = ? AND mission_type = 'daily' AND date = ?
        """, (user_id, mission_id, today))
    else:
        cursor.execute("""
            SELECT completed, claimed, reward_gem, reward_point FROM user_missions 
            JOIN (SELECT reward_gem, reward_point, id FROM weekly_missions) ON mission_id = id
            WHERE user_id = ? AND mission_id = ? AND mission_type = 'weekly' AND date >= ?
        """, (user_id, mission_id, week_start))
    
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False, "ماموریت پیدا نشد!"
    
    completed, claimed, reward_gem, reward_point = result
    
    if not completed:
        conn.close()
        return False, "ماموریت کامل نشده است!"
    
    if claimed:
        conn.close()
        return False, "پاداش این ماموریت قبلاً دریافت شده!"
    
    # اعطای پاداش
    if reward_gem > 0:
        db.update_field(user_id, "hop_gem", reward_gem, relative=True)
    if reward_point > 0:
        db.update_field(user_id, "points", reward_point, relative=True)
    
    cursor.execute("""
        UPDATE user_missions SET claimed = 1 
        WHERE user_id = ? AND mission_id = ? AND mission_type = ? AND date = ?
    """, (user_id, mission_id, mission_type, today))
    conn.commit()
    conn.close()
    
    return True, f"✅ پاداش دریافت شد!\n💎 {reward_gem} جم\n💰 {reward_point} هاپ پوینت"


# ==================== دستور ماموریت‌ها ====================

async def missions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش ماموریت‌های روزانه و هفتگی"""
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    daily_missions, weekly_missions = get_user_missions(user_id)
    
    text = "🎯 **ماموریت‌های روزانه** 🎯\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for mission in daily_missions:
        status = "✅" if mission["claimed"] else "⬜"
        progress_bar = make_progress_bar(mission["progress"], mission["target"])
        text += f"{mission['emoji']} {mission['name']}\n"
        text += f"   {mission['description']}\n"
        text += f"   پیشرفت: {progress_bar} {mission['progress']}/{mission['target']}\n"
        if mission["completed"] and not mission["claimed"]:
            text += f"   🎁 قابل دریافت!\n"
        elif mission["claimed"]:
            text += f"   ✅ دریافت شد!\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    text += "\n🏆 **ماموریت‌های هفتگی** 🏆\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for mission in weekly_missions:
        status = "✅" if mission["claimed"] else "⬜"
        progress_bar = make_progress_bar(mission["progress"], mission["target"])
        text += f"{mission['emoji']} {mission['name']}\n"
        text += f"   {mission['description']}\n"
        text += f"   پیشرفت: {progress_bar} {mission['progress']}/{mission['target']}\n"
        if mission["completed"] and not mission["claimed"]:
            text += f"   🎁 قابل دریافت!\n"
        elif mission["claimed"]:
            text += f"   ✅ دریافت شد!\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 دریافت پاداش", callback_data="missions_claim")],
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="missions_refresh")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def missions_claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پاداش ماموریت‌ها"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    daily_missions, weekly_missions = get_user_missions(user_id)
    
    claimed = False
    for mission in daily_missions + weekly_missions:
        if mission["completed"] and not mission["claimed"]:
            success, message = claim_mission_reward(user_id, mission["id"], mission["type"])
            if success:
                claimed = True
    
    if claimed:
        await query.message.edit_text("✅ پاداش‌های قابل دریافت دریافت شد!")
    else:
        await query.message.edit_text("❌ هیچ پاداش قابل دریافت‌ای وجود ندارد!")
    
    await missions_command(update, context)


async def missions_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بروزرسانی ماموریت‌ها"""
    query = update.callback_query
    await query.answer()
    await missions_command(update, context)


def make_progress_bar(current, target):
    """ساخت نوار پیشرفت"""
    if target <= 0:
        return "⬜⬜⬜⬜⬜"
    percent = min(current / target, 1.0)
    filled = int(round(percent * 5))
    empty = 5 - filled
    return "🟩" * filled + "⬜" * empty
  # ==================== دکمه‌های ماموریت ====================

async def missions_claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پاداش ماموریت‌ها"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    daily_missions, weekly_missions = get_user_missions(user_id)
    
    claimed_any = False
    messages = []
    
    for mission in daily_missions + weekly_missions:
        if mission["completed"] and not mission["claimed"]:
            success, message = claim_mission_reward(user_id, mission["id"], mission["type"])
            if success:
                claimed_any = True
                messages.append(f"✅ {mission['emoji']} {mission['name']}: دریافت شد!")
    
    if claimed_any:
        text = "🎁 **پاداش‌ها دریافت شدند!**\n━━━━━━━━━━━━━━━━━━━\n\n"
        text += "\n".join(messages)
        await query.message.edit_text(text, parse_mode="Markdown")
    else:
        await query.message.edit_text("❌ هیچ پاداش قابل دریافت‌ای وجود ندارد!", parse_mode="Markdown")
    
    await asyncio.sleep(2)
    await missions_command(update, context)


async def missions_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بروزرسانی ماموریت‌ها"""
    query = update.callback_query
    await query.answer()
    await missions_command(update, context)


def make_progress_bar(current, target):
    """ساخت نوار پیشرفت"""
    if target <= 0:
        return "⬜⬜⬜⬜⬜"
    percent = min(current / target, 1.0)
    filled = int(round(percent * 5))
    empty = 5 - filled
    return "🟩" * filled + "⬜" * empty


# ==================== تابع بروزرسانی خودکار ماموریت‌ها ====================

async def update_missions_on_action(user_id, action_type, count=1):
    """بروزرسانی ماموریت‌ها بر اساس اقدام کاربر"""
    # ماموریت هاپ
    if action_type == "hop":
        update_mission_progress(user_id, "daily_hop", count)
        update_mission_progress(user_id, "weekly_hop", count)
    
    # ماموریت گردونه
    elif action_type == "spin":
        update_mission_progress(user_id, "daily_spin", count)
        update_mission_progress(user_id, "weekly_spin", count)
    
    # ماموریت فروش
    elif action_type == "sell":
        update_mission_progress(user_id, "daily_sell", count)
    
    # ماموریت غذا
    elif action_type == "feed":
        update_mission_progress(user_id, "daily_feed", count)
    
    # ماموریت کارخانه
    elif action_type == "factory":
        update_mission_progress(user_id, "weekly_factory", count)
    
    # ماموریت دعوت
    elif action_type == "invite":
        update_mission_progress(user_id, "weekly_invite", count)


# ==================== دستور ماموریت ====================

async def missions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش ماموریت‌های روزانه و هفتگی"""
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    daily_missions, weekly_missions = get_user_missions(user_id)
    
    text = "🎯 **ماموریت‌های روزانه** 🎯\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for mission in daily_missions:
        progress_bar = make_progress_bar(mission["progress"], mission["target"])
        status = "✅" if mission["claimed"] else "⬜"
        text += f"{mission['emoji']} **{mission['name']}**\n"
        text += f"   📝 {mission['description']}\n"
        text += f"   📊 پیشرفت: {progress_bar} `{mission['progress']}/{mission['target']}`\n"
        if mission["completed"] and not mission["claimed"]:
            text += f"   🎁 **قابل دریافت!**\n"
        elif mission["claimed"]:
            text += f"   ✅ دریافت شد!\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    text += "\n🏆 **ماموریت‌های هفتگی** 🏆\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for mission in weekly_missions:
        progress_bar = make_progress_bar(mission["progress"], mission["target"])
        status = "✅" if mission["claimed"] else "⬜"
        text += f"{mission['emoji']} **{mission['name']}**\n"
        text += f"   📝 {mission['description']}\n"
        text += f"   📊 پیشرفت: {progress_bar} `{mission['progress']}/{mission['target']}`\n"
        if mission["completed"] and not mission["claimed"]:
            text += f"   🎁 **قابل دریافت!**\n"
        elif mission["claimed"]:
            text += f"   ✅ دریافت شد!\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 دریافت همه پاداش‌ها", callback_data="missions_claim")],
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="missions_refresh")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ==================== تابع ریست ماموریت‌ها (هر روز) ====================

async def reset_daily_missions():
    """ریست ماموریت‌های روزانه (هر روز ساعت ۱۲ شب)"""
    while True:
        now = datetime.now()
        # محاسبه زمان تا نیمه شب
        next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
        sleep_seconds = (next_midnight - now).total_seconds()
        
        await asyncio.sleep(sleep_seconds)
        
        # ریست کردن ماموریت‌های روزانه
        conn = db.get_connection()
        cursor = conn.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        cursor.execute("DELETE FROM user_missions WHERE mission_type = 'daily' AND date <= ?", (yesterday,))
        conn.commit()
        conn.close()
        
        print("✅ ماموریت‌های روزانه ریست شدند!")
