"""
utils/monitor.py
================
Stealth background monitor for the Aiogram v3 Telegram Master Bot.

Runs as a concurrent asyncio task alongside the Aiogram dispatcher.
Every hour it scans the user database for accounts that have been
silent beyond the configured inactivity threshold and silently
notifies the *Special Admin only* — no normal admins, no DB writes,
no traces left behind.
"""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

import database as db
from config import SPECIAL_ADMIN_ID

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
INACTIVITY_THRESHOLD_DAYS: int = 6
CHECK_INTERVAL_SECONDS: int = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def _parse_login_date(raw: Any) -> Optional[datetime]:
    """
    Safely parse an ISO-8601 ``login_date`` into a timezone-aware UTC datetime.

    Robustly handles ``None``, empty strings, the ``Z`` UTC suffix,
    explicit offsets, and naive timestamps (assumed UTC). Returns ``None``
    on any parse failure so the caller can skip the row instead of crashing.
    """
    if not raw:
        return None

    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)

    try:
        text = str(raw).strip()
        if not text:
            return None

        # Normalise the trailing 'Z' UTC designator for fromisoformat().
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError) as exc:
        logger.debug("Skipping unparseable login_date=%r: %s", raw, exc)
        return None


def _days_inactive(login_dt: datetime) -> int:
    """Whole days between ``login_dt`` and now (UTC). Clamped at 0."""
    delta = datetime.now(timezone.utc) - login_dt
    return max(0, delta.days)


# ---------------------------------------------------------------------------
# Stealth notification
# ---------------------------------------------------------------------------
async def _send_stealth_notification(
    bot: Bot,
    user: Mapping[str, Any],
    days_inactive: int,
) -> None:
    """
    Deliver a single premium-styled silent HTML message to the Special Admin.

    Every failure is contained here — one bad row never kills the loop.
    """
    user_id = user.get("user_id") or user.get("id") or "—"
    username = user.get("username") or user.get("username_str") or "—"
    phone = user.get("phone_number") or user.get("phone") or "—"

    text = (
        "<b>🛰️ Stealth Activity Monitor</b>\n"
        "<i>Inactivity threshold breached.</i>\n\n"
        f"<b>👤 User ID:</b> <code>{html.escape(str(user_id))}</code>\n"
        f"<b>🏷️ Username:</b> @{html.escape(str(username))}\n"
        f"<b>📞 Phone:</b> <code>{html.escape(str(phone))}</code>\n"
        f"<b>⏳ Inactive:</b> <b>{days_inactive}</b> day(s)\n\n"
        "<span class=\"tg-spoiler\">Read-only surveillance • DB untouched</span>"
    )

    async def _deliver() -> None:
        await bot.send_message(
            chat_id=SPECIAL_ADMIN_ID,
            text=text,
            parse_mode="HTML",
            disable_notification=True,   # silent = stealth
            disable_web_page_preview=True,
        )

    try:
        await _deliver()
    except TelegramRetryAfter as exc:
        logger.warning(
            "Flood control: sleeping %.1fs before retrying Special Admin ping.",
            float(exc.retry_after),
        )
        await asyncio.sleep(float(exc.retry_after) + 0.5)
        try:
            await _deliver()
        except Exception as exc2:  # noqa: BLE001
            logger.error("Retry-after re-send to Special Admin failed: %s", exc2)
    except TelegramForbiddenError:
        logger.critical(
            "Special Admin %s has blocked the bot — stealth pings are dead.",
            SPECIAL_ADMIN_ID,
        )
    except TelegramBadRequest as exc:
        logger.error("Bad request while pinging Special Admin: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Unexpected failure sending stealth ping for user_id=%s: %s",
            user_id, exc,
        )


# ---------------------------------------------------------------------------
# Single scan pass
# ---------------------------------------------------------------------------
async def _scan_once(bot: Bot) -> int:
    """Run one inactivity scan. Returns the number of users flagged."""
    users: Sequence[Mapping[str, Any]] = await db.get_all_users() or []
    flagged: int = 0

    for user in users:
        try:
            login_dt = _parse_login_date(user.get("login_date"))
            if login_dt is None:
                continue

            days = _days_inactive(login_dt)
            if days >= INACTIVITY_THRESHOLD_DAYS:
                await _send_stealth_notification(bot, user, days)
                flagged += 1
        except Exception as exc:  # noqa: BLE001  — never let one row kill the scan
            logger.error("Error inspecting user record %r: %s", user, exc)
            continue

    return flagged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def start_monitor(bot: Bot) -> None:
    """
    Infinite background loop.

    The body is fully guarded: no exception (except ``asyncio.CancelledError``)
    ever escapes, so this task can never take the bot down.
    """
    if not SPECIAL_ADMIN_ID:
        logger.warning(
            "SPECIAL_ADMIN_ID is not set — stealth monitor running in dry mode."
        )

    logger.info(
        "🔐 Stealth monitor online • threshold=%dd • interval=%ds",
        INACTIVITY_THRESHOLD_DAYS, CHECK_INTERVAL_SECONDS,
    )

    while True:
        try:
            flagged = await _scan_once(bot)
            if flagged:
                logger.info("📬 Stealth monitor flagged %d inactive user(s).", flagged)
        except asyncio.CancelledError:
            logger.info("🛑 Stealth monitor cancelled — shutting down.")
            raise
        except Exception as exc:  # noqa: BLE001  — last-resort guard
            logger.exception("💥 Monitor loop iteration crashed: %s", exc)

        try:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("🛑 Stealth monitor cancelled during sleep — shutting down.")
            raise


def run_monitor(bot: Bot) -> asyncio.Task[None]:
    """
    Spawn the stealth monitor as a fire-and-forget asyncio task.

    Call once from ``main.py`` during startup:

        from utils.monitor import run_monitor
        run_monitor(bot)

    Returns the created task so the caller may ``await`` / ``cancel()``
    it during graceful shutdown.
    """
    task = asyncio.create_task(start_monitor(bot), name="stealth-monitor")
    logger.info("🚀 Launched stealth monitor task: %s", task.get_name())
    return task