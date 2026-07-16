# worker_bot/modules/spam.py
# Spam & Sticker module for the Telegram Userbot.
# Loaded dynamically by userbot.py via register(client).

import asyncio
import base64
import json
import os
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.types import InputDocument

# ─── Paths ──────────────────────────────────────────────────────────────────
GSPAM_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gspam_data.json"
)

# ─── JSON Helpers ───────────────────────────────────────────────────────────

def _save_gspam(doc):
    """Persist a sticker Document's id / access_hash / file_reference to JSON."""
    try:
        file_ref = (
            base64.b64encode(doc.file_reference).decode("utf-8")
            if doc.file_reference
            else ""
        )
        payload = {
            "id": str(doc.id),
            "access_hash": str(doc.access_hash),
            "file_reference": file_ref,
        }
        with open(GSPAM_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return True
    except Exception:
        return False


def _load_gspam():
    """Return an ``InputDocument`` from the JSON file, or ``None``."""
    try:
        with open(GSPAM_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        file_ref = (
            base64.b64decode(data["file_reference"])
            if data.get("file_reference")
            else b""
        )
        return InputDocument(
            id=int(data["id"]),
            access_hash=int(data["access_hash"]),
            file_reference=file_ref,
        )
    except Exception:
        return None


def _clear_gspam():
    """Delete the gspam JSON file."""
    try:
        if os.path.exists(GSPAM_FILE):
            os.remove(GSPAM_FILE)
    except Exception:
        pass


# ─── Module Entry Point ─────────────────────────────────────────────────────

def register(client):
    """Register all spam & sticker handlers on *client*."""

    # ── Background task helpers ──────────────────────────────────────────

    async def _text_spam_task(event, chat, count, text, delay, label):
        """Send *text* to *chat* *count* times with *delay* seconds between."""
        key = f"spam_{event.id}"
        sent = 0
        try:
            for _ in range(count):
                try:
                    await client.send_message(chat, text, link_preview=False)
                    sent += 1
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds + 1)
                    try:
                        await client.send_message(chat, text, link_preview=False)
                        sent += 1
                    except Exception:
                        continue
                except asyncio.CancelledError:
                    raise
                except Exception:
                    continue

                if delay > 0:
                    await asyncio.sleep(delay)
                elif sent % 25 == 0:          # yield to the event loop
                    await asyncio.sleep(0)

            try:
                await event.reply(
                    f"✅ **{label}** finished — {sent}/{count} messages sent."
                )
            except Exception:
                pass
        except asyncio.CancelledError:
            try:
                await event.reply(
                    f"⛔ **{label}** stopped — {sent}/{count} messages sent."
                )
            except Exception:
                pass
            raise
        finally:
            client.stop_processes.pop(key, None)

    # ─────────────────────────────────────────────────────────────────────

    async def _sticker_spam_task(event, chat, count, sticker_doc, label):
        """Send *sticker_doc* (InputDocument) to *chat* *count* times."""
        key = f"spam_{event.id}"
        sent = 0
        try:
            for _ in range(count):
                try:
                    await client.send_file(chat, sticker_doc)
                    sent += 1
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds + 1)
                    try:
                        await client.send_file(chat, sticker_doc)
                        sent += 1
                    except Exception:
                        continue
                except asyncio.CancelledError:
                    raise
                except Exception:
                    continue

                await asyncio.sleep(0.05)
                if sent % 25 == 0:
                    await asyncio.sleep(0)

            try:
                await event.reply(
                    f"✅ **{label}** finished — {sent}/{count} stickers sent."
                )
            except Exception:
                pass
        except asyncio.CancelledError:
            try:
                await event.reply(
                    f"⛔ **{label}** stopped — {sent}/{count} stickers sent."
                )
            except Exception:
                pass
            raise
        finally:
            client.stop_processes.pop(key, None)

    # ─────────────────────────────────────────────────────────────────────

    async def _dm_spam_task(event, target, count, text, delay):
        """Send *text* to a user's DM *count* times."""
        key = f"spam_{event.id}"
        sent = 0
        try:
            for _ in range(count):
                try:
                    await client.send_message(target, text, link_preview=False)
                    sent += 1
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds + 1)
                    try:
                        await client.send_message(target, text, link_preview=False)
                        sent += 1
                    except Exception:
                        continue
                except asyncio.CancelledError:
                    raise
                except Exception:
                    continue

                if delay > 0:
                    await asyncio.sleep(delay)
                elif sent % 25 == 0:
                    await asyncio.sleep(0)

            try:
                await event.reply(
                    f"✅ **dmspam** finished — {sent}/{count} messages sent."
                )
            except Exception:
                pass
        except asyncio.CancelledError:
            try:
                await event.reply(
                    f"⛔ **dmspam** stopped — {sent}/{count} messages sent."
                )
            except Exception:
                pass
            raise
        finally:
            client.stop_processes.pop(key, None)

    # ── Parsing helper ───────────────────────────────────────────────────

    def _parse_count_text(args, usage):
        """Return (count, text, error_message)."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return None, None, usage
        try:
            count = int(parts[0])
        except ValueError:
            return None, None, "❌ **Count** must be an integer."
        if count <= 0:
            return None, None, "❌ **Count** must be a positive integer."
        return count, parts[1], None

    # ── .spam  (1 s delay) ───────────────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.spam(?:\s|$)"))
    @client.flood_safe
    async def spam_handler(event):
        args = event.raw_text[len(".spam"):].strip()
        if not args:
            await event.reply("Usage: `.spam <count> <text>`")
            return
        count, text, err = _parse_count_text(args, "Usage: `.spam <count> <text>`")
        if err:
            await event.reply(err)
            return
        chat = await event.get_input_chat()
        task = asyncio.create_task(
            _text_spam_task(event, chat, count, text, 1.0, "spam")
        )
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .uspam  (no delay) ───────────────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.uspam(?:\s|$)"))
    @client.flood_safe
    async def uspam_handler(event):
        args = event.raw_text[len(".uspam"):].strip()
        if not args:
            await event.reply("Usage: `.uspam <count> <text>`")
            return
        count, text, err = _parse_count_text(args, "Usage: `.uspam <count> <text>`")
        if err:
            await event.reply(err)
            return
        chat = await event.get_input_chat()
        task = asyncio.create_task(
            _text_spam_task(event, chat, count, text, 0.0, "uspam")
        )
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .fastspam  (0.1 s delay) ─────────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.fastspam(?:\s|$)"))
    @client.flood_safe
    async def fastspam_handler(event):
        args = event.raw_text[len(".fastspam"):].strip()
        if not args:
            await event.reply("Usage: `.fastspam <count> <text>`")
            return
        count, text, err = _parse_count_text(args, "Usage: `.fastspam <count> <text>`")
        if err:
            await event.reply(err)
            return
        chat = await event.get_input_chat()
        task = asyncio.create_task(
            _text_spam_task(event, chat, count, text, 0.1, "fastspam")
        )
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .delayspam  (custom delay) ───────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.delayspam(?:\s|$)"))
    @client.flood_safe
    async def delayspam_handler(event):
        args = event.raw_text[len(".delayspam"):].strip()
        if not args:
            await event.reply("Usage: `.delayspam <count> <seconds> <text>`")
            return
        parts = args.split(maxsplit=2)
        if len(parts) < 3:
            await event.reply("Usage: `.delayspam <count> <seconds> <text>`")
            return
        try:
            count = int(parts[0])
            delay = float(parts[1])
        except ValueError:
            await event.reply("❌ **Count** and **seconds** must be numbers.")
            return
        if count <= 0:
            await event.reply("❌ **Count** must be a positive integer.")
            return
        if delay < 0:
            await event.reply("❌ **Delay** cannot be negative.")
            return
        text = parts[2]
        chat = await event.get_input_chat()
        task = asyncio.create_task(
            _text_spam_task(event, chat, count, text, delay, "delayspam")
        )
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .dmspam  (DM spam) ───────────────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.dmspam(?:\s|$)"))
    @client.flood_safe
    async def dmspam_handler(event):
        args = event.raw_text[len(".dmspam"):].strip()
        if not args:
            await event.reply("Usage: `.dmspam <count> <username> <text>`")
            return
        parts = args.split(maxsplit=2)
        if len(parts) < 3:
            await event.reply("Usage: `.dmspam <count> <username> <text>`")
            return
        try:
            count = int(parts[0])
        except ValueError:
            await event.reply("❌ **Count** must be an integer.")
            return
        if count <= 0:
            await event.reply("❌ **Count** must be a positive integer.")
            return
        username = parts[1].lstrip("@")
        text = parts[2]

        # ── Resolve the target entity to avoid Peer ID errors ──
        try:
            target = await client.get_input_entity(username)
        except Exception as exc:
            await event.reply(f"❌ Failed to resolve `{username}`:\n`{exc}`")
            return

        task = asyncio.create_task(_dm_spam_task(event, target, count, text, 1.0))
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .mspam  (reply to a sticker) ─────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.mspam(?:\s|$)"))
    @client.flood_safe
    async def mspam_handler(event):
        args = event.raw_text[len(".mspam"):].strip()
        if not args:
            await event.reply("Usage: `.mspam <count>`  (reply to a sticker)")
            return
        try:
            count = int(args.split()[0])
        except ValueError:
            await event.reply("❌ **Count** must be an integer.")
            return
        if count <= 0:
            await event.reply("❌ **Count** must be a positive integer.")
            return

        reply = await event.get_reply_message()
        if not reply:
            await event.reply("❌ Please reply to a sticker.")
            return
        if not reply.sticker:
            await event.reply("❌ The replied message is not a sticker.")
            return

        doc = reply.media.document
        sticker_input = InputDocument(
            id=doc.id,
            access_hash=doc.access_hash,
            file_reference=doc.file_reference,
        )
        chat = await event.get_input_chat()
        task = asyncio.create_task(
            _sticker_spam_task(event, chat, count, sticker_input, "mspam")
        )
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .gspam  (globally saved sticker) ─────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.gspam(?:\s|$)"))
    @client.flood_safe
    async def gspam_handler(event):
        args = event.raw_text[len(".gspam"):].strip()
        if not args:
            await event.reply("Usage: `.gspam <count>`")
            return
        try:
            count = int(args.split()[0])
        except ValueError:
            await event.reply("❌ **Count** must be an integer.")
            return
        if count <= 0:
            await event.reply("❌ **Count** must be a positive integer.")
            return

        sticker_input = _load_gspam()
        if not sticker_input:
            await event.reply(
                "❌ No global sticker is set.\n"
                "Use `.setgspam` (reply to a sticker) to set one."
            )
            return

        chat = await event.get_input_chat()
        task = asyncio.create_task(
            _sticker_spam_task(event, chat, count, sticker_input, "gspam")
        )
        client.stop_processes[f"spam_{event.id}"] = task

    # ── .setgspam  (save a sticker) ──────────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.setgspam(?:\s|$)"))
    @client.flood_safe
    async def setgspam_handler(event):
        reply = await event.get_reply_message()
        if not reply:
            await event.reply("❌ Please reply to a sticker to save it.")
            return
        if not reply.sticker:
            await event.reply("❌ The replied message is not a sticker.")
            return

        doc = reply.media.document
        if _save_gspam(doc):
            await event.reply(
                f"✅ **Global sticker saved.**\n"
                f"📄 Document ID: `{doc.id}`\n"
                f"🔑 Access Hash: `{doc.access_hash}`"
            )
        else:
            await event.reply("❌ Failed to save the global sticker.")

    # ── .listgspam  (view saved sticker) ─────────────────────────────────

    @client.on(events.NewMessage(pattern=r"^\.listgspam(?:\s|$)"))
    @client.flood_safe
    async def listgspam_handler(event):
        sticker_input = _load_gspam()
        if not sticker_input:
            await event.reply(
                "📭 No global sticker is currently set.\n"
                "Use `.setgspam` (reply to a sticker) to set one."
            )
            return
        await event.reply(
            f"📌 **Saved Global Sticker**\n"
            f"📄 Document ID: `{sticker_input.id}`\n"
            f"🔑 Access Hash: `{sticker_input.access_hash}`"
        )

    # ── .clrgspam  /  .delgspam  (delete saved sticker) ──────────────────

    @client.on(events.NewMessage(pattern=r"^\.clrgspam(?:\s|$)"))
    @client.flood_safe
    async def clrgspam_handler(event):
        _clear_gspam()
        await event.reply("🗑️ Global sticker has been **cleared**.")

    @client.on(events.NewMessage(pattern=r"^\.delgspam(?:\s|$)"))
    @client.flood_safe
    async def delgspam_handler(event):
        _clear_gspam()
        await event.reply("🗑️ Global sticker has been **deleted**.")