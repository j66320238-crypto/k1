# worker_bot/modules/info.py
"""
Info Module — User information, name history, and related utilities.

Commands:
    .id           — Basic user info (ID, name, username, premium).
    .info         — Detailed user info (bio, flags, DC, common chats count).
    .sg           — Name history via @SangMata_BOT (alias: .namehistory).
    .namehistory  — Alias for .sg.
    .common       — Common chats with the replied user.
    .pfp / .pp    — Fetch and send the replied user's profile photo.
    .uname        — Just the username (or "no username").
    .dc           — Data-centre info of the replied user.
    .me           — Full info about *yourself*.

Designed to be loaded dynamically by ``userbot.py``.
"""

import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetCommonChatsRequest


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

def _safe(obj, attr, default=None):
    """Buller-proof ``getattr``."""
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


_DC_LOCATIONS = {
    1: "Miami, USA",
    2: "Amsterdam, Netherlands",
    3: "Miami, USA",
    4: "Amsterdam, Netherlands",
    5: "Singapore",
}


def _format_card(user, full_user=None, detailed=False):
    """Build a nicely-formatted info card string."""

    user_id   = user.id
    fname     = user.first_name or "—"
    lname     = user.last_name  or "—"
    username  = f"@{user.username}" if user.username else "—"
    mention   = f"[{fname or 'User'}](tg://user?id={user_id})"

    is_premium    = _safe(user, "premium", False) or _safe(user, "is_premium", False)
    is_bot        = _safe(user, "bot", False)
    is_verified   = _safe(user, "verified", False)
    is_restricted = _safe(user, "restricted", False)
    is_scam       = _safe(user, "scam", False)
    is_fake       = _safe(user, "fake", False)
    is_support    = _safe(user, "support", False)

    lines = [
        "┌──────────────────────────┐",
        "│   👤  USER INFORMATION   │",
        "└──────────────────────────┘",
        "",
        f"🆔  **ID**         : `{user_id}`",
        f"👤  **First Name** : {fname}",
        f"👥  **Last Name**  : {lname}",
        f"📛  **Username**   : {username}",
        f"🔗  **Mention**    : {mention}",
        f"⭐  **Premium**    : {'✅ Yes' if is_premium else '❌ No'}",
    ]

    if detailed:
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🤖  **Bot**        : {'✅' if is_bot else '❌'}",
            f"✔️  **Verified**   : {'✅' if is_verified else '❌'}",
            f"🚫  **Restricted** : {'⚠️ Yes' if is_restricted else '✅ No'}",
            f"🎭  **Scam**       : {'⚠️ Yes' if is_scam else '✅ No'}",
            f"👻  **Fake**       : {'⚠️ Yes' if is_fake else '✅ No'}",
            f"🛠️  **Support**    : {'✅' if is_support else '❌'}",
        ]

        if full_user:
            about = _safe(full_user, "about", None) or "—"
            lines.append(f"📝  **Bio**        : {about}")

            common_count = _safe(full_user, "common_chats_count", 0)
            lines.append(f"💬  **Common Chats**: {common_count}")

            has_photo = bool(_safe(full_user, "profile_photo", None))
            lines.append(f"🖼️  **Photo**      : {'✅' if has_photo else '❌'}")

            calls_ok  = _safe(full_user, "phone_calls_available", False)
            calls_priv = _safe(full_user, "phone_calls_private", False)
            lines.append(f"📞  **Calls OK**   : {'✅' if calls_ok else '❌'}")
            lines.append(f"🔒  **Calls Priv** : {'✅' if calls_priv else '❌'}")

            settings = _safe(full_user, "settings", None)
            if settings:
                auto_arch = _safe(settings, "auto_archived", False)
                lines.append(f"🗄️  **Auto-Archive**: {'✅' if auto_arch else '❌'}")

        # DC
        photo = _safe(user, "photo", None)
        dc_id = _safe(photo, "dc_id", None) if photo else None
        if dc_id:
            loc = _DC_LOCATIONS.get(dc_id, "Unknown")
            lines.append(f"🌍  **DC**         : `{dc_id}` ({loc})")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def _resolve_target(event):
    """Return ``(target_input_entity, reply_msg)`` or ``(None, None)``."""
    reply = await event.get_reply_message()
    if not reply:
        return None, None
    try:
        target = await reply.get_input_entity()
    except Exception:
        return None, reply
    return target, reply


async def _fetch_full_user(client, target):
    """Best-effort ``GetFullUserRequest`` — never raises."""
    try:
        result = await client(GetFullUserRequest(target))
        return result.full_user if result else None
    except FloodWaitError as fe:
        await asyncio.sleep(fe.seconds + 1)
        try:
            result = await client(GetFullUserRequest(target))
            return result.full_user if result else None
        except Exception:
            return None
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
#  Register
# ──────────────────────────────────────────────────────────────

def register(client):
    """Register every command exposed by this module."""

    # ── .id ────────────────────────────────────────────────
    @client.flood_safe
    async def _id_handler(event):
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            await event.reply(_format_card(user, detailed=False),
                              link_preview=False)
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .info ──────────────────────────────────────────────
    @client.flood_safe
    async def _info_handler(event):
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            full_user = await _fetch_full_user(client, target)
            await event.reply(_format_card(user, full_user, detailed=True),
                              link_preview=False)
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .sg  /  .namehistory ──────────────────────────────
    @client.flood_safe
    async def _sg_handler(event):
        status_msg = None
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
                user_id = str(user.id)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            status_msg = await event.reply(
                "⏳ **Querying @SangMata_BOT …**"
            )

            # Resolve SangMata entity (fall back to raw username).
            try:
                sm_entity = await client.get_entity("@SangMata_BOT")
            except Exception:
                sm_entity = "@SangMata_BOT"

            # Send the user-ID to SangMata.
            try:
                await client.send_message(sm_entity, user_id)
            except Exception as e:
                await status_msg.edit(
                    f"❌ **Cannot reach @SangMata_BOT.**\n`{e}`"
                )
                return

            # Wait for SangMata's reply (10 s timeout).
            try:
                async with client.conversation(sm_entity, timeout=10) as conv:
                    try:
                        resp = await conv.get_response(timeout=10)
                    except asyncio.TimeoutError:
                        await status_msg.edit(
                            "⏰ **@SangMata_BOT did not reply within 10 s. "
                            "It may be offline or rate-limited.**"
                        )
                        return

                    if not resp or not resp.message:
                        await status_msg.edit(
                            "❌ **SangMata returned an empty response.**"
                        )
                        return

                    text = resp.message.strip()

                    # If SangMata asks to /start first, do it & retry once.
                    low = text.lower()
                    if ("/start" in low
                            and len(text) < 300
                            and "name" not in low
                            and "history" not in low):
                        try:
                            await conv.send_message("/start")
                            await asyncio.sleep(1.5)
                            await conv.send_message(user_id)
                            resp2 = await conv.get_response(timeout=10)
                            if resp2 and resp2.message:
                                text = resp2.message.strip()
                        except Exception:
                            pass  # keep the original text

                    await status_msg.edit(
                        f"📜 **Name History** — `{user_id}`\n\n{text}",
                        link_preview=False,
                    )

            except asyncio.TimeoutError:
                await status_msg.edit(
                    "⏰ **Timed out waiting for @SangMata_BOT.**"
                )
            except Exception as e:
                msg = str(e).lower()
                if "timeout" in msg or "wait" in msg:
                    await status_msg.edit(
                        "⏰ **Timed out waiting for @SangMata_BOT.**"
                    )
                else:
                    await status_msg.edit(
                        f"❌ **SangMata conversation failed:**\n`{e}`"
                    )
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                if status_msg:
                    await status_msg.edit(f"❌ **Unexpected error:**\n`{e}`")
                else:
                    await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .common ────────────────────────────────────────────
    @client.flood_safe
    async def _common_handler(event):
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            status_msg = await event.reply("⏳ **Fetching common chats …**")

            try:
                result = await client(
                    GetCommonChatsRequest(user.id, max_id=0, limit=100)
                )
                chats = result.chats if result else []

                if not chats:
                    await status_msg.edit(
                        f"🤷 **No common chats with** `{user.id}`."
                    )
                    return

                lines = [f"💬 **Common Chats with** `{user.id}`", ""]
                for c in chats[:30]:
                    title = _safe(c, "title", "Untitled")
                    cid   = _safe(c, "id", 0)
                    lines.append(f"• **{title}**  (`{cid}`)")

                if len(chats) > 30:
                    lines.append(f"\n_…and {len(chats) - 30} more._")

                await status_msg.edit("\n".join(lines), link_preview=False)
            except Exception as e:
                await status_msg.edit(
                    f"❌ **Failed to fetch common chats:**\n`{e}`"
                )
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .pfp / .pp ─────────────────────────────────────────
    @client.flood_safe
    async def _pfp_handler(event):
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            try:
                photos = await client.get_profile_photos(user)
            except Exception as e:
                await event.reply(f"❌ **Cannot fetch photos:**\n`{e}`")
                return

            if not photos:
                await event.reply("❌ **This user has no profile photo.**")
                return

            await event.reply(file=photos[0])
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .uname ─────────────────────────────────────────────
    @client.flood_safe
    async def _uname_handler(event):
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            if user.username:
                await event.reply(
                    f"📛 **Username:** @{user.username}\n🆔 **ID:** `{user.id}`"
                )
            else:
                await event.reply(
                    f"❌ **No username set.**\n🆔 **ID:** `{user.id}`"
                )
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .dc ────────────────────────────────────────────────
    @client.flood_safe
    async def _dc_handler(event):
        try:
            chat = await event.get_input_chat()
            target, reply = await _resolve_target(event)
            if not target:
                await event.reply("❌ **Reply to a user's message first.**")
                return

            try:
                user = await client.get_entity(target)
            except Exception as e:
                await event.reply(f"❌ **Could not fetch user:**\n`{e}`")
                return

            photo = _safe(user, "photo", None)
            dc_id = _safe(photo, "dc_id", None) if photo else None

            if dc_id:
                loc = _DC_LOCATIONS.get(dc_id, "Unknown")
                await event.reply(
                    "🌍 **Data-Centre Info**\n\n"
                    f"🆔 **User ID** : `{user.id}`\n"
                    f"🖥️ **DC ID**   : `{dc_id}`\n"
                    f"📍 **Location**: {loc}",
                    link_preview=False,
                )
            else:
                await event.reply(
                    f"❌ **No DC info available.**\n🆔 **ID:** `{user.id}`"
                )
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ── .me ────────────────────────────────────────────────
    @client.flood_safe
    async def _me_handler(event):
        try:
            chat = await event.get_input_chat()
            me = await client.get_me()
            full_user = await _fetch_full_user(client, "me")
            await event.reply(_format_card(me, full_user, detailed=True),
                              link_preview=False)
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            try:
                await event.reply(f"❌ **Unexpected error:**\n`{e}`")
            except Exception:
                pass

    # ───────────────────────────────────────────────────────
    #  Wire-up
    # ───────────────────────────────────────────────────────
    _PAT = {
        _id_handler:     [r"^\.id$",          r"^\.id\s"],
        _info_handler:   [r"^\.info$",        r"^\.info\s"],
        _sg_handler:     [r"^\.sg$",          r"^\.sg\s",
                          r"^\.namehistory$", r"^\.namehistory\s"],
        _common_handler: [r"^\.common$",      r"^\.common\s"],
        _pfp_handler:    [r"^\.pfp$",         r"^\.pfp\s",
                          r"^\.pp$",          r"^\.pp\s"],
        _uname_handler:  [r"^\.uname$",       r"^\.uname\s"],
        _dc_handler:     [r"^\.dc$",          r"^\.dc\s"],
        _me_handler:     [r"^\.me$",          r"^\.me\s"],
    }

    for handler, patterns in _PAT.items():
        for pat in patterns:
            client.add_event_handler(
                handler,
                events.NewMessage(pattern=pat, outgoing=True),
            )

    # Log
    try:
        client._logger.info(  # type: ignore[attr-defined]
            "[info] Registered %d commands.", len(_PAT)
        )
    except Exception:
        pass