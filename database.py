import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # ساخت جدول اگر وجود ندارد
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            dog_status TEXT DEFAULT 'بدون سگ',
            bank_balance INTEGER DEFAULT 0,
            account_number TEXT,
            last_hop TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user_field(user_id, field):
    conn = sqlite3.connect('database.db')
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
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if relative and isinstance(value, (int, float)):
        cursor.execute(f"UPDATE users SET {field} = {field} + ? WHERE user_id = ?", (value, user_id))
    else:
        cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()
