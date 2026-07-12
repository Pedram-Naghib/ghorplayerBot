"""
music/pool.py
----------------
مدیریتِ استخرِ یوزربات‌ها (assistant pool) برای پخشِ هم‌زمانِ موزیک در چند
گروه.

چرا چند یوزربات؟ یک اکانتِ تلگرامِ تنها هم از نظرِ فنی (تعدادِ گروه‌هایی که
عضوشونه) و هم از نظرِ ریسکِ فلود/بن شدن از سمتِ تلگرام محدودیت داره. این
ماژول اجازه می‌ده چند اکانت (هرکدام با سشنِ خودش - بساز با
tools/generate_userbot_session.py) هم‌زمان بالا بیان؛ هر گروه یک‌بار به
یکی از این‌ها «چسبانده» می‌شه (اولین باری که «پخش» توی اون گروه جواب بده)
و از اون به بعد همیشه همون یوزربات جواب‌گوی همون گروهه - هم برای رفتارِ
قابلِ‌پیش‌بینی، هم چون ری‌استارت شدنِ سرویس نباید یوزربات‌ها رو قاطی کنه.

اگه هیچ‌کدوم از یوزربات‌های استخر عضوِ گروهی نباشن، ربات باید صریحاً بهِ
ادمین بگه کدوم یوزرنیم‌ها رو باید اضافه کنه - نه این‌که سکوت کنه.
"""

import os
from urllib.parse import urlparse  # ماژول استاندارد برای شکستن آدرس پراکسی

from telethon import TelegramClient
from telethon.sessions import StringSession

from pytgcalls import PyTgCalls
from pytgcalls.types import StreamEnded

# حتماً PROXY_URL باید اینجا ایمپورت شود
from config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSIONS, PROXY_URL, SUPPORT_CONTACT


class Assistant:
    def __init__(self, index: int, client: TelegramClient, calls: PyTgCalls):
        self.index = index
        self.client = client
        self.calls = calls
        self.user_id = None
        self.username = None
        self.name = None
        self.ready = False


_assistants: list = []
_on_stream_ended_cb = None  # async def(chat_id) - تنظیم می‌شه توسط music/playback.py


def register_stream_ended_callback(cb):
    """playback.py موقعِ start شدن، تابعِ _play_next خودش رو اینجا ثبت می‌کنه."""
    global _on_stream_ended_cb
    _on_stream_ended_cb = cb


def all_assistants() -> list:
    return list(_assistants)


def get_assistant(index: int):
    for a in _assistants:
        if a.index == index:
            return a
    return None


def any_ready() -> bool:
    return any(a.ready for a in _assistants)


async def start_pool():
    """راه‌اندازیِ همه‌ی یوزربات‌های تعریف‌شده در USERBOT_SESSIONS."""
    sessions = [s.strip() for s in USERBOT_SESSIONS.split(",") if s.strip()]
    if not sessions:
        print("⚠️ USERBOT_SESSIONS خالیه - موتورِ موزیک غیرفعال ماند.")
        return
    if not USERBOT_API_ID or not USERBOT_API_HASH:
        print("⚠️ USERBOT_API_ID/USERBOT_API_HASH تنظیم نشده‌اند - موتورِ موزیک غیرفعال ماند.")
        return

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception as e:
        print(f"⚠️ static_ffmpeg setup skipped: {e}")

    # تبدیلِ داینامیکِ PROXY_URL محیطی به فرمتِ مدنظرِ Telethon
    proxy_settings = None
    if PROXY_URL:
        parsed = urlparse(PROXY_URL)
        # خروجی نهایی: مثلاً ("http", "127.0.0.1", 10809)
        proxy_settings = (parsed.scheme, parsed.hostname, parsed.port)

    for idx, session_str in enumerate(sessions):
        # اضافه کردنِ پراکسی به کلاینت در زمانِ ساخت
        client = TelegramClient(
            StringSession(session_str), 
            USERBOT_API_ID, 
            USERBOT_API_HASH,
            proxy=proxy_settings
        )
        calls = PyTgCalls(client)
        assistant = Assistant(idx, client, calls)

        def _handler_for(a: Assistant):
            async def _on_update(_, update):
                if isinstance(update, StreamEnded) and update.stream_type == StreamEnded.Type.AUDIO:
                    if _on_stream_ended_cb:
                        await _on_stream_ended_cb(update.chat_id)
            return _on_update

        calls.on_update()(_handler_for(assistant))
        _assistants.append(assistant)

        try:
            await client.start()
            await calls.start()
            me = await client.get_me()
            assistant.user_id = me.id
            assistant.username = me.username
            assistant.name = me.first_name or str(me.id)
            assistant.ready = True
            print(f"✅ یوزربات #{idx} آماده شد: {assistant.name} (@{assistant.username or '—'})")

            # کش کردنِ دیالوگ‌ها لازمه تا get_entity(chat_id) بعداً موفق باشه
            dialog_count = 0
            async for _ in client.iter_dialogs():
                dialog_count += 1
            print(f"📚 یوزربات #{idx}: {dialog_count} دیالوگ/چت کش شد.")
        except Exception as e:
            print(f"💥 راه‌اندازیِ یوزربات #{idx} ناموفق بود: {e}")

    if not any_ready():
        print("⚠️ هیچ یوزرباتی با موفقیت بالا نیامد - موتورِ موزیک عملاً غیرفعاله.")


def pool_status_text() -> str:
    if not _assistants:
        text = "هیچ یوزرباتی تنظیم نشده. USERBOT_SESSIONS رو در .env پر کن."
    else:
        lines = []
        for a in _assistants:
            state = "🟢 آماده" if a.ready else "🔴 خطا در راه‌اندازی"
            uname = f"@{a.username}" if a.username else "بدون‌یوزرنیم"
            lines.append(f"#{a.index} — {a.name or '؟'} ({uname}) — {state}")
        lines.append("\nهرکدوم از این یوزرنیم‌ها رو می‌تونی مستقیم به این گروه اضافه کنی.")
        text = "\n".join(lines)
    if SUPPORT_CONTACT:
        text += f"\n\n🆘 اگه خودت نتونستی اضافه‌شون کنی، به پشتیبانی پیام بده: {SUPPORT_CONTACT}"
    return text


async def find_membership(chat_id: int):
    """اولین یوزرباتِ آماده‌ای که واقعاً عضوِ این گروهه رو پیدا می‌کنه
    (فقط برای اولین assignment یک گروه استفاده می‌شه)."""
    for a in _assistants:
        if not a.ready:
            continue
        try:
            await a.client.get_entity(chat_id)
            return a
        except Exception:
            continue
    return None


async def get_or_assign(db, chat_id: int):
    """
    برمی‌گردونه: (Assistant یا None, پیامِ خطا یا None).

    منطق: اول assignment ذخیره‌شده در DB رو چک می‌کنه (که به‌خاطر ری‌استارت
    شدنِ سرویس هنوز معتبره)؛ اگه نبود، دنبالِ اولین یوزرباتِ عضوِ این گروه
    می‌گرده و اون رو برای همیشه به این گروه می‌چسبونه.
    """
    if not any_ready():
        return None, "⚠️ موتورِ موزیک راه‌اندازی نشده (هیچ یوزرباتی وصل نیست)."

    from music import state as _state

    cached_idx = _state.get_cached_assistant_index(chat_id)
    if cached_idx is not None:
        a = get_assistant(cached_idx)
        if a and a.ready:
            return a, None

    db_idx = await db.get_music_assignment(chat_id)
    if db_idx is not None:
        a = get_assistant(db_idx)
        if a and a.ready:
            _state.set_cached_assistant_index(chat_id, a.index)
            return a, None

    a = await find_membership(chat_id)
    if a is None:
        usernames = [f"@{x.username}" for x in _assistants if x.ready and x.username]
        who = "، ".join(usernames) if usernames else "یکی از یوزربات‌های تنظیم‌شده"
        support_line = f"\nیا به پشتیبانی پیام بده: {SUPPORT_CONTACT}" if SUPPORT_CONTACT else ""
        return None, (
            f"❗️ هیچ‌کدام از یوزربات‌ها هنوز عضو این گروه نیستند.\n"
            f"اول {who} را به گروه اضافه کن، بعد دوباره «پخش» رو امتحان کن.{support_line}"
        )

    await db.set_music_assignment(chat_id, a.index)
    _state.set_cached_assistant_index(chat_id, a.index)
    return a, None