"""kalshi_preflight.py -- the single GO/NO-GO before arming kalshi_trader with real money.

Mirrors go_live.py's discipline for the Kalshi venue: read-only, secrets checked for presence only,
every money-path dependency verified to fail loudly HERE rather than mid-session.

    python kalshi_preflight.py [--asset btc]
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import time

import requests

B = "https://api.elections.kalshi.com/trade-api/v2"
OK, WARN, FAIL = "OK", "WARN", "FAIL"
GLYPH = {OK: "+", WARN: "!", FAIL: "x"}


def chk_secrets():
    kid = os.environ.get("KALSHI_API_KEY_ID", "")
    pem = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    armed = os.environ.get("I_UNDERSTAND_REAL_MONEY", "no")
    if not kid:
        return FAIL, "KALSHI_API_KEY_ID missing (set in .env)", True
    if not pem or not os.path.exists(pem):
        return FAIL, f"KALSHI_PRIVATE_KEY_PATH missing/not found ({pem or 'unset'})", True
    mode = stat.S_IMODE(os.stat(pem).st_mode)
    note = f"key id + pem present, pem perms {oct(mode)}, I_UNDERSTAND_REAL_MONEY={armed}"
    if mode & 0o077:
        return WARN, note + "  -> chmod 600 the pem", True
    return OK, note, True


def chk_signing():
    """Load the pem and produce one RSA-PSS signature -- the exact hot-path operation."""
    pem = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not pem or not os.path.exists(pem):
        return FAIL, "no pem to test (see secrets)", True
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_private_key(open(pem, "rb").read(), password=None)
        t0 = time.time()
        key.sign(b"1700000000000GET/trade-api/v2/portfolio/balance",
                 padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                             salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        return OK, f"RSA-PSS signing OK ({(time.time()-t0)*1e3:.1f}ms)", True
    except Exception as e:  # noqa: BLE001
        return FAIL, f"signing failed: {type(e).__name__}: {str(e)[:80]}", True


def chk_auth():
    """One authenticated call (balance) -- proves key id + pem pair and clock are accepted."""
    if not os.environ.get("KALSHI_API_KEY_ID") or not os.path.exists(
            os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")):
        return FAIL, "no credentials to test (see secrets)", True
    try:
        from kalshi_trader import _api, _load_private_key
        key = _load_private_key()
        b = _api(requests.Session(), key, "GET", "/portfolio/balance")
        if isinstance(b, dict) and "balance" in json.dumps(b):
            return OK, "authenticated: /portfolio/balance OK (value not printed)", True
        return FAIL, f"unexpected balance response shape: {str(b)[:80]}", True
    except Exception as e:  # noqa: BLE001
        return FAIL, f"auth call failed: {type(e).__name__}: {str(e)[:90]}", True


def chk_latency():
    s = requests.Session(); ts = []
    for _ in range(10):
        t0 = time.time()
        try:
            s.get(f"{B}/exchange/status", timeout=5); ts.append((time.time()-t0)*1e3)
        except Exception:
            pass
    if not ts:
        return FAIL, "Kalshi unreachable", True
    ts.sort(); med = ts[len(ts)//2]; p95 = ts[min(len(ts)-1, int(len(ts)*0.95))]
    tail = f"median {med:.0f}ms p95 {p95:.0f}"
    if med < 30:
        return OK, f"{tail} -> in-region (us-east)", True
    if med < 80:
        return WARN, f"{tail} -> near-region; co-locate us-east for queue races", False
    return FAIL, f"{tail} -> cross-region; co-locate before live", True


def chk_market(asset):
    try:
        d = requests.get(f"{B}/markets", params={"series_ticker": f"KX{asset.upper()}15M",
                                                 "status": "open", "limit": 2}, timeout=10).json()
        ms = d.get("markets") or []
        if ms:
            return OK, f"active {asset}-15m market: {ms[0]['ticker']}", True
        return FAIL, f"no open KX{asset.upper()}15M market found", True
    except Exception as e:  # noqa: BLE001
        return FAIL, f"discovery failed: {type(e).__name__}", True


def chk_fees(asset):
    try:
        sr = requests.get(f"{B}/series/KX{asset.upper()}15M", timeout=10).json().get("series", {})
        ft = sr.get("fee_type"); fm = sr.get("fee_multiplier")
        note = f"fee_type={ft} multiplier={fm} (taker quadratic). MAKER fee assumed 0 -- "
        note += "CONFIRM on kalshi.com/docs fee schedule + the first real fill (the A1-equivalent)"
        return (OK if ft == "quadratic" and fm in (1, None) else WARN), note, False
    except Exception:
        return WARN, "could not read series fee fields", False


def chk_sentinel(asset):
    p = f".kalshi_killed_{asset}15m"
    if os.path.exists(p):
        return FAIL, f"kill sentinel {p} exists -- investigate, then delete to re-arm", True
    return OK, "no kill sentinel", False


def chk_roster():
    try:
        import strategies
        errs = strategies.validate()
        return (FAIL, "; ".join(errs), True) if errs else (OK, f"{len(strategies.enabled())} variants valid", False)
    except Exception as e:  # noqa: BLE001
        return FAIL, str(e)[:80], True


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--asset", default="btc")
    a = ap.parse_args()
    print("=" * 70)
    print("  KALSHI GO-LIVE PREFLIGHT (read-only; secret values never printed)")
    print("=" * 70)
    checks = [("secrets", chk_secrets()), ("signing", chk_signing()), ("auth", chk_auth()),
              ("latency", chk_latency()), ("market", chk_market(a.asset)),
              ("fees", chk_fees(a.asset)), ("kill sentinel", chk_sentinel(a.asset)),
              ("roster", chk_roster())]
    crit = 0
    for name, (st, detail, critical) in checks:
        print(f"  [{GLYPH[st]}] {st:<4} {'CRIT' if critical else '    '} {name:<13} {detail}")
        crit += (st == FAIL and critical)
    print("-" * 70)
    print("  VERDICT: GO -> dry-run first: python kalshi_trader.py --duration 120" if crit == 0
          else f"  VERDICT: NO-GO ({crit} critical failures)")
    print("=" * 70)


if __name__ == "__main__":
    main()
