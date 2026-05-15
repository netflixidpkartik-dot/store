# TGAccsShop — Railway Deployment Guide

## Files required in your GitHub repo
```
store_bot.py
admin_bot.py
run_all.py
Procfile
requirements.txt
```

## Step 1 — Get a new bot token for Admin Bot
1. Open Telegram → @BotFather
2. Send /newbot → give it a name like "AccsShop Admin"
3. Copy the token

## Step 2 — Find your Telegram ID
Open @userinfobot on Telegram → it will show your numeric ID

## Step 3 — Edit admin_bot.py
```python
ADMIN_BOT_TOKEN = "YOUR_ADMIN_BOT_TOKEN"
ADMIN_IDS       = [YOUR_NUMERIC_ID]   # e.g. [987654321]
```

## Step 4 — Push to GitHub
```bash
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Step 5 — Deploy on Railway
1. Go to https://railway.app → New Project
2. Deploy from GitHub repo → select your repo
3. Railway auto-detects Procfile → click Deploy
4. Done! Both bots will run together.

## ⚠️ Important: Persistent Database on Railway
Railway's filesystem resets on redeploy (SQLite data lost).
To keep data permanently, add a Volume in Railway:
1. In your Railway project → Add Volume
2. Mount path: /data
3. In store_bot.py and admin_bot.py change:
   DB_FILE = "/data/tgaccs.db"

## Commands
- Store bot: /start
- Admin bot: /start (only works for IDs in ADMIN_IDS)
