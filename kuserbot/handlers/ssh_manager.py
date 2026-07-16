"""
handlers/ssh_manager.py
-----------------------
SSH Server management (alwaysdata.net) for the Aiogram v3 Telegram Bot.

Only admins (defined in ADMIN_IDS and SPECIAL_ADMIN_ID) can access these handlers.
"""

import asyncio
import json
import os
import logging
from typing import Any, Dict, List

import paramiko
from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from config import ADMIN_IDS, SPECIAL_ADMIN_ID, SERVERS_JSON_PATH
from database import db  # noqa: F401  (used for logging admin actions if needed)
from keyboards.ssh_kb import get_ssh_dashboard_kb, get_ssh_manage_kb

logger = logging.getLogger(__name__)

router = Router()


# ---------------------------------------------------------------------------
# Custom Filter: IsAdmin
# ---------------------------------------------------------------------------
class IsAdmin(BaseFilter):
    """
    Custom Aiogram v3 filter that restricts handler access to admins only.
    Admins are defined via ADMIN_IDS (list) and SPECIAL_ADMIN_ID (single id).
    """

    async def __call__(self, event) -> bool:
        if not hasattr(event, "from_user") or event.from_user is None:
            return False
        uid = event.from_user.id
        return uid in ADMIN_IDS or uid == SPECIAL_ADMIN_ID


# ---------------------------------------------------------------------------
# FSM States for "Add SSH Server" flow
# ---------------------------------------------------------------------------
class AddServerStates(StatesGroup):
    waiting_for_host = State()
    waiting_for_username = State()
    waiting_for_password = State()


# ---------------------------------------------------------------------------
# JSON helpers — safe read/write of servers.json
# ---------------------------------------------------------------------------
def load_servers() -> List[Dict[str, Any]]:
    """Safely load the servers.json file. Returns an empty list on any error."""
    if not os.path.exists(SERVERS_JSON_PATH):
        return []
    try:
        with open(SERVERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("servers.json is not a list. Resetting to [].")
            return []
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in servers.json: {e}")
        return []
    except OSError as e:
        logger.error(f"OS error reading servers.json: {e}")
        return []


def save_servers(servers_list: List[Dict[str, Any]]) -> bool:
    """
    Atomically save the servers list to servers.json.
    Writes to a temp file first, then replaces the original (atomic on POSIX).
    """
    try:
        parent = os.path.dirname(os.path.abspath(SERVERS_JSON_PATH))
        os.makedirs(parent, exist_ok=True)
        tmp_path = SERVERS_JSON_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(servers_list, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, SERVERS_JSON_PATH)
        return True
    except OSError as e:
        logger.error(f"Failed to write servers.json: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error saving servers.json: {e}")
        return False


# ---------------------------------------------------------------------------
# SSH helper — test connection using paramiko (Synchronous)
# ---------------------------------------------------------------------------
def test_ssh_connection(host: str, username: str, password: str, port: int = 22) -> bool:
    """Try to establish an SSH connection using paramiko. Returns True on success."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=15,
            look_for_keys=False,
            allow_agent=False,
            banner_timeout=15,
            auth_timeout=15,
        )
        return True
    except paramiko.AuthenticationException:
        logger.warning(f"SSH authentication failed for {username}@{host}")
        return False
    except paramiko.SSHException as e:
        logger.error(f"SSH error connecting to {host}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected SSH error ({username}@{host}): {e}")
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Internal UI helpers
# ---------------------------------------------------------------------------
def _dashboard_text(servers: List[Dict[str, Any]]) -> str:
    return (
        "<b>🖥 SSH Server Dashboard</b>\n\n"
        f"📦 Total servers: <b>{len(servers)}</b>\n\n"
        "Select a server to manage or add a new one."
    )


async def _show_dashboard(target, edit: bool = True):
    """Render the SSH dashboard either by editing or sending a new message."""
    servers = load_servers()
    kb = get_ssh_dashboard_kb(servers)
    text = _dashboard_text(servers)
    try:
        if edit:
            await target.edit_text(text, reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)
    except TelegramBadRequest:
        # Fall back to sending a fresh message if edit fails
        try:
            await target.answer(text, reply_markup=kb)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "ssh_dashboard", IsAdmin())
async def ssh_dashboard(callback: CallbackQuery):
    """Open the SSH dashboard."""
    await _show_dashboard(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "ssh_refresh", IsAdmin())
async def ssh_refresh(callback: CallbackQuery):
    """Refresh the dashboard."""
    await _show_dashboard(callback.message, edit=True)
    await callback.answer("Dashboard refreshed ✅")


# ---- Add Server FSM Flow ---------------------------------------------------
@router.callback_query(F.data == "ssh_add", IsAdmin())
async def cmd_add_ssh(callback: CallbackQuery, state: FSMContext):
    """Begin the add-server FSM flow."""
    await state.set_state(AddServerStates.waiting_for_host)
    try:
        await callback.message.edit_text(
            "➕ <b>Add New SSH Server</b>\n\n"
            "Step <b>1/3</b> — Send the SSH Host.\n"
            "Example: <code>ssh-username.alwaysdata.net</code>"
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "➕ <b>Add New SSH Server</b>\n\n"
            "Step <b>1/3</b> — Send the SSH Host.\n"
            "Example: <code>ssh-username.alwaysdata.net</code>"
        )
    await callback.answer()


@router.message(AddServerStates.waiting_for_host, IsAdmin())
async def process_host(message: Message, state: FSMContext):
    host = (message.text or "").strip()
    if not host or " " in host or "/" in host:
        await message.answer("❌ Invalid host. Please send a valid hostname:")
        return
    await state.update_data(host=host)
    await state.set_state(AddServerStates.waiting_for_username)
    await message.answer(
        "Step <b>2/3</b> — Send the SSH Username.\n"
        "Example: <code>your_alwaysdata_user</code>"
    )


@router.message(AddServerStates.waiting_for_username, IsAdmin())
async def process_username(message: Message, state: FSMContext):
    username = (message.text or "").strip()
    if not username or " " in username:
        await message.answer("❌ Invalid username. Please send a valid username:")
        return
    await state.update_data(username=username)
    await state.set_state(AddServerStates.waiting_for_password)
    await message.answer(
        "Step <b>3/3</b> — Send the SSH Password.\n"
        "⚠️ <i>For security, please delete this message afterwards.</i>"
    )


@router.message(AddServerStates.waiting_for_password, IsAdmin())
async def process_password(message: Message, state: FSMContext):
    password = message.text or ""
    if not password:
        await message.answer("❌ Invalid password. Please send a valid password:")
        return

    data = await state.get_data()
    host = data.get("host")
    username = data.get("username")

    if not host or not username:
        await message.answer("⚠️ Missing data. Please start over.")
        await state.clear()
        return

    await message.answer("🔄 Testing SSH connection…")

    # Run blocking paramiko connection in a separate thread to prevent bot freeze
    is_connected = await asyncio.to_thread(test_ssh_connection, host, username, password)

    if not is_connected:
        await message.answer(
            f"❌ <b>SSH connection failed</b> for <code>{username}@{host}</code>.\n"
            "Please verify your credentials and try adding it again."
        )
        await state.clear()
        return

    # Update servers.json
    servers = load_servers()
    servers = [s for s in servers if s.get("host") != host]  # replace if exists
    servers.append({
        "host": host,
        "username": username,
        "password": password,
        "port": 22,
    })
    if not save_servers(servers):
        await message.answer(
            "⚠️ SSH connection was successful, but failed to save the server to disk."
        )
    else:
        await message.answer(
            f"✅ Server <code>{username}@{host}</code> added successfully!"
        )

    await state.clear()

    # Return to dashboard
    await _show_dashboard(message, edit=False)


# ---- Manage specific server ------------------------------------------------
@router.callback_query(F.data.regexp(r"^ssh_manage:(.+)$"), IsAdmin())
async def ssh_manage(callback: CallbackQuery):
    """Show management options for a specific server."""
    parts = callback.data.split(":", 1)
    if len(parts) != 2:
        await callback.answer("Invalid callback data", show_alert=True)
        return
    host = parts[1]

    servers = load_servers()
    server = next((s for s in servers if s.get("host") == host), None)
    if not server:
        await callback.answer("Server not found.", show_alert=True)
        return

    kb = get_ssh_manage_kb(host)
    text = (
        "⚙️ <b>Manage Server</b>\n\n"
        f"🌐 Host: <code>{server.get('host')}</code>\n"
        f"👤 Username: <code>{server.get('username')}</code>\n"
        f"🔌 Port: <code>{server.get('port', 22)}</code>\n"
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


# ---- Kill server process (Placeholder) -------------------------------------
@router.callback_query(F.data.regexp(r"^ssh_kill:(.+)$"), IsAdmin())
async def ssh_kill(callback: CallbackQuery):
    """Placeholder handler for ssh_kill button to prevent dead button errors."""
    parts = callback.data.split(":", 1)
    if len(parts) != 2:
        await callback.answer("Invalid callback data", show_alert=True)
        return
    host = parts[1]
    
    # TODO: Add actual logic to kill a process via SSH here
    await callback.answer(f"Kill command sent to {host} (placeholder) 🛑", show_alert=True)


# ---- Delete server ---------------------------------------------------------
@router.callback_query(F.data.regexp(r"^ssh_del:(.+)$"), IsAdmin())
async def ssh_delete(callback: CallbackQuery):
    """Delete a server from servers.json and return to dashboard."""
    parts = callback.data.split(":", 1)
    if len(parts) != 2:
        await callback.answer("Invalid callback data", show_alert=True)
        return
    host = parts[1]

    servers = load_servers()
    new_servers = [s for s in servers if s.get("host") != host]

    if len(new_servers) == len(servers):
        await callback.answer("Server not found.", show_alert=True)
        return

    if not save_servers(new_servers):
        await callback.answer("Failed to save changes.", show_alert=True)
        return

    await callback.answer("Server deleted 🗑")

    # Return to dashboard
    kb = get_ssh_dashboard_kb(new_servers)
    text = _dashboard_text(new_servers)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)


# ---------------------------------------------------------------------------
# Optional: /ssh command — open dashboard directly
# ---------------------------------------------------------------------------
@router.message(F.text == "/ssh", IsAdmin())
async def cmd_ssh(message: Message):
    await _show_dashboard(message, edit=False)s