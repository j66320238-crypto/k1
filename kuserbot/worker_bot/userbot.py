"""
worker_bot/userbot.py
=====================
Main entry point for the Premium Telegram Userbot.

Designed to run on an SSH server via `nohup`:
    nohup python -m worker_bot.userbot > userbot.log 2>&1 &

STRICT ANTI-ERROR FEATURES:
1. Never calls client.start() to prevent SSH hangs. Uses connect() + is_user_authorized().
2. Uses StringSession properly wrapped.
3. Uses asyncio.run() at the bottom. No deprecated loop methods.
4. Dynamically scans and loads modules from the `modules/` directory.
5. Global `stop_processes` dict to track and kill background spam/raid tasks via `.stop`.
6. `@flood_safe` decorator to catch FloodWaitError and sleep automatically.
7. Premium ASCII banner on boot.
"""

import os
import sys
import asyncio
import importlib
import importlib.util
import logging
from pathlib import Path
from functools import wraps
from datetime import datetime

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError


# ============================================================================
# CONFIGURATION (Loaded from environment variables)
# ============================================================================
API_ID: int        = int(os.getenv("API_ID", "0") or "0")
API_HASH: str      = os.getenv("API_HASH", "")
SESSION_STRING: str = os.getenv("SESSION_STRING", "")

BOT_VERSION: str  = "3.0.0"
MODULES_DIR: Path = Path(__file__).resolve().parent / "modules"


# ============================================================================
# GLOBAL STATE
# ============================================================================
# Tracks every running background task (spam/raid/bomb/etc.) so the built-in
# `.stop` command can cancel them by name — or all at once.
stop_processes: dict = {}


# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    format="%(asctime)s │ %(levelname)-7s │ %(name)-18s │ %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("userbot")


# ============================================================================
# ASCII BANNER
# ============================================================================
_BANNER = r"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ██╗   ██╗ ██████╗ ██╗████████╗ ██████╗ ██████╗ ███████╗██████╗     ║
║   ██║   ██║██╔═══██╗██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗    ║
║   ██║   ██║██║   ██║██║   ██║   ██║   ██║██████╔╝█████╗  ██████╔╝    ║
║   ██║   ██║██║   ██║██║   ██║   ██║   ██║██╔══██╗██╔══╝  ██╔══██╗    ║
║   ╚██████╔╝╚██████╔╝██║   ██║   ╚██████╔╝██║  ██║███████╗██║  ██║    ║
║    ╚═════╝  ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝    ║
║                                                                      ║
║            >>  Premium Userbot v{ver}  │  Telethon Edition  <<          ║
║            >>  Booted: {ts}                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

def print_banner() -> None:
    """Print the boot banner to stdout (captured by nohup into the log file)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # left-pad timestamp so the right border line stays aligned
    ts_line = ts.ljust(33)
    print(_BANNER.format(ver=BOT_VERSION, ts=ts_line))


# ============================================================================
# FLOOD-SAFE DECORATOR
# ============================================================================
def flood_safe(func):
    """
    Decorator that catches `FloodWaitError`, sleeps for the required number
    of seconds, then transparently retries the call. Non-flood exceptions
    are logged and swallowed (returns None) so one bad call can't kill an
    entire raid loop.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        while True:
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                log.warning(
                    "FloodWaitError in %s — sleeping %ds before retry...",
                    func.__name__, e.seconds,
                )
                await asyncio.sleep(e.seconds + 1)
                # loop back and retry
            except asyncio.CancelledError:
                # Propagate so `.stop` cancellations are honoured cleanly.
                log.info("Task %s cancelled via .stop", func.__name__)
                raise
            except Exception as e:
                log.error("[flood_safe] %s failed: %s", func.__name__, e, exc_info=True)
                return None
    return wrapper


# ============================================================================
# DYNAMIC MODULE LOADER
# ============================================================================
def load_modules(client: TelegramClient, directory: Path = MODULES_DIR) -> int:
    """
    Scan `directory` for `*.py` files (skipping dunder-prefixed ones),
    import each, and call its `register(client)` function if present.
    """
    if not directory.is_dir():
        log.warning("Modules directory not found: %s. Creating it...", directory)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return 0

    loaded = 0
    for file in sorted(directory.glob("*.py")):
        if file.name.startswith("_"):
            continue

        mod_name = file.stem
        full_name = f"userbot_modules.{mod_name}"

        try:
            # Use spec-based loading so we don't depend on package layout
            spec = importlib.util.spec_from_file_location(full_name, file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create spec for {file}")

            module = importlib.util.module_from_spec(spec)
            # Register in sys.modules *before* exec so intra-package imports resolve
            sys.modules[full_name] = module
            spec.loader.exec_module(module)

            register = getattr(module, "register", None)
            if callable(register):
                register(client)
                loaded += 1
                log.info("  ✓  Loaded module: %s", mod_name)
            else:
                log.warning("  !  Skipped (no register fn): %s", mod_name)

        except Exception as e:
            log.error("  ✗  Failed to load %s: %s", mod_name, e, exc_info=True)

    return loaded


# ============================================================================
# BUILT-IN COMMANDS (always available, even with zero modules)
# ============================================================================
def register_builtin_commands(client: TelegramClient) -> None:
    """Register core commands: `.stop`, `.tasks`, `.alive`."""

    @client.on(events.NewMessage(pattern=r"^\.stop(?:\s+(\S+))?$"))
    async def _stop_handler(event):
        """
        `.stop`          → cancel ALL tracked background tasks
        `.stop <name>`   → cancel one specific task by its key
        """
        if not stop_processes:
            return await event.reply("⏹  No active tasks to stop.")

        target = event.pattern_match.group(1)

        if target:
            task = stop_processes.get(target)
            if task is None:
                return await event.reply(f"⚠  No task named `{target}`.")
            if task.done():
                stop_processes.pop(target, None)
                return await event.reply(f"ℹ  `{target}` already finished.")
            task.cancel()
            stop_processes.pop(target, None)
            return await event.reply(f"⏹  Stopped task: `{target}`")

        # No name → stop everything
        stopped = 0
        for name, task in list(stop_processes.items()):
            if not task.done():
                task.cancel()
                stopped += 1
        stop_processes.clear()
        await event.reply(f"⏹  Stopped **{stopped}** active task(s).")

    @client.on(events.NewMessage(pattern=r"^\.tasks$"))
    async def _tasks_handler(event):
        """List all currently tracked background tasks."""
        if not stop_processes:
            return await event.reply("📭  No active tasks.")

        lines = ["**Active Tasks:**", ""]
        for name, task in stop_processes.items():
            status = "✅ done" if task.done() else "🔄 running"
            lines.append(f"• `{name}` — {status}")
        await event.reply("\n".join(lines))

    @client.on(events.NewMessage(pattern=r"^\.alive$"))
    async def _alive_handler(event):
        """Health-check / heartbeat."""
        me = await client.get_me()
        await event.reply(
            f"🤖  **Premium Userbot — Alive**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Version:**  `{BOT_VERSION}`\n"
            f"**User:**     {me.first_name} (@{me.username or 'n/a'})\n"
            f"**ID:**       `{me.id}`\n"
            f"**Tasks:**    {len(stop_processes)} active\n"
            f"**Ping:**     `{datetime.now():%H:%M:%S}`"
        )

    log.info("Built-in commands registered: .stop  .tasks  .alive")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
async def main() -> None:
    print_banner()

    # ---- Validate environment variables ----
    if not API_ID or not API_HASH or not SESSION_STRING:
        log.critical(
            "Missing environment variables. Export API_ID, API_HASH, and "
            "SESSION_STRING before launching."
        )
        sys.exit(1)

    # ---- Build the client (StringSession — no interactive login) ----
    client = TelegramClient(
        session=StringSession(SESSION_STRING),
        api_id=API_ID,
        api_hash=API_HASH,
        device_model="PremiumUserbot",
        system_version=BOT_VERSION,
        app_version=BOT_VERSION,
        lang_code="en",
        system_lang_code="en",
        connection_retries=None,   # retry forever
        retry_delay=1,
        request_retries=5,
        flood_sleep_threshold=60,  # auto-sleep short FloodWaits internally
    )

    # Expose shared utilities on the client so modules can grab them via
    # `client.stop_processes` / `client.flood_safe` without circular imports.
    client.stop_processes = stop_processes
    client.flood_safe     = flood_safe

    # ---- Connect WITHOUT interactive prompts (no SSH hang) ----
    log.info("Connecting to Telegram servers...")
    await client.connect()

    if not await client.is_user_authorized():
        log.critical(
            "Session is NOT authorised. Regenerate SESSION_STRING via "
            "`python -m worker_bot.gen_session` and try again."
        )
        await client.disconnect()
        sys.exit(1)

    me = await client.get_me()
    log.info(
        "✅  Authorised as: %s (@%s)  │  ID: %s",
        me.first_name, me.username or "n/a", me.id,
    )

    # ---- Register built-in commands ----
    register_builtin_commands(client)

    # ---- Load dynamic modules from ./modules ----
    log.info("Scanning modules directory: %s", MODULES_DIR)
    count = load_modules(client)
    log.info("Loaded %d module(s).", count)

    # ---- Run forever ----
    log.info("🚀  Userbot is online.  (Ctrl+C to shut down.)")
    try:
        await client.run_until_disconnected()
    finally:
        # Best-effort cleanup of any lingering tasks
        for name, task in list(stop_processes.items()):
            if not task.done():
                task.cancel()
        stop_processes.clear()
        await client.disconnect()
        log.info("Disconnected.  Goodbye! 👋")


# ============================================================================
# BOOTSTRAP — asyncio.run, NOT client.loop.run_until_complete
# ============================================================================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔  Shutdown requested (Ctrl+C).")
    except Exception as exc:
        log.critical("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)