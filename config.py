"""
config.py
----------
Central configuration, loaded from environment variables (see .env.example).

This bot is standalone (a separate bot/repo from ghormanagmentBot) - it
only does one thing: play music in a group's voice chat, gated by the same
owner/owner2/admin role hierarchy (no VIP tier here).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --- Optional outbound proxy for reaching api.telegram.org ---
# Leave empty if you can reach Telegram directly. If you're somewhere that
# blocks it, point this at a local SOCKS5/HTTP proxy you already have
# running, e.g. "socks5://127.0.0.1:10808". Requires the aiohttp-socks
# package (already in requirements.txt) for socks5:// URLs.
PROXY_URL = os.getenv("PROXY_URL", "")

# --- Database: direct asyncpg connection to your Supabase Postgres ---
# Find these in Supabase: Project Settings -> Database -> Connection info.
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "postgres")

# --- Owners ---
# Comma-separated Telegram numeric user IDs (get yours from @userinfobot).
# Full access, every group, always - this bootstrap never depends on the
# database, so it always works even if something else is misconfigured.
OWNER_USER_IDS = {
    int(uid) for uid in os.getenv("OWNER_USER_IDS", "").split(",") if uid.strip().isdigit()
}

# --- Run mode: webhook (server) vs polling (local) ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", 8080)))

# --- Music (پخش موزیک در ویس‌چت) ---
# پخش نیاز به یک یا چند «یوزربات» دارد - اکانتِ واقعیِ تلگرام (نه ربات) که
# وارد ویس‌چتِ گروه می‌شود. چند تا از این‌ها با هم یک «استخر» (pool) تشکیل
# می‌دهند تا بشود هم‌زمان در چند گروه پخش کرد بدون این‌که یک اکانت تنها زیر
# فشار بمونه؛ هر گروه دائمی به یکی از این یوزربات‌ها «چسبانده» می‌شود (اولین
# باری که توی اون گروه پخش انجام می‌شه - نگاه کن به music/pool.py).
#
# سشن‌ها با اجرای مستقلِ tools/generate_userbot_session.py ساخته می‌شن (نه
# با اجرای خودِ ربات) - این اسکریپت رو یک‌بار به‌ازای هر اکانتی که می‌خوای
# به استخر اضافه کنی، لوکال اجرا کن و رشته‌ی خروجی رو اینجا کپی کن.
#
# API_ID/API_HASH رو از my.telegram.org می‌گیری (یک‌بار کافیه، برای همه‌ی
# اکانت‌های خودت قابل استفاده‌ست - نه یک جفت جدا برای هر اکانت).
USERBOT_API_ID = int(os.getenv("USERBOT_API_ID", 0))
USERBOT_API_HASH = os.getenv("USERBOT_API_HASH", "")

# رشته‌های StringSession، جدا شده با کاما - یکی به‌ازای هر یوزربات توی استخر.
# مثال: USERBOT_SESSIONS="1BVtsOK...session1,1BVtsOK...session2"
USERBOT_SESSIONS = os.getenv("USERBOT_SESSIONS", "")

# مدت بیکاریِ مجاز (ثانیه) پیش از این‌که یوزربات خودکار از ویس‌چت خارج بشه.
MUSIC_IDLE_TIMEOUT_SECONDS = int(os.getenv("MUSIC_IDLE_TIMEOUT_SECONDS", 180))

# جستجو/دانلود از یوتیوب (اختیاری، جدا از حالتِ «ریپلای فایل»). سرورهای
# ابری (Render هم همین‌طور) معمولاً بدونِ کوکیِ یک اکانتِ واقعیِ یوتیوب توسط
# خودِ یوتیوب «ربات» تشخیص داده و بلاک می‌شن؛ اگه فایلِ cookies.txt رو کنارِ
# ربات بذاری (همون‌جایی که این فایل هست)، این ماژول خودکار ازش استفاده
# می‌کنه. حتی با کوکی هم تضمینی نیست - اگه یوتیوب دوباره بلاک کرد، فقط
# حالتِ «ریپلای فایل» کار می‌کنه (music/youtube.py پیامِ خطای واضح می‌ده).
YOUTUBE_COOKIES_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "cookies.txt")

# آیدیِ/یوزرنیمِ پشتیبانی (اختیاری، مثلاً "@YourSupportUsername") - وقتی
# هیچ‌کدوم از یوزربات‌های استخر عضوِ یک گروه نیستن (پس نمی‌شه پخش کرد)،
# پیامِ خطا هم لیستِ یوزرنیمِ یوزربات‌ها رو نشون می‌ده هم این آیدی رو، تا
# ادمینِ گروه اگه خودش نتونست اضافه‌شون کنه، مستقیم به پشتیبانی پیام بده.
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "https://t.me/IT_NAJI")