# worker_bot/modules/raid.py
"""
Raid module for the Telegram Userbot.
Dynamically loaded by userbot.py via ``register(client)``.
"""

import asyncio
import json
import os
from telethon import events
from telethon.errors import FloodWaitError

# ─── Module-level constants & state ───────────────────────────────────────

RAID_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "raid_data.json",
)

# In-memory store of user IDs with active reply-raid.
active_reply_raids = []


# ─── File I/O helpers ─────────────────────────────────────────────────────

def _load_raid_text():
    """Return saved raid text or ``None``."""
    if not os.path.exists(RAID_DATA_FILE):
        return None
    try:
        with open(RAID_DATA_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("raid_text")
    except (json.JSONDecodeError, OSError):
        return None


def _save_raid_text(text):
    """Persist raid text.  Return ``True`` on success."""
    try:
        with open(RAID_DATA_FILE, "w", encoding="utf-8") as fh:
            json.dump({"raid_text": text}, fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def _delete_raid_text():
    """Remove the raid-data file.  Return ``True`` on success."""
    if not os.path.exists(RAID_DATA_FILE):
        return True
    try:
        os.remove(RAID_DATA_FILE)
        return True
    except OSError:
        return False


def _escape_html(text):
    """Escape HTML special characters for safe display inside ``<code>``."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def _build_mention(user_id, display_name):
    """Build an HTML ``<a>`` mention tag."""
    name = display_name or "User"
    return f'<a href="tg://user?id={user_id}">{name}</a>'


# ─── Module entry-point ───────────────────────────────────────────────────

def register(client):
    """Register all raid commands on the given Telethon client."""

    # ── .setraid <text> ──────────────────────────────────────────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.setraid\s+([\s\S]+)$"))
    @client.flood_safe
    async def setraid_handler(event):
        """Save custom raid text to raid_data.json."""
        text = event.pattern_match.group(1).strip()
        if not text:
            await event.edit(
                "<b>Usage:</b> <code>.setraid &lt;text&gt;</code>",
                parse_mode="html",
            )
            return
        if _save_raid_text(text):
            await event.edit(
                "✅ <b>Raid text saved successfully.</b>",
                parse_mode="html",
            )
        else:
            await event.edit(
                "❌ <b>Failed to save raid text.</b>",
                parse_mode="html",
            )

    # ── .listraid ────────────────────────────────────────────────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.listraid$"))
    @client.flood_safe
    async def listraid_handler(event):
        """Display the currently saved raid text."""
        text = _load_raid_text()
        if text:
            safe = _escape_html(text)
            await event.edit(
                f"📝 <b>Current Raid Text:</b>\n\n<code>{safe}</code>",
                parse_mode="html",
            )
        else:
            await event.edit(
                "❌ <b>No raid text is currently saved.</b>\n"
                "Use <code>.setraid &lt;text&gt;</code> to set one.",
                parse_mode="html",
            )

    # ── .delraid / .clrraid ──────────────────────────────────────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(?:delraid|clrraid)$"))
    @client.flood_safe
    async def delraid_handler(event):
        """Delete the saved raid text."""
        if _delete_raid_text():
            await event.edit("✅ <b>Raid text deleted.</b>", parse_mode="html")
        else:
            await event.edit("❌ <b>Failed to delete raid text.</b>", parse_mode="html")

    # ── .raid <count> ────────────────────────────────────────────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.raid(?:\s+(\d+))?$"))
    @client.flood_safe
    async def raid_handler(event):
        """Raid the replied user with the saved text."""
        # ── Validate raid text ───────────────────────────────────────────
        text = _load_raid_text()
        if not text:
            await event.edit(
                "❌ <b>No raid text set.</b>\n"
                "Use <code>.setraid &lt;text&gt;</code> first.",
                parse_mode="html",
            )
            return

        # ── Parse count ──────────────────────────────────────────────────
        count_str = event.pattern_match.group(1)
        try:
            count = int(count_str) if count_str else 10
        except ValueError:
            count = 10
        if count <= 0:
            await event.edit(
                "❌ <b>Count must be a positive integer.</b>",
                parse_mode="html",
            )
            return
        if count > 500:
            await event.edit(
                "❌ <b>Maximum count is 500.</b>",
                parse_mode="html",
            )
            return

        # ── Resolve target user ──────────────────────────────────────────
        target = await event.get_reply_message()
        if not target:
            await event.edit(
                "❌ <b>Reply to a user to raid them.</b>",
                parse_mode="html",
            )
            return
        try:
            target_entity = await target.get_input_entity()
        except Exception:
            try:
                target_entity = await target.get_input_sender()
            except Exception:
                await event.edit(
                    "❌ <b>Could not resolve target user.</b>",
                    parse_mode="html",
                )
                return

        # ── Resolve chat (avoid Peer ID errors) ──────────────────────────
        try:
            chat = await event.get_input_chat()
        except Exception:
            await event.edit(
                "❌ <b>Could not resolve chat.</b>",
                parse_mode="html",
            )
            return

        # ── Fetch user details for mention ───────────────────────────────
        try:
            user_obj = await client.get_entity(target_entity)
            user_id = user_obj.id
            display_name = (
                getattr(user_obj, "first_name", None)
                or getattr(user_obj, "title", None)
                or "User"
            )
        except Exception:
            await event.edit(
                "❌ <b>Could not fetch target user details.</b>",
                parse_mode="html",
            )
            return

        mention = _build_mention(user_id, display_name)
        raid_msg = f"{text} {mention}"

        await event.edit(
            f"💥 <b>Raid started</b> on "
            f'<a href="tg://user?id={user_id}">{display_name}</a> '
            f"| Count: <b>{count}</b>",
            parse_mode="html",
        )

        # ── Background raid loop ─────────────────────────────────────────
        async def _raid_loop():
            try:
                for _ in range(count):
                    try:
                        await client.send_message(
                            chat, raid_msg, parse_mode="html"
                        )
                    except FloodWaitError as fw:
                        await asyncio.sleep(fw.seconds + 1)
                        try:
                            await client.send_message(
                                chat, raid_msg, parse_mode="html"
                            )
                        except Exception:
                            pass
                    except Exception:
                        await asyncio.sleep(0.5)
                    # Small delay between messages to ease rate-limit pressure
                    await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                raise
            finally:
                client.stop_processes.pop(f"raid_{event.id}", None)

        task = asyncio.create_task(_raid_loop())
        client.stop_processes[f"raid_{event.id}"] = task

    # ── .drraid  (activate reply-raid) ───────────────────────────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.drraid$"))
    @client.flood_safe
    async def drraid_handler(event):
        """Activate reply-raid on the replied user."""
        text = _load_raid_text()
        if not text:
            await event.edit(
                "❌ <b>No raid text set.</b>\n"
                "Use <code>.setraid &lt;text&gt;</code> first.",
                parse_mode="html",
            )
            return

        target = await event.get_reply_message()
        if not target:
            await event.edit(
                "❌ <b>Reply to a user to enable reply-raid.</b>",
                parse_mode="html",
            )
            return
        try:
            target_entity = await target.get_input_entity()
        except Exception:
            try:
                target_entity = await target.get_input_sender()
            except Exception:
                await event.edit(
                    "❌ <b>Could not resolve target user.</b>",
                    parse_mode="html",
                )
                return

        try:
            user_obj = await client.get_entity(target_entity)
            user_id = user_obj.id
            display_name = (
                getattr(user_obj, "first_name", None)
                or getattr(user_obj, "title", None)
                or "User"
            )
        except Exception:
            await event.edit(
                "❌ <b>Could not fetch target user details.</b>",
                parse_mode="html",
            )
            return

        if user_id in active_reply_raids:
            await event.edit(
                "⚠️ <b>Reply-raid is already active on this user.</b>",
                parse_mode="html",
            )
            return

        active_reply_raids.append(user_id)
        await event.edit(
            f"✅ <b>Reply-raid activated</b> on "
            f'<a href="tg://user?id={user_id}">{display_name}</a>.\n'
            "Every message they send will be replied to with the raid text.",
            parse_mode="html",
        )

    # ── .stopraid  (deactivate reply-raid) ───────────────────────────────
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stopraid$"))
    @client.flood_safe
    async def stopraid_handler(event):
        """Deactivate reply-raid on the replied user (or all if no reply)."""
        target = await event.get_reply_message()
        if not target:
            # No reply → clear every active reply-raid
            if active_reply_raids:
                cleared = len(active_reply_raids)
                active_reply_raids.clear()
                await event.edit(
                    f"✅ <b>Cleared {cleared} active reply-raid(s).</b>",
                    parse_mode="html",
                )
            else:
                await event.edit(
                    "❌ <b>No reply-raid is currently active.</b>",
                    parse_mode="html",
                )
            return

        try:
            target_entity = await target.get_input_entity()
        except Exception:
            try:
                target_entity = await target.get_input_sender()
            except Exception:
                await event.edit(
                    "❌ <b>Could not resolve target user.</b>",
                    parse_mode="html",
                )
                return

        try:
            user_obj = await client.get_entity(target_entity)
            user_id = user_obj.id
        except Exception:
            await event.edit(
                "❌ <b>Could not fetch target user details.</b>",
                parse_mode="html",
            )
            return

        if user_id in active_reply_raids:
            active_reply_raids.remove(user_id)
            await event.edit(
                f"✅ <b>Reply-raid stopped</b> on user <code>{user_id}</code>.",
                parse_mode="html",
            )
        else:
            await event.edit(
                "⚠️ <b>Reply-raid was not active on this user.</b>",
                parse_mode="html",
            )

    # ── Reply-raid listener (fires on every incoming message) ────────────
    @client.on(events.NewMessage(incoming=True))
    async def reply_raid_listener(event):
        """Reply with raid text whenever a reply-raid target sends a message."""
        if not active_reply_raids:
            return
        sender_id = event.sender_id
        if sender_id is None or sender_id not in active_reply_raids:
            return

        text = _load_raid_text()
        if not text:
            return

        try:
            sender = await event.get_sender()
            display_name = (
                getattr(sender, "first_name", None)
                or getattr(sender, "title", None)
                or "User"
            )
        except Exception:
            display_name = "User"

        mention = _build_mention(sender_id, display_name)
        raid_msg = f"{text} {mention}"

        try:
            await event.reply(raid_msg, parse_mode="html")
        except FloodWaitError as fw:
            await asyncio.sleep(fw.seconds + 1)
            try:
                await event.reply(raid_msg, parse_mode="html")
            except Exception:
                pass
        except Exception:
            pass