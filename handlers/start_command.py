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
مجبور نباشه یک پیامِ بلند رو اسکرول کنه.
"""

from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core import bot
from utils.text import normalize_trigger

START_TEXT = (
    "🎵 <b>سلام!</b>\n\n"
    "من یک ربات پخشِ موزیک برایِ ویس‌چتِ گروه‌هایِ تلگرام هستم.\n\n"
    "برایِ شروع:\n"
    "۱. من رو به یک گروه اضافه کن (خودکار <b>مالکِ اصلیِ</b> همون گروه می‌شی)\n"
    "۲. از تنظیماتِ گروه من رو <b>ادمین</b> کن (توضیحِ این‌که چرا لازمه رو با "
    "<code>راهنما</code> ببین)\n"
    "۳. رویِ یک فایلِ صوتی/ویدیویی ریپلای کن و بنویس <code>پخش</code>\n\n"
    "برایِ راهنمایِ کامل بنویس: <code>راهنما</code>"
)

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


def _menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for key, (label, _text) in HELP_SECTIONS.items():
        kb.row(InlineKeyboardButton(label, callback_data=f"help_{key}"))
    kb.row(InlineKeyboardButton("❌ بستن", callback_data="help_close"))
    return kb


def _section_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("🔙 بازگشت به راهنما", callback_data="help_menu"))
    return kb


MENU_TEXT = "📖 <b>راهنمایِ ربات</b>\n\nیک بخش رو انتخاب کن:"


@bot.message_handler(commands=["start"])
async def handle_start(message: Message):
    await bot.reply_to(message, START_TEXT)


@bot.message_handler(func=lambda m: normalize_trigger(m.text or "").strip() in ("راهنما", "کمک", "help"))
async def handle_help(message: Message):
    await bot.reply_to(message, MENU_TEXT, reply_markup=_menu_kb())


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("help_"))
async def handle_help_buttons(call: CallbackQuery):
    key = call.data[len("help_"):]

    if key == "close":
        try:
            await bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        await bot.answer_callback_query(call.id)
        return

    if key == "menu":
        await bot.edit_message_text(MENU_TEXT, call.message.chat.id, call.message.message_id, reply_markup=_menu_kb())
        await bot.answer_callback_query(call.id)
        return

    section = HELP_SECTIONS.get(key)
    if not section:
        await bot.answer_callback_query(call.id)
        return
    _label, text = section
    await bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=_section_kb())
    await bot.answer_callback_query(call.id)