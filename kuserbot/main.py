"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║   ██████   ███   ██  ██████  ███████ ███████     ██████  ██   ██         ║
║   ██   ██  ████  ██ ██    ██ ██      ██          ██   ██ ██   ██         ║
║   ██████   ██ ██ ██ ██    ██ █████   ███████     ██████  ███████         ║
║   ██   ██  ██  ██ ██ ██    ██ ██           ██     ██   ██ ██   ██         ║
║   ██████   ██   ████  ██████  ███████ ███████     ██████  ██   ██         ║
║                                                                          ║
║   PHANTOM-X — Premium Telegram Bot Powered by Aiogram v3.x               ║
║   © 2024 All Rights Reserved                                            ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

main.py — Entry Point
─────────────────────
• Initializes the Bot & Dispatcher (Aiogram v3.x)
• Sets up database connections
• Registers all routers in conflict-free order
• Provides premium console output with ASCII art
• Handles graceful startup / shutdown lifecycle
• Global error handler with admin notification
• FSM storage for dynamic help & support flows
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import ErrorEvent, Update

# ──────────────────────────────────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────────────────────────────────
from config import BOT_TOKEN, ADMIN_IDS, SPECIAL_ADMIN_ID

# ──────────────────────────────────────────────────────────────────────────
#  Routers — imported from individual handler modules
# ──────────────────────────────────────────────────────────────────────────
from handlers.user import router as user_router
from handlers.normal_admin import router as normal_admin_router
from handlers.special_admin import router as special_admin_router
from handlers.ssh_manager import router as ssh_manager_router
from handlers.deploy import router as deploy_router  # <-- NEW: deploy router

# ──────────────────────────────────────────────────────────────────────────
#  Database
# ──────────────────────────────────────────────────────────────────────────
from database import db

# ──────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────
BOT_VERSION: str = "3.0.0"
BOT_NAME: str = "PHANTOM-X"
logger = logging.getLogger("phantom_bot")

# ──────────────────────────────────────────────────────────────────────────
#  ANSI Colour Codes — for premium console output
# ──────────────────────────────────────────────────────────────────────────
class C:
    """ANSI terminal colour constants."""
    R = "\033[0m"       # reset
    B = "\033[1m"       # bold
    D = "\033[2m"       # dim
    RED = "\033[91m"
    GRN = "\033[92m"
    YEL = "\033[93m"
    BLU = "\033[94m"
    MAG = "\033[95m"
    CYN = "\033[96m"
    WHT = "\033[97m"


# ──────────────────────────────────────────────────────────────────────────
#  Logging Configuration
# ──────────────────────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    formatter = logging.Formatter(
        fmt=(
            f"{C.D}[%(asctime)s]{C.R} "
            f"{C.CYN}%(name)-22s{C.R} "
            f"{C.YEL}%(levelname)-7s{C.R} "
            f"%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(
            fmt="[%(asctime)s] %(name)-22s %(levelname)-7s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiogram.bot.api").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    return logging.getLogger("phantom_bot")


# ──────────────────────────────────────────────────────────────────────────
#  ASCII Art Banner
# ──────────────────────────────────────────────────────────────────────────
BANNER: str = rf"""
{C.CYN}{C.B}
  ██████╗ ██╗  ██╗ ██████╗ ███╗   ███╗███████╗██╗  ██╗ ██████╗ ███╗   ██╗
  ██╔══██╗██║  ██║██╔═══██╗████╗ ████║██╔════╝██║  ██║██╔═══██╗████╗  ██║
  ██████╔╝███████║██║   ██║██╔████╔██║███████╗██████╔╝██║   ██║██╔██╗ ██║
  ██╔═══╝ ██╔══██║██║   ██║██║╚██╔╝██║╚════██║██╔══██║██║   ██║██║╚██╗██║
  ██║     ██║  ██║╚██████╔╝██║ ╚═╝ ██║███████║██║  ██║╚██████╔╝██║ ╚████║
  ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
{C.R}
  {C.D}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}
  {C.GRN}●{C.R}  {C.B}PHANTOM-X{C.R} — Premium Telegram Userbot Master
  {C.GRN}●{C.R}  Powered by Aiogram v3.x  ·  English Only
  {C.D}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}
"""


def print_banner(logger: logging.Logger) -> None:
    print(BANNER)
    print(f"  {C.GRN}●{C.R} {C.B}Version    :{C.R} {BOT_VERSION}")
    print(f"  {C.GRN}●{C.R} {C.B}Admins     :{C.R} {len(ADMIN_IDS)} registered")
    print(f"  {C.GRN}●{C.R} {C.B}Special    :{C.R} {SPECIAL_ADMIN_ID}")
    print(f"  {C.GRN}●{C.R} {C.B}Started    :{C.R} {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  {C.D}{'─' * 63}{C.R}\n")


# ──────────────────────────────────────────────────────────────────────────
#  Router Registration
# ──────────────────────────────────────────────────────────────────────────
def register_routers(dp: Dispatcher, logger: logging.Logger) -> None:
    routers = [
        ("special_admin", special_admin_router),
        ("normal_admin",  normal_admin_router),
        ("user",          user_router),
        ("ssh_manager",   ssh_manager_router),
        ("deploy",        deploy_router),  # <-- NEW: deploy router
    ]

    for name, router in routers:
        dp.include_router(router)
        logger.info(f"  {C.GRN}✓{C.R} Router registered: {C.CYN}{name}{C.R}")

    logger.info(
        f"  {C.GRN}✓{C.R} {C.B}All routers active — "
        f"special_admin → normal_admin → user → ssh_manager → deploy{C.R}"  # <-- updated
    )


# ──────────────────────────────────────────────────────────────────────────
#  Lifecycle — Startup
# ──────────────────────────────────────────────────────────────────────────
async def on_startup(bot: Bot) -> None:
    try:
        await db.init()
        logger.info(f"{C.GRN}✓ Database initialised successfully.{C.R}")
    except Exception as exc:
        logger.error(f"{C.RED}✗ Database init failed: {exc}{C.R}")
        raise

    me = await bot.get_me()
    separator = "═" * 55

    logger.info(
        f"\n{C.GRN}{C.B}"
        f"  {separator}\n"
        f"  ║  🟢  BOT IS NOW ONLINE                          ║\n"
        f"  {separator}\n"
        f"  ║  Username : @{me.username}\n"
        f"  ║  Bot ID   : {me.id}\n"
        f"  ║  Name     : {me.first_name}\n"
        f"  ║  Version  : {BOT_VERSION}\n"
        f"  ║  Started  : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"  {separator}"
        f"{C.R}\n"
    )

    try:
        await bot.send_message(
            chat_id=SPECIAL_ADMIN_ID,
            text=(
                f"🟢 <b>{BOT_NAME} is Online</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <b>Bot:</b> @{me.username}\n"
                f"🆔 <b>ID:</b> <code>{me.id}</code>\n"
                f"📦 <b>Version:</b> <code>{BOT_VERSION}</code>\n"
                f"🕐 <b>Started:</b> <code>{datetime.now():%Y-%m-%d %H:%M:%S}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            ),
        )
        logger.info(f"{C.GRN}✓ Special Admin notified of startup.{C.R}")
    except TelegramForbiddenError:
        logger.warning(f"{C.YEL}⚠ Could not notify Special Admin (bot not started by user).{C.R}")
    except Exception as exc:
        logger.warning(f"{C.YEL}⚠ Special Admin notification skipped: {exc}{C.R}")


# ──────────────────────────────────────────────────────────────────────────
#  Lifecycle — Shutdown
# ──────────────────────────────────────────────────────────────────────────
async def on_shutdown(bot: Bot) -> None:
    logger.info(f"{C.YEL}⟳ Initiating graceful shutdown…{C.R}")

    try:
        await bot.send_message(
            chat_id=SPECIAL_ADMIN_ID,
            text=(
                f"🔴 <b>{BOT_NAME} is Offline</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🕐 <b>Stopped:</b> <code>{datetime.now():%Y-%m-%d %H:%M:%S}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            ),
        )
    except Exception:
        pass

    try:
        await db.close()
        logger.info(f"{C.GRN}✓ Database connections closed.{C.R}")
    except Exception as exc:
        logger.error(f"{C.RED}✗ Error closing database: {exc}{C.R}")

    try:
        await bot.session.close()
        logger.info(f"{C.GRN}✓ Bot aiohttp session closed.{C.R}")
    except Exception as exc:
        logger.error(f"{C.RED}✗ Error closing bot session: {exc}{C.R}")

    logger.info(f"{C.CYN}● {BOT_NAME} shut down gracefully.{C.R}")


# ──────────────────────────────────────────────────────────────────────────
#  Global Error Handler
# ──────────────────────────────────────────────────────────────────────────
async def global_error_handler(event: ErrorEvent, bot: Bot) -> None:
    logger = logging.getLogger("phantom_bot.errors")
    exception = event.exception
    update: Optional[Update] = event.update

    logger.error(
        f"{C.RED}✗ Unhandled Exception{C.R}\n"
        f"  {C.B}Type:{C.R}    {type(exception).__name__}\n"
        f"  {C.B}Message:{C.R} {exception}\n"
        f"  {C.B}Update:{C.R}  {update.model_dump_json(indent=2)[:300] if update else 'N/A'}"
    )
    logger.debug(f"Traceback:\n{traceback.format_exc()}")

    if isinstance(exception, TelegramRetryAfter):
        logger.warning(f"{C.YEL}⚠ Rate limited — retry after {exception.retry_after}s{C.R}")
        await asyncio.sleep(exception.retry_after + 1)
        return

    try:
        await bot.send_message(
            chat_id=SPECIAL_ADMIN_ID,
            text=(
                f"⚠️ <b>Error Occurred</b>\n\n"
                f"<b>Type:</b> <code>{type(exception).__name__}</code>\n"
                f"<b>Message:</b> <code>{str(exception)[:300]}</code>\n"
                f"<b>Time:</b> <code>{datetime.now():%Y-%m-%d %H:%M:%S}</code>"
            ),
        )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────
#  Main Entry Point
# ──────────────────────────────────────────────────────────────────────────
async def main() -> None:
    logger = setup_logging()
    print_banner(logger)
    logger.info(f"{C.CYN}● Initialising {BOT_NAME} v{BOT_VERSION}…{C.R}")

    if not BOT_TOKEN or not BOT_TOKEN.strip():
        logger.error(f"{C.RED}✗ BOT_TOKEN is not set in config.py!{C.R}")
        sys.exit(1)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )

    dp = Dispatcher(storage=MemoryStorage())

    logger.info(f"{C.CYN}● Registering routers…{C.R}")
    register_routers(dp, logger)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.error()(global_error_handler)

    logger.info(f"{C.GRN}● Starting long-polling…{C.R}\n")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=30,
        )
    except TelegramNetworkError as exc:
        logger.error(f"{C.RED}✗ Network error: {exc}{C.R}")
        logger.info(f"{C.YEL}● Retrying in 5 seconds…{C.R}")
        await asyncio.sleep(5)
    except KeyboardInterrupt:
        logger.info(f"{C.YEL}● Interrupted by user (Ctrl-C).{C.R}")
    except Exception as exc:
        logger.error(f"{C.RED}✗ Unexpected error during polling: {exc}{C.R}")
        logger.debug(traceback.format_exc())
    finally:
        try:
            await on_shutdown(bot, logger)
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.YEL}● {BOT_NAME} stopped by user.{C.R}")
    except Exception as exc:
        print(f"\n{C.RED}✗ Fatal error: {exc}{C.R}")
        traceback.print_exc()
        sys.exit(1)
