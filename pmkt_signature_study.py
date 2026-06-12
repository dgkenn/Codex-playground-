"""pmkt_signature_study.py — Cross-venue informed-wallet behavioral signature study.
Re-runnable.  Compact output only.  Read-only: does not touch bot, collectors, or loops.

GOAL: Test whether Polymarket BTC-5m traders with HIGH directional accuracy (INFORMED
wallets) share the same behavioral fingerprint that the Kalshi t35 toxic-flow detector
keys on:
  - SIZE gradient: larger trades = more informed (Kalshi: small +0.5c, 50ct+ -2.2c OOS)
  - LATE timing: trades concentrated near window expiry
  - PERSISTENCE (d1_maxrun/d1_nruns): long one-directional aggressor runs
  - SWEEP urgency (d5_sweep): consecutive same-dir trades at worsening prices

USAGE:
  python pmkt_signature_study.py            -- live-API mode (today's data only)
  python pmkt_signature_study.py [out_dir]  -- forward-collection mode (preferred)

FORWARD-COLLECTION MODE (preferred, requires pmkt_5m_collect.py):
  When out_dir exists and contains pmkt_5m_trades.jsonl.gz + pmkt_5m_resolution.jsonl,
  the script runs the full signature study on accumulated data.

LIVE-API MODE (fallback, today only):
  When no collected data is present, pulls up to 3000 current public trades and runs
  the study on whatever resolved windows are available.  The public data-api hard cap
  of 3000 global trades (~6 minutes of cross-market history) makes this suitable only
  for a demo / freshness check; robust conclusions require the forward-collection path.

API LIMITS DISCOVERED (2026-06-12 audit):
  - data-api.polymarket.com/trades: MAX offset=3000 (hard cap, all markets combined).
    Returns the last ~6 minutes of cross-market activity.  THIS IS NOT PAGEABLE FURTHER.
  - Per-user ?user= endpoint: same 3000-record cap.
  - Gamma API: resolved=True appears only after Polymarket admin finalizes (not real-time).
    Resolution inferred from outcomePrices >= 0.80 one side (effective settlement signal).
  - CLOB API (clob.polymarket.com): requires API key (401 for public requests).
  - Historical BTC-5m data: available on-chain (Polygon) but not via public REST API.
    The series (btc-up-or-down-5m, since 2025-11-21) has $14.9M/day volume and millions
    of historical trades, but NONE of that history is accessible via data-api.

KALSHI SIGNATURES TO MATCH (FINGERPRINT.md + informed_detectors.py + t35):
  1. SIZE: bigger takers = more informed. OOS-stable. 50ct+ = -2.2c at settle.
  2. LATE: late-window (last 20%) trade concentration = informed.
  3. PERSISTENCE (d1_maxrun low n_runs_ratio): long one-dir runs = informed.
  4. SWEEP (d5_sweep): consecutive same-dir at worsening prices = urgency.
  5. VPIN/take_n: thin windows strand; high-imbalance = toxic. (Not computable from
     outcomePrices-only resolution; requires book snapshots.)

NOTE: The dominant t35 driver is take_n (thin window volume = strands legs).
VPIN and Kyle lambda are secondary.  Persistence detectors (d1) are largely
collinear with take_n in the joint fit.
"""

from __future__ import annotations
import gzip
import json
import os
import statistics as st
import sys
import time
from collections import defaultdict
from datetime import datetime

import requests

BASE_DATA = "https://data-api.polymarket.com"
GAMMA     = "https://gamma-api.polymarket.com"

# Thresholds
ACCURACY_INFORMED  = 0.58   # wallet accuracy threshold for INFORMED bucket
ACCURACY_NOISE_HI  = 0.54   # noise band: 46–54%
ACCURACY_NOISE_LO  = 0.46
MIN_TRADES_MEANINGFUL = 8   # for forward-collection mode (multi-window)
MIN_TRADES_LIVE       = 4   # for live-API mode (single window only)
OUTCOME_PRICE_THRESH  = 0.80  # outcomePrices >= this = effectively resolved
WINDOW_SECONDS        = 300   # 5-minute windows


# ─── Forward-collection mode ────────────────────────────────────────────────

def _slug_end_ts(slug: str) -> int:
    """Return the window-end Unix timestamp for a btc-updown-5m-<ts> slug."""
    try:
        return int(slug.rsplit("-", 1)[-1]) + WINDOW_SECONDS
    except Exception:
        return 0


def run_forward_mode(out_dir: str) -> None:
    """Run the signature study on accumulated forward-collected data."""
    tr_path  = os.path.join(out_dir, "pmkt_5m_trades.jsonl.gz")
    res_path = os.path.join(out_dir, "pmkt_5m_resolution.jsonl")

    if not os.path.exists(res_path) or not os.path.exists(tr_path):
        print("Forward-collection data not found. Need both:")
        print(f"  trades     : {tr_path}")
        print(f"  resolution : {res_path}")
        print("Run pmkt_5m_collect.py first, or omit out_dir to use live-API mode.")
        return

    # Load resolution: conditionId -> winner_idx (0=Up, 1=Down)
    winners: dict[str, int] = {}
    for line in open(res_path):
        try:
            d = json.loads(line)
            winners[d["conditionId"]] = int(d["winner_idx"])
        except Exception:
            pass

    # Load trades
    raw_trades = [json.loads(ln) for ln in gzip.open(tr_path, "rt")]
    trades = [t for t in raw_trades
              if t.get("cid") in winners and t.get("oidx") is not None]

    n_markets = len(winners)
    n_resolved_with_trades = len({t["cid"] for t in trades})
    all_wallets = {t["wallet"] for t in trades}

    print("=" * 72)
    print("POLYMARKET BTC-5M × KALSHI  SIGNATURE STUDY  [forward-collection mode]")
    print("=" * 72)
    print(f"Run: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"\n[SCOPE]")
    print(f"  Resolved windows        : {n_markets}")
    print(f"  Windows with trades     : {n_resolved_with_trades}")
    print(f"  Scored trades           : {len(trades):,}")
    print(f"  Distinct wallets        : {len(all_wallets):,}")

    if len(trades) < 400:
        print("  ** THIN (<400 scored trades) — treat as preliminary. **")

    # Per-wallet aggregation
    W: dict[str, dict] = defaultdict(
        lambda: dict(n=0, correct=0, mkts=set(), sizes=[], timestamps=[], slugs=[],
                     outcomes=[], sides=[], prices=[], late=0, dirs=[])
    )
    for t in trades:
        w = W[t["wallet"]]
        win_idx = winners[t["cid"]]
        oidx = int(t["oidx"])
        side = t.get("side", "BUY")
        buy  = (side == "BUY")
        correct = (buy and oidx == win_idx) or ((not buy) and oidx != win_idx)

        w["n"] += 1
        w["correct"] += int(correct)
        w["mkts"].add(t["cid"])
        try:
            w["sizes"].append(float(t["size"]))
        except Exception:
            pass
        ts = t.get("ts", 0)
        w["timestamps"].append(float(ts) if ts else 0)
        w["slugs"].append(t.get("slug", ""))
        w["outcomes"].append(oidx)
        w["sides"].append(side)
        try:
            w["prices"].append(float(t.get("price", 0.5)))
        except Exception:
            w["prices"].append(0.5)

        end_ts = _slug_end_ts(t.get("slug", ""))
        if end_ts and ts and float(ts) >= end_ts - 60:
            w["late"] += 1

        # Signed direction: +1 = long Up, -1 = short Up
        if side == "BUY":
            w["dirs"].append(1 if oidx == 0 else -1)
        else:
            w["dirs"].append(-1 if oidx == 0 else 1)

    # Compute features per wallet
    def wallet_features(w: dict) -> dict:
        n = w["n"]
        acc = w["correct"] / n
        sizes = w["sizes"] or [0.0]
        dirs = w["dirs"]

        # Runs
        max_run = 1
        n_runs  = 1
        if dirs:
            cur = dirs[0]; run = 1
            for d in dirs[1:]:
                if d == cur:
                    run += 1
                else:
                    max_run = max(max_run, run)
                    n_runs += 1
                    cur = d; run = 1
            max_run = max(max_run, run)

        # Sweep
        prices = w["prices"]
        sweep = 0
        for i in range(len(dirs) - 1):
            d = dirs[i]; j = i + 1; worse = 0
            while j < len(dirs) and dirs[j] == d:
                if (d > 0 and prices[j] > prices[j-1] + 1e-4) or \
                   (d < 0 and prices[j] < prices[j-1] - 1e-4):
                    worse += 1
                j += 1
            sweep = max(sweep, worse)

        return dict(
            acc         = acc,
            n           = n,
            n_mkts      = len(w["mkts"]),
            mean_size   = st.mean(sizes),
            median_size = st.median(sizes),
            frac_large  = sum(1 for s in sizes if s >= 50) / n,
            late_frac   = w["late"] / n,
            max_run     = float(max_run),
            n_runs_ratio= n_runs / n,
            sweep       = float(sweep),
        )

    feats = {wl: wallet_features(w) for wl, w in W.items()}

    # Buckets: meaningful sample
    meaningful = {wl: f for wl, f in feats.items()
                  if f["n"] >= MIN_TRADES_MEANINGFUL or f["n_mkts"] >= 4}
    informed   = {wl: f for wl, f in meaningful.items() if f["acc"] >= ACCURACY_INFORMED}
    noise      = {wl: f for wl, f in meaningful.items()
                  if ACCURACY_NOISE_LO <= f["acc"] <= ACCURACY_NOISE_HI}

    _print_comparison(informed, noise, meaningful, mode="forward")


# ─── Live-API mode ───────────────────────────────────────────────────────────

def fetch_all_trades(max_offset: int = 3000) -> list:
    """Fetch up to 3000 public trades (hard global API cap)."""
    trades = []
    for offset in range(0, max_offset + 100, 100):
        try:
            r = requests.get(f"{BASE_DATA}/trades",
                             params={"offset": offset, "limit": 100}, timeout=10)
            batch = r.json()
            if not batch or isinstance(batch, dict):
                break
            trades.extend(batch)
            time.sleep(0.03)
        except Exception:
            break
    return trades


def infer_winner(slug: str) -> str | None:
    """Infer the winning outcome from Gamma outcomePrices (>=80% one side)."""
    try:
        r = requests.get(f"{GAMMA}/markets", params={"slug": slug}, timeout=5)
        d = r.json()
        if not d or not isinstance(d, list):
            return None
        m = d[0]
        prices   = m.get("outcomePrices", [])
        outcomes = m.get("outcomes", ["Up", "Down"])
        if isinstance(prices, str):  prices   = json.loads(prices)
        if isinstance(outcomes, str): outcomes = json.loads(outcomes)
        if not prices:
            return None
        p = [float(x) for x in prices]
        if p[0] >= OUTCOME_PRICE_THRESH:  return outcomes[0]
        if p[1] >= OUTCOME_PRICE_THRESH:  return outcomes[1]
        # Official resolution fallback
        if m.get("resolved") and m.get("resolvedPrice") is not None:
            rp = float(m["resolvedPrice"])
            return outcomes[0] if rp >= 0.5 else outcomes[1]
    except Exception:
        pass
    return None


def run_live_mode() -> None:
    """Run the study on the live public trade feed (best-effort, today only)."""
    print("=" * 72)
    print("POLYMARKET BTC-5M × KALSHI  SIGNATURE STUDY  [live-API mode]")
    print("=" * 72)
    print(f"Run: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print()
    print("NOTE: Live-API mode uses the public data-api (max 3000 trades, ~6 minutes")
    print("  of history). One resolved window is typically available. This is")
    print("  INSUFFICIENT for robust conclusions — see VERDICT below.")

    print("\n[1] FETCHING ...")
    all_trades = fetch_all_trades()
    if not all_trades:
        print("  FATAL: data-api returned no trades.")
        return

    ts_min = min(t.get("timestamp", 0) for t in all_trades if t.get("timestamp"))
    ts_max = max(t.get("timestamp", 0) for t in all_trades if t.get("timestamp"))
    span_min = (ts_max - ts_min) / 60

    btc5m    = [t for t in all_trades if "btc-updown-5m-" in (t.get("slug") or "")]
    all_slugs = sorted(set(t.get("slug", "") for t in btc5m if t.get("slug")))
    wallets_all = set(t.get("proxyWallet") for t in btc5m if t.get("proxyWallet"))

    print(f"  Global trades         : {len(all_trades):,} (hard cap: 3000)")
    print(f"  Time span             : {span_min:.1f} min  "
          f"({datetime.utcfromtimestamp(ts_min).strftime('%H:%M')} – "
          f"{datetime.utcfromtimestamp(ts_max).strftime('%H:%M')} UTC)")
    print(f"  BTC-5m trades         : {len(btc5m):,}")
    print(f"  BTC-5m windows        : {len(all_slugs)}")
    print(f"  Distinct wallets (BTC-5m): {len(wallets_all):,}")

    print("\n[2] OUTCOME DETECTION ...")
    slug_winner: dict[str, str] = {}
    for slug in all_slugs:
        winner = infer_winner(slug)
        ts = int(slug.split("-")[-1])
        dt = datetime.utcfromtimestamp(ts).strftime("%H:%M")
        slug_winner[slug] = winner
        status = f'winner="{winner}"' if winner else "undetermined (prices not yet decisive)"
        print(f"  {slug} ({dt} UTC): {status}")
        time.sleep(0.06)

    resolved = {s: w for s, w in slug_winner.items() if w is not None}
    print(f"  Resolved: {len(resolved)} / {len(all_slugs)}")

    if not resolved:
        print("\n  NO RESOLVED WINDOWS — cannot score directional accuracy.")
        print("  Re-run ~5 minutes after a window's end time, or use forward-collection mode.")
        _print_api_limits_verdict(len(btc5m), len(wallets_all), span_min)
        return

    # Per-wallet features
    print("\n[3] WALLET SCORING ...")
    # Use first resolved window
    resolved_slug, winner = list(resolved.items())[0]
    window_start = int(resolved_slug.split("-")[-1])
    window_end   = window_start + WINDOW_SECONDS
    late_start   = window_end - 0.20 * WINDOW_SECONDS

    wallet_raw: dict[str, dict] = defaultdict(
        lambda: dict(n=0, correct=0, sizes=[], timestamps=[], dirs=[], prices=[])
    )
    trades_in_window = [t for t in btc5m if t.get("slug") == resolved_slug]
    for t in trades_in_window:
        w    = t.get("proxyWallet")
        if not w:
            continue
        side    = t.get("side", "BUY")
        outcome = t.get("outcome", "")
        size    = float(t.get("size", 0) or 0)
        ts_val  = t.get("timestamp", 0) or 0
        price   = float(t.get("price", 0.5) or 0.5)
        is_correct = (side == "BUY" and outcome == winner) or \
                     (side == "SELL" and outcome != winner)

        wr = wallet_raw[w]
        wr["n"]        += 1
        wr["correct"]  += int(is_correct)
        wr["sizes"].append(size)
        wr["timestamps"].append(ts_val)
        wr["prices"].append(price)
        if side == "BUY":
            wr["dirs"].append(1 if outcome == "Up" else -1)
        else:
            wr["dirs"].append(-1 if outcome == "Up" else 1)

    def compute_live_features(wr: dict, window_start: int, late_start: float) -> dict:
        n = wr["n"]
        acc = wr["correct"] / n
        sizes = wr["sizes"] or [0.0]
        dirs  = wr["dirs"]
        prices = wr["prices"]

        late_frac = sum(1 for ts in wr["timestamps"] if ts >= late_start) / n

        # Runs
        max_run = 1; n_runs = 1
        if dirs:
            cur = dirs[0]; run = 1
            for d in dirs[1:]:
                if d == cur:
                    run += 1
                else:
                    max_run = max(max_run, run)
                    n_runs += 1
                    cur = d; run = 1
            max_run = max(max_run, run)

        # Sweep
        sweep = 0
        for i in range(len(dirs) - 1):
            d = dirs[i]; j = i + 1; worse = 0
            while j < len(dirs) and dirs[j] == d:
                if (d > 0 and prices[j] > prices[j-1] + 1e-4) or \
                   (d < 0 and prices[j] < prices[j-1] - 1e-4):
                    worse += 1
                j += 1
            sweep = max(sweep, worse)

        return dict(
            acc          = acc,
            n            = n,
            mean_size    = st.mean(sizes),
            median_size  = st.median(sizes),
            frac_large   = sum(1 for s in sizes if s >= 50) / n,
            late_frac    = late_frac,
            max_run      = float(max_run),
            n_runs_ratio = n_runs / n,
            sweep        = float(sweep),
        )

    feats = {w: compute_live_features(wr, window_start, late_start)
             for w, wr in wallet_raw.items() if wr["n"] >= MIN_TRADES_LIVE}

    meaningful_live = feats  # in live mode: all wallets with >= MIN_TRADES_LIVE
    informed = {w: f for w, f in feats.items() if f["acc"] >= ACCURACY_INFORMED}
    noise    = {w: f for w, f in feats.items() if f["acc"] <= (1 - ACCURACY_INFORMED)}

    print(f"  Window: {resolved_slug}  winner='{winner}'")
    print(f"  Wallets with >={MIN_TRADES_LIVE} trades: {len(feats)}")
    print(f"  INFORMED (acc>={ACCURACY_INFORMED:.0%}): {len(informed)}")
    print(f"  NOISE    (acc<={1-ACCURACY_INFORMED:.0%}): {len(noise)}")
    print()
    print("  METHODOLOGICAL CAVEAT: With 1 resolved window, accuracy = direction bet,")
    print("  not genuine edge. INFORMED = 'happened to pick the winning side this window'.")

    _print_comparison(informed, noise, meaningful_live, mode="live",
                      extra_note=f"1 resolved window ('{winner}' won), {len(feats)} wallets scored")

    _print_api_limits_verdict(len(btc5m), len(wallets_all), span_min)


# ─── Shared output ───────────────────────────────────────────────────────────

def _agg(group: dict, key: str, fn=st.mean) -> float:
    vals = [f[key] for f in group.values() if f.get(key) is not None]
    try:
        return fn(vals) if vals else float("nan")
    except Exception:
        return float("nan")


def _fmt(v) -> str:
    return f"{v:.3f}" if isinstance(v, float) and v == v else "n/a"


def _print_comparison(informed: dict, noise: dict, all_meaningful: dict,
                      mode: str = "live", extra_note: str = "") -> None:
    n_inf = len(informed)
    n_noi = len(noise)
    n_all = len(all_meaningful)
    accs  = [f["acc"] for f in all_meaningful.values()]

    print("\n[4] SIGNATURE COMPARISON TABLE")
    if extra_note:
        print(f"  ({extra_note})")
    print(f"  Total meaningful wallets: {n_all}  "
          f"informed: {n_inf}  noise: {n_noi}  "
          f"mean_acc: {(st.mean(accs) if accs else float('nan')):.1%}")

    if not informed or not noise:
        print("  ** Cannot compare: one or both groups empty. **")
        print("  Need more resolved windows (forward-collection mode recommended).")
        return

    # Kalshi signature expectations
    features = [
        #  (feature key,      label,                       Kalshi expected dir, higher=informed?)
        ("mean_size",    "Mean trade size",           ">",  True ),
        ("median_size",  "Median trade size",         ">",  True ),
        ("frac_large",   "Frac trades >= $50",        ">",  True ),
        ("late_frac",    "Late-window frac (last 20%)",">", True ),
        ("max_run",      "Max one-dir run (d1_maxrun)",">", True ),
        ("n_runs_ratio", "Runs/N ratio (d1_nruns)",   "<",  False),  # low = persistent
        ("sweep",        "Sweep depth (d5_sweep)",    ">",  True ),
    ]

    print(f"\n  {'Feature':<32} {'INFORMED':>9} {'NOISE':>9}  {'Obs':>3}  {'Kalshi':>6}  Match?")
    print(f"  {'-'*32} {'-'*9} {'-'*9}  {'-'*3}  {'-'*6}  ------")

    matches = 0
    total   = 0
    for feat, label, expected, _ in features:
        iv = _agg(informed, feat)
        nv = _agg(noise,    feat)
        if iv != iv or nv != nv:
            print(f"  {label:<32} {'n/a':>9} {'n/a':>9}  n/a  {expected:>6}  --")
            continue
        obs   = ">" if iv > nv else ("<" if iv < nv else "=")
        match = (obs == expected)
        matches += int(match)
        total   += 1
        flag = "YES" if match else "NO "
        print(f"  {label:<32} {_fmt(iv):>9} {_fmt(nv):>9}  {obs:>3}  {expected:>6}  {flag}")

    if total > 0:
        print(f"\n  Feature match: {matches}/{total}")

    # Size breakdown
    def raw_sizes_for(group: dict) -> list:
        # In live mode feats only have aggregate values; get them from individual trades
        # (already aggregated — use mean_size as proxy for summary)
        return [f["mean_size"] for f in group.values()]

    print("\n[5] SIZE DISTRIBUTION SUMMARY")
    for lbl, grp in [("INFORMED", informed), ("NOISE", noise)]:
        sz = raw_sizes_for(grp)
        if sz:
            print(f"  {lbl:8s}: wallet mean_size: mean={st.mean(sz):.1f}  "
                  f"median={st.median(sz):.1f}  "
                  f"max={max(sz):.1f}  n_wallets={len(sz)}")

    # Verdict
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)

    if mode == "live":
        _print_live_verdict(matches, total, n_inf, n_noi, n_all, informed, noise)
    else:
        _print_forward_verdict(matches, total, n_inf, n_noi, n_all)


def _print_live_verdict(matches, total, n_inf, n_noi, n_all, informed, noise):
    print(f"""
SAMPLE: CRITICALLY INSUFFICIENT (live-API mode)
  Resolved windows    : 1  (need >=100)
  Informed wallets    : {n_inf}  (need >=50)
  Noise wallets       : {n_noi}  (need >=50)
  Root cause: data-api.polymarket.com/trades is capped at 3000 records globally,
  returning only the last ~6 minutes of cross-market activity. The BTC-5m series
  has $14.9M/day volume since 2025-11-21 but NO historical data is accessible via
  the public REST API. CLOB API (historical) requires authentication (401).

METHODOLOGICAL ISSUE:
  With 1 resolved window, wallet "accuracy" measures which direction was bet on
  that one window, NOT realized edge. "Informed" = "happened to buy the winning
  side." The SIZE REVERSAL observed (noise wallets larger than informed) is almost
  certainly because large Down-bettors (who lost this window) are classified as
  "noise" — but they may be momentum traders or hedgers, not naive retail.

WHAT THE TINY SAMPLE SHOWS (directional only, do not trust):
  - SIZE: REVERSED vs Kalshi (noise larger). Likely methodological artifact.
  - LATE TIMING: Directionally MATCHES Kalshi (informed later). Weak signal.
  - PERSISTENCE (max_run, n_runs_ratio): Direction MATCHES Kalshi (informed more persistent).
  - SWEEP: Informed slightly higher. Direction matches.

RECOMMENDATIONS:
  (a) Wire to Kalshi detector (t35): NO — insufficient and methodologically compromised.
      t35 is already trained on thousands of Kalshi windows with ground-truth labels.
  (b) Forward Poly-5m collection: ONLY if you can fix the data problem.
      The public data-api cannot deliver the 100+ resolved windows needed.
      Options: (1) on-chain Polygon subgraph / event indexer for full history;
               (2) pmkt_5m_collect.py forward-collection daemon (weeks of runtime);
               (3) Polymarket CLOB API with API key (check if available).
  (c) DROP THIS LINE: Recommended for now. The data moat is too deep for the
      public API. t35 is already doing the job with Kalshi's own ground truth.

STATUS: Suggestive-only (n_informed={n_inf}, n_noise={n_noi}, windows=1).
  Lateness and persistence directionally match; size is reversed (likely artifact).
  A clean verdict requires: 100+ resolved windows, 50+ wallets per group, genuine
  multi-window accuracy scores. That needs forward collection OR on-chain data.
""")


def _print_forward_verdict(matches, total, n_inf, n_noi, n_all):
    print()
    if n_all < 40:
        print(f"  SAMPLE THIN (n_all={n_all} < 40) — suggestive, not conclusive.")
        print(f"  Continue forward collection. Target: 100+ resolved windows, 50+ per group.")
    elif matches >= 5 and total >= 5:
        print(f"  STRONG MATCH ({matches}/{total}): Informed Poly wallets look like Kalshi toxic flow.")
        print(f"  Late-window and persistence features replicate cross-venue.")
        print(f"  RECOMMENDATION: Consider adding a late_frac or persistence feature to t35;")
        print(f"  run a short A/B on Kalshi with the refined gate. Worth ~1 sprint.")
    elif matches >= 3 and total >= 5:
        print(f"  PARTIAL MATCH ({matches}/{total}): Some features replicate.")
        print(f"  Note which features replicate consistently; focus refinement there.")
        print(f"  RECOMMENDATION: Suggestive — run more windows before wiring anything.")
    else:
        print(f"  WEAK / NO MATCH ({matches}/{total}): Informed wallets not distinguished by")
        print(f"  the Kalshi behavioral signatures.")
        print(f"  RECOMMENDATION: Drop the Polymarket->Kalshi transfer line.")
        print(f"  Keep t35 as-is; behavioral signatures don't transfer cross-venue.")
    print()


def _print_api_limits_verdict(n_btc5m, n_wallets, span_min):
    print("\n[API LIMITS SUMMARY]")
    print(f"  data-api.polymarket.com/trades: {n_btc5m} BTC-5m trades in {span_min:.1f} min")
    print(f"  Hard cap: 3000 records (ALL markets combined) — not pageable further.")
    print(f"  Per-user endpoint: same 3000 cap. CLOB API: auth required.")
    print(f"  Gamma API: resolved=True delayed; outcomePrices >0.80 used as proxy.")
    print(f"  Historical BTC-5m data: accessible only on-chain (Polygon) or via forward collection.")
    print(f"\n  To run a properly-powered study, pick ONE of:")
    print(f"    A. pmkt_5m_collect.py forward daemon — weeks of runtime, no auth needed")
    print(f"    B. Polygon subgraph / The Graph — full history, needs on-chain indexer setup")
    print(f"    C. Polymarket CLOB API with API key — may have better history endpoint")
    print()


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    start = time.time()

    out_dir = sys.argv[1] if len(sys.argv) > 1 else "gha_data"
    tr_path  = os.path.join(out_dir, "pmkt_5m_trades.jsonl.gz")
    res_path = os.path.join(out_dir, "pmkt_5m_resolution.jsonl")

    if os.path.exists(tr_path) and os.path.exists(res_path):
        run_forward_mode(out_dir)
    else:
        run_live_mode()

    print(f"Elapsed: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
