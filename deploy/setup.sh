#!/usr/bin/env bash
# setup.sh -- provision a FRESH Ubuntu box (Oracle Cloud Always Free, London / AWS eu-west-2) to run
# the Polymarket maker with sub-10ms-capable infra. Idempotent. See DEPLOY.md for the free-colo guide.
#
#   ssh ubuntu@<box>;  git clone <repo> pmkit && cd pmkit && bash deploy/setup.sh
#
# It installs python + the live deps (incl. coincurve for <1ms signing), then prints the latency
# self-test so you can confirm the box is actually co-located BEFORE you fund anything.
set -euo pipefail

echo "== pmkit setup on $(uname -m) =="
sudo apt-get update -qq
# build deps for coincurve (libsecp256k1) + python
sudo apt-get install -y -qq python3 python3-pip python3-venv build-essential pkg-config libffi-dev \
    libsecp256k1-dev git

cd "$(dirname "$0")/.."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip wheel
pip install -q -r requirements.txt
# live-only deps (commented out of requirements.txt so paper/research installs stay light)
pip install -q py-clob-client web3 coincurve
python3 - <<'PY'
import importlib.util as u
print("  coincurve:", "OK (eth_account will use libsecp256k1 -> sub-ms signing)" if u.find_spec("coincurve") else "MISSING")
PY

echo
echo "== LATENCY SELF-TEST (this is the colo verdict; run it before funding) =="
python3 latency.py 20 || true

echo
echo "Next:"
echo "  1) confirm CLOB POST TTFB above is single-digit ms (else you are NOT co-located -- see DEPLOY.md)"
echo "  2) put PRIVATE_KEY / DEPOSIT_WALLET_ADDRESS in a gitignored .env on THIS box only (never commit)"
echo "  3) dry-run first:   python3 live_trader.py --presign --duration 120"
echo "  4) when satisfied:  see deploy/pmkit.service to run it persistently under systemd"
