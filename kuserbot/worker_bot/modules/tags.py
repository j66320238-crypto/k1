# worker_bot/modules/tags.py
"""
Mass-tagging module for the Telegram Userbot.

Provides:
    .tagall <text>   - Tag every member of the current chat in batches of 5.
    .onetag <text>   - Tag every member of the current chat strictly one-by-one.
    .admins <text>   - Tag every admin of the current chat (single message).
    .cancel / .tagstop - Cancel any running tagging task.

This module is loaded dynamically by `userbot.py` via the `register(client)`
entry point.  No globals, no circular imports.
"""

import asyncio

from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.types import ChannelParticipantsAdmins


# --------------------------------------------------------------------------- #
#  Module-level tunables
# --------------------------------------------------------------------------- #
TAG_DELAY    = 2   # seconds between successive tag messages (anti-ban)
BATCH_SIZE   = 5   # users per message in `.tagall`
TAG_KEY_PREFIX = "tag_"


def register(client):
    """Register all tag commands on the supplied Telethon client."""

    # ------------------------------------------------------------------ #
    #  Small helpers
    # ------------------------------------------------------------------ #
    def _key(event_id: str) -> str:
        return f"{TAG_KEY_PREFIX}{event_id}"

    def _mention(user) -> str:
        """Return an HTML mention string for any user object."""
        if getattr(user, "username", None):
            return f"@{user.username}"
        name = (getattr(user, "first_name", None) or "User").strip() or "User"
        return f'<a href="tg://user?id={user.id}">{name}</a>'

    def _alive(event_id: str) -> bool:
        """True if the tagging task should keep running."""
        return client.stop_processes.get(_key(event_id)) is not None

    async def _safe_send(chat, text: str):
        """Send a message, sleeping through any FloodWaitError."""
        try:
            await client.send_message(chat, text, parse_mode="html")
        except FloodWaitError as fw:
            await asyncio.sleep(fw.seconds + 1)
            await client.send_message(chat, text, parse_mode="html")

    async def _gather_users(chat, admins_only: bool = False):
        """Fetch participants (optionally admins) and filter dead/bot accounts."""
        if admins_only:
            users = await client.get_participants(
                chat, filter=ChannelParticipantsAdmins
            )
        else:
            users = await client.get_participants(chat)
        return [u for u in users if not u.deleted and not getattr(u, "bot", False)]

    # ------------------------------------------------------------------ #
    #  .tagall
    # ------------------------------------------------------------------ #
    async def _tagall_task(event, text: str):
        try:
            chat = await event.get_input_chat()
            users = await _gather_users(chat)
            total = len(users)
            sent  = 0

            for i in range(0, total, BATCH_SIZE):
                if not _alive(event.id):
                    break

                batch    = users[i:i + BATCH_SIZE]
                mentions = " ".join(_mention(u) for u in batch)
                msg      = f"{text}\n{mentions}" if text else mentions

                await _safe_send(chat, msg)
                sent += len(batch)
                await asyncio.sleep(TAG_DELAY)

            await event.reply(
                f"✅ **tagall** finished — tagged `{sent}/{total}` users."
            )
        except asyncio.CancelledError:
            await event.reply("🛑 **tagall** cancelled.")
            raise
        except Exception as e:  # noqa: BLE001
            await event.reply(f"❌ **tagall** error: `{e}`")
        finally:
            client.stop_processes.pop(_key(event.id), None)

    @client.on(events.NewMessage(pattern=r"^\.tagall(?:\s+(.*))?$"))
    @client.flood_safe
    async def tagall_handler(event):
        if event.is_private:
            await event.reply("⚠️ Use `.tagall` inside a group or channel.")
            return
        if _key(event.id) in client.stop_processes:
            await event.reply("⚠️ A tagging task is already running here.")
            return

        text = (event.pattern_match.group(1) or "").strip()
        task = asyncio.create_task(_tagall_task(event, text))
        client.stop_processes[_key(event.id)] = task

        await event.reply(
            f"📢 **tagall** started\n"
            f"• Batch size: `{BATCH_SIZE}`\n"
            f"• Delay: `{TAG_DELAY}s`\n"
            f"• Message: `{text or '(none)'}`"
        )

    # ------------------------------------------------------------------ #
    #  .onetag
    # ------------------------------------------------------------------ #
    async def _onetag_task(event, text: str):
        try:
            chat = await event.get_input_chat()
            users = await _gather_users(chat)
            total = len(users)
            sent  = 0

            for u in users:
                if not _alive(event.id):
                    break

                mention = _mention(u)
                msg     = f"{text}\n{mention}" if text else mention

                await _safe_send(chat, msg)
                sent += 1
                await asyncio.sleep(TAG_DELAY)

            await event.reply(
                f"✅ **onetag** finished — tagged `{sent}/{total}` users."
            )
        except asyncio.CancelledError:
            await event.reply("🛑 **onetag** cancelled.")
            raise
        except Exception as e:  # noqa: BLE001
            await event.reply(f"❌ **onetag** error: `{e}`")
        finally:
            client.stop_processes.pop(_key(event.id), None)

    @client.on(events.NewMessage(pattern=r"^\.onetag(?:\s+(.*))?$"))
    @client.flood_safe
    async def onetag_handler(event):
        if event.is_private:
            await event.reply("⚠️ Use `.onetag` inside a group or channel.")
            return
        if _key(event.id) in client.stop_processes:
            await event.reply("⚠️ A tagging task is already running here.")
            return

        text = (event.pattern_match.group(1) or "").strip()
        task = asyncio.create_task(_onetag_task(event, text))
        client.stop_processes[_key(event.id)] = task

        await event.reply(
            f"📢 **onetag** started\n"
            f"• Mode: `one-by-one`\n"
            f"• Delay: `{TAG_DELAY}s`\n"
            f"• Message: `{text or '(none)'}`"
        )

    # ------------------------------------------------------------------ #
    #  .admins
    # ------------------------------------------------------------------ #
    async def _admins_task(event, text: str):
        try:
            chat   = await event.get_input_chat()
            admins = await _gather_users(chat, admins_only=True)

            if not admins:
                await event.reply("⚠️ No admins found in this chat.")
                return

            mentions = " ".join(_mention(a) for a in admins)
            msg      = f"{text}\n{mentions}" if text else mentions

            await _safe_send(chat, msg)
            await event.reply(f"✅ Tagged `{len(admins)}` admin(s).")
        except asyncio.CancelledError:
            await event.reply("🛑 **admins** cancelled.")
            raise
        except Exception as e:  # noqa: BLE001
            await event.reply(f"❌ **admins** error: `{e}`")
        finally:
            client.stop_processes.pop(_key(event.id), None)

    @client.on(events.NewMessage(pattern=r"^\.admins(?:\s+(.*))?$"))
    @client.flood_safe
    async def admins_handler(event):
        if event.is_private:
            await event.reply("⚠️ Use `.admins` inside a group or channel.")
            return
        if _key(event.id) in client.stop_processes:
            await event.reply("⚠️ A tagging task is already running here.")
            return

        text = (event.pattern_match.group(1) or "").strip()
        task = asyncio.create_task(_admins_task(event, text))
        client.stop_processes[_key(event.id)] = task

        await event.reply("📢 Tagging admins…")

    # ------------------------------------------------------------------ #
    #  .cancel / .tagstop
    # ------------------------------------------------------------------ #
    @client.on(events.NewMessage(pattern=r"^\.tagstop$|^\.cancel$"))
    @client.flood_safe
    async def cancel_handler(event):
        keys = [k for k in list(client.stop_processes.keys())
                if k.startswith(TAG_KEY_PREFIX)]

        if not keys:
            await event.reply("ℹ️ No active tagging tasks.")
            return

        cancelled = 0
        for k in keys:
            task = client.stop_processes.pop(k, None)
            if task is not None and not task.done():
                task.cancel()
                cancelled += 1

        await event.reply(f"🛑 Cancelled `{cancelled}` tagging task(s).")

    # ------------------------------------------------------------------ #
    #  Diagnostics
    # ------------------------------------------------------------------ #
    client._tg_modules = getattr(client, "_tg_modules", {})
    client._tg_modules["tags"] = {
        "commands": [".tagall", ".onetag", ".admins", ".cancel", ".tagstop"],
        "version": "1.0",
    }