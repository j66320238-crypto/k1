"""
Keyboards for the Start Menu, Guide, About, Help, and Force Join flows.
All keyboards are built using Aiogram v3's InlineKeyboardBuilder.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_start_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📟 Click to Host", callback_data="host_start"))
    builder.row(
        InlineKeyboardButton(text="📗 About", callback_data="about"),
        InlineKeyboardButton(text="💌 Owner", callback_data="owner")
    )
    builder.row(
        InlineKeyboardButton(text="💡 Guide", callback_data="guide"),
        InlineKeyboardButton(text="💻 Support", callback_data="support")
    )
    builder.row(InlineKeyboardButton(text="📚 Help & Commands", callback_data="help_menu"))
    return builder.as_markup()


def get_force_join_kb(link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Join Channel", url=link))
    builder.row(InlineKeyboardButton(text="✅ Verify", callback_data="verify_join"))
    return builder.as_markup()


def get_guide_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start"))
    return builder.as_markup()


def get_about_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start"))
    return builder.as_markup()


def get_owner_kb(owner_username: str, dev_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👑 Owner", url=f"https://t.me/{owner_username.lstrip('@')}"),
        InlineKeyboardButton(text="💻 Developer", url=f"https://t.me/{dev_username.lstrip('@')}")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start"))
    return builder.as_markup()


def get_support_kb(support_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Support Group", url=support_link))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start"))
    return builder.as_markup()


def get_donate_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start"))
    return builder.as_markup()


def get_help_kb(buttons: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for button in buttons:
        # Fixed: DB returns "button_name", not "name"
        button_name: str = button.get("button_name", "Unknown")
        builder.row(
            InlineKeyboardButton(
                text=button_name,
                callback_data=f"help_{button_name}"
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start"))
    return builder.as_markup()


def get_help_info_kb(button_name: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back to Help", callback_data="help_menu"))
    return builder.as_markup()