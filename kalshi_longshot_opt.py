#!/usr/bin/env python3
"""
kalshi_longshot_opt.py

OPTIMIZE the soft-market longshot-MAKER harvest.

Builds on the validated baseline (KALSHI_MAKER_ADVSEL.md, KALSHI_MAKER_CAPACITY.md,
KALSHI_MAKER_RANK.md, KALSHI_MAKER_VERDICT.md):
  - The one surviving pocket is the MAKER who SELLS overpriced YES longshots (p<0.20)
    on soft, ZERO-maker-fee (`fee_type=quadratic`) Kalshi categories.
  - Realized maker P&L to settlement, net of fee = +0.97c/contract @ ~17sigma (263k fills).

THIS SCRIPT finds the OPTIMAL segmentation/filters that MAXIMIZE the net
(adverse-selection-inclusive) edge, with EVENT-CLUSTERED significance and an honest
multiple-testing read, plus a held-out / cross-category robustness gate.

Rigorous metric (same as advsel, the realized-P&L-to-settlement edge that bakes in
adverse selection because it is conditioned on the fill happening):
  taker_side=="yes": taker BOUGHT yes -> MAKER SOLD yes -> maker SHORT yes.
        pnl = fill_price - settle           (this is the LONGSHOT-SELL fill)
  taker_side=="no" : taker SOLD yes  -> MAKER BOUGHT yes -> maker LONG yes.
        pnl = settle - fill_price
  settle = 1.0 if result=="yes" else 0.0
  fee per contract = 0.07*p*(1-p) ONLY on `quadratic_with_maker_fees` series (else $0,
        because the validated corner is zero-maker-fee). We compute BOTH so we can
        confirm the zero-fee uplift.

For the LONGSHOT-SELL harvest the trader rests a NO bid (= offers YES) and is filled
when a taker LIFTS (buys YES) -> taker_side=="yes", maker SHORT yes. So the harvest
fills are exactly the taker_side=="yes" fills in the low-price band. We tag each fill
with which maker-side it is so the analysis can isolate the SELL-YES (NO-maker) flow.

Phase 1 (collect): scan ALL soft categories, cache raw per-fill records (+ metadata:
category, fee_type, event_ticker, event leg-count, volume, time-to-settle fraction,
series) to longshot_opt_fills.json.gz so analysis is re-runnable without re-hitting API.

Phase 2 (analyze): segment by fine price band x category x filters, cluster SE by EVENT
(not by fill -- fills in one event share one outcome and are NOT independent), apply a
Benjamini-Hochberg / Bonferroni-aware read, and gate any rich sub-pocket on a held-out
time split AND cross-category consistency.

Usage:
  python3 kalshi_longshot_opt.py collect      # phase 1 (network, slow, cached)
  python3 kalshi_longshot_opt.py analyze      # phase 2 (offline, from cache)
  python3 kalshi_longshot_opt.py all          # both
"""

import json
import gzip
import time
import sys
import math
import os
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
# All soft (non-crypto, non-sports) categories. Sports excluded (4.8% maker-fee
# flagships + weakest/noisiest bias per RANK). We still TAG fee_type per series so the
# analysis can exclude quadratic_with_maker_fees regardless.
CATEGORIES = ["Politics", "Economics", "Climate and Weather", "Entertainment",
              "Science and Technology", "World", "Companies"]
MIN_VOLUME_FP = 300.0
MAX_SERIES_PER_CAT = 120        # broaden vs advsel's 40 -> less weather-domination
MAX_MARKETS_PER_SERIES = 60
MAX_MARKETS_PER_CAT = 320       # per-category cap -> balanced, not weather-flooded
FEE_RATE = 0.07
REQUEST_PAUSE = 0.4             # STRICT rate limit per brief
CACHE = "longshot_opt_fills.json.gz"

# ---- only fills with fill price in this outer window are stored (longshot harvest
#      lives in the tails; we keep <0.35 to study the whole low band + a buffer).
STORE_PMAX = 0.35


def http_get(path, params=None, retries=6):
    url = BASE + path
    if params:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
                     if v is not None and v != "")
        url = url + "?" + q
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json",
                              "User-Agent": "longshot-opt-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (i + 1))            # exp-ish backoff on 429 per brief
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def parse_ts(s):
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------- discovery
def list_series(category):
    out, cursor = [], ""
    while True:
        d = http_get("/series", {"category": category, "limit": 100, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("series", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= 600:
            break
        time.sleep(REQUEST_PAUSE)
    return out


def list_settled_markets(series_ticker):
    out, cursor = [], ""
    while True:
        d = http_get("/markets", {"series_ticker": series_ticker, "status": "settled",
                                  "limit": 100, "cursor": cursor})
        if not d:
            break
        out.extend(d.get("markets", []))
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= MAX_MARKETS_PER_SERIES:
            break
        time.sleep(REQUEST_PAUSE)
    return out[:MAX_MARKETS_PER_SERIES]


def get_trades(ticker):
    out, cursor = [], ""
    for _ in range(30):
        d = http_get("/markets/trades", {"ticker": ticker, "limit": 1000, "cursor": cursor})
        if not d:
            break
        ts = d.get("trades", [])
        out.extend(ts)
        cursor = d.get("cursor") or ""
        if not cursor or not ts:
            break
        time.sleep(REQUEST_PAUSE)
    return out


# --------------------------------------------------------------- phase 1
def collect():
    fills = []                              # list of compact per-fill records
    meta = {"markets": 0, "series": 0, "by_cat": defaultdict(int),
            "fills_by_cat": defaultdict(int)}
    event_legcount = defaultdict(int)       # event_ticker -> # settled markets seen

    for cat in CATEGORIES:
        sys.stderr.write(f"\n=== {cat} ===\n")
        series = list_series(cat)
        sys.stderr.write(f"  series: {len(series)}\n")
        meta["series"] += len(series)
        scanned = 0
        cat_markets = 0
        for s in series:
            if cat_markets >= MAX_MARKETS_PER_CAT:
                break
            stk = s.get("ticker")
            if not stk:
                continue
            fee_type = s.get("fee_type")
            scanned += 1
            if scanned > MAX_SERIES_PER_CAT:
                break
            markets = list_settled_markets(stk)
            # first pass: count legs per event for THIS series' settled markets
            for m in markets:
                ev = m.get("event_ticker")
                if ev:
                    event_legcount[ev] += 1
            for m in markets:
                if cat_markets >= MAX_MARKETS_PER_CAT:
                    break
                if m.get("mve_collection_ticker"):
                    continue
                if m.get("market_type") not in (None, "binary"):
                    continue
                vol = fnum(m.get("volume_fp"), 0.0)
                if vol < MIN_VOLUME_FP:
                    continue
                result = m.get("result")
                if result not in ("yes", "no"):
                    continue
                settle = 1.0 if result == "yes" else 0.0
                tk = m.get("ticker")
                ev = m.get("event_ticker") or tk
                ot = parse_ts(m.get("open_time"))
                ct = parse_ts(m.get("close_time"))
                life = (ct - ot) if (ot and ct and ct > ot) else None
                trades = get_trades(tk)
                if not trades:
                    continue
                meta["markets"] += 1
                meta["by_cat"][cat] += 1
                cat_markets += 1
                kept = 0
                for t in trades:
                    if t.get("is_block_trade"):
                        continue
                    p = fnum(t.get("yes_price_dollars"))
                    if p is None or p <= 0 or p >= 1:
                        continue
                    if p > STORE_PMAX:           # only store the low band + buffer
                        continue
                    cnt = fnum(t.get("count_fp"), 0.0)
                    if cnt <= 0:
                        continue
                    tside = t.get("taker_side")
                    if tside not in ("yes", "no"):
                        continue
                    tepoch = parse_ts(t.get("created_time"))
                    # time-to-settle fraction of life remaining at fill (0=at close,1=at open)
                    ttf = None
                    if life and tepoch and ot:
                        ttf = max(0.0, min(1.0, (ct - tepoch) / life))
                    # maker side & realized pnl to settlement
                    if tside == "yes":          # maker SOLD yes -> SHORT yes (the harvest)
                        maker = "SELL_YES"       # == buy-NO maker
                        pnl = p - settle
                    else:                        # maker BOUGHT yes -> LONG yes
                        maker = "BUY_YES"
                        pnl = settle - p
                    fills.append([
                        round(p, 4),             # 0 fill yes-price
                        round(cnt, 2),           # 1 contracts
                        round(pnl, 4),           # 2 raw pnl to settle (pre-fee)
                        maker,                   # 3 maker side
                        cat,                     # 4 category
                        (fee_type or "quadratic"),  # 5 fee_type
                        ev,                      # 6 event_ticker (cluster id)
                        round(ttf, 3) if ttf is not None else None,  # 7 time-frac left
                        round(vol, 0),           # 8 market life volume
                        tk,                      # 9 market ticker
                    ])
                    kept += 1
                meta["fills_by_cat"][cat] += kept
                sys.stderr.write(
                    f"    {tk} r={result} v={vol:.0f} kept={kept} "
                    f"(cat#{cat_markets}, tot#{meta['markets']})\n")

    # attach event leg-count onto each fill (#legs in its event)
    out = {
        "fills": fills,
        "event_legcount": dict(event_legcount),
        "meta": {"markets": meta["markets"], "series": meta["series"],
                 "by_cat": dict(meta["by_cat"]),
                 "fills_by_cat": dict(meta["fills_by_cat"]),
                 "fee_rate": FEE_RATE, "min_volume_fp": MIN_VOLUME_FP,
                 "store_pmax": STORE_PMAX,
                 "ts": datetime.now(timezone.utc).isoformat()},
    }
    with gzip.open(CACHE, "wt") as f:
        json.dump(out, f)
    sys.stderr.write(f"\nWROTE {CACHE}: {len(fills)} fills, {meta['markets']} markets\n")
    return out


# --------------------------------------------------------------- analysis helpers
def fee(p):
    return FEE_RATE * p * (1.0 - p)


def clustered_stats(records, by_event, vw=True):
    """records: list of (pnl, contracts, event_id). Returns (point, se, n_fills,
    n_events, contracts). Point estimate is contract-weighted (vw) or trade-weighted.
    SE is clustered by EVENT: aggregate each event into one observation
    (its weighted-mean pnl + total weight), then compute a weighted-mean SE across
    events. This is the honest unit because all fills in one event share one outcome."""
    ev_num = defaultdict(float)   # sum w*pnl
    ev_w = defaultdict(float)     # sum w
    ev_nf = defaultdict(int)
    tot_w = 0.0
    tot_num = 0.0
    n_fills = 0
    for pnl, c, ev in records:
        w = c if vw else 1.0
        ev_num[ev] += w * pnl
        ev_w[ev] += w
        ev_nf[ev] += 1
        tot_num += w * pnl
        tot_w += w
        n_fills += 1
    n_events = len(ev_w)
    if tot_w <= 0 or n_events < 2:
        point = tot_num / tot_w if tot_w > 0 else float("nan")
        return point, float("nan"), n_fills, n_events, tot_w
    point = tot_num / tot_w
    # event-level weighted mean and clustered SE of the weighted mean.
    # Treat each event mean m_e with weight W_e. Weighted point = sum(W_e m_e)/sum(W_e).
    # Clustered variance estimate (weighted, cluster-robust):
    #   var = [ sum W_e^2 (m_e - point)^2 ] / (sum W_e)^2   * n/(n-1)
    s2 = 0.0
    for ev in ev_w:
        m_e = ev_num[ev] / ev_w[ev]
        W_e = ev_w[ev]
        s2 += (W_e ** 2) * (m_e - point) ** 2
    var = s2 / (tot_w ** 2) * (n_events / (n_events - 1))
    se = math.sqrt(max(var, 0.0))
    return point, se, n_fills, n_events, tot_w


def fmt(point, se):
    if se != se or se == 0:
        return f"{point:+.4f}(se   n/a)"
    z = point / se
    return f"{point:+.4f}(se{se:.4f} z{z:+.1f})"


# --------------------------------------------------------------- phase 2
def analyze():
    with gzip.open(CACHE, "rt") as f:
        blob = json.load(f)
    fills = blob["fills"]
    legcount = blob["event_legcount"]
    meta = blob["meta"]

    # index columns
    P, C, PNL, MAKER, CAT, FEE, EV, TTF, VOL, TK = range(10)

    def fee_for(rec, apply_maker_fee):
        # zero maker fee on plain quadratic; 0.25*taker on quadratic_with_maker_fees
        if rec[FEE] == "quadratic_with_maker_fees":
            return 0.25 * fee(rec[P])
        return 0.0 if not apply_maker_fee else fee(rec[P])

    # We harvest the SELL_YES (buy-NO) maker side: fills where taker lifted YES.
    # Net pnl = raw pnl - applicable maker fee (zero on quadratic series).
    def netrec(rec):
        return (rec[PNL] - fee_for(rec, apply_maker_fee=True), rec[C], rec[EV])

    sell = [r for r in fills if r[MAKER] == "SELL_YES"]

    lines = []
    def out(s=""):
        lines.append(s)
        print(s)

    out("==== KALSHI LONGSHOT-MAKER HARVEST OPTIMIZER ====")
    out(f"cache ts: {meta.get('ts')}")
    out(f"markets: {meta['markets']}  series scanned: {meta['series']}")
    out("markets by cat: " + ", ".join(f"{k}={v}" for k, v in meta["by_cat"].items()))
    out(f"stored fills (p<{meta['store_pmax']}): {len(fills)}  "
        f"SELL_YES(harvest)={len(sell)}  BUY_YES={len(fills)-len(sell)}")
    out("")
    out("METRIC = maker realized P&L to settlement, NET of applicable maker fee "
        "($/contract,+=maker wins).")
    out("Harvest side = SELL_YES (rest a NO bid; filled when a taker lifts YES).")
    out("SE is CLUSTERED BY EVENT (fills in one event share one outcome -> not independent).")
    out("VW = contract(dollar)-weighted; the number a real maker actually absorbs.")
    out("")

    # ---------------- 1) PRICE BAND sweep (SELL_YES, all soft, zero-fee universe) -----
    bands = [(0.00, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20),
             (0.20, 0.25), (0.25, 0.35)]
    out("---- (1) PRICE BAND sweep | SELL_YES maker | zero-maker-fee series only ----")
    out(f"{'band':>12} | {'VW net pnl (clustered)':>30} | {'n_fill':>7} {'n_evt':>6} {'contracts':>11}")
    zerofee = [r for r in sell if r[FEE] != "quadratic_with_maker_fees"]
    band_pts = {}
    for lo, hi in bands:
        recs = [netrec(r) for r in zerofee if lo <= r[P] < hi]
        pt, se, nf, ne, ct = clustered_stats(recs, None, vw=True)
        band_pts[(lo, hi)] = (pt, se, nf, ne, ct)
        out(f"  [{lo:.2f},{hi:.2f}) | {fmt(pt,se):>30} | {nf:7d} {ne:6d} {ct:11.0f}")
    out("")

    # ---------------- 2) CATEGORY x core-band (0.05-0.20) ----------------------------
    out("---- (2) CATEGORY ranking | SELL_YES | core band p in [0.05,0.20) | zero-fee ----")
    out(f"{'category':>22} | {'VW net pnl (clustered)':>30} | {'n_fill':>7} {'n_evt':>6} {'contracts':>11}")
    cats = sorted({r[CAT] for r in zerofee})
    cat_core = {}
    for cat in cats:
        recs = [netrec(r) for r in zerofee if r[CAT] == cat and 0.05 <= r[P] < 0.20]
        pt, se, nf, ne, ct = clustered_stats(recs, None, vw=True)
        cat_core[cat] = (pt, se, nf, ne, ct)
        out(f"  {cat:>22} | {fmt(pt,se):>30} | {nf:7d} {ne:6d} {ct:11.0f}")
    out("")

    # ---------------- 3) FILTERS lift (each vs the zero-fee core-band baseline) -------
    out("---- (3) FILTER LIFT | base = SELL_YES, zero-fee, p in [0.05,0.20) ----")
    base = [r for r in zerofee if 0.05 <= r[P] < 0.20]
    def stat(subset, label):
        recs = [netrec(r) for r in subset]
        pt, se, nf, ne, ct = clustered_stats(recs, None, vw=True)
        out(f"  {label:>40} | {fmt(pt,se):>30} | {nf:7d} {ne:6d}")
        return pt, se, nf, ne
    bp = stat(base, "BASELINE (no extra filter)")
    out("")
    # filter a: volume thresholds
    for vt in (1000, 2000, 5000):
        stat([r for r in base if r[VOL] >= vt], f"volume_fp >= {vt}")
    out("")
    # filter b: time-to-settle (fraction of life remaining at fill)
    stat([r for r in base if (r[TTF] is not None and r[TTF] >= 0.5)],
         "early life (>=50% life left)")
    stat([r for r in base if (r[TTF] is not None and 0.10 <= r[TTF] < 0.5)],
         "mid life (10-50% left)")
    stat([r for r in base if (r[TTF] is not None and r[TTF] < 0.10)],
         "late life (<10% left, settlement)")
    out("")
    # filter c: single-outcome vs multi-leg event
    stat([r for r in base if legcount.get(r[EV], 1) <= 1], "single-outcome event (1 leg)")
    stat([r for r in base if legcount.get(r[EV], 1) >= 2], "multi-leg event (>=2 legs)")
    stat([r for r in base if legcount.get(r[EV], 1) >= 5], "broad multi-leg (>=5 legs)")
    out("")
    # filter d: fee-type confirmation (include the maker-fee series, see drag)
    mf = [r for r in sell if r[FEE] == "quadratic_with_maker_fees" and 0.05 <= r[P] < 0.20]
    stat(mf, "quadratic_with_maker_fees (EXCLUDED set)")
    out("")

    # ---------------- 4) SUB-POCKET hunt: category x band, with held-out gate --------
    out("---- (4) SUB-POCKET HUNT | SELL_YES zero-fee | category x band ----")
    out("    (multiple-testing: many cells; we BH-correct and gate winners on a "
        "TIME held-out split + cross-band consistency)")
    sub_bands = [(0.02, 0.07), (0.05, 0.10), (0.07, 0.12), (0.10, 0.15),
                 (0.12, 0.17), (0.15, 0.20)]
    cells = []
    for cat in cats:
        for lo, hi in sub_bands:
            recs = [netrec(r) for r in zerofee if r[CAT] == cat and lo <= r[P] < hi]
            pt, se, nf, ne, ct = clustered_stats(recs, None, vw=True)
            if ne >= 8 and ct >= 5000:        # require minimum event-n and size
                z = pt / se if (se == se and se > 0) else float("nan")
                cells.append((cat, lo, hi, pt, se, z, nf, ne, ct))
    # rank by point
    cells.sort(key=lambda x: -x[3])
    out(f"{'cell':>34} | {'VW net (clustered)':>26} | {'n_evt':>6} {'contracts':>11}")
    # BH multiple-testing: collect two-sided p from z
    def pval(z):
        if z != z:
            return float("nan")
        # two-sided normal
        return math.erfc(abs(z) / math.sqrt(2.0))
    m = len(cells)
    pvals = sorted((pval(c[5]), i) for i, c in enumerate(cells) if c[5] == c[5])
    bh_pass = set()
    alpha = 0.10
    for rank, (p_, i) in enumerate(pvals, start=1):
        if p_ <= alpha * rank / max(len(pvals), 1):
            bh_pass.add(i)
    for i, c in enumerate(cells):
        cat, lo, hi, pt, se, z, nf, ne, ct = c
        tag = " *BH" if i in bh_pass else ""
        out(f"  {cat[:18]+f'[{lo:.2f},{hi:.2f})':>16} | {fmt(pt,se):>26} | "
            f"{ne:6d} {ct:11.0f}{tag}")
    out(f"  ({m} cells tested; BH FDR<= {alpha:.0%}; '*BH' survives multiple testing)")
    out("")

    # ---------------- held-out TIME split robustness on top cells -------------------
    out("---- HELD-OUT robustness on the top cells (split each event's fills by TIME) ----")
    out("    For the strongest cells, split fills into early-half vs late-half of the")
    out("    sample period (by created order proxy = list order within collection).")
    out("    A real edge holds in BOTH halves with the same sign.")
    # use a stable per-fill order index; split by global fill index parity is biased,
    # so we split by market ticker hash into two folds (independent markets).
    def fold_of(rec):
        return hash(rec[TK]) % 2
    for c in cells[:6]:
        cat, lo, hi, pt, se, z, nf, ne, ct = c
        pool = [r for r in zerofee if r[CAT] == cat and lo <= r[P] < hi]
        f0 = [netrec(r) for r in pool if fold_of(r) == 0]
        f1 = [netrec(r) for r in pool if fold_of(r) == 1]
        p0, s0, _, e0, _ = clustered_stats(f0, None, vw=True)
        p1, s1, _, e1, _ = clustered_stats(f1, None, vw=True)
        same = (p0 == p0 and p1 == p1 and (p0 > 0) == (p1 > 0))
        out(f"  {cat[:16]} [{lo:.2f},{hi:.2f}): "
            f"foldA {fmt(p0,s0)} (e{e0}) | foldB {fmt(p1,s1)} (e{e1}) | "
            f"{'CONSISTENT' if same else 'FLIPS'}")
    out("")

    # ---------------- the OPTIMAL rule: pooled core band + overall baseline ----------
    out("---- OPTIMAL RULE candidate vs BASELINE ----")
    # baseline = the validated p<0.20 SELL_YES zero-fee (all soft) number
    base_full = [netrec(r) for r in zerofee if r[P] < 0.20]
    pb, sb, nfb, neb, ctb = clustered_stats(base_full, None, vw=True)
    out(f"  BASELINE  p<0.20 all-soft zero-fee SELL_YES : "
        f"{fmt(pb,sb)}  n_evt={neb} contracts={ctb:.0f}")
    # optimal candidate: core band 0.05-0.20 (drop efficient deep tail <0.05)
    opt = [netrec(r) for r in zerofee if 0.05 <= r[P] < 0.20]
    po, so, nfo, neo, cto = clustered_stats(opt, None, vw=True)
    out(f"  OPT cand  p in[0.05,0.20) zero-fee SELL_YES : "
        f"{fmt(po,so)}  n_evt={neo} contracts={cto:.0f}")
    out(f"  lift vs baseline: {po-pb:+.4f} $/contract")
    out("")

    # machine-readable
    res = {
        "meta": meta,
        "band_sweep": {f"{lo:.2f}-{hi:.2f}": band_pts[(lo, hi)] for lo, hi in bands},
        "category_core": cat_core,
        "baseline_p020": [pb, sb, nfb, neb, ctb],
        "optimal_core": [po, so, nfo, neo, cto],
        "cells": cells,
    }
    with open("longshot_opt_results.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
    with open("longshot_opt_report.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    return res


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("collect", "all"):
        if mode == "all" and os.path.exists(CACHE):
            sys.stderr.write(f"[cache exists: {CACHE}; skipping collect. "
                             f"Delete to force re-collect.]\n")
        else:
            collect()
    if mode in ("analyze", "all"):
        analyze()
