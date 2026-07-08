import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "1000"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Dhaka")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set. Copy .env.example to .env and fill it in.")
