"""
bot.py
--------
Entry point. Picks the run mode automatically:

    - WEBHOOK_URL set in .env  -> runs an aiohttp webhook server (for a server/VPS/PaaS).
    - WEBHOOK_URL empty        -> runs long polling (for local development).

Run with:
    python bot.py
"""

import asyncio
import logging

from aiohttp import web

from config import BOT_TOKEN, WEBAPP_HOST, WEBAPP_PORT, WEBHOOK_PATH, WEBHOOK_URL
from core import bot, db
from utils import global_admins

# Import handler modules so their @bot.message_handler decorators register.
# ORDER MATTERS: pyTelegramBotAPI tests handlers in registration order and
# stops at the first match, so start/roles must be imported before music
# (music's own handlers are already narrow/specific - see
# handlers/music_commands.py's module docstring for why that matters).
from handlers import start_command  # noqa: F401
from handlers import roles_commands  # noqa: F401
from handlers import music_commands  # noqa: F401  (registers its own handlers on import)
from music import playback as music_playback
from music import pool as music_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member"]


def _build_web_app() -> web.Application:
    """Bare aiohttp app - just a health-check route so Render (or any PaaS
    that expects something bound to $PORT) sees the service as up, whether
    we're in webhook mode or polling mode. The actual Telegram webhook
    route (if any) is added on top of this in run_webhook()."""
    app = web.Application()

    async def health(_request):
        return web.Response(text="ok")

    app.router.add_get("/", health)
    return app


async def _start_web_app(app: web.Application):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logger.info("Web server (health check) listening on %s:%s", WEBAPP_HOST, WEBAPP_PORT)


async def run_polling():
    logger.info("Starting in POLLING mode (local development)...")
    await bot.remove_webhook()
    await _start_web_app(_build_web_app())
    await bot.infinity_polling(skip_pending=True, allowed_updates=ALLOWED_UPDATES)


async def run_webhook():
    """Production mode: run an aiohttp server and let Telegram push updates to it.

    Assumes you're behind a reverse proxy / PaaS that terminates HTTPS
    (Render, Railway, Fly.io, nginx, Caddy, etc.)."""
    from telebot.types import Update

    logger.info("Starting in WEBHOOK mode -> %s%s", WEBHOOK_URL, WEBHOOK_PATH)

    app = _build_web_app()

    async def handle_webhook(request: web.Request):
        if request.match_info.get("token") != BOT_TOKEN:
            return web.Response(status=403)
        update = Update.de_json(await request.json())
        await bot.process_new_updates([update])
        return web.Response()

    app.router.add_post("/webhook/{token}", handle_webhook)

    await bot.remove_webhook()
    await bot.set_webhook(url=f"{WEBHOOK_URL}{WEBHOOK_PATH}", allowed_updates=ALLOWED_UPDATES)

    await _start_web_app(app)
    await asyncio.Event().wait()  # keep the process alive


async def main():
    logger.info("Connecting to the database...")
    await db.connect()  # opens the asyncpg pool AND creates tables if missing
    await global_admins.load(db)  # seed the in-memory ادمین کل cache

    music_playback.init(bot, db)  # wires playback.py to the bot instance + db, before the pool starts
    asyncio.create_task(music_pool.start_pool())  # connects every configured یوزربات in the background
    # so a slow/misconfigured music engine never blocks the bot itself from
    # coming up - handlers/music_commands.py already handles "engine not
    # ready yet" gracefully (see music/pool.py:get_or_assign).

    try:
        if WEBHOOK_URL:
            await run_webhook()
        else:
            await run_polling()
    finally:
        try:
            await bot.close_session()
        except Exception:
            pass  # nothing to close if no request was ever made
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())