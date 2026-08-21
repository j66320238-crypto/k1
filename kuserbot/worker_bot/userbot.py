"""
worker_bot/userbot.py
=====================
Main entry point for the Premium Telegram Userbot (v3.1).

Designed to run on an SSH server via `nohup`:
    nohup python3 userbot.py > userbot.log 2>&1 &

STRICT ANTI-ERROR FEATURES:
1. Never calls client.start() to prevent SSH hangs. Uses connect() + is_user_authorized().
2. Uses StringSession properly wrapped.
3. Uses asyncio.run() at the bottom. No deprecated loop methods.
4. Dynamically scans and loads modules from the `modules/` directory.
5. Global `stop_processes` dict to track and kill background spam/raid tasks via `.stop`.
6. `@flood_safe` decorator to catch FloodWaitError and sleep automatically.
7. Premium ASCII banner on boot.
8. NEW v3.1:
   • ALL built-in commands are outgoing-only (strangers can't trigger them).
   • Auto-reconnect loop — network drops never kill the bot.
   • `.alive` shows real ping + uptime.
   • `.help` lists every loaded module's commands (via COMMANDS metadata).
   • Command registry collected from each module's `COMMANDS` dict.
"""

import os
import sys
import time
import asyncio
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
API_ID: int = int(os.getenv("API_ID", "0") or "0")
API_HASH: str = os.getenv("API_HASH", "")
SESSION_STRING: str = os.getenv("SESSION_STRING", "")

BOT_VERSION: str = "3.1.0"
MODULES_DIR: Path = Path(__file__).resolve().parent / "modules"
START_TIME: float = time.time()


# ============================================================================
# GLOBAL STATE
# ============================================================================
# Tracks every running background task (spam/raid/animation/etc.) so the
# built-in `.stop` command can cancel them by name — or all at once.
stop_processes: dict = {}

# {module_name: {"description": str, "commands": [(cmd, help), ...]}}
command_registry: dict = {}


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
║   ██║   ██║██║   ██║██║   ██║   ██║   ██║██████╔╝█████╗  ██████╔║    ║
║   ██║   ██║██║   ██║██║   ██║   ██║   ██║██╔══██╗██╔══╝  ██╔══██╗    ║
║   ╚██████╔╝╚██████╔╝██║   ██║   ╚██████╔╝██║  ██║███████╗██║  ██║    ║
║    ╚═════╝  ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝    ║
║                                                                      ║
║          >>  Premium Userbot v{ver}  │  Telethon Edition  <<         ║
║          >>  Booted: {ts}                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""


def print_banner() -> None:
    """Print the boot banner to stdout (captured by nohup into the log file)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_line = ts.ljust(20)
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
    Scan `directory` for `*.py` files (skipping underscore-prefixed ones),
    import each, and call its `register(client)` function if present.

    If a module exposes a `COMMANDS` dict, it is merged into the global
    command registry so the built-in `.help` can list everything.
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

                # Merge optional command metadata for `.help`
                meta = getattr(module, "COMMANDS", None)
                if isinstance(meta, dict):
                    command_registry[mod_name] = meta
            else:
                log.warning("  !  Skipped (no register fn): %s", mod_name)

        except Exception as e:
            log.error("  ✗  Failed to load %s: %s", mod_name, e, exc_info=True)

    return loaded


# ============================================================================
# BUILT-IN COMMANDS (always available, even with zero modules)
# ============================================================================
def _fmt_uptime(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m {s}s")
    return " ".join(parts)


def register_builtin_commands(client: TelegramClient) -> None:
    """Register core commands: `.stop`, `.tasks`, `.alive`, `.help`.

    NOTE: every built-in is OUTGOING-ONLY so other people in a chat can
    never trigger (or stop) your tasks.
    """

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stop(?:\s+(\S+))?$"))
    async def _stop_handler(event):
        """
        `.stop`          → cancel ALL tracked background tasks
        `.stop <name>`   → cancel one specific task by its key
        """
        if not stop_processes:
            return await event.edit("⏹  No active tasks to stop.")

        target = event.pattern_match.group(1)

        if target:
            task = stop_processes.get(target)
            if task is None:
                return await event.edit(f"⚠  No task named `{target}`.")
            if task.done():
                stop_processes.pop(target, None)
                return await event.edit(f"ℹ  `{target}` already finished.")
            task.cancel()
            stop_processes.pop(target, None)
            return await event.edit(f"⏹  Stopped task: `{target}`")

        # No name → stop everything
        stopped = 0
        for name, task in list(stop_processes.items()):
            if not task.done():
                task.cancel()
                stopped += 1
        stop_processes.clear()
        await event.edit(f"⏹  Stopped **{stopped}** active task(s).")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.tasks$"))
    async def _tasks_handler(event):
        """List all currently tracked background tasks."""
        if not stop_processes:
            return await event.edit("📭  No active tasks.")

        lines = ["**Active Tasks:**", ""]
        for name, task in stop_processes.items():
            status = "✅ done" if task.done() else "🔄 running"
            lines.append(f"• `{name}` — {status}")
        await event.edit("\n".join(lines))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.alive$"))
    async def _alive_handler(event):
        """Health-check / heartbeat with real ping & uptime."""
        t0 = datetime.now()
        me = await client.get_me()
        ping = (datetime.now() - t0).total_seconds() * 1000
        await event.edit(
            f"🤖  **Premium Userbot — Alive**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Version:**  `{BOT_VERSION}`\n"
            f"**User:**     {me.first_name} (@{me.username or 'n/a'})\n"
            f"**ID:**       `{me.id}`\n"
            f"**Tasks:**    {len(stop_processes)} active\n"
            f"**Uptime:**   {_fmt_uptime(time.time() - START_TIME)}\n"
            f"**Ping:**     `{ping:.0f} ms`"
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.help$"))
    async def _help_handler(event):
        """Full command index built from loaded modules."""
        lines = [
            "📖  **Premium Userbot — Help**",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "🛠  **Core**",
            "• `.alive` — heartbeat + ping + uptime",
            "• `.tasks` — list background tasks",
            "• `.stop` / `.stop <name>` — kill tasks",
            "• `.help` — this message",
            "",
        ]
        if command_registry:
            for mod, meta in sorted(command_registry.items()):
                title = meta.get("description", mod.title())
                lines.append(f"📦  **{title}**")
                for cmd, desc in meta.get("commands", []):
                    lines.append(f"• `{cmd}` — {desc}")
                lines.append("")
        else:
            lines.append("_Modules loaded without command metadata._")
            lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        await event.edit("\n".join(lines), link_preview=False)

    log.info("Built-in commands registered: .stop  .tasks  .alive  .help")


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
    try:
        session_obj = StringSession(SESSION_STRING)
    except ValueError:
        log.critical(
            "SESSION_STRING is malformed (not a valid Telethon string "
            "session). Regenerate it and try again."
        )
        sys.exit(1)

    client = TelegramClient(
        session=session_obj,
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
    client.flood_safe = flood_safe
    client.command_registry = command_registry

    # ---- Connect WITHOUT interactive prompts (no SSH hang) ----
    log.info("Connecting to Telegram servers...")
    await client.connect()

    if not await client.is_user_authorized():
        log.critical(
            "Session is NOT authorised. Regenerate SESSION_STRING and try again."
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

    # ---- Run forever (with auto-reconnect on network drops) ----
    log.info("🚀  Userbot is online.  (Ctrl+C to shut down.)")
    try:
        while True:
            try:
                await client.run_until_disconnected()
                break  # clean disconnect (e.g. user logged out)
            except ConnectionError as exc:
                log.warning("Connection dropped (%s) — reconnecting...", exc)
                await asyncio.sleep(3)
                try:
                    await client.connect()
                except Exception as retry_exc:
                    log.error("Reconnect failed: %s", retry_exc)
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
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
