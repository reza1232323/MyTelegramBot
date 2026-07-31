import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    
    REQUIRED_CHANNELS = [
        {
            "name": os.getenv("CHANNEL_1_NAME", "کانال اول"),
            "username": os.getenv("CHANNEL_1_USERNAME", "@esmok_shop_poy"),
            "url": os.getenv("CHANNEL_1_URL", "https://t.me/esmok_shop_poy")
        },
        {
            "name": os.getenv("CHANNEL_2_NAME", "کانال دوم"),
            "username": os.getenv("CHANNEL_2_USERNAME", "@CODMSAOPZX"),
            "url": os.getenv("CHANNEL_2_URL", "https://t.me/CODMSAOPZX")
        }
    ]

config = Config()
