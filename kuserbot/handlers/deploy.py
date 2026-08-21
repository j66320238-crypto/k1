"""
handlers/deploy.py
==================
Handles the deployment of Worker Bots to remote SSH servers.
Strictly restricted to the Special Admin.
"""

import json
import os
import logging
from typing import Optional, Dict, Any

from aiogram import Router, F
from aiogram.filters import Command, CommandObject, BaseFilter
from aiogram.types import Message

from config import SPECIAL_ADMIN_ID, API_ID, API_HASH, SERVERS_JSON_PATH
from database import db
from encryption import DataEncryptor
from utils.ssh_connector import SSHManager

logger = logging.getLogger(__name__)
router = Router()


# ────────────────────────────────────────────────
# Custom Filter: IsSpecialAdmin
# ────────────────────────────────────────────────
class IsSpecialAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        return event.from_user and event.from_user.id == SPECIAL_ADMIN_ID

# Apply filter to all routes in this router
router.message.filter(IsSpecialAdmin())


# ────────────────────────────────────────────────
# Helper: Load Servers from JSON
# ────────────────────────────────────────────────
def _load_servers() -> list:
    if not os.path.exists(SERVERS_JSON_PATH):
        return []
    try:
        with open(SERVERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


# ────────────────────────────────────────────────
# Command: /deploy <user_id>
# ────────────────────────────────────────────────
@router.message(Command("deploy"))
async def deploy_userbot_handler(message: Message, command: CommandObject):
    """
    Deploys the worker bot for a specific user onto an available SSH server.
    Usage: /deploy <user_id>
    """
    if not command.args:
        return await message.reply("❌ Usage: <code>/deploy &lt;user_id&gt;</code>")
    
    try:
        target_user_id = int(command.args.strip())
    except ValueError:
        return await message.reply("❌ Invalid User ID. Must be an integer.")

    # 1. Fetch User Data from DB
    user_data = await db.get_user(target_user_id)
    if not user_data:
        return await message.reply("❌ User not found in database.")
    
    session_string = user_data.get("session_string")
    if not session_string:
        return await message.reply("❌ User does not have an active session string.")

    # NEW (v3.1): sessions are stored encrypted — decrypt for deployment,
    # falling back to the raw value for legacy (pre-encryption) rows.
    session_string = DataEncryptor.decrypt(session_string) or session_string

    # 2. Fetch Available SSH Servers
    servers = _load_servers()
    if not servers:
        return await message.reply("❌ No SSH servers configured. Use the SSH Dashboard to add one.")

    # Pick the first available server (Basic Load Balancing)
    server = servers[0]
    host = server.get("host")
    username = server.get("username")
    password = server.get("password")
    port = server.get("port", 22)

    status_msg = await message.reply(f"🚀 Starting deployment for user <code>{target_user_id}</code> on <code>{host}</code>...")

    # 3. Initialize SSH Manager
    ssh = SSHManager(host, username, password, port)
    try:
        if not await ssh.connect():
            return await status_msg.edit_text(f"❌ SSH authentication failed for <code>{host}</code>.")

        # 4. Upload Worker Bot Files
        await status_msg.edit_text("📦 Uploading worker_bot files ...")
        # Assuming the worker_bot directory is in the same root as the master bot
        await ssh.deploy_worker_bot("./worker_bot")

        # 5. Install Requirements
        await status_msg.edit_text("📥 Installing requirements (Telethon, etc.) ...")
        res = await ssh.install_requirements()
        if not res.ok:
            err_msg = res.stderr[:1000] if res.stderr else "Unknown error"
            return await status_msg.edit_text(f"⚠️ pip install failed:\n<code>{err_msg}</code>")

        # 6. Start Userbot
        await status_msg.edit_text("🟢 Starting userbot in background ...")
        pid = await ssh.start_userbot(session_string, API_ID, API_HASH)
        
        if pid:
            await status_msg.edit_text(
                f"✅ <b>Deployment Successful!</b>\n\n"
                f"👤 <b>User:</b> <code>{target_user_id}</code>\n"
                f"🖥 <b>Server:</b> <code>{host}</code>\n"
                f"🆔 <b>PID:</b> <code>{pid}</code>"
            )
        else:
            await status_msg.edit_text(
                "⚠️ Userbot started, but failed to capture PID. Check logs via SSH."
            )
            
    except Exception as e:
        logger.exception("Deployment failed")
        await status_msg.edit_text(f"❌ Deployment crashed:\n<code>{str(e)[:1000]}</code>")
    finally:
        await ssh.close()


# ────────────────────────────────────────────────
# Command: /servers — list all SSH servers
# ────────────────────────────────────────────────
@router.message(Command("servers"))
async def list_servers_handler(message: Message):
    """List every configured SSH server."""
    servers = _load_servers()
    if not servers:
        return await message.reply(
            "📭 No SSH servers configured.\nUse the SSH Dashboard (/ssh) to add one."
        )

    lines = ["🖥 <b>Configured SSH Servers</b>\n"]
    for i, srv in enumerate(servers, start=1):
        host = srv.get("host", "?")
        user = srv.get("username", "?")
        port = srv.get("port", 22)
        lines.append(
            f"<b>{i}.</b> <code>{user}@{host}:{port}</code>"
        )
    lines.append(f"\n📦 Total: <b>{len(servers)}</b>")
    await message.reply("\n".join(lines))


# ────────────────────────────────────────────────
# Command: /logs <host> — tail the userbot log
# ────────────────────────────────────────────────
@router.message(Command("logs"))
async def logs_handler(message: Message, command: CommandObject):
    """Tail the last lines of the userbot log on a server.
    Usage: /logs <host> [lines]
    """
    args = (command.args or "").strip().split()
    if not args:
        return await message.reply(
            "❌ Usage: <code>/logs &lt;host&gt; [lines]</code>"
        )

    host = args[0]
    lines_n = 30
    if len(args) > 1:
        try:
            lines_n = max(1, min(int(args[1]), 100))
        except ValueError:
            pass

    server = next(
        (s for s in _load_servers() if s.get("host") == host), None
    )
    if not server:
        return await message.reply(f"❌ Server <code>{host}</code> not found.")

    status = await message.reply(f"📂 Reading log from <code>{host}</code>…")

    ssh = SSHManager(
        server.get("host"), server.get("username"),
        server.get("password"), server.get("port", 22),
    )
    try:
        if not await ssh.connect():
            return await status.edit_text(f"❌ SSH connection failed for <code>{host}</code>.")

        log_text = await ssh.tail_log(lines_n)
        if not log_text or not log_text.strip():
            return await status.edit_text(
                f"📭 <code>{host}</code> has no <code>worker_bot/userbot.log</code> yet — "
                f"the userbot has probably never been started there."
            )

        # Keep Telegram happy: cap length, escape HTML via <pre>
        snippet = log_text[-3500:]
        await status.edit_text(
            f"📂 <b>Log — {host}</b> (last {lines_n} lines)\n"
            f"<pre>{snippet}</pre>"
        )
    except Exception as e:
        logger.exception("Log fetch failed")
        await status.edit_text(f"❌ Failed: <code>{str(e)[:500]}</code>")
    finally:
        await ssh.close()


# ────────────────────────────────────────────────
# Command: /syncssh
# ────────────────────────────────────────────────
@router.message(Command("syncssh"))
async def sync_ssh_handler(message: Message):
    """
    Syncs the latest worker_bot files to ALL SSH servers without starting the bot.
    Useful for updating modules.
    """
    servers = _load_servers()
    if not servers:
        return await message.reply("❌ No SSH servers configured.")

    status_msg = await message.reply("🔄 Starting synchronization to all servers...")

    for server in servers:
        host = server.get("host")
        username = server.get("username")
        password = server.get("password")
        port = server.get("port", 22)
        
        ssh = SSHManager(host, username, password, port)
        try:
            await status_msg.edit_text(f"🔄 Syncing to <code>{host}</code>...")
            if await ssh.connect():
                await ssh.deploy_worker_bot("./worker_bot")
                await message.answer(f"✅ Synced: <code>{host}</code>")
            else:
                await message.answer(f"❌ SSH Failed: <code>{host}</code>")
        except Exception as e:
            await message.answer(f"❌ Error on <code>{host}</code>: {str(e)[:100]}")
        finally:
            await ssh.close()
            
    await status_msg.edit_text("✅ Synchronization process completed.")