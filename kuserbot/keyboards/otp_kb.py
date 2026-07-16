"""
keyboards/otp_kb.py
-------------------
Inline keyboard for OTP (One-Time Password) entry.
Provides a calculator-style number pad (0-9), delete, submit, and cancel actions.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ---------------------------------------------------------------------------
# Callback data prefixes — keep them centralized to avoid typos elsewhere.
# ---------------------------------------------------------------------------
OTP_DIGIT_PREFIX = "otp_digit:"      # followed by the digit, e.g. otp_digit:5
OTP_DELETE_CB    = "otp_delete"
OTP_SUBMIT_CB    = "otp_submit"
OTP_CANCEL_CB    = "otp_cancel"


def get_otp_kb() -> InlineKeyboardMarkup:
    """
    Build the OTP number-pad keyboard.

    Layout:
        Row 1:  [ 1 ] [ 2 ] [ 3 ]
        Row 2:  [ 4 ] [ 5 ] [ 6 ]
        Row 3:  [ 7 ] [ 8 ] [ 9 ]
        Row 4:  [ ⬅️ Delete ] [ 0 ] [ ✅ Submit ]
        Row 5:  [ ❌ Cancel ]            (full width)

    Returns:
        InlineKeyboardMarkup: The assembled OTP keyboard.
    """
    builder = InlineKeyboardBuilder()

    # --- Rows 1-3: digits 1 through 9 in a 3x3 grid ---
    # Using callback_data=f"{OTP_DIGIT_PREFIX}{digit}" so the handler
    # can split(":") to recover the digit cleanly.
    for digit in range(1, 10):
        builder.button(
            text=str(digit),
            callback_data=f"{OTP_DIGIT_PREFIX}{digit}",
        )

    # --- Row 4: Delete | 0 | Submit ---
    builder.button(text="⬅️ Delete", callback_data=OTP_DELETE_CB)
    builder.button(text="0",         callback_data=f"{OTP_DIGIT_PREFIX}0")
    builder.button(text="✅ Submit", callback_data=OTP_SUBMIT_CB)

    # The first 12 buttons (9 digits + Delete + 0 + Submit) should
    # be laid out 3 per row.
    builder.adjust(3, 3, 3, 3)

    # --- Row 5: Cancel (full width) ---
    # Adding it AFTER adjust() keeps it on its own row because
    # the previous row is already "complete" (3 buttons).
    builder.button(text="❌ Cancel", callback_data=OTP_CANCEL_CB)

    return builder.as_markup()


def get_empty_otp_kb() -> InlineKeyboardMarkup:
    """
    Return an empty inline keyboard.

    Useful when editing a message after submission/cancellation —
    pass this as `reply_markup=` to remove all buttons cleanly.
    """
    return InlineKeyboardBuilder().as_markup()