"""
tools/generate_userbot_session.py
------------------------------------
اسکریپتِ مستقل برایِ ساختنِ سشنِ یک یوزربات (اکانتِ واقعیِ تلگرام، نه ربات)
که قراره به استخرِ موزیک اضافه بشه (music/pool.py) - این فایل هیچ ارتباطی
با پروسه‌یِ اصلیِ ربات نداره و هیچ‌وقت روی سرور دیپلوی نمی‌شه؛ فقط یک‌بار،
لوکال روی کامپیوترِ خودت، به‌ازایِ هر اکانتی که می‌خوای اضافه کنی اجرا می‌شه.

اجرا:
    pip install telethon
    python tools/generate_userbot_session.py

مراحل: API_ID/API_HASH (از my.telegram.org - یک‌بار کافیه، برایِ همه‌یِ
اکانت‌های خودت قابلِ استفاده‌ست) رو می‌پرسه، بعد شماره‌یِ همون اکانتی که
می‌خوای یوزربات بشه، بعد کدِ تاییدی که تلگرام برایِ همون اکانت می‌فرسته
(و رمزِ دو-مرحله‌ای اگه روشن بود). در پایان یک رشته‌یِ طولانی (StringSession)
چاپ می‌کنه - این رشته رو کپی کن و به لیستِ USERBOT_SESSIONS در .env اضافه
کن (با کاما جدا از بقیه‌یِ سشن‌ها اگه از قبل چیزی اونجا بود).

⚠️ این رشته معادلِ لاگین‌بودنِ کاملِ اون اکانته - مثلِ رمزِ عبور باهاش رفتار
کن، جایی paste نکن که بقیه ببینن، و توی گیت‌هاب کامیت نکن.
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

    if not api_id.isdigit() or not api_hash:
        print("❌ API_ID باید عدد باشه و API_HASH نباید خالی باشه.")
        return

    client = TelegramClient(StringSession(), int(api_id), api_hash)
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