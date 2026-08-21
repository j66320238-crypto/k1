#!/usr/bin/env bash
# ============================================================
#  PHANTOM-X Master Bot — one-command installer & runner
#  Usage:
#     ./start.sh          → install deps (first run) + start bot
#     ./start.sh --userbot→ start the worker userbot instead
# ============================================================
set -e
cd "$(dirname "$0")"

# ── 1. Virtual-env bootstrapping (skip if user manages deps) ──
if [ -z "$PHANTOM_NO_VENV" ]; then
  if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)…"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# ── 2. Dependencies ──
if [ -f "requirements.txt" ]; then
  echo "📥 Installing / verifying dependencies…"
  python3 -m pip install --quiet --upgrade pip
  python3 -m pip install --quiet -r requirements.txt
fi

# ── 3. .env sanity check ──
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    echo "⚠️  No .env found — creating from .env.example (FILL IT IN!)"
    cp .env.example .env
  fi
fi

# ── 4. Launch ──
if [ "$1" = "--userbot" ]; then
  echo "🤖 Starting worker USERBOT…"
  if [ -z "$SESSION_STRING" ] || [ -z "$API_ID" ] || [ -z "$API_HASH" ]; then
    echo "❌ SESSION_STRING / API_ID / API_HASH must be exported first."
    echo "   export API_ID=... API_HASH=... SESSION_STRING=... && ./start.sh --userbot"
    exit 1
  fi
  exec python3 worker_bot/userbot.py
else
  echo "🤖 Starting PHANTOM-X master bot…"
  exec python3 main.py
fi
