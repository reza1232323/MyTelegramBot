import sqlite3
import json
from datetime import datetime

DB_NAME = "hopo.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            hop_point REAL DEFAULT 500,
            hop_gem REAL DEFAULT 0,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            hopo_name TEXT DEFAULT "هاپوی من",
            hopo_breed TEXT DEFAULT "معمولی",
            hopo_stage TEXT DEFAULT "egg",
            hopo_health INTEGER DEFAULT 100,
            hopo_happiness INTEGER DEFAULT 100,
            hopo_energy INTEGER DEFAULT 100,
            hopo_hunger INTEGER DEFAULT 100,
            hopo_power INTEGER DEFAULT 1,
            hopo_hatch_time TEXT,
            factory_level INTEGER DEFAULT 0,
            factory_production REAL DEFAULT 0,
            factory_last_collect TEXT,
            bank_balance REAL DEFAULT 0,
            bank_interest REAL DEFAULT 0.05,
            bank_last_interest TEXT,
            daily_mission_done INTEGER DEFAULT 0,
            weekly_mission_done INTEGER DEFAULT 0,
            invite_code TEXT,
            invite_count INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_hop_claim REAL DEFAULT 0,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول آیتم‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # جدول فروشگاه
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price_hop REAL,
            price_gem REAL,
            emoji TEXT,
            stock INTEGER DEFAULT 999,
            is_available INTEGER DEFAULT 1
        )
    ''')
    
    # جدول مأموریت‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            type TEXT,
            target INTEGER,
            reward_hop REAL,
            reward_gem REAL,
            emoji TEXT
        )
    ''')
    
    # جدول تاریخچه بازی
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            bet REAL,
            win REAL,
            result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # اضافه کردن آیتم‌های اولیه فروشگاه
    cursor.execute("SELECT COUNT(*) FROM shop_items")
    if cursor.fetchone()[0] == 0:
        items = [
            ("غذا", "غذای هاپو", 20, 0, "🍖", 999, 1),
            ("اسباب‌بازی", "برای خوشحالی هاپو", 30, 0, "🧸", 999, 1),
            ("تخم طلایی", "هاپوی طلایی بدست بیار", 0, 5, "🥚", 50, 1),
            ("تقویت کننده", "قدرت هاپو رو زیاد کن", 100, 0, "⚡", 999, 1),
        ]
        cursor.executemany(
            "INSERT INTO shop_items (name, description, price_hop, price_gem, emoji, stock, is_available) VALUES (?,?,?,?,?,?,?)",
            items
        )
    
    # اضافه کردن مأموریت‌ها
    cursor.execute("SELECT COUNT(*) FROM missions")
    if cursor.fetchone()[0] == 0:
        missions = [
            ("۱۰ بار هاپ", "۱۰ بار دستور هاپ بزن", "daily", 10, 50, 0, "🎯"),
            ("۵۰ بار هاپ", "۵۰ بار دستور هاپ بزن", "weekly", 50, 200, 5, "🏆"),
        ]
        cursor.executemany(
            "INSERT INTO missions (name, description, type, target, reward_hop, reward_gem, emoji) VALUES (?,?,?,?,?,?,?)",
            missions
        )
    
    conn.commit()
    conn.close()

# اجرای اولیه
init_db()
