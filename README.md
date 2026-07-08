# Telegram Ad Bot (Monetag, 1000/day per user, resets at 00:00)

## How it works

- Bot sends a "🎬 Watch Ad" button that opens `ad.html` as a **Telegram
  WebApp** (an in-app browser view — real ad iframes can't be embedded
  directly in a chat message, so this is the standard pattern).
- `ad.html` loads the Monetag SDK and shows a **Rewarded Interstitial**.
- Once the user finishes watching, the page calls
  `Telegram.WebApp.sendData(...)`, which delivers a signed message back to
  your bot. The bot increments that user's counter for today.
- Counters are stored per `(user_id, date)` in SQLite. When the date rolls
  over at local midnight, every user automatically starts back at 0/1000 —
  no cron job needed, nothing to forget to run.
- Once a user hits 1000 for the day, further ad views are rejected until
  the next calendar day.

Note: this is a **long-running bot process** (it polls Telegram
continuously), not a scheduled job — it needs a host that stays on
(VPS, Railway, Render, Fly.io, PythonAnywhere always-on task, etc.),
unlike your GitHub Actions IPTV workflows which run on a schedule and exit.

---

## 1. Set up Monetag

1. Log into your Monetag publisher dashboard.
2. Create (or open) a **Rewarded Interstitial** zone.
3. Copy your **Zone ID**.
4. In `webapp/ad.html`, replace every occurrence of `YOUR_ZONE_ID` with
   your real zone ID (there are 3: the `data-zone` attribute, the
   `data-sdk` attribute value `show_YOUR_ZONE_ID`, and the JS function
   call `show_YOUR_ZONE_ID()`). They must match exactly.

## 2. Create the bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram.
2. `/newbot` → follow prompts → copy the **bot token**.

## 3. Host the WebApp page (needs HTTPS)

Pick any static host — simplest options:

**GitHub Pages**
```bash
# inside webapp/
git init
git add ad.html
git commit -m "ad webapp"
git branch -M main
git remote add origin https://github.com/YOUR_USER/ad-bot-webapp.git
git push -u origin main
# then enable Pages in repo Settings → Pages → deploy from main branch
```
Your URL will look like `https://YOUR_USER.github.io/ad-bot-webapp/ad.html`.

**Or Vercel / Netlify**: drag-and-drop the `webapp/` folder in their
dashboard — both give you an HTTPS URL instantly.

## 4. Configure the bot

```bash
cd telegram_ad_bot
cp .env.example .env
```

Edit `.env`:
```
BOT_TOKEN=<token from BotFather>
WEBAPP_URL=<your hosted ad.html HTTPS URL>
DAILY_LIMIT=1000
TIMEZONE=Asia/Dhaka
```

## 5. Install & run

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

Message your bot `/start` on Telegram — you should see the "Watch Ad"
button.

## 6. Keep it running in production

Simple option, on any Linux VPS:
```bash
sudo apt install -y python3-pip
pip install -r requirements.txt
nohup python3 bot.py > bot.log 2>&1 &
```

More robust: run it as a `systemd` service or inside a small Docker
container with `restart: always`, so it survives reboots/crashes.

---

## Testing

1. Send `/start` to the bot.
2. Tap **Watch Ad** — the WebApp opens and Monetag's ad should load.
3. Watch/complete it — the page closes and the bot replies with your
   updated count (`1/1000`).
4. Send `/stats` any time to check progress.
5. To test the reset without waiting for midnight, either temporarily
   change your system clock, or manually edit a row's `date_key` in
   `ads.db` (SQLite) to yesterday's date and confirm the count starts
   fresh.

---

## Important notes

- **Fraud resistance**: this build trusts the client-side `sendData()`
  call, which is fine for low-stakes use but is technically spoofable by
  a user opening dev tools. If real payouts depend on ad-view accuracy at
  scale, ask Monetag support about **S2S (server-to-server) postbacks**
  for Rewarded formats — Monetag calls your server directly once its own
  system confirms the view, which is much harder to fake. I can build
  that Flask endpoint too if you want to move to that model later.
- **Per-user vs global limit**: this build enforces 1000/day *per user*,
  as you specified. If you ever want a bot-wide daily cap instead, that's
  a one-line change to `database.py` (key by date only, not by user_id).
- Monetag's exact SDK function name can vary by ad format/zone type —
  double check the embed snippet shown in your specific zone's dashboard
  page and mirror it in `ad.html` if it differs from `show_<ZoneID>`.
