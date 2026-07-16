"""
Admin Panel Keyboards for Aiogram v3 Bot
Contains inline keyboards for Admin Panel, Special Admin Panel, and Admin Settings.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_panel_kb(is_special: bool = False) -> InlineKeyboardMarkup:
    """
    Build the Main Admin Panel inline keyboard.

    Args:
        is_special (bool): If True, adds the Special Panel button.
                           Defaults to False.

    Returns:
        InlineKeyboardMarkup: The assembled admin panel keyboard.
    """
    builder = InlineKeyboardBuilder()

    # Row 1: Stats | Broadcast
    builder.button(text="📊 Stats", callback_data="admin_stats")
    builder.button(text="📢 Broadcast", callback_data="admin_broadcast")

    # Row 2: Settings | Help Menu
    builder.button(text="⚙️ Settings", callback_data="admin_settings")
    builder.button(text="📑 Help Menu", callback_data="admin_help_menu")

    # Row 3: SSH Servers (full width)
    builder.button(text="🖥 SSH Servers", callback_data="ssh_dashboard")

    # Row 4: Special Panel — only for special admin
    if is_special:
        builder.button(text="🔐 Special Panel", callback_data="special_panel")

    # Row 5: Back to Bot (full width)
    builder.button(text="⬅️ Back to Bot", callback_data="back_to_start")

    # Adjust row layout: [2, 2, 1, (1), 1]
    if is_special:
        builder.adjust(2, 2, 1, 1, 1)
    else:
        builder.adjust(2, 2, 1, 1)

    return builder.as_markup()


def get_special_admin_kb() -> InlineKeyboardMarkup:
    """
    Build the Special Admin Panel inline keyboard.
    Restricted to the Special Admin only.

    Returns:
        InlineKeyboardMarkup: The assembled special admin keyboard.
    """
    builder = InlineKeyboardBuilder()

    # Row 1: Download DB | All Users
    builder.button(text="📁 Download DB", callback_data="download_db")
    builder.button(text="👥 All Users", callback_data="list_all_users")

    # Row 2: Inactive Users (full width)
    builder.button(text="🛑 Inactive Users", callback_data="inactive_users")

    # Row 3: Back to Admin (full width)
    builder.button(text="⬅️ Back to Admin", callback_data="admin_panel")

    # Adjust row layout: [2, 1, 1]
    builder.adjust(2, 1, 1)

    return builder.as_markup()


def get_admin_settings_kb() -> InlineKeyboardMarkup:
    """
    Build the Admin Settings inline keyboard.

    Returns:
        InlineKeyboardMarkup: The assembled admin settings keyboard.
    """
    builder = InlineKeyboardBuilder()

    # Row 1: Set FJoin | Del FJoin
    builder.button(text="🔗 Set FJoin", callback_data="set_fjoin")
    builder.button(text="🗑 Del FJoin", callback_data="del_fjoin")

    # Row 2: Set Support | Set Owner
    builder.button(text="💬 Set Support", callback_data="set_support")
    builder.button(text="👑 Set Owner", callback_data="set_owner")

    # Row 3: Back to Admin (full width)
    builder.button(text="⬅️ Back to Admin", callback_data="admin_panel")

    # Adjust row layout: [2, 2, 1]
    builder.adjust(2, 2, 1)

    return builder.as_markup()