"""
music/panel_io.py
--------------------
فرستادن/ویرایشِ پیامِ «هاب» (پنلِ کنترلِ موزیک)، با در نظر گرفتنِ بنرِ
اختیاریِ «music_hub_banner» - دقیقاً همون الگویی که «پنل»/«راهنما»/«/start»
از قبل استفاده می‌کنن (نگاه کن به utils/banners.py + handlers/panel_command.py).

اگه یک عکس/گیف/ویدیو با کلیدِ music_hub_banner ثبت شده باشه (توسطِ مالکِ
ربات یا ادمین‌کل، با ریپلای‌کردن رویِ اون رسانه و نوشتنِ
«ثبت تصویر music_hub_banner»)، هاب همیشه به‌صورتِ همون رسانه + کپشن فرستاده
می‌شه؛ وگرنه دقیقاً مثلِ قبل یک پیامِ متنیِ ساده‌ست. مسیرِ کد برایِ هر دو
حالت یکیه - بقیه‌یِ فایل‌ها (music/playback.py، handlers/music_commands.py)
هیچ‌وقت مستقیماً edit_message_text/edit_message_caption صدا نمی‌زنن، همیشه
از send_panel_message/edit_panel_message اینجا رد می‌شن.

نکته‌یِ مهم (رفعِ خطایِ «wrong file identifier/HTTP URL specified»): اگه
بنرِ ثبت‌شده به هر دلیلی نامعتبر باشه (مثلاً یک file_id خراب/قدیمی، یا
content_type ثبت‌شده با نوعِ واقعیِ فایل هم‌خون نباشه)، ارسالِ بنر با یک
Bad Request از تلگرام fail می‌شه. قبلاً این خطا اینجا catch نمی‌شد و بالا
می‌رفت تا وسطِ cmd_play/handle_hub که به‌صورتِ یک ارور خام تویِ لاگ می‌افتاد
و کلِ هاب اصلاً فرستاده نمی‌شد. الان send_panel_message این حالت رو catch
می‌کنه و به‌جاش با متنِ سادهٔ همون هاب ادامه می‌ده - همون رفتاری که وقتی
اصلاً بنری ثبت نشده اتفاق می‌افته.
"""

from typing import Optional

from telebot.types import InlineKeyboardMarkup, Message

from core import bot
from utils.banners import send_banner
from music import state

BANNER_KEY = "music_hub_banner"


async def send_panel_message(
    chat_id: int,
    text: str,
    kb: Optional[InlineKeyboardMarkup] = None,
    reply_to_message_id: Optional[int] = None,
) -> Message:
    """پیامِ هاب رو می‌فرسته (بنر اگه ثبت شده و معتبر بود، وگرنه متنِ ساده) و
    یادش می‌مونه کدومش بود تا edit_panel_message بعداً درست ویرایشش کنه."""
    sent = None
    try:
        sent = await send_banner(chat_id, BANNER_KEY, text, reply_markup=kb, reply_to_message_id=reply_to_message_id)
    except Exception as e:
        print(
            f"⚠️ ارسالِ بنرِ '{BANNER_KEY}' ناموفق بود (احتمالاً file_id نامعتبر) - "
            f"برگشت به متنِ ساده: {type(e).__name__}: {e}"
        )
        sent = None

    if sent:
        state.set_panel_is_banner(chat_id, True)
        return sent

    sent = await bot.send_message(chat_id, text, reply_markup=kb, reply_to_message_id=reply_to_message_id)
    state.set_panel_is_banner(chat_id, False)
    return sent


async def edit_panel_message(chat_id: int, message_id: int, text: str, kb: Optional[InlineKeyboardMarkup] = None):
    """پیامِ هابِ موجود رو ویرایش می‌کنه - کپشن اگه بنر بود، متن اگه ساده بود.
    هیچ‌وقت exception بالا نمی‌ده (فقط لاگ می‌کنه) - این یک آپدیتِ best-effortِ
    ظاهریه، وضعیتِ واقعیِ پخش (music/state.py) از قبل درست ثبت شده."""
    try:
        if state.get_panel_is_banner(chat_id):
            await bot.edit_message_caption(caption=text, chat_id=chat_id, message_id=message_id, reply_markup=kb)
        else:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            print(f"⚠️ ویرایشِ پیامِ هاب برای چتِ {chat_id} (پیامِ {message_id}) ناموفق بود: {type(e).__name__}: {e}")