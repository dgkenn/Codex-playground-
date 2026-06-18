#!/usr/bin/env python3
"""
kalshi_maker_rank.py
====================
Rank Kalshi SOFT (non-crypto) categories by favorite-longshot MISCALIBRATION to
find the most promising MAKER (favorite-longshot harvest) corners.

Public API only (no auth):  https://api.elections.kalshi.com/trade-api/v2

Method
------
For each category in the soft set:
  1. GET /series?category=<cat>           -> series list (+ fee_type, fee_multiplier)
  2. For a sample of series:
       GET /markets?series_ticker=<s>&status=settled   -> settled binary markets
       keep binary, non-MVE, volume_fp >= MIN_VOLUME, result in {yes,no}
  3. For each kept market, GET candlesticks (period_interval=60) over [open,close],
     take the MID-LIFE hour candle and compute:
         mid   = (yes_bid.close + yes_ask.close)/2     (the "fair" probability proxy)
         spread= yes_ask.close - yes_bid.close
     realized YES outcome = 1 if result=='yes' else 0
  4. Bin by mid price.  For each bin:  bias = realized_WR - mean(mid)
     Favorite-longshot pattern => longshot bins (low mid) have bias<0 (overpriced;
     buy NO maker edge), favorite bins (high mid) have bias>0 (underpriced; buy YES).
  5. Rank categories by volume-weighted |bias| and report spread + volume.

Notes / honesty
---------------
* The API does NOT expose a maker fee field. fee_multiplier is the TAKER multiplier
  relative to the base 0.07 quadratic.  Maker fee policy comes from the published
  Kalshi fee schedule (see KALSHI_MAKER_RANK.md citations), not the API.
* mid-life price is a coarse "fair" proxy; with only one candle per market and
  thin volume it is noisy.  Bias estimates carry wide CIs; treat as directional.
"""
import urllib.request, urllib.error, json, time, math, datetime, sys, argparse
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SOFT_CATEGORIES = ["Economics", "Politics", "Climate and Weather", "Entertainment",
                   "Science and Technology", "World", "Companies", "Sports"]
MIN_VOLUME = 300.0
# price bins (mid):  longshot ... favorite
BIN_EDGES = [0.0, 0.05, 0.10, 0.15, 0.25, 0.40, 0.60, 0.75, 0.85, 0.90, 0.95, 1.0]


def get(path, retries=4):
    url = BASE + path
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'kalshi-maker-rank/1.0'})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < retries - 1:
                time.sleep(1.5 * (2 ** i)); continue
            return None
        except Exception:
            if i < retries - 1:
                time.sleep(1.0 * (2 ** i)); continue
            return None
    return None


def ts(iso):
    return int(datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp())


def bin_of(p):
    for i in range(len(BIN_EDGES) - 1):
        if BIN_EDGES[i] <= p < BIN_EDGES[i + 1]:
            return i
    return len(BIN_EDGES) - 2


def midlife_quote(series_ticker, mkt):
    """Return (mid, spread) at the mid-life hour, or None."""
    try:
        st, en = ts(mkt['open_time']), ts(mkt['close_time'])
    except Exception:
        return None
    if en <= st:
        return None
    cs = get(f"/series/{series_ticker}/markets/{mkt['ticker']}/candlesticks"
             f"?period_interval=60&start_ts={st}&end_ts={en}")
    if not cs:
        return None
    cands = cs.get('candlesticks', [])
    # keep candles that have a real two-sided quote
    quotes = []
    for c in cands:
        try:
            ya = float(c['yes_ask']['close_dollars'])
            yb = float(c['yes_bid']['close_dollars'])
        except Exception:
            continue
        if ya <= 0 and yb <= 0:
            continue
        if ya >= 1.0 and yb <= 0:
            continue
        quotes.append((yb, ya))
    if not quotes:
        return None
    yb, ya = quotes[len(quotes) // 2]      # mid-life
    if ya < yb:
        ya, yb = yb, ya
    mid = (yb + ya) / 2.0
    spread = ya - yb
    if mid <= 0 or mid >= 1:
        return None
    return mid, spread


def collect_category(cat, max_series, max_markets_per_series, verbose=True):
    sd = get(f"/series?category={urllib.parse.quote(cat)}")
    if not sd:
        return None
    series = sd.get('series', [])
    fee_types = {s.get('fee_type') for s in series}
    fee_mults = {s.get('fee_multiplier') for s in series}
    rows = []          # (mid, spread, y, volume)
    n_series_used = 0
    for s in series[:max_series]:
        st = s['ticker']
        md = get(f"/markets?series_ticker={st}&status=settled&limit=100")
        if not md:
            continue
        mkts = md.get('markets', [])
        good = [m for m in mkts
                if m.get('market_type') == 'binary'
                and not (m.get('mve_collection_ticker') or '').startswith('KXMVE')
                and float(m.get('volume_fp', 0) or 0) >= MIN_VOLUME
                and m.get('result') in ('yes', 'no')]
        if not good:
            continue
        used_here = 0
        for m in good[:max_markets_per_series]:
            q = midlife_quote(st, m)
            if q is None:
                continue
            mid, spread = q
            y = 1.0 if m['result'] == 'yes' else 0.0
            vol = float(m.get('volume_fp', 0) or 0)
            rows.append((mid, spread, y, vol))
            used_here += 1
        if used_here:
            n_series_used += 1
        if verbose:
            sys.stderr.write(f"  [{cat}] {st}: {len(good)} good, {used_here} priced "
                             f"(total rows={len(rows)})\n")
    return {"category": cat, "n_series": len(series), "n_series_used": n_series_used,
            "fee_types": sorted(map(str, fee_types)),
            "fee_multipliers": sorted(map(str, fee_mults)), "rows": rows}


def summarize(res):
    rows = res['rows']
    n = len(rows)
    if n == 0:
        return {**res, "n_markets": 0}
    # overall volume-weighted |bias| by bin
    bins = defaultdict(list)
    for mid, spread, y, vol in rows:
        bins[bin_of(mid)].append((mid, spread, y, vol))
    bin_stats = []
    wsum = 0.0; wbias = 0.0
    for bi in sorted(bins):
        b = bins[bi]
        cnt = len(b)
        mmid = sum(x[0] for x in b) / cnt
        mspread = sum(x[1] for x in b) / cnt
        wr = sum(x[2] for x in b) / cnt
        tvol = sum(x[3] for x in b)
        bias = wr - mmid          # realized - priced
        # binomial SE on WR
        se = math.sqrt(max(wr * (1 - wr), 1e-9) / cnt)
        bin_stats.append({"bin": f"{BIN_EDGES[bi]:.2f}-{BIN_EDGES[bi+1]:.2f}",
                          "n": cnt, "mean_mid": round(mmid, 4),
                          "realized_wr": round(wr, 4), "bias_pp": round(bias * 100, 1),
                          "se_pp": round(se * 100, 1),
                          "avg_spread_pp": round(mspread * 100, 1),
                          "tot_vol": round(tvol)})
        wsum += cnt
        wbias += cnt * abs(bias)
    cat_abs_bias = (wbias / wsum) if wsum else 0.0
    return {**res, "n_markets": n, "cat_weighted_abs_bias_pp": round(cat_abs_bias * 100, 2),
            "bins": bin_stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-series", type=int, default=60)
    ap.add_argument("--max-markets", type=int, default=8)
    ap.add_argument("--categories", nargs="*", default=SOFT_CATEGORIES)
    ap.add_argument("--out", default="/tmp/rank/maker_rank_results.json")
    args = ap.parse_args()

    all_summ = []
    for cat in args.categories:
        sys.stderr.write(f"=== {cat} ===\n")
        res = collect_category(cat, args.max_series, args.max_markets)
        if res is None:
            sys.stderr.write(f"  FAILED {cat}\n"); continue
        summ = summarize(res)
        summ.pop('rows', None)
        all_summ.append(summ)
        sys.stderr.write(f"  -> n_markets={summ['n_markets']} "
                         f"abs_bias={summ.get('cat_weighted_abs_bias_pp')}pp\n")

    all_summ.sort(key=lambda x: x.get('cat_weighted_abs_bias_pp', 0), reverse=True)
    with open(args.out, "w") as f:
        json.dump(all_summ, f, indent=2)
    print(json.dumps(all_summ, indent=2))


if __name__ == "__main__":
    import urllib.parse
    main()
