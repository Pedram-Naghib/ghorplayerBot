"""
database.py
-------------
Direct asyncpg connection to your Supabase Postgres database. This is the
ONLY file that talks to the database - every handler goes through the
`Database` class methods below.

Table creation lives in connect() below and runs once at bot startup (see
bot.py) - there's no separate schema.sql to run manually; this file IS the
schema.

--------------------------------------------------------------------------
ROLE MODEL - single `role` column on group_users, scoped per (chat_id, user_id)
--------------------------------------------------------------------------
This bot is standalone (separate from ghormanagmentBot) but mirrors its
exact role hierarchy, MINUS "عضو ویژه" (vip) - there is no VIP tier here:

    'owner'  -> whoever added the bot to this specific group. Auto-set by
                handlers/roles_commands.py the moment the bot joins.
    'owner2' -> appointed by that group's owner (or a Global Owner/Admin).
    'admin'  -> appointed by owner or owner2.
    'normal' -> default for everyone else.

Global Owners (OWNER_USER_IDS in .env) and Global Admins (global_admins
table, promoted dynamically) are NOT scoped to a chat - full access, every
group, always. See utils/permissions.py for the full rank model.
"""

from typing import List, Optional

import asyncpg

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if not DB_HOST or not DB_PASSWORD:
            raise RuntimeError(
                "DB_HOST / DB_PASSWORD are not set. Copy .env.example to .env and fill in "
                "your Supabase Postgres connection details (Project Settings -> Database)."
            )
        self.pool = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            min_size=2,
            max_size=10,
            ssl="require",
            # If you point DB_PORT at Supabase's pooler (6543 / pgbouncer
            # transaction mode) instead of the direct connection (5432),
            # uncomment this - pgbouncer transaction mode can't handle
            # asyncpg's prepared statement cache:
            # statement_cache_size=0,
        )
        await self._init_schema()

    async def close(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def _init_schema(self):
        async with self.pool.acquire() as conn:
            # --- Per-chat role hierarchy (owner/owner2/admin/normal - no vip) ---
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS group_users (
                    chat_id BIGINT,
                    user_id BIGINT,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    role TEXT NOT NULL DEFAULT 'normal',  -- 'normal' | 'admin' | 'owner2' | 'owner'
                    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (chat_id, user_id)
                );
                """
            )

            # --- Optional media banners (ثبت تصویر [key]) - e.g. music_hub_banner ---
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_assets (
                    key TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'photo',  -- photo | animation | video
                    set_by BIGINT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )

            # --- Music: which pool-userbot is "attached" to which group
            # (see music/pool.py) - set once, the first time «پخش» succeeds
            # in that group, and reused after that so the same account
            # keeps handling that group across restarts. ---
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS music_assignments (
                    chat_id BIGINT PRIMARY KEY,
                    userbot_index INT NOT NULL,
                    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )

            # --- Global Admins (ادمین کل) - BOT-WIDE, not scoped to a chat.
            # Full access in every group, exactly like the hardcoded
            # OWNER_USER_IDS in .env, EXCEPT these are dynamic: promoted by
            # a Global Owner (or removed by that same promoter), so they
            # don't require editing .env + redeploying. ---
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS global_admins (
                    user_id BIGINT PRIMARY KEY,
                    promoted_by BIGINT NOT NULL,
                    promoted_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )

    # ---------------------------------------------------------------- #
    # USERS / PROFILE  (all scoped per chat_id, since group_users is)
    # ---------------------------------------------------------------- #

    async def upsert_user(
        self,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_users (chat_id, user_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (chat_id, user_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name
                """,
                chat_id, user_id, username, first_name, last_name,
            )

    async def get_user_display_name(self, chat_id: int, user_id: int) -> str:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT username, first_name, last_name FROM group_users WHERE chat_id=$1 AND user_id=$2",
                chat_id, user_id,
            )
        if not row:
            return str(user_id)
        name = " ".join(filter(None, [row["first_name"], row["last_name"]])).strip()
        return name or (f"@{row['username']}" if row["username"] else str(user_id))

    async def get_user_id_by_username(self, username: str) -> Optional[int]:
        """Look up a numeric user_id by @username (case-insensitive), across any chat."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id FROM group_users WHERE username ILIKE $1 LIMIT 1", username
            )
        return row["user_id"] if row else None

    # ---------------------------------------------------------------- #
    # ROLES: owner / owner2 / admin / normal  (no vip in this bot)
    # ---------------------------------------------------------------- #

    async def get_user_role(self, chat_id: int, user_id: int) -> str:
        async with self.pool.acquire() as conn:
            role = await conn.fetchval(
                "SELECT role FROM group_users WHERE chat_id=$1 AND user_id=$2", chat_id, user_id
            )
        return role or "normal"

    async def set_user_role(
        self,
        chat_id: int,
        user_id: int,
        role: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ):
        """Upsert - also creates the row if this user hasn't been seen in this chat yet."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_users (chat_id, user_id, username, first_name, last_name, role)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (chat_id, user_id) DO UPDATE SET role = EXCLUDED.role
                """,
                chat_id, user_id, username, first_name, last_name, role,
            )

    async def list_users_by_role(self, chat_id: int, role: str) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id FROM group_users WHERE chat_id=$1 AND role=$2", chat_id, role
            )
        return [r["user_id"] for r in rows]

    async def get_chat_owner(self, chat_id: int) -> Optional[int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id FROM group_users WHERE chat_id=$1 AND role='owner' LIMIT 1", chat_id
            )
        return row["user_id"] if row else None

    # ---------------------------------------------------------------- #
    # BANNERS (bot_assets) - "ثبت تصویر [key]", e.g. music_hub_banner
    # ---------------------------------------------------------------- #

    async def get_asset(self, key: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT file_id, content_type FROM bot_assets WHERE key=$1", key
            )
        return dict(row) if row else None

    async def set_asset(self, key: str, file_id: str, content_type: str = "photo", set_by: Optional[int] = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bot_assets (key, file_id, content_type, set_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (key) DO UPDATE
                    SET file_id = EXCLUDED.file_id,
                        content_type = EXCLUDED.content_type,
                        set_by = EXCLUDED.set_by,
                        updated_at = now()
                """,
                key, file_id, content_type, set_by,
            )

    # ---------------------------------------------------------------- #
    # GLOBAL ADMINS (ادمین کل) - bot-wide, see utils/global_admins.py
    # ---------------------------------------------------------------- #

    async def add_global_admin(self, user_id: int, promoted_by: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO global_admins (user_id, promoted_by)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET promoted_by = EXCLUDED.promoted_by
                """,
                user_id, promoted_by,
            )

    async def remove_global_admin(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM global_admins WHERE user_id=$1", user_id)

    async def list_global_admins(self) -> List[tuple]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, promoted_by FROM global_admins")
        return [(r["user_id"], r["promoted_by"]) for r in rows]

    # ---------------------------------------------------------------- #
    # MUSIC: chat -> pool-userbot assignment (see music/pool.py)
    # ---------------------------------------------------------------- #

    async def get_music_assignment(self, chat_id: int) -> Optional[int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT userbot_index FROM music_assignments WHERE chat_id=$1", chat_id
            )
        return row["userbot_index"] if row else None

    async def set_music_assignment(self, chat_id: int, userbot_index: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO music_assignments (chat_id, userbot_index)
                VALUES ($1, $2)
                ON CONFLICT (chat_id) DO UPDATE SET userbot_index = EXCLUDED.userbot_index
                """,
                chat_id, userbot_index,
            )