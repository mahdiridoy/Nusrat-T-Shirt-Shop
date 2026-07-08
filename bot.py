import json
import logging
from datetime import datetime

import pytz
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TZ = pytz.timezone(config.TIMEZONE)


def today_str() -> str:
    """Calendar date in the configured timezone. Changes at local 00:00,
    which is what drives the daily reset (see database.py docstring)."""
    return datetime.now(TZ).strftime("%Y-%m-%d")


def watch_ad_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎬 Watch Ad", web_app=WebAppInfo(url=config.WEBAPP_URL))],
            [InlineKeyboardButton("📊 My Stats", callback_data="stats")],
        ]
    )


def status_text(count: int) -> str:
    remaining = max(config.DAILY_LIMIT - count, 0)
    return (
        f"📊 Today's progress: {count}/{config.DAILY_LIMIT}\n"
        f"Remaining: {remaining}\n"
        f"Resets daily at 00:00 ({config.TIMEZONE})."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = db.get_count(user_id, today_str())
    await update.message.reply_text(
        "👋 Welcome!\n\n" + status_text(count) + "\n\nTap below to watch an ad.",
        reply_markup=watch_ad_keyboard(),
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = db.get_count(user_id, today_str())
    await update.message.reply_text(status_text(count))


async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = db.get_count(user_id, today_str())
    await query.message.reply_text(status_text(count))


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fired when ad.html calls Telegram.WebApp.sendData() after an ad completes."""
    user_id = update.effective_user.id
    raw = update.effective_message.web_app_data.data

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        payload = {}

    if payload.get("status") != "watched":
        await update.effective_message.reply_text("⚠️ Ad not confirmed as watched.")
        return

    date_key = today_str()
    count = db.get_count(user_id, date_key)

    if count >= config.DAILY_LIMIT:
        await update.effective_message.reply_text(
            f"✅ You've already hit today's limit of {config.DAILY_LIMIT} ads.\n"
            f"Come back after 00:00 ({config.TIMEZONE})."
        )
        return

    new_count = db.increment(user_id, date_key)

    if new_count >= config.DAILY_LIMIT:
        await update.effective_message.reply_text(
            f"🎉 Ad counted! {new_count}/{config.DAILY_LIMIT}\n"
            f"That's your limit for today. See you after 00:00 ({config.TIMEZONE})!"
        )
    else:
        await update.effective_message.reply_text(
            f"✅ Ad counted! {new_count}/{config.DAILY_LIMIT}",
            reply_markup=watch_ad_keyboard(),
        )


def main():
    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(stats_callback, pattern="^stats$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    logger.info("Bot starting (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
