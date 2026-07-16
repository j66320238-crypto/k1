# worker_bot/modules/antipm.py
"""
Anti-PM (PM Guard) module for the Telegram Userbot.

Handles:
  - Toggling PM Guard on / off
  - Customizable warning and block messages
  - Configurable message limit before blocking
  - Approve / disapprove users
  - Persistent storage via antipm_data.json

This module is designed to be loaded dynamically by userbot.py via
``importlib`` and ``module.register(client)``.
"""

import asyncio
import json
import os

from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import BlockRequest


# ---------------------------------------------------------------------------
#  Persistence helpers  (module-level, no client dependency → no circular import)
# ---------------------------------------------------------------------------

DATA_FILE = "antipm_data.json"

_DEFAULT_DATA = {
    "enabled": False,
    "limit": 3,
    "pmmsg": (
        "Hello! This inbox is protected by PM Guard.\n"
        "Please wait for the owner to approve you.\n"
        "Sending further messages before approval may result in a block."
    ),
    "blockmsg": "You have exceeded the message limit and have been blocked.",
    "approved": {},   # { "user_id": "Display Name" }
    "counts":   {},   # { "user_id": int }
    "warned":   {},   # { "user_id": true }
}


def _deep_copy_defaults():
    return {
        k: (v.copy() if isinstance(v, dict) else v)
        for k, v in _DEFAULT_DATA.items()
    }


def _load_data():
    """Load persisted data, merging with defaults so every key always exists."""
    if not os.path.exists(DATA_FILE):
        return _deep_copy_defaults()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        merged = _deep_copy_defaults()
        for key in ("enabled", "limit", "pmmsg", "blockmsg"):
            if key in raw:
                merged[key] = raw[key]
        for key in ("approved", "counts", "warned"):
            if isinstance(raw.get(key), dict):
                merged[key].update(raw[key])
        return merged
    except (json.JSONDecodeError, OSError, TypeError):
        return _deep_copy_defaults()


def _save_data(data):
    """Best-effort synchronous save (file is tiny)."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ---------------------------------------------------------------------------
#  Module entry-point
# ---------------------------------------------------------------------------

def register(client):
    """
    Register all Anti-PM commands and the incoming-DM listener on *client*.

    No global ``client`` is used — everything is a closure over the
    ``client`` argument, so the module can be loaded / unloaded cleanly.
    """

    data = _load_data()            # shared mutable state for all handlers
    _state = {"me_id": None}       # tiny cache for our own user id

    def save():
        _save_data(data)

    async def _get_me_id(event):
        """Return our own user id, caching it after the first call."""
        if _state["me_id"] is None:
            try:
                me = await event.client.get_me()
                _state["me_id"] = me.id
            except Exception:
                return None
        return _state["me_id"]

    # ==================================================================
    #  Commands
    # ==================================================================

    # ---- .pmguard on | off ----
    @client.on(events.NewMessage(pattern=r"^\.pmguard(?:\s+(on|off))?$"))
    @client.flood_safe
    async def pmguard_toggle(event):
        if not event.is_private:
            return
        try:
            arg = event.pattern_match.group(1)
            if arg is None:
                state = "ON" if data["enabled"] else "OFF"
                await event.reply(
                    f"**PM Guard:** {state}\n\n"
                    "Usage: `.pmguard on` / `.pmguard off`"
                )
                return
            arg = arg.lower()
            if arg == "on":
                data["enabled"] = True
                save()
                await event.reply("✅ **PM Guard enabled.**")
            elif arg == "off":
                data["enabled"] = False
                save()
                await event.reply("❌ **PM Guard disabled.**")
        except Exception:
            pass

    # ---- .setpmmsg <text> ----
    @client.on(events.NewMessage(pattern=r"^\.setpmmsg(?:\s+(.*))?$"))
    @client.flood_safe
    async def set_pmmsg(event):
        if not event.is_private:
            return
        try:
            text = event.pattern_match.group(1)
            if not text or not text.strip():
                await event.reply(
                    f"**Current PM warning message:**\n\n{data['pmmsg']}\n\n"
                    "Usage: `.setpmmsg <text>`"
                )
                return
            data["pmmsg"] = text.strip()
            save()
            await event.reply("✅ **PM warning message updated.**")
        except Exception:
            pass

    # ---- .setblockmsg <text> ----
    @client.on(events.NewMessage(pattern=r"^\.setblockmsg(?:\s+(.*))?$"))
    @client.flood_safe
    async def set_blockmsg(event):
        if not event.is_private:
            return
        try:
            text = event.pattern_match.group(1)
            if not text or not text.strip():
                await event.reply(
                    f"**Current block message:**\n\n{data['blockmsg']}\n\n"
                    "Usage: `.setblockmsg <text>`"
                )
                return
            data["blockmsg"] = text.strip()
            save()
            await event.reply("✅ **Block message updated.**")
        except Exception:
            pass

    # ---- .setlimit <number> ----
    @client.on(events.NewMessage(pattern=r"^\.setlimit(?:\s+(\d+))?$"))
    @client.flood_safe
    async def set_limit(event):
        if not event.is_private:
            return
        try:
            num = event.pattern_match.group(1)
            if not num:
                await event.reply(
                    f"**Current limit:** {data['limit']}\n\n"
                    "Usage: `.setlimit <number>`"
                )
                return
            limit = int(num)
            if limit < 1:
                await event.reply("⚠️ Limit must be at least 1.")
                return
            data["limit"] = limit
            save()
            await event.reply(f"✅ **PM limit set to {limit} messages.**")
        except Exception:
            pass

    # ---- .approve / .a  (reply-based) ----
    @client.on(events.NewMessage(pattern=r"^\.(?:approve|a)(?:\s+(.*))?$"))
    @client.flood_safe
    async def approve_user(event):
        if not event.is_private:
            return
        try:
            if not event.is_reply:
                await event.reply("Reply to a user's message to approve them.")
                return
            reply = await event.get_reply_message()
            if not reply:
                await event.reply("⚠️ Could not fetch the replied message.")
                return

            target_id = reply.sender_id
            if target_id is None:
                await event.reply("⚠️ Could not determine the user.")
                return

            # Resolve a human-readable name (best-effort)
            sender = await reply.get_input_sender()
            name = str(target_id)
            try:
                entity = await event.client.get_entity(sender)
                first = getattr(entity, "first_name", "") or ""
                last  = getattr(entity, "last_name", "")  or ""
                name  = (f"{first} {last}").strip() or getattr(entity, "title", "") or name
            except Exception:
                pass

            sid = str(target_id)
            data["approved"][sid] = name
            data["counts"].pop(sid, None)
            data["warned"].pop(sid, None)
            save()
            await event.reply(f"✅ **Approved** {name} (`{target_id}`)")
        except Exception:
            pass

    # ---- .disapprove / .d  (reply-based) ----
    @client.on(events.NewMessage(pattern=r"^\.(?:disapprove|d)(?:\s+(.*))?$"))
    @client.flood_safe
    async def disapprove_user(event):
        if not event.is_private:
            return
        try:
            if not event.is_reply:
                await event.reply("Reply to a user's message to disapprove them.")
                return
            reply = await event.get_reply_message()
            if not reply:
                await event.reply("⚠️ Could not fetch the replied message.")
                return

            target_id = reply.sender_id
            if target_id is None:
                await event.reply("⚠️ Could not determine the user.")
                return

            sid = str(target_id)
            if sid in data["approved"]:
                name = data["approved"].pop(sid)
                save()
                await event.reply(f"❌ **Disapproved** {name} (`{target_id}`)")
            else:
                await event.reply("ℹ️ That user is not in the approved list.")
        except Exception:
            pass

    # ---- .approved ----
    @client.on(events.NewMessage(pattern=r"^\.approved$"))
    @client.flood_safe
    async def list_approved(event):
        if not event.is_private:
            return
        try:
            if not data["approved"]:
                await event.reply("ℹ️ No approved users yet.")
                return
            lines = ["**Approved Users:**\n"]
            for uid, name in data["approved"].items():
                lines.append(f"• {name} — `{uid}`")
            await event.reply("\n".join(lines))
        except Exception:
            pass

    # ==================================================================
    #  Incoming-DM Listener  (non-blocking, fast-exit for non-PM)
    # ==================================================================

    @client.on(events.NewMessage(incoming=True))
    @client.flood_safe
    async def antipm_listener(event):
        """
        PM Guard listener.

        Fast-exits for:
          - non-private chats
          - PM Guard disabled
          - self-messages
          - approved users

        For unapproved users:
          - increments message count
          - sends warning message once (per user)
          - blocks when count exceeds the limit
        """

        # ---- Fast exits (no I/O, no await needed) ----
        if not event.is_private:
            return
        if not data["enabled"]:
            return

        try:
            # Use InputChat / InputSender to avoid PeerIdError
            chat   = await event.get_input_chat()
            sender = await event.get_input_sender()
            if chat is None or sender is None:
                return

            sender_id = event.sender_id
            if sender_id is None:
                return

            # Don't guard self
            me_id = await _get_me_id(event)
            if me_id is not None and sender_id == me_id:
                return

            sid = str(sender_id)

            # Approved — do nothing
            if sid in data["approved"]:
                return

            # ---- Unapproved user: increment count ----
            count = data["counts"].get(sid, 0) + 1
            data["counts"][sid] = count
            limit = data["limit"]

            if count > limit:
                # ---- Exceeded limit: warn + block ----
                try:
                    if data["blockmsg"]:
                        await event.client.send_message(sender, data["blockmsg"])
                except Exception:
                    pass

                try:
                    # Fixed Telethon Syntax: get_input_entity() returns the correct type
                    await event.client(BlockRequest(id=await event.get_input_entity()))
                except Exception:
                    pass

                # Clean up tracking for this user
                data["counts"].pop(sid, None)
                data["warned"].pop(sid, None)
                save()

            else:
                # ---- Under limit: send warning once ----
                if not data["warned"].get(sid, False):
                    try:
                        if data["pmmsg"]:
                            await event.client.send_message(sender, data["pmmsg"])
                    except Exception:
                        pass
                    data["warned"][sid] = True
                save()

        except FloodWaitError as e:
            # Respect Telegram's rate-limit
            await asyncio.sleep(e.seconds + 1)
        except Exception:
            # Never let the listener crash the client
            pass