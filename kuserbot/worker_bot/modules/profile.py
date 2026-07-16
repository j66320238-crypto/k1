# worker_bot/modules/profile.py
# Profile cloning, media saving and view-once capture module
# Dynamically loaded by userbot.py

import asyncio
import base64
import json
import os
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument


# ---------- Constants ----------
PROFILES_FILE = "profiles_data.json"
DEFAULT_NAME = "Userbot"


# ---------- JSON helpers ----------
def _load_profiles() -> dict:
    """Load saved profiles from JSON file."""
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_profiles(data: dict) -> bool:
    """Persist profiles dict to JSON file."""
    try:
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"[profile._save_profiles] Failed: {e}")
        return False


def _is_view_once(message) -> bool:
    """Check if a message contains view-once / TTL media."""
    try:
        if message and message.media:
            if hasattr(message.media, "ttl_seconds") and message.media.ttl_seconds:
                return True
    except Exception:
        return False
    return False


# ---------- Register ----------
def register(client):
    """Register all profile module handlers onto the given client."""

    # Persistent VO state on client
    if not hasattr(client, "vo_enabled"):
        client.vo_enabled = False

    # =====================================================================
    # .clone  —  Reply to a user to clone their pfp, name, bio
    # =====================================================================
    @client.flood_safe
    async def clone_handler(event):
        if not event.is_reply:
            await event.edit("`➤ Reply to a user to clone their profile.`")
            return

        chat = await event.get_input_chat()
        reply = await event.get_reply_message()
        if reply is None:
            await event.edit("`➤ Could not fetch replied message.`")
            return

        try:
            target = await reply.get_input_entity()
        except Exception as e:
            await event.edit(f"`➤ Failed to get target entity: {e}`")
            return

        await event.edit("`➤ Cloning profile in progress...`")
        photo_path = None
        try:
            full = await client(GetFullUserRequest(target))
            user_info = full.users[0]
            user_full = full.full_user

            first_name = user_info.first_name or ""
            last_name = user_info.last_name or ""
            bio = user_full.bio or ""

            me = await client.get_input_entity("me")

            # Download their profile photo
            try:
                photo_path = await client.download_profile_photo(
                    target, file="profile_clone_temp.jpg"
                )
            except Exception as e:
                print(f"[profile.clone] Photo download failed: {e}")
                photo_path = None

            # Backup original photo to Saved Messages
            if photo_path and os.path.exists(photo_path):
                backup_caption = (
                    f"👤 **Cloned Profile Backup**\n"
                    f"**Name:** {first_name} {last_name}\n"
                    f"**Bio:** {bio or 'N/A'}\n"
                    f"**User ID:** `{user_info.id}`"
                )
                try:
                    await client.send_file(me, photo_path, caption=backup_caption)
                except Exception as e:
                    print(f"[profile.clone] Backup send failed: {e}")

            # Update name + bio
            await client(UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name,
                about=bio,
            ))

            # Update profile photo
            if photo_path and os.path.exists(photo_path):
                try:
                    existing = await client.get_profile_photos("me")
                    if existing:
                        # Fixed: Using friendly method instead of DeletePhotosRequest
                        await client.delete_photos([p.id for p in existing])
                except Exception as e:
                    print(f"[profile.clone] Old photo delete failed: {e}")
                try:
                    file_obj = await client.upload_file(photo_path)
                    await client(UploadProfilePhotoRequest(file=file_obj))
                except Exception as e:
                    print(f"[profile.clone] New photo upload failed: {e}")

            await event.edit(
                f"`✅ Profile cloned successfully!\n"
                f"Name: {first_name} {last_name}\n"
                f"Bio: {bio or 'N/A'}`"
            )
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Clone error: {e}`")
        finally:
            if photo_path and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass

    # =====================================================================
    # .revert  —  Reset to default profile
    # =====================================================================
    @client.flood_safe
    async def revert_handler(event):
        chat = await event.get_input_chat()
        await event.edit("`➤ Reverting to default profile...`")
        try:
            await client(UpdateProfileRequest(
                first_name=DEFAULT_NAME,
                last_name="",
                about="",
            ))
            try:
                existing = await client.get_profile_photos("me")
                if existing:
                    # Fixed: Using friendly method instead of DeletePhotosRequest
                    await client.delete_photos([p.id for p in existing])
            except Exception as e:
                print(f"[profile.revert] Delete photos failed: {e}")

            await event.edit(f"`✅ Reverted to default profile ({DEFAULT_NAME})`")
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Revert error: {e}`")

    # =====================================================================
    # .saveprofile <name>  —  Save a user's profile to JSON
    # =====================================================================
    @client.flood_safe
    async def saveprofile_handler(event):
        if not event.is_reply:
            await event.edit("`➤ Reply to a user to save their profile.`")
            return

        chat = await event.get_input_chat()
        reply = await event.get_reply_message()
        if reply is None:
            await event.edit("`➤ Could not fetch replied message.`")
            return

        try:
            target = await reply.get_input_entity()
        except Exception as e:
            await event.edit(f"`➤ Failed to get target entity: {e}`")
            return

        raw_args = event.pattern_match.group(1)
        args = raw_args.strip() if raw_args else ""

        if not args:
            data = _load_profiles()
            args = str(len(data) + 1)

        await event.edit(f"`➤ Saving profile as '{args}'...`")
        photo_path = None
        try:
            full = await client(GetFullUserRequest(target))
            user_info = full.users[0]
            user_full = full.full_user

            first_name = user_info.first_name or ""
            last_name = user_info.last_name or ""
            bio = user_full.bio or ""

            try:
                photo_path = await client.download_profile_photo(
                    target, file=f"profile_save_{args}.jpg"
                )
            except Exception as e:
                print(f"[profile.saveprofile] Photo download failed: {e}")
                photo_path = None

            photo_b64 = None
            if photo_path and os.path.exists(photo_path):
                try:
                    with open(photo_path, "rb") as f:
                        photo_b64 = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    print(f"[profile.saveprofile] Photo encode failed: {e}")

            data = _load_profiles()
            data[args] = {
                "first_name": first_name,
                "last_name": last_name,
                "bio": bio,
                "user_id": user_info.id,
                "photo": photo_b64,
            }
            _save_profiles(data)

            await event.edit(
                f"`✅ Profile saved as '{args}'\n"
                f"Name: {first_name} {last_name}\n"
                f"Bio: {bio or 'N/A'}`"
            )
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Save error: {e}`")
        finally:
            if photo_path and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass

    # =====================================================================
    # .loadprofile <name>  —  Load a saved profile from JSON
    # =====================================================================
    @client.flood_safe
    async def loadprofile_handler(event):
        raw_args = event.pattern_match.group(1)
        args = raw_args.strip() if raw_args else ""
        if not args:
            await event.edit("`➤ Usage: .loadprofile <name>`")
            return

        chat = await event.get_input_chat()
        data = _load_profiles()
        if args not in data:
            await event.edit(f"`➤ No saved profile named '{args}' found.`")
            return

        profile = data[args]
        await event.edit(f"`➤ Loading profile '{args}'...`")
        temp_photo = None
        try:
            await client(UpdateProfileRequest(
                first_name=profile.get("first_name", ""),
                last_name=profile.get("last_name", ""),
                about=profile.get("bio", ""),
            ))

            photo_b64 = profile.get("photo")
            if photo_b64:
                temp_photo = f"profile_load_{args}.jpg"
                try:
                    with open(temp_photo, "wb") as f:
                        f.write(base64.b64decode(photo_b64))
                    existing = await client.get_profile_photos("me")
                    if existing:
                        # Fixed: Using friendly method instead of DeletePhotosRequest
                        await client.delete_photos([p.id for p in existing])
                    file_obj = await client.upload_file(temp_photo)
                    await client(UploadProfilePhotoRequest(file=file_obj))
                except Exception as e:
                    print(f"[profile.loadprofile] Photo apply failed: {e}")

            await event.edit(f"`✅ Loaded profile '{args}'`")
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Load error: {e}`")
        finally:
            if temp_photo and os.path.exists(temp_photo):
                try:
                    os.remove(temp_photo)
                except OSError:
                    pass

    # =====================================================================
    # .savedprofiles  —  List all saved profiles
    # =====================================================================
    @client.flood_safe
    async def savedprofiles_handler(event):
        chat = await event.get_input_chat()
        data = _load_profiles()
        if not data:
            await event.edit("`➤ No saved profiles found.`")
            return

        text = "**📁 Saved Profiles:**\n\n"
        for name, info in data.items():
            fname = info.get("first_name", "")
            lname = info.get("last_name", "")
            text += f"• **{name}** — {fname} {lname}\n"
        await event.edit(text)

    # =====================================================================
    # .vo on | off | status  —  Toggle view-once media saving
    # =====================================================================
    @client.flood_safe
    async def vo_handler(event):
        chat = await event.get_input_chat()
        raw_arg = event.pattern_match.group(1)
        arg = (raw_arg.strip().lower() if raw_arg else "") or "status"

        if arg in ("on", "enable", "true", "1"):
            client.vo_enabled = True
            await event.edit("`✅ View-Once media saving is now ON.`")
        elif arg in ("off", "disable", "false", "0"):
            client.vo_enabled = False
            await event.edit("`✅ View-Once media saving is now OFF.`")
        else:
            status = "ON ✅" if client.vo_enabled else "OFF ❌"
            await event.edit(f"`➤ View-Once media saving: {status}`")

    # =====================================================================
    # Background watcher for view-once media
    # =====================================================================
    async def vo_watcher(event):
        try:
            if not client.vo_enabled:
                return
            if event.out:
                return
            if not _is_view_once(event.message):
                return

            chat = await event.get_input_chat()
            me = await client.get_input_entity("me")
            sender = await event.get_sender()
            sender_id = sender.id if sender else "Unknown"

            sender_name = ""
            if sender:
                first = getattr(sender, "first_name", "") or ""
                last = getattr(sender, "last_name", "") or ""
                sender_name = f"{first} {last}".strip() or str(sender_id)

            timestamp = (
                event.message.date.strftime("%Y-%m-%d %H:%M:%S")
                if event.message.date else "Unknown"
            )

            media_type = (
                "Photo" if isinstance(event.message.media, MessageMediaPhoto)
                else "Video/Document"
            )

            try:
                downloaded = await client.download_media(event.message)
            except Exception as e:
                print(f"[profile.vo_watcher] Download failed: {e}")
                return

            if not downloaded:
                print("[profile.vo_watcher] No media returned.")
                return

            caption = (
                f"👁️ **View-Once {media_type} Saved**\n"
                f"**Sender:** {sender_name} (`{sender_id}`)\n"
                f"**Time:** {timestamp}"
            )

            try:
                await client.send_file(me, downloaded, caption=caption)
            except Exception as e:
                print(f"[profile.vo_watcher] Send to Saved Messages failed: {e}")
            finally:
                try:
                    if isinstance(downloaded, str) and os.path.exists(downloaded):
                        os.remove(downloaded)
                except OSError:
                    pass
        except Exception as e:
            print(f"[profile.vo_watcher] General error: {e}")

    # =====================================================================
    # Bonus commands (improvements)
    # =====================================================================
    @client.flood_safe
    async def setname_handler(event):
        raw_args = event.pattern_match.group(1)
        args = raw_args.strip() if raw_args else ""
        if not args:
            await event.edit("`➤ Usage: .setname <first_name> [last_name]`")
            return
        chat = await event.get_input_chat()
        parts = args.split(None, 1)
        first = parts[0][:64]
        last = parts[1][:64] if len(parts) > 1 else ""
        try:
            await client(UpdateProfileRequest(first_name=first, last_name=last))
            await event.edit(f"`✅ Name set to: {first} {last}`".strip())
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Error: {e}`")

    @client.flood_safe
    async def setbio_handler(event):
        raw_args = event.pattern_match.group(1)
        args = raw_args.strip() if raw_args else ""
        if not args:
            await event.edit("`➤ Usage: .setbio <text>`")
            return
        chat = await event.get_input_chat()
        try:
            await client(UpdateProfileRequest(about=args[:70]))
            await event.edit("`✅ Bio updated.`")
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Error: {e}`")

    @client.flood_safe
    async def delpfp_handler(event):
        chat = await event.get_input_chat()
        try:
            existing = await client.get_profile_photos("me")
            if not existing:
                await event.edit("`➤ No profile photos to delete.`")
                return
            # Fixed: Using friendly method instead of DeletePhotosRequest
            await client.delete_photos([p.id for p in existing])
            await event.edit(f"`✅ Deleted {len(existing)} profile photo(s).`")
        except FloodWaitError as e:
            await event.edit(f"`⏳ FloodWait: {e.seconds}s`")
        except Exception as e:
            await event.edit(f"`❌ Error: {e}`")

    @client.flood_safe
    async def delprofile_handler(event):
        raw_args = event.pattern_match.group(1)
        args = raw_args.strip() if raw_args else ""
        if not args:
            await event.edit("`➤ Usage: .delprofile <name>`")
            return
        chat = await event.get_input_chat()
        data = _load_profiles()
        if args not in data:
            await event.edit(f"`➤ No saved profile named '{args}' found.`")
            return
        del data[args]
        _save_profiles(data)
        await event.edit(f"`✅ Deleted saved profile '{args}'`")

    # =====================================================================
    # Bind all handlers
    # =====================================================================
    client.add_event_handler(
        clone_handler,
        events.NewMessage(pattern=r"^\.clone(?:\s+(.*))?$")
    )
    client.add_event_handler(
        revert_handler,
        events.NewMessage(pattern=r"^\.revert(?:\s+(.*))?$")
    )
    client.add_event_handler(
        saveprofile_handler,
        events.NewMessage(pattern=r"^\.saveprofile(?:\s+(.*))?$")
    )
    client.add_event_handler(
        loadprofile_handler,
        events.NewMessage(pattern=r"^\.loadprofile(?:\s+(.*))?$")
    )
    client.add_event_handler(
        savedprofiles_handler,
        events.NewMessage(pattern=r"^\.savedprofiles$")
    )
    client.add_event_handler(
        vo_handler,
        events.NewMessage(pattern=r"^\.vo(?:\s+(on|off|status))?$")
    )
    client.add_event_handler(
        vo_watcher,
        events.NewMessage()
    )
    client.add_event_handler(
        setname_handler,
        events.NewMessage(pattern=r"^\.setname(?:\s+(.*))?$")
    )
    client.add_event_handler(
        setbio_handler,
        events.NewMessage(pattern=r"^\.setbio(?:\s+(.*))?$")
    )
    client.add_event_handler(
        delpfp_handler,
        events.NewMessage(pattern=r"^\.delpfp$")
    )
    client.add_event_handler(
        delprofile_handler,
        events.NewMessage(pattern=r"^\.delprofile(?:\s+(.*))?$")
    )

    print(
        "[Module] profile.py loaded — "
        ".clone .revert .saveprofile .loadprofile .savedprofiles "
        ".vo .setname .setbio .delpfp .delprofile"
    )