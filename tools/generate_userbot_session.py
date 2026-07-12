"""
tools/generate_userbot_session.py
------------------------------------
اسکریپتِ مستقل برایِ ساختنِ سشنِ یک یوزربات (اکانتِ واقعیِ تلگرام، نه ربات)
که قراره به استخرِ موزیک اضافه بشه (music/pool.py) - این فایل هیچ ارتباطی
با پروسه‌یِ اصلیِ ربات نداره و هیچ‌وقت روی سرور دیپلوی نمی‌شه؛ فقط یک‌بار،
لوکال روی کامپیوترِ خودت، به‌ازایِ هر اکانتی که می‌خوای اضافه کنی اجرا می‌شه.

اجرا:
    pip install telethon python-socks[asyncio]
    python tools/generate_userbot_session.py
"""

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    print("=" * 60)
    print("ساختِ سشنِ یوزربات برایِ استخرِ موزیک")
    print("=" * 60)

    api_id = input("API_ID (از my.telegram.org): ").strip()
    api_hash = input("API_HASH (از my.telegram.org): ").strip()
    use_proxy = input("استفاده از پراکسی لوکال (پورت 10808)؟ (y/n) [پیش‌فرض y]: ").strip().lower() != 'n'

    if not api_id.isdigit() or not api_hash:
        print("❌ API_ID باید عدد باشه و API_HASH نباید خالی باشه.")
        return

    # تنظیم داینامیک پراکسی برای جلوگیری از هاردکد شدن مقادیر لوکال
    proxy_settings = ("socks5", '127.0.0.1', 10808) if use_proxy else None

    client = TelegramClient(
        StringSession(), 
        int(api_id), 
        api_hash,
        proxy=proxy_settings
    )
    
    await client.start()  # شماره/کد/رمزِ دو-مرحله‌ای رو خودِ Telethon تعاملی می‌پرسه

    me = await client.get_me()
    session_str = client.session.save()

    print("\n" + "=" * 60)
    print(f"✅ لاگین موفق بود: {me.first_name} (@{me.username or '—'}, id={me.id})")
    print("=" * 60)
    print("\nاین رشته رو کپی کن و به USERBOT_SESSIONS در .env اضافه کن")
    print("(اگه از قبل سشنِ دیگه‌ای اونجا هست، با کاما جداش کن):\n")
    print(session_str)
    print()

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())