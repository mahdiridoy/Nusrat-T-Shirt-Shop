import json
import logging
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytz
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
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


def watch_ad_keyboard() -> ReplyKeyboardMarkup:
    # IMPORTANT: tg.sendData() (used by ad.html to report a completed view)
    # only works for Web Apps launched from a *keyboard* button. Web Apps
    # launched from an *inline* button never trigger the bot's
    # web_app_data update, so counts silently never increment. Hence
    # ReplyKeyboardMarkup + KeyboardButton here instead of an inline one.
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 Watch Ad", web_app=WebAppInfo(url=config.WEBAPP_URL))],
            [KeyboardButton("📊 My Stats")],
        ],
        resize_keyboard=True,
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


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        # UptimeRobot (and some health checkers) send HEAD, not GET.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence request logging


def _start_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info(f"Health check server listening on port {port}")
    server.serve_forever()


def main():
    db.init_db()

    # Render (free Web Service) requires an open port or it kills the
    # service. This thread satisfies that check; it does nothing else.
    threading.Thread(target=_start_health_server, daemon=True).start()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.Regex("^📊 My Stats$"), stats))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    logger.info("Bot starting (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
