"""
worker_bot/modules/admin.py
============================
Admin Module for Telegram Userbot (Telethon v1.x+)

Handles group administration commands:
    .ban  .unban  .kick  .promote  .demote
    .mute <min>  .unmute
    .pin  .unpin  .unpinall
    .del  .purge [n]
    .lock <type>  .unlock <type>
    .autodelete on|off|list
    .admins  .info
    .warn <reason>  .warnings  .resetwarn
    .gban  .ungban
    .antiflood on <count> <sec> | off | status

This module is loaded dynamically by `userbot.py`. It MUST expose
`def register(client):` and NEVER use a global `client` object.
"""

import asyncio
import time

from telethon import events
from telethon.errors import (
    FloodWaitError,
    UserAdminInvalidError,
    ChatAdminRequiredError,
)
from telethon.tl.functions.channels import (
    EditBannedRequest,
    EditAdminRequest,
)
from telethon.tl.functions.messages import (
    EditChatDefaultBannedRightsRequest,
    UpdatePinnedMessageRequest,
)
from telethon.tl.types import (
    ChatBannedRights,
    ChatAdminRights,
    ChannelParticipantAdmin,
    ChannelParticipantCreator,
    ChannelParticipantsAdmins,
)


# ────────────────────────────────────────────────────────────────────────────
# Module-level state (shared per process; only one client per process anyway)
# ────────────────────────────────────────────────────────────────────────────
autodelete_targets = {}  # {chat_id: [user_id, ...]}
warn_storage        = {}  # {(chat_id, user_id): [count, [reasons...]]}
antiflood_state     = {}  # {chat_id: {"limit": int, "window": int, "users": {uid: [ts,...]}}}
gban_list           = set()  # {user_id, ...}

# lock-type → ChatBannedRights field
LOCK_MAP = {
    "msg":      "send_messages",
    "messages": "send_messages",
    "media":    "send_media",
    "sticker":  "send_stickers",
    "stickers": "send_stickers",
    "gif":      "send_gifs",
    "gifs":     "send_gifs",
    "game":     "send_games",
    "games":    "send_games",
    "inline":   "send_inline",
    "link":     "embed_links",
    "links":    "embed_links",
    "poll":     "send_polls",
    "polls":    "send_polls",
    "info":     "change_info",
    "invite":   "invite_users",
    "pin":      "pin_messages",
}

# Default "all-banned" rights (used for ban / kick-step-1)
_FULL_BAN_RIGHTS = ChatBannedRights(
    until_date=None,
    view_messages=True,
    send_messages=True,
    send_media=True,
    send_stickers=True,
    send_gifs=True,
    send_games=True,
    send_inline=True,
    embed_links=True,
    send_polls=True,
)

# Default "all-allowed" rights (used for unban / unmute / kick-step-2)
_FULL_FREE_RIGHTS = ChatBannedRights(
    until_date=None,
    view_messages=False,
    send_messages=False,
    send_media=False,
    send_stickers=False,
    send_gifs=False,
    send_games=False,
    send_inline=False,
    embed_links=False,
    send_polls=False,
)

# Default mute rights (only send-restrictions, view allowed)
_MUTE_RIGHTS = ChatBannedRights(
    until_date=None,
    view_messages=False,
    send_messages=True,
    send_media=True,
    send_stickers=True,
    send_gifs=True,
    send_games=True,
    send_inline=True,
    embed_links=True,
    send_polls=True,
)

# Default promote rights
_PROMOTE_RIGHTS = ChatAdminRights(
    change_info=True,
    post_messages=True,
    edit_messages=True,
    delete_messages=True,
    ban_users=True,
    invite_users=True,
    pin_messages=True,
    manage_call=True,
    other=True,
)

_DEMOTE_RIGHTS = ChatAdminRights(
    change_info=False,
    post_messages=False,
    edit_messages=False,
    delete_messages=False,
    ban_users=False,
    invite_users=False,
    pin_messages=False,
    manage_call=False,
    other=False,
)


# ────────────────────────────────────────────────────────────────────────────
# Registration
# ────────────────────────────────────────────────────────────────────────────
def register(client):
    """Register all admin commands on the given client.

    No globals — `client` is passed in by `userbot.py`. The `stop_processes`
    attribute and the `flood_safe` decorator are accessed off `client`.
    """

    # ───── Internal helpers ─────
    async def _target_from_reply(event):
        """Return (input_chat, target_input_sender) from a reply message.

        Returns (chat, None) if no reply.
        """
        reply = await event.get_reply_message()
        chat = await event.get_input_chat()
        if not reply:
            return chat, None
        target = await reply.get_input_sender()
        return chat, target

    async def _resolve_target(event, arg):
        """Resolve target from reply, else from a username/ID string."""
        chat = await event.get_input_chat()
        reply = await event.get_reply_message()
        if reply:
            return chat, await reply.get_input_sender()
        if arg:
            try:
                ent = await client.get_entity(arg.strip().lstrip("@"))
                return chat, ent
            except Exception:
                return chat, None
        return chat, None

    def _perm_msg(e):
        if isinstance(e, UserAdminInvalidError):
            return ("❌ **Permission denied.** Either the target is an admin "
                    "or I don't have sufficient admin rights.")
        if isinstance(e, ChatAdminRequiredError):
            return "❌ I need **admin rights** in this chat to do that."
        return f"⚠️ Unexpected error: `{type(e).__name__}: {e}`"

    def _strip_reason(match):
        return (match or "").strip() or "No reason provided"

    # ════════════════════════════ .ban ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]ban(?:\s+(.*))?$"))
    @client.flood_safe
    async def ban_handler(event):
        try:
            chat, target = await _target_from_reply(event)
            if not target:
                return await event.reply("❌ Reply to the user you want to **ban**.")
            reason = _strip_reason(event.pattern_match.group(1))
            await client(EditBannedRequest(
                channel=chat, user_id=target, banned_rights=_FULL_BAN_RIGHTS))
            await event.reply(
                f"🚫 **Banned** `{target.user_id}`\n📝 Reason: {reason}")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .unban ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]unban(?:\s+(.*))?$"))
    @client.flood_safe
    async def unban_handler(event):
        try:
            chat, target = await _resolve_target(event, event.pattern_match.group(1))
            if not target:
                return await event.reply("❌ Reply to user or specify @username/ID.")
            await client(EditBannedRequest(
                channel=chat, user_id=target, banned_rights=_FULL_FREE_RIGHTS))
            await event.reply(f"✅ **Unbanned** `{target.user_id}`")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .kick ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]kick(?:\s+(.*))?$"))
    @client.flood_safe
    async def kick_handler(event):
        try:
            chat, target = await _target_from_reply(event)
            if not target:
                return await event.reply("❌ Reply to the user you want to **kick**.")
            reason = _strip_reason(event.pattern_match.group(1))
            # kick = ban + unban
            await client(EditBannedRequest(
                channel=chat, user_id=target, banned_rights=_FULL_BAN_RIGHTS))
            await client(EditBannedRequest(
                channel=chat, user_id=target, banned_rights=_FULL_FREE_RIGHTS))
            await event.reply(
                f"👢 **Kicked** `{target.user_id}`\n📝 Reason: {reason}")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .promote ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]promote(?:\s+(.*))?$"))
    @client.flood_safe
    async def promote_handler(event):
        try:
            chat, target = await _target_from_reply(event)
            if not target:
                return await event.reply("❌ Reply to the user you want to **promote**.")
            title = _strip_reason(event.pattern_match.group(1))
            await client(EditAdminRequest(
                channel=chat, user_id=target, admin_rights=_PROMOTE_RIGHTS))
            await event.reply(f"⬆️ **Promoted** `{target.user_id}` as **{title}**")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .demote ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]demote$"))
    @client.flood_safe
    async def demote_handler(event):
        try:
            chat, target = await _target_from_reply(event)
            if not target:
                return await event.reply("❌ Reply to the user you want to **demote**.")
            await client(EditAdminRequest(
                channel=chat, user_id=target, admin_rights=_DEMOTE_RIGHTS))
            await event.reply(f"⬇️ **Demoted** `{target.user_id}`")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .mute <minutes> ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]mute(?:\s+(\d+))?$"))
    @client.flood_safe
    async def mute_handler(event):
        try:
            chat, target = await _target_from_reply(event)
            if not target:
                return await event.reply("❌ Reply to the user you want to **mute**.")
            minutes = int(event.pattern_match.group(1) or 0)
            until = int(time.time()) + minutes * 60 if minutes > 0 else 0
            rights = ChatBannedRights(
                until_date=until,
                view_messages=False,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
            )
            await client(EditBannedRequest(channel=chat, user_id=target, banned_rights=rights))
            dur = f"{minutes} min" if minutes else "indefinitely"
            await event.reply(f"🔇 **Muted** `{target.user_id}` for **{dur}**")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .unmute ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]unmute$"))
    @client.flood_safe
    async def unmute_handler(event):
        try:
            chat, target = await _target_from_reply(event)
            if not target:
                return await event.reply("❌ Reply to the user you want to **unmute**.")
            await client(EditBannedRequest(
                channel=chat, user_id=target, banned_rights=_FULL_FREE_RIGHTS))
            await event.reply(f"🔊 **Unmuted** `{target.user_id}`")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .pin ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]pin(?:\s+(silent))?$"))
    @client.flood_safe
    async def pin_handler(event):
        try:
            chat = await event.get_input_chat()
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the message you want to **pin**.")
            silent = bool(event.pattern_match.group(1))
            await client(UpdatePinnedMessageRequest(peer=chat, id=reply.id, silent=silent))
            await event.reply("📌 **Pinned** message.")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .unpin ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]unpin$"))
    @client.flood_safe
    async def unpin_handler(event):
        try:
            chat = await event.get_input_chat()
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the pinned message you want to **unpin**.")
            await client(UpdatePinnedMessageRequest(peer=chat, id=reply.id, unpin=True))
            await event.reply("📍 **Unpinned** message.")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .unpinall ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]unpinall$"))
    @client.flood_safe
    async def unpinall_handler(event):
        try:
            chat = await event.get_input_chat()
            await client(UpdatePinnedMessageRequest(peer=chat, id=0, unpin=True))
            await event.reply("📍 **Unpinned all messages.**")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))

    # ════════════════════════════ .del ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]del$"))
    @client.flood_safe
    async def del_handler(event):
        try:
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the message you want to **delete**.")
            await reply.delete()
            await event.delete()
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .purge [limit] ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]purge(?:\s+(\d+))?$"))
    @client.flood_safe
    async def purge_handler(event):
        try:
            chat = await event.get_input_chat()
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to a message to start **purging** from.")
            limit = int(event.pattern_match.group(1) or 100)
            count = 0
            batch = []
            async for msg in client.iter_messages(chat, min_id=reply.id - 1, limit=limit):
                batch.append(msg.id)
                if len(batch) >= 100:
                    await client.delete_messages(chat, batch)
                    count += len(batch)
                    batch = []
            if batch:
                await client.delete_messages(chat, batch)
                count += len(batch)
            await event.delete()
            if count:
                await event.reply(f"🧹 **Purged {count} messages.**", delete_after=5)
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .lock <type> ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]lock(?:\s+(\w+))?$"))
    @client.flood_safe
    async def lock_handler(event):
        try:
            chat = await event.get_input_chat()
            lt = (event.pattern_match.group(1) or "").strip().lower()
            if not lt:
                return await event.reply(
                    "❌ Usage: `.lock <type>`\n"
                    "Available: `msg, media, stickers, gifs, games, inline, "
                    "links, polls, info, invite, pin`"
                )
            if lt not in LOCK_MAP:
                return await event.reply(f"❌ Unknown lock type: `{lt}`")
            rights = ChatBannedRights(until_date=None)
            setattr(rights, LOCK_MAP[lt], True)
            await client(EditChatDefaultBannedRightsRequest(peer=chat, banned_rights=rights))
            await event.reply(f"🔒 **Locked** `{lt}` in this chat.")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .unlock <type> ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]unlock(?:\s+(\w+))?$"))
    @client.flood_safe
    async def unlock_handler(event):
        try:
            chat = await event.get_input_chat()
            lt = (event.pattern_match.group(1) or "").strip().lower()
            if not lt:
                return await event.reply("❌ Usage: `.unlock <type>`")
            if lt not in LOCK_MAP:
                return await event.reply(f"❌ Unknown unlock type: `{lt}`")
            rights = ChatBannedRights(until_date=None)
            setattr(rights, LOCK_MAP[lt], False)
            await client(EditChatDefaultBannedRightsRequest(peer=chat, banned_rights=rights))
            await event.reply(f"🔓 **Unlocked** `{lt}` in this chat.")
        except (UserAdminInvalidError, ChatAdminRequiredError) as e:
            await event.reply(_perm_msg(e))
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .autodelete ════════════════════════════
    @client.on(events.NewMessage(
        pattern=r"^[\.!]autodelete(?:\s+(on|off|list))?(?:\s+(\S+))?$"))
    @client.flood_safe
    async def autodelete_handler(event):
        try:
            chat_id = event.chat_id
            action = (event.pattern_match.group(1) or "").strip().lower()
            arg = event.pattern_match.group(2)

            # ── LIST ──
            if action == "list":
                users = autodelete_targets.get(chat_id, [])
                if not users:
                    return await event.reply(
                        "📭 No users have auto-delete active in this chat.")
                text = "**🗑 Auto-delete targets in this chat:**\n" + \
                       "\n".join(f"• `{u}`" for u in users)
                return await event.reply(text)

            if action not in ("on", "off"):
                return await event.reply(
                    "❌ Usage:\n"
                    "• `.autodelete on` (reply to user, or `.autodelete on @username`)\n"
                    "• `.autodelete off` (same)\n"
                    "• `.autodelete list`"
                )

            # ── Resolve target user id ──
            target_id = None
            reply = await event.get_reply_message()
            if reply:
                target_id = reply.sender_id
            elif arg:
                try:
                    ent = await client.get_entity(arg.strip().lstrip("@"))
                    target_id = ent.id
                except Exception:
                    return await event.reply(
                        f"❌ Couldn't resolve `{arg}` to a Telegram user.")

            if not target_id:
                return await event.reply(
                    "❌ Reply to a user or specify @username/ID.")

            # Don't allow self-targeting
            me = await client.get_me()
            if target_id == me.id:
                return await event.reply("❌ Cannot auto-delete your own messages.")

            autodelete_targets.setdefault(chat_id, [])
            if action == "on":
                if target_id not in autodelete_targets[chat_id]:
                    autodelete_targets[chat_id].append(target_id)
                return await event.reply(
                    f"🗑 **Auto-delete enabled** for `{target_id}` in this chat.")
            else:  # off
                if target_id in autodelete_targets[chat_id]:
                    autodelete_targets[chat_id].remove(target_id)
                    if not autodelete_targets[chat_id]:
                        del autodelete_targets[chat_id]
                return await event.reply(
                    f"✅ **Auto-delete disabled** for `{target_id}`.")
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ Auto-delete listener ════════════════════════════
    @client.on(events.NewMessage())
    @client.flood_safe
    async def autodelete_listener(event):
        # Optimization: Ignore own messages
        if event.out:
            return
        try:
            cid = event.chat_id
            uid = event.sender_id
            if cid is None or uid is None:
                return
            targets = autodelete_targets.get(cid)
            if targets and uid in targets:
                await event.delete()
        except Exception:
            # Never let listener errors crash the event loop
            pass

    # ════════════════════════════ .admins ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]admins$"))
    @client.flood_safe
    async def admins_handler(event):
        try:
            chat = await event.get_input_chat()
            lines = []
            async for u in client.iter_participants(chat, filter=ChannelParticipantsAdmins):
                name = (u.first_name or "") + (f" {u.last_name}" if u.last_name else "")
                tag = "👑" if isinstance(u.participant, ChannelParticipantCreator) else "🛡"
                lines.append(f"{tag} {name.strip()} (`{u.id}`)")
            if not lines:
                return await event.reply("No admins found / no admin list access.")
            await event.reply("**Admins in this chat:**\n" + "\n".join(lines))
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .info ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]info$"))
    @client.flood_safe
    async def info_handler(event):
        try:
            reply = await event.get_reply_message()
            user = await reply.get_sender() if reply else await event.get_sender()
            full = ""
            if getattr(user, "last_name", ""):
                full = f" {user.last_name}"
            text = (
                "👤 **User Info**\n"
                f"• Name: {(user.first_name or '')}{full}\n"
                f"• ID: `{user.id}`\n"
                f"• Username: @{user.username if user.username else '—'}\n"
                f"• Bot: `{user.bot}`\n"
                f"• Deleted: `{user.deleted}`\n"
                f"• Premium: `{getattr(user, 'premium', False)}`"
            )
            await event.reply(text)
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .warn / .warnings / .resetwarn ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]warn(?:\s+(.*))?$"))
    @client.flood_safe
    async def warn_handler(event):
        try:
            chat_id = event.chat_id
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the user you want to **warn**.")
            uid = reply.sender_id
            reason = _strip_reason(event.pattern_match.group(1))
            key = (chat_id, uid)
            warn_storage.setdefault(key, [0, []])
            warn_storage[key][0] += 1
            warn_storage[key][1].append(reason)
            count = warn_storage[key][0]
            await event.reply(
                f"⚠️ **Warning #{count}** for `{uid}`\n📝 {reason}\n"
                f"(3 warnings → auto-ban)")
            if count >= 3:
                chat = await event.get_input_chat()
                target = await reply.get_input_sender()
                try:
                    await client(EditBannedRequest(
                        channel=chat, user_id=target, banned_rights=_FULL_BAN_RIGHTS))
                    await event.reply(f"🚫 Auto-banned `{uid}` after 3 warnings.")
                except (UserAdminInvalidError, ChatAdminRequiredError) as e:
                    await event.reply(_perm_msg(e))
                finally:
                    warn_storage.pop(key, None)
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    @client.on(events.NewMessage(pattern=r"^[\.!]warnings$"))
    @client.flood_safe
    async def warnings_handler(event):
        try:
            chat_id = event.chat_id
            reply = await event.get_reply_message()
            uid = reply.sender_id if reply else event.sender_id
            key = (chat_id, uid)
            if key not in warn_storage:
                return await event.reply(f"✅ `{uid}` has no warnings.")
            count, reasons = warn_storage[key]
            text = f"⚠️ `{uid}` has **{count}** warning(s):\n" + \
                   "\n".join(f"• {r}" for r in reasons)
            await event.reply(text)
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    @client.on(events.NewMessage(pattern=r"^[\.!]resetwarn$"))
    @client.flood_safe
    async def resetwarn_handler(event):
        try:
            chat_id = event.chat_id
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the user whose warnings to reset.")
            uid = reply.sender_id
            if warn_storage.pop((chat_id, uid), None) is not None:
                await event.reply(f"♻️ Reset warnings for `{uid}`.")
            else:
                await event.reply(f"ℹ️ `{uid}` had no warnings.")
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .gban / .ungban ════════════════════════════
    @client.on(events.NewMessage(pattern=r"^[\.!]gban(?:\s+(.*))?$"))
    @client.flood_safe
    async def gban_handler(event):
        try:
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the user to **globally ban**.")
            target = await reply.get_input_sender()
            uid = target.user_id
            reason = _strip_reason(event.pattern_match.group(1))
            gban_list.add(uid)
            await event.reply(
                f"🌍 **GBan registered** for `{uid}`\n📝 {reason}\n"
                f"I'll ban them in every chat where I'm admin. Working…")
            done = 0
            async for dialog in client.iter_dialogs():
                if not (dialog.is_group or dialog.is_channel):
                    continue
                try:
                    await client(EditBannedRequest(
                        channel=dialog.input_entity,
                        user_id=target,
                        banned_rights=_FULL_BAN_RIGHTS,
                    ))
                    done += 1
                except (UserAdminInvalidError, ChatAdminRequiredError):
                    continue
                except Exception:
                    continue
                await asyncio.sleep(0.4)  # be polite
            await event.reply(f"✅ **GBan applied** in `{done}` chats.")
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    @client.on(events.NewMessage(pattern=r"^[\.!]ungban$"))
    @client.flood_safe
    async def ungban_handler(event):
        try:
            reply = await event.get_reply_message()
            if not reply:
                return await event.reply("❌ Reply to the user to remove from **gban**.")
            uid = reply.sender_id
            if uid in gban_list:
                gban_list.discard(uid)
                return await event.reply(f"✅ **Removed GBan** for `{uid}`.")
            return await event.reply(f"ℹ️ `{uid}` is not in gban list.")
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ .antiflood ════════════════════════════
    @client.on(events.NewMessage(
        pattern=r"^[\.!]antiflood(?:\s+(on|off|status))?(?:\s+(\d+))?(?:\s+(\d+))?$"))
    @client.flood_safe
    async def antiflood_handler(event):
        try:
            chat_id = event.chat_id
            action = (event.pattern_match.group(1) or "").lower()
            if action == "on":
                limit = int(event.pattern_match.group(2) or 5)
                window = int(event.pattern_match.group(3) or 10)
                antiflood_state[chat_id] = {
                    "limit": limit, "window": window, "users": {}}
                return await event.reply(
                    f"🌊 **Anti-flood ON**: `{limit}` msgs / `{window}s`")
            if action == "off":
                antiflood_state.pop(chat_id, None)
                return await event.reply("✅ **Anti-flood OFF**")
            if action == "status":
                st = antiflood_state.get(chat_id)
                if st:
                    return await event.reply(
                        f"🌊 Anti-flood active: `{st['limit']}` msgs / `{st['window']}s`")
                return await event.reply("❌ Anti-flood is **OFF**.")
            return await event.reply(
                "❌ Usage:\n"
                "• `.antiflood on <count> <seconds>`\n"
                "• `.antiflood off`\n"
                "• `.antiflood status`")
        except Exception as e:
            await event.reply(f"⚠️ Error: `{e}`")

    # ════════════════════════════ Anti-flood listener ════════════════════════════
    @client.on(events.NewMessage())
    @client.flood_safe
    async def antiflood_listener(event):
        try:
            cid = event.chat_id
            uid = event.sender_id
            if cid is None or uid is None:
                return
            if cid not in antiflood_state:
                return
            if event.out:  # ignore own messages
                return
            st = antiflood_state[cid]
            now = time.time()
            history = st["users"].setdefault(uid, [])
            # drop expired timestamps
            history[:] = [t for t in history if now - t < st["window"]]
            
            # Memory Leak Fix: If history is empty, remove user from dict
            if not history:
                del st["users"][uid]
                return

            history.append(now)
            if len(history) > st["limit"]:
                try:
                    chat = await event.get_input_chat()
                    target = await event.get_input_sender()
                    await client(EditBannedRequest(
                        channel=chat,
                        user_id=target,
                        banned_rights=ChatBannedRights(
                            until_date=int(now) + 3600,  # 1h
                            view_messages=False,
                            send_messages=True,
                            send_media=True,
                            send_stickers=True,
                            send_gifs=True,
                            send_games=True,
                            send_inline=True,
                            embed_links=True,
                            send_polls=True,
                        ),
                    ))
                    await event.reply(
                        f"🛑 **Flood detected** — muted `{uid}` for 1h.")
                except (UserAdminInvalidError, ChatAdminRequiredError):
                    pass
                except Exception:
                    pass
                finally:
                    history.clear()
        except Exception:
            pass

    # Mark module as registered
    client._admin_module_loaded = True