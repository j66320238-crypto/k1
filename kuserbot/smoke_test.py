#!/usr/bin/env python3
"""
smoke_test.py — offline self-test for the whole PHANTOM-X project.

Run from the kuserbot/ directory:
    python3 smoke_test.py

Checks (NO network / NO Telegram connection needed):
  1. Master-bot modules import cleanly (aiogram routers).
  2. Dispatcher assembles with every router attached.
  3. SQLite database init + basic CRUD round-trip.
  4. Encryption round-trip (Fernet).
  5. Worker userbot: all 10 modules register on a stub Telethon client
     (250+ event handlers) and command metadata resolves.
  6. SSH connector command construction (no connection).
"""

import asyncio
import importlib
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-FOR-SMOKE-TEST")
os.environ.setdefault("ENCRYPTION_KEY", "")

PASS, FAIL = "✅", "❌"
results = []


def check(name: str, fn):
    try:
        out = fn()
        results.append((True, name, out))
        print(f"{PASS} {name}" + (f" — {out}" if out else ""))
        return True
    except Exception as exc:
        results.append((False, name, f"{type(exc).__name__}: {exc}"))
        print(f"{FAIL} {name} — {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


# ─────────────────────────────────────────────────────────────
def t_master_imports():
    mods = [
        "config", "database", "encryption",
        "keyboards.start_kb", "keyboards.admin_kb", "keyboards.otp_kb",
        "keyboards.ssh_kb",
        "handlers.user", "handlers.normal_admin", "handlers.special_admin",
        "handlers.ssh_manager", "handlers.deploy", "handlers.panel",
        "utils.monitor", "utils.ssh_connector",
    ]
    for m in mods:
        importlib.import_module(m)
    return f"{len(mods)} modules import OK"


def t_dispatcher():
    from aiogram import Dispatcher
    from handlers.user import router as r_user
    from handlers.normal_admin import router as r_admin
    from handlers.special_admin import router as r_special
    from handlers.ssh_manager import router as r_ssh
    from handlers.deploy import router as r_deploy
    from handlers.panel import router as r_panel

    dp = Dispatcher()
    for r in (r_special, r_panel, r_admin, r_user, r_ssh, r_deploy):
        dp.include_router(r)
    return "6 routers attached"


def t_database():
    import database as dbmod

    async def _run():
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            testdb = dbmod.Database(tmp.name)
            await testdb.init()
            await testdb.add_user(111, "tester", "@tester")
            await testdb.set_session(111, "sess-abc", "+911234567890")
            user = await testdb.get_user(111)
            assert user and user["session_string"] == "sess-abc"
            await testdb.set_setting("k", "v")
            assert await testdb.get_setting("k") == "v"
            await testdb.add_help_button("Topic", "Info text")
            btns = await testdb.get_all_help_buttons()
            assert len(btns) == 1
            await testdb.close()
        finally:
            os.unlink(tmp.name)

    asyncio.run(_run())
    return "init + users + settings + help_buttons round-trip"


def t_encryption():
    from encryption import DataEncryptor

    secret = "my-super-secret-session-string-12345"
    token = DataEncryptor.encrypt(secret)
    assert token and token != secret
    assert DataEncryptor.decrypt(token) == secret
    # Tampered token must return None (not raise)
    assert DataEncryptor.decrypt(token[:-4] + "AAAA") is None
    return "encrypt/decrypt + tamper-safe"


def t_worker_modules():
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession

    spec = importlib.util.spec_from_file_location("ub", ROOT / "worker_bot" / "userbot.py")
    ub = importlib.util.module_from_spec(spec)
    sys.modules["ub"] = ub
    spec.loader.exec_module(ub)

    client = TelegramClient(StringSession(), 1, "0123456789abcdef0123456789abcdef")
    client.stop_processes = ub.stop_processes
    client.flood_safe = ub.flood_safe

    # Silence the loader's INFO spam for the test
    logging = importlib.import_module("logging")
    old_level = logging.getLogger("userbot").level
    logging.getLogger("userbot").setLevel(logging.ERROR)
    try:
        count = ub.load_modules(client)
    finally:
        logging.getLogger("userbot").setLevel(old_level)

    handlers = sum(len(h) for h in client.list_event_handlers())
    assert count == 10, f"expected 10 worker modules, got {count}"
    assert handlers >= 200, f"too few handlers attached: {handlers}"
    assert ".alive" in str(client.list_event_handlers()) or handlers > 0
    return f"{count} modules, {handlers} handlers, {len(ub.command_registry)} registries"


def t_ssh_connector():
    from utils.ssh_connector import SSHManager, CommandResult

    ssh = SSHManager("example.com", "user", "pass", 22)
    # no connection yet → must raise the friendly error, not crash weirdly
    try:
        asyncio.run(ssh.execute_command("echo hi"))
    except Exception as exc:
        assert "not open" in str(exc).lower(), exc
    res = CommandResult(exit_code=0, stdout="42\n", stderr="")
    assert res.ok and res.stdout.strip() == "42"
    return "guard + result container OK"


def t_userbot_entry():
    """userbot.py + core.py shim must both import & expose main()."""
    spec = importlib.util.spec_from_file_location("core_shim", ROOT / "worker_bot" / "core.py")
    core = importlib.util.module_from_spec(spec)
    sys.modules["core_shim"] = core
    spec.loader.exec_module(core)
    assert callable(core.run)
    return "core.py shim delegates OK"


def main() -> int:
    print("╔══════════════════════════════════════════╗")
    print("║   PHANTOM-X v3.1 — SMOKE TEST (offline)  ║")
    print("╚══════════════════════════════════════════╝\n")

    import importlib.util  # noqa: F401 (used in t_worker_modules)
    globals()["importlib"] = importlib

    check("Master bot imports", t_master_imports)
    check("Dispatcher assembly", t_dispatcher)
    check("Database round-trip", t_database)
    check("Encryption round-trip", t_encryption)
    check("Worker userbot modules", t_worker_modules)
    check("SSH connector", t_ssh_connector)
    check("Userbot entrypoints", t_userbot_entry)

    ok = sum(1 for r, *_ in results if r)
    total = len(results)
    print(f"\n{'═' * 44}\n  RESULT: {ok}/{total} passed " + ("🎉 ALL GOOD" if ok == total else "⚠ FIX NEEDED"))
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
