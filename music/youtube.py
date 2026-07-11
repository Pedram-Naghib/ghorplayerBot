"""
music/youtube.py
-------------------
جستجو/دانلودِ آهنگ از یوتیوب با yt-dlp، برای دستورِ «پخش آهنگ <عبارت یا لینک>».

⚠️ نکته‌ی مهم: یوتیوب سرورهای ابری (Render هم همین‌طور) رو اغلب به‌عنوانِ
ربات شناسایی و بلاک می‌کنه («Sign in to confirm you're not a bot»). گذاشتنِ
یک فایلِ cookies.txt (کوکی‌های یک اکانتِ واقعیِ یوتیوب - از افزونه‌ی مرورگرِ
"Get cookies.txt" می‌شه گرفت) کنارِ ربات معمولاً این مشکل رو حل می‌کنه، ولی
تضمینی نیست؛ یوتیوب می‌تونه IP رنجِ Render رو دوباره بلاک کنه. اگه این
اتفاق افتاد، فقط حالتِ «ریپلای روی فایل» کار می‌کنه - نه جستجو/لینک.
"""

import asyncio
import glob
import os

import yt_dlp

from config import YOUTUBE_COOKIES_PATH

DOWNLOAD_DIR = "downloads"


class YoutubeUnavailable(Exception):
    """پیامِ آماده برای نمایش به کاربر - جستجو/دانلود ممکن نشد."""


def _ydl_opts() -> dict:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        # این ترکیبِ player_client اغلب دورزدنِ بلاکِ IP سرورهای ابری رو
        # ممکن می‌کنه (بدونِ کوکی هم گاهی جواب می‌ده).
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if os.path.exists(YOUTUBE_COOKIES_PATH):
        opts["cookiefile"] = YOUTUBE_COOKIES_PATH
    return opts


def _extract_and_download(query: str) -> dict:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info and info["entries"]:
            info = info["entries"][0]

        path = ydl.prepare_filename(info)
        if not os.path.exists(path):
            # پسوندِ نهایی گاهی بعدِ پردازش فرق می‌کنه (مثلاً webm به‌جای m4a)
            candidates = glob.glob(os.path.splitext(path)[0] + ".*")
            path = candidates[0] if candidates else path

        return {
            "path": path,
            "title": info.get("title") or "آهنگ ناشناس",
            "performer": info.get("uploader") or "",
            "duration": int(info.get("duration") or 0),
            "webpage_url": info.get("webpage_url") or "",
        }


async def search_and_download(query: str) -> dict:
    """
    query: یک عبارتِ جستجو («شادمهر عقیلی یلدا») یا یک لینکِ مستقیمِ یوتیوب.
    خروجی: dict با کلیدهای path/title/performer/duration/webpage_url.
    در صورتِ شکست (بلاک شدنِ IP یا هر خطای دیگه)، YoutubeUnavailable با
    پیامِ آماده برای نشون دادن به کاربر raise می‌شه.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _extract_and_download, query)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Sign in to confirm" in msg or "not a bot" in msg.lower():
            raise YoutubeUnavailable(
                "❗️ یوتیوب دانلود از این سرور رو موقتاً مسدود کرده (شناساییِ ربات).\n"
                "فعلاً فقط حالتِ «ریپلای روی فایلِ صوتی» رو استفاده کن؛ اگه یک فایلِ "
                "کوکیِ معتبر (cookies.txt) کنارِ ربات هست، دوباره امتحان کن."
            )
        raise YoutubeUnavailable(f"❗️ خطا در دریافت از یوتیوب:\n<code>{msg[:200]}</code>")
    except Exception as e:
        raise YoutubeUnavailable(f"❗️ خطای غیرمنتظره در دانلود:\n<code>{str(e)[:200]}</code>")