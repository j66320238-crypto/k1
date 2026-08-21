#!/usr/bin/env python3
"""
worker_bot/gen_session.py
=========================
Generate a Telethon SESSION_STRING for the worker userbot.

Run LOCALLY or on your server (needs a terminal — it asks for phone+OTP):

    pip install telethon
    python3 worker_bot/gen_session.py

It prints a `SESSION_STRING=...` line you can:
  • paste into .env, or
  • export before starting the userbot:
        export API_ID=... API_HASH=... SESSION_STRING=...
        python3 worker_bot/userbot.py

NOTE: never share your session string — it IS your Telegram login.
"""

import asyncio
import os
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)


async def main() -> None:
    print("=" * 58)
    print("  PHANTOM-X — Session String Generator")
    print("=" * 58)

    api_id = os.getenv("API_ID") or _ask("API_ID (my.telegram.org): ")
    api_hash = os.getenv("API_HASH") or _ask("API_HASH: ")
    phone = _ask("Phone (international, e.g. +919876543210): ")

    if not (api_id.isdigit() and api_hash and phone.startswith("+")):
        print("❌ Invalid input — API_ID must be numeric & phone must start with '+'.")
        sys.exit(1)

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()

    print("\n⏳ Requesting login code…")
    await client.send_code_request(phone)
    code = _ask("Enter the login code (from Telegram app): ")

    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = _ask("2FA password: ")
        await client.sign_in(password=password)

    session_string = client.session.save()
    me = await client.get_me()
    await client.disconnect()

    print("\n" + "=" * 58)
    print(f"✅ Logged in as: {me.first_name} (@{me.username or 'n/a'})  [{me.id}]")
    print("=" * 58)
    print("YOUR SESSION STRING (keep it SECRET!):\n")
    print(session_string)
    print("\n" + "=" * 58)
    print("Use it like this:")
    print(f"  export API_ID={api_id} API_HASH={api_hash}")
    print(f"  export SESSION_STRING='{session_string[:20]}...{session_string[-10:]}'")
    print("  python3 worker_bot/userbot.py")
    print("=" * 58)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        sys.exit(1)
