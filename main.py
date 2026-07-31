import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import config
from handlers import router
from database import init_db
import sys
import os

logging.basicConfig(level=logging.INFO)

if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)

async def main():
    init_db()
    print("✅ ربات هاپو راه‌اندازی شد!")
    print("📱 هم در پیوی و هم در گروه کار میکنه!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
