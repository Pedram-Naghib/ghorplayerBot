"""
handlers/start_command.py
-----------------------------
«/start» و «راهنما» - این متن‌ها باید برایِ یک ادمینِ گروه که هیچ‌وقت
گیت‌هاب یا setup.md رو باز نمی‌کنه، به‌تنهایی کافی باشن. یعنی همه‌چیز رو
فقط از داخلِ خودِ تلگرام توضیح می‌دن، نه با ارجاع به فایل/لینکِ بیرونی.

دستورها با <code>...</code> نوشته می‌شن چون تویِ تلگرام رویِ موبایل/دسکتاپ
با لمس/کلیک روی متنِ کد، همون متن کپی می‌شه - یعنی کاربر لازم نیست دستی
تایپ کنه، فقط لمس می‌کنه و پیست می‌کنه.

«راهنما» به‌جایِ یک پیامِ متنیِ طولانی، یک منویِ دکمه‌ایه - هر بخش با یک
دکمه‌یِ شیشه‌ای باز می‌شه (با دکمه‌یِ «بازگشت» برایِ رجوع به منو)، تا کسی
مجبور نباشه یک پیامِ بلند رو اسکرول کنه. «/start» هم خودش یک دکمه‌ی «📖
راهنما» داره که مستقیم همین منو رو باز می‌کنه.

INVOKER-LOCK: هر پیامِ حاویِ این دکمه‌ها (چه از «/start» چه از «راهنما»)
فقط توسطِ همون کسی که دستور رو زده قابلِ‌استفاده‌ست - آیدیِ همون فرستنده
داخلِ خودِ callback_data کدگذاری می‌شه (نیازی به دیتابیس/حافظه‌ی جدا نیست)
و هر کلیکِ کسِ دیگه‌ای رد می‌شه.
"""

from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core import bot
from utils.text import normalize_trigger

# هر بخش: (عنوانِ دکمه، متنِ کامل). ترتیبِ دیکشنری همون ترتیبِ دکمه‌هاست.
HELP_SECTIONS = {
    "admin": (
        "🔧 چرا باید ادمینم کنی",
        "🔧 <b>چرا باید ادمینم کنی</b>\n\n"
        "بدونِ این‌که ادمینِ گروه باشم، تلگرام اصلاً پیام‌هایِ متنیِ گروه (مثلِ "
        "<code>پخش</code>, <code>هاب</code>, <code>یوزربات ها</code>) رو برایِ من "
        "نمی‌فرسته و کاملاً ساکت می‌مونم - این محدودیتِ خودِ تلگرامه، نه خرابیِ ربات.\n\n"
        "برایِ رفعش: از تنظیماتِ گروه -> اعضا -> رویِ من بزن -> ارتقا به ادمین. "
        "به هیچ دسترسیِ خاصی نیاز ندارم، همینِ عنوانِ «ادمین» کافیه.",
    ),
    "roles": (
        "👑 نقش‌ها و دسترسی‌ها",
        "👑 <b>نقش‌ها</b> (فقط این‌ها می‌تونن موزیک رو کنترل کنن)\n\n"
        "• <b>مالکِ اصلی</b>: خودکار، هرکس من رو به گروه اضافه کرده باشه\n"
        "• <b>مالکِ ۲</b>: با <code>افزودن مالک دو</code> (ریپلای رویِ کاربر، "
        "فقط توسطِ مالکِ اصلی)\n"
        "• <b>ادمین</b>: با <code>افزودن ادمین</code> (ریپلای رویِ کاربر، توسطِ "
        "مالکِ اصلی یا مالکِ ۲)\n\n"
        "برایِ برداشتنِ هرکدوم: <code>حذف مالک دو</code> یا <code>حذف ادمین</code> "
        "(ریپلای رویِ همون کاربر)\n"
        "برایِ دیدنِ لیستِ نقش‌هایِ همین گروه: <code>مدیران</code>",
    ),
    "music": (
        "🎵 دستورهایِ پخش",
        "🎵 <b>پخشِ موزیک</b>\n\n"
        "• <code>پخش</code> - رویِ یک فایلِ صوتی/ویدیویی ریپلای کن و همینو بنویس\n"
        "• <code>پخش آهنگ</code> - بعدش اسمِ آهنگ یا لینکِ یوتیوب رو بنویس "
        "(مثلاً: <code>پخش آهنگ شادمهر عقیلی یلدا</code>)\n"
        "• <code>هاب</code> - نمایشِ دوباره‌یِ پنلِ شیشه‌ایِ کنترل\n"
        "• <code>مکث</code> / <code>ادامه پخش</code> / <code>بعدی</code> / "
        "<code>پایان پخش</code> / <code>شافل</code>",
    ),
    "pool": (
        "🎛 یوزربات ها (ورود به ویس‌چت)",
        "🎛 <b>یوزربات ها</b>\n\n"
        "برایِ پخش در ویس‌چت، یک اکانتِ کمکی («یوزربات») باید عضوِ این گروه "
        "باشه. بنویس <code>یوزربات ها</code> تا ببینی کدوم‌ها آماده‌ان و کدوم‌ها "
        "رو باید به گروه اضافه کنی؛ اولین باری که <code>پخش</code> جواب بده، "
        "یکی از اون‌ها همیشگی به همین گروه چسبیده می‌مونه.",
    ),
}

MENU_TEXT = "📖 <b>راهنمایِ ربات</b>\n\nیک بخش رو انتخاب کن:"

START_TEXT = (
    "🎵 <b>سلام!</b>\n\n"
    "من یک ربات پخشِ موزیک برایِ ویس‌چتِ گروه‌هایِ تلگرام هستم.\n\n"
    "برایِ شروع:\n"
    "۱. من رو به یک گروه اضافه کن (خودکار <b>مالکِ اصلیِ</b> همون گروه می‌شی)\n"
    "۲. از تنظیماتِ گروه من رو <b>ادمین</b> کن\n"
    "۳. رویِ یک فایلِ صوتی/ویدیویی ریپلای کن و بنویس <code>پخش</code>\n\n"
    "برایِ راهنمایِ کامل، دکمه‌یِ زیر رو بزن 👇"
)


# ── ساختِ callback_data با آیدیِ فرستنده داخلش (invoker-lock) ──────────
def _cb(action: str, invoker_id: int) -> str:
    return f"help|{action}|{invoker_id}"


def _parse_cb(data: str):
    _prefix, action, invoker_id = data.split("|", 2)
    return action, int(invoker_id)


def _menu_kb(invoker_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for key, (label, _text) in HELP_SECTIONS.items():
        kb.row(InlineKeyboardButton(label, callback_data=_cb(key, invoker_id)))
    kb.row(InlineKeyboardButton("❌ بستن", callback_data=_cb("close", invoker_id)))
    return kb


def _section_kb(invoker_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔙 بازگشت به راهنما", callback_data=_cb("menu", invoker_id)))
    return kb


def _start_kb(invoker_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("📖 راهنما", callback_data=_cb("menu", invoker_id)))
    return kb


@bot.message_handler(commands=["start"])
async def handle_start(message: Message):
    await bot.reply_to(message, START_TEXT, reply_markup=_start_kb(message.from_user.id))


@bot.message_handler(func=lambda m: normalize_trigger(m.text or "").strip() in ("راهنما", "کمک", "help"))
async def handle_help(message: Message):
    await bot.reply_to(message, MENU_TEXT, reply_markup=_menu_kb(message.from_user.id))


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("help|"))
async def handle_help_buttons(call: CallbackQuery):
    action, invoker_id = _parse_cb(call.data)

    if call.from_user.id != invoker_id:
        await bot.answer_callback_query(
            call.id, "⛔️ این دکمه فقط برایِ کسیه که خودش این دستور رو زده.", show_alert=True
        )
        return

    if action == "close":
        try:
            await bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        await bot.answer_callback_query(call.id)
        return

    if action == "menu":
        await bot.edit_message_text(
            MENU_TEXT, call.message.chat.id, call.message.message_id, reply_markup=_menu_kb(invoker_id)
        )
        await bot.answer_callback_query(call.id)
        return

    section = HELP_SECTIONS.get(action)
    if not section:
        await bot.answer_callback_query(call.id)
        return
    _label, text = section
    await bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=_section_kb(invoker_id)
    )
    await bot.answer_callback_query(call.id)