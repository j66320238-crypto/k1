"""
config.py
---------
Configuration module for the Phantom-X Telegram Bot (Aiogram v3).

Responsibilities:
  • Load environment variables from a local `.env` file via python-dotenv.
  • Expose typed configuration constants used throughout the bot.
  • Provide default settings used to seed the SQLite `settings` table.
  • Perform a minimal startup sanity-check on critical values.

Usage:
    from config import BOT_TOKEN, API_ID, API_HASH, ADMIN_IDS, ...
"""

import os
from dotenv import load_dotenv


# ─────────────────────────────────────────────────────────────────────────────
# 1. Load environment variables from the .env file (if present)
# ─────────────────────────────────────────────────────────────────────────────
# `override=False` means real OS environment variables take precedence over
# values defined in the .env file — useful for Docker/CI deployments.
load_dotenv(override=False)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Telegram API credentials
# ─────────────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
API_HASH:  str = os.getenv("API_HASH", "").strip()

# API_ID must be an integer. If the value is missing or non-numeric, we fall
# back to 0 and warn — this keeps the module importable for tooling/scripts.
try:
    API_ID: int = int(os.getenv("API_ID", "0").strip())
except (TypeError, ValueError):
    print("⚠️  [config] Invalid API_ID in environment — expected an integer.")
    API_ID = 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Administrator user IDs
# ─────────────────────────────────────────────────────────────────────────────
def _parse_admin_ids(raw: str) -> list[int]:
    """
    Parse a comma-separated string of Telegram user IDs into a list of ints.

    Example:
        "123456789, 987654321"  ->  [123456789, 987654321]

    Invalid entries are skipped with a warning instead of crashing.
    """
    if not raw:
        return []

    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            print(f"⚠️  [config] Skipping invalid ADMIN_ID entry: '{part}'")
    return ids


ADMIN_IDS: list[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

# The primary/owner admin — always guaranteed full access.
SPECIAL_ADMIN_ID: int = 7839547993

# Make sure the special admin is always part of ADMIN_IDS (no duplicates).
if SPECIAL_ADMIN_ID not in ADMIN_IDS:
    ADMIN_IDS.append(SPECIAL_ADMIN_ID)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Filesystem paths
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH:          str = "phantom_bot.db"   # SQLite database file
SERVERS_JSON_PATH: str = "servers.json"   # SSH-managed server list (JSON)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Default settings (used to seed the DB `settings` table on first run)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS: dict[str, str] = {
    "force_join_link":     "",
    "support_link":        "",
    "welcome_text":        "Welcome to Phantom-X!",
    "welcome_photo":       "",
    "donate_qr":           "",
    "owner_username":      "zenindeveloper",
    "developer_username":  "botdeveloper08",
}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Startup sanity check
# ─────────────────────────────────────────────────────────────────────────────
# We intentionally do NOT raise/exit here so that tooling (linters, tests,
# migration scripts, etc.) can still import this module safely.
if not BOT_TOKEN:
    print(
        "⚠️  [config] WARNING: BOT_TOKEN is missing or empty!\n"
        "    Please define BOT_TOKEN=... in your .env file before starting the bot."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "BOT_TOKEN",
    "API_ID",
    "API_HASH",
    "ADMIN_IDS",
    "SPECIAL_ADMIN_ID",
    "DB_PATH",
    "SERVERS_JSON_PATH",
    "DEFAULT_SETTINGS",
]