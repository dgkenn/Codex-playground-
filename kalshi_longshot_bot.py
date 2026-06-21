#!/usr/bin/env python3
"""kalshi_longshot_bot.py -- LIVE maker bot for the longshot-sell harvest.

The one validated +EV Kalshi edge (KALSHI_MAKER_VERDICT.md / KALSHI_MAKER_ADVSEL.md):
on soft, ZERO-maker-fee categories, recreational buyers overpay for cheap YES longshots.
We are the maker on the other side -- rest a passive NO-buy at the touch on longshots
(YES mid 0.02-0.20). +0.97c/contract @17sigma net of adverse selection + fee; capacity
~$30-150/mo; negative skew (collect ~1c often, lose ~95c when a longshot hits) -> tiny
clips + diversify across many uncorrelated events.

SAFETY: DRY-RUN by default. Set LONGSHOT_LIVE=1 to actually place orders. Hard caps on
clip size, per-theme exposure, total collateral, and # positions. Maker-only (post_only)
so we never cross/pay taker fees. Venue-side TTL dead-man on every order.

Auth (RSA-PSS, copied from the proven kalshi_trader.py so behavior is identical):
  KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY_PATH
Config (env, all optional):
  LONGSHOT_LIVE=0|1        (default 0 = dry-run; 1 = place real orders)
  LONGSHOT_CLIP=1          contracts per leg (keep tiny -- negative skew)
  LONGSHOT_MAX_THEME=5     max contracts of exposure per series/event-theme
  LONGSHOT_MAX_NOTIONAL=200  max total collateral $ committed (sum of NO costs)
  LONGSHOT_MAX_POS=120     max # simultaneous open positions
  LONGSHOT_TTL=82800       order TTL seconds (default 23h; re-quoted each daily run)

    python kalshi_longshot_bot.py            # one pass (cron-friendly)
"""
import os, sys, time, json, uuid, base64, urllib.parse, datetime as dt
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CATS = ["Entertainment", "Science and Technology", "Climate and Weather", "Politics"]  # OPT: pref order
# OPTIMIZED band (KALSHI_LONGSHOT_OPT.md): p in [0.05,0.15) is the sweet spot -- net +5.45c/ctr
# (event-clustered 95% CI [+3.2,+7.7]), ~3-5x the old [0.02,0.20] blend. Deep tail <0.05 is +1.4c but
# thin; p>=0.15 has no edge. Widen via env only to trade edge-quality for marginal capacity.
LONG_LO = float(os.environ.get("LONGSHOT_BAND_LO", "0.05"))
LONG_HI = float(os.environ.get("LONGSHOT_BAND_HI", "0.15"))
MAXSPREAD = 0.10
MIN_VOL = 200.0
MAX_LIFE_FRAC = float(os.environ.get("LONGSHOT_MAX_LIFE_FRAC", "0.50"))  # OPT+EXEC: fill EARLY. Both
# studies agree -- segmentation finds >=50% life-left adds +1.3c (z3.1) & cuts skew; execution finds the
# final third's edge is NEGATIVE (-1.6 to -3.1c). Quoting only the first HALF captures both. (0.67 for
# more capacity at lower per-contract edge.)


def _life_frac(m):
    """Fraction of [open_time, close_time] elapsed (0=fresh, 1=at close). None if unknown."""
    try:
        o = dt.datetime.fromisoformat((m.get("open_time") or "").replace("Z", "+00:00"))
        c = dt.datetime.fromisoformat((m.get("close_time") or "").replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        span = (c - o).total_seconds()
        return (now - o).total_seconds() / span if span > 0 else None
    except Exception:
        return None


# ---- auth + order primitives (faithful copy of kalshi_trader.py) ----
def _load_private_key():
    path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not path:
        return None
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    with open(path, "rb") as fh:
        return load_pem_private_key(fh.read(), password=None)


def _sign(private_key, method, path):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(time.time() * 1000))
    sig = private_key.sign((ts + method.upper() + path).encode(),
                           padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                       salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": os.environ.get("KALSHI_API_KEY_ID", ""),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "Content-Type": "application/json"}


def _api(sess, pk, method, path_suffix, body=None, params=None, timeout=8):
    api_path = "/trade-api/v2" + path_suffix.removeprefix("/trade-api/v2")
    url = BASE + path_suffix.removeprefix("/trade-api/v2")
    h = _sign(pk, method, api_path) if pk else {}
    try:
        if method == "GET":
            r = sess.get(url, headers=h, params=params, timeout=timeout)
        elif method == "POST":
            r = sess.post(url, headers=h, json=body, timeout=timeout)
        elif method == "DELETE":
            r = sess.delete(url, headers=h, timeout=timeout)
        else:
            return 0, None
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception as e:
        return 0, {"_exc": str(e)[:80]}


def place_no_buy(sess, pk, ticker, price_dollars, count, ttl_s):
    """Rest a maker NO buy (post_only) -- harvest the overpriced longshot from the NO side."""
    body = {"ticker": ticker, "client_order_id": str(uuid.uuid4()), "side": "no", "action": "buy",
            "count": int(count), "type": "limit", "no_price_dollars": f"{price_dollars:.4f}",
            "post_only": True, "expiration_ts": int(time.time() + ttl_s)}
    sc, resp = _api(sess, pk, "POST", "/portfolio/orders", body=body)
    if not (200 <= sc < 300) or resp is None:
        msg = ""
        try:
            msg = (resp or {}).get("error", {}).get("message") or json.dumps(resp)[:100]
        except Exception:
            msg = str(resp)[:100]
        return None, sc, msg
    return str((resp.get("order") or {}).get("order_id")), sc, ""


# ---- public market data (no auth) ----
def pub(sess, path, params=""):
    u = f"{BASE}{path}" + ("?" + params if params else "")
    for a in range(5):
        try:
            r = sess.get(u, timeout=20)
            if r.status_code == 429:
                time.sleep(2*(a+1)); continue
            return r.json()
        except Exception:
            time.sleep(1.0*(a+1))
    return {}


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def scan_longshots(sess, want):
    """Returns (candidates, scan_stats). scan_stats counts WHY each market was rejected at the
    pre-filter stage -- the first half of the decision audit (the per-candidate decisions in main()
    are the second half)."""
    out = []
    stats = {"scanned": 0, "not_binary": 0, "maker_fee": 0, "no_quote": 0, "out_of_band": 0,
             "wide_spread": 0, "low_vol": 0, "late_life": 0, "kept": 0}
    for cat in CATS:
        cur = ""
        seriess = []
        while len(seriess) < 80:
            d = pub(sess, "/series", f"category={urllib.parse.quote(cat)}&limit=100" + (f"&cursor={cur}" if cur else ""))
            seriess += [s["ticker"] for s in d.get("series", []) if s.get("ticker")]
            cur = d.get("cursor") or ""
            if not cur:
                break
        for st in seriess:
            if len(out) >= want:
                return out, stats
            cur = ""
            while True:
                d = pub(sess, "/markets", f"series_ticker={st}&status=open&limit=100" + (f"&cursor={cur}" if cur else ""))
                ms = d.get("markets", [])
                for m in ms:
                    stats["scanned"] += 1
                    if m.get("mve_collection_ticker") or (m.get("market_type") and m.get("market_type") != "binary"):
                        stats["not_binary"] += 1; continue
                    if "maker_fee" in (m.get("fee_type") or "").lower():
                        stats["maker_fee"] += 1; continue
                    yb = fnum(m.get("yes_bid_dollars")); ya = fnum(m.get("yes_ask_dollars"))
                    nb = fnum(m.get("no_bid_dollars"))
                    if yb is None or ya is None or nb is None or not (0 < yb < ya < 1):
                        stats["no_quote"] += 1; continue
                    mid = (yb + ya) / 2
                    if not (LONG_LO <= mid <= LONG_HI):
                        stats["out_of_band"] += 1; continue
                    if (ya - yb) > MAXSPREAD:
                        stats["wide_spread"] += 1; continue
                    vol = fnum(m.get("volume_fp")) or 0.0
                    if vol < MIN_VOL:
                        stats["low_vol"] += 1; continue
                    lf = _life_frac(m)             # EXEC: skip the final third (edge goes negative there)
                    if lf is not None and lf > MAX_LIFE_FRAC:
                        stats["late_life"] += 1; continue
                    stats["kept"] += 1
                    out.append({"ticker": m["ticker"], "series": st, "category": cat,
                                "no_bid": nb, "yes_ask": ya, "mid": mid, "spread": round(ya - yb, 4),
                                "volume": vol, "life_frac": (round(lf, 4) if lf is not None else None),
                                "title": (m.get("title") or "")[:70]})
                cur = d.get("cursor") or ""
                if not cur or not ms:
                    break
    return out, stats


def flow_toxic(sess, ticker, max_take, max_imb):
    """Counterparty-avoidance guard ported from the box A/B (KALSHI_LONGSHOT_ABXFER.md):
    skip a longshot if recent flow looks INFORMED -- (a) a large crossing take (box t33
    take-tail-trim, OOS +0.05-0.10c) or (b) heavily one-sided YES-buying into the longshot
    (a VPIN-style toxicity proxy / box t31-t32). Returns (toxic, reason)."""
    d = pub(sess, f"/markets/{ticker}/trades", "limit=50")
    trades = d.get("trades") or []
    if not trades:
        return False, ""
    buy_yes = buy_no = 0.0
    biggest = 0.0
    for t in trades:
        c = fnum(t.get("count")) or 0.0
        biggest = max(biggest, c)
        if (t.get("taker_side") or "").lower() == "yes":
            buy_yes += c
        else:
            buy_no += c
    if biggest > max_take:
        return True, f"large take {biggest:.0f}>{max_take}"
    tot = buy_yes + buy_no
    if tot >= 20:                              # need enough flow to judge
        imb = (buy_yes - buy_no) / tot         # +1 = all aggressive YES-buying (toxic for our NO)
        if imb > max_imb:
            return True, f"one-sided YES-buy imb {imb:+.2f}>{max_imb}"
    return False, ""


def main():
    live = os.environ.get("LONGSHOT_LIVE", "0") == "1"
    clip = int(os.environ.get("LONGSHOT_CLIP", "1"))
    max_theme = int(os.environ.get("LONGSHOT_MAX_THEME", "3"))  # SIZING: tight per-theme cap = more
    # independent themes = higher Sharpe (KALSHI_LONGSHOT_SIZING.md: Sharpe ~ sqrt(uncorrelated themes);
    # clustering bets into few themes halves it). Breadth across themes is THE Sharpe lever, not clip size.
    max_notional = float(os.environ.get("LONGSHOT_MAX_NOTIONAL", "200"))
    max_pos = int(os.environ.get("LONGSHOT_MAX_POS", "120"))
    ttl = int(os.environ.get("LONGSHOT_TTL", "82800"))
    flow_guard = os.environ.get("LONGSHOT_FLOW_GUARD", "1") == "1"   # box-A/B counterparty-avoidance transfer
    max_take = float(os.environ.get("LONGSHOT_MAX_TAKE", "100"))     # box t33 take-tail-trim threshold
    max_imb = float(os.environ.get("LONGSHOT_MAX_FLOWIMB", "0.70"))  # one-sided YES-buy toxicity cap
    sess = requests.Session()

    pk = None
    if live:
        pk = _load_private_key()
        if pk is None or not os.environ.get("KALSHI_API_KEY_ID"):
            print("[FATAL] LONGSHOT_LIVE=1 but KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH not set."); sys.exit(2)

    # existing exposure (live): positions + resting orders, to respect caps & avoid double-quoting
    have_ticker, theme_ct, notional = set(), {}, 0.0
    if live:
        sc, pos = _api(sess, pk, "GET", "/portfolio/positions", params={"limit": 1000})
        for p in (pos or {}).get("market_positions", []) if isinstance(pos, dict) else []:
            if p.get("position"):
                have_ticker.add(p.get("ticker"))
        sc, od = _api(sess, pk, "GET", "/portfolio/orders", params={"status": "resting", "limit": 1000})
        for o in (od or {}).get("orders", []) if isinstance(od, dict) else []:
            have_ticker.add(o.get("ticker"))
        bal = _api(sess, pk, "GET", "/portfolio/balance")[1]
        print(f"[balance] {bal}")

    run_ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    audit = []                                   # one record PER candidate decision (the decision log)

    def log(c, decision, reason, **extra):
        rec = {"run_ts": run_ts, "live": live, "ticker": c["ticker"], "category": c["category"],
               "series": c["series"], "mid": c["mid"], "no_bid": c["no_bid"], "yes_ask": c["yes_ask"],
               "spread": c.get("spread"), "volume": c.get("volume"), "life_frac": c.get("life_frac"),
               "decision": decision, "reason": reason}
        rec.update(extra)
        audit.append(rec)

    cands, scan_stats = scan_longshots(sess, want=400)
    print(f"[scan] kept {len(cands)} of {scan_stats['scanned']} scanned (mid {LONG_LO}-{LONG_HI}) | rejects: "
          + ", ".join(f"{k}={v}" for k, v in scan_stats.items() if k not in ("scanned", "kept") and v))
    placed = skipped = 0
    for c in cands:
        tk = c["ticker"]; th = c["series"]
        if placed >= max_pos:
            log(c, "skip", "max_pos_reached"); skipped += 1; continue
        if tk in have_ticker:
            log(c, "skip", "already_held_or_quoted"); skipped += 1; continue
        if theme_ct.get(th, 0) + clip > max_theme:
            log(c, "skip", "theme_cap"); skipped += 1; continue
        cost = c["no_bid"] * clip            # collateral committed if filled
        if notional + cost > max_notional:
            log(c, "skip", "notional_cap"); skipped += 1; continue
        if flow_guard:                       # box-A/B counterparty-avoidance: dodge informed flow
            toxic, why = flow_toxic(sess, tk, max_take, max_imb)
            if toxic:
                print(f"  SKIP(toxic) {tk} [{why}] | {c['title']}")
                log(c, "skip", "flow_toxic", detail=why); skipped += 1; continue
        # harvest: rest a maker NO-buy at the NO touch (no_bid); fills when a NO seller hits us
        price = c["no_bid"]
        if live:
            oid, sc, err = place_no_buy(sess, pk, tk, price, clip, ttl)
            ok = oid is not None
            print(f"  {'PLACED' if ok else 'REJECT'} NO-buy {tk} @{price:.3f} x{clip} "
                  f"(yes_mid {c['mid']:.2f}) {'' if ok else f'[{sc} {err}]'} | {c['title']}")
            if not ok:
                log(c, "reject", "venue_reject", price=price, clip=clip, http=sc, err=str(err)[:120])
                continue
            log(c, "place", "placed", price=price, clip=clip, order_id=oid, collateral=round(cost, 4))
        else:
            print(f"  DRY  NO-buy {tk} @{price:.3f} x{clip} (yes_mid {c['mid']:.2f}) | {c['category']} | {c['title']}")
            log(c, "place", "dry_run", price=price, clip=clip, collateral=round(cost, 4))
        placed += 1; theme_ct[th] = theme_ct.get(th, 0) + clip; notional += cost; have_ticker.add(tk)

    # ---- write the decision audit (JSONL) so it can be joined to the collector by ticker+time ----
    audit_path = os.environ.get("LONGSHOT_AUDIT", "longshot_audit.jsonl")
    try:
        os.makedirs(os.path.dirname(audit_path), exist_ok=True) if os.path.dirname(audit_path) else None
        with open(audit_path, "a") as f:
            f.write(json.dumps({"run_ts": run_ts, "live": live, "type": "scan_summary",
                                "scan_stats": scan_stats, "placed": placed, "skipped": skipped,
                                "notional": round(notional, 4), "config": {
                                    "band": [LONG_LO, LONG_HI], "max_life_frac": MAX_LIFE_FRAC,
                                    "clip": clip, "flow_guard": flow_guard, "max_take": max_take,
                                    "max_imb": max_imb}}) + "\n")
            for rec in audit:
                f.write(json.dumps(rec) + "\n")
        print(f"[audit] {len(audit)} decisions + 1 summary -> {audit_path}")
    except Exception as e:
        print(f"[audit] WARN could not write {audit_path}: {e}")

    print(f"[done] {'LIVE' if live else 'DRY-RUN'} | quoted {placed} longshots | skipped {skipped} "
          f"(dup/theme/notional/toxic) | committed ${notional:.2f}/{max_notional:.0f} collateral")
    if not live:
        print("       set LONGSHOT_LIVE=1 (with keys) to place real maker NO-buys. Start tiny: CLIP=1.")


if __name__ == "__main__":
    main()
