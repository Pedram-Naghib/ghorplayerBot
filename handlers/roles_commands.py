"""
handlers/roles_commands.py
-----------------------------
مدیریتِ سلسله‌مراتبِ نقش‌ها - دقیقاً همون مدلِ ghormanagmentBot، منهایِ عضوِ
ویژه (چون اینجا فقط موزیک رو کنترل می‌کنه و ویژه هیچ‌وقت به موزیک دسترسی
نداشت): مالکِ ربات (env) > ادمین‌کل > مالکِ اصلیِ گروه > مالکِ ۲ > ادمین > عادی.

- مالکِ اصلیِ گروه خودکار ثبت می‌شه: هرکس ربات رو به گروه اضافه کنه.
- «افزودن مالک دو» / «حذف مالک دو»   - فقط مالکِ اصلی (یا بالاتر)
- «افزودن ادمین» / «حذف ادمین»       - مالکِ اصلی یا مالکِ ۲
- «افزودن ادمین کل» / «حذف ادمین کل» - فقط مالکِ ربات (بات‌وایید، نه مخصوصِ یک گروه)
- «مدیران»                          - نمایشِ نقش‌هایِ همین گروه
- «ثبت تصویر [کلید]»                 - ثبتِ بنر (مثلاً music_hub_banner) - فقط مالکِ ربات/ادمین‌کل
"""

import re
from dataclasses import dataclass
from typing import Optional

from telebot.types import ChatMemberUpdated, Message

from core import bot, db
from utils.text import normalize_trigger, normalize_fa
from utils.permissions import (
    is_global_owner,
    is_super_admin,
    can_assign_role,
    ROLE_LABELS_FA,
)
from utils import global_admins

IN_CHAT_STATUSES = {"member", "administrator", "restricted"}

ADD_OWNER2_TRIGGERS = {"افزودن مالک دو", "افزودن مالک ۲"}
REMOVE_OWNER2_TRIGGERS = {"حذف مالک دو", "حذف مالک ۲"}
ADD_ADMIN_TRIGGERS = {"افزودن ادمین گروه", "افزودن ادمین"}
REMOVE_ADMIN_TRIGGERS = {"حذف ادمین گروه", "حذف ادمین"}
ADD_GLOBAL_ADMIN_TRIGGERS = {"افزودن ادمین کل"}
REMOVE_GLOBAL_ADMIN_TRIGGERS = {"حذف ادمین کل"}
LIST_GLOBAL_ADMINS_TRIGGERS = {"لیست ادمین کل"}
SHOW_ROLES_TRIGGERS = {"مدیران", "نقش ها", "نقش‌ها"}
SET_IMAGE_PREFIX = "ثبت تصویر"

_BANNER_CONTENT_TYPES = ("photo", "animation", "video")


def _norm(message: Message) -> str:
    return normalize_trigger(message.text or "").strip()


# ---------------------------------------------------------------- #
# TARGET RESOLUTION - same three ways as ghormanagmentBot:
#   1. "@username" written directly in the command
#   2. reply to a bare "@username" message
#   3. reply to the person's own message
# ---------------------------------------------------------------- #
@dataclass
class _TargetRef:
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @property
    def full_name(self) -> str:
        if self.first_name:
            return self.first_name + (f" {self.last_name}" if self.last_name else "")
        return f"@{self.username}" if self.username else str(self.id)


def _is_bare_username(text: str) -> Optional[str]:
    tokens = text.strip().split()
    if len(tokens) == 1 and tokens[0].startswith("@") and len(tokens[0]) > 1:
        return tokens[0][1:]
    return None


async def _resolve_target(message: Message) -> Optional[_TargetRef]:
    match = re.search(r"@(\w+)", normalize_fa(message.text or ""))
    if match:
        username = match.group(1)
        user_id = await db.get_user_id_by_username(username)
        if user_id:
            return _TargetRef(id=user_id, username=username)

    reply = message.reply_to_message
    if not reply:
        return None

    reply_text = normalize_fa(reply.text or reply.caption or "")
    bare_username = _is_bare_username(reply_text)
    if bare_username:
        user_id = await db.get_user_id_by_username(bare_username)
        if user_id:
            return _TargetRef(id=user_id, username=bare_username)
        return None

    if reply.from_user:
        u = reply.from_user
        return _TargetRef(id=u.id, username=u.username, first_name=u.first_name, last_name=u.last_name)
    return None


def _mention(target: _TargetRef) -> str:
    return f'<a href="tg://user?id={target.id}">{target.full_name}</a>'


# ---------------------------------------------------------------- #
# AUTO-OWNER: whoever adds the bot to a group becomes its «مالک اصلی»
# ---------------------------------------------------------------- #
@bot.my_chat_member_handler()
async def on_bot_added_to_chat(update: ChatMemberUpdated):
    if update.chat.type not in ("group", "supergroup"):
        return

    was_in_chat = update.old_chat_member.status in IN_CHAT_STATUSES
    is_in_chat = update.new_chat_member.status in IN_CHAT_STATUSES

    if not was_in_chat and is_in_chat and update.from_user:
        await db.set_user_role(
            update.chat.id, update.from_user.id, "owner",
            username=update.from_user.username, first_name=update.from_user.first_name,
            last_name=update.from_user.last_name,
        )
        try:
            await bot.send_message(
                update.chat.id,
                f"👑 {update.from_user.full_name} من رو به این گروه اضافه کرد و به‌عنوان "
                f"<b>مالکِ اصلیِ این گروه</b> ثبت شد - فقط در همین گروه، دسترسیِ کامل به کنترلِ "
                f"موزیک داره و می‌تونه مالکِ ۲/ادمین هم تعیین کنه.\n\n"
                f"⚠️ برای این‌که بتونم وارد ویس‌چت بشم، یکی از یوزربات‌های استخر باید عضوِ این "
                f"گروه باشه - با «یوزربات‌ها» می‌تونی ببینی کدوم‌ها آماده‌ان.\n\n"
                f"برای شروع: رویِ یک فایلِ صوتی ریپلای کن و بنویس «پخش».",
            )
        except Exception:
            pass


# ---------------------------------------------------------------- #
# ADMIN (owner or owner2 can appoint/remove)
# ---------------------------------------------------------------- #
@bot.message_handler(chat_types=["group", "supergroup"], func=lambda m: _norm(m) in ADD_ADMIN_TRIGGERS)
async def add_admin(message: Message):
    if not await can_assign_role(db, message.chat.id, message.from_user.id, "admin"):
        await bot.reply_to(message, "⚠️ فقط مالکِ اصلی یا مالکِ ۲ این گروه می‌تواند ادمین اضافه کند.")
        return
    target = await _resolve_target(message)
    if not target:
        await bot.reply_to(message, "⚠️ رویِ پیامِ کاربری که می‌خواهید ادمین شود ریپلای کنید.")
        return
    await db.set_user_role(message.chat.id, target.id, "admin",
                            username=target.username, first_name=target.first_name, last_name=target.last_name)
    await bot.reply_to(
        message,
        f"✅ {target.full_name} اکنون ادمینِ این گروه است (فقط در همین گروه) و می‌تواند موزیک "
        f"را کنترل کند.\n\n{_mention(target)}",
    )


@bot.message_handler(chat_types=["group", "supergroup"], func=lambda m: _norm(m) in REMOVE_ADMIN_TRIGGERS)
async def remove_admin(message: Message):
    if not await can_assign_role(db, message.chat.id, message.from_user.id, "admin"):
        await bot.reply_to(message, "⚠️ فقط مالکِ اصلی یا مالکِ ۲ این گروه می‌تواند دسترسیِ ادمین را بگیرد.")
        return
    target = await _resolve_target(message)
    if not target:
        await bot.reply_to(message, "⚠️ رویِ پیامِ کاربرِ موردنظر ریپلای کنید.")
        return
    if await db.get_user_role(message.chat.id, target.id) != "admin":
        await bot.reply_to(message, f"{target.full_name} ادمینِ این گروه نیست.")
        return
    await db.set_user_role(message.chat.id, target.id, "normal")
    await bot.reply_to(message, f"✅ دسترسیِ ادمین از {target.full_name} گرفته شد.")


# ---------------------------------------------------------------- #
# OWNER2 (only the group owner can appoint/remove)
# ---------------------------------------------------------------- #
@bot.message_handler(chat_types=["group", "supergroup"], func=lambda m: _norm(m) in ADD_OWNER2_TRIGGERS)
async def add_owner2(message: Message):
    if not await can_assign_role(db, message.chat.id, message.from_user.id, "owner2"):
        await bot.reply_to(message, "⚠️ فقط مالکِ اصلیِ این گروه می‌تواند مالکِ ۲ تعیین کند.")
        return
    target = await _resolve_target(message)
    if not target:
        await bot.reply_to(message, "⚠️ رویِ پیامِ کاربری که می‌خواهید مالکِ ۲ شود ریپلای کنید.")
        return
    await db.set_user_role(message.chat.id, target.id, "owner2",
                            username=target.username, first_name=target.first_name, last_name=target.last_name)
    await bot.reply_to(
        message,
        f"✅ {target.full_name} اکنون مالکِ ۲ این گروه است (فقط در همین گروه) و می‌تواند ادمین "
        f"هم تعیین/عزل کند.\n\n{_mention(target)}",
    )


@bot.message_handler(chat_types=["group", "supergroup"], func=lambda m: _norm(m) in REMOVE_OWNER2_TRIGGERS)
async def remove_owner2(message: Message):
    if not await can_assign_role(db, message.chat.id, message.from_user.id, "owner2"):
        await bot.reply_to(message, "⚠️ فقط مالکِ اصلیِ این گروه می‌تواند دسترسیِ مالکِ ۲ را بگیرد.")
        return
    target = await _resolve_target(message)
    if not target:
        await bot.reply_to(message, "⚠️ رویِ پیامِ کاربرِ موردنظر ریپلای کنید.")
        return
    if await db.get_user_role(message.chat.id, target.id) != "owner2":
        await bot.reply_to(message, f"{target.full_name} مالکِ ۲ این گروه نیست.")
        return
    await db.set_user_role(message.chat.id, target.id, "normal")
    await bot.reply_to(message, f"✅ دسترسیِ مالکِ ۲ از {target.full_name} گرفته شد.")


# ---------------------------------------------------------------- #
# GLOBAL ADMIN (ادمین کل) - bot-wide, only the hardcoded Global Owner
# ---------------------------------------------------------------- #
@bot.message_handler(func=lambda m: _norm(m) in ADD_GLOBAL_ADMIN_TRIGGERS)
async def add_global_admin_cmd(message: Message):
    if not is_global_owner(message.from_user.id):
        await bot.reply_to(message, "⛔️ فقط مالکِ ربات می‌تواند ادمینِ کلِ جدید تعیین کند.")
        return
    target = await _resolve_target(message)
    if not target:
        await bot.reply_to(message, "⚠️ رویِ پیامِ کاربری که می‌خواهید ادمینِ کل شود ریپلای کنید.")
        return
    await global_admins.add(db, target.id, promoted_by=message.from_user.id)
    await bot.reply_to(
        message,
        f"✅ {target.full_name} اکنون ادمینِ کلِ ربات است - دسترسیِ کامل در همه‌یِ گروه‌ها، "
        f"بالاتر از مالکِ اصلی/مالکِ ۲/ادمینِ هر گروه.\n\n{_mention(target)}",
    )


@bot.message_handler(func=lambda m: _norm(m) in REMOVE_GLOBAL_ADMIN_TRIGGERS)
async def remove_global_admin_cmd(message: Message):
    target = await _resolve_target(message)
    if not target:
        await bot.reply_to(message, "⚠️ رویِ پیامِ کاربرِ موردنظر ریپلای کنید.")
        return
    if not global_admins.is_global_admin(target.id):
        await bot.reply_to(message, f"{target.full_name} ادمینِ کل نیست.")
        return
    promoter_id = global_admins.get_promoter(target.id)
    if not (is_global_owner(message.from_user.id) or message.from_user.id == promoter_id):
        await bot.reply_to(message, "⛔️ فقط مالکِ ربات یا کسی که این فرد را ادمینِ کل کرده می‌تواند این دسترسی را بگیرد.")
        return
    await global_admins.remove(db, target.id)
    await bot.reply_to(message, f"✅ دسترسیِ ادمینِ کل از {target.full_name} گرفته شد.")


@bot.message_handler(func=lambda m: _norm(m) in LIST_GLOBAL_ADMINS_TRIGGERS)
async def list_global_admins_cmd(message: Message):
    if not is_global_owner(message.from_user.id):
        await bot.reply_to(message, "⛔️ این دستور فقط مخصوصِ مالکِ ربات است.")
        return
    ids = global_admins.list_ids()
    if not ids:
        await bot.reply_to(message, "هیچ ادمینِ کلی تعیین نشده.")
        return
    lines = []
    for uid in ids:
        name = await db.get_user_display_name(message.chat.id, uid) or str(uid)
        lines.append(f"• {name} (<code>{uid}</code>)")
    await bot.reply_to(message, "🔓 ادمین‌های کل:\n" + "\n".join(lines))


# ---------------------------------------------------------------- #
# SHOW ROLES - «مدیران»
# ---------------------------------------------------------------- #
@bot.message_handler(chat_types=["group", "supergroup"], func=lambda m: _norm(m) in SHOW_ROLES_TRIGGERS)
async def show_roles(message: Message):
    chat_id = message.chat.id
    lines = []
    for role in ("owner", "owner2", "admin"):
        ids = await db.list_users_by_role(chat_id, role)
        if not ids:
            continue
        label = ROLE_LABELS_FA[role]
        names = [await db.get_user_display_name(chat_id, uid) for uid in ids]
        lines.append(f"{label}: " + "، ".join(names))
    if not lines:
        await bot.reply_to(message, "هنوز هیچ نقشی در این گروه ثبت نشده.")
        return
    await bot.reply_to(message, "👥 <b>نقش‌های این گروه</b>\n\n" + "\n".join(lines))


# ---------------------------------------------------------------- #
# IMAGE REGISTRATION - reply to a photo/GIF/video with "ثبت تصویر [key]"
# ---------------------------------------------------------------- #
# Global-Owner-only (these are bot-wide assets, e.g. music_hub_banner, not
# per-group). Captures the media's file_id (+ which of photo/animation/
# video it is - see utils/banners.py) and stores just that tiny string -
# Telegram keeps hosting the actual file forever, we never touch the bytes.
@bot.message_handler(func=lambda m: _norm(m).startswith(SET_IMAGE_PREFIX))
async def set_image(message: Message):
    if not is_super_admin(message.from_user.id):
        await bot.reply_to(message, "⛔️ این دستور فقط مخصوصِ مالکِ ربات/ادمینِ کل است.")
        return
    parts = _norm(message).split()
    reply = message.reply_to_message
    if len(parts) < 3 or not reply or reply.content_type not in _BANNER_CONTENT_TYPES:
        await bot.reply_to(
            message,
            "⚠️ رویِ یک عکس، گیف یا ویدیو ریپلای کنید و بنویسید:\n<code>ثبت تصویر [کلید]</code>\n"
            "مثال: <code>ثبت تصویر music_hub_banner</code>",
        )
        return
    key = parts[2]
    if reply.content_type == "photo":
        file_id = reply.photo[-1].file_id
    elif reply.content_type == "animation":
        file_id = reply.animation.file_id
    else:  # video
        file_id = reply.video.file_id
    await db.set_asset(key, file_id, content_type=reply.content_type, set_by=message.from_user.id)
    kind_label = {"photo": "تصویر", "animation": "گیف", "video": "ویدیو"}[reply.content_type]
    await bot.reply_to(message, f"✅ {kind_label} با کلیدِ <code>{key}</code> ذخیره شد.")