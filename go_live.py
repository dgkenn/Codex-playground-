"""go_live.py -- the single GO/NO-GO preflight gate. Run this on the box BEFORE arming real money.

It runs every safety check we've built, in order, and prints one verdict. Nothing here places an order or
needs to be trusted with funds; it only READS config + pokes public endpoints. Secrets are checked for
PRESENCE/permissions only -- their values are never printed or logged.

    python go_live.py [--asset btc] [--tenor-min 15]

Checks (critical ones must pass to GO):
  1  secrets        .env present, chmod 600, keys set (not placeholders), I_UNDERSTAND_REAL_MONEY value
  2  roster         strategies.py validates (no malformed/duplicate/unknown-gate strategy)
  3  paper edge     micro_gate is net- AND gross-positive in the shadow data (the edge still holds)
  4  live SDK       the exact client live_trader imports is installed (py_clob_client_v2)
  5  signing        coincurve present (libsecp256k1 -> sub-ms EIP-712 signing on the hot path)
  6  latency/colo   CLOB round-trip median (must be co-located in eu-west-2, single-digit ms)
  7  connectivity   can reach Gamma + discover the active market for --asset/--tenor-min
  8  post-only      the would_cross guard logic self-tests correctly (A3 accidental-taker guard)
  9  risk rails     max-notional / loss-limit are configured small for a pilot
"""
from __future__ import annotations
import argparse, glob, json, math, os, stat, time

G = "https://gamma-api.polymarket.com"
C = "https://clob.polymarket.com"
OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"
GLYPH = {OK: "✓", WARN: "!", FAIL: "✗", SKIP: "-"}


def chk_secrets():
    """Presence + permissions only -- never read or print the key material."""
    if not os.path.exists(".env"):
        return FAIL, ".env not found -- copy .env.example to .env on THIS box (chmod 600), fill keys", True
    mode = stat.S_IMODE(os.stat(".env").st_mode)
    perm_ok = (mode & 0o077) == 0
    env = {}
    for ln in open(".env"):
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); env[k.strip()] = v.strip()
    have_pk = env.get("PRIVATE_KEY", "").startswith("0x") and "YOUR" not in env.get("PRIVATE_KEY", "").upper()
    have_fn = env.get("DEPOSIT_WALLET_ADDRESS", "").startswith("0x") and "YOUR" not in env.get("DEPOSIT_WALLET_ADDRESS", "").upper()
    armed = env.get("I_UNDERSTAND_REAL_MONEY", "no")
    bits = []
    if not perm_ok:
        bits.append(f"perms {oct(mode)} too open -> chmod 600 .env")
    if not have_pk:
        bits.append("PRIVATE_KEY missing/placeholder")
    if not have_fn:
        bits.append("DEPOSIT_WALLET_ADDRESS missing/placeholder")
    if bits:
        return FAIL, "; ".join(bits), True
    note = f"keys present, perms {oct(mode)}, I_UNDERSTAND_REAL_MONEY={armed}"
    if armed != "yes":
        note += "  (DRY-RUN until set to 'yes')"
    return OK, note, True


def chk_roster():
    try:
        import strategies
        errs = strategies.validate()
        if errs:
            return FAIL, "; ".join(errs), True
        return OK, f"{len(strategies.enabled())} live / {len(strategies.REGISTRY)} total, valid", True
    except Exception as e:
        return FAIL, f"{type(e).__name__}: {e}", True


def chk_paper_edge():
    by_ws = {}
    for fp in glob.glob("gha_data/shadow_windows_*.jsonl"):
        try:
            for ln in open(fp):
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                if r.get("ws") is not None:
                    by_ws[r["ws"]] = r
        except Exception:
            pass
    rows = list(by_ws.values())
    nets = [r["micro_gate"]["net"] for r in rows if isinstance(r.get("micro_gate"), dict) and "net" in r["micro_gate"]]
    grs = [r["micro_gate"].get("gross") for r in rows if isinstance(r.get("micro_gate"), dict) and r["micro_gate"].get("gross") is not None]
    if len(nets) < 10:
        return WARN, f"only {len(nets)} shadow windows -- let the collector accumulate before trusting the edge", False
    nm = sum(nets) / len(nets); gm = (sum(grs) / len(grs)) if grs else float("nan")
    n = len(nets); sd = (sum((x - nm) ** 2 for x in nets) / (n - 1)) ** 0.5 if n > 1 else float("nan")
    t = nm / (sd / math.sqrt(n)) if sd and sd > 0 else float("nan")
    if nm > 0 and (gm != gm or gm > 0):
        return OK, f"micro_gate net/win {nm:+.2f} (t={t:+.1f}), gross/win {gm:+.2f} -> edge holds (n={n})", False
    return FAIL, f"micro_gate net/win {nm:+.2f} gross/win {gm:+.2f} -- edge NOT confirmed positive", True


def chk_live_sdk():
    try:
        import py_clob_client_v2  # noqa: F401  (the exact import live_trader.make_client uses)
        return OK, "py_clob_client_v2 importable", True
    except Exception:
        return FAIL, ("py_clob_client_v2 NOT installed (live_trader needs it). On the box: install the v2 "
                      "client. NOTE: deploy/setup.sh installs 'py-clob-client' (module py_clob_client) -- "
                      "confirm which the box actually has before arming."), True


def chk_signing():
    try:
        import coincurve  # noqa: F401
        return OK, "coincurve present -> libsecp256k1 fast signing", False
    except Exception:
        return WARN, "coincurve missing -> slower pure-python signing (hurts sub-10ms; pip install coincurve)", False


def chk_latency():
    try:
        import netfast
        sess = netfast.fast_session()
    except Exception:
        import requests
        sess = requests.Session()
    ts = []
    for _ in range(10):
        t0 = time.time()
        try:
            sess.get(C + "/time", timeout=5); ts.append((time.time() - t0) * 1e3)
        except Exception:
            pass
    if not ts:
        return FAIL, "CLOB unreachable (network/geo/VPN?) -- cannot trade blind", True
    ts.sort(); med = ts[len(ts) // 2]
    p95 = ts[min(len(ts) - 1, int(len(ts) * 0.95))]; p99 = ts[min(len(ts) - 1, int(len(ts) * 0.99))]
    tail = f"median {med:.0f}ms p95 {p95:.0f} p99 {p99:.0f}"   # p99 is what loses queue races (point 5)
    if med < 25 and p99 < 40:
        return OK, f"CLOB {tail} -> co-located (eu-west-2)", True
    if med < 80:
        return WARN, f"CLOB {tail} -> near-region / tail; tighten for queue priority (p99!)", False
    return FAIL, f"CLOB {tail} -> CROSS-REGION; co-locate in eu-west-2 before live", True


def chk_connectivity(asset, tenor):
    try:
        import netfast
        sess = netfast.fast_session()
    except Exception:
        import requests
        sess = requests.Session()
    win = tenor * 60
    now = int(time.time())
    cand = now - (now % win)
    for c in (cand, cand - win, cand + win):
        try:
            ev = sess.get(G + "/events", params={"slug": f"{asset}-updown-{tenor}m-{c}"}, timeout=10).json()
            if ev and ev[0].get("markets"):
                return OK, f"discovered active {asset}-{tenor}m market (ws={c})", True
        except Exception:
            pass
    return FAIL, f"could not discover an active {asset}-updown-{tenor}m market", True


def chk_post_only():
    try:
        from live_trader import would_cross
    except Exception as e:
        return WARN, f"could not import would_cross ({type(e).__name__}); guard untested here", False
    cases = [
        ("BUY", 0.60, 0.55, 0.60, True),   # BUY at ask -> crosses
        ("BUY", 0.54, 0.55, 0.60, False),  # BUY below ask -> ok
        ("SELL", 0.55, 0.55, 0.60, True),  # SELL at bid -> crosses
        ("SELL", 0.61, 0.55, 0.60, False), # SELL above ask -> ok
        ("BUY", 0.59, None, None, False),  # no book -> don't block
    ]
    for sd, p, bb, ba, exp in cases:
        if would_cross(sd, p, bb, ba) != exp:
            return FAIL, f"would_cross({sd},{p},{bb},{ba}) != {exp} -- post-only guard BROKEN", True
    return OK, "post-only guard self-test passed (no accidental crosses)", True


def chk_risk_rails():
    # parse defaults from live_trader's argparse without running it
    mn, ll = 25.0, 5.0
    try:
        for ln in open("live_trader.py"):
            if '"--max-notional"' in ln and "default=" in ln:
                mn = float(ln.split("default=")[1].split(")")[0].split(",")[0])
            if '"--loss-limit"' in ln and "default=" in ln:
                ll = float(ln.split("default=")[1].split(")")[0].split(",")[0])
    except Exception:
        pass
    ok = mn <= 50 and ll <= 10
    return (OK if ok else WARN), f"defaults max_notional=${mn:g} loss_limit=${ll:g} (+ markout kill + dead-man)", False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="btc")
    ap.add_argument("--tenor-min", type=int, default=15)
    a = ap.parse_args()
    print("=" * 72)
    print("  GO-LIVE PREFLIGHT  (read-only; secrets checked for presence only, never printed)")
    print("=" * 72)
    checks = [
        ("secrets", chk_secrets()),
        ("roster", chk_roster()),
        ("paper edge", chk_paper_edge()),
        ("live SDK", chk_live_sdk()),
        ("signing", chk_signing()),
        ("latency/colo", chk_latency()),
        ("connectivity", chk_connectivity(a.asset, a.tenor_min)),
        ("post-only guard", chk_post_only()),
        ("risk rails", chk_risk_rails()),
    ]
    crit_fail = 0
    for name, (status, detail, critical) in checks:
        tag = "CRIT" if critical else "    "
        print(f"  [{GLYPH[status]}] {status:<4} {tag} {name:<16} {detail}")
        if status == FAIL and critical:
            crit_fail += 1
    print("-" * 72)
    if crit_fail == 0:
        print("  VERDICT: GO  ->  DRY-RUN on this box first:")
        print("    python live_trader.py --presign --duration 120        (places nothing)")
        print("  then arm tiny:")
        print("    I_UNDERSTAND_REAL_MONEY=yes python live_trader.py --live --presign "
              "--max-notional 25 --loss-limit 5")
        print("  after the session:  python pilot_reconcile.py   (the real go/no-go on the edge)")
    else:
        print(f"  VERDICT: NO-GO  ->  {crit_fail} critical check(s) failed above. Fix, then re-run.")
        print("  (Running in the sandbox? secrets/SDK/colo will FAIL here by design -- run this ON THE BOX.)")
    print("=" * 72)


if __name__ == "__main__":
    main()
