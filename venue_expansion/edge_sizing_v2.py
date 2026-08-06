"""edge_sizing_v2.py -- Stage 1 of EDGE_SIZING_SPEC.md, with the sampling defect fixed.

WHY V2. The first pass drew a seeded random sample but then re-sorted the chosen indices back into
population order (`sorted(idx[:n])`). Population order is grouped by series, so an interrupted run
yielded a SERIES-ORDERED PREFIX, not a random subsample: 748 markets covering 13 of 40 series and
ZERO KXLOW* markets -- the very family holding the one ground-truth instance this study exists to
size. Direction of bias unknown, which is worse than a known direction.

THE FIX, two parts:
  1. STRATIFIED by series (equal draw per series, capped at series size) so no family can be absent,
     with population re-weighting when the rate is aggregated.
  2. SHUFFLED work order (fixed seed) and NEVER re-sorted, so ANY PREFIX of the run is itself a
     representative sample. An interruption now degrades precision, not validity.

Also fixes the denominator: months are derived from the OBSERVED close-date span of the population,
not the nominal frozen window (the catalog has no settled weather market before 2026-05-23, so the
frozen 3.15-month window over-divided by ~30%).

Definitions are frozen in EDGE_SIZING_SPEC.md and reproduced exactly:
  winner cost = yes_ask            if the market settled YES
              = 100 - yes_bid      if it settled NO      <-- NOT 100 - yes_ask (that is the NO bid)
  capturable minute iff cost <= 98 AND net > 0, net = 100 - cost - ceil(7*p*(1-p)), p = cost/100

Read-only against public endpoints; caches every candlestick pull. Resumable.
Usage: python venue_expansion/edge_sizing_v2.py [--per-series N] [--max-fetch M]
"""
from __future__ import annotations

import collections
import json
import math
import os
import random
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "edge_sizing")
CANDLES = os.path.join(CACHE, "candles")
POP = os.path.join(CACHE, "population.json")
OUT_JSONL = os.path.join(CACHE, "stage1_v2.jsonl")
OUT_JSON = os.path.join(HERE, "out", "edge_sizing_v2.json")
API = "https://api.elections.kalshi.com/trade-api/v2"
SEED = 20260806
WINDOW_MIN = 60          # final 60 minutes before close, per the frozen spec
MAX_PAY_C = 98           # deployed MAX_PAY gate


def fee_c(cost_c: float) -> int:
    p = cost_c / 100.0
    return math.ceil(7 * p * (1 - p))


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kwx-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as fh:
                return json.load(fh)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def candles_for(m):
    """1-minute candles over the final WINDOW_MIN before close. Cached per ticker."""
    tk = m["ticker"]
    path = os.path.join(CANDLES, tk + ".json")
    if os.path.exists(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception:
            pass
    import datetime as dt
    close = dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
    end = int(close.timestamp())
    url = (f"{API}/series/{m['series_ticker']}/markets/{tk}/candlesticks"
           f"?start_ts={end - WINDOW_MIN * 60}&end_ts={end}&period_interval=1")
    try:
        data = get(url).get("candlesticks", [])
    except Exception:
        data = None
    os.makedirs(CANDLES, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh)
    time.sleep(0.25)
    return data


def _cents(node, field):
    """Candlestick bid/ask nodes carry *_dollars; return integer cents or None."""
    if not node:
        return None
    v = node.get(field)
    if v is None:
        return None
    try:
        return int(round(float(v) * 100))
    except Exception:
        return None


def normalize(cs, close_ts):
    """Return [(ts, yes_bid_c, yes_ask_c, vol)] for the final WINDOW_MIN, from EITHER cache format.

    The v1 pass cached a pre-normalized {"rows":[{ts,yes_bid_c,yes_ask_c,vol}]} over the market's
    whole life; this pass fetches raw Kalshi candlesticks for the final window only. Accept both so
    the ~764 markets v1 already paid for are reused rather than re-fetched.
    """
    out = []
    if isinstance(cs, dict) and "rows" in cs:
        for r in cs["rows"]:
            ts = r.get("ts")
            if ts is None or ts < close_ts - WINDOW_MIN * 60 or ts > close_ts:
                continue
            yb, ya = r.get("yes_bid_c"), r.get("yes_ask_c")
            out.append((ts,
                        None if yb is None else int(round(float(yb))),
                        None if ya is None else int(round(float(ya))),
                        float(r.get("vol") or 0)))
    elif isinstance(cs, list):
        for k in cs:
            if not isinstance(k, dict):
                continue
            ts = k.get("end_period_ts")
            if ts is not None and (ts < close_ts - WINDOW_MIN * 60 or ts > close_ts):
                continue
            vol = k.get("volume_fp") or k.get("volume") or 0
            try:
                vol = float(vol)
            except Exception:
                vol = 0.0
            out.append((ts, _cents(k.get("yes_bid"), "close_dollars"),
                        _cents(k.get("yes_ask"), "close_dollars"), vol))
    return out


def scan(m):
    """Per-market capturable summary over the final window. Outcome from the official result only."""
    result = m.get("result")
    if result not in ("yes", "no"):
        return {"ticker": m["ticker"], "skip": "no_official_result"}
    cs = candles_for(m)
    if cs is None:
        return {"ticker": m["ticker"], "skip": "candles_fetch_failed"}
    import datetime as dt
    close_ts = int(dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp())
    rows = normalize(cs, close_ts)
    if not rows:
        return {"ticker": m["ticker"], "skip": "no_candles"}

    best_cost, best_net, n_cap, cap_vol, n_min = None, None, 0, 0.0, 0
    for _ts, yb, ya, vol in rows:
        cost = ya if result == "yes" else (None if yb is None else 100 - yb)
        if cost is None:
            continue
        n_min += 1
        if not (0 < cost <= MAX_PAY_C):
            continue
        net = 100 - cost - fee_c(cost)
        if net <= 0:
            continue
        n_cap += 1
        cap_vol += vol
        if best_cost is None or cost < best_cost:
            best_cost, best_net = cost, net
    return {"ticker": m["ticker"], "series": m["series_ticker"], "result": result,
            "close_time": m["close_time"], "n_data_minutes": n_min,
            "capturable": n_cap > 0, "n_capturable_minutes": n_cap,
            "best_winner_cost_c": best_cost, "best_net_c": best_net,
            "capturable_volume": cap_vol}


def main():
    per_series = 45
    max_fetch = 10 ** 9
    for i, a in enumerate(sys.argv):
        if a == "--per-series":
            per_series = int(sys.argv[i + 1])
        if a == "--max-fetch":
            max_fetch = int(sys.argv[i + 1])

    pop = json.load(open(POP))
    pop = pop if isinstance(pop, list) else pop.get("markets", pop)
    by_series = collections.defaultdict(list)
    for m in pop:
        by_series[m["series_ticker"]].append(m)
    print(f"population {len(pop):,} markets across {len(by_series)} series")

    rng = random.Random(SEED)
    work = []
    for s in sorted(by_series):
        ms = by_series[s][:]
        rng.shuffle(ms)
        work.extend(ms[:per_series])
    # *** THE FIX: shuffle the combined work list and NEVER re-sort. Any prefix is representative. ***
    rng.shuffle(work)
    print(f"stratified sample: {len(work):,} markets ({per_series}/series, shuffled work order)")

    done = {}
    if os.path.exists(OUT_JSONL):
        for l in open(OUT_JSONL):
            try:
                r = json.loads(l)
                done[r["ticker"]] = r
            except Exception:
                pass
    print(f"resuming: {len(done):,} already scanned")

    fetched = 0
    with open(OUT_JSONL, "a") as fh:
        for i, m in enumerate(work, 1):
            if m["ticker"] in done:
                continue
            if fetched >= max_fetch:
                break
            r = scan(m)
            done[m["ticker"]] = r
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            fetched += 1
            if fetched % 100 == 0:
                cap = sum(1 for x in done.values() if x.get("capturable"))
                print(f"  {fetched} fetched ({len(done)} total), capturable so far: {cap}", flush=True)

    rows = [r for r in done.values() if r["ticker"] in {m["ticker"] for m in work}]
    ok = [r for r in rows if "skip" not in r]
    skips = collections.Counter(r["skip"] for r in rows if "skip" in r)
    cap = [r for r in ok if r.get("capturable")]

    # population-weighted capturable rate (stratified -> weight each series by its population share)
    per_s = collections.defaultdict(lambda: [0, 0])
    for r in ok:
        per_s[r["series"]][0] += 1
        if r.get("capturable"):
            per_s[r["series"]][1] += 1
    weighted, tot_w = 0.0, 0
    for s, ms in by_series.items():
        n, c = per_s.get(s, [0, 0])
        if n:
            weighted += (c / n) * len(ms)
            tot_w += len(ms)
    rate_w = weighted / tot_w if tot_w else None

    import datetime as dt
    cds = [dt.datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")) for m in pop]
    months = max((max(cds) - min(cds)).days, 1) / 30.44

    nets = [r["best_net_c"] for r in cap if r.get("best_net_c")]
    vols = [r["capturable_volume"] for r in cap]
    res = {
        "spec": "venue_expansion/EDGE_SIZING_SPEC.md (frozen)",
        "sampling": {"method": "stratified by series, shuffled work order, never re-sorted",
                     "per_series": per_series, "seed": SEED,
                     "series_in_population": len(by_series),
                     "series_covered": len({r["series"] for r in ok}),
                     "planned": len(work), "scanned": len(rows), "usable": len(ok),
                     "complete": len(rows) >= len(work)},
        "coverage": {"skips": dict(skips),
                     "coverage_pct": round(100 * len(ok) / max(len(rows), 1), 2)},
        "window": {"observed_close_min": str(min(cds).date()), "observed_close_max": str(max(cds).date()),
                   "months_observed": round(months, 3),
                   "note": "months derived from OBSERVED close span, not the nominal frozen window"},
        "stage1": {
            "capturable_markets": len(cap), "usable_markets": len(ok),
            "capturable_rate_sample": round(len(cap) / len(ok), 5) if ok else None,
            "capturable_rate_population_weighted": round(rate_w, 5) if rate_w is not None else None,
            "best_net_c_mean": round(sum(nets) / len(nets), 2) if nets else None,
            "best_net_c_median": round(sorted(nets)[len(nets) // 2], 2) if nets else None,
            "capturable_volume_mean": round(sum(vols) / len(vols), 1) if vols else None,
            "capturable_volume_median": round(sorted(vols)[len(vols) // 2], 1) if vols else None,
        },
        "oracle_framing": ("CEILING, NOT ACHIEVABLE. Assumes perfect foreknowledge of the winner, "
                           "zero detection latency, zero competition, and that 100% of printed volume "
                           "was available to one taker. No strategy can beat it and none can reach it. "
                           "Stage 2 (lock-rule replay) exists to falsify it."),
        "depth_caveat": ("Candlesticks carry NO order-book depth. Volume traded during capturable "
                         "minutes is an UPPER BOUND on what one participant could have taken."),
        "capturable_markets_detail": sorted(cap, key=lambda r: r.get("best_net_c") or 0, reverse=True)[:40],
    }
    if cap and rate_w is not None:
        pop_cap = rate_w * len(pop)
        for est, tag in ((res["stage1"]["capturable_volume_mean"], "mean"),
                         (res["stage1"]["capturable_volume_median"], "median")):
            net = res["stage1"]["best_net_c_" + tag] or 0
            res.setdefault("oracle_capacity_usd_per_month", {})[tag + "_estimator"] = round(
                pop_cap * (est or 0) * net / 100.0 / months, 2)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(res, open(OUT_JSON, "w"), indent=1)
    print("\n" + json.dumps({k: v for k, v in res.items() if k != "capturable_markets_detail"}, indent=1))
    print(f"\nwrote {OUT_JSON}")


if __name__ == "__main__":
    main()
