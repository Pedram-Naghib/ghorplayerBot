"""
handlers/music_commands.py
-----------------------------
دستورهای متنیِ فارسیِ پخشِ موزیک در ویس‌چت + هابِ شیشه‌ای برایِ کنترل.

مجوز: دقیقاً همون مدلِ نقش‌هایِ بقیه‌یِ دستورهایِ مدیریتیِ ربات - owner،
owner2, admin (و ادمین‌کل/مالکِ ربات به‌صورتِ خودکار) - بدونِ عضوِ ویژه
(vip). این چک از utils/permissions.py:is_authorized_admin میاد، همونی که
handlers/admin_commands.py هم استفاده می‌کنه، پس این‌جا هیچ سیستمِ
مجوزِ جدا و موازی‌ای ساخته نشده.

دو راهِ معرفیِ آهنگ:
  «پخش»            (رویِ یک فایلِ صوتی/ویدیویی ریپلای‌شده)
  «پخش آهنگ <متن>»  (جستجو یا لینکِ یوتیوب - نگاه کن به music/youtube.py)

نکته‌یِ مهم دربارهِ ترتیبِ ثبتِ هندلرها: هر func اینجا فقط رویِ پیام‌هایی که
واقعاً یک دستورِ موزیک هستند True برمی‌گردونه (نه رویِ هر متنِ گروهی) - چون
pyTelegramBotAPI رویِ اولین هندلرِ منطبق متوقف می‌شه (نگاه کن به bot.py)،
یک func خیلی گسترده باعث می‌شد بقیه‌یِ پیام‌های عادیِ گروه هیچ‌وقت به
آنتی‌اسپم/ترکینگ نرسند.
"""

import asyncio
import html
import os

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from core import bot, db
from utils.permissions import is_authorized_admin
from utils.text import normalize_trigger, matches_command, bidi_isolate
from music import state, pool, playback
from music.panel_io import send_panel_message, edit_panel_message
from music.youtube import search_and_download, YoutubeUnavailable

_LOOP_LABELS = {
    state.LOOP_NONE: "🔁 لوپ: خاموش",
    state.LOOP_TRACK: "🔂 لوپ: یک آهنگ",
    state.LOOP_QUEUE: "🔁 لوپ: همه صف",
}

BOT_DL_LIMIT = 20 * 1024 * 1024

_CONTROL_ACTIONS = {
    "بعدی": "skip",
    "پایان": "stop",
    "اتمام": "stop",
    "مکث": "pause",
    "ادامه پخش": "resume",
    "شافل": "shuffle",
}


# ════════════════════════════════════════════════════════════
#  کمک‌توابع
# ════════════════════════════════════════════════════════════
def _fmt_duration(seconds: int) -> str:
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _info_line(performer: str, duration: int) -> str:
    parts = []
    if performer:
        parts.append(f"🎤 {html.escape(performer)}")
    dur = _fmt_duration(duration)
    if dur:
        parts.append(f"⏱ {dur}")
    return ("\n" + "   ".join(parts)) if parts else ""


def _requester_line(requester_id: int, requester_name: str) -> str:
    if not requester_id:
        return ""
    name = bidi_isolate(html.escape(requester_name or "کاربر"))
    return f'\n🎧 درخواست: <a href="tg://user?id={requester_id}">{name}</a>'


def _build_kb(state_now: str, loop_label: str, muted: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    if state_now == "playing":
        kb.row(
            InlineKeyboardButton("⏸️ توقف", callback_data="music_pause"),
            InlineKeyboardButton("⏭️ بعدی", callback_data="music_skip"),
        )
    else:
        kb.row(
            InlineKeyboardButton("▶️ ادامه", callback_data="music_resume"),
            InlineKeyboardButton("⏭️ بعدی", callback_data="music_skip"),
        )
    kb.row(InlineKeyboardButton("⏹️ پایان", callback_data="music_stop"))
    kb.row(
        InlineKeyboardButton("🔀 شافل", callback_data="music_shuffle"),
        InlineKeyboardButton("🔇 قطع صدا" if not muted else "🔊 وصل کردن صدا", callback_data="music_mute"),
        InlineKeyboardButton(loop_label, callback_data="music_loop"),
    )
    kb.row(InlineKeyboardButton("📋 صف پخش", callback_data="music_queue"))
    kb.row(InlineKeyboardButton("❌ بستن هاب", callback_data="music_close"))
    return kb


def build_panel(state_now: str, title: str, queue_len: int, performer: str = "",
                duration: int = 0, with_video: bool = False, requester_id: int = None,
                requester_name: str = "", loop_mode: str = state.LOOP_NONE,
                volume: int = 100, muted: bool = False):
    safe_title = html.escape(title or "نامشخص")
    info = _info_line(performer, duration)
    req_line = _requester_line(requester_id, requester_name)
    queue_line = f"\n\n📋 در صف: <b>{queue_len}</b> آهنگ" if queue_len > 0 else ""
    icon = "🎬" if with_video else "🎧"
    vol_line = "\n🔈 بی‌صدا" if muted else f"\n🔊 صدا: {volume}%"
    loop_label = _LOOP_LABELS.get(loop_mode, _LOOP_LABELS[state.LOOP_NONE])

    if state_now == "playing":
        text = f"🎵 <b>در حال پخش</b>\n{icon} {safe_title}{info}{req_line}{vol_line}{queue_line}"
        return text, _build_kb("playing", loop_label, muted)
    if state_now == "paused":
        text = f"⏸ <b>متوقف شده</b>\n{icon} {safe_title}{info}{req_line}{vol_line}{queue_line}"
        return text, _build_kb("paused", loop_label, muted)

    text = "✅ <b>پخش به پایان رسید.</b>\nاگر تا چند دقیقه آهنگی پخش نشود، از ویس‌چت خارج می‌شوم."
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🚪 خروج از ویس‌چت", callback_data="music_kick"))
    return text, kb


def build_queue_added(title: str, performer: str, duration: int, position: int) -> str:
    safe_title = html.escape(title or "نامشخص")
    info = _info_line(performer, duration)
    return f"➕ <b>به صف اضافه شد</b>\n🎧 {safe_title}{info}\n\n📋 موقعیت در صف: <b>{position}</b>"


def _extract_media(replied):
    """از پیامِ ریپلای‌شده، فیلدهای لازم برایِ track رو استخراج می‌کنه، یا None
    اگه هیچ رسانه‌یِ قابلِ پخشی توش نبود."""
    if replied.audio:
        return dict(title=replied.audio.title or replied.audio.file_name or "آهنگ ناشناس",
                    performer=replied.audio.performer or "", duration=replied.audio.duration or 0,
                    file_id=replied.audio.file_id, file_size=replied.audio.file_size or 0,
                    file_unique_id=replied.audio.file_unique_id or "", with_video=False)
    if replied.voice:
        return dict(title="پیام صوتی", performer="", duration=replied.voice.duration or 0,
                    file_id=replied.voice.file_id, file_size=replied.voice.file_size or 0,
                    file_unique_id=replied.voice.file_unique_id or "", with_video=False)
    if replied.video:
        return dict(title=replied.video.file_name or "ویدیو", performer="", duration=replied.video.duration or 0,
                    file_id=replied.video.file_id, file_size=replied.video.file_size or 0,
                    file_unique_id=replied.video.file_unique_id or "", with_video=True)
    if replied.video_note:
        return dict(title="پیام ویدیویی", performer="", duration=replied.video_note.duration or 0,
                    file_id=replied.video_note.file_id, file_size=replied.video_note.file_size or 0,
                    file_unique_id=replied.video_note.file_unique_id or "", with_video=True)
    if replied.document and (replied.document.mime_type or "").startswith("audio"):
        return dict(title=replied.document.file_name or "فایل صوتی", performer="", duration=0,
                    file_id=replied.document.file_id, file_size=replied.document.file_size or 0,
                    file_unique_id=replied.document.file_unique_id or "", with_video=False)
    if replied.document and (replied.document.mime_type or "").startswith("video"):
        return dict(title=replied.document.file_name or "ویدیو", performer="", duration=0,
                    file_id=replied.document.file_id, file_size=replied.document.file_size or 0,
                    file_unique_id=replied.document.file_unique_id or "", with_video=True)
    return None


def _is_group_text(m) -> bool:
    return m.chat.type in ("group", "supergroup") and m.text is not None


def _matched_control_action(m):
    if not _is_group_text(m):
        return None
    text = normalize_trigger(m.text)
    for trig, action in _CONTROL_ACTIONS.items():
        if matches_command(text, {trig}):
            return action
    return None


# ── «پخش» - ریپلای رویِ فایل ─────────────────────────────
@bot.message_handler(
    func=lambda m: _is_group_text(m) and m.reply_to_message is not None
    and matches_command(normalize_trigger(m.text), {"پخش"}),
)
async def handle_play_reply(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_authorized_admin(db, chat_id, user_id):
        await bot.reply_to(message, "⛔️ فقط مدیرانِ گروه اجازه‌یِ پخشِ موزیک دارند.")
        return

    media = _extract_media(message.reply_to_message)
    if media is None:
        await bot.reply_to(message, "❗️ لطفاً رویِ یک فایلِ صوتی یا ویدیویی ریپلای کن.")
        return

    kind = "ویدیو" if media["with_video"] else "موزیک"
    panel = await send_panel_message(
        chat_id, f"⏳ در حال اتصال به ویس‌چت برایِ پخشِ {kind} «{html.escape(media['title'])}»...",
        reply_to_message_id=message.message_id,
    )

    # دانلودِ فایل و پیدا/چسبوندنِ یوزربات هر دو کارِ کندِ شبکه‌ای‌ان و کاملاً
    # مستقل از هم - قبلاً پشتِ سرِ هم (اول دانلود، بعد پیدا کردنِ یوزربات)
    # اجرا می‌شدن که یعنی زمانشون جمع می‌شد؛ الان هم‌زمان اجرا می‌شن تا
    # زمانِ کلی به‌جایِ جمع، تقریباً برابرِ کندترینشون بشه.
    async def _download():
        if media["file_size"] == 0 or media["file_size"] <= BOT_DL_LIMIT:
            try:
                os.makedirs("downloads", exist_ok=True)
                finfo = await bot.get_file(media["file_id"])
                data = await bot.download_file(finfo.file_path)
                ext = os.path.splitext(finfo.file_path or "")[1] or ".audio"
                path = os.path.join("downloads", f"{chat_id}_{message.reply_to_message.message_id}{ext}")
                with open(path, "wb") as f:
                    f.write(data)
                return path
            except Exception as e:
                print(f"⚠️ bot-side download failed ({e}); یوزربات fallback می‌کنه.")
        return None

    download_task = asyncio.create_task(_download())
    assign_task = asyncio.create_task(pool.get_or_assign(db, chat_id))
    local_path = await download_task
    assistant, assign_err = await assign_task

    track = {
        "source": "file", "audio_chat_id": chat_id, "audio_msg_id": message.reply_to_message.message_id,
        "audio_path": local_path, "title": media["title"], "performer": media["performer"],
        "duration": media["duration"], "with_video": media["with_video"],
        "file_unique_id": media["file_unique_id"], "requester_id": user_id,
        "requester_name": message.from_user.first_name or "",
    }
    asyncio.create_task(playback.cmd_play(chat_id, track, panel.message_id, user_id,
                                           assistant=assistant, assign_err=assign_err))

# ── «پخش آهنگ <عبارت/لینک>» - جستجویِ یوتیوب ───────────────
@bot.message_handler(
    func=lambda m: _is_group_text(m) and normalize_trigger(m.text).startswith("پخش آهنگ "),
)
async def handle_play_youtube(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_authorized_admin(db, chat_id, user_id):
        await bot.reply_to(message, "⛔️ فقط مدیرانِ گروه اجازه‌یِ پخشِ موزیک دارند.")
        return

    query = normalize_trigger(message.text)[len("پخش آهنگ "):].strip()
    if not query:
        await bot.reply_to(message, "❗️ بعدِ «پخش آهنگ» اسمِ آهنگ یا لینکِ یوتیوب رو بنویس.")
        return

    panel = await send_panel_message(chat_id, f"🔎 در حال جستجویِ «{html.escape(query)}»...", reply_to_message_id=message.message_id)

    assign_task = asyncio.create_task(pool.get_or_assign(db, chat_id))
    try:
        result = await search_and_download(query)
    except YoutubeUnavailable as e:
        assign_task.cancel()
        await edit_panel_message(chat_id, panel.message_id, str(e))
        return
    assistant, assign_err = await assign_task

    track = {
        "source": "youtube", "audio_path": result["path"], "title": result["title"],
        "performer": result["performer"], "duration": result["duration"], "with_video": False,
        "file_unique_id": result.get("webpage_url", ""), "requester_id": user_id,
        "requester_name": message.from_user.first_name or "",
    }
    asyncio.create_task(playback.cmd_play(chat_id, track, panel.message_id, user_id,
                                           assistant=assistant, assign_err=assign_err))

# ── دستورهایِ کنترلِ سریع (بدونِ نیاز به هاب) ────────────────
@bot.message_handler(func=lambda m: _matched_control_action(m) is not None)
async def handle_control(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    action = _matched_control_action(message)

    if action != "stop" and not state.get_now(chat_id):
        await bot.reply_to(message, "🔇 الان چیزی در حال پخش نیست.")
        return
    if not await is_authorized_admin(db, chat_id, user_id):
        await bot.reply_to(message, "⛔️ فقط مدیرانِ گروه اجازه‌یِ این کار رو دارند.")
        return

    if action == "skip":
        asyncio.create_task(playback.cmd_skip(chat_id))
        await bot.reply_to(message, "⏭ رفتم سراغِ آهنگِ بعدی.")
    elif action == "stop":
        asyncio.create_task(playback.cmd_stop(chat_id))
        await bot.reply_to(message, "⛔️ پخش متوقف شد.")
    elif action == "pause":
        asyncio.create_task(playback.cmd_pause(chat_id))
        await bot.reply_to(message, "⏸ پخش موقتاً متوقف شد.")
    elif action == "resume":
        asyncio.create_task(playback.cmd_resume(chat_id))
        await bot.reply_to(message, "▶️ پخش ادامه یافت.")
    elif action == "shuffle":
        asyncio.create_task(playback.cmd_shuffle(chat_id))
        await bot.reply_to(message, "🔀 صف قاطی شد.")

# ── «هاب» - نمایشِ پنلِ شیشه‌ای ────────────────────────────
@bot.message_handler(
    func=lambda m: _is_group_text(m) and matches_command(normalize_trigger(m.text), {"هاب"}),
)
async def handle_hub(message):
    chat_id = message.chat.id
    now = state.get_now(chat_id)
    if not now:
        await bot.reply_to(message, "🔇 الان چیزی در حال پخش نیست تا هابی نشان دهم.")
        return
    text_out, kb = build_panel(
        now.get("state", "idle"), now.get("title", ""), state.get_queue_len(chat_id),
        now.get("performer", ""), now.get("duration", 0), now.get("with_video", False),
        now.get("requester_id"), now.get("requester_name", ""),
        state.get_loop(chat_id), state.get_volume(chat_id), state.is_muted(chat_id),
    )
    sent = await send_panel_message(chat_id, text_out, kb=kb, reply_to_message_id=message.message_id)
    playback.repoint_panel(chat_id, sent.message_id)

# ── «یوزربات ها» - وضعیتِ استخر (اطلاعاتیه، برای همه قابل دیدنه؛ نیازی به
# نقشِ خاصی نداره چون کلِ هدفش کمک به هرکسیه که بخواد یوزربات رو اضافه کنه؛
# در گروه و در پیوی هردو کار می‌کنه) ─────────────────────────────
@bot.message_handler(
    func=lambda m: matches_command(
        normalize_trigger(m.text), {"یوزربات ها", "یوزربات‌ها", "یوزرباتها"}
    ),
)
async def handle_pool_status(message):
    await bot.reply_to(
        message,
        f"🎛 وضعیتِ استخرِ یوزربات‌ها:\n\n{pool.pool_status_text()}",
        reply_markup=pool.support_keyboard(),
    )

# ════════════════════════════════════════════════════════
#  دکمه‌هایِ هاب
# ════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("music_"))
async def handle_music_buttons(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data[len("music_"):]

    if data == "queue":
        tracks = state.peek_queue(chat_id)
        if not tracks:
            await bot.answer_callback_query(call.id, "📋 صف خالیه.", show_alert=True)
            return

        # نسخه‌ی فشرده و بدونِ HTML (چون popup فرمت‌بندی رو نشون نمی‌ده) -
        # همون حالتِ قبلی، فقط اگه جا بشه.
        compact_lines = []
        for i, t in enumerate(tracks, start=1):
            title = (t.get("title") or "نامشخص")[:30]
            dur = _fmt_duration(t.get("duration", 0))
            compact_lines.append(f"{i}. {title}" + (f" ({dur})" if dur else ""))
        compact_txt = f"📋 صفِ پخش ({len(tracks)} آهنگ):\n" + "\n".join(compact_lines)

        if len(compact_txt) <= 200:
            await bot.answer_callback_query(call.id, compact_txt, show_alert=True)
            return

        # فقط وقتی صف اونقدر بلنده که تو یک alert جا نمی‌شه، یک پیامِ جدا
        # می‌فرستیم (با جزئیاتِ کامل‌تر - خواننده و مدت‌زمان هم داره).
        lines = []
        for i, t in enumerate(tracks, start=1):
            t_title = html.escape(t.get("title") or "نامشخص")
            performer = t.get("performer") or ""
            dur = _fmt_duration(t.get("duration", 0))
            extra = "   ".join(filter(None, [f"🎤 {html.escape(performer)}" if performer else "", f"⏱ {dur}" if dur else ""]))
            lines.append(f"{i}. {t_title}" + (f"\n   {extra}" if extra else ""))
        txt = f"📋 <b>صفِ پخش</b> ({len(tracks)} آهنگ)\n\n" + "\n".join(lines)
        await bot.answer_callback_query(call.id)
        await bot.send_message(chat_id, txt, reply_to_message_id=call.message.message_id)
        return

    if data == "kick":
        if not await is_authorized_admin(db, chat_id, user_id):
            await bot.answer_callback_query(call.id, "⛔️ فقط مدیرانِ گروه!", show_alert=True)
            return
        asyncio.create_task(playback.cmd_stop(chat_id))
        try:
            await bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        await bot.answer_callback_query(call.id, "🚪 یوزربات از ویس‌چت خارج شد.")
        return

    if data == "close":
        if not await is_authorized_admin(db, chat_id, user_id):
            await bot.answer_callback_query(call.id, "⛔️ فقط مدیرانِ گروه!", show_alert=True)
            return
        try:
            await bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            await bot.answer_callback_query(call.id, "⚠️ حذف ممکن نشد.", show_alert=True)
        return

    # ── بقیه‌یِ دکمه‌ها همه نیازمندِ مجوزن ─────────────
    if not await is_authorized_admin(db, chat_id, user_id):
        await bot.answer_callback_query(call.id, "⛔️ این هاب فقط برایِ مدیرانِ گروهه.", show_alert=True)
        return

    labels = {"pause": "⏸ توقف شد", "resume": "▶️ ادامه یافت", "skip": "⏭ آهنگ بعدی",
              "stop": "⏹️ پخش پایان یافت", "shuffle": "🔀 صف قاطی شد!"}

    if data == "pause":
        asyncio.create_task(playback.cmd_pause(chat_id))
    elif data == "resume":
        asyncio.create_task(playback.cmd_resume(chat_id))
    elif data == "skip":
        asyncio.create_task(playback.cmd_skip(chat_id))
    elif data == "stop":
        asyncio.create_task(playback.cmd_stop(chat_id))
    elif data == "shuffle":
        asyncio.create_task(playback.cmd_shuffle(chat_id))
    elif data == "loop":
        new_mode = await playback.cmd_loop(chat_id)
        names = {state.LOOP_NONE: "خاموش", state.LOOP_TRACK: "یک آهنگ", state.LOOP_QUEUE: "همه‌یِ صف"}
        await bot.answer_callback_query(call.id, f"🔁 لوپ: {names.get(new_mode, new_mode)}")
        return
    elif data == "mute":
        try:
            muted = await playback.cmd_mute(chat_id)
            await bot.answer_callback_query(
                call.id, "🔇 صدا قطع شد." if muted else f"🔊 صدا وصل شد ({state.get_volume(chat_id)}%)."
            )
        except Exception as e:
            print(f"💥 mute error: {e}")
            await bot.answer_callback_query(call.id, "⚠️ تغییرِ صدا انجام نشد.")
        return
    else:
        await bot.answer_callback_query(call.id)
        return

    await bot.answer_callback_query(call.id, labels.get(data, "✅ انجام شد"))

print("🎵 Music handlers registered.")