"""
keyboards/ssh_kb.py
-------------------
Inline keyboards for the SSH-management dashboard:
  • Server list (dynamic) with status & active users
  • Per-server management actions (delete / kill userbots)
  • Generic "Cancel" keyboard used by FSM states
"""

from typing import Any

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ---------------------------------------------------------------------------
# Status → emoji mapping. Extend here if you add more states later.
# ---------------------------------------------------------------------------
_STATUS_EMOJI: dict[str, str] = {
    "online":  "🟢",
    "offline": "🔴",
}


def _status_emoji(status: Any) -> str:
    """Return an emoji for a server status, defaulting to 🔴 on unknowns."""
    if isinstance(status, str):
        return _STATUS_EMOJI.get(status.lower(), "🔴")
    return "🔴"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def get_ssh_dashboard_kb(servers: list[dict]) -> InlineKeyboardMarkup:
    """
    Build the SSH dashboard keyboard.

    Each server produces one button:
        [🟢 host — Users: N]   or   [🔴 host — Users: N]
    with callback_data=f"ssh_manage:{host}".

    Below the server list:
        Row A: [ ➕ Add Server ] [ 🔄 Refresh ]
        Row B: [ ⬅️ Back ]

    Args:
        servers: List of dicts with keys `host`, `status`, `active_users`.

    Returns:
        InlineKeyboardMarkup: The assembled dashboard keyboard.
    """
    builder = InlineKeyboardBuilder()

    # --- Dynamic server buttons (1 per row) ---
    for srv in servers:
        host: str         = srv.get("host", "unknown")
        status: Any       = srv.get("status", "offline")
        active_users: int = int(srv.get("active_users", 0))

        emoji = _status_emoji(status)
        text  = f"{emoji} {host} — Users: {active_users}"

        builder.button(
            text=text,
            callback_data=f"ssh_manage:{host}",
        )

    # --- Static action buttons ---
    builder.button(text="➕ Add Server", callback_data="ssh_add")
    builder.button(text="🔄 Refresh",    callback_data="ssh_refresh")
    builder.button(text="⬅️ Back",       callback_data="back_to_admin")

    # Layout:
    #   • 1 button per row for each server
    #   • then 2 buttons per row (Add | Refresh)
    #   • then 1 button per row (Back)
    server_count = len(servers)
    builder.adjust(*([1] * server_count), 2, 1)

    return builder.as_markup()


# ---------------------------------------------------------------------------
# Per-server management
# ---------------------------------------------------------------------------
def get_ssh_manage_kb(host: str) -> InlineKeyboardMarkup:
    """
    Build the per-server management keyboard.

    Layout:
        Row 1: [ 🗑 Delete Server ]        (callback_data=f"ssh_del:{host}")
        Row 2: [ ⚡ Kill All Userbots ]    (callback_data=f"ssh_kill:{host}")
        Row 3: [ ⬅️ Back to Dashboard ]    (callback_data="ssh_dashboard")

    Args:
        host: The SSH host string (used inside callback_data).

    Returns:
        InlineKeyboardMarkup: The assembled management keyboard.
    """
    builder = InlineKeyboardBuilder()

    builder.button(text="🗑 Delete Server",     callback_data=f"ssh_del:{host}")
    builder.button(text="⚡ Kill All Userbots", callback_data=f"ssh_kill:{host}")
    builder.button(text="⬅️ Back to Dashboard", callback_data="ssh_dashboard")

    # Each button on its own row.
    builder.adjust(1, 1, 1)

    return builder.as_markup()


# ---------------------------------------------------------------------------
# Generic cancel — usable from any FSM state.
# ---------------------------------------------------------------------------
def get_cancel_kb() -> InlineKeyboardMarkup:
    """
    Build a single-button Cancel keyboard.

    Layout:
        Row 1: [ ❌ Cancel ]  (callback_data="cancel_action")

    Returns:
        InlineKeyboardMarkup: The assembled cancel keyboard.
    """
    builder = InlineKeyboardBuilder()

    builder.button(text="❌ Cancel", callback_data="cancel_action")

    return builder.as_markup()