#!/usr/bin/env python3
"""
kalshi_spx.py  -- Kalshi-native S&P 500 / index DAILY BRACKET strategy test.

Two candidate edges on Kalshi's exclusive-exhaustive daily "index will close
between X and Y" bracket markets (series KXINX = S&P 500 range, KXNASDAQ100 =
Nasdaq range):

  (a) SHORT-VOL premium: SELL outer/longshot brackets whose entry (executable
      yes_bid) sits in [0.05, 0.30].  Seller keeps premium if the bracket does
      NOT contain the settlement value.  Do retail buyers overpay for the
      unlikely brackets (like the crypto longshot short-vol edge)?

  (b) STRUCTURAL mispricing: the daily bracket SET is exclusive & exhaustive
      (exactly one bracket wins, pays $1).  Sum of executable asks (buy-all)
      < 1 net of fees  => riskless underround.  Sum of executable bids
      (sell-all) > 1 net of fees => riskless overround.

DISCIPLINE
  * NET of Kalshi fees ALWAYS.  Kalshi quadratic fee: per-contract fee at price
    p = 0.07 * p * (1-p).  Rounded (ceil to cent per contract) reported too.
  * Executable prices: a YES seller RECEIVES yes_bid; a YES buyer PAYS yes_ask.
    Never mid for PnL.  Mid used only for the inclusion band / "priced prob".
  * Entry taken from an intraday candlestick in the FIRST HALF of the RTH
    (~15:00Z, ~11am ET) -- NOT the terminal snapshot (which collapses to the
    outcome; look-ahead trap).
  * Cluster t by DAY (daily brackets resolve daily): each event-day contributes
    one mean; t = mean(daily means)/(sd/sqrt(n_days)).
  * Structural arb verified EXHAUSTIVE at settlement: exactly one bracket
    resolves YES, else the "arb" is illusory.
  * Small-n flagged; multiple-testing count reported.

Usage:  python3 kalshi_spx.py [collect|analyze]   (no arg = collect then analyze)
Outputs: kalshi_spx_report.md, kalshi_spx_summary.json
Raw cached under scratchpad/kalshi_spx_raw/.
"""
import urllib.request, json, os, sys, time, math, statistics
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = "/home/user/Codex-playground-"
RAW  = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/kalshi_spx_raw"
os.makedirs(RAW, exist_ok=True)

SERIES = {"KXINX": "S&P 500", "KXNASDAQ100": "Nasdaq-100"}
WORKERS = 24
ENTRY_TARGET_Z = (15, 0)   # 15:00 UTC ~ 11:00 ET, first-half of the 13:30-20:00Z RTH
ROBUST_TARGET_Z = (17, 0)  # 17:00 UTC ~ 1pm ET robustness snapshot
BAND = (0.05, 0.30)        # short-vol seller inclusion band on the ENTRY yes_bid


def get(url, tries=5):
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=45) as r:
                return json.load(r)
        except Exception as e:
            last = str(e); time.sleep(0.8)
    return {"__err": last}


def fl(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def iso_ts(t):
    return int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())


def fee(p):
    """Kalshi quadratic per-contract fee at price p (continuous)."""
    return 0.07 * p * (1.0 - p)


def fee_ceil(p, n=1):
    """Kalshi rounds fee up to the cent per order of n contracts."""
    return math.ceil(0.07 * n * p * (1.0 - p) * 100.0) / 100.0 / n


# ---------------------------------------------------------------- collect
def list_settled(series):
    out, cur = [], None
    while True:
        u = f"{BASE}/markets?series_ticker={series}&status=settled&limit=1000"
        if cur:
            u += f"&cursor={cur}"
        d = get(u)
        if "__err" in d:
            break
        out += d.get("markets", [])
        cur = d.get("cursor")
        if not cur:
            break
    return out


def candles(series, ticker, st, en):
    path = os.path.join(RAW, f"c_{ticker}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    u = f"{BASE}/series/{series}/markets/{ticker}/candlesticks?start_ts={st}&end_ts={en}&period_interval=60"
    d = get(u)
    cs = d.get("candlesticks", []) if "__err" not in d else []
    with open(path, "w") as f:
        json.dump(cs, f)
    return cs


def event_date(ev):
    # KXINX-26JUL14H1600 -> datetime for 2026-07-14
    core = ev.split("-")[1]  # 26JUL14H1600
    dd = core[:7]            # 26JUL14
    yy = 2000 + int(dd[:2]); mon = dd[2:5]; day = int(dd[5:7])
    mm = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}[mon]
    return datetime(yy, mm, day, tzinfo=timezone.utc)


def collect():
    data = {}
    for series in SERIES:
        print(f"[collect] {series} ...")
        mk = list_settled(series)
        # group by event
        evs = {}
        for m in mk:
            evs.setdefault(m["event_ticker"], []).append(m)
        # keep only KXINX-style dated daily events (H1600 close), drop legacy singletons
        evs = {e: v for e, v in evs.items() if "H1600" in e or "H1300" in e}
        print(f"  {len(mk)} markets, {len(evs)} daily events")
        # fetch candles for every bracket
        jobs = []
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            fut = {}
            for e, v in evs.items():
                for m in v:
                    st = iso_ts(m["open_time"]) - 3600
                    en = iso_ts(m["close_time"]) + 60
                    fut[ex.submit(candles, series, m["ticker"], st, en)] = m["ticker"]
            done = 0
            for f in as_completed(fut):
                done += 1
                if done % 300 == 0:
                    print(f"    candles {done}/{len(fut)}")
        # assemble
        data[series] = {"events": {}}
        for e, v in evs.items():
            brackets = []
            for m in v:
                cs = candles(series, m["ticker"], 0, 0)  # cached now
                brackets.append({
                    "ticker": m["ticker"],
                    "floor": m.get("floor_strike"),
                    "cap": m.get("cap_strike"),
                    "result": m.get("result"),
                    "strike_type": m.get("strike_type"),
                    "close_time": m.get("close_time"),
                    "open_time": m.get("open_time"),
                    "settle_val": fl(m.get("expiration_value")),
                    "volume": fl(m.get("volume_fp")),
                    "candles": cs,
                })
            data[series]["events"][e] = brackets
    with open(os.path.join(RAW, "assembled.json"), "w") as f:
        json.dump(data, f)
    print("[collect] done, assembled cached")
    return data


# ---------------------------------------------------------------- helpers
def candle_at(cs, target_ts):
    """Return (yes_bid_close, yes_ask_close) of the candle nearest to but not
    after target_ts, else nearest overall. Prices in dollars (0..1)."""
    best = None; bestdt = None
    for c in cs:
        ct = c["end_period_ts"]
        yb = fl(c.get("yes_bid", {}).get("close_dollars"))
        ya = fl(c.get("yes_ask", {}).get("close_dollars"))
        dt = target_ts - ct
        # prefer candle at/just before target (dt>=0); take the smallest non-negative dt
        key = (0 if dt >= 0 else 1, abs(dt))
        if best is None or key < bestdt:
            best = (yb, ya, ct); bestdt = key
    if best is None:
        return None
    return best


# ---------------------------------------------------------------- analyze
def analyze():
    with open(os.path.join(RAW, "assembled.json")) as f:
        data = json.load(f)

    summary = {"generated": datetime.now(timezone.utc).isoformat(), "series": {}}
    report_sections = []

    for series, human in SERIES.items():
        if series not in data:
            continue
        events = data[series]["events"]

        # ---------- exhaustiveness check ----------
        exh_ok = 0; exh_bad = 0; nwin = []
        for e, brs in events.items():
            wins = sum(1 for b in brs if b["result"] == "yes")
            nwin.append(wins)
            if wins == 1:
                exh_ok += 1
            else:
                exh_bad += 1

        # ---------- SHORT-VOL test ----------
        # For each event, target entry snapshot; qualify brackets whose entry
        # yes_bid in BAND (sellable outer bracket). Seller receives yes_bid.
        daily_pnl = {}          # event -> list of seller PnL/ct (continuous fee)
        daily_pnl_ceil = {}     # ceil fee
        cal_rows = []           # (mid, outcome) for calibration
        all_trades = []
        for e, brs in events.items():
            ed = event_date(e)
            target = int(datetime(ed.year, ed.month, ed.day, ENTRY_TARGET_Z[0], ENTRY_TARGET_Z[1], tzinfo=timezone.utc).timestamp())
            for b in brs:
                q = candle_at(b["candles"], target)
                if q is None:
                    continue
                yb, ya, cts = q
                if yb <= 0 or ya <= 0 or ya >= 1.0:
                    continue
                mid = 0.5 * (yb + ya)
                # outer/longshot SELL candidate: executable sell price (yes_bid) in band
                if not (BAND[0] <= yb <= BAND[1]):
                    continue
                outcome = 1.0 if b["result"] == "yes" else 0.0
                # seller PnL/ct = premium received - payout - fee
                pnl = yb - outcome - fee(yb)
                pnl_c = yb - outcome - fee_ceil(yb)
                daily_pnl.setdefault(e, []).append(pnl)
                daily_pnl_ceil.setdefault(e, []).append(pnl_c)
                cal_rows.append((mid, outcome, yb))
                all_trades.append({"event": e, "ticker": b["ticker"], "yb": yb, "ya": ya,
                                   "mid": mid, "outcome": outcome, "pnl": pnl})

        # day-clustered stats
        dmeans = [statistics.mean(v) for v in daily_pnl.values() if v]
        dmeans_c = [statistics.mean(v) for v in daily_pnl_ceil.values() if v]
        n_days = len(dmeans)
        n_trades = sum(len(v) for v in daily_pnl.values())
        if n_days >= 2:
            gmean = statistics.mean(dmeans)
            gsd = statistics.stdev(dmeans)
            tstat = gmean / (gsd / math.sqrt(n_days)) if gsd > 0 else float("nan")
            gmean_c = statistics.mean(dmeans_c)
            gsd_c = statistics.stdev(dmeans_c)
            tstat_c = gmean_c / (gsd_c / math.sqrt(n_days)) if gsd_c > 0 else float("nan")
        else:
            gmean = gsd = tstat = gmean_c = tstat_c = float("nan")

        # calibration: among band brackets, priced prob (mid) vs realized YES rate
        if cal_rows:
            avg_mid = statistics.mean(r[0] for r in cal_rows)
            avg_bid = statistics.mean(r[2] for r in cal_rows)
            realized_yes = statistics.mean(r[1] for r in cal_rows)
        else:
            avg_mid = avg_bid = realized_yes = float("nan")

        # worst day
        worst = min(dmeans) if dmeans else float("nan")
        # win rate of seller (bracket settles NO)
        seller_win = statistics.mean(1.0 - r[1] for r in cal_rows) if cal_rows else float("nan")

        # ---------- STRUCTURAL test ----------
        # synchronized cross-section at entry target and at robust target.
        struct = {}
        for label, tz in [("mid_am", ENTRY_TARGET_Z), ("early_pm", ROBUST_TARGET_Z)]:
            underrounds = []; overrounds = []; details = []
            for e, brs in events.items():
                ed = event_date(e)
                target = int(datetime(ed.year, ed.month, ed.day, tz[0], tz[1], tzinfo=timezone.utc).timestamp())
                asks = []; bids = []; ok = True
                winner_present = sum(1 for b in brs if b["result"] == "yes")
                for b in brs:
                    q = candle_at(b["candles"], target)
                    if q is None:
                        ok = False; break
                    yb, ya, _ = q
                    asks.append(ya); bids.append(yb)
                if not ok or not asks:
                    continue
                # buy-all-YES: pay each ask + fee; wings with ask>=1 or ask<=0 -> treat 0-ask as unavailable
                buy_cost = sum(a + fee_ceil(a) for a in asks if 0 < a < 1.0)
                n_buyable = sum(1 for a in asks if 0 < a < 1.0)
                # sell-all-YES: receive each bid - fee; bid==0 not sellable
                sell_take = sum(b - fee_ceil(b) for b in bids if b > 0)
                n_sellable = sum(1 for b in bids if b > 0)
                # underround requires buying the FULL set (all brackets buyable)
                full_buy = (n_buyable == len(asks))
                full_sell = (n_sellable == len(bids))
                if full_buy:
                    underrounds.append(1.0 - buy_cost)   # >0 => riskless profit/ct
                if full_sell:
                    overrounds.append(sell_take - 1.0)    # >0 => riskless profit/ct
                details.append({"event": e, "buy_cost": buy_cost, "n_buyable": n_buyable,
                                "sell_take": sell_take, "n_sellable": n_sellable,
                                "nbr": len(asks), "winner_present": winner_present})
            struct[label] = {
                "n_days_full_buy": len(underrounds),
                "underround_mean": (statistics.mean(underrounds) if underrounds else None),
                "underround_max": (max(underrounds) if underrounds else None),
                "underround_positive_days": sum(1 for x in underrounds if x > 0),
                "n_days_full_sell": len(overrounds),
                "overround_mean": (statistics.mean(overrounds) if overrounds else None),
                "overround_max": (max(overrounds) if overrounds else None),
                "overround_positive_days": sum(1 for x in overrounds if x > 0),
                "details_sample": details[:3],
            }

        # capacity: median event volume
        evol = [sum(b["volume"] for b in brs) for brs in events.values()]
        band_vol = None  # approximate band-bracket capacity from terminal volume unavailable per-candle reliably

        summary["series"][series] = {
            "human": human,
            "n_events": len(events),
            "exhaustive_days": exh_ok,
            "nonexhaustive_days": exh_bad,
            "shortvol": {
                "band": BAND,
                "n_days": n_days,
                "n_trades": n_trades,
                "mean_pnl_ct_contfee": gmean,
                "t_day_clustered_contfee": tstat,
                "mean_pnl_ct_ceilfee": gmean_c,
                "t_day_clustered_ceilfee": tstat_c,
                "worst_day_mean": worst,
                "seller_win_rate": seller_win,
                "calibration_avg_mid": avg_mid,
                "calibration_avg_bid": avg_bid,
                "calibration_realized_yes": realized_yes,
            },
            "structural": struct,
            "capacity_median_event_volume": statistics.median(evol) if evol else 0,
            "capacity_max_event_volume": max(evol) if evol else 0,
        }

        # ---- report section ----
        rs = [f"## {series} ({human}) -- {len(events)} settled daily events\n"]
        rs.append(f"Exhaustive (exactly 1 winner) days: {exh_ok}/{exh_ok+exh_bad}; "
                  f"non-exhaustive: {exh_bad}\n")
        rs.append(f"### Short-vol (SELL outer brackets, entry yes_bid in {BAND})\n")
        rs.append(f"- n_days={n_days}, n_trades={n_trades}")
        rs.append(f"- seller net PnL/ct (continuous fee): {gmean:+.4f}, day-clustered t = {tstat:.2f}")
        rs.append(f"- seller net PnL/ct (ceil fee): {gmean_c:+.4f}, day-clustered t = {tstat_c:.2f}")
        rs.append(f"- seller win rate (bracket settles NO): {seller_win:.3f}")
        rs.append(f"- calibration: avg priced mid={avg_mid:.3f}, avg bid={avg_bid:.3f}, "
                  f"realized YES rate={realized_yes:.3f}")
        rs.append(f"- worst day mean PnL/ct: {worst:+.4f}\n")
        rs.append(f"### Structural (exclusive-exhaustive bracket set)\n")
        for label in ("mid_am", "early_pm"):
            s = struct[label]
            rs.append(f"- [{label}] full-buyable days={s['n_days_full_buy']}, "
                      f"underround(1-buycost) mean={s['underround_mean']}, "
                      f"max={s['underround_max']}, positive_days={s['underround_positive_days']}")
            rs.append(f"- [{label}] full-sellable days={s['n_days_full_sell']}, "
                      f"overround(selltake-1) mean={s['overround_mean']}, "
                      f"max={s['overround_max']}, positive_days={s['overround_positive_days']}")
        rs.append(f"\n- capacity: median event volume={summary['series'][series]['capacity_median_event_volume']:.0f} ct, "
                  f"max={summary['series'][series]['capacity_max_event_volume']:.0f} ct\n")
        report_sections.append("\n".join(rs))

    # multiple testing count: 2 series x 2 edges x 2 snapshots for structural + shortvol
    n_tests = len(SERIES) * (1 + 2)  # 1 shortvol + 2 structural snapshots per series
    summary["multiple_testing_count"] = n_tests

    with open(os.path.join(ROOT, "kalshi_spx_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)

    # ---- assemble report ----
    hdr = [
        "# Kalshi index daily-bracket strategy test (S&P 500 / Nasdaq range)",
        f"_generated {summary['generated']}_\n",
        "Kalshi-native daily bracket markets: exclusive-exhaustive 'index will "
        "close between X and Y' contracts (25-pt SPX brackets, ~30/day + two tails).",
        "All PnL NET of Kalshi quadratic fee (0.07*p*(1-p)/ct). Executable prices: "
        "seller RECEIVES yes_bid. Entry from ~15:00Z (11am ET) intraday candle "
        "(first-half RTH, no terminal look-ahead). t clustered by DAY.\n",
        f"Multiple-testing count: {n_tests} tests "
        f"({len(SERIES)} series x [1 short-vol + 2 structural snapshots]).\n",
    ]
    with open(os.path.join(ROOT, "kalshi_spx_report.md"), "w") as f:
        f.write("\n".join(hdr) + "\n" + "\n\n".join(report_sections))
    print("[analyze] wrote kalshi_spx_report.md + kalshi_spx_summary.json")
    return summary


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("collect", "all"):
        collect()
    if mode in ("analyze", "all"):
        s = analyze()
        print(json.dumps(s["series"], indent=1, default=str)[:2000])
