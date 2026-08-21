"""
handlers/user.py
================
User-facing handlers for the Aiogram v3 Telegram Bot.
"""

import logging
import re
from typing import Optional, Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    PhoneNumberInvalidError,
)

# Cleaned imports (FIX: explicit imports instead of `import *`)
from keyboards.start_kb import (
    get_start_kb,
    get_force_join_kb,
    get_about_kb,
    get_owner_kb,
    get_guide_kb,
    get_support_kb,
    get_help_kb,
    get_help_info_kb,
)
from keyboards.otp_kb import (
    get_otp_kb,
    get_empty_otp_kb,
    OTP_DIGIT_PREFIX,
    OTP_DELETE_CB,
    OTP_SUBMIT_CB,
    OTP_CANCEL_CB,
)
from database import db
from config import SPECIAL_ADMIN_ID, ADMIN_IDS, API_ID, API_HASH
from encryption import DataEncryptor

router = Router()
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
#  FSM STATES
# ════════════════════════════════════════════════════════════════════

class HostStates(StatesGroup):
    """States for the account-hosting flow."""
    waiting_for_phone    = State()
    waiting_for_otp      = State()
    waiting_for_password = State()


# ════════════════════════════════════════════════════════════════════
#  CONSTANTS & TEMPLATES
# ════════════════════════════════════════════════════════════════════

WELCOME_ASCII = (
    "<pre>\n"
    "╔══════════════════════════════════════╗\n"
    "║                                      ║\n"
    "║      ⚡  ID  USERBOT  ⚡             ║\n"
    "║                                      ║\n"
    "╚══════════════════════════════════════╝\n"
    "</pre>"
)

WELCOME_TEXT = (
    WELCOME_ASCII
    + "\n\n"
    + "👋 <b>Welcome, {name}!</b>\n\n"
    + "🚀 <b>ID Userbot</b> — Fast & Powerful Telegram ID Userbot\n\n"
    + "✨ <b>Features:</b>\n"
    + "   ▸ 🖥 Host &amp; manage Telegram accounts\n"
    + "   ▸ 📢 Send bulk / broadcast messages\n"
    + "   ▸ 🔍 Scrape &amp; collect user data\n"
    + "   ▸ 📂 Multi-session support\n\n"
    + "👇 <i>Choose an option below to get started:</i>"
)

FORCE_JOIN_TEXT = (
    WELCOME_ASCII
    + "\n\n"
    + "🔒 <b>Verification Required</b>\n\n"
    + "To continue using this bot, please join our channel first.\n"
    + "After joining, click the <b>✅ Verify Join</b> button below."
)


# ════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def _is_admin(user_id: int) -> bool:
    """Return ``True`` if *user_id* belongs to a bot administrator."""
    return user_id == SPECIAL_ADMIN_ID or user_id in ADMIN_IDS


def _build_welcome(name: str = "there") -> str:
    """Render the premium welcome text with the user's first name."""
    safe_name = (name or "there")[:64]
    return WELCOME_TEXT.format(name=safe_name)


async def _safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    """
    Edit ``callback.message`` in place.
    Falls back to sending a new message if editing fails.
    """
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except TelegramAPIError as exc:
        logger.warning("safe_edit fallback — API error: %s", exc)
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


async def _fetch_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Safely fetch a setting from the database."""
    try:
        value = await db.get_setting(key)
        return value if value else default
    except Exception:
        logger.exception("DB error while fetching setting '%s'", key)
        return default


# ════════════════════════════════════════════════════════════════════
#  /start  COMMAND
# ════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return

    user_id   = user.id
    full_name = (user.full_name or "Unknown").strip()
    username  = user.username or ""

    # ── Persist user (Using your db.get_user() logic) ────────
    try:
        user_data = await db.get_user(user_id)
        if not user_data:
            await db.add_user(user_id, full_name, username)
        else:
            # Only update username as per your DB schema
            await db.update_user(user_id, username=username)
    except Exception:
        logger.exception("DB error while registering user %s", user_id)

    # ── Admins bypass force-join ──────────────────────────
    if _is_admin(user_id):
        await message.answer(
            _build_welcome(user.first_name or "Admin"),
            reply_markup=get_start_kb(),
            parse_mode="HTML",
        )
        return

    # ── Check force-join requirement ──────────────────────
    force_join_link = await _fetch_setting("force_join_link")

    if force_join_link:
        await message.answer(
            FORCE_JOIN_TEXT,
            reply_markup=get_force_join_kb(force_join_link),
            parse_mode="HTML",
        )
        return

    # ── No force-join → main menu ─────────────────────────
    await message.answer(
        _build_welcome(user.first_name or "there"),
        reply_markup=get_start_kb(),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════
#  VERIFY JOIN  (callback: verify_join)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "verify_join")
async def cb_verify_join(callback: CallbackQuery, bot: Bot) -> None:
    user = callback.from_user
    if user is None:
        return

    user_id = user.id
    force_join_link = await _fetch_setting("force_join_link")
    is_member = True

    if force_join_link:
        chat_target: Optional[str] = None

        if force_join_link.startswith("@"):
            chat_target = force_join_link
        elif "t.me/" in force_join_link:
            tail = force_join_link.rsplit("t.me/", 1)[-1].strip("/")
            if tail and not tail.startswith("+") and "joinchat" not in tail.lower():
                chat_target = "@" + tail

        if chat_target:
            try:
                member = await bot.get_chat_member(chat_target, user_id)
                is_member = member.status not in ("left", "kicked")
            except TelegramAPIError as exc:
                logger.warning(
                    "Membership check failed for %s in %s: %s — allowing entry",
                    user_id, chat_target, exc,
                )
                is_member = True  # fail-open

    if not is_member:
        await callback.answer(
            "⚠️ You haven't joined the channel yet!\nPlease join first.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Verified successfully!")
    await _safe_edit(
        callback,
        _build_welcome(user.first_name or "there"),
        get_start_kb(),
    )


# ════════════════════════════════════════════════════════════════════
#  ABOUT  (callback: about)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery) -> None:
    text = (
        "📖 <b>About ID Userbot</b>\n\n"
        "⚡ <b>ID Userbot</b> is a Fast &amp; Powerful Telegram ID Userbot "
        "designed to automate and streamline your Telegram operations.\n\n"
        "🔹 <b>Key Capabilities:</b>\n"
        "   ▸ 🖥 Host multiple Telegram accounts securely\n"
        "   ▸ 📢 Send bulk / broadcast messages effortlessly\n"
        "   ▸ 🔍 Scrape users, groups &amp; channel data\n"
        "   ▸ 📂 Manage sessions with OTP verification\n"
        "   ▸ ⏰ Schedule and automate recurring tasks\n\n"
        "🛡 <b>Tech Stack:</b>  Python • Aiogram v3 • Telethon\n\n"
        "⚠️ <i>Please use this bot responsibly and in accordance "
        "with Telegram's Terms of Service.</i>"
    )
    await _safe_edit(callback, text, get_about_kb())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  OWNER  (callback: owner)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "owner")
async def cb_owner(callback: CallbackQuery) -> None:
    owner     = await _fetch_setting("owner_username",    "Unknown")
    developer = await _fetch_setting("developer_username", "Unknown")

    text = (
        "👤 <b>Owner &amp; Developer</b>\n\n"
        f"👑 <b>Owner:</b>  {owner}\n"
        f"💻 <b>Developer:</b>  {developer}\n\n"
        "Feel free to reach out for inquiries, support, or collaborations."
    )
    await _safe_edit(callback, text, get_owner_kb(owner, developer))
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  GUIDE  (callback: guide)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "guide")
async def cb_guide(callback: CallbackQuery) -> None:
    text = (
        "📚 <b>Hosting Guide</b>\n\n"
        "Follow these steps to host your Telegram account:\n\n"
        "1️⃣  Click the <b>🖥 Host</b> button in the main menu.\n\n"
        "2️⃣  Send your phone number in international format\n"
        "      (e.g., <code>+919876543210</code>).\n\n"
        "3️⃣  The bot will trigger an OTP code request.\n"
        "      Check your Telegram app for the login code.\n\n"
        "4️⃣  Send the OTP code back to the bot.\n\n"
        "5️⃣  If 2-Step Verification is enabled, you'll be asked\n"
        "      for your password.\n\n"
        "✅ Your session will be created and stored securely.\n\n"
        "⚠️ <i>Only provide your phone number to bots you trust.</i>"
    )
    await _safe_edit(callback, text, get_guide_kb())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  SUPPORT  (callback: support)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery) -> None:
    support_link = await _fetch_setting("support_link", "https://t.me/support")

    text = (
        "🛠 <b>Support</b>\n\n"
        "Need help? Found a bug? Have a feature request?\n\n"
        "🔗 Click the button below to contact our support team.\n"
        "We'll get back to you as soon as possible!"
    )
    await _safe_edit(callback, text, get_support_kb(support_link))
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  HELP MENU  (callback: help_menu)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "help_menu")
async def cb_help_menu(callback: CallbackQuery) -> None:
    buttons: list = []
    try:
        result = await db.get_all_help_buttons()
        buttons = result if result else []
    except Exception:
        logger.exception("DB error while fetching help buttons")

    text = (
        "❓ <b>Help Center</b>\n\n"
        "Browse the topics below to find answers to common questions.\n"
        "Tap a button to view detailed information.\n\n"
        f"📋 <b>{len(buttons)}</b> topic(s) available."
    )
    await _safe_edit(callback, text, get_help_kb(buttons))
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  BACK TO START  (callback: back_to_start)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "back_to_start")
async def cb_back_to_start(callback: CallbackQuery) -> None:
    user = callback.from_user
    name = (user.first_name if user else "there") or "there"
    await _safe_edit(callback, _build_welcome(name), get_start_kb())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  DYNAMIC HELP TOPIC  (regex callback: ^help_(.*))
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.regexp(r"^help_(.*)"))
async def cb_help_topic(callback: CallbackQuery) -> None:
    match = re.match(r"^help_(.*)", callback.data or "")
    if not match:
        await callback.answer("Invalid request.", show_alert=True)
        return

    button_name = match.group(1).strip()
    if not button_name:
        await callback.answer("Invalid topic.", show_alert=True)
        return

    # ── Fetch info text from DB (Handling dictionary result) ──
    info_text: Optional[str] = None
    try:
        result: Optional[dict[str, Any]] = await db.get_help_button(button_name)
        if result and isinstance(result, dict):
            info_text = result.get("info_text")
    except Exception:
        logger.exception("DB error fetching help button '%s'", button_name)

    if not info_text:
        info_text = "ℹ️ No information is available for this topic at the moment."

    title = button_name.replace("_", " ").title()
    full_text = f"❓ <b>{title}</b>\n\n{info_text}"

    await _safe_edit(callback, full_text, get_help_info_kb(button_name))
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  HOST FLOW — ENTRY POINT  (callback: host_start)
# ════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "host_start")
async def cb_host_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(HostStates.waiting_for_phone)

    text = (
        "🖥 <b>Host a Telegram Account</b>\n\n"
        "Please send your phone number in international format.\n\n"
        "📝 <b>Example:</b> <code>+919876543210</code>\n\n"
        "⚠️ <i>Make sure the number is correct and active on Telegram.\n"
        "Your session will be stored securely.</i>\n\n"
        "❌ Send <code>/cancel</code> to abort."
    )

    await _safe_edit(callback, text, None)
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
#  /cancel  —  ABORT ANY HOST-FLOW STATE
# ════════════════════════════════════════════════════════════════════

@router.message(Command("cancel"), StateFilter(HostStates))
async def cmd_cancel_host(message: Message, state: FSMContext) -> None:
    await state.clear()

    user = message.from_user
    name = (user.first_name if user else "there") or "there"

    await message.answer(
        "❌ <b>Operation cancelled.</b>\n\nReturning to the main menu…",
        parse_mode="HTML",
    )
    await message.answer(
        _build_welcome(name),
        reply_markup=get_start_kb(),
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════════════════════
#  HOST FLOW — PHONE NUMBER HANDLER
# ════════════════════════════════════════════════════════════════════

# --- Phone Number Handler ---
@router.message(HostStates.waiting_for_phone, F.text)
async def process_phone(message: Message, state: FSMContext):
    phone_number = message.text.strip()
    if not phone_number.startswith("+"):
        await message.reply("❌ Invalid format. Please send in international format (e.g., +919876543210).")
        return

    # Telethon Client Setup (Using StringSession to avoid file system errors)
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    try:
        await client.send_code_request(phone_number)
        await state.update_data(phone=phone_number, client_session=client.session.save(), otp_digits="")
        await state.set_state(HostStates.waiting_for_otp)
        await message.reply(
            "✅ OTP sent to your Telegram app!\n\n"
            "Please send the OTP code now (e.g., 12345).\n\n"
            "❌ Send /cancel to abort.",
            reply_markup=get_otp_kb(),  # NEW: tap-to-type OTP numpad
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")
    finally:
        # FIX: the client was never disconnected on the success path,
        # leaking a socket + event loop per hosting attempt.
        await client.disconnect()


# ════════════════════════════════════════════════════════════════════
#  HOST FLOW — OTP HANDLER (shared by text input & numpad)
# ════════════════════════════════════════════════════════════════════

async def _verify_otp_and_store(reply_target, user_id: int, state: FSMContext, otp_code: str) -> bool:
    """Shared OTP verification for BOTH input paths (text + numpad).

    Returns True on success (state cleared), False otherwise.
    """
    data = await state.get_data()
    phone = data.get("phone")
    session_str = data.get("client_session")

    if not session_str or not phone:
        await reply_target.reply(
            "⚠️ Session expired. Please start the host flow again via "
            "<b>🖥 Host</b>.",
            parse_mode="HTML",
        )
        await state.clear()
        return False

    # Reconnect using saved string session
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=otp_code)

        # ── Login Successful! ─────────────────────────────
        string_session = client.session.save()

        # NEW (v3.1): encrypt the session string at rest (AES/Fernet)
        stored_session = DataEncryptor.encrypt(string_session)
        await db.set_session(user_id, stored_session, phone)

        await state.clear()
        await reply_target.reply(
            "✅ <b>Login Successful!</b>\n\n"
            "Your account has been securely hosted. You can now use the "
            "userbot commands.\n\n"
            "Use /start to return to the main menu.",
            parse_mode="HTML",
        )
        return True
    except PhoneCodeInvalidError:
        await reply_target.reply(
            "❌ <b>Invalid OTP.</b> Please send the correct OTP or send "
            "<code>/cancel</code>.",
            parse_mode="HTML",
        )
    except SessionPasswordNeededError:
        # 2FA is enabled — keep the same session for password step
        await state.update_data(client_session=client.session.save())
        await state.set_state(HostStates.waiting_for_password)
        await reply_target.reply(
            "🔒 <b>Two-Step Verification (2FA) Detected</b>\n\n"
            "Please send your password now.\n\n"
            "❌ Send <code>/cancel</code> to abort.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Telethon sign_in (OTP) failed for %s", user_id)
        await reply_target.reply(
            f"❌ <b>Error:</b> <code>{str(e)}</code>", parse_mode="HTML"
        )
    finally:
        # Disconnect only when not entering 2FA flow
        current_state = await state.get_state()
        if current_state != HostStates.waiting_for_password:
            await client.disconnect()
    return False


@router.message(HostStates.waiting_for_otp, F.text)
async def process_otp(message: Message, state: FSMContext) -> None:
    otp_code = (message.text or "").strip()
    await _verify_otp_and_store(message, message.from_user.id, state, otp_code)


# ════════════════════════════════════════════════════════════════════
#  HOST FLOW — OTP NUMPAD CALLBACKS (NEW v3.1)
#  Calculator-style keypad from keyboards/otp_kb.py — tap digits,
#  delete, or submit. Text input still works alongside.
# ════════════════════════════════════════════════════════════════════

def _render_otp_text(digits: str) -> str:
    if digits:
        masked = " ".join("▪" * int(d) for d in digits)
    else:
        masked = "▫ ▫ ▫ ▫ ▫ ▫"
    return (
        "✅ OTP sent to your Telegram app!\n\n"
        f"🔢 <b>Code:</b> <code>{masked}</code>\n\n"
        "Tap the digits below (or simply type the code).\n"
        "❌ Send <code>/cancel</code> to abort."
    )


@router.callback_query(HostStates.waiting_for_otp, F.data.startswith(OTP_DIGIT_PREFIX))
async def cb_otp_digit(callback: CallbackQuery, state: FSMContext):
    digit = callback.data.split(":", 1)[1]
    if not digit.isdigit():
        return await callback.answer()
    data = await state.get_data()
    digits = (data.get("otp_digits") or "") + digit
    if len(digits) > 8:
        return await callback.answer("⚠️ Too many digits!")
    await state.update_data(otp_digits=digits)
    try:
        await callback.message.edit_text(
            _render_otp_text(digits), reply_markup=get_otp_kb(), parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass  # identical text — ignore
    await callback.answer()


@router.callback_query(HostStates.waiting_for_otp, F.data == OTP_DELETE_CB)
async def cb_otp_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    digits = (data.get("otp_digits") or "")[:-1]
    await state.update_data(otp_digits=digits)
    try:
        await callback.message.edit_text(
            _render_otp_text(digits), reply_markup=get_otp_kb(), parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.callback_query(HostStates.waiting_for_otp, F.data == OTP_SUBMIT_CB)
async def cb_otp_submit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    digits = data.get("otp_digits") or ""
    if len(digits) < 4:
        return await callback.answer("⚠️ Enter the full code first!", show_alert=True)

    await callback.answer("⏳ Verifying…")
    try:
        await callback.message.edit_text(
            _render_otp_text(digits), reply_markup=get_empty_otp_kb(), parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    await _verify_otp_and_store(callback.message, callback.from_user.id, state, digits)


@router.callback_query(HostStates.waiting_for_otp, F.data == OTP_CANCEL_CB)
async def cb_otp_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("❌ <b>Operation cancelled.</b>", parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await callback.answer("Cancelled")


# ════════════════════════════════════════════════════════════════════
#  HOST FLOW — 2FA PASSWORD HANDLER
# ════════════════════════════════════════════════════════════════════

@router.message(HostStates.waiting_for_password, F.text)
async def process_password(message: Message, state: FSMContext) -> None:
    password = (message.text or "").strip()
    data = await state.get_data()
    session_str = data.get("client_session")
    phone = data.get("phone")

    if not session_str:
        await message.reply(
            "⚠️ Session expired. Please start the host flow again via "
            "<b>🖥 Host</b>.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()

    try:
        await client.sign_in(password=password)
        string_session = client.session.save()

        # Save to Database (encrypted at rest)
        stored_session = DataEncryptor.encrypt(string_session)
        await db.set_session(message.from_user.id, stored_session, phone)

        await state.clear()
        await message.reply(
            "✅ <b>Login Successful with 2FA!</b>\n\n"
            "Your account has been securely hosted.\n\n"
            "Use /start to return to the main menu.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Telethon 2FA sign_in failed for %s",
                         message.from_user.id)
        await message.reply(
            f"❌ <b>Incorrect password or error:</b>\n<code>{str(e)}</code>\n\n"
            "Try again or send <code>/cancel</code>.",
            parse_mode="HTML",
        )
    finally:
        # Only disconnect after success or final cancel
        if await state.get_state() is None:
            await client.disconnect()
