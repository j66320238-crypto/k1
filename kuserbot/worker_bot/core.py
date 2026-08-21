"""
worker_bot/core.py
------------------
COMPATIBILITY SHIM (v3.1).

Earlier this file contained a *second*, divergent Telethon loader that
never attached ``client.flood_safe`` / ``client.stop_processes`` — so every
module failed with AttributeError when started through it.

The single, canonical entry point is now ``userbot.py``.  This shim simply
delegates to it so that old docs / cron entries / systemd units using
``python -m worker_bot.core`` (or ``python core.py``) keep working:

    python3 userbot.py      # ← preferred
    python3 core.py         # ← also works (delegates)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Make sibling modules importable when run as a bare script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from userbot import main as _userbot_main  # noqa: E402

log = logging.getLogger("userbot.core")


def run() -> None:
    """Delegate to userbot.main() — kept for backward compatibility."""
    try:
        asyncio.run(_userbot_main())
    except KeyboardInterrupt:
        print("\n[Core] Shutting down gracefully...")
    except Exception as exc:  # noqa: BLE001
        log.critical("Fatal error: %s", exc, exc_info=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    if not (os.getenv("API_ID") and os.getenv("API_HASH") and os.getenv("SESSION_STRING")):
        print(
            "[Core] Missing API_ID / API_HASH / SESSION_STRING environment "
            "variables — cannot start."
        )
        raise SystemExit(1)
    run()
