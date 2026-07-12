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
    """پیامِ هاب رو می‌فرسته (بنر اگه ثبت شده، وگرنه متنِ ساده) و یادش می‌مونه
    کدومش بود تا edit_panel_message بعداً درست ویرایشش کنه."""
    sent = await send_banner(chat_id, BANNER_KEY, text, reply_markup=kb, reply_to_message_id=reply_to_message_id)
    if sent:
        state.set_panel_is_banner(chat_id, True)
        return sent

    sent = await bot.send_message(chat_id, text, reply_markup=kb, reply_to_message_id=reply_to_message_id)
    state.set_panel_is_banner(chat_id, False)
    return sent


async def edit_panel_message(chat_id: int, message_id: int, text: str, kb: Optional[InlineKeyboardMarkup] = None):
    """پیامِ هابِ موجود رو ویرایش می‌کنه - کپشن اگه بنر بود، متن اگه ساده بود."""
    if state.get_panel_is_banner(chat_id):
        await bot.edit_message_caption(caption=text, chat_id=chat_id, message_id=message_id, reply_markup=kb)
    else:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb)