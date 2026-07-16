#!/usr/bin/env python3
"""
Cross-asset replication + capacity study of the Kalshi hourly-ladder deep-OTM
WING variance-risk-premium edge.

Validated edge (on BTC KXBTCD): deep-OTM wing strikes (early YES price in
(0,0.15]) are systematically OVERPRICED. SELLING YES on wings, entered in the
first half of [open,close] at the real observed bid, nets ~+1-2c/ct net of fees.

This script tests whether that REPLICATES on sibling hourly crypto ladders
(ETH=KXETHD, SOL=KXSOLD, XRP=KXXRPD, DOGE=KXDOGED) and measures CAPACITY.

Method (mirrors the BTC verification, per asset):
  - Wing = market whose count-weighted first-half YES VWAP is in (0, 0.15],
    with >= 2 first-half trades (first half strictly by created_time).
  - entry price  = count-weighted VWAP of yes_price over first-half trades.
  - executable SELL price = mean yes_price of first-half taker-SELL trades
    (taker_side=="no" => taker bought NO == sold YES == hit the yes bid).
    This is what a real seller would actually receive.
  - Outcome from SETTLEMENT only (result yes=1 / no=0).
  - PnL/ct (sell yes) = sell_price - outcome - fee,
    fee = max(0.01, ceil(0.07*p*(1-p)*100)/100).
  - Bin by entry VWAP: <=.02, .02-.04, .04-.06, .06-.10, .10-.15.
  - Calibration: realized YES rate vs entry. Day-cluster t (cluster by close
    DATE). OOS split train 70% / test 30% by date.
  - Power gate: need >=1500 wing obs and >=30 dates/asset else flag underpowered.

Anti-artifact: first-half entry strictly by created_time (no look-ahead);
outcome only from settlement; everything day-clustered; per-asset reporting.
"""
import json, os, sys, time, math, statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/xasset_cache"
os.makedirs(CACHE, exist_ok=True)

ASSETS = {
    "BTC": "KXBTCD",
    "ETH": "KXETHD",
    "SOL": "KXSOLD",
    "XRP": "KXXRPD",
    "DOGE": "KXDOGED",
}
TARGET_EVENTS = int(os.environ.get("TARGET_EVENTS", "900"))  # per asset
WING_MAX = 0.15
MIN_EARLY_TRADES = 2
BINS = [(0.00, 0.02), (0.02, 0.04), (0.04, 0.06), (0.06, 0.10), (0.10, 0.15)]

S = requests.Session()
S.headers.update({"Accept": "application/json"})


def get(path, params=None, tries=5):
    for i in range(tries):
        try:
            r = S.get(BASE + path, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.8 * (i + 1)); continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(0.8 * (i + 1))
    return None


def parse_ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def fnum(x, default=None):
    if x is None:
        return default
    try:
        return float(x)
    except Exception:
        return default


def yes_price(t):
    return fnum(t.get("yes_price_dollars"))


def count_of(t):
    return fnum(t.get("count_fp"), 1.0)


def kalshi_fee(price):
    p = min(max(price, 0.0), 1.0)
    return max(0.01, math.ceil(0.07 * p * (1 - p) * 100.0) / 100.0)


# ---------------- data pulls (cached) ----------------
def pull_events(series):
    cf = os.path.join(CACHE, f"events_{series}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out, cursor = [], None
    while len(out) < TARGET_EVENTS:
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        j = get("/events", p)
        if not j:
            break
        evs = j.get("events", [])
        out.extend(evs)
        cursor = j.get("cursor")
        if not cursor or not evs:
            break
    json.dump(out, open(cf, "w"))
    return out


def pull_markets(et):
    cf = os.path.join(CACHE, f"mk_{et}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out, cursor = [], None
    while True:
        p = {"event_ticker": et, "limit": 400}
        if cursor:
            p["cursor"] = cursor
        j = get("/markets", p)
        if not j:
            break
        mk = j.get("markets", [])
        out.extend(mk)
        cursor = j.get("cursor")
        if not cursor or not mk:
            break
    json.dump(out, open(cf, "w"))
    return out


def pull_trades_window(ticker, min_ts, max_ts, maxpages=4):
    cf = os.path.join(CACHE, f"trw_{ticker}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out, cursor, pages = [], None, 0
    while pages < maxpages:
        p = {"ticker": ticker, "limit": 1000, "min_ts": int(min_ts), "max_ts": int(max_ts)}
        if cursor:
            p["cursor"] = cursor
        j = get("/markets/trades", p)
        if not j:
            break
        tr = j.get("trades", [])
        out.extend(tr)
        cursor = j.get("cursor")
        pages += 1
        if not cursor or not tr or len(tr) < 1000:
            break
    json.dump(out, open(cf, "w"))
    return out


# ---------------- build per-asset wing records ----------------
def build_asset(name, series):
    events = pull_events(series)
    print(f"[{name}] settled events pulled: {len(events)}", file=sys.stderr)
    ev_tickers = [e["event_ticker"] for e in events]

    markets_by_ev = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(pull_markets, et): et for et in ev_tickers}
        for f in as_completed(futs):
            et = futs[f]
            try:
                markets_by_ev[et] = f.result()
            except Exception:
                markets_by_ev[et] = []

    # candidate markets: settled + traded + HOURLY (life ~1h). The KXxxxD roots
    # also carry a few 25h/169h daily/weekly products; restrict to the hourly
    # ladder the edge is defined on.
    cand = []
    n_nonhourly = 0
    for et, mks in markets_by_ev.items():
        for m in mks:
            if m.get("result") not in ("yes", "no"):
                continue
            if fnum(m.get("volume_fp"), 0) <= 0:
                continue
            ot = parse_ts(m.get("open_time")); ct = parse_ts(m.get("close_time"))
            if ot is None or ct is None or ct <= ot:
                continue
            life_h = (ct - ot) / 3600.0
            if not (0.8 <= life_h <= 1.2):   # hourly ladder only
                n_nonhourly += 1
                continue
            cand.append(m)
    print(f"[{name}] settled HOURLY markets with volume>0: {len(cand)} "
          f"(dropped {n_nonhourly} non-hourly)", file=sys.stderr)

    def job(m):
        ot = parse_ts(m.get("open_time")); ct = parse_ts(m.get("close_time"))
        if ot is None or ct is None or ct <= ot:
            return (m["ticker"], [])
        half = ot + (ct - ot) * 0.5
        return (m["ticker"], pull_trades_window(m["ticker"], ot, half))

    trades_by_tk = {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = {ex.submit(job, m): m for m in cand}
        done = 0
        for f in as_completed(futs):
            try:
                tk, tr = f.result(); trades_by_tk[tk] = tr
            except Exception:
                pass
            done += 1
            if done % 2000 == 0:
                print(f"[{name}] trades {done}/{len(cand)}", file=sys.stderr)

    recs = []
    for m in cand:
        tk = m["ticker"]
        ot = parse_ts(m.get("open_time")); ct = parse_ts(m.get("close_time"))
        if ot is None or ct is None or ct <= ot:
            continue
        life = ct - ot
        halfmark = ot + life * 0.5
        res = 1.0 if m.get("result") == "yes" else 0.0
        trs = trades_by_tk.get(tk, [])
        first = []
        for t in trs:
            ts = parse_ts(t.get("created_time"))
            yp = yes_price(t)
            if ts is None or yp is None:
                continue
            if ts < ot - 2 or ts > halfmark:   # strict first-half by created_time
                continue
            first.append((ts, yp, t.get("taker_side"), count_of(t)))
        if len(first) < MIN_EARLY_TRADES:
            continue
        csum = sum(x[3] for x in first)
        if csum <= 0:
            continue
        vwap = sum(x[1] * x[3] for x in first) / csum
        # taker-side split: taker_side=="no" => sold YES (hit yes bid)
        sell_trades = [x for x in first if x[2] == "no"]
        buy_trades = [x for x in first if x[2] == "yes"]
        sell_px = statistics.mean([x[1] for x in sell_trades]) if sell_trades else None
        sell_vol = sum(x[3] for x in sell_trades)
        buy_vol = sum(x[3] for x in buy_trades)
        first_vol = csum
        close_date = (m.get("close_time") or "")[:10]
        recs.append(dict(
            ticker=tk, asset=name, close_date=close_date, result=res,
            vwap=vwap, sell_px=sell_px, n_first=len(first),
            first_vol=first_vol, sell_vol=sell_vol, buy_vol=buy_vol,
            volume_fp=fnum(m.get("volume_fp"), 0.0),
            yes_bid_size_fp=fnum(m.get("yes_bid_size_fp"), None),
            floor_strike=fnum(m.get("floor_strike"), None),
        ))
    print(f"[{name}] markets with >=2 first-half trades: {len(recs)}", file=sys.stderr)
    json.dump(recs, open(os.path.join(CACHE, f"recs_{name}.json"), "w"))
    return recs


# ---------------- stats ----------------
def cluster_t(pairs):
    """pairs: list of (value, cluster_key) -> (mean, day-clustered t, N, G)."""
    vals = [p[0] for p in pairs]
    N = len(vals)
    if N < 2:
        return (float("nan"), float("nan"), N, 0)
    mean = sum(vals) / N
    cs = defaultdict(float)
    for v, g in pairs:
        cs[g] += (v - mean)
    G = len(cs)
    if G < 2:
        return (mean, float("nan"), N, G)
    meat = sum(s * s for s in cs.values())
    var = (G / (G - 1.0)) * meat / (N * N)
    se = math.sqrt(var) if var > 0 else float("nan")
    return (mean, mean / se if se and se > 0 else float("nan"), N, G)


def sell_pnl(price, result):
    return price - result - kalshi_fee(price)


def analyze_asset(name, recs, out):
    def P(s=""):
        out.append(s); print(s)

    wings = [r for r in recs if r["vwap"] is not None and 0 < r["vwap"] <= WING_MAX]
    dates = sorted(set(r["close_date"] for r in wings))
    P("=" * 92)
    P(f"ASSET {name}: total first-half-traded markets={len(recs)}  "
      f"WING obs={len(wings)}  distinct dates={len(dates)}")
    if wings:
        P(f"  date range {dates[0]}..{dates[-1]}")
    underpowered = (len(wings) < 1500) or (len(dates) < 30)
    if underpowered:
        P(f"  ** UNDERPOWERED ** (need >=1500 wing obs & >=30 dates; "
          f"have {len(wings)} obs, {len(dates)} dates)")
    if not wings:
        return dict(asset=name, wings=0, dates=0, underpowered=True)

    # ---- calibration + full-sample day-clustered sell PnL by bin ----
    P("\n  CALIBRATION & SELL-YES PnL (full sample)")
    P(f"  {'bin':>10}{'N':>6}{'dts':>5}{'entry':>7}{'realYes':>8}{'gap':>7}"
      f"{'sellVWAP¢':>10}{'tVWAP':>7}{'sellExec¢':>10}{'tExec':>7}{'nExec':>6}")
    for lo, hi in BINS + [(0.0, WING_MAX)]:
        if (lo, hi) == (0.0, WING_MAX):
            sub = wings; lab = "ALL<=.15"
        else:
            sub = [r for r in wings if lo < r["vwap"] <= hi]; lab = f"{lo:.2f}-{hi:.2f}"
        if not sub:
            P(f"  {lab:>10}{0:>6}"); continue
        entry = statistics.mean(r["vwap"] for r in sub)
        realy = statistics.mean(r["result"] for r in sub)
        dts = len(set(r["close_date"] for r in sub))
        A = cluster_t([(sell_pnl(r["vwap"], r["result"]), r["close_date"]) for r in sub])
        ex = [r for r in sub if r["sell_px"] is not None]
        B = cluster_t([(sell_pnl(r["sell_px"], r["result"]), r["close_date"]) for r in ex])
        P(f"  {lab:>10}{A[3-1] if False else A[2]:>6}{dts:>5}{entry:>7.3f}{realy:>8.3f}"
          f"{realy-entry:>7.3f}{A[0]*100:>10.2f}{A[1]:>7.2f}"
          f"{(B[0]*100 if B[2] else float('nan')):>10.2f}{(B[1] if B[2] else float('nan')):>7.2f}{B[2]:>6}")

    # ---- OOS split by date: train 70% / test 30% ----
    ndates = len(dates)
    cut = dates[int(ndates * 0.7)] if ndates > 3 else dates[-1]
    train = [r for r in wings if r["close_date"] < cut]
    test = [r for r in wings if r["close_date"] >= cut]

    def split_stats(grp, use_exec):
        if use_exec:
            g = [r for r in grp if r["sell_px"] is not None]
            pnl = [(sell_pnl(r["sell_px"], r["result"]), r["close_date"]) for g_ in [g] for r in g_]
        else:
            pnl = [(sell_pnl(r["vwap"], r["result"]), r["close_date"]) for r in grp]
        return cluster_t(pnl)

    P("\n  OUT-OF-SAMPLE (train dates<{}  test>=cut)".format(cut))
    for lab, grp in [("TRAIN", train), ("TEST", test)]:
        tr_dts = len(set(r["close_date"] for r in grp))
        v = split_stats(grp, False)
        e = split_stats(grp, True)
        P(f"  {lab:>6} obs={len(grp):>5} dates={tr_dts:>3}  "
          f"sellVWAP={v[0]*100:>6.2f}c t={v[1]:>5.2f}  "
          f"sellExec={ (e[0]*100 if e[2] else float('nan')):>6.2f}c t={(e[1] if e[2] else float('nan')):>5.2f} (nExec={e[2]})")

    test_exec = split_stats(test, True)
    test_vwap = split_stats(test, False)
    exec_cov = sum(1 for r in wings if r["sell_px"] is not None) / len(wings)
    return dict(asset=name, wings=len(wings), dates=len(dates), underpowered=underpowered,
                test_exec_c=test_exec[0]*100 if test_exec[2] else float("nan"),
                test_exec_t=test_exec[1] if test_exec[2] else float("nan"),
                test_exec_n=test_exec[2],
                test_vwap_c=test_vwap[0]*100, test_vwap_t=test_vwap[1],
                exec_coverage=exec_cov)


def capacity(name, recs, out):
    def P(s=""):
        out.append(s); print(s)
    wings = [r for r in recs if r["vwap"] is not None and 0 < r["vwap"] <= WING_MAX]
    if not wings:
        return None
    P("\n  CAPACITY [{}]  (n wings={})".format(name, len(wings)))

    def pctiles(vals, ps=(10, 25, 50, 75, 90, 99)):
        vals = sorted(vals)
        if not vals:
            return {}
        return {p: vals[min(len(vals) - 1, int(p / 100 * len(vals)))] for p in ps}

    # (a) yes_bid_size_fp snapshot at wing strikes (settlement snapshot; caveat)
    bids = [r["yes_bid_size_fp"] for r in wings if r["yes_bid_size_fp"] is not None]
    nonzero = [b for b in bids if b > 0]
    P("  (a) yes_bid_size_fp @ wing (SETTLEMENT snapshot, stale) "
      "nonzero {}/{}  pctiles(nonzero)={}".format(
          len(nonzero), len(bids),
          {k: round(v, 0) for k, v in pctiles(nonzero).items()} if nonzero else {}))

    # (b) first-half wing trade VOLUME (count_fp) per market
    fv = pctiles([r["first_vol"] for r in wings])
    P("  (b) first-half wing VOLUME/market (contracts): " +
      "  ".join(f"p{k}={round(v):,}".replace(",", " ") for k, v in fv.items()))

    # (c) realistic sellable-into-bid without moving >~1c:
    #     use the observed first-half taker-SELL volume (contracts that actually
    #     transacted by hitting the yes bid) as a lower-bound tradeable size.
    sv = pctiles([r["sell_vol"] for r in wings])
    sv_prem = pctiles([r["sell_vol"] * r["vwap"] for r in wings])
    P("  (c) first-half taker-SELL vol/market (sellable w/o moving px): " +
      "  ".join(f"p{k}={round(v):,}".replace(",", " ") for k, v in sv.items()))
    P("      premium $ per market (sellvol*price): " +
      "  ".join(f"p{k}=${round(v):,}".replace(",", " ") for k, v in sv_prem.items()))

    # per-event and per-day aggregates
    by_ev = defaultdict(float); by_day = defaultdict(float)
    by_ev_prem = defaultdict(float); by_day_prem = defaultdict(float)
    for r in wings:
        ev = r["ticker"].rsplit("-", 1)[0]
        by_ev[ev] += r["sell_vol"]; by_ev_prem[ev] += r["sell_vol"] * r["vwap"]
        by_day[r["close_date"]] += r["sell_vol"]; by_day_prem[r["close_date"]] += r["sell_vol"] * r["vwap"]
    ev_c = pctiles(list(by_ev.values())); day_c = pctiles(list(by_day.values()))
    P("  per-EVENT sellable contracts (sum over wing strikes): " +
      "  ".join(f"p{k}={round(v):,}".replace(",", " ") for k, v in ev_c.items()))
    P("  per-DAY  sellable contracts: " +
      "  ".join(f"p{k}={round(v):,}".replace(",", " ") for k, v in day_c.items()))
    med_day = statistics.median(list(by_day.values()))
    med_day_prem = statistics.median(list(by_day_prem.values()))
    P(f"  >> BLUNT: median day ~{round(med_day):,} sellable wing contracts, "
      f"~${round(med_day_prem):,} premium".replace(",", " "))
    return dict(asset=name, med_day_contracts=med_day, med_day_prem=med_day_prem,
                med_event_contracts=statistics.median(list(by_ev.values())))


def main():
    out = []
    # verify which sibling series exist
    exist = {}
    for name, series in ASSETS.items():
        j = get("/events", {"series_ticker": series, "status": "settled", "limit": 5})
        n = len(j.get("events", [])) if j else 0
        exist[name] = n > 0
    out.append("SERIES EXISTENCE: " + ", ".join(f"{k}({ASSETS[k]})={'yes' if v else 'NO'}"
                                                 for k, v in exist.items()))
    print(out[-1])

    summary = []; caps = []
    for name, series in ASSETS.items():
        if not exist[name]:
            continue
        recs = build_asset(name, series)
        s = analyze_asset(name, recs, out)
        c = capacity(name, recs, out)
        summary.append(s)
        if c:
            caps.append(c)

    out.append("\n" + "=" * 92)
    out.append("PER-ASSET SUMMARY (OOS TEST set, day-clustered, executable sell price)")
    out.append(f"{'asset':>6}{'wings':>7}{'dates':>6}{'underpwr':>9}"
               f"{'testExec¢':>11}{'tExec':>7}{'testVWAP¢':>11}{'tVWAP':>7}{'execCov':>8}")
    for s in summary:
        out.append(f"{s['asset']:>6}{s['wings']:>7}{s['dates']:>6}"
                   f"{('YES' if s['underpowered'] else 'no'):>9}"
                   f"{s.get('test_exec_c', float('nan')):>11.2f}{s.get('test_exec_t', float('nan')):>7.2f}"
                   f"{s.get('test_vwap_c', float('nan')):>11.2f}{s.get('test_vwap_t', float('nan')):>7.2f}"
                   f"{s.get('exec_coverage', float('nan')):>8.2f}")
    for line in out[-(len(summary) + 3):]:
        print(line)

    json.dump({"summary": summary, "caps": caps}, open(os.path.join(CACHE, "summary.json"), "w"))
    open(os.path.join(CACHE, "report_lines.txt"), "w").write("\n".join(out))
    return summary, caps


if __name__ == "__main__":
    main()
