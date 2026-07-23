async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"/start از کاربر {user_id} (@{username})")

    try:
        # ===== بررسی عضویت با try/except =====
        try:
            member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            is_member_flag = member.status in ["member", "administrator", "creator"]
        except Exception as e:
            logger.error(f"خطا در بررسی عضویت: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ ربات به کانال دسترسی ندارد!\n"
                "لطفاً ربات را به کانال اضافه کنید و ادمین کنید."
            )
            return

        # ===== اگر عضو نیست =====
        if not is_member_flag:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 جوین کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
                [InlineKeyboardButton("✅ تایید عضویت", callback_data="check_sub")]
            ])
            await update.message.reply_text(
                f"🔒 برای استفاده از ربات، ابتدا در کانال عضو شوید:\n\n"
                f"📢 {CHANNEL_USERNAME}\n\n"
                "بعد از عضویت، دکمه تایید رو بزن.",
                reply_markup=keyboard
            )
            return

        # ===== ثبت کاربر =====
        try:
            create_user(user_id, username)
        except Exception as e:
            logger.error(f"خطا در ثبت کاربر: {e}")

        # ===== منوی اصلی =====
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 خرید تون", callback_data="buy_ton")],
            [InlineKeyboardButton("⭐ خرید استارز", callback_data="buy_stars")],
            [InlineKeyboardButton("📊 سفارشات من", callback_data="my_orders")],
        ])

        await update.message.reply_text(
            "🌟 به فروشگاه استارز لند خوش آمدی! 🌟\n\n"
            "🪙 تون: 340,000 تومن\n"
            "⭐ استارز رو پست: 4,000 تومن هر عدد\n\n"
            "👇 یکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {type(e).__name__} - {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ خطا: {type(e).__name__}\n"
            "لطفاً دوباره /start رو بزن."
        )
