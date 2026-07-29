import sqlite3

DB_NAME = 'database.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # ساخت جدول اصلی کاربران همراه با تمام ستون‌های مورد نیاز
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            dog_status TEXT DEFAULT 'بدون سگ',
            dog_health INTEGER DEFAULT 0,
            bank_balance INTEGER DEFAULT 0,
            account_number TEXT,
            last_hop TEXT,
            factory_count INTEGER DEFAULT 0,
            in_jail INTEGER DEFAULT 0,
            inventory_diamond INTEGER DEFAULT 0,
            inventory_cig INTEGER DEFAULT 0,
            inventory_choco INTEGER DEFAULT 0
        )
    ''')

    # ساخت جدول برای متغیرهای کلی سیستم (مثل صندوق شهر)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_vars (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def get_user(user_id, username="کاربر"):
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

def get_user_field(user_id, field):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT {field} FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        return res[0] if res else None
    except:
        return None
    finally:
        conn.close()

def update_field(user_id, field, value, relative=True):
    conn = get_connection()
    cursor = conn.cursor()
    if relative and isinstance(value, (int, float)):
        cursor.execute(f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?", (value, user_id))
    else:
        cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def get_or_create_account_number(user_id):
    acc = get_user_field(user_id, "account_number")
    if not acc:
        import random
        acc = str(random.randint(1000000000, 9999999999))
        update_field(user_id, "account_number", acc, relative=False)
    return acc

def get_global_field(key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_vars WHERE key = ?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def update_global_field(key, amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO global_vars (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?", (key, amount, amount))
    conn.commit()
    conn.close()
