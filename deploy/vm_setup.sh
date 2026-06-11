#!/usr/bin/env bash
# ============================================================================
#  24/7 KALSHI BOT on a fresh Ubuntu VM (Oracle Cloud always-free, us-east).
#  Installs deps, clones the bot, and registers a systemd service that runs
#  live_supervisor.sh forever -- survives crashes, reboots, and your laptop
#  being off. Control is identical to everywhere else: ./live_switch.sh on|off
#  or text the Telegram bot on/off.
#
#  RUN:  curl -fsSL <raw-url>/deploy/vm_setup.sh | bash      (after creds are in place)
#   or:  bash deploy/vm_setup.sh
# ============================================================================
set -euo pipefail
REPO="https://github.com/dgkenn/Codex-playground-.git"
BRANCH="claude/polymarket-bot-live-ready-vw7ut5"
DIR="$HOME/kalshi-bot"
KDIR="$HOME/.kalshi"

echo ">> Installing dependencies (python, git, libs)..."
sudo apt-get update -qq
# apt-installed python libs avoid the PEP-668 'externally-managed' pip breakage on Ubuntu 24.04;
# python-is-python3 makes the scripts' `python` resolve (Ubuntu ships only python3 by default).
sudo apt-get install -y -qq git python3 python-is-python3 \
  python3-numpy python3-scipy python3-requests python3-cryptography python3-websockets

echo ">> Fetching the bot..."
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q origin "$BRANCH" && git -C "$DIR" checkout -q "$BRANCH" \
    && git -C "$DIR" reset -q --hard "origin/$BRANCH"
else
  git clone -q -b "$BRANCH" "$REPO" "$DIR"
fi

echo ">> Checking credentials in $KDIR ..."
mkdir -p "$KDIR"; chmod 700 "$KDIR"
if [ ! -f "$KDIR/key.pem" ] || [ ! -f "$KDIR/env" ]; then
  cat <<MSG

  CREDENTIALS NOT FOUND. Put them in place, then re-run this script:
    $KDIR/key.pem        <- your Kalshi RSA private key
    $KDIR/env            <- (chmod 600) exactly these lines:
        export KALSHI_API_KEY_ID=YOUR_KEY_ID
        export KALSHI_PRIVATE_KEY_PATH=$KDIR/key.pem
        export TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
        export TELEGRAM_CHAT_ID=YOUR_CHAT_ID

  Copy them up from your laptop with, e.g.:
    scp ~/.kalshi/key.pem ~/.kalshi/env  ubuntu@<vm-ip>:~/.kalshi/
MSG
  exit 1
fi
chmod 600 "$KDIR/key.pem" "$KDIR/env"

echo ">> Installing the 24/7 systemd service..."
SVC=/etc/systemd/system/kalshi-bot.service
sudo tee "$SVC" >/dev/null <<UNIT
[Unit]
Description=Kalshi maker-box bot (supervisor: trader + collector + telegram control)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
ExecStart=/usr/bin/env bash $DIR/live_supervisor.sh
Restart=always
RestartSec=10
# the supervisor sources ~/.kalshi/env itself; HOME must be set for that to resolve
Environment=HOME=$HOME

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable kalshi-bot >/dev/null 2>&1
sudo systemctl restart kalshi-bot

echo ""
echo ">> DONE. The bot now runs 24/7 (even with your laptop off)."
echo "   Turn trading ON:    cd $DIR && ./live_switch.sh on      (or text the bot: on)"
echo "   Turn trading OFF:   cd $DIR && ./live_switch.sh off     (or text the bot: off)"
echo "   Live logs:          journalctl -u kalshi-bot -f"
echo "   Trader log:         tail -f $DIR/overnight_data/trader.log"
echo "   Service status:     systemctl status kalshi-bot"
