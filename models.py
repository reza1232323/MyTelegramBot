from database import get_db
from datetime import datetime
import random
import hashlib

class User:
    @staticmethod
    def get_or_create(telegram_user):
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE id = ?", (telegram_user.id,))
        user = cursor.fetchone()
        
        if not user:
            # ثبت‌نام جدید
            invite_code = hashlib.md5(str(telegram_user.id).encode()).hexdigest()[:8]
            cursor.execute('''
                INSERT INTO users (id, username, first_name, invite_code)
                VALUES (?, ?, ?, ?)
            ''', (telegram_user.id, telegram_user.username, telegram_user.first_name, invite_code))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE id = ?", (telegram_user.id,))
            user = cursor.fetchone()
            
            # چک کردن ریفرال
            # (در start با پارامتر مدیریت میشه)
        
        conn.close()
        return dict(user)
    
    @staticmethod
    def get(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    @staticmethod
    def update(user_id, **kwargs):
        conn = get_db()
        cursor = conn.cursor()
        for key, value in kwargs.items():
            cursor.execute(f"UPDATE users SET {key} = ? WHERE id = ?", (value, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_top_users(limit=10):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, first_name, hop_point, level FROM users ORDER BY hop_point DESC LIMIT ?",
            (limit,)
        )
        users = cursor.fetchall()
        conn.close()
        return [dict(u) for u in users]
    
    @staticmethod
    def get_hopo(user_id):
        user = User.get(user_id)
        if not user:
            return None
        return {
            "name": user["hopo_name"],
            "breed": user["hopo_breed"],
            "stage": user["hopo_stage"],
            "health": user["hopo_health"],
            "happiness": user["hopo_happiness"],
            "energy": user["hopo_energy"],
            "hunger": user["hopo_hunger"],
            "power": user["hopo_power"],
            "hatch_time": user["hopo_hatch_time"]
        }

class Inventory:
    @staticmethod
    def get_items(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory WHERE user_id = ?", (user_id,))
        items = cursor.fetchall()
        conn.close()
        return [dict(item) for item in items]
    
    @staticmethod
    def add_item(user_id, item_name, quantity=1):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)",
            (user_id, item_name, quantity)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def use_item(user_id, item_name):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        )
        item = cursor.fetchone()
        
        if not item or item["quantity"] < 1:
            conn.close()
            return False
        
        if item["quantity"] == 1:
            cursor.execute(
                "DELETE FROM inventory WHERE user_id = ? AND item_name = ?",
                (user_id, item_name)
            )
        else:
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ?",
                (user_id, item_name)
            )
        
        conn.commit()
        conn.close()
        return True

class Shop:
    @staticmethod
    def get_items():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shop_items WHERE is_available = 1")
        items = cursor.fetchall()
        conn.close()
        return [dict(item) for item in items]
    
    @staticmethod
    def get_item(item_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shop_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()
        conn.close()
        return dict(item) if item else None
    
    @staticmethod
    def buy(user_id, item_id, quantity=1):
        item = Shop.get_item(item_id)
        if not item:
            return {"success": False, "message": "آیتم پیدا نشد!"}
        
        user = User.get(user_id)
        if not user:
            return {"success": False, "message": "کاربر پیدا نشد!"}
        
        total_hop = item["price_hop"] * quantity
        total_gem = item["price_gem"] * quantity
        
        if total_hop > 0 and user["hop_point"] < total_hop:
            return {"success": False, "message": f"{total_hop:.1f} هاپ نیاز داری!"}
        
        if total_gem > 0 and user["hop_gem"] < total_gem:
            return {"success": False, "message": f"{total_gem:.1f} جم نیاز داری!"}
        
        # کاهش پول
        User.update(user_id, hop_point=user["hop_point"] - total_hop, hop_gem=user["hop_gem"] - total_gem)
        
        # اضافه به انبار
        Inventory.add_item(user_id, item["name"], quantity)
        
        return {"success": True, "message": f"{quantity} عدد {item['name']} خریداری شد!"}
