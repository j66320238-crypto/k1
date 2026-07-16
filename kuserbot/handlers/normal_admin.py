"""
handlers/normal_admin.py
========================
Admin-only command handlers for the Aiogram v3 Telegram Bot.

All handlers in this router are protected by an `IsAdmin` custom filter
that checks `ADMIN_IDS` (list) and `SPECIAL_ADMIN_ID` (int) from config.
"""

import asyncio
import logging
from typing import Any, Optional

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import ADMIN_IDS, SPECIAL_ADMIN_ID
from database import db

logger = logging.getLogger(__name__)

router = Router(name="normal_admin")


# ────────────────────────────────────────────────
# Custom Admin Filter
# ────────────────────────────────────────────────
class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        uid = message.from_user.id
        return uid in ADMIN_IDS or uid == SPECIAL_ADMIN_ID

router.message.filter(IsAdmin())


# ────────────────────────────────────────────────
# FSM States
# ────────────────────────────────────────────────
class AddHelpForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_text = State()


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def _extract_user_id(user: Any) -> Optional[int]:
    if isinstance(user, int):
        return user
    if isinstance(user, dict):
        return user.get("user_id") or user.get("id")
    if isinstance(user, (list, tuple)) and user:
        return user[0]
    return None


# ────────────────────────────────────────────────
# /cancel — universal FSM cancellation
# ────────────────────────────────────────────────
@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.reply("ℹ️ Nothing to cancel.")
        return
    await state.clear()
    await message.reply("❌ Operation cancelled.")


# ────────────────────────────────────────────────
# /addhelp  — FSM flow to add a help button
# ────────────────────────────────────────────────
@router.message(Command("addhelp"))
async def cmd_addhelp(message: Message, state: FSMContext):
    await state.clear()
    await message.reply(
        "🛠 <b>Add Help Button</b>\n\n"
        "Please send the <b>Button Name</b> "
        "(this will be the text shown on the inline button).\n\n"
        "💡 Type /cancel to abort."
    )
    await state.set_state(AddHelpForm.waiting_for_name)


@router.message(AddHelpForm.waiting_for_name, F.text)
async def process_help_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.reply("❌ Name too short. Please send a valid button name:")
        return
    if len(name) > 64:
        await message.reply("❌ Name too long (max 64 chars). Please send a shorter name:")
        return
    await state.update_data(name=name)
    await state.set_state(AddHelpForm.waiting_for_text)
    await message.reply(
        f"✅ Button Name: <b>{name}</b>\n\n"
        "Now send the <b>Info Text</b> that should be displayed "
        "when the button is clicked.\n\n"
        "💡 You can use HTML formatting. Type /cancel to abort."
    )


@router.message(AddHelpForm.waiting_for_text, F.text)
async def process_help_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.reply("❌ Info text cannot be empty. Please send a valid text:")
        return

    data = await state.get_data()
    name = data.get("name")
    try:
        await db.add_help_button(name, text)
        await message.reply(
            f"✅ <b>Help Button Added Successfully!</b>\n\n"
            f"🔹 Button Name: <code>{name}</code>\n"
            f"🔹 Info Text: saved."
        )
    except Exception as e:
        logger.exception("Failed to add help button")
        await message.reply(f"❌ Failed to add help button.\n<code>{e}</code>")
    finally:
        await state.clear()


# ────────────────────────────────────────────────
# /delhelp <name>
# ────────────────────────────────────────────────
@router.message(Command("delhelp"))
async def cmd_delhelp(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❌ Usage: <code>/delhelp &lt;name&gt;</code>")
        return

    name = command.args.strip()
    try:
        deleted = await db.delete_help_button(name)
        if deleted:
            await message.reply(f"✅ Help button <code>{name}</code> has been deleted.")
        else:
            await message.reply(f"⚠️ Help button <code>{name}</code> not found.")
    except Exception as e:
        logger.exception("Failed to delete help button")
        await message.reply(f"❌ Failed to delete. Error:\n<code>{e}</code>")


# ────────────────────────────────────────────────
# /listhelp — list all help buttons
# ────────────────────────────────────────────────
@router.message(Command("listhelp"))
async def cmd_listhelp(message: Message):
    try:
        # Fixed DB method name
        buttons = await db.get_all_help_buttons()
    except Exception as e:
        logger.exception("Failed to fetch help buttons")
        await message.reply(f"❌ Failed to fetch help buttons.\n<code>{e}</code>")
        return

    if not buttons:
        await message.reply("📭 No help buttons found. Use /addhelp to create one.")
        return

    text = "📑 <b>Help Buttons List</b>\n\n"
    for i, btn in enumerate(buttons, start=1):
        name = btn.get("button_name", "Unknown") if isinstance(btn, dict) else str(btn)
        text += f"<b>{i}.</b> <code>{name}</code>\n"

    text += "\n💡 Use <code>/delhelp &lt;name&gt;</code> to delete a button."
    await message.reply(text)


# ────────────────────────────────────────────────
# Settings Commands
# ────────────────────────────────────────────────

@router.message(Command("setsupport"))
async def cmd_setsupport(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❌ Usage: <code>/setsupport &lt;link&gt;</code>")
        return
    link = command.args.strip()
    try:
        await db.set_setting("support_link", link)
        await message.reply(f"✅ Support link updated:\n<code>{link}</code>")
    except Exception as e:
        await message.reply(f"❌ Failed to update support link.\n<code>{e}</code>")

@router.message(Command("setowner"))
async def cmd_setowner(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❌ Usage: <code>/setowner &lt;username&gt;</code>")
        return
    username = command.args.strip().lstrip("@")
    try:
        await db.set_setting("owner_username", username)
        await message.reply(f"✅ Owner username updated: <code>@{username}</code>")
    except Exception as e:
        await message.reply(f"❌ Failed to update owner username.\n<code>{e}</code>")

@router.message(Command("setfjoin"))
async def cmd_setfjoin(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❌ Usage: <code>/setfjoin &lt;link&gt;</code>")
        return
    link = command.args.strip()
    try:
        await db.set_setting("force_join_link", link)
        await message.reply(f"✅ Force Join link set to:\n<code>{link}</code>")
    except Exception as e:
        await message.reply(f"❌ Failed to set force join link.\n<code>{e}</code>")

@router.message(Command("delfjoin"))
async def cmd_delfjoin(message: Message):
    try:
        await db.set_setting("force_join_link", "")
        await message.reply("✅ Force Join link has been removed.")
    except Exception as e:
        await message.reply(f"❌ Failed to remove force join link.\n<code>{e}</code>")

@router.message(Command("setwelcome"))
async def cmd_setwelcome(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("❌ Usage: <code>/setwelcome &lt;text&gt;</code>")
        return
    text = command.args.strip()
    try:
        await db.set_setting("welcome_text", text)
        await message.reply("✅ Welcome message updated.\n\n<b>Preview:</b>\n" + text)
    except Exception as e:
        await message.reply(f"❌ Failed to update welcome text.\n<code>{e}</code>")


# ────────────────────────────────────────────────
# /broadcast <message>  OR  reply /broadcast
# ────────────────────────────────────────────────
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject):
    broadcast_text: Optional[str] = None
    use_copy: bool = False

    if command.args:
        broadcast_text = command.args.strip()
    elif message.reply_to_message:
        use_copy = True
    else:
        await message.reply(
            "📢 <b>Broadcast</b>\n\n"
            "Usage:\n"
            "• <code>/broadcast &lt;message&gt;</code> — send a text message\n"
            "• Reply to any message with <code>/broadcast</code> — forward it"
        )
        return

    try:
        users = await db.get_all_users()
    except Exception as e:
        await message.reply(f"❌ Failed to fetch users.\n<code>{e}</code>")
        return

    if not users:
        await message.reply("⚠️ No users found in the database.")
        return

    total = len(users)
    success = failed = blocked = 0
    update_every = 50

    status_msg = await message.reply(
        f"📤 <b>Broadcasting started...</b>\n\n"
        f"👥 Total users: <b>{total}</b>\n"
        f"✅ Sent: 0\n❌ Failed: 0\n🚫 Blocked: 0"
    )

    for i, user in enumerate(users, start=1):
        user_id = _extract_user_id(user)
        if not user_id:
            failed += 1
            continue

        try:
            # Fixed Aiogram v3 copy logic
            if use_copy:
                await message.reply_to_message.copy_to(chat_id=user_id)
            else:
                await message.bot.send_message(user_id, broadcast_text)
            success += 1

        except TelegramRetryAfter as e:
            logger.warning(f"FloodWait: sleeping {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            try:
                if use_copy:
                    await message.reply_to_message.copy_to(chat_id=user_id)
                else:
                    await message.bot.send_message(user_id, broadcast_text)
                success += 1
            except TelegramBadRequest:
                failed += 1
                blocked += 1
                try: await db.update_user_status(user_id, 0)
                except: pass

        except TelegramBadRequest as e:
            failed += 1
            err = str(e).lower()
            if "block" in err or "chat not found" in err or "user is deactivated" in err:
                blocked += 1
                try: await db.update_user_status(user_id, 0)
                except: pass
            else:
                logger.warning(f"Send failed for {user_id}: {e}")

        except Exception as e:
            failed += 1
            logger.error(f"Unexpected error sending to {user_id}: {e}")

        if i % update_every == 0 or i == total:
            try:
                await status_msg.edit_text(
                    f"📤 <b>Broadcasting...</b>\n\n"
                    f"👥 Total users: <b>{total}</b>\n"
                    f"📊 Progress: {i}/{total}\n"
                    f"✅ Sent: {success}\n❌ Failed: {failed}\n🚫 Blocked: {blocked}"
                )
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.05)

    final_text = (
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"👥 Total users: <b>{total}</b>\n"
        f"✅ Successfully sent: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n🚫 Blocked: <b>{blocked}</b>"
    )
    try: await status_msg.edit_text(final_text)
    except: await message.reply(final_text)


# ────────────────────────────────────────────────
# /stats — bot statistics
# ────────────────────────────────────────────────
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    try:
        users = await db.get_all_users()
        total = len(users)
        active = inactive = 0
        
        for u in users:
            status = u.get("is_active", 1) if isinstance(u, dict) else 1
            if status == 1: active += 1
            else: inactive += 1

        help_buttons = await db.get_all_help_buttons()
        help_count = len(help_buttons) if help_buttons else 0

        support_link = await db.get_setting("support_link") or "Not set"
        owner = await db.get_setting("owner_username") or "Not set"
        fjoin = await db.get_setting("force_join_link") or "Not set"

        text = (
            "📊 <b>Bot Statistics</b>\n\n"
            f"👥 <b>Users</b>\n   • Total: <code>{total}</code>\n   • Active: <code>{active}</code>\n   • Inactive: <code>{inactive}</code>\n\n"
            f"📑 <b>Help Buttons</b>: <code>{help_count}</code>\n\n"
            f"⚙️ <b>Settings</b>\n   • Support: <code>{support_link}</code>\n   • Owner: <code>@{owner}</code>\n   • Force Join: <code>{fjoin}</code>"
        )
        await message.reply(text)
    except Exception as e:
        await message.reply(f"❌ Failed to fetch stats.\n<code>{e}</code>")