"""
config.py
----------
Central configuration, loaded from environment variables (see .env.example).
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
# Using the direct connection (port 5432) is recommended here since the bot
# keeps its own connection pool open for its whole lifetime. If you use the
# pooler instead (port 6543 / pgbouncer transaction mode), asyncpg needs
# statement_cache_size=0 - see the note in database.py's connect().
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

# --- Anti-spam fallback defaults ---
# Only used for a chat that hasn't set its own thresholds yet.
# NOTE: the time window is intentionally fixed at 3 seconds and no longer
# admin-configurable (see handlers/admin_commands.py) - simpler for a
# normal admin than tuning three separate numbers.
DEFAULT_SPAM_MESSAGE_LIMIT = int(os.getenv("SPAM_MESSAGE_LIMIT", 6))
DEFAULT_SPAM_TIME_WINDOW_SECONDS = int(os.getenv("SPAM_TIME_WINDOW_SECONDS", 3))
DEFAULT_SPAM_MUTE_MINUTES = int(os.getenv("SPAM_MUTE_MINUTES", 30))

# --- Stats ---
STATS_TOP_N = int(os.getenv("STATS_TOP_N", 15))

# --- Message log retention ---
# message_logs stores ONE ROW PER MESSAGE (needed for «آمار روزانه» and for
# «حذف N»/«حذف کل» to know real Telegram message_ids to delete) - unlike
# the running totals in group_users (messages_all_time), this table grows
# forever unless pruned. A background job (see bot.py) deletes rows older
# than this many days on a timer, keeping Supabase storage bounded
# regardless of how chatty a group is. «آمار کل» is unaffected (it's a
# counter, not row-based); «آمار روزانه» only ever needs 24h so this has
# huge headroom; «حذف کل» will only reach messages within this window,
# which matches what's actually useful anyway.
MESSAGE_LOG_RETENTION_DAYS = int(os.getenv("MESSAGE_LOG_RETENTION_DAYS", 3))

# --- Optional: shown as a button on /start if set ---
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/it_modi")

# --- Web-based message editor (/admin/messages) ---
# Leave both empty to disable the page entirely (returns 404) rather than
# ever accepting a blank/guessable login.
ADMIN_PANEL_USERNAME = os.getenv("ADMIN_PANEL_USERNAME", "")
ADMIN_PANEL_PASSWORD = os.getenv("ADMIN_PANEL_PASSWORD", "")

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
# اکانت‌های خودت قابل استفاده‌ست).
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