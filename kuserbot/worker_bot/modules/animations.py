"""
worker_bot/modules/animations.py
Premium ASCII art & text animations for Telegram Userbot.
Dynamically loaded by userbot.py via register(client).

Commands:
  .hack    — Fake hacking terminal (finite, 7 frames)
  .dino    — Running dinosaur (infinite loop)
  .brain   — Expanding brain meme (finite)
  .fuck    — Rising middle finger (finite)
  .moon    — Moon phase cycle (2 loops)
  .clock   — Ticking clock (2 loops)
  .earth   — Spinning earth (infinite)
  .heart   — Beating heart (infinite)
  .matrix  — Matrix code rain (infinite)
  .bomb    — Bomb explosion (finite)
  .rocket  — Rocket launch sequence (finite)
  .loading — Progress bar (finite)
  .wave    — Waving hand (infinite)
  .dance   — Dancing emojis (infinite)
  .ghost   — Floating ghost (infinite)
  .fire    — Flickering fire (infinite)
  .shoot   — Shooting animation (finite)
  .stars   — Star sparkle (infinite)
"""

import asyncio
from telethon import events
from telethon.errors import FloodWaitError


# ============================================================
#  ASCII / EMOJI FRAME DATA
# ============================================================

HACK_FRAMES = [
    "╔══════════════════════════════════╗\n"
    "║  ⚡ NEURAL HACK ENGINE v3.0      ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Booting kernel modules...     ║\n"
    "║  > [██░░░░░░░░░░░░] 15%          ║\n"
    "╚══════════════════════════════════╝",

    "╔══════════════════════════════════╗\n"
    "║  ⚡ NEURAL HACK ENGINE v3.0      ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Scanning target network...    ║\n"
    "║  > [████░░░░░░░░░░] 35%          ║\n"
    "╚══════════════════════════════════╝",

    "╔══════════════════════════════════╗\n"
    "║  ⚡ NEURAL HACK ENGINE v3.0      ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Bypassing firewall rules...   ║\n"
    "║  > [██████░░░░░░░░] 55%          ║\n"
    "╚══════════════════════════════════╝",

    "╔══════════════════════════════════╗\n"
    "║  ⚡ NEURAL HACK ENGINE v3.0      ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Injecting exploit payload...  ║\n"
    "║  > [█████████░░░░░] 80%          ║\n"
    "╚══════════════════════════════════╝",

    "╔══════════════════════════════════╗\n"
    "║  ⚡ NEURAL HACK ENGINE v3.0      ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Decrypting AES-256 cipher...  ║\n"
    "║  > [██████████░░░░] 90%          ║\n"
    "╚══════════════════════════════════╝",

    "╔══════════════════════════════════╗\n"
    "║  ⚡ NEURAL HACK ENGINE v3.0      ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Escalating to root...         ║\n"
    "║  > [████████████░░] 95%          ║\n"
    "╚══════════════════════════════════╝",

    "╔══════════════════════════════════╗\n"
    "║  ✅ HACK COMPLETE                ║\n"
    "╠══════════════════════════════════╣\n"
    "║  > Target  : [REDACTED]          ║\n"
    "║  > Status  : COMPROMISED ✓       ║\n"
    "║  > root@target:~# _              ║\n"
    "╚══════════════════════════════════╝",
]

DINO_FRAMES = [
    "     __\n"
    "    /o \n"
    "    \\__/\n"
    "    /  |\n"
    "   /   |\n"
    "  /  | |\n"
    " /___|_|\n"
    "   ||   \n"
    "   ||   ",

    "     __\n"
    "    /o \n"
    "    \\__/\n"
    "    /  |\n"
    "   /   |\n"
    "  /  | |\n"
    " /___|_|\n"
    "     || \n"
    "     || ",
]

BRAIN_FRAMES = [
    "🧠",
    "🧠 → 🧠",
    "🧠 → 🧠 → 🧠",
    "🧠 → 🧠 → 🧠 → 🧠",
    "🧠 → 🧠 → 🧠 → 🧠 → 🧠",
    "🧠 → 🧠 → 🧠 → 🧠 → 🧠 → 🧠",
    "🧠 → 🧠 → 🧠 → 🧠 → 🧠 → 🧠 → 🧠",
    "🧠🧠🧠🧠🧠🧠🧠🧠\n\n✨ GALAXY BRAIN ✨",
]

FUCK_FRAMES = [
    "       \n"
    "       \n"
    "       \n"
    "  ___  \n"
    " |   | \n"
    " |___| ",

    "       \n"
    "       \n"
    "   _   \n"
    "  |_|  \n"
    " |   | \n"
    " |___| ",

    "   _   \n"
    "  | |  \n"
    "  | |  \n"
    "  |_|  \n"
    " |   | \n"
    " |___| ",

    "   _   \n"
    "  | |  \n"
    "  | |  \n"
    "  |_|  \n"
    " |   | \n"
    " |___| \n"
    "FUCK YOU! 😤",
]

MOON_FRAMES = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]

CLOCK_FRAMES = [
    "🕐", "🕑", "🕒", "🕓", "🕔", "🕕",
    "🕖", "🕗", "🕘", "🕙", "🕚", "🕛",
]

EARTH_FRAMES = ["🌍", "🌎", "🌏"]

HEART_FRAMES = ["❤️", "💖", "💗", "💓", "💕", "❤️‍🔥"]

MATRIX_FRAMES = [
    "```\n"
    "1 0 1 0 0 1 1 0 1\n"
    "0 1 0 1 1 0 0 1 0\n"
    "1 1 0 0 1 0 1 0 1\n"
    "0 0 1 1 0 1 0 1 0\n"
    "1 0 1 0 0 1 1 0 1\n"
    "0 1 0 1 1 0 0 1 0\n"
    "```",
    "```\n"
    "0 1 0 1 1 0 0 1 0\n"
    "1 0 1 0 0 1 1 0 1\n"
    "0 0 1 1 0 1 0 1 0\n"
    "1 1 0 0 1 0 1 0 1\n"
    "0 1 0 1 1 0 0 1 0\n"
    "1 0 1 0 0 1 1 0 1\n"
    "```",
    "```\n"
    "1 1 0 0 1 0 1 0 1\n"
    "0 0 1 1 0 1 0 1 0\n"
    "1 0 1 0 0 1 1 0 1\n"
    "0 1 0 1 1 0 0 1 0\n"
    "1 1 0 0 1 0 1 0 1\n"
    "0 0 1 1 0 1 0 1 0\n"
    "```",
    "```\n"
    "0 0 1 1 0 1 0 1 0\n"
    "1 1 0 0 1 0 1 0 1\n"
    "0 1 0 1 1 0 0 1 0\n"
    "1 0 1 0 0 1 1 0 1\n"
    "0 0 1 1 0 1 0 1 0\n"
    "1 1 0 0 1 0 1 0 1\n"
    "```",
]

BOMB_FRAMES = [
    "   🧨\n      ",
    "  🧨🧨\n      ",
    " 🧨🧨🧨\n      ",
    "  💣  \n  🕹️  ",
    "  💣  \n  🔥  ",
    "💥💥💥\n💥💥💥\n💥💥💥",
]

ROCKET_FRAMES = [
    "🚀\n\nLaunch in 3...",
    "🚀\n\nLaunch in 2...",
    "🚀\n\nLaunch in 1...",
    "🚀\n\n🛫 LIFT OFF!",
    "  🚀  \n\n      ",
    "    🚀\n\n      ",
    "      🚀\n\n      ",
    "        🚀\n\n      ",
    "🚀🚀🚀\n\n🛰️ IN ORBIT!",
]

LOADING_FRAMES = [
    "[▱▱▱▱▱▱▱▱▱▱] 0%",
    "[▰▱▱▱▱▱▱▱▱▱] 10%",
    "[▰▰▱▱▱▱▱▱▱▱] 20%",
    "[▰▰▰▱▱▱▱▱▱▱] 30%",
    "[▰▰▰▰▱▱▱▱▱▱] 40%",
    "[▰▰▰▰▰▱▱▱▱▱] 50%",
    "[▰▰▰▰▰▰▱▱▱▱] 60%",
    "[▰▰▰▰▰▰▰▱▱▱] 70%",
    "[▰▰▰▰▰▰▰▰▱▱] 80%",
    "[▰▰▰▰▰▰▰▰▰▱] 90%",
    "[▰▰▰▰▰▰▰▰▰▰] 100% ✅",
]

WAVE_FRAMES = [
    "👋      ",
    "  👋    ",
    "    👋  ",
    "  👋    ",
]

DANCE_FRAMES = [
    "🕺    💃",
    "    💃  🕺",
    "🕺    💃",
    "    💃  🕺",
]

GHOST_FRAMES = [
    "    👻  \n         ",
    "  👻    \n         ",
    "👻      \n         ",
    "  👻    \n         ",
    "    👻  \n         ",
]

FIRE_FRAMES = [
    "   🔥  \n  🔥🔥 \n 🔥🔥🔥",
    "  🔥🔥 \n 🔥🔥🔥\n  🔥🔥 ",
    " 🔥🔥🔥\n  🔥🔥 \n   🔥  ",
    "  🔥🔥 \n 🔥🔥🔥\n  🔥🔥 ",
]

SHOOT_FRAMES = [
    "🔫\n\n      ",
    "  🔫\n\n      ",
    "    🔫💨\n\n      ",
    "    🔫💨💨\n\n      ",
    "    🔫💨💨💨\n💀    \n      ",
    "    🔫\n\n💀 HEADSHOT! 🎯",
]

STARS_FRAMES = [
    "⭐",
    "✨⭐",
    "✨⭐✨",
    "🌟✨⭐✨🌟",
    "✨🌟✨⭐✨🌟✨",
    "⭐✨🌟✨⭐✨🌟✨⭐",
]


# ============================================================
#  NEW PREMIUM ANIMATIONS (v3.1)
# ============================================================

LOADER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

COINTOSS_FRAMES = [
    "🪙",
    "🌀",
    "🪙",
    "🌀",
    "🪙",
    "✨ UP! ✨",
    "🪙 HEADS! 🪙",
]

DICE_FRAMES = ["⚀", "⚁", "⚂", "⚃", "⚄", "🎲", "⚅", "🎲 ROLLED! ⚅"]

RAIN_FRAMES = [
    "☁️\n     ☁️\n          ☁️\n\n       💧",
    "☁️☁️\n     ☁️\n\n   💧   💧",
    "☁️☁️☁️\n\n 💧  💧  💧",
    "🌧️🌧️🌧️\n  💧  💧  💧  💧",
    "⛈️⛈️⛈️⛈️\n 💧💧💧💧💧",
    "🌧️ RAINING! 🌧️",
]

SNOW_FRAMES = [
    "☁️\n\n   ❄️        ❅",
    "☁️☁️\n  ❅     ❄️     ❆",
    "☁️☁️☁️\n ❆   ❄️   ❅   ❄️",
    "🌨️🌨️🌨️\n❄️ ❅ ❆ ❄️ ❅ ❆",
    "⛄ SNOWING! ⛄",
]

SIREN_FRAMES = [
    "🚨🔵",
    "🔵🚨",
    "🚨🔵",
    "🔵🚨",
    "🚨 WEEE-OOOO 🚨",
]

FIGHT_FRAMES = [
    "🥷      👊",
    "🥷    👊",
    "🥷  👊",
    "🥷👊",
    "💥 K.O. 💥",
]

SNAKE_FRAMES = [
    "___@",
    "__@_",
    "_@__",
    "@___",
    "_@__",
    "__@_",
]

LOVE_FRAMES = [
    "💌",
    "💌💗",
    "💌💗💖",
    "💌💗💖💕",
    "💌💗💖💕❤️",
    "💝 I LOVE YOU! 💝",
]

NINJA_FRAMES = [
    "🥷     🏃",
    "  🥷   🏃",
    "    🥷 🏃",
    "      🥷💨",
    "      🥷 NINJA VANISH! 💨",
]

COUNTDOWN_FRAMES = [
    "5️⃣",
    "4️⃣",
    "3️⃣",
    "2️⃣",
    "1️⃣",
    "🚀 BLAST OFF! 🚀",
]

TYPEWRITER_FRAMES = [
    "T_",
    "Ty_",
    "Typ_",
    "Typi_",
    "Typin_",
    "Typing_",
    "Typing._",
    "Typing.._",
    "Typing...",
    "✍️ Done typing! ✍️",
]

BALLOON_FRAMES = [
    "🎈",
    " 🎈",
    "  🎈",
    "   🎈",
    "    🎈",
    "     🎈",
    "🎈 FREEDOM! 🎈",
]


# ============================================================
#  ANIMATION RUNNER HELPER
# ============================================================

async def _start_animation(
    client,
    event,
    frames,
    *,
    delay: float = 0.5,
    loops: int = 0,
    prefix: str = "",
    suffix: str = "",
    stop_text: str = "⏹️ Animation stopped.",
    name: str = "anim",
):
    """
    Launch a cancellable background animation.

    Parameters
    ----------
    frames : list[str]
        Ordered list of frame strings to cycle through.
    delay : float
        Seconds between successive edits.
    loops : int
        0  → infinite loop (until cancelled by .stop)
        N  → run through all frames N times, then stop naturally.
    prefix / suffix : str
        Optional static text wrapped around every frame.
    stop_text : str
        Message shown when the animation is cancelled.  Set to ``""``
        to leave the last frame as-is.
    name : str
        Unique tag used in the ``stop_processes`` key.
    """
    chat = await event.get_input_chat()
    initial = prefix + frames[0] + suffix
    # Premium UX: animate the *command message itself* (it is outgoing),
    # falling back to a new message if editing is not possible.
    msg = event.message
    try:
        await event.edit(initial, link_preview=False)
    except Exception:
        msg = await client.send_message(chat, initial)
    task_key = f"{name}_{event.chat_id}_{event.id}"
    last_content = initial

    async def _animate():
        nonlocal last_content
        fail_count = 0
        try:
            loop_count = 0
            while loops == 0 or loop_count < loops:
                stop = False
                for frame in frames:
                    content = prefix + frame + suffix
                    if content == last_content:
                        await asyncio.sleep(delay)
                        continue
                    try:
                        await msg.edit(content)
                        last_content = content
                        fail_count = 0
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds + 1)
                        try:
                            await msg.edit(content)
                            last_content = content
                            fail_count = 0
                        except Exception:
                            fail_count += 1
                    except Exception:
                        fail_count += 1

                    if fail_count >= 3:
                        stop = True
                        break

                    await asyncio.sleep(delay)

                if stop:
                    break
                loop_count += 1
        except asyncio.CancelledError:
            if stop_text:
                try:
                    await msg.edit(stop_text)
                except Exception:
                    pass
            raise
        finally:
            client.stop_processes.pop(task_key, None)

    task = asyncio.create_task(_animate())
    client.stop_processes[task_key] = task
    return task


# ============================================================
#  COMMAND REGISTRATION
# ============================================================

def register(client):
    """Register every animation command on the given Telethon client."""

    # Safety nets – ensure shared attributes exist even if the loader
    # forgot to attach them.
    if not hasattr(client, "stop_processes"):
        client.stop_processes = {}
    if not hasattr(client, "flood_safe"):
        from functools import wraps as _wraps

        def _identity_fsafe(func):
            @_wraps(func)
            async def _wrapper(*a, **kw):
                return await func(*a, **kw)
            return _wrapper

        client.flood_safe = _identity_fsafe

    # ---- .hack -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.hack$"))
    @client.flood_safe
    async def _hack(event):
        await _start_animation(
            client, event, HACK_FRAMES,
            delay=0.8, loops=1, name="hack",
            stop_text="⏹️ Hack aborted.",
        )

    # ---- .dino -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.dino$"))
    @client.flood_safe
    async def _dino(event):
        await _start_animation(
            client, event, DINO_FRAMES,
            delay=0.3, loops=0, name="dino",
            stop_text="⏹️ Dino stopped.",
        )

    # ---- .brain ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.brain$"))
    @client.flood_safe
    async def _brain(event):
        await _start_animation(
            client, event, BRAIN_FRAMES,
            delay=0.6, loops=1, name="brain",
            stop_text="⏹️ Brain stopped.",
        )

    # ---- .fuck -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.fuck$"))
    @client.flood_safe
    async def _fuck(event):
        await _start_animation(
            client, event, FUCK_FRAMES,
            delay=0.5, loops=2, name="fuck",
            stop_text="⏹️ Stopped.",
        )

    # ---- .moon -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.moon$"))
    @client.flood_safe
    async def _moon(event):
        await _start_animation(
            client, event, MOON_FRAMES,
            delay=0.5, loops=2, name="moon",
            stop_text="⏹️ Moon stopped.",
        )

    # ---- .clock ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.clock$"))
    @client.flood_safe
    async def _clock(event):
        await _start_animation(
            client, event, CLOCK_FRAMES,
            delay=0.5, loops=2, name="clock",
            stop_text="⏹️ Clock stopped.",
        )

    # ---- .earth ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.earth$"))
    @client.flood_safe
    async def _earth(event):
        await _start_animation(
            client, event, EARTH_FRAMES,
            delay=0.3, loops=0, name="earth",
            stop_text="⏹️ Earth stopped.",
        )

    # ---- .heart ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.heart$"))
    @client.flood_safe
    async def _heart(event):
        await _start_animation(
            client, event, HEART_FRAMES,
            delay=0.4, loops=0, name="heart",
            stop_text="⏹️ Heart stopped.",
        )

    # ---- .matrix -----------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.matrix$"))
    @client.flood_safe
    async def _matrix(event):
        await _start_animation(
            client, event, MATRIX_FRAMES,
            delay=0.2, loops=0, name="matrix",
            stop_text="⏹️ Matrix disconnected.",
        )

    # ---- .bomb -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.bomb$"))
    @client.flood_safe
    async def _bomb(event):
        await _start_animation(
            client, event, BOMB_FRAMES,
            delay=0.6, loops=1, name="bomb",
            stop_text="⏹️ Bomb defused.",
        )

    # ---- .rocket -----------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.rocket$"))
    @client.flood_safe
    async def _rocket(event):
        await _start_animation(
            client, event, ROCKET_FRAMES,
            delay=0.7, loops=1, name="rocket",
            stop_text="⏹️ Launch aborted.",
        )

    # ---- .loading ----------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.loading$"))
    @client.flood_safe
    async def _loading(event):
        await _start_animation(
            client, event, LOADING_FRAMES,
            delay=0.4, loops=1, name="loading",
            stop_text="⏹️ Loading interrupted.",
        )

    # ---- .wave -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.wave$"))
    @client.flood_safe
    async def _wave(event):
        await _start_animation(
            client, event, WAVE_FRAMES,
            delay=0.4, loops=0, name="wave",
            stop_text="⏹️ Wave stopped.",
        )

    # ---- .dance ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.dance$"))
    @client.flood_safe
    async def _dance(event):
        await _start_animation(
            client, event, DANCE_FRAMES,
            delay=0.4, loops=0, name="dance",
            stop_text="⏹️ Dance stopped.",
        )

    # ---- .ghost ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ghost$"))
    @client.flood_safe
    async def _ghost(event):
        await _start_animation(
            client, event, GHOST_FRAMES,
            delay=0.4, loops=0, name="ghost",
            stop_text="⏹️ Ghost vanished. 👻",
        )

    # ---- .fire -------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.fire$"))
    @client.flood_safe
    async def _fire(event):
        await _start_animation(
            client, event, FIRE_FRAMES,
            delay=0.3, loops=0, name="fire",
            stop_text="⏹️ Fire extinguished.",
        )

    # ---- .shoot ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.shoot$"))
    @client.flood_safe
    async def _shoot(event):
        await _start_animation(
            client, event, SHOOT_FRAMES,
            delay=0.6, loops=1, name="shoot",
            stop_text="⏹️ Gun holstered.",
        )

    # ---- .stars ------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stars$"))
    @client.flood_safe
    async def _stars(event):
        await _start_animation(
            client, event, STARS_FRAMES,
            delay=0.4, loops=0, name="stars",
            stop_text="⏹️ Stars faded.",
        )


    # ---- NEW PREMIUM ANIMATIONS (v3.1) ------------------------

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.loader$"))
    @client.flood_safe
    async def _loader(event):
        await _start_animation(
            client, event, LOADER_FRAMES,
            delay=0.15, loops=3, name="loader",
            stop_text="⏹️ Loader stopped.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.cointoss$"))
    @client.flood_safe
    async def _cointoss(event):
        await _start_animation(
            client, event, COINTOSS_FRAMES,
            delay=0.35, loops=1, name="cointoss",
            stop_text="⏹️ Toss cancelled.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.dice$"))
    @client.flood_safe
    async def _dice(event):
        await _start_animation(
            client, event, DICE_FRAMES,
            delay=0.4, loops=1, name="dice",
            stop_text="⏹️ Roll cancelled.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.rain$"))
    @client.flood_safe
    async def _rain(event):
        await _start_animation(
            client, event, RAIN_FRAMES,
            delay=0.5, loops=0, name="rain",
            stop_text="🌈 Rain stopped.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.snow$"))
    @client.flood_safe
    async def _snow(event):
        await _start_animation(
            client, event, SNOW_FRAMES,
            delay=0.5, loops=0, name="snow",
            stop_text="⛄ Snow stopped.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.siren$"))
    @client.flood_safe
    async def _siren(event):
        await _start_animation(
            client, event, SIREN_FRAMES,
            delay=0.25, loops=0, name="siren",
            stop_text="⏹️ Siren off.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.fight$"))
    @client.flood_safe
    async def _fight(event):
        await _start_animation(
            client, event, FIGHT_FRAMES,
            delay=0.5, loops=1, name="fight",
            stop_text="⏹️ Fight over.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.snake$"))
    @client.flood_safe
    async def _snake(event):
        await _start_animation(
            client, event, SNAKE_FRAMES,
            delay=0.25, loops=0, name="snake",
            stop_text="🐍 Snake went home.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.love$"))
    @client.flood_safe
    async def _love(event):
        await _start_animation(
            client, event, LOVE_FRAMES,
            delay=0.5, loops=1, name="love",
            stop_text="⏹️ Love cancelled.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ninja$"))
    @client.flood_safe
    async def _ninja(event):
        await _start_animation(
            client, event, NINJA_FRAMES,
            delay=0.4, loops=1, name="ninja",
            stop_text="💨 Vanished.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.countdown$"))
    @client.flood_safe
    async def _countdown(event):
        await _start_animation(
            client, event, COUNTDOWN_FRAMES,
            delay=1.0, loops=1, name="countdown",
            stop_text="⏹️ Countdown aborted.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.typewriter$"))
    @client.flood_safe
    async def _typewriter(event):
        await _start_animation(
            client, event, TYPEWRITER_FRAMES,
            delay=0.3, loops=1, name="typewriter",
            stop_text="⏹️ Typing stopped.",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.balloon$"))
    @client.flood_safe
    async def _balloon(event):
        await _start_animation(
            client, event, BALLOON_FRAMES,
            delay=0.5, loops=1, name="balloon",
            stop_text="⏹️ Balloon popped. 🎈",
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.anims$"))
    @client.flood_safe
    async def _anims(event):
        await event.edit(
            "🎬 **Available Animations**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ `.hack`  `.dino`  `.brain`  `.fuck`\n"
            "🌙 `.moon`  `.clock`  `.earth`  `.heart`\n"
            "🟩 `.matrix`  `.bomb`  `.rocket`  `.loading`\n"
            "👋 `.wave`  `.dance`  `.ghost`  `.fire`\n"
            "🔫 `.shoot`  `.stars`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ **NEW:** `.loader`  `.cointoss`  `.dice`\n"
            "🌧️ `.rain`  `.snow`  `.siren`  `.fight`\n"
            "🐍 `.snake`  `.love`  `.ninja`  `.countdown`\n"
            "⌨️ `.typewriter`  `.balloon`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏹️ Stop any: `.stop`",
            link_preview=False,
        )

COMMANDS = {
    "description": "Premium Animations (30+)",
    "commands": [
        (".hack .dino .brain .fuck", "classic animations"),
        (".moon .clock .earth .heart", "emoji loops"),
        (".matrix .bomb .rocket .loading", "terminal / action"),
        (".wave .dance .ghost .fire .stars", "fun loops"),
        (".shoot", "headshot animation"),
        (".loader .cointoss .dice", "NEW — spinner / toss / roll"),
        (".rain .snow .siren .fight", "NEW — weather / fight"),
        (".snake .love .ninja .countdown", "NEW — more fun"),
        (".typewriter .balloon", "NEW — typewriter / balloon"),
        (".anims", "list all animations"),
    ],
}
