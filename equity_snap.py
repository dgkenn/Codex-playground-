"""equity_snap.py -- independent, READ-ONLY daily Kalshi account snapshot (dead-man audit companion).

WHY THIS EXISTS: kalshi_trader.py's own P&L ledger (`realized`, `pos`, `net_delta`) lives entirely
in-process and resets to zero on every restart -- it never re-adopts venue-side positions on startup
(see DEADMAN_AUDIT.md). That means the bot's self-reported P&L can silently drift from the venue's
true account state across a runner death, and nothing else checks. This script is a SEPARATE,
minimal, ground-truth check: it asks Kalshi directly for the account balance and open positions,
independent of anything the trader believes about itself.

AUTH: reuses kalshi_trader.py's RSA-PSS signer (`_load_private_key` / `_api`) via import -- the same
KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH secrets, the same signing code kalshi_preflight.py
already imports this exact way. Falls back to a minimal local re-implementation of just the auth
approach if that import ever fails (e.g. a future kalshi_trader.py refactor breaks importability),
so this audit tool never depends on the trader module staying importable.

READ-ONLY BY CONSTRUCTION: this file calls `_api()` with method="GET" ONLY, against exactly two
endpoints (/trade-api/v2/portfolio/balance, /trade-api/v2/portfolio/positions). It contains no
reference to place_order / cancel_order / any POST or DELETE call, and must never be modified to add
any. That is the whole point of an INDEPENDENT accounting/audit tool -- it must be structurally
incapable of moving money.

SAFE NO-OP: if KALSHI_API_KEY_ID or KALSHI_PRIVATE_KEY_PATH (or the pem file itself) is absent, this
prints "no secrets, skipping" and exits 0. It never raises past main() when secrets are missing.

OUTPUT: appends one JSON line to gha_data/equity_<YYYY-MM-DD>.jsonl (UTC calendar date):
    {"ts": <unix seconds>, "balance_cents": <int>, "positions": [...], "n_open": <int>}

If TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are set, also sends a one-line digest: balance, open
position count, and the delta vs the most recent prior snapshot found under gha_data/.

    python equity_snap.py
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Auth: reuse kalshi_trader's signer/caller (kalshi_preflight.py already imports it this exact way).
# Fallback below replicates ONLY the auth approach (RSA-PSS signing) if the import ever breaks --
# it still only ever performs GET requests; see _api() docstring in the fallback.
# ---------------------------------------------------------------------------
try:
    from kalshi_trader import _api, _load_private_key  # noqa: F401  (READ-ONLY use: GET calls only)
except Exception:
    import base64

    BASE = "https://api.elections.kalshi.com/trade-api/v2"

    def _load_private_key():
        path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
        if not path or not os.path.exists(path):
            return None
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        with open(path, "rb") as fh:
            return load_pem_private_key(fh.read(), password=None)

    def _sign(private_key, method: str, path: str) -> dict:
        """Kalshi RSA-PSS headers (mirrors kalshi_trader._sign)."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        ts = str(int(time.time() * 1000))
        msg = (ts + method.upper() + path).encode()
        sig = private_key.sign(msg, padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ), hashes.SHA256())
        return {
            "KALSHI-ACCESS-KEY": os.environ.get("KALSHI_API_KEY_ID", ""),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "Content-Type": "application/json",
        }

    def _api(sess, private_key, method, path_suffix, body=None, params=None, timeout=8):
        """READ-ONLY fallback caller -- this file only ever invokes it with method='GET'."""
        if method != "GET":
            raise ValueError(f"equity_snap fallback _api only supports GET (got {method!r})")
        url = BASE + path_suffix
        headers = _sign(private_key, method, "/trade-api/v2" + path_suffix)
        r = sess.get(url, headers=headers, params=params, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None


def _have_secrets() -> bool:
    if not os.environ.get("KALSHI_API_KEY_ID"):
        return False
    pem_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    return bool(pem_path) and os.path.exists(pem_path)


def _prev_snapshot(out_dir: str = "gha_data"):
    """Last line of the most recently-dated gha_data/equity_*.jsonl file (for the delta digest)."""
    files = sorted(glob.glob(os.path.join(out_dir, "equity_*.jsonl")))
    for path in reversed(files):
        try:
            with open(path) as fh:
                lines = [ln for ln in fh if ln.strip()]
            if lines:
                return json.loads(lines[-1])
        except Exception:
            continue
    return None


def _telegram_digest(balance_cents: int, n_open: int, prev) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    delta_txt = ""
    if isinstance(prev, dict) and "balance_cents" in prev:
        try:
            d = (balance_cents - int(prev["balance_cents"])) / 100.0
            delta_txt = f" (Δ{d:+.2f} vs prior snap)"
        except Exception:
            pass
    msg = (f"\U0001F4D2 equity snap: balance ${balance_cents / 100:.2f}{delta_txt}, "
           f"{n_open} open position(s)")
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": msg[:4000]}, timeout=8)
    except Exception:
        pass


def main() -> int:
    if not _have_secrets():
        print("no secrets, skipping")
        return 0

    try:
        priv = _load_private_key()
    except SystemExit as e:
        print(f"no secrets, skipping ({e})")
        return 0
    if priv is None:
        print("no secrets, skipping")
        return 0

    sess = requests.Session()

    sc_b, bal = _api(sess, priv, "GET", "/portfolio/balance")
    if sc_b < 200 or sc_b >= 300 or not isinstance(bal, dict):
        print(f"[equity_snap] balance fetch FAILED (status {sc_b}); not writing a snapshot")
        return 1

    sc_p, pos = _api(sess, priv, "GET", "/portfolio/positions", params={"limit": 1000})
    if sc_p < 200 or sc_p >= 300 or not isinstance(pos, dict):
        print(f"[equity_snap] positions fetch FAILED (status {sc_p}); not writing a snapshot")
        return 1

    balance_cents = int(bal.get("balance", 0) or 0)
    all_positions = pos.get("market_positions") or []
    open_positions = [p for p in all_positions if int(p.get("position", 0) or 0) != 0]

    record = {
        "ts": int(time.time()),
        "balance_cents": balance_cents,
        "positions": open_positions,
        "n_open": len(open_positions),
    }

    out_dir = "gha_data"
    os.makedirs(out_dir, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = os.path.join(out_dir, f"equity_{day}.jsonl")

    prev = _prev_snapshot(out_dir)

    with open(out_path, "a") as fh:
        fh.write(json.dumps(record) + "\n")

    print(f"[equity_snap] balance=${balance_cents / 100:.2f} n_open={len(open_positions)} -> {out_path}")

    _telegram_digest(balance_cents, len(open_positions), prev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
