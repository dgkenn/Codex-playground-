#!/usr/bin/env python3
"""
kalshi_maker_advsel.py

DECISIVE KILLER TEST: ADVERSE SELECTION on Kalshi SOFT (non-crypto) maker fills.

Question
--------
A separate test shows a MAKER (resting limit order) appears to have positive EV
"if filled at the bid" on low-volume soft markets, harvesting favorite-longshot
bias (GWU: "makers win, takers lose"). BUT a resting maker only gets filled when a
TAKER chooses to trade against them. If takers are informed, the maker's FILLED
outcomes are systematically worse than the market's unconditional outcomes ->
adverse selection. This script measures the maker's REALIZED P&L (to settlement and
short-horizon markout) on actual fills, NET of the Kalshi quadratic fee, by price band.

Method (markout)
----------------
For each public trade in a SETTLED binary soft market:
  - taker lifts; the MAKER is the passive counterparty.
  - taker_side == "yes": taker BOUGHT yes  -> maker SOLD yes  -> maker SHORT yes.
        maker P&L to settle = fill_price - settle
  - taker_side == "no" : taker SOLD yes    -> maker BOUGHT yes -> maker LONG yes.
        maker P&L to settle = settle - fill_price
  settle = 1.0 if market result == "yes" else 0.0
  fee (per contract) = 0.07 * p * (1-p), p = fill_price   (subtracted from maker P&L)

We weight each fill by its contract count (count_fp) for the volume-weighted mean,
and also report the equal-weight-per-trade mean.

Short-horizon markout (selection signal independent of settlement): using 60s
candles, find the mid price (yes_bid.close + yes_ask.close)/2, or price.close,
~MARKOUT_MIN minutes after the trade. Maker P&L_markout = (mid_future - fill) for a
long maker, (fill - mid_future) for a short maker. If the price moves AGAINST the
maker right after the fill, that is direct evidence of adverse selection / informed
takers, with no settlement dependence.

Bands: longshot (fill price < 0.20), mid [0.20,0.80], favorite (> 0.80).

Comparison: "naive fill-at-bid, ignore selection" EV is computed as the unconditional
settlement value of the position the maker took, i.e. assume the maker's fill price
equals the *market mid* / unconditional fair value. We approximate the naive EV per
band by the band-average of (settle outcome treated symmetrically) -- see code.
"""

import json
import time
import sys
import math
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CATEGORIES = ["Economics", "Politics", "Climate and Weather", "Entertainment"]
MIN_VOLUME_FP = 300.0
MAX_SERIES_PER_CAT = 40         # cap series scanned per category
MAX_MARKETS_PER_SERIES = 60     # cap settled markets per series
MAX_MARKETS_TOTAL = 600         # global cap on markets analyzed
MARKOUT_MIN = 10                # short-horizon markout window (minutes)
FEE_RATE = 0.07                 # Kalshi quadratic fee coefficient
REQUEST_PAUSE = 0.05

def http_get(path, params=None, retries=4):
    url = BASE + path
    if params:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None and v != "")
        url = url + "?" + q
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "advsel-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(0.5 * (2 ** i))
                continue
            # 4xx other -> give up on this call
            return None
        except Exception as e:
            last = e
            time.sleep(0.5 * (2 ** i))
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

# ---------------------------------------------------------------- discovery
def list_series(category):
    out = []
    cursor = ""
    while True:
        d = http_get("/series", {"category": category, "limit": 100, "cursor": cursor})
        if not d:
            break
        s = d.get("series", [])
        out.extend(s)
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= 400:
            break
        time.sleep(REQUEST_PAUSE)
    return out

def list_settled_markets(series_ticker):
    out = []
    cursor = ""
    while True:
        d = http_get("/markets", {"series_ticker": series_ticker, "status": "settled",
                                  "limit": 100, "cursor": cursor})
        if not d:
            break
        ms = d.get("markets", [])
        out.extend(ms)
        cursor = d.get("cursor") or ""
        if not cursor or len(out) >= MAX_MARKETS_PER_SERIES:
            break
        time.sleep(REQUEST_PAUSE)
    return out[:MAX_MARKETS_PER_SERIES]

def get_trades(ticker):
    out = []
    cursor = ""
    for _ in range(20):  # up to 20k trades cap
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

def get_candles(series_ticker, ticker, start_ts, end_ts):
    d = http_get(f"/series/{series_ticker}/markets/{ticker}/candlesticks",
                 {"start_ts": int(start_ts), "end_ts": int(end_ts), "period_interval": 60})
    if not d:
        return []
    return d.get("candlesticks", [])

def candle_mid(c):
    yb = fnum(c.get("yes_bid", {}).get("close_dollars"))
    ya = fnum(c.get("yes_ask", {}).get("close_dollars"))
    if yb is not None and ya is not None and 0 < yb <= 1 and 0 < ya <= 1 and ya >= yb:
        return (yb + ya) / 2.0
    pc = fnum(c.get("price", {}).get("close_dollars"))
    return pc

# ---------------------------------------------------------------- bands
def band_of(p):
    if p < 0.20:
        return "longshot(<0.20)"
    if p > 0.80:
        return "favorite(>0.80)"
    return "mid[0.20,0.80]"

BANDS = ["longshot(<0.20)", "mid[0.20,0.80]", "favorite(>0.80)"]

def fee(p):
    return FEE_RATE * p * (1.0 - p)

class Acc:
    """Volume-weighted and trade-weighted accumulator for a P&L series."""
    def __init__(self):
        self.n = 0            # number of fills (trades)
        self.contracts = 0.0  # sum of count_fp
        self.sum_w = 0.0      # sum_i count_i * pnl_i  (volume-weighted numerator)
        self.sum_t = 0.0      # sum_i pnl_i            (trade-weighted numerator)
        self.sumsq_t = 0.0
    def add(self, pnl, contracts):
        self.n += 1
        self.contracts += contracts
        self.sum_w += contracts * pnl
        self.sum_t += pnl
        self.sumsq_t += pnl * pnl
    def vw_mean(self):
        return self.sum_w / self.contracts if self.contracts > 0 else float("nan")
    def tw_mean(self):
        return self.sum_t / self.n if self.n else float("nan")
    def tw_se(self):
        if self.n < 2:
            return float("nan")
        m = self.tw_mean()
        var = (self.sumsq_t - self.n * m * m) / (self.n - 1)
        return math.sqrt(max(var, 0.0) / self.n)

def main():
    settle_band = defaultdict(Acc)   # maker P&L to settlement, net of fee, by band
    settle_all = Acc()
    markout_band = defaultdict(Acc)  # short-horizon markout (pre-fee, mid-based), by band
    markout_all = Acc()
    # naive "fill-at-bid ignore selection": for each fill, the unconditional value of
    # the maker's directional position priced at fill = E[settle]-fill for long etc.
    # We don't know true fair val per market, so approximate naive EV as the position's
    # P&L if the market were a fair coin at the fill price -> 0 by construction is wrong.
    # Instead: naive baseline = maker P&L to settlement assuming the OTHER side's flow
    # (counterfactual): we report maker realized minus a "no-selection" benchmark where
    # the maker is equally likely to have been on either side at that price. That
    # benchmark P&L per contract = (1-2p)*(settle? )... We instead compute the
    # symmetric benchmark below as 'naive_band'.
    naive_band = defaultdict(Acc)
    naive_all = Acc()

    markets_done = 0
    markets_with_candles = 0
    series_seen = set()
    market_count_by_cat = defaultdict(int)
    trade_count_by_cat = defaultdict(int)

    for cat in CATEGORIES:
        sys.stderr.write(f"\n=== CATEGORY {cat} ===\n")
        series = list_series(cat)
        sys.stderr.write(f"  series found: {len(series)}\n")
        scanned = 0
        for s in series:
            if markets_done >= MAX_MARKETS_TOTAL:
                break
            stk = s.get("ticker")
            if not stk or stk in series_seen:
                continue
            series_seen.add(stk)
            scanned += 1
            if scanned > MAX_SERIES_PER_CAT:
                break
            markets = list_settled_markets(stk)
            for m in markets:
                if markets_done >= MAX_MARKETS_TOTAL:
                    break
                # filters: binary, no mve collection, volume>=300, result in yes/no
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
                trades = get_trades(tk)
                if not trades:
                    continue
                markets_done += 1
                market_count_by_cat[cat] += 1

                # candles for markout, spanning the market lifetime
                ot = parse_ts(m.get("open_time"))
                ct = parse_ts(m.get("close_time"))
                candles = []
                if ot and ct and ct > ot:
                    candles = get_candles(stk, tk, ot - 120, ct + 120)
                # build sorted list of (end_period_ts, mid)
                cseries = []
                for c in candles:
                    ept = c.get("end_period_ts")
                    mid = candle_mid(c)
                    if ept is not None and mid is not None:
                        cseries.append((float(ept), mid))
                cseries.sort()
                if cseries:
                    markets_with_candles += 1

                def mid_after(t_epoch, minutes):
                    if not cseries:
                        return None
                    target = t_epoch + minutes * 60
                    # first candle whose end >= target
                    for ept, mid in cseries:
                        if ept >= target:
                            # only accept if within a reasonable window (<= 3*window)
                            if ept - target <= minutes * 60 * 3 + 120:
                                return mid
                            return None
                    return None

                for t in trades:
                    if t.get("is_block_trade"):
                        continue
                    p = fnum(t.get("yes_price_dollars"))
                    if p is None or p <= 0 or p >= 1:
                        continue
                    cnt = fnum(t.get("count_fp"), 0.0)
                    if cnt <= 0:
                        continue
                    tside = t.get("taker_side")
                    tepoch = parse_ts(t.get("created_time"))
                    if tside == "yes":
                        # taker buys yes -> maker sold yes -> maker SHORT yes
                        maker_long = False
                        pnl_settle = (p - settle)
                    elif tside == "no":
                        # taker sells yes -> maker bought yes -> maker LONG yes
                        maker_long = True
                        pnl_settle = (settle - p)
                    else:
                        continue
                    pnl_settle_net = pnl_settle - fee(p)
                    b = band_of(p)
                    settle_band[b].add(pnl_settle_net, cnt)
                    settle_all.add(pnl_settle_net, cnt)
                    trade_count_by_cat[cat] += 1

                    # naive benchmark: no-selection symmetric P&L per contract.
                    # If selection were absent, a maker resting at price p on a market
                    # that settles 'settle' would, on the directional position implied
                    # by p, earn the favorite-longshot edge = |settle - p| signed by
                    # the rational side (buy yes if p<fair). With no per-market fair val,
                    # the cleanest no-selection benchmark is the position a maker would
                    # hold if its side were determined by the market price relative to
                    # 0.5 (i.e., always fade the longshot): long yes if p<0.5 else short.
                    if p < 0.5:
                        naive_pnl = (settle - p) - fee(p)   # long yes (fade longshot 'no')
                    else:
                        naive_pnl = (p - settle) - fee(p)   # short yes (fade longshot 'yes')
                    naive_band[b].add(naive_pnl, cnt)
                    naive_all.add(naive_pnl, cnt)

                    # short-horizon markout
                    if tepoch is not None:
                        fm = mid_after(tepoch, MARKOUT_MIN)
                        if fm is not None:
                            if maker_long:
                                mo = (fm - p)
                            else:
                                mo = (p - fm)
                            markout_band[b].add(mo, cnt)
                            markout_all.add(mo, cnt)
                sys.stderr.write(f"    {tk} r={result} v={vol:.0f} trades={len(trades)} (mkt#{markets_done})\n")
        if markets_done >= MAX_MARKETS_TOTAL:
            break

    # ---------------------------------------------------------- report
    def line(name, acc):
        return (f"{name:>18s}  n={acc.n:6d}  contracts={acc.contracts:11.0f}  "
                f"VWmean={acc.vw_mean():+.4f}  TWmean={acc.tw_mean():+.4f}  "
                f"TWse={acc.tw_se():.4f}")

    report = []
    report.append("==== KALSHI MAKER ADVERSE SELECTION ====")
    report.append(f"markets analyzed: {markets_done}  (with candles: {markets_with_candles})")
    report.append(f"series scanned: {len(series_seen)}")
    report.append("markets by category: " + ", ".join(f"{k}={v}" for k, v in market_count_by_cat.items()))
    report.append("trades by category:  " + ", ".join(f"{k}={v}" for k, v in trade_count_by_cat.items()))
    report.append("")
    report.append("MAKER REALIZED P&L TO SETTLEMENT, NET OF FEE ($/contract; +=maker wins):")
    for b in BANDS:
        report.append("  " + line(b, settle_band[b]))
    report.append("  " + line("OVERALL", settle_all))
    report.append("")
    report.append(f"SHORT-HORIZON MARKOUT (+{MARKOUT_MIN}min mid move, maker dir, PRE-fee):")
    for b in BANDS:
        report.append("  " + line(b, markout_band[b]))
    report.append("  " + line("OVERALL", markout_all))
    report.append("")
    report.append("NAIVE 'fade-the-longshot, ignore selection' BENCHMARK (net of fee):")
    for b in BANDS:
        report.append("  " + line(b, naive_band[b]))
    report.append("  " + line("OVERALL", naive_all))

    out = "\n".join(report)
    print(out)
    with open("advsel_results.txt", "w") as f:
        f.write(out + "\n")

    # machine-readable for the .md writer
    def dump(acc):
        return {"n": acc.n, "contracts": acc.contracts, "vw": acc.vw_mean(),
                "tw": acc.tw_mean(), "se": acc.tw_se()}
    blob = {
        "markets": markets_done, "markets_with_candles": markets_with_candles,
        "series": len(series_seen),
        "markets_by_cat": dict(market_count_by_cat),
        "trades_by_cat": dict(trade_count_by_cat),
        "settle": {b: dump(settle_band[b]) for b in BANDS} | {"OVERALL": dump(settle_all)},
        "markout": {b: dump(markout_band[b]) for b in BANDS} | {"OVERALL": dump(markout_all)},
        "naive": {b: dump(naive_band[b]) for b in BANDS} | {"OVERALL": dump(naive_all)},
        "markout_min": MARKOUT_MIN, "fee_rate": FEE_RATE, "min_volume_fp": MIN_VOLUME_FP,
    }
    with open("advsel_results.json", "w") as f:
        json.dump(blob, f, indent=2)

if __name__ == "__main__":
    main()
