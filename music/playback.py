"""
music/playback.py
--------------------
منطقِ اصلیِ پخش: شروع/توقف/ادامه/بعدی/پایان/شافل/لوپ/ولوم/میوت، به‌علاوه‌ی
مدیریتِ صف و خروجِ خودکار به‌خاطرِ بیکاری - با استفاده از استخرِ یوزربات‌ها
(music/pool.py) که تصمیم می‌گیره کدوم اکانت مسئولِ کدوم گروهه.

هر تابعِ عمومیِ اینجا (cmd_play, cmd_pause, ...) چتِ موردنظر رو می‌گیره، از
music/pool.py یوزربات/PyTgCalls متناظرش رو پیدا می‌کنه، و بعد دستور رو روی
همون اجرا می‌کنه.
"""

import asyncio
import os
import traceback

from pytgcalls.types import MediaStream
from pytgcalls.exceptions import NoActiveGroupCall

from music import pool, state
from music.state import LOOP_NONE, LOOP_TRACK, LOOP_QUEUE
from music.panel_io import edit_panel_message

_bot_instance = None
_db = None
_last_panel: dict = {}


def init(bot_instance, db):
    """صدا زده می‌شه از bot.py هنگامِ استارت - قبل از pool.start_pool()."""
    global _bot_instance, _db
    _bot_instance = bot_instance
    _db = db
    pool.register_stream_ended_callback(_play_next)


# ════════════════════════════════════════════════════════════
#  ارسالِ پنل/پیام به ربات
# ════════════════════════════════════════════════════════════
async def _emit_panel(chat_id: int):
    if not _bot_instance:
        return
    from handlers.music_commands import build_panel

    now = state.get_now(chat_id)
    if not now:
        text, kb = build_panel("idle", "", 0)
        panel_msg_id = _last_panel.get(chat_id)
        if panel_msg_id:
            try:
                await edit_panel_message(chat_id, panel_msg_id, text, kb)
            except Exception:
                pass
        return

    text, kb = build_panel(
        now.get("state", "idle"), now.get("title", ""), state.get_queue_len(chat_id),
        now.get("performer", ""), now.get("duration", 0), now.get("with_video", False),
        now.get("requester_id"), now.get("requester_name", ""),
        state.get_loop(chat_id), state.get_volume(chat_id), state.is_muted(chat_id),
    )
    try:
        await edit_panel_message(chat_id, now.get("panel_msg_id"), text, kb)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            print(f"⚠️ _emit_panel edit failed for {chat_id}: {type(e).__name__}: {e}")


async def _emit_toast(chat_id: int, text: str):
    if not _bot_instance:
        return
    try:
        await _bot_instance.send_message(chat_id, text)
    except Exception:
        pass


def repoint_panel(chat_id: int, new_panel_msg_id: int):
    _last_panel[chat_id] = new_panel_msg_id
    now = state.get_now(chat_id)
    if now:
        now["panel_msg_id"] = new_panel_msg_id
        state.set_now(chat_id, now)


async def refresh_panel(chat_id: int):
    await _emit_panel(chat_id)


# ════════════════════════════════════════════════════════════
#  دانلودِ فایل (فقط برای source == "file" وقتی دانلودِ سمتِ ربات جواب نداده)
# ════════════════════════════════════════════════════════════
async def _download_via_assistant(assistant, audio_chat_id: int, audio_msg_id: int) -> str:
    os.makedirs("downloads", exist_ok=True)
    client = assistant.client
    try:
        await client.get_entity(audio_chat_id)
    except Exception as e:
        raise ValueError(f"ENTITY_NOT_FOUND: {e}")

    msg = None
    last_err = None
    for delay in (0, 0.7, 1.5, 2.5):
        if delay:
            await asyncio.sleep(delay)
        try:
            msg = await client.get_messages(audio_chat_id, ids=audio_msg_id)
        except Exception as e:
            last_err = e
            continue
        if msg:
            break
    if not msg:
        raise ValueError(f"GET_MESSAGE_FAILED: {last_err}")

    path = await client.download_media(
        msg, file=os.path.join("downloads", f"{audio_chat_id}_{audio_msg_id}")
    )
    if not path:
        raise ValueError("DOWNLOAD_EMPTY")
    return path


def _cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
#  شروعِ استریم
# ════════════════════════════════════════════════════════════
async def _start_stream(chat_id: int, assistant, track: dict) -> str:
    path = track.get("audio_path")
    if not (path and os.path.exists(path)):
        if track.get("source") == "file":
            path = await _download_via_assistant(assistant, track["audio_chat_id"], track["audio_msg_id"])
        else:
            raise ValueError("MISSING_LOCAL_FILE")

    # قبل از پیوستن به تماس، مطمئن می‌شیم کشِ entity هایِ Telethon برای این چت
    # تازه‌ست - رایج‌ترین دلیلِ ارورِ "Could not find the input entity for
    # PeerChannel" همینه (مثلاً درست بعدِ اضافه‌شدنِ یوزربات به گروه، یا بعدِ
    # ری‌استارتِ سرویس، که کش هنوز خالیه). این یک تلاشِ best-effortِ اضافیه،
    # نه یک ضمانتِ صددرصدی - اگه بازم نشد، پایین با یک پیامِ روشن مدیریت می‌شه.
    try:
        await assistant.client.get_entity(chat_id)
    except Exception:
        pass

    video_flags = MediaStream.Flags.AUTO_DETECT if track.get("with_video") else MediaStream.Flags.IGNORE
    try:
        await assistant.calls.play(chat_id, MediaStream(path, video_flags=video_flags))
        if not state.is_muted(chat_id):
            await asyncio.sleep(1)
            await assistant.calls.change_volume_call(chat_id, state.get_volume(chat_id))
    except Exception:
        _cleanup_file(path)
        raise
    return path


# ════════════════════════════════════════════════════════════
#  cmd_play
# ════════════════════════════════════════════════════════════
async def cmd_play(chat_id: int, track: dict, panel_msg_id: int, initiator_id: int,
                    assistant=None, assign_err: str = None):
    """
    track باید شاملِ این کلیدها باشه:
      source: "file" | "youtube"
      title, performer, duration, with_video, file_unique_id
      requester_id, requester_name
      audio_path (اختیاری - اگه از قبل دانلود شده)
      audio_chat_id/audio_msg_id (فقط برای source == "file"، برای fallback دانلود)
      webpage_url (فقط برای source == "youtube")

    assistant/assign_err: اگه از قبل با pool.get_or_assign() محاسبه شده
    (مثلاً هم‌زمان با دانلودِ فایل، تویِ handlers/music_commands.py - برایِ
    این‌که این دو تا کارِ کندِ شبکه‌ای به‌صورتِ موازی انجام بشن نه پشتِ سرِ
    هم)، همون رو مستقیم پاس بده تا اینجا دوباره صدا زده نشه. اگه هیچ‌کدوم
    داده نشه (پیش‌فرض)، خودش pool.get_or_assign رو صدا می‌زنه - رفتارِ قبلی.
    """
    if assistant is None and assign_err is None:
        assistant, assign_err = await pool.get_or_assign(_db, chat_id)
    if assign_err:
        _cleanup_file(track.get("audio_path"))
        await edit_panel_message(chat_id, panel_msg_id, assign_err, kb=pool.support_keyboard())
        return

    now = state.get_now(chat_id)
    if now and now.get("state") in ("playing", "paused"):
        stale = False
        try:
            active = await assistant.calls.calls
            stale = chat_id not in active
        except Exception:
            stale = False
        if stale:
            _cleanup_file(now.get("path"))
            state.clear_now(chat_id)
            now = None

    if now and now.get("state") in ("playing", "paused"):
        pos = state.push_to_queue(chat_id, track)
        try:
            from handlers.music_commands import build_queue_added
            await edit_panel_message(
                chat_id, panel_msg_id,
                build_queue_added(track.get("title", ""), track.get("performer", ""),
                                   track.get("duration", 0), pos),
            )
        except Exception:
            await _emit_toast(chat_id, f"🎵 «{track.get('title')}» به صف اضافه شد (موقعیت {pos}).")
        await _emit_panel(chat_id)
        return

    old_panel = _last_panel.get(chat_id)
    if old_panel and old_panel != panel_msg_id:
        try:
            await _bot_instance.delete_message(chat_id, old_panel)
        except Exception:
            pass
    _last_panel[chat_id] = panel_msg_id

    try:
        path = await _start_stream(chat_id, assistant, track)
    except NoActiveGroupCall:
        await _emit_toast(chat_id, "❗️ اول یک ویس‌چت در گروه باز کن، بعد دوباره «پخش» بزن.")
        return
    except ValueError as e:
        reason = str(e)
        if "ENTITY_NOT_FOUND" in reason:
            msg = "❗️ یوزربات این گروه/چت را نمی‌شناسد. مطمئن شو عضوش هست."
        elif "GET_MESSAGE" in reason:
            msg = "❗️ فایل صوتی پیدا نشد. دوباره روی یک فایل تازه ریپلای کن."
        elif "input entity" in reason.lower() or "peerchannel" in reason.lower():
            msg = (
                "❗️ یوزربات هنوز اطلاعات این گروه رو کامل نگرفته (کش داخلی خالیه)، یا این که اصلا یوزربات داخل گروه اد نشده!\n"
                "برای حل مشکل:\n"
                "۱. اول مطمئن شو که یوزربات عضو گروه هست.\n"
                "۲. اگر عضو بود، یک پیام ساده تو گروه بفرست تا یوزربات گروه رو بشناسه.\n"
                "۳. بعد دوباره «پخش» رو امتحان کن."
            )
        else:
            msg = f"❗️ خطا:\n<code>{reason[:200]}</code>"
        await _emit_toast(chat_id, msg)
        return
    except Exception as e:
        reason = str(e)
        if "input entity" in reason.lower() or "peerchannel" in reason.lower():
            msg = (
                "❗️ یوزربات هنوز اطلاعات این گروه رو کامل نگرفته (کش داخلی خالیه)، یا این که اصلا یوزربات داخل گروه اد نشده!\n"
                "برای حل مشکل:\n"
                "۱. اول مطمئن شو که یوزربات عضو گروه هست.\n"
                "۲. اگر عضو بود، یک پیام ساده تو گروه بفرست تا یوزربات گروه رو بشناسه.\n"
                "۳. بعد دوباره «پخش» رو امتحان کن."
            )
            await _emit_toast(chat_id, msg)
        else:
            traceback.print_exc()
            await _emit_toast(chat_id, f"❗️ اتصال به ویس‌چت ناموفق بود.\n<code>{type(e).__name__}: {reason[:200]}</code>")
        return

    state.set_now(chat_id, {
        **track, "state": "playing", "panel_msg_id": panel_msg_id,
        "initiator_id": initiator_id, "path": path, "assistant_index": assistant.index,
    })
    await _emit_panel(chat_id)


async def _play_next(chat_id: int):
    prev = state.get_now(chat_id)
    if prev:
        state.push_to_history(chat_id, prev)

    loop_mode = state.get_loop(chat_id)
    assistant = pool.get_assistant(state.get_cached_assistant_index(chat_id))

    if loop_mode == LOOP_TRACK and prev and assistant:
        track_for_loop = {**prev, "audio_path": None}
        try:
            _cleanup_file(prev.get("path"))
            path = await _start_stream(chat_id, assistant, track_for_loop)
        except Exception as e:
            print(f"💥 loop-track error in {chat_id}: {e}")
            await _play_next_from_queue(chat_id, prev)
            return
        state.set_now(chat_id, {
            **track_for_loop, "state": "playing", "panel_msg_id": prev.get("panel_msg_id"),
            "initiator_id": prev.get("initiator_id"), "path": path, "assistant_index": assistant.index,
        })
        await _emit_panel(chat_id)
        return

    if loop_mode == LOOP_QUEUE and prev:
        state.push_to_queue(chat_id, {k: v for k, v in prev.items()
                                       if k not in ("state", "panel_msg_id", "initiator_id", "path", "assistant_index")})

    _cleanup_file(prev.get("path") if prev else None)
    await _play_next_from_queue(chat_id, prev)


async def _play_next_from_queue(chat_id: int, prev: dict, _attempt: int = 0):
    panel_msg_id = (prev.get("panel_msg_id") if prev else None) or _last_panel.get(chat_id)
    initiator_id = prev.get("initiator_id") if prev else None
    assistant = pool.get_assistant(state.get_cached_assistant_index(chat_id))

    MAX_CONSECUTIVE_FAILURES = 5
    if _attempt >= MAX_CONSECUTIVE_FAILURES:
        await _leave(
            chat_id,
            f"❗️ {MAX_CONSECUTIVE_FAILURES} آهنگِ پیاپی تو صف پخش نشدن - از ویس‌چت خارج شدم. "
            f"بقیه‌یِ صف رو دوباره امتحان کن.",
        )
        return

    track = state.pop_from_queue(chat_id)
    if track and assistant:
        try:
            path = await _start_stream(chat_id, assistant, track)
        except Exception as e:
            print(f"💥 next-play error in {chat_id} (attempt {_attempt + 1}): {e}")
            await _play_next_from_queue(chat_id, prev, _attempt=_attempt + 1)
            return
        state.set_now(chat_id, {
            **track, "state": "playing", "panel_msg_id": panel_msg_id,
            "initiator_id": initiator_id, "path": path, "assistant_index": assistant.index,
        })
        await _emit_panel(chat_id)
    else:
        # صف خالیه - بلافاصله از ویس‌چت خارج می‌شیم (نه بعد از یک تایم‌اوتِ
        # بیکاری) چون دیگه هیچ آهنگی برای پخش نمونده.
        await _leave(chat_id, "✅ پخش تمام شد و از ویس‌چت خارج شدم.")


# ════════════════════════════════════════════════════════════
#  دستورهای کنترل
# ════════════════════════════════════════════════════════════
def _current_assistant(chat_id: int):
    return pool.get_assistant(state.get_cached_assistant_index(chat_id))


async def cmd_pause(chat_id: int):
    a = _current_assistant(chat_id)
    if a:
        try:
            await a.calls.pause(chat_id)
        except Exception:
            pass
    now = state.get_now(chat_id)
    if now:
        now["state"] = "paused"
        state.set_now(chat_id, now)
    await _emit_panel(chat_id)


async def cmd_resume(chat_id: int):
    a = _current_assistant(chat_id)
    if a:
        try:
            await a.calls.resume(chat_id)
        except Exception:
            pass
    now = state.get_now(chat_id)
    if now:
        now["state"] = "playing"
        state.set_now(chat_id, now)
    await _emit_panel(chat_id)


async def cmd_skip(chat_id: int):
    if state.get_queue_len(chat_id) > 0 or state.get_loop(chat_id) != LOOP_NONE:
        await _play_next(chat_id)
    else:
        await _leave(chat_id, "⏭ آهنگ بعدی‌ای در صف نبود؛ از ویس‌چت خارج شدم.")


async def cmd_stop(chat_id: int):
    state.clear_queue(chat_id)
    await _leave(chat_id, "⛔️ پخش پایان یافت و از ویس‌چت خارج شدم.")


async def cmd_shuffle(chat_id: int):
    state.shuffle_queue(chat_id)
    await _emit_panel(chat_id)


async def cmd_loop(chat_id: int) -> str:
    new_mode = state.cycle_loop(chat_id)
    await _emit_panel(chat_id)
    return new_mode


async def cmd_volume(chat_id: int, delta: int) -> int:
    old_vol = state.get_volume(chat_id)
    new_vol = state.adjust_volume(chat_id, delta)
    if old_vol == new_vol:
        return new_vol
    a = _current_assistant(chat_id)
    if a:
        try:
            state.unmute(chat_id)
            await a.calls.change_volume_call(chat_id, new_vol)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"⚠️ cmd_volume failed: {type(e).__name__}: {e}")
    await _emit_panel(chat_id)
    return new_vol


async def cmd_mute(chat_id: int) -> bool:
    muted = state.toggle_mute(chat_id)
    a = _current_assistant(chat_id)
    if a:
        try:
            if muted:
                await a.calls.pause(chat_id)
            else:
                await a.calls.resume(chat_id)
                await asyncio.sleep(0.5)
                await a.calls.change_volume_call(chat_id, state.get_volume(chat_id))
        except Exception as e:
            print(f"⚠️ cmd_mute failed: {type(e).__name__}: {e}")
    await _emit_panel(chat_id)
    return muted


async def _leave(chat_id: int, toast: str = ""):
    now = state.get_now(chat_id)
    if now:
        state.push_to_history(chat_id, now)
        _cleanup_file(now.get("path"))
        panel_msg_id = now.get("panel_msg_id")
        if panel_msg_id:
            _last_panel[chat_id] = panel_msg_id

    a = _current_assistant(chat_id)
    if a:
        try:
            await a.calls.leave_call(chat_id)
        except Exception:
            pass

    state.clear_now(chat_id)
    await _emit_panel(chat_id)
    if toast:
        await _emit_toast(chat_id, toast)