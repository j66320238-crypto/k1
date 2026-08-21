# worker_bot/modules/afk.py
"""
AFK (Away From Keyboard) Module for the Telegram Userbot.

Commands:
    .afk [reason]  — go AFK (auto-replies to mentions & DMs)
    .back          — return from AFK

Features:
    • Auto-reply to anyone who mentions you or DMs you while AFK.
    • Shows how long you've been away when you return.
    • Cooldown — max one auto-reply per user per 60s (no spam).
    • Ignores bots and service messages.
    • Persisted to afk_data.json so AFK survives a restart.
"""

import os
import json
import time
import asyncio
import datetime

from telethon import events
from telethon.errors import FloodWaitError

DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "afk_data.json"
)

REPLY_COOLDOWN = 60  # seconds between auto-replies to the same user

COMMANDS = {
    "description": "AFK — Away From Keyboard",
    "commands": [
        (".afk [reason]", "go AFK, auto-reply to mentions/DMs"),
        (".back", "return from AFK (shows away time)"),
    ],
}


def _load() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _fmt_dur(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def register(client):
    state = _load()
    # {user_id: last_reply_ts}
    last_replied: dict = {}

    if not hasattr(client, "stop_processes"):
        client.stop_processes = {}

    # ---- .afk [reason] ----
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.afk(?:\s+(.*))?$"))
    async def _afk_on(event):
        reason = (event.pattern_match.group(1) or "").strip() or "I'm busy right now."
        state["afk"] = True
        state["reason"] = reason
        state["since"] = time.time()
        _save(state)
        await event.edit(
            f"😴 **AFK mode ON**\n"
            f"📝 Reason: **{reason}**\n"
            f"⏰ Since: `{datetime.datetime.now():%Y-%m-%d %H:%M:%S}`\n"
            f"↩️ Send `.back` when you return."
        )

    # ---- .back ----
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.back$"))
    async def _afk_off(event):
        if not state.get("afk"):
            return await event.edit("ℹ️ You are not AFK.")
        since = state.get("since")
        dur = _fmt_dur(time.time() - since) if since else "unknown"
        state.clear()
        _save(state)
        await event.edit(f"✅ **Welcome back!** You were AFK for `{dur}`.")

    # ---- Auto-reply listener ----
    @client.on(events.NewMessage(incoming=True))
    async def _afk_listener(event):
        if not state.get("afk"):
            return
        try:
            if event.is_private:
                pass  # always reply in DMs
            else:
                # In groups, only reply when we are mentioned
                text = (event.raw_text or "").lower()
                me = await client.get_me()
                mentioned = (
                    f"@{me.username.lower()}" in text
                    if me.username
                    else False
                )
                if not mentioned:
                    return

            sender = await event.get_sender()
            if sender is None or getattr(sender, "bot", False) or getattr(sender, "verified", False):
                return

            uid = event.sender_id
            now = time.time()
            if now - last_replied.get(uid, 0) < REPLY_COOLDOWN:
                return
            last_replied[uid] = now

            since = state.get("since")
            away = _fmt_dur(now - since) if since else "a while"
            reason = state.get("reason", "I'm busy right now.")

            await event.reply(
                f"😴 **Owner is AFK** — away for `{away}`.\n"
                f"📝 _{reason}_\n"
                f"📌 He'll reply as soon as he's back."
            )
        except FloodWaitError as fw:
            await asyncio.sleep(fw.seconds + 1)
        except Exception:
            pass  # never crash the listener
