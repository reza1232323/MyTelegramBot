from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from datetime import datetime
import random

# ==================== دیکشنری مارکت ====================

market_items = {}  # {item_id: {user_id, name, price, description, emoji, quantity, created_at}}

# ==================== توابع مارکت ====================

def init_market_table():
    """ایجاد جدول مارکت در دیتابیس"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            item_emoji TEXT,
            price REAL,
            description TEXT,
            quantity INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

def get_market_items(limit=20):
    """دریافت آیتم‌های فعال مارکت"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, user_id, item_name, item_emoji, price, description, quantity, created_at
        FROM market_items 
        WHERE is_active = 1 AND quantity > 0
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    items = cursor.fetchall()
    conn.close()
    
    result = []
    for item in items:
        # دریافت نام کاربر فروشنده
        seller = db.get_user(item[1])
        seller_name = seller[1] if seller else "نامشخص"
        
        result.append({
            "id": item[0],
            "user_id": item[1],
            "seller_name": seller_name,
            "name": item[2],
            "emoji": item[3] or "📦",
            "price": item[4],
            "description": item[5] or "بدون توضیح",
            "quantity": item[6],
            "created_at": item[7]
        })
    
    return result

def add_market_item(user_id, name, price, description, emoji="📦", quantity=1):
    """افزودن آیتم به مارکت"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO market_items (user_id, item_name, item_emoji, price, description, quantity)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, name, emoji, price, description, quantity))
    
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return item_id

def buy_market_item(user_id, item_id, quantity=1):
    """خرید آیتم از مارکت"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id, item_name, item_emoji, price, quantity, description
        FROM market_items WHERE id = ? AND is_active = 1
    """, (item_id,))
    
    item = cursor.fetchone()
    
    if not item:
        conn.close()
        return False, "❌ آیتم پیدا نشد!"
    
    seller_id, item_name, item_emoji, price, available_qty, description = item
    
    if seller_id == user_id:
        conn.close()
        return False, "❌ نمی‌توانید آیتم خودتان را بخرید!"
    
    if quantity > available_qty:
        conn.close()
        return False, f"❌ فقط {available_qty} عدد از این آیتم موجود است!"
    
    # بررسی موجودی خریدار
    buyer_points = db.get_user_field(user_id, "points") or 0
    total_price = price * quantity
    
    if buyer_points < total_price:
        conn.close()
        return False, f"❌ موجودی کافی نیست! نیاز به {total_price:,} هاپ پوینت دارید."
    
    # انجام خرید
    db.update_field(user_id, "points", -total_price, relative=True)
    db.update_field(seller_id, "points", total_price, relative=True)
    
    # کاهش موجودی
    new_qty = available_qty - quantity
    if new_qty <= 0:
        cursor.execute("UPDATE market_items SET is_active = 0, quantity = 0 WHERE id = ?", (item_id,))
    else:
        cursor.execute("UPDATE market_items SET quantity = ? WHERE id = ?", (new_qty, item_id))
    
    conn.commit()
    conn.close()
    
    return True, f"✅ **خرید موفق!**\n━━━━━━━━━━━━━━━━━━━\n\n{item_emoji} **{item_name}**\n📦 تعداد: {quantity} عدد\n💰 قیمت: {total_price:,} هاپ\n📝 {description}"


def delete_market_item(user_id, item_id):
    """حذف آیتم از مارکت (فقط فروشنده)"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id FROM market_items WHERE id = ? AND is_active = 1
    """, (item_id,))
    
    item = cursor.fetchone()
    
    if not item:
        conn.close()
        return False, "❌ آیتم پیدا نشد!"
    
    if item[0] != user_id:
        conn.close()
        return False, "❌ شما اجازه حذف این آیتم را ندارید!"
    
    cursor.execute("UPDATE market_items SET is_active = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    return True, "✅ آیتم با موفقیت حذف شد!"


# ==================== دستورات مارکت ====================

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش مارکت"""
    user_id = update.effective_user.id
    
    in_jail, _ = is_user_in_jail(user_id)
    if in_jail:
        await update.message.reply_text("🔒 شما در زندان هستید! فقط از دستور `زندان` میتوانید استفاده کنید.")
        return
    
    is_joined = await check_user_membership(context.bot, user_id)
    if not is_joined:
        await send_must_join_message(update, context)
        return
    
    items = get_market_items(20)
    
    if not items:
        text = "🛒 **مارکت هاپو**\n━━━━━━━━━━━━━━━━━━━\n\n📭 هیچ آیتمی در مارکت وجود ندارد!\n\n💡 برای افزودن آیتم: `/افزودن آیتم`"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن آیتم", callback_data="market_add")],
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data="market_refresh")]
        ])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return
    
    text = "🛒 **مارکت هاپو** 🛒\n━━━━━━━━━━━━━━━━━━━\n\n"
    
    for item in items[:10]:
        text += f"{item['emoji']} **{item['name']}**\n"
        text += f"   👤 فروشنده: {item['seller_name']}\n"
        text += f"   💰 قیمت: {item['price']:,} هاپ\n"
        text += f"   📦 موجودی: {item['quantity']} عدد\n"
        text += f"   📝 {item['description']}\n"
        text += f"   🆔 {item['id']}\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن آیتم", callback_data="market_add")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="market_search")],
        [InlineKeyboardButton("📋 آیتم‌های من", callback_data="market_my_items")],
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="market_refresh")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def market_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزودن آیتم به مارکت"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    context.user_data['market_state'] = "waiting_name"
    await query.message.edit_text(
        "🛒 **افزودن آیتم به مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 لطفاً نام آیتم را وارد کنید:\n"
        "مثال: `کلاه طلایی`"
    )


async def handle_market_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت اطلاعات آیتم از کاربر"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = context.user_data.get('market_state')
    
    if not state:
        return False
    
    if state == "waiting_name":
        context.user_data['market_name'] = text
        context.user_data['market_state'] = "waiting_emoji"
        await update.message.reply_text(
            "🛒 **افزودن آیتم به مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
            "🎨 لطفاً ایموجی آیتم را وارد کنید:\n"
            "مثال: `👑` یا `🎩`\n\n"
            "💡 اگر نمی‌خواهید ایموجی بذارید، `-` را وارد کنید."
        )
        return True
    
    elif state == "waiting_emoji":
        if text == "-":
            context.user_data['market_emoji'] = "📦"
        else:
            context.user_data['market_emoji'] = text
        context.user_data['market_state'] = "waiting_price"
        await update.message.reply_text(
            "🛒 **افزودن آیتم به مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 لطفاً قیمت هر عدد را به هاپ پوینت وارد کنید:\n"
            "مثال: `500`"
        )
        return True
    
    elif state == "waiting_price":
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ قیمت باید بیشتر از صفر باشد!")
                return True
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
            return True
        
        context.user_data['market_price'] = price
        context.user_data['market_state'] = "waiting_description"
        await update.message.reply_text(
            "🛒 **افزودن آیتم به مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 لطفاً توضیحات آیتم را وارد کنید:\n"
            "مثال: `کلاه طلایی مخصوص هاپوها`\n\n"
            "💡 اگر توضیحی ندارید، `-` را وارد کنید."
        )
        return True
    
    elif state == "waiting_description":
        if text == "-":
            description = "بدون توضیح"
        else:
            description = text
        
        context.user_data['market_description'] = description
        context.user_data['market_state'] = "waiting_quantity"
        await update.message.reply_text(
            "🛒 **افزودن آیتم به مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 لطفاً تعداد موجودی را وارد کنید:\n"
            "مثال: `10`"
        )
        return True
    
    elif state == "waiting_quantity":
        try:
            quantity = int(text)
            if quantity <= 0:
                await update.message.reply_text("❌ تعداد باید بیشتر از صفر باشد!")
                return True
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
            return True
        
        # افزودن آیتم به مارکت
        name = context.user_data.get('market_name')
        emoji = context.user_data.get('market_emoji', '📦')
        price = context.user_data.get('market_price')
        description = context.user_data.get('market_description', 'بدون توضیح')
        
        item_id = add_market_item(user_id, name, price, description, emoji, quantity)
        
        # پاک کردن حالت
        context.user_data['market_state'] = None
        
        await update.message.reply_text(
            f"✅ **آیتم با موفقیت به مارکت اضافه شد!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} **{name}**\n"
            f"💰 قیمت: {price:,} هاپ\n"
            f"📦 موجودی: {quantity} عدد\n"
            f"📝 {description}\n"
            f"🆔 {item_id}\n\n"
            f"برای دیدن مارکت: **مارکت**"
        )
        return True
    
    return False


async def market_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خرید آیتم از مارکت"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    # فرمت: market_buy_123
    parts = data.split("_")
    item_id = int(parts[2])
    
    context.user_data['market_buy_item'] = item_id
    context.user_data['market_state'] = "waiting_buy_quantity"
    
    # دریافت اطلاعات آیتم
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_name, item_emoji, price, quantity FROM market_items WHERE id = ? AND is_active = 1
    """, (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        await query.message.reply_text("❌ آیتم پیدا نشد!")
        return
    
    await query.message.reply_text(
        f"🛒 **خرید آیتم**\n━━━━━━━━━━━━━━━━━━━\n\n"
        f"{item[1]} **{item[0]}**\n"
        f"💰 قیمت هر عدد: {item[2]:,} هاپ\n"
        f"📦 موجودی: {item[3]} عدد\n\n"
        f"📝 لطفاً تعداد مورد نظر را وارد کنید:"
    )


async def market_my_items_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آیتم‌های من در مارکت"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, item_name, item_emoji, price, quantity, created_at
        FROM market_items 
        WHERE user_id = ? AND is_active = 1
        ORDER BY created_at DESC
    """, (user_id,))
    
    items = cursor.fetchall()
    conn.close()
    
    if not items:
        await query.message.edit_text(
            "📋 **آیتم‌های من در مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
            "📭 شما هیچ آیتمی در مارکت ندارید!\n\n"
            "💡 برای افزودن آیتم: `/افزودن آیتم`"
        )
        return
    
    text = "📋 **آیتم‌های من در مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
    
    for item in items:
        text += f"{item[2]} **{item[1]}**\n"
        text += f"   💰 قیمت: {item[3]:,} هاپ\n"
        text += f"   📦 موجودی: {item[4]} عدد\n"
        text += f"   🆔 {item[0]}\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن آیتم", callback_data="market_add")],
        [InlineKeyboardButton("🔙 بازگشت به مارکت", callback_data="market_back")]
    ])
    
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def market_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به مارکت"""
    query = update.callback_query
    await query.answer()
    await market_command(update, context)


async def market_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بروزرسانی مارکت"""
    query = update.callback_query
    await query.answer()
    await market_command(update, context)


async def market_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جستجو در مارکت"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['market_state'] = "waiting_search"
    await query.message.edit_text(
        "🔍 **جستجو در مارکت**\n━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 لطفاً نام آیتم مورد نظر را وارد کنید:"
    )


async def handle_market_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جستجو و نمایش نتایج"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('market_state') != "waiting_search":
        return False
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, item_name, item_emoji, price, description, quantity
        FROM market_items 
        WHERE is_active = 1 AND quantity > 0 AND item_name LIKE ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (f"%{text}%",))
    
    items = cursor.fetchall()
    conn.close()
    
    context.user_data['market_state'] = None
    
    if not items:
        await update.message.reply_text(f"🔍 **نتیجه جستجو برای `{text}`**\n━━━━━━━━━━━━━━━━━━━\n\n📭 هیچ آیتمی پیدا نشد!")
        return True
    
    text = f"🔍 **نتیجه جستجو برای `{text}`**\n━━━━━━━━━━━━━━━━━━━\n\n"
    
    for item in items:
        seller = db.get_user(item[1])
        seller_name = seller[1] if seller else "نامشخص"
        
        text += f"{item[3]} **{item[2]}**\n"
        text += f"   👤 فروشنده: {seller_name}\n"
        text += f"   💰 قیمت: {item[4]:,} هاپ\n"
        text += f"   📦 موجودی: {item[6]} عدد\n"
        text += f"   🆔 {item[0]}\n"
        text += "━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به مارکت", callback_data="market_back")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    return True
