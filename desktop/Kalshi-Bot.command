#!/bin/bash
# ============================================================================
#  KALSHI BOT  --  double-click to START trading,  close this window to STOP.
#  (Closing the window cancels every resting order via the bot's dead-man.)
#  macOS / Linux. First run does a one-time setup; after that it just trades.
# ============================================================================
set -u
REPO="https://github.com/dgkenn/Codex-playground-.git"
BRANCH="claude/polymarket-bot-live-ready-vw7ut5"
DIR="$HOME/kalshi-bot"
KDIR="$HOME/.kalshi"

echo "=========================================="
echo "   KALSHI MAKER-BOX BOT"
echo "=========================================="

# 1) one-time credentials -------------------------------------------------
if [ ! -f "$KDIR/key.pem" ] || [ ! -f "$KDIR/env" ]; then
  mkdir -p "$KDIR"; chmod 700 "$KDIR"
  echo
  echo "FIRST-TIME SETUP (do this once):"
  echo "  1. Put your Kalshi RSA private key here:   $KDIR/key.pem"
  echo "  2. Create this file:                       $KDIR/env"
  echo "       export KALSHI_API_KEY_ID=YOUR_KEY_ID"
  echo "       export KALSHI_PRIVATE_KEY_PATH=$KDIR/key.pem"
  echo "  (optional, for phone alerts when you're away:)"
  echo "       export TELEGRAM_BOT_TOKEN=...   ;  export TELEGRAM_CHAT_ID=..."
  echo
  open "$KDIR" 2>/dev/null || xdg-open "$KDIR" 2>/dev/null || true
  echo "Then double-click this file again."
  read -r -p "Press Enter to close... "; exit 1
fi
chmod 600 "$KDIR/key.pem" "$KDIR/env" 2>/dev/null || true

# 2) get / update the bot code -------------------------------------------
echo "Updating bot code..."
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q origin "$BRANCH" 2>/dev/null
  git -C "$DIR" checkout -q "$BRANCH" 2>/dev/null
  git -C "$DIR" reset -q --hard "origin/$BRANCH" 2>/dev/null
else
  git clone -q -b "$BRANCH" "$REPO" "$DIR" || { echo "git clone failed -- is git installed?"; read -r -p "Enter to close... "; exit 1; }
fi
cd "$DIR" || { echo "cannot enter $DIR"; read -r -p "Enter to close... "; exit 1; }

# 3) python + deps --------------------------------------------------------
PY=$(command -v python3 || command -v python) || { echo "Install Python 3 from python.org, then retry."; read -r -p "Enter to close... "; exit 1; }
"$PY" -m pip install --quiet --user numpy scipy requests cryptography websockets 2>/dev/null || true

# 4) load creds + preflight ----------------------------------------------
set -a; . "$KDIR/env"; set +a
echo "Running safety preflight..."
if ! "$PY" kalshi_preflight.py --asset btc | grep -q "VERDICT: GO"; then
  echo
  echo "PREFLIGHT NO-GO (details above). Common cause: a sticky loss-limit kill"
  echo "sentinel (.kalshi_killed_btc15m) from a prior session. Delete it to re-arm:"
  echo "   rm \"$DIR/.kalshi_killed_btc15m\""
  read -r -p "Enter to close... "; exit 1
fi

# 5) start the Telegram on/off + alerts listener (text on/off/status from your phone)
if grep -q TELEGRAM_BOT_TOKEN "$KDIR/env" 2>/dev/null; then
  pgrep -f "telegram_control.py" >/dev/null 2>&1 || "$PY" telegram_control.py >/dev/null 2>&1 &
fi

# 6) clean shutdown on window close: SIGTERM the bot -> dead-man cancels all
BOTPID=""
cleanup() {
  echo; echo ">> Stopping bot (cancelling all resting orders)..."
  [ -n "$BOTPID" ] && kill -TERM "$BOTPID" 2>/dev/null
  wait "$BOTPID" 2>/dev/null
  echo ">> Bot stopped. All orders cancelled. Safe to close."
}
trap cleanup EXIT INT TERM HUP

echo
echo "=========================================="
echo "   BOT IS LIVE.  CLOSE THIS WINDOW TO STOP."
echo "=========================================="
echo
# --duration is effectively unbounded; the window/process lifetime is the on/off switch.
I_UNDERSTAND_REAL_MONEY=yes "$PY" -u kalshi_trader.py --asset btc --live \
  --size-mode flat --post 1 --max-notional 5 --loss-limit 6 --max-rungs 1 \
  --duration 31536000 &
BOTPID=$!
wait "$BOTPID"
