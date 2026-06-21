"""qcex_longshot_probe.py -- PORTABILITY TEST of the validated Kalshi longshot-maker edge
onto Polymarket-US / QCEX, using the OFFSHORE Polymarket CLOB+Gamma API as a PROXY.

WHY A PROXY (read QCEX_PORTABILITY.md for the full access reality):
  Polymarket-US (QCX/QCEX, the CFTC-licensed DCM) IS live for US retail (waitlist dropped
  May 2026, iOS), BUT its market-data/order API is gated behind an application + sandbox +
  production-credential process (onboarding@polymarket.us, docs.polymarket.us) -- there is
  NO open public QCEX CLOB/REST/GraphQL endpoint we can hit today. The OFFSHORE venue
  (gamma-api.polymarket.com / clob.polymarket.com) IS public and is the SAME order-book
  engine + product line Polymarket-US mirrors, so it is the best available proxy for the
  long-tail overpricing. CAVEAT: the US/QCEX user base (KYC'd, FCM-intermediated, USD-rail,
  no MA/IL/NJ/... ) may be SHARPER or DIFFERENT than the offshore crypto-native base, so the
  measured bias is a FORWARD-LOOKING proxy, not a deployable QCEX result.

THE METRIC (identical to kalshi_longshot_opt.py / KALSHI_LONGSHOT_OPT.md):
  Harvest side = SELL_YES (rest a NO bid; filled when a taker lifts YES).
    SELL_YES pnl/contract = fill_price - settle      (settle = 1 if YES resolved, else 0)
  We take a REAL PRE-SETTLEMENT price (the median traded YES price in a clean pre-resolution
  window, from CLOB /prices-history) as the maker's effective fill price, bin by price band,
  compute realized YES-rate vs price, and the SELL_YES P&L band-by-band, NET of the Mar-2026
  Polymarket fee schedule (makers pay ZERO -> net=gross for the maker; taker fee shown for
  context). Significance is EVENT-CLUSTERED (cluster on events[0].id), NOT per-trade -- the
  Becker lesson: markets sharing one event share one outcome and are not independent.

DATA PATH (validated live 2026-06-21):
  - Gamma /markets closed=true, end_date in a recent window, volume-sorted -> resolved binaries
    with outcomePrices (settlement) + clobTokenIds (YES=token[0]) + events[0].id (cluster key).
  - CLOB /prices-history?market=<yes_token>&interval=1m&fidelity=180 -> pre-settlement prices.
    NOTE: Polymarket purges CLOB history shortly after resolution, so only markets resolved in
    roughly the last ~2 weeks still serve history. We therefore scan a recent window and keep
    only those that still return history (this is a data-availability constraint, reported).

READ-ONLY: public Gamma + CLOB only. No auth, no orders, no money.

    python qcex_longshot_probe.py            # default scan
    python qcex_longshot_probe.py --out qcex_probe.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

# Mar-2026 Polymarket fee schedule (verified, see QCEX_PORTABILITY.md citations):
#   taker fee/contract = feeRate * p * (1-p);  MAKERS PAY ZERO + get 20-25% rebate.
FEE_RATE = {  # category constant -> taker feeRate; maker pays 0 in every category
    "crypto": 0.072, "economics": 0.05, "culture": 0.05, "weather": 0.05,
    "other": 0.05, "finance": 0.04, "politics": 0.04, "mentions": 0.04,
    "tech": 0.04, "sports": 0.03, "geopolitics": 0.0,
}

# Price bands -- IDENTICAL to KALSHI_LONGSHOT_OPT.md
BANDS = [(0.00, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20),
         (0.20, 0.25), (0.25, 0.35)]
CORE = (0.05, 0.15)  # the Kalshi sweet spot


def _jl(x):
    return json.loads(x) if isinstance(x, str) else x


def _iso(s):
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def fetch_resolved(session, end_min, end_max, pages=6, per=100):
    """Resolved binary markets in [end_min,end_max), volume-sorted, with settlement+tokens."""
    out = []
    for pg in range(pages):
        try:
            r = session.get(GAMMA + "/markets", params={
                "closed": "true", "limit": per, "offset": pg * per,
                "order": "volumeNum", "ascending": "false",
                "end_date_min": end_min, "end_date_max": end_max,
            }, timeout=30)
            d = r.json()
        except Exception:
            break
        if not d:
            break
        out.extend(d)
        time.sleep(0.25)
    return out


def presettle_price(session, token, end_ts):
    """Median traded YES price in a clean pre-settlement window (skip the last 12h, which is
    settlement-loaded / informed, mirroring the Kalshi 'fill early' finding). Returns
    (median_price, n_points, last_price) or (None,0,None)."""
    # interval=1m gives ~max retained history at fidelity 180 (3-min bars) for recent markets
    try:
        ph = session.get(CLOB + "/prices-history", params={
            "market": token, "interval": "1m", "fidelity": "180"}, timeout=20)
        hist = ph.json().get("history", [])
    except Exception:
        hist = []
    if not hist:
        return None, 0, None
    cutoff = (end_ts - 12 * 3600) if end_ts else None
    pre = [h for h in hist if (cutoff is None or h.get("t", 0) <= cutoff)]
    if len(pre) < 3:                      # too thin pre-window -> use all but final point
        pre = hist[:-1] if len(hist) > 3 else hist
    ps = [float(h["p"]) for h in pre if h.get("p") is not None]
    if not ps:
        return None, 0, None
    return statistics.median(ps), len(ps), ps[-1]


def cat_of(m):
    # Gamma 'category' is often None; infer from event/slug for fee bucket only.
    c = (m.get("category") or "").lower()
    if c in FEE_RATE:
        return c
    blob = (str(m.get("slug", "")) + " " +
            str((m.get("events") or [{}])[0].get("ticker", "")) + " " +
            str(m.get("question", ""))).lower()
    for key, tags in {
        "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana"],
        "sports": ["win on 20", "world-cup", "world cup", "nba", "nfl", "vs-", "beat"],
        "politics": ["president", "election", "senate", "congress", "governor", "primary"],
        "economics": ["fed", "rate", "cpi", "gdp", "inflation", "jobs", "recession"],
        "weather": ["temperature", "weather", "hurricane", "rain", "snow"],
        "tech": ["openai", "gpt", "ai-", "tech", "launch", "ship"],
        "geopolitics": ["peace", "ceasefire", "war", "deal-by", "treaty"],
    }.items():
        if any(t in blob for t in tags):
            return key
    return "other"


def collect(session, args):
    raw = fetch_resolved(session, args.end_min, args.end_max, args.pages)
    rows = []
    seen_tok = set()
    n_hist = n_nohist = 0
    for m in raw:
        toks = m.get("clobTokenIds")
        op = m.get("outcomePrices")
        if not toks or not op:
            continue
        toks = _jl(toks); op = _jl(op)
        if not toks or not op or len(op) < 2:
            continue
        # binary resolved: outcomePrices in {0,1}
        try:
            settle_yes = float(op[0])
        except Exception:
            continue
        if settle_yes not in (0.0, 1.0):
            continue
        yes_tok = str(toks[0])
        if yes_tok in seen_tok:
            continue
        seen_tok.add(yes_tok)
        end_ts = _iso(m.get("endDate") or "")
        price, npts, last = presettle_price(session, yes_tok, end_ts)
        if price is None:
            n_nohist += 1
            continue
        n_hist += 1
        evs = m.get("events") or [{}]
        event_id = str(evs[0].get("id") or evs[0].get("ticker") or m.get("slug") or yes_tok)
        cat = cat_of(m)
        vol = m.get("volumeNum") or m.get("volume") or 0
        rows.append({
            "q": m.get("question", "")[:80], "event_id": event_id, "cat": cat,
            "price": price, "last": last, "npts": npts,
            "settle_yes": int(settle_yes), "volume": float(vol or 0),
        })
        if (n_hist + n_nohist) % 25 == 0:
            print(f"  scanned {n_hist+n_nohist}: {n_hist} with history, {n_nohist} purged",
                  flush=True)
    print(f"  TOTAL resolved binaries scanned={len(seen_tok)}  "
          f"with-history={n_hist}  history-purged={n_nohist}")
    return rows


# ---- event-clustered stats (identical approach to kalshi_longshot_opt.py) ----
def clustered(rows, lo, hi):
    """SELL_YES net P&L in [lo,hi), event-clustered z + 95% CI. Maker fee = 0 (net=gross)."""
    sel = [r for r in rows if lo <= r["price"] < hi]
    if not sel:
        return None
    # per-contract SELL_YES pnl = price - settle  (maker fee 0)
    for r in sel:
        r["pnl"] = r["price"] - r["settle_yes"]
    n = len(sel)
    mean = sum(r["pnl"] for r in sel) / n
    yes_rate = sum(r["settle_yes"] for r in sel) / n
    avg_price = sum(r["price"] for r in sel) / n
    # cluster means by event
    byev = defaultdict(list)
    for r in sel:
        byev[r["event_id"]].append(r["pnl"])
    ev_means = [sum(v) / len(v) for v in byev.values()]
    k = len(ev_means)
    gm = sum(ev_means) / k
    if k > 1:
        var = sum((x - gm) ** 2 for x in ev_means) / (k - 1)
        se = math.sqrt(var / k)
    else:
        se = float("nan")
    z = gm / se if se and not math.isnan(se) and se > 0 else float("nan")
    ci = (gm - 1.96 * se, gm + 1.96 * se) if se and not math.isnan(se) else (None, None)
    return {"lo": lo, "hi": hi, "n": n, "n_events": k, "yes_rate": yes_rate,
            "avg_price": avg_price, "pnl_per_contract": mean,
            "event_clustered_mean": gm, "se": se, "z": z, "ci": ci}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--end_min", default="2026-06-05T00:00:00Z")
    ap.add_argument("--end_max", default="2026-06-21T00:00:00Z")
    ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("--out", default="qcex_probe.json")
    args = ap.parse_args()

    print(f"=== qcex_longshot_probe (OFFSHORE proxy)  resolved end in "
          f"[{args.end_min} .. {args.end_max}) ===")
    sess = requests.Session()
    rows = collect(sess, args)
    if not rows:
        raise SystemExit("STOP: no resolved markets with retained price history. "
                         "Widen --end_max toward today (history purges ~2wk post-resolution).")

    print(f"\n  usable resolved binaries with pre-settlement price: {len(rows)}")
    # Band-by-band
    print("\n  BAND-BY-BAND (SELL_YES, maker fee=0, event-clustered):")
    print(f"  {'band':<14}{'n':>5}{'n_evt':>6}{'avg_p':>8}{'yes_rate':>10}"
          f"{'pnl/ct':>10}{'z':>7}  95% CI")
    band_out = []
    for lo, hi in BANDS:
        s = clustered(rows, lo, hi)
        if not s:
            print(f"  [{lo:.2f},{hi:.2f})   (no data)")
            continue
        ci = s["ci"]
        cis = f"[{ci[0]:+.4f},{ci[1]:+.4f}]" if ci[0] is not None else "[n/a]"
        print(f"  [{lo:.2f},{hi:.2f})  {s['n']:>4}{s['n_events']:>6}{s['avg_price']:>8.3f}"
              f"{s['yes_rate']:>10.3f}{s['pnl_per_contract']:>+10.4f}{s['z']:>7.2f}  {cis}")
        band_out.append(s)

    core = clustered(rows, *CORE)
    print("\n  CORE BAND [0.05,0.15) (the Kalshi sweet spot):")
    if core:
        ci = core["ci"]
        print(f"    n_fills={core['n']}  n_events={core['n_events']}  "
              f"avg_price={core['avg_price']:.3f}  realized_yes_rate={core['yes_rate']:.3f}")
        print(f"    SELL_YES net (maker fee=0): {core['pnl_per_contract']*100:+.2f}c/contract  "
              f"event-clustered z={core['z']:.2f}  "
              f"95% CI [{ci[0]*100:+.2f}c, {ci[1]*100:+.2f}c]"
              if ci[0] is not None else "    (CI n/a, k<2)")
        print(f"    >> Kalshi reference: +5.45c, CI [+3.2c,+7.7c]. "
              f"OVERPRICED (sell-YES +EV) if realized_yes_rate < avg_price.")

    with open(args.out, "w") as f:
        json.dump({"rows": rows, "bands": band_out, "core": core,
                   "window": [args.end_min, args.end_max],
                   "metric": "SELL_YES pnl=price-settle, maker fee=0, event-clustered",
                   "proxy_note": "OFFSHORE polymarket.com data; QCEX/US base may be sharper"},
                  f, indent=2, default=str)
    print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
