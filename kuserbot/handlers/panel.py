"""
handlers/panel.py
=================
NEW (v3.1): Admin Panel — wires up the previously DEAD admin_kb.py
keyboards into a working /admin dashboard.

Commands:
    /admin      — open the admin panel

Working buttons:
    📊 Stats            — live bot statistics
    📢 Broadcast        — instructions + /broadcast
    ⚙️ Settings         — settings menu with set/del buttons
    📑 Help Menu        — instructions + /listhelp
    🖥 SSH Servers      — opens the existing SSH dashboard
    🔐 Special Panel    — special-admin only: DB download, all users,
                          inactive users
    👥 All Users        — full user list
    🛑 Inactive Users   — users marked inactive
"""

import html
import logging
import os

from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from config import ADMIN_IDS, SPECIAL_ADMIN_ID, DB_PATH
from database import db
from keyboards.admin_kb import (
    get_admin_panel_kb,
    get_admin_settings_kb,
    get_special_admin_kb,
)

logger = logging.getLogger(__name__)
router = Router(name="admin_panel")


# ────────────────────────────────────────────────
# Filters
# ────────────────────────────────────────────────
class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user) and (user.id in ADMIN_IDS or user.id == SPECIAL_ADMIN_ID)


class IsSpecialAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user) and user.id == SPECIAL_ADMIN_ID


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """Edit in place; fall back to a new message if editing fails."""
    try:
        await callback.message.edit_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        try:
            await callback.message.answer(
                text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def _stats_text() -> str:
    users = await db.get_all_users()
    total = len(users)
    active = sum(
        1 for u in users
        if (u.get("is_active", 1) if isinstance(u, dict) else 1) == 1
    )
    hosted = sum(
        1 for u in users
        if isinstance(u, dict) and u.get("session_string")
    )
    help_buttons = await db.get_all_help_buttons()
    support = await db.get_setting("support_link") or "Not set"
    owner = await db.get_setting("owner_username") or "Not set"
    fjoin = await db.get_setting("force_join_link") or "Not set"

    return (
        "📊 <b>Bot Statistics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👥 <b>Users</b>\n"
        f"   • Total: <code>{total}</code>\n"
        f"   • Active: <code>{active}</code>\n"
        f"   • Inactive: <code>{total - active}</code>\n"
        f"   • Hosted sessions: <code>{hosted}</code>\n\n"
        f"📑 <b>Help buttons:</b> <code>{len(help_buttons or [])}</code>\n\n"
        "⚙️ <b>Settings</b>\n"
        f"   • Support: <code>{html.escape(str(support))}</code>\n"
        f"   • Owner: <code>@{html.escape(str(owner))}</code>\n"
        f"   • Force Join: <code>{html.escape(str(fjoin))}</code>"
    )


# ────────────────────────────────────────────────
# /admin — open the panel
# ────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    is_special = bool(message.from_user) and message.from_user.id == SPECIAL_ADMIN_ID
    await message.reply(
        "🛠 <b>Admin Panel</b>\n\n"
        "Choose an action below:",
        reply_markup=get_admin_panel_kb(is_special=is_special),
    )


# ────────────────────────────────────────────────
# Panel callbacks
# ────────────────────────────────────────────────
@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    is_special = callback.from_user.id == SPECIAL_ADMIN_ID
    await _safe_edit(
        callback,
        "🛠 <b>Admin Panel</b>\n\nChoose an action below:",
        get_admin_panel_kb(is_special=is_special),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    try:
        await _safe_edit(callback, await _stats_text(), get_admin_panel_kb(
            is_special=callback.from_user.id == SPECIAL_ADMIN_ID))
    except Exception as exc:
        logger.exception("stats failed")
        await callback.answer(f"Error: {exc}", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery):
    await _safe_edit(
        callback,
        "📢 <b>Broadcast</b>\n\n"
        "Usage:\n"
        "• <code>/broadcast &lt;message&gt;</code> — text broadcast\n"
        "• Reply to any message with <code>/broadcast</code> — copy it "
        "to everyone\n\n"
        "<i>The broadcast runs with live progress updates.</i>",
        get_admin_panel_kb(is_special=callback.from_user.id == SPECIAL_ADMIN_ID),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_help_menu")
async def cb_admin_help_menu(callback: CallbackQuery):
    try:
        buttons = await db.get_all_help_buttons() or []
    except Exception:
        buttons = []
    lines = ["📑 <b>Help Buttons</b>\n"]
    if buttons:
        for i, btn in enumerate(buttons, start=1):
            name = btn.get("button_name", "?") if isinstance(btn, dict) else str(btn)
            lines.append(f"{i}. <code>{html.escape(name)}</code>")
    else:
        lines.append("📭 None yet.")
    lines.append(
        "\n💡 <code>/addhelp</code> to add · <code>/delhelp &lt;name&gt;</code> "
        "to delete · <code>/listhelp</code> to list"
    )
    await _safe_edit(
        callback, "\n".join(lines),
        get_admin_panel_kb(is_special=callback.from_user.id == SPECIAL_ADMIN_ID),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    await _safe_edit(callback, "⚙️ <b>Settings</b>\n\nChoose a setting to change:",
                     get_admin_settings_kb())
    await callback.answer()


@router.callback_query(F.data == "back_to_admin")
async def cb_back_to_admin(callback: CallbackQuery):
    is_special = callback.from_user.id == SPECIAL_ADMIN_ID
    await _safe_edit(
        callback,
        "🛠 <b>Admin Panel</b>\n\nChoose an action below:",
        get_admin_panel_kb(is_special=is_special),
    )
    await callback.answer()


# Settings shortcuts — tell the admin which command to use
_SETTING_HINTS = {
    "set_fjoin":  ("🔗 <b>Force Join</b>", "/setfjoin &lt;link&gt;", "sets the required channel"),
    "del_fjoin":  ("🗑 <b>Force Join</b>", "/delfjoin", "removes the force-join requirement"),
    "set_support": ("💬 <b>Support Link</b>", "/setsupport &lt;link&gt;", "updates the support link"),
    "set_owner":  ("👑 <b>Owner</b>", "/setowner &lt;username&gt;", "updates the owner username"),
}


@router.callback_query(F.data.in_({"set_fjoin", "del_fjoin", "set_support", "set_owner"}))
async def cb_setting_hint(callback: CallbackQuery):
    title, cmd, desc = _SETTING_HINTS[callback.data]
    await _safe_edit(
        callback,
        f"{title}\n\nUse:\n<code>{cmd}</code>\n\n<i>This {desc}.</i>",
        get_admin_settings_kb(),
    )
    await callback.answer()


# ────────────────────────────────────────────────
# Special panel (special admin only)
# ────────────────────────────────────────────────
@router.callback_query(F.data == "special_panel", IsSpecialAdmin())
async def cb_special_panel(callback: CallbackQuery):
    await _safe_edit(
        callback,
        "🔐 <b>Special Admin Panel</b>\n\nOwner-only tools:",
        get_special_admin_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "special_panel")
async def cb_special_panel_denied(callback: CallbackQuery):
    await callback.answer("⛔ Special Admin only!", show_alert=True)


@router.callback_query(F.data == "download_db", IsSpecialAdmin())
async def cb_download_db(callback: CallbackQuery, bot: Bot):
    await callback.answer("📦 Uploading database…")
    try:
        if not os.path.isfile(DB_PATH):
            return await callback.message.answer(
                "❌ Database file not found on the server."
            )
        size = os.path.getsize(DB_PATH)
        await callback.message.answer_document(
            FSInputFile(DB_PATH),
            caption=(f"📦 <b>Database</b>\n📁 <code>{os.path.basename(DB_PATH)}</code>"
                     f"\n📊 {size:,} bytes"),
        )
    except Exception as exc:
        logger.exception("DB download failed")
        await callback.message.answer(f"❌ Upload failed:\n<code>{exc}</code>")


@router.callback_query(F.data == "list_all_users", IsSpecialAdmin())
async def cb_list_all_users(callback: CallbackQuery):
    await callback.answer("👥 Loading…")
    try:
        users = await db.get_all_users() or []
    except Exception as exc:
        return await callback.message.answer(f"❌ DB error:\n<code>{exc}</code>")

    if not users:
        return await callback.message.answer("📭 No users registered yet.")

    lines = [f"👥 <b>All Users ({len(users)})</b>\n"]
    for u in users[:100]:  # Telegram message limit safety
        uid = u.get("user_id", "?")
        uname = u.get("username") or "—"
        phone = u.get("phone") or "—"
        status = "✅" if u.get("is_active", 1) == 1 else "🚫"
        hosted = " 🔑" if u.get("session_string") else ""
        lines.append(
            f"{status} <code>{uid}</code> · @{html.escape(str(uname))} · "
            f"{html.escape(str(phone))}{hosted}"
        )
    if len(users) > 100:
        lines.append(f"\n… and {len(users) - 100} more.")
    await callback.message.answer("\n".join(lines))


@router.callback_query(F.data == "inactive_users", IsSpecialAdmin())
async def cb_inactive_users(callback: CallbackQuery):
    await callback.answer("🛑 Loading…")
    try:
        users = await db.get_all_users() or []
    except Exception as exc:
        return await callback.message.answer(f"❌ DB error:\n<code>{exc}</code>")

    inactive = [u for u in users if u.get("is_active", 1) != 1]
    if not inactive:
        return await callback.message.answer("✅ No inactive users — everyone's active!")

    lines = [f"🛑 <b>Inactive Users ({len(inactive)})</b>\n"]
    for u in inactive[:100]:
        lines.append(f"• <code>{u.get('user_id', '?')}</code> · "
                     f"@{html.escape(str(u.get('username') or '—'))}")
    await callback.message.answer("\n".join(lines))
