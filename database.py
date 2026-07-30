from datetime import datetime, timedelta
import sqlite3

DB_NAME = "database.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # جدول کاربران
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            hops INTEGER DEFAULT 0,
            level_hops_progress INTEGER DEFAULT 0,
            last_hop_time INTEGER DEFAULT 0,
            dogs INTEGER DEFAULT 0,
            dog_status TEXT DEFAULT 'بدون سگ',
            dog_health INTEGER DEFAULT 0,
            bank_balance INTEGER DEFAULT 0,
            account_number TEXT,
            last_hop TEXT,
            factory_count INTEGER DEFAULT 0,
            in_jail INTEGER DEFAULT 0,
            jail_until TEXT DEFAULT NULL,
            inviter_id INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            inventory_diamond INTEGER DEFAULT 0,
            inventory_cig INTEGER DEFAULT 0,
            inventory_choco INTEGER DEFAULT 0,
            inventory_car INTEGER DEFAULT 0,
            inventory_gold INTEGER DEFAULT 0,
            inventory_clothes INTEGER DEFAULT 0,
            inventory_food INTEGER DEFAULT 0,
            inventory_toy INTEGER DEFAULT 0,
            inventory_house INTEGER DEFAULT 0
        )
    """)

    # جدول متغیرهای عمومی
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_vars (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)

    # جدول اهدایی‌های شهر
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS city_donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # جدول تنظیمات عمومی و سطح شهر
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id, username="کاربر"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()
    return user


def get_user_field(user_id, field):
    # نگاشت نام‌های مستعار برای بانک
    if field == "bank":
        field = "bank_balance"

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"SELECT {field} FROM users WHERE user_id = ?", (user_id,)
        )
        res = cursor.fetchone()
        return res[0] if res and res[0] is not None else 0
    except Exception:
        return 0
    finally:
        conn.close()


def update_field(user_id, field, value, relative=False):
    # نگاشت نام‌های مستعار برای بانک
    if field == "bank":
        field = "bank_balance"

    conn = get_connection()
    cursor = conn.cursor()

    # اطمینان از وجود کاربر در دیتابیس
    get_user(user_id)

    try:
        if relative and isinstance(value, (int, float)):
            cursor.execute(
                f"UPDATE users SET {field} = COALESCE({field}, 0) + ? WHERE user_id = ?",
                (value, user_id),
            )
        else:
            cursor.execute(
                f"UPDATE users SET {field} = ? WHERE user_id = ?",
                (value, user_id),
            )
        conn.commit()
    except Exception as e:
        print(f"Error updating field {field}: {e}")
    finally:
        conn.close()


def get_or_create_account_number(user_id):
    acc = get_user_field(user_id, "account_number")
    if not acc or acc == 0:
        import random

        acc = str(random.randint(1000000000, 9999999999))
        update_field(user_id, "account_number", acc, relative=False)
    return acc


def get_global_field(key):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM global_vars WHERE key = ?", (key,))
        res = cursor.fetchone()
        return res[0] if res else 0
    except Exception:
        return 0
    finally:
        conn.close()


def update_global_field(key, amount):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO global_vars (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
            (key, amount, amount),
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating global field {key}: {e}")
    finally:
        conn.close()


# ----------------- متدهای مربوط به زندان -----------------


def set_jail(user_id, minutes=15):
    jail_until = (datetime.now() + timedelta(minutes=minutes)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    update_field(user_id, "in_jail", 1, relative=False)
    update_field(user_id, "jail_until", jail_until, relative=False)


def is_in_jail(user_id):
    jail_until_str = get_user_field(user_id, "jail_until")
    if jail_until_str and isinstance(jail_until_str, str):
        try:
            jail_until = datetime.strptime(jail_until_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < jail_until:
                return True, jail_until
        except ValueError:
            pass

    release_from_jail(user_id)
    return False, None


def release_from_jail(user_id):
    update_field(user_id, "in_jail", 0, relative=False)
    update_field(user_id, "jail_until", None, relative=False)


# ----------------- متدهای مربوط به آمار شهر -----------------


def get_city_treasury(chat_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SUM(amount) FROM city_donations")
        res = cursor.fetchone()
        return res[0] if res and res[0] is not None else 0
    except Exception:
        return 0
    finally:
        conn.close()


def add_city_donation(user_id, amount=0):
    if isinstance(user_id, (int, float)) and amount == 0:
        amount = user_id
        user_id = 0

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO city_donations (user_id, amount) VALUES (?, ?)",
            (user_id, amount),
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding city donation: {e}")
    finally:
        conn.close()


def add_city_treasury(amount, chat_id=None):
    add_city_donation(0, amount)


def get_total_hops(chat_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SUM(hops) FROM users")
        res = cursor.fetchone()
        return res[0] if res and res[0] is not None else 0
    except Exception:
        return 0
    finally:
        conn.close()


def get_total_dogs(chat_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SUM(dogs) FROM users")
        res = cursor.fetchone()
        return res[0] if res and res[0] is not None else 0
    except Exception:
        return 0
    finally:
        conn.close()


def get_total_item(column_name, chat_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT SUM({column_name}) FROM users")
        res = cursor.fetchone()
        return res[0] if res and res[0] is not None else 0
    except Exception:
        return 0
    finally:
        conn.close()


def get_city_level(chat_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE key='city_level'")
        res = cursor.fetchone()
        return int(res[0]) if res and res[0] else 1
    except Exception:
        return 1
    finally:
        conn.close()


def set_city_level(arg1, arg2=None):
    level = arg1
    if arg2 is not None:
        if isinstance(arg1, int) and arg1 < 0:
            level = arg2
        elif isinstance(arg2, int) and arg2 < 100:
            level = arg2

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES ('city_level', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (str(level), str(level)),
        )
        conn.commit()
    except Exception as e:
        print(f"Error setting city level: {e}")
    finally:
        conn.close()


# توابع مستعار (Alias)
get_group_total_hops = get_total_hops
get_group_total_dogs = get_total_dogs


# ----------------- متدهای مربوط به زیرمجموعه‌گیری -----------------


def set_inviter(user_id, inviter_id):
    """ثبت معرف برای کاربر جدید (در صورتی که قبلاً معرف نداشته باشد)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT inviter_id FROM users WHERE user_id = ?", (user_id,)
        )
        res = cursor.fetchone()

        if res and (res[0] is None or res[0] == 0) and user_id != inviter_id:
            cursor.execute(
                "UPDATE users SET inviter_id = ? WHERE user_id = ?",
                (inviter_id, user_id),
            )
            cursor.execute(
                "UPDATE users SET referral_count = COALESCE(referral_count, 0) + 1 WHERE user_id = ?",
                (inviter_id,),
            )
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error setting inviter: {e}")
        return False
    finally:
        conn.close()


def get_referral_stats(user_id):
    """دریافت آمار زیرمجموعه‌های کاربر"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COALESCE(referral_count, 0) FROM users WHERE user_id = ?",
            (user_id,),
        )
        res = cursor.fetchone()
        return res[0] if res else 0
    except Exception:
        return 0
    finally:
        conn.close()


# ساخت خودکار جداول هنگام اجرای برنامه
init_db()
