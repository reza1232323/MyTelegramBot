import sqlite3
from datetime import datetime

DB_NAME = "hapo_advanced.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # جدول کامل کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        points INTEGER DEFAULT 100,
        gems INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        bank_balance INTEGER DEFAULT 0,
        
        -- ویژگی‌های هاپو (سگ)
        dog_level INTEGER DEFAULT 1,
        dog_health INTEGER DEFAULT 100,
        dog_happiness INTEGER DEFAULT 100,
        dog_hunger INTEGER DEFAULT 100,
        dog_type TEXT DEFAULT 'معمولی',
        
        -- ابزارها و کارخانه
        fishing_rod INTEGER DEFAULT 1,
        bones INTEGER DEFAULT 0,
        factory_level INTEGER DEFAULT 0,
        factory_income INTEGER DEFAULT 0,
        
        -- وضعیت‌ها
        in_jail INTEGER DEFAULT 0,
        is_smuggler INTEGER DEFAULT 0,
        invites_count INTEGER DEFAULT 0,
        last_hop TIMESTAMP
    )
    ''')

    # جدول مارکت (خرید و فروش)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS market (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        item_name TEXT,
        price INTEGER,
        status TEXT DEFAULT 'pending'
    )
    ''')

    conn.commit()
    conn.close()

def get_user(user_id, username=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()
    return user

def update_field(user_id, field, value, relative=True):
    conn = get_connection()
    cursor = conn.cursor()
    if relative:
        cursor.execute(f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?", (value, user_id))
    else:
        cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def get_top_players(limit=10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, points, level FROM users ORDER BY points DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows