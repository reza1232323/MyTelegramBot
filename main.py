import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import config
import database as db
from handlers import economy, games, pet, city, admin

logging.basicConfig(level=logging.INFO)
db.init_db()

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # ثبت‌نام خودکار
    user = db.get_user(user_id, username)

    # 🛑 ۱. بررسی پیوی (محدودیت استفاده فقط در گروه)
    if chat_type == 'private':
        if text.startswith("ثبت آگهی"):
            await economy.register_market_item(update, context)
        else:
            await update.message.reply_text(
                "❌ **برای استفاده از ربات، لطفا من را وارد یک گروه (گپ) کنید!**\n\n"
                "در پیوی فقط می‌توانید آگهی مارکت خود را ثبت و مدیریت کنید.",
                parse_mode='Markdown'
            )
        return

    # 🛑 ۲. دستورات گروه
    # دستورات عمومی
    if text == "هاپ":
        await pet.claim_hop(update, context, user)
    elif text in ["هاپوهام", "پروفایل"]:
        await pet.show_profile(update, context, user)
    elif text == "هاپ هاش":
        await pet.show_target_profile(update, context)
    elif text in ["لیدربرد", "برترین‌ها"]:
        await pet.show_leaderboard(update, context)
    elif text == "راهنما":
        await pet.show_help(update, context)

    # سگ و ماهیگیری
    elif text in ["سگ", "هاپو"]:
        await pet.dog_status(update, context, user)
    elif text == "استخوان":
        await pet.fish_bone(update, context, user)

    # اقتصاد
    # بخش اقتصاد
    elif text.startswith("بانک"):
        await economy.bank_status(update, context, user)
    elif text == "کارخونه":
        await economy.factory_status(update, context, user)
    elif text.startswith("انتقال"):
        await economy.transfer_points(update, context, user)
    elif text == "مارکت":
        await economy.show_market(update, context)

    # بازی‌ها
    elif text == "گردونه":
        await games.spin_wheel(update, context, user)
    elif text == "تاس":
        await games.roll_dice(update, context, user)

    # شهر و قاچاق
    elif text == "شهر":
        await city.city_info(update, context)
    elif text == "قاچاق":
        await city.smuggle(update, context, user)

    # دستورات ادمین
    elif user_id in config.ADMIN_IDS:
        if text.startswith("افزایش پوینت"):
            await admin.add_points(update, context)
        elif text.startswith("کاهش پوینت"):
            await admin.remove_points(update, context)

def main():
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, router))
    print("🤖 Hapo Advanced Bot Started...")
    app.run_polling()

if __name__ == '__main__':
    main()
