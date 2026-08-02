from telegram import Update
from telegram.ext import ContextTypes
import database as db
import config

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ این دستور را باید روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    if len(text) < 3 or not text[2].isdigit():
        await update.message.reply_text("💡 فرمت: `افزایش پوینت 100`")
        return
    target_id = update.message.reply_to_message.from_user.id
    amt = int(text[2])
    db.update_field(target_id, "points", amt, relative=True)
    await update.message.reply_text(f"✅ **{amt:,}** پوینت به کاربر اضافه شد.")

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    if len(text) < 3 or not text[2].isdigit():
        await update.message.reply_text("💡 فرمت: `کاهش پوینت 100`")
        return
    target_id = update.message.reply_to_message.from_user.id
    amt = int(text[2])
    db.update_field(target_id, "points", -amt, relative=True)
    await update.message.reply_text(f"✅ **{amt:,}** پوینت از کاربر کسر شد.")

async def add_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    amt = int(text[2]) if len(text) >= 3 and text[2].isdigit() else 1
    target_id = update.message.reply_to_message.from_user.id
    db.update_field(target_id, "level", amt, relative=True)
    await update.message.reply_text(f"✅ لول کاربر **{amt}** درجه افزایش یافت.")

async def remove_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ روی پیام کاربر ریپلای کنید!")
        return
    text = update.message.text.split()
    amt = int(text[2]) if len(text) >= 3 and text[2].isdigit() else 1
    target_id = update.message.reply_to_message.from_user.id
    db.update_field(target_id, "level", -amt, relative=True)
    await update.message.reply_text(f"✅ لول کاربر **{amt}** درجه کاهش یافت.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text.replace("همگانی", "").strip()
    if not msg_text:
        await update.message.reply_text("💡 فرمت: `همگانی متن پیام`")
        return
    await update.message.reply_text("📢 پیام همگانی ارسال شد.")

# ==================== دستورات ادمین برای جم (نسخه نهایی) ====================

async def add_gem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزایش جم کاربر (ادمین)"""
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ این دستور را باید روی پیام کاربر ریپلای کنید!")
        return
    
    if update.effective_user.id not in config.ADMIN_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید!")
        return
    
    text = update.message.text.split()
    if len(text) < 3 or not text[2].isdigit():
        await update.message.reply_text("💡 فرمت: `افزایش جم 10`")
        return
    
    target_id = update.message.reply_to_message.from_user.id
    amount = int(text[2])
    
    # ===== روش مستقیم با SQL =====
    import sqlite3
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # اول ببین ستون وجود داره یا نه
    try:
        cursor.execute("SELECT hop_gem FROM users WHERE user_id = ?", (target_id,))
        result = cursor.fetchone()
        if result:
            current = result[0] or 0
            new_amount = current + amount
            cursor.execute("UPDATE users SET hop_gem = ? WHERE user_id = ?", (new_amount, target_id))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"✅ **{amount:,}** جم به کاربر اضافه شد.\n"
                f"💎 موجودی جدید: {new_amount:,} جم"
            )
        else:
            conn.close()
            await update.message.reply_text("❌ کاربر پیدا نشد!")
    except sqlite3.OperationalError:
        # اگه ستون وجود نداشت، اضافه کن
        cursor.execute("ALTER TABLE users ADD COLUMN hop_gem INTEGER DEFAULT 0")
        conn.commit()
        cursor.execute("UPDATE users SET hop_gem = ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ **{amount:,}** جم به کاربر اضافه شد.")


async def remove_gem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاهش جم کاربر (ادمین)"""
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ این دستور را باید روی پیام کاربر ریپلای کنید!")
        return
    
    if update.effective_user.id not in config.ADMIN_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید!")
        return
    
    text = update.message.text.split()
    if len(text) < 3 or not text[2].isdigit():
        await update.message.reply_text("💡 فرمت: `کاهش جم 10`")
        return
    
    target_id = update.message.reply_to_message.from_user.id
    amount = int(text[2])
    
    import sqlite3
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT hop_gem FROM users WHERE user_id = ?", (target_id,))
        result = cursor.fetchone()
        if result:
            current = result[0] or 0
            if current < amount:
                conn.close()
                await update.message.reply_text(f"❌ کاربر فقط {current:,} جم دارد!")
                return
            new_amount = current - amount
            cursor.execute("UPDATE users SET hop_gem = ? WHERE user_id = ?", (new_amount, target_id))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"✅ **{amount:,}** جم از کاربر کسر شد.\n"
                f"💎 موجودی جدید: {new_amount:,} جم"
            )
        else:
            conn.close()
            await update.message.reply_text("❌ کاربر پیدا نشد!")
    except sqlite3.OperationalError:
        conn.close()
        await update.message.reply_text("❌ ستون جم در دیتابیس وجود ندارد!")
