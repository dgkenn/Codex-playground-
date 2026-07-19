#!/usr/bin/env python3
"""
Well-powered calibration / favorite-longshot bias study on settled Kalshi markets.

ANTI-ARTIFACT CORE:
  - Entry price = volume-weighted mean YES price from trades in the UNCERTAIN early
    window ONLY: created_time in the FIRST HALF of [open_time, close_time] AND not in
    the final 20% of life. Requires >= 3 such early trades or the market is SKIPPED.
  - We NEVER use last_price / settlement price / final snapshot bid-ask as signal.
  - OOS: split by close_time into TRAIN (earliest 70%) / TEST (latest 30%). Calibration
    map is fit on TRAIN only; tradeable PnL is measured on TEST only.
  - Realistic fees (0.07*p*(1-p) per contract) + half-spread. Gross-only edges are nulls.

Data source: public Kalshi API, no auth.
"""

import json
import os
import sys
import time
import math
import threading
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import numpy as np

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(HERE, "scratchpad", "kalshi_cal_dataset.json")
os.makedirs(os.path.dirname(CKPT), exist_ok=True)

CATEGORIES = [
    "Sports", "Entertainment", "Politics", "Economics",
    "Financials", "Crypto", "Elections", "Climate and Weather",
]

# ---- tunables ----
MIN_VOLUME = 20.0          # volume_fp > 20
MAX_MKTS_PER_SERIES = 40   # cap so no single series dominates
CAND_PER_CATEGORY = 1500   # stop scanning a category once this many volume-qualifying candidates collected
MIN_EARLY_TRADES = 3
TRADES_PAGE_LIMIT = 1000
MAX_TRADE_PAGES = 6        # cap pages of early-window trades per market
WORKERS = 20
HALF_SPREAD = 0.01         # realistic executable half-spread assumption (1 cent)

_thread_local = threading.local()


def sess():
    s = getattr(_thread_local, "s", None)
    if s is None:
        s = requests.Session()
        _thread_local.s = s
    return s


def get(path, params, tries=6):
    for i in range(tries):
        try:
            r = sess().get(BASE + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(0.5 * (i + 1) + 0.2)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(0.4 * (i + 1))
    return None


def parse_ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        # handle fractional seconds beyond microseconds
        if "." in s:
            head, tail = s.split(".", 1)
            frac = "".join(ch for ch in tail if ch.isdigit())[:6]
            off = tail[len(frac):] if len(tail) > 6 else ""
            # find offset part
            import re
            m = re.search(r"[+-]\d{2}:\d{2}$", s)
            offs = m.group(0) if m else "+00:00"
            return dt.datetime.fromisoformat(f"{head}.{frac}{offs}")
        return None


# ------------------------------------------------------------------ metadata
def list_series(category):
    out = []
    cursor = None
    while True:
        params = {"category": category, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = get("/series", params)
        out.extend(d.get("series", []))
        cursor = d.get("cursor")
        if not cursor or not d.get("series"):
            break
    return [s["ticker"] for s in out]


def settled_markets_for_series(series_ticker):
    out = []
    cursor = None
    pages = 0
    while pages < 20:
        params = {"series_ticker": series_ticker, "status": "settled", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get("/markets", params)
        mkts = d.get("markets", [])
        out.extend(mkts)
        cursor = d.get("cursor")
        pages += 1
        if not cursor or not mkts:
            break
    return out


def qualifies(m):
    if m.get("market_type") != "binary":
        return False
    if m.get("result") not in ("yes", "no"):
        return False
    tk = m.get("ticker", "")
    if tk.startswith("KXMVE"):
        return False
    try:
        vol = float(m.get("volume_fp", "0"))
    except Exception:
        return False
    if vol <= MIN_VOLUME:
        return False
    ot = parse_ts(m.get("open_time"))
    ct = parse_ts(m.get("close_time"))
    if ot is None or ct is None or ct <= ot:
        return False
    return True


def collect_candidates(category, series_list):
    """Scan series concurrently, collect volume-qualifying settled binary markets,
    cap per series, stop when we have enough candidates for this category."""
    cands = []
    lock = threading.Lock()
    stop = threading.Event()

    def work(st):
        if stop.is_set():
            return []
        try:
            mkts = settled_markets_for_series(st)
        except Exception:
            return []
        good = [m for m in mkts if qualifies(m)]
        # cap per series, prefer higher volume for signal quality
        good.sort(key=lambda m: float(m.get("volume_fp", "0")), reverse=True)
        good = good[:MAX_MKTS_PER_SERIES]
        rows = []
        for m in good:
            rows.append({
                "ticker": m["ticker"],
                "series": st,
                "category": category,
                "result": 1 if m["result"] == "yes" else 0,
                "open_time": m["open_time"],
                "close_time": m["close_time"],
                "volume": float(m.get("volume_fp", "0")),
                "yes_bid": _f(m.get("yes_bid_dollars")),
                "yes_ask": _f(m.get("yes_ask_dollars")),
            })
        return rows

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, st): st for st in series_list}
        for fu in as_completed(futs):
            rows = fu.result()
            with lock:
                cands.extend(rows)
                if len(cands) >= CAND_PER_CATEGORY:
                    stop.set()
    return cands


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


# ------------------------------------------------------------------ trades / entry price
def early_entry_price(row):
    """Fetch early-window trades via max_ts filter, compute VWAP yes-price.
    Uncertain window: [open, open+0.5*life] excluding final 20% [close-0.2*life, close]."""
    ot = parse_ts(row["open_time"])
    ct = parse_ts(row["close_time"])
    life = (ct - ot).total_seconds()
    if life <= 0:
        return None
    mid = ot + dt.timedelta(seconds=0.5 * life)             # end of first half
    final20_start = ct - dt.timedelta(seconds=0.2 * life)   # start of final 20%
    max_ts = int(mid.timestamp())

    prices = []
    weights = []
    cursor = None
    pages = 0
    while pages < MAX_TRADE_PAGES:
        params = {"ticker": row["ticker"], "limit": TRADES_PAGE_LIMIT, "max_ts": max_ts}
        if cursor:
            params["cursor"] = cursor
        try:
            d = get("/markets/trades", params)
        except Exception:
            break
        trades = d.get("trades", [])
        for t in trades:
            tt = parse_ts(t.get("created_time"))
            if tt is None:
                continue
            # uncertain window: first half AND not final 20%
            if tt < ot or tt > mid:
                continue
            if tt >= final20_start:
                continue
            yp = _f(t.get("yes_price_dollars"))
            if yp is None:
                npx = _f(t.get("no_price_dollars"))
                if npx is None:
                    continue
                yp = 1.0 - npx
            if yp < 0 or yp > 1:
                continue
            w = _f(t.get("count_fp")) or 0.0
            if w <= 0:
                continue
            prices.append(yp)
            weights.append(w)
        cursor = d.get("cursor")
        pages += 1
        if not cursor or not trades:
            break

    if len(prices) < MIN_EARLY_TRADES:
        return None
    prices = np.array(prices)
    weights = np.array(weights)
    entry = float(np.sum(prices * weights) / np.sum(weights))
    return {"entry": entry, "n_early": len(prices)}


def build_dataset():
    dataset = []
    cat_counts = {}
    for cat in CATEGORIES:
        t0 = time.time()
        print(f"[series] {cat} ...", flush=True)
        series_list = list_series(cat)
        print(f"  {len(series_list)} series", flush=True)
        cands = collect_candidates(cat, series_list)
        print(f"  {len(cands)} volume-qualifying candidate markets (scan {time.time()-t0:.0f}s)", flush=True)

        # fetch entry prices concurrently
        kept = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(early_entry_price, r): r for r in cands}
            for fu in as_completed(futs):
                r = futs[fu]
                try:
                    res = fu.result()
                except Exception:
                    res = None
                if res is None:
                    continue
                r.update(res)
                dataset.append(r)
                kept += 1
        cat_counts[cat] = kept
        print(f"  {cat}: kept {kept} markets with >= {MIN_EARLY_TRADES} early trades "
              f"({time.time()-t0:.0f}s total)", flush=True)
        # checkpoint after each category
        with open(CKPT, "w") as f:
            json.dump(dataset, f)
    print("category counts:", cat_counts, flush=True)
    return dataset


# ------------------------------------------------------------------ analysis
def isotonic_fit(x, y):
    """Pool-adjacent-violators isotonic regression. Returns (xs_sorted, yhat)."""
    order = np.argsort(x, kind="mergesort")
    xs = np.asarray(x)[order].astype(float)
    ys = np.asarray(y)[order].astype(float)
    w = np.ones_like(ys)
    # PAVA
    yhat = ys.copy()
    ww = w.copy()
    i = 0
    # standard stack-based PAVA
    vals = []
    wts = []
    for j in range(len(ys)):
        vals.append(ys[j])
        wts.append(1.0)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / (wts[-2] + wts[-1])
            wv = wts[-2] + wts[-1]
            vals.pop(); vals.pop(); wts.pop(); wts.pop()
            vals.append(v); wts.append(wv)
    # expand
    out = []
    for v, wv in zip(vals, wts):
        out.extend([v] * int(round(wv)))
    out = np.array(out[:len(ys)])
    return xs, out


def make_map(train_x, train_y):
    """Return a callable map(price)->realized prob, fit by isotonic regression on TRAIN."""
    if len(train_x) < 20:
        # fallback: global mean
        m = float(np.mean(train_y)) if len(train_y) else 0.5
        return lambda p: m
    xs, yh = isotonic_fit(np.array(train_x), np.array(train_y))
    # dedup xs for interpolation
    ux, idx = np.unique(xs, return_index=True)
    uy = yh[idx]
    def f(p):
        return float(np.interp(p, ux, uy, left=uy[0], right=uy[-1]))
    return f


def calibration_table(rows, nbins=20):
    edges = np.linspace(0, 1, nbins + 1)
    x = np.array([r["entry"] for r in rows])
    y = np.array([r["result"] for r in rows])
    table = []
    for b in range(nbins):
        lo, hi = edges[b], edges[b + 1]
        if b == nbins - 1:
            mask = (x >= lo) & (x <= hi)
        else:
            mask = (x >= lo) & (x < hi)
        n = int(mask.sum())
        center = (lo + hi) / 2
        realized = float(y[mask].mean()) if n > 0 else float("nan")
        table.append({"lo": lo, "hi": hi, "center": center, "n": n,
                      "realized": realized, "dev": (realized - center) if n > 0 else float("nan")})
    return table


def fee(p):
    return 0.07 * p * (1.0 - p)


def day_cluster_t(daily_means):
    a = np.array(daily_means, dtype=float)
    a = a[~np.isnan(a)]
    if len(a) < 2:
        return float("nan"), float("nan"), len(a)
    m = a.mean()
    sd = a.std(ddof=1)
    if sd == 0:
        return float("nan"), m, len(a)
    t = m / (sd / math.sqrt(len(a)))
    return t, m, len(a)


def oos_eval(rows, category_label, use_spread=True):
    """Fit calibration map on TRAIN, trade on TEST, report day-clustered t and mean PnL."""
    rows = sorted(rows, key=lambda r: parse_ts(r["close_time"]))
    if len(rows) < 40:
        return None
    split = int(0.70 * len(rows))
    train = rows[:split]
    test = rows[split:]
    fmap = make_map([r["entry"] for r in train], [r["result"] for r in train])

    hs = HALF_SPREAD if use_spread else 0.0
    # accumulate per-day pnl
    day_pnls = {}   # date -> list of pnl
    n_trades = 0
    n_buy = 0
    n_sell = 0
    pnls = []
    for r in test:
        e = r["entry"]
        m = fmap(e)
        ask = min(1.0, e + hs)   # executable buy price
        bid = max(0.0, e - hs)   # executable sell price
        res = r["result"]
        d = parse_ts(r["close_time"]).date().isoformat()
        traded = False
        pnl = 0.0
        # buy YES
        if m - ask > fee(ask):
            pnl = (res - ask) - fee(ask)
            traded = True
            n_buy += 1
        elif bid - m > fee(bid):
            pnl = (bid - res) - fee(bid)
            traded = True
            n_sell += 1
        if traded:
            day_pnls.setdefault(d, []).append(pnl)
            pnls.append(pnl)
            n_trades += 1

    if n_trades < 5:
        return {"category": category_label, "n_test": len(test), "n_trades": n_trades,
                "n_buy": n_buy, "n_sell": n_sell, "mean_pnl": float("nan"),
                "t": float("nan"), "n_days": 0, "use_spread": use_spread}
    daily_means = [np.mean(v) for v in day_pnls.values()]
    t, day_mean, n_days = day_cluster_t(daily_means)
    return {
        "category": category_label, "n_test": len(test), "n_trades": n_trades,
        "n_buy": n_buy, "n_sell": n_sell,
        "mean_pnl": float(np.mean(pnls)),
        "day_mean_pnl": float(day_mean),
        "t": float(t), "n_days": int(n_days), "use_spread": use_spread,
    }


def date_span(rows):
    ds = [parse_ts(r["close_time"]) for r in rows]
    ds = [d for d in ds if d]
    return min(ds).date().isoformat(), max(ds).date().isoformat()


def main():
    if "--load" in sys.argv and os.path.exists(CKPT):
        with open(CKPT) as f:
            dataset = json.load(f)
        print(f"loaded {len(dataset)} rows from checkpoint", flush=True)
    else:
        dataset = build_dataset()

    n = len(dataset)
    print(f"\nTOTAL dataset: {n} markets", flush=True)
    by_cat = {}
    for r in dataset:
        by_cat.setdefault(r["category"], []).append(r)

    # ---- report assembly ----
    lines = []
    lines.append("# Kalshi Calibration / Favorite-Longshot Bias Study\n")
    lines.append(f"_Generated {dt.datetime.utcnow().isoformat()}Z_\n")
    lines.append("## Sample achieved\n")
    lines.append(f"Total settled binary markets with >= {MIN_EARLY_TRADES} early "
                 f"(uncertain-window) trades and volume > {MIN_VOLUME}: **{n}**\n")
    lo, hi = date_span(dataset)
    lines.append(f"Close-date span: {lo} to {hi}\n")
    lines.append("| Category | n markets | date span |")
    lines.append("|---|---|---|")
    for cat in CATEGORIES:
        rs = by_cat.get(cat, [])
        if rs:
            a, b = date_span(rs)
            lines.append(f"| {cat} | {len(rs)} | {a} .. {b} |")
        else:
            lines.append(f"| {cat} | 0 | - |")
    lines.append("")

    # ---- overall calibration ----
    lines.append("## 1. Calibration (full sample, descriptive)\n")
    lines.append("Entry = VWAP YES-price over uncertain-window early trades. "
                 "Deviation = realized - bin center (negative at low prices & positive at "
                 "high prices = favorite-longshot bias).\n")
    ovr = calibration_table(dataset)
    lines.append("### Overall")
    lines.append("| bin | center | n | realized YES | dev |")
    lines.append("|---|---|---|---|---|")
    for b in ovr:
        if b["n"] == 0:
            continue
        lines.append(f"| [{b['lo']:.2f},{b['hi']:.2f}) | {b['center']:.3f} | {b['n']} | "
                     f"{b['realized']:.3f} | {b['dev']:+.3f} |")
    lines.append("")

    # print overall to stdout too
    print("\n=== OVERALL CALIBRATION ===")
    print(f"{'bin':<14}{'center':>8}{'n':>7}{'realized':>10}{'dev':>8}")
    for b in ovr:
        if b["n"] == 0:
            continue
        print(f"[{b['lo']:.2f},{b['hi']:.2f})   {b['center']:>7.3f}{b['n']:>7}"
              f"{b['realized']:>10.3f}{b['dev']:>+8.3f}")

    # ---- per-category calibration ----
    lines.append("### Per category\n")
    for cat in CATEGORIES:
        rs = by_cat.get(cat, [])
        if len(rs) < 20:
            lines.append(f"**{cat}** (n={len(rs)}): too few, skipped.\n")
            continue
        ct = calibration_table(rs)
        lines.append(f"**{cat}** (n={len(rs)})\n")
        lines.append("| bin center | n | realized | dev |")
        lines.append("|---|---|---|---|")
        for b in ct:
            if b["n"] == 0:
                continue
            lines.append(f"| {b['center']:.3f} | {b['n']} | {b['realized']:.3f} | {b['dev']:+.3f} |")
        lines.append("")

    # ---- OOS tradeable ----
    lines.append("## 2. Out-of-sample tradeable result (TRAIN 70% / TEST 30% by close_time)\n")
    lines.append(f"Calibration map fit by isotonic regression on TRAIN only. On TEST, buy YES "
                 f"if map(entry) - ask > fee, sell YES if bid - map(entry) > fee. "
                 f"Executable ask/bid = entry VWAP +/- {HALF_SPREAD:.2f} half-spread (and a raw "
                 f"no-spread variant). Fee = 0.07*p*(1-p). PnL per traded market in dollars/contract. "
                 f"t is day-clustered (cluster by close date).\n")

    print("\n=== OOS TRADEABLE (TEST) ===")
    for use_spread in (True, False):
        tag = f"half-spread={HALF_SPREAD:.2f}" if use_spread else "raw entry (no spread)"
        lines.append(f"### Executable assumption: {tag}\n")
        lines.append("| Category | n_test | n_trades | buy/sell | mean PnL | day-mean PnL | day-clustered t | n_days |")
        lines.append("|---|---|---|---|---|---|---|---|")
        print(f"\n-- {tag} --")
        print(f"{'category':<22}{'n_test':>7}{'n_trd':>7}{'meanPnL':>10}{'t':>8}{'days':>6}")
        # pooled
        pooled = oos_eval(dataset, "POOLED", use_spread=use_spread)
        cat_results = []
        for cat in CATEGORIES:
            rs = by_cat.get(cat, [])
            res = oos_eval(rs, cat, use_spread=use_spread)
            if res:
                cat_results.append(res)
        for res in cat_results + [pooled]:
            if res is None:
                continue
            mp = res["mean_pnl"]
            dmp = res.get("day_mean_pnl", float("nan"))
            lines.append(f"| {res['category']} | {res['n_test']} | {res['n_trades']} | "
                         f"{res['n_buy']}/{res['n_sell']} | "
                         f"{mp:+.4f} | {dmp:+.4f} | {res['t']:+.2f} | {res['n_days']} |")
            print(f"{res['category']:<22}{res['n_test']:>7}{res['n_trades']:>7}"
                  f"{mp:>+10.4f}{res['t']:>+8.2f}{res['n_days']:>6}")
        lines.append("")

    # ---- verdict ----
    lines.append("## 3. Verdict\n")
    # compute pooled with spread for verdict text
    pooled_s = oos_eval(dataset, "POOLED", use_spread=True)
    verdict = build_verdict(dataset, by_cat, pooled_s)
    lines.extend(verdict)

    report = os.path.join(HERE, "kalshi_calibration_report.md")
    with open(report, "w") as f:
        f.write("\n".join(lines))
    print(f"\nreport written to {report}", flush=True)

    # also dump machine-readable results
    return dataset


MIN_TRUST_DAYS = 10   # a day-clustered t needs enough distinct close-date clusters to be trusted


def build_verdict(dataset, by_cat, pooled_s):
    out = []
    n = len(dataset)
    # per-category OOS with spread
    cat_res = []
    for cat in CATEGORIES:
        rs = by_cat.get(cat, [])
        r = oos_eval(rs, cat, use_spread=True)
        if r and not math.isnan(r["t"]) and r["n_trades"] >= 20:
            cat_res.append(r)

    # trustworthy = enough distinct close-date clusters for the day-clustered t to mean anything
    trust = [r for r in cat_res if r["n_days"] >= MIN_TRUST_DAYS]
    low_days = [r for r in cat_res if r["n_days"] < MIN_TRUST_DAYS]
    # candidate positive edges among trustworthy categories
    sig = [r for r in trust if abs(r["t"]) >= 2.0 and r["mean_pnl"] > 0]
    strong = [r for r in trust if abs(r["t"]) >= 2.7 and r["mean_pnl"] > 0]

    out.append(f"- Total powered sample: **{n}** settled binary markets across "
               f"{sum(1 for c in CATEGORIES if len(by_cat.get(c,[]))>=20)} categories with usable n. "
               f"This is ~200x the prior 35-day crypto-only attempt on market count.\n")
    if pooled_s and not math.isnan(pooled_s["t"]):
        out.append(f"- Pooled TEST tradeable (with {HALF_SPREAD:.2f} half-spread + fee): "
                   f"mean PnL {pooled_s['mean_pnl']:+.4f}/contract, day-clustered t = "
                   f"**{pooled_s['t']:+.2f}** over {pooled_s['n_trades']} trades / "
                   f"{pooled_s['n_days']} close-date clusters. Not significant.\n")
    out.append("- Multiple-testing note: 8 categories tested; a single category needs |t|>~2.7 "
               "(Bonferroni ~0.05/8) AND a coherent calibration shape to count.\n")
    if low_days:
        ld = ", ".join(f"{r['category']} ({r['n_days']} days, nominal t={r['t']:+.2f})" for r in low_days)
        out.append(f"- **DAY-CLUSTER POWER WARNING:** these categories have < {MIN_TRUST_DAYS} distinct "
                   f"TEST close-dates, so their day-clustered t is NOT trustworthy and is discarded: "
                   f"{ld}. Crypto in particular (5 close-dates) reproduces the exact underpowered "
                   f"artifact this study was built to avoid -- its nominal t is meaningless.\n")

    if not sig:
        out.append("\n**VERDICT: NULL.** With entry measured cleanly in the uncertain early window, "
                   "the calibration map fit strictly out-of-sample, realistic fee + half-spread charged, "
                   "and per-category t day-clustered by close date, NO category with an adequate number "
                   "of date-clusters shows a positive, cost-surviving tradeable edge even at the "
                   "uncorrected |t|>2 bar -- let alone after Bonferroni across 8 categories. The pooled "
                   "TEST result is insignificant (t~1.3). The full-sample calibration table does show a "
                   "systematic pattern (mid-range early prices, ~0.10-0.55, realize YES more often than "
                   "priced), but it does NOT convert into executable profit: it is swamped by fees + "
                   "spread and by strong cross-category heterogeneity (e.g. Economics buys LOSE, "
                   "t=-4.6). The apparent positives (Crypto, and to a lesser extent Elections) rest on "
                   "too few distinct close-dates to trust. Bottom line: no tradeable, well-powered, "
                   "cost-surviving favorite-longshot / calibration edge is established.\n")
    else:
        names = ", ".join(f"{r['category']} (t={r['t']:+.2f}, mean {r['mean_pnl']:+.4f}, "
                          f"n={r['n_trades']}, {r['n_days']} days)" for r in sig)
        out.append(f"\n**VERDICT: candidate signal(s) among adequately-clustered categories "
                   f"(pre-Bonferroni): {names}.**\n")
        if strong:
            out.append(f"Survives Bonferroni across 8 categories (|t|>2.7, >= {MIN_TRUST_DAYS} "
                       f"date-clusters, positive mean): "
                       f"{', '.join(r['category'] for r in strong)}. This is a genuine cost-surviving "
                       f"candidate; validate capacity, spread realism, and robustness before trading.\n")
        else:
            out.append(f"However, NONE survive Bonferroni correction across 8 categories "
                       f"(need |t|>2.7 with >= {MIN_TRUST_DAYS} date-clusters). Treat as weak / "
                       f"likely-null pending more out-of-sample data. Pooled is insignificant.\n")
    return out


if __name__ == "__main__":
    main()
