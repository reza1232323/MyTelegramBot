import sqlite3
from datetime import datetime, timedelta

DB_NAME = "hapo_advanced.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # جدول جامع کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        points INTEGER DEFAULT 100,
        gems INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        bank_balance INTEGER DEFAULT 0,
        
        dog_level INTEGER DEFAULT 0,
        dog_health INTEGER DEFAULT 100,
        dog_happiness INTEGER DEFAULT 100,
        dog_hunger INTEGER DEFAULT 100,
        dog_type TEXT DEFAULT 'معمولی',
        
        fishing_rod INTEGER DEFAULT 1,
        bones INTEGER DEFAULT 0,
        factory_level INTEGER DEFAULT 0,
        factory_type TEXT DEFAULT 'بدون کارخانه',
        factory_income INTEGER DEFAULT 0,
        
        in_jail_until TEXT,
        last_hop TEXT,
        last_income_claim TEXT
    )
    ''')

    # جدول ارزهای ساختنی در مارکت
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tokens (
        token_id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER,
        token_name TEXT UNIQUE,
        price INTEGER DEFAULT 100,
        investors_count INTEGER DEFAULT 0
    )
    ''')

    # سرمایه‌گذاری‌ها روی ارزها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS investments (
        user_id INTEGER,
        token_id INTEGER,
        amount INTEGER
    )
    ''')

    # جدول خزانه شهر
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS city (
        id INTEGER PRIMARY KEY,
        treasury INTEGER DEFAULT 0,
        total_hops INTEGER DEFAULT 0,
        total_dogs INTEGER DEFAULT 0,
        total_bones INTEGER DEFAULT 0,
        total_fish INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute("INSERT OR IGNORE INTO city (id, treasury) VALUES (1, 0)")

    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_user(user_id, username=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
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

def update_last_hop(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("UPDATE users SET last_hop = ? WHERE user_id = ?", (now_str, user_id))
    conn.commit()
    conn.close()

def check_level_up(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT points, level FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        points, current_level = row[0], row[1]
        new_level = (points // 100) + 1
        if new_level > current_level:
            cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user_id))
            conn.commit()
            conn.close()
            return True, new_level
    conn.close()
    return False, 1

def get_city():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT treasury, total_hops, total_dogs, total_bones, total_fish FROM city WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    return res

def update_city(field, val):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE city SET {field} = {field} + ? WHERE id = 1", (val,))
    conn.commit()
    conn.close()
