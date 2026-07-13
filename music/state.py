"""
music/state.py
-----------------
حافظه‌ی موقتِ درون‌برنامه‌ای (In-Memory State) برای سیستم موزیک ویس‌چت -
صف، آهنگ در حال پخش، لوپ، ولوم، تاریخچه، و این‌که کدام یوزربات (استخر -
music/pool.py) مسئولِ کدام گروه است.

نکته: این حافظه با ری‌استارت شدنِ پروسه پاک می‌شود (پخش/صف در حال اجرا -
که طبیعی هم هست، چون خودِ ویس‌چت هم قطع می‌شه)، ولی assignment یوزربات به
گروه (chat -> userbot_index) در دیتابیس پایدار می‌ماند (music/pool.py) و
اینجا فقط به‌عنوان کش خونده می‌شود.
"""

import random

LOOP_NONE = "none"
LOOP_TRACK = "track"
LOOP_QUEUE = "queue"

_music_now: dict = {}
_music_queue: dict = {}
_music_history: dict = {}
_music_loop: dict = {}
_music_volume: dict = {}
_music_muted: dict = {}
_chat_assistant: dict = {}  # {chat_id: userbot_index} - کشِ سریع، منبعِ اصلی DB است

HISTORY_MAX = 20
VOLUME_DEFAULT = 100


# ── Now Playing ──────────────────────────────────────────────
def get_now(chat_id: int) -> dict:
    return _music_now.get(chat_id, {})


def set_now(chat_id: int, data: dict):
    _music_now[chat_id] = data


def clear_now(chat_id: int):
    _music_now.pop(chat_id, None)


# ── Queue ─────────────────────────────────────────────────────
def get_queue_len(chat_id: int) -> int:
    return len(_music_queue.get(chat_id, []))


def peek_queue(chat_id: int) -> list:
    return list(_music_queue.get(chat_id, []))


def push_to_queue(chat_id: int, track: dict) -> int:
    _music_queue.setdefault(chat_id, []).append(track)
    return len(_music_queue[chat_id])


def pop_from_queue(chat_id: int) -> dict:
    q = _music_queue.get(chat_id)
    return q.pop(0) if q else {}


def clear_queue(chat_id: int):
    _music_queue[chat_id] = []


def shuffle_queue(chat_id: int):
    q = _music_queue.get(chat_id)
    if q and len(q) > 1:
        random.shuffle(q)


# ── Loop ──────────────────────────────────────────────────────
def get_loop(chat_id: int) -> str:
    return _music_loop.get(chat_id, LOOP_NONE)


def cycle_loop(chat_id: int) -> str:
    current = get_loop(chat_id)
    nxt = {LOOP_NONE: LOOP_TRACK, LOOP_TRACK: LOOP_QUEUE, LOOP_QUEUE: LOOP_NONE}[current]
    _music_loop[chat_id] = nxt
    return nxt


# ── Volume ────────────────────────────────────────────────────
def get_volume(chat_id: int) -> int:
    return _music_volume.get(chat_id, VOLUME_DEFAULT)


def set_volume(chat_id: int, volume: int) -> int:
    v = max(1, min(200, volume))
    _music_volume[chat_id] = v
    return v


def adjust_volume(chat_id: int, delta: int) -> int:
    return set_volume(chat_id, get_volume(chat_id) + delta)


def is_muted(chat_id: int) -> bool:
    return _music_muted.get(chat_id, False)


def toggle_mute(chat_id: int) -> bool:
    muted = not is_muted(chat_id)
    _music_muted[chat_id] = muted
    return muted


def unmute(chat_id: int):
    _music_muted[chat_id] = False


# ── History ───────────────────────────────────────────────────
def push_to_history(chat_id: int, track: dict):
    h = _music_history.setdefault(chat_id, [])
    if h and h[0].get("file_unique_id") == track.get("file_unique_id"):
        return
    h.insert(0, track)
    if len(h) > HISTORY_MAX:
        h.pop()


def get_history(chat_id: int) -> list:
    return list(_music_history.get(chat_id, []))


# ── Chat -> Assistant cache (see music/pool.py for DB-backed source) ──
def get_cached_assistant_index(chat_id: int):
    return _chat_assistant.get(chat_id)


def set_cached_assistant_index(chat_id: int, index: int):
    _chat_assistant[chat_id] = index


# ── Hub panel: is the current panel message a media banner (caption) or
# plain text? (see music/panel_io.py + "ثبت تصویر music_hub_banner") ──
_panel_is_banner: dict = {}


def get_panel_is_banner(chat_id: int) -> bool:
    return _panel_is_banner.get(chat_id, False)


def set_panel_is_banner(chat_id: int, is_banner: bool):
    _panel_is_banner[chat_id] = is_banner