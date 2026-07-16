"""
worker_bot/core.py
------------------
Core engine of the Telegram Userbot.

Responsibilities:
    • Initialize the Telethon client using a String Session.
    • Provide a flood-wait-resilient decorator.
    • Dynamically load command modules from the `modules/` directory.
    • Maintain a global registry of long-running tasks (spam/raid) that
      can be cancelled via the built-in `.stop` command.
    • Print a premium ASCII banner on boot.

Target: Telethon v1.x  •  Runtime: Python 3.10+  •  Platform: SSH/Linux
"""

import os
import sys
import asyncio
import importlib
from pathlib import Path
from functools import wraps
from typing import Any, Callable, Dict, Optional

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession  # Fix 1: Imported StringSession


# ─────────────────────────────────────────────────────────────────────
# 1.  ENVIRONMENT / CONFIG
# ─────────────────────────────────────────────────────────────────────
API_ID: int        = int(os.environ.get("API_ID", "0") or 0)
API_HASH: str      = os.environ.get("API_HASH", "")
SESSION_STRING: str = os.environ.get("SESSION_STRING", "")

if not (API_ID and API_HASH and SESSION_STRING):
    raise RuntimeError(
        "Missing environment variables. "
        "Ensure API_ID, API_HASH and SESSION_STRING are exported."
    )


# ─────────────────────────────────────────────────────────────────────
# 2.  TELETHON CLIENT
# ─────────────────────────────────────────────────────────────────────
client = TelegramClient(
    session=StringSession(SESSION_STRING),  # Fix 1: Wrapped string in StringSession
    api_id=API_ID,
    api_hash=API_HASH,
    connection_retries=None,   # retry forever on transient network drops
    retry_delay=1,
    auto_reconnect=True,
    request_retries=5,
    flood_sleep_threshold=60   # Telethon auto-sleeps short FloodWaits
)


# ─────────────────────────────────────────────────────────────────────
# 3.  GLOBAL TASK REGISTRY  (for spam/raid-style long-running loops)
# ─────────────────────────────────────────────────────────────────────
# key   -> human-readable task name (e.g. "spam_12345")
# value -> asyncio.Task object that can be cancelled
stop_processes: Dict[str, asyncio.Task] = {}


def register_stop_task(name: str, task: asyncio.Task) -> None:
    """Add a running task to the registry so `.stop` can kill it later."""
    stop_processes[name] = task


def unregister_stop_task(name: str) -> None:
    """Remove a completed/finished task from the registry."""
    stop_processes.pop(name, None)


# ─────────────────────────────────────────────────────────────────────
# 4.  FLOOD-WAIT-RESILIENT DECORATOR
# ─────────────────────────────────────────────────────────────────────
def flood_safe(func: Callable[..., Any], max_retries: int = 5) -> Callable[..., Any]:
    """
    Wraps an *async* function so that a `FloodWaitError` no longer crashes
    the userbot. When raised, the wrapper sleeps the requested seconds
    (+1s safety buffer) and retries. After `max_retries` consecutive
    flood-waits the original error is re-raised.

    Usage:
        @flood_safe
        async def send_spam(chat, msg):
            await client.send_message(chat, msg)
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        attempt = 0
        while True:
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                attempt += 1
                if attempt > max_retries:
                    print(f"[FloodSafe] Giving up after {max_retries} retries.")
                    raise
                wait = e.seconds + 1
                print(
                    f"[FloodSafe] FloodWait {e.seconds}s → "
                    f"sleeping {wait}s (attempt {attempt}/{max_retries})"
                )
                await asyncio.sleep(wait)

    return wrapper


# ─────────────────────────────────────────────────────────────────────
# 5.  DYNAMIC MODULE LOADER
# ─────────────────────────────────────────────────────────────────────
MODULES_DIR: Path = Path(__file__).resolve().parent / "modules"


def load_modules(telethon_client: TelegramClient) -> None:
    """
    Walk the `modules/` directory, import every `*.py` file (except dunders
    and files prefixed with `_`), and call its `register(client)` function.
    """
    if not MODULES_DIR.exists():
        print(f"[Loader] Modules directory not found: {MODULES_DIR}")
        return

    # Make `modules` importable as a top-level package.
    parent_dir = str(MODULES_DIR.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Ensure the package marker exists.
    init_file = MODULES_DIR / "__init__.py"
    if not init_file.exists():
        init_file.touch()

    loaded, failed = 0, 0
    for module_path in sorted(MODULES_DIR.glob("*.py")):
        name = module_path.name
        if name.startswith("_") or name == "__init__.py":
            continue

        module_fqn = f"modules.{module_path.stem}"
        try:
            module = importlib.import_module(module_fqn)
            importlib.reload(module)  # pick up edits without restart

            if not hasattr(module, "register") or not callable(module.register):
                print(f"[Loader] ✗ {module_path.stem}: missing register()")
                failed += 1
                continue

            module.register(telethon_client)
            print(f"[Loader] ✓ Loaded module: {module_path.stem}")
            loaded += 1

        except Exception as exc:  # noqa: BLE001  (loader must not crash)
            print(f"[Loader] ✗ {module_path.stem}: {exc!r}")
            failed += 1

    print(f"[Loader] Done — loaded={loaded}  failed={failed}")


# ─────────────────────────────────────────────────────────────────────
# 6.  BUILT-IN  .stop  COMMAND
# ─────────────────────────────────────────────────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.stop(?:\s+(\S+))?$"))
async def _stop_command(event: events.NewMessage.Event) -> None:
    """
    Usage:
        .stop             → stop *all* running tasks
        .stop <task_id>   → stop one specific task
    """
    target: Optional[str] = event.pattern_match.group(1)

    if not stop_processes:
        await event.edit("❌ No running processes to stop.")
        return

    if target is None:
        stopped = 0
        for name, task in list(stop_processes.items()):
            if not task.done():
                task.cancel()
                stopped += 1
            stop_processes.pop(name, None)
        await event.edit(f"🛑 Stopped **{stopped}** running task(s).")
        return

    task = stop_processes.get(target)
    if task is None:
        await event.edit(f"❌ No task found with id `{target}`.")
        return

    if not task.done():
        task.cancel()
    stop_processes.pop(target, None)
    await event.edit(f"🛑 Stopped task `{target}`.")


# ─────────────────────────────────────────────────────────────────────
# 7.  ASCII BANNER
# ─────────────────────────────────────────────────────────────────────
BANNER: str = r"""
 __        __    _       _                 _   _           
 \ \      / /__ | |_ ___| |__   ___   __ _| |_| |_ _   _   
  \ \ /\ / / _ \| __/ __| '_ \ / _ \ / _` | __| __| | | |  
   \ V  V / (_) | || (__| | | | (_) | (_| | |_| |_| |_| |  
    \_/\_/ \___/ \__\___|_| |_|\___/ \__,_|\__|\__|\__, |  
                                                   |___/   
______________________________________________________________
        [ ✦ Userbot Online · String Session Auth ✦ ]
        [ Telethon v1.x · Async Engine Running      ]
        [ Type .help in any chat for commands       ]
______________________________________________________________
"""


# ─────────────────────────────────────────────────────────────────────
# 8.  MAIN ENTRY-POINT
# ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    """Async entry point: connect, verify session, load modules, run forever."""
    print(BANNER)

    # Fix 2: Use connect() instead of start() to prevent SSH hangs.
    # start() asks for phone/OTP interactively if the session is invalid.
    await client.connect()
    
    if not await client.is_user_authorized():
        print("[Auth] ❌ Invalid or Unauthorized Session String!")
        print("[Auth] Please regenerate the SESSION_STRING and try again.")
        await client.disconnect()
        return

    me = await client.get_me()
    print(
        f"[Auth] ✅ Logged in as "
        f"{me.first_name} (@{me.username})  [ID: {me.id}]"
    )

    load_modules(client)

    print("[Core] 🚀 Userbot is up and running. Press Ctrl+C to shut down.")
    
    # Block main task until the client disconnects
    await client.run_until_disconnected()


def run() -> None:
    """Synchronous wrapper used by `python -m worker_bot.core` or scripts."""
    try:
        # Fix 3: Replaced deprecated client.loop.run_until_complete with asyncio.run
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Core] Shutting down gracefully...")
    except Exception as exc:  # noqa: BLE001
        print(f"[Core] Fatal error: {exc!r}")
    finally:
        # Ensure any lingering tasks are cancelled before completely exiting
        for name, task in list(stop_processes.items()):
            if not task.done():
                task.cancel()
                print(f"[Core] Cancelled lingering task: {name}")


if __name__ == "__main__":
    run()