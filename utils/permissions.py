"""
utils/permissions.py
----------------------
Role model for this bot (standalone - mirrors ghormanagmentBot's hierarchy
exactly, MINUS "عضو ویژه"/vip - there is no VIP tier here, since the only
thing this bot gates is music playback and vip never had music access
there either):

    Global Owner  -> hardcoded in .env (OWNER_USER_IDS). Full access,
                     every group, always. Not stored in the database.
                     Outranks everyone below, everywhere.

    owner   (مالک اصلی)  -> whoever added the bot to a specific group.
                     Auto-set the moment the bot joins (see
                     handlers/roles_commands.py -> on_bot_added_to_chat).
                     Full access, ONLY in that group. Can appoint AND
                     remove owner2/admin - "عزل همه".

    owner2  (مالک ۲)      -> appointed by the group's owner (or a Global
                     Owner/Admin). Full access, ONLY in that group. Can
                     appoint/remove admin, but NOT another owner2 or the
                     owner - "عزل ادمین".

    admin   (ادمین)       -> appointed by owner or owner2. Full access,
                     ONLY in that group. Cannot appoint/remove anyone.

    normal  (عادی)        -> default for everyone else. No music access.

--------------------------------------------------------------------------
HIERARCHY / RANKS
--------------------------------------------------------------------------
ROLE_RANK below encodes "can actor A appoint-to/remove-from role X?" as one
comparison: an actor may appoint-to or remove-from a given role ONLY IF
their own rank is STRICTLY GREATER than that role's rank.
    owner (3) > owner2 (2) > admin (1) > normal (0)
  - owner  can manage owner2, admin (ranks 2,1)  -> "عزل همه"
  - owner2 can manage admin (rank 1), NOT owner2  -> "عزل ادمین"
  - admin  can manage nobody

Being a real Telegram admin/creator of a group does NOT, by itself, grant
bot-command access - see is_group_admin() below, used only by the
ownership-claim bootstrap for groups added before this role system
existed and so have no recorded owner yet.
"""

from telebot.async_telebot import AsyncTeleBot

from config import OWNER_USER_IDS
from database import Database
from utils import global_admins

ADMIN_STATUSES = {"administrator", "creator"}

# Higher = more powerful. Global Owner/Global Admin isn't in here - it's
# handled separately below since it's above the per-chat role system
# entirely (env-hardcoded OR dynamically promoted - see is_super_admin()).
ROLE_RANK = {"owner": 3, "owner2": 2, "admin": 1, "normal": 0}
GLOBAL_OWNER_RANK = 100  # always above everything

ROLE_LABELS_FA = {
    "owner": "👑 مالک اصلی",
    "owner2": "👑 مالک ۲",
    "admin": "👮‍♂️ ادمین",
    "normal": "👤 عادی",
}

MANAGEMENT_ROLES = ("owner", "owner2", "admin")  # all three can control music


def is_global_owner(user_id: int) -> bool:
    """STRICT/hardcoded only - OWNER_USER_IDS in .env. Prefer is_super_admin()
    below for actual access decisions; this is kept separate because WHO
    may promote a new ادمین کل is deliberately restricted to the hardcoded
    set only, not to dynamic ادمین کل too."""
    return user_id in OWNER_USER_IDS


def is_super_admin(user_id: int) -> bool:
    """True for a hardcoded Global Owner OR a dynamically-promoted
    ادمین کل (Global Admin) - both get IDENTICAL full access, every group,
    always."""
    return is_global_owner(user_id) or global_admins.is_global_admin(user_id)


async def is_group_admin(bot: AsyncTeleBot, chat_id: int, user_id: int) -> bool:
    """Real Telegram admin/creator status - used ONLY by the ownership-claim bootstrap."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ADMIN_STATUSES
    except Exception:
        return False


async def get_rank(db: Database, chat_id: int, user_id: int) -> int:
    """The actor's rank in THIS chat - a super admin always wins regardless
    of any per-chat role they may or may not also have."""
    if is_super_admin(user_id):
        return GLOBAL_OWNER_RANK
    role = await db.get_user_role(chat_id, user_id)
    return ROLE_RANK.get(role, 0)


async def is_authorized_admin(db: Database, chat_id: int, user_id: int) -> bool:
    """True if the user can control music in THIS chat - owner, owner2,
    and admin all qualify equally (no vip); the hierarchy only matters for
    WHO CAN APPOINT/REMOVE WHOM, see can_assign_role() below."""
    if is_super_admin(user_id):
        return True
    role = await db.get_user_role(chat_id, user_id)
    return role in MANAGEMENT_ROLES


async def can_assign_role(db: Database, chat_id: int, user_id: int, target_role: str) -> bool:
    """True if `user_id` may appoint someone TO `target_role`, or remove
    someone currently holding it, in THIS chat."""
    actor_rank = await get_rank(db, chat_id, user_id)
    return actor_rank > ROLE_RANK.get(target_role, 0)


async def outranks(db: Database, chat_id: int, actor_id: int, target_id: int) -> bool:
    """True if `actor_id` outranks `target_id` in THIS chat."""
    actor_rank = await get_rank(db, chat_id, actor_id)
    if is_super_admin(target_id):
        return False  # nobody outranks a super admin, ever
    target_role = await db.get_user_role(chat_id, target_id)
    return actor_rank > ROLE_RANK.get(target_role, 0)