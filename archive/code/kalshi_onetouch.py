#!/usr/bin/env python3
"""
Kalshi longer-horizon crypto ONE-TOUCH mispricing test (from scratch).

Target: KXBTCMAXMON (and KXETHMAXMON) -- monthly BTC/ETH one-touch ("MAX"):
resolves YES if the CF trimmed-mean price is EVER above strike B during the
month. For B above spot at open this is a genuine upside barrier ("will it
rise to touch B"); for B <= spot it is trivially already-touched.

Hypothesis under test (retail underprices barrier/touch probability):
  Kalshi YES(touch) price is systematically BELOW a fair driftless one-touch
  value FV = 2*N(-ln(B/S)/(sigma*sqrt(T)))  ->  buying touch is +EV.

Anti-artifact discipline baked in:
  * Entry price = first-half-of-life, COUNT-weighted VWAP of yes-price,
    requiring >=2 early trades. Never settlement/last price. No look-ahead.
  * Spot S and sigma are strictly CAUSAL (spot = open-day open; sigma =
    realized vol of the 30 daily log-returns ending the day BEFORE open).
  * We report MARKET-weighted vs TRADE-weighted (fill-weighted) results
    separately. Divergence => market-weighted number is the artifact.
  * Fees charged on every simulated fill: max(0.01, ceil(0.07*p*(1-p)*100)/100).
  * Clustering by close-month; distinct-month count reported (power is tiny).

Outputs: prints tables and writes kalshi_onetouch_report.md.
"""
import json, os, io, math, time, zipfile, statistics
from datetime import datetime, timezone
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SCRATCH = "/tmp/claude-0/-home-user-Codex-playground-/be5bb0ff-7d7c-52f9-a69a-39546079c154/scratchpad/onetouch"
os.makedirs(SCRATCH, exist_ok=True)
S = requests.Session()
S.headers.update({"Accept": "application/json"})

SERIES = {"KXBTCMAXMON": "BTCUSDT", "KXETHMAXMON": "ETHUSDT"}

# ----------------------------- helpers -------------------------------------
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def kfee(p):
    """Kalshi taker fee per contract at price p (dollars)."""
    return max(0.01, math.ceil(0.07 * p * (1.0 - p) * 100.0) / 100.0)

def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def get(path, params, tries=6):
    for i in range(tries):
        try:
            r = S.get(BASE + path, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.0 * (i + 1)); continue
            r.raise_for_status()
        except requests.RequestException:
            time.sleep(1.0 * (i + 1))
    return None

# ----------------------------- markets -------------------------------------
def pull_settled_markets(series):
    cf = os.path.join(SCRATCH, f"mk_{series}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out = []; cur = None
    while True:
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cur: p["cursor"] = cur
        j = get("/markets", p)
        if not j: break
        mk = j.get("markets", [])
        out.extend(mk); cur = j.get("cursor")
        if not cur or not mk: break
    json.dump(out, open(cf, "w"))
    return out

def pull_trades(ticker):
    cf = os.path.join(SCRATCH, f"tr_{ticker}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    out = []; cur = None
    while True:
        p = {"ticker": ticker, "limit": 1000}
        if cur: p["cursor"] = cur
        j = get("/markets/trades", p)
        if not j: break
        tr = j.get("trades", [])
        out.extend(tr); cur = j.get("cursor")
        if not cur or not tr: break
    json.dump(out, open(cf, "w"))
    return out

# ----------------------------- price history -------------------------------
def load_klines(symbol):
    """Return dict date(YYYY-MM-DD)->{'open','high','low','close'} from Binance Vision.
    Uses complete monthly files + daily files for the current (partial) month."""
    cf = os.path.join(SCRATCH, f"kl_{symbol}.json")
    if os.path.exists(cf):
        return json.load(open(cf))
    bars = {}
    def add_zip(content):
        z = zipfile.ZipFile(io.BytesIO(content))
        name = z.namelist()[0]
        for line in z.read(name).decode().strip().splitlines():
            c = line.split(",")
            ot = int(c[0])
            # openTime may be micro (16 digits) or milli (13); normalize to sec
            if ot > 1e15: sec = ot / 1e6
            elif ot > 1e12: sec = ot / 1e3
            else: sec = ot
            d = datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%d")
            bars[d] = {"open": float(c[1]), "high": float(c[2]),
                       "low": float(c[3]), "close": float(c[4])}
    # monthly complete files
    for ym in ["2026-03", "2026-04", "2026-05", "2026-06"]:
        url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{ym}.zip"
        r = S.get(url, timeout=60)
        if r.status_code == 200:
            add_zip(r.content)
    # daily files for July 2026 (partial current month)
    for day in range(1, 17):
        ds = f"2026-07-{day:02d}"
        url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1d/{symbol}-1d-{ds}.zip"
        r = S.get(url, timeout=60)
        if r.status_code == 200:
            add_zip(r.content)
    json.dump(bars, open(cf, "w"))
    return bars

def spot_and_vol(bars, open_dt):
    """Causal spot at open-day open, and annualized 30d realized vol of daily
    log-returns ending the day BEFORE open."""
    od = open_dt.strftime("%Y-%m-%d")
    spot = bars.get(od, {}).get("open")
    days = sorted(bars.keys())
    # closes strictly before open date
    prior = [d for d in days if d < od]
    prior = prior[-31:]  # need 31 closes -> 30 returns
    closes = [bars[d]["close"] for d in prior]
    if len(closes) < 10 or spot is None:
        return spot, None, len(closes)
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    sd = statistics.pstdev(rets)
    sigma = sd * math.sqrt(365.0)
    return spot, sigma, len(rets)

# ----------------------------- entry VWAP ----------------------------------
def entry_vwap(trades, open_dt, close_dt, min_trades=2):
    """First-half-of-life count-weighted VWAP of yes-price. Causal entry."""
    mid = open_dt + (close_dt - open_dt) / 2
    num = den = 0.0; n = 0
    for t in trades:
        ct = dt(t["created_time"])
        if open_dt <= ct <= mid:
            c = float(t["count_fp"]); p = float(t["yes_price_dollars"])
            num += c * p; den += c; n += 1
    if n < min_trades or den == 0:
        return None, n
    return num / den, n

# ----------------------------- main analysis -------------------------------
def build():
    rows = []
    for series, symbol in SERIES.items():
        bars = load_klines(symbol)
        mkts = pull_settled_markets(series)
        for m in mkts:
            open_dt = dt(m["open_time"]); close_dt = dt(m["close_time"])
            # horizon = open -> scheduled expiration (use expected_expiration if present)
            exp = m.get("expected_expiration_time") or m.get("expiration_time") or m["close_time"]
            end_dt = dt(exp)
            T = max((end_dt - open_dt).total_seconds(), 0) / (365.0 * 86400.0)
            B = float(m["floor_strike"])
            spot, sigma, ndays = spot_and_vol(bars, open_dt)
            result = m.get("result")
            touched = 1 if result == "yes" else 0
            trades = pull_trades(m["ticker"])
            ev, ntr = entry_vwap(trades, open_dt, close_dt)
            # fair value one-touch (driftless reflection). Only meaningful for B>spot.
            fv = None; genuine = None
            if spot and sigma and T > 0:
                if B > spot:
                    genuine = True
                    z = math.log(B / spot) / (sigma * math.sqrt(T))
                    fv = min(1.0, 2.0 * norm_cdf(-z))
                else:
                    genuine = False
                    fv = 1.0  # already at/above barrier -> already touched
            rows.append({
                "series": series, "ticker": m["ticker"],
                "event": m["event_ticker"],
                "close_month": m["event_ticker"].split("-")[-1],  # e.g. 26MAY31
                "open": m["open_time"][:10], "close": m["close_time"][:10],
                "T_years": T, "strike": B, "spot": spot, "sigma": sigma,
                "moneyness": (B / spot) if spot else None,
                "genuine": genuine, "result": result, "touched": touched,
                "entry_yes": ev, "n_early_trades": ntr, "fv": fv,
                "volume": float(m.get("volume_fp", 0)),
                "trades": trades, "open_dt": open_dt, "close_dt": close_dt,
            })
    return rows

# ----------------------------- stats ---------------------------------------
def clustered_t(pairs):
    """pairs: list of (value, cluster_key). Returns mean, cluster-robust t,
    n_obs, n_clusters. Cluster-robust SE = sqrt(sum(g_c^2))/N where g_c is the
    sum of demeaned values in cluster c."""
    vals = [v for v, _ in pairs]
    N = len(vals)
    if N == 0: return None
    mean = sum(vals) / N
    clusters = {}
    for v, k in pairs:
        clusters.setdefault(k, []).append(v - mean)
    ssum = sum((sum(g)) ** 2 for g in clusters.values())
    se = math.sqrt(ssum) / N if ssum > 0 else float("nan")
    tstat = mean / se if se and se == se and se > 0 else float("nan")
    return {"mean": mean, "se": se, "t": tstat, "n": N, "clusters": len(clusters)}

def main():
    rows = build()
    genuine = [r for r in rows if r["genuine"] is True]
    trivial = [r for r in rows if r["genuine"] is False]

    out = []
    def emit(s=""):
        print(s); out.append(s)

    emit("# Kalshi longer-horizon crypto ONE-TOUCH mispricing test\n")
    emit(f"Generated {datetime.now(timezone.utc).isoformat()}  (analysis date 2026-07-16)\n")

    # ---- sample summary
    months = sorted(set(r["close_month"] for r in rows))
    gmonths = sorted(set(r["close_month"] for r in genuine))
    emit("## Sample\n")
    emit(f"- Settled markets pulled: {len(rows)} "
         f"(BTC {sum(1 for r in rows if r['series']=='KXBTCMAXMON')}, "
         f"ETH {sum(1 for r in rows if r['series']=='KXETHMAXMON')})")
    emit(f"- Distinct close-months (all): {len(months)} -> {months}")
    emit(f"- GENUINE upside barriers (strike>spot at open): {len(genuine)} "
         f"across {len(gmonths)} distinct close-months {gmonths}")
    emit(f"- Trivial (strike<=spot, already-touched): {len(trivial)}")
    emit(f"- No KXBTCMAXW (weekly) settled markets exist on the venue.")
    emit(f"- GENUINE realized touch count: {sum(r['touched'] for r in genuine)} / {len(genuine)}")
    emit("")

    # ---- per-market table (genuine)
    emit("## Genuine upside-barrier markets (causal spot/vol, entry VWAP, fair value)\n")
    emit("| series | month | strike | spot | B/S | sigma | T(yr) | entry_yes | n_trd | FV(touch) | FV-entry | result |")
    emit("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(genuine, key=lambda x: (x["series"], x["close_month"], x["strike"])):
        ev = f"{r['entry_yes']:.3f}" if r["entry_yes"] is not None else "  -  "
        fv = f"{r['fv']:.3f}" if r["fv"] is not None else "  -  "
        edge = (f"{r['fv']-r['entry_yes']:+.3f}"
                if (r["fv"] is not None and r["entry_yes"] is not None) else "  -  ")
        emit(f"| {r['series'][2:5]} | {r['close_month']} | {r['strike']:.0f} | "
             f"{r['spot']:.0f} | {r['moneyness']:.3f} | {r['sigma']:.2f} | "
             f"{r['T_years']:.3f} | {ev} | {r['n_early_trades']} | {fv} | {edge} | {r['result']} |")
    emit("")

    # ---- TEST 1: calibration by entry price
    emit("## Test 1 - Calibration (realized touch-rate vs entry price)\n")
    cal = [r for r in genuine if r["entry_yes"] is not None]
    bins = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 1.01)]
    emit("| entry-price bin | n markets | mean entry | realized touch-rate |")
    emit("|---|---|---|---|")
    for lo, hi in bins:
        sub = [r for r in cal if lo <= r["entry_yes"] < hi]
        if not sub: continue
        me = sum(r["entry_yes"] for r in sub) / len(sub)
        tr = sum(r["touched"] for r in sub) / len(sub)
        emit(f"| [{lo:.2f},{hi:.2f}) | {len(sub)} | {me:.3f} | {tr:.3f} |")
    emit("")
    emit(f"Distinct close-months among calibrated genuine markets: "
         f"{len(set(r['close_month'] for r in cal))} (power is minimal).")
    emit("")

    # ---- TEST 2: fair-value mispricing edge
    emit("## Test 2 - Fair-value mispricing (does FV-entry predict outcome?)\n")
    fvset = [r for r in genuine if r["fv"] is not None and r["entry_yes"] is not None]
    if fvset:
        edges = [(r["fv"] - r["entry_yes"], r["close_month"]) for r in fvset]
        st = clustered_t(edges)
        emit(f"- Mean (FV - entry) across {st['n']} genuine markets: {st['mean']:+.4f} "
             f"(month-clustered t={st['t']:.2f}, {st['clusters']} clusters)")
        # realized touch minus entry (did touch happen more than Kalshi implied?)
        rmp = [(r["touched"] - r["entry_yes"], r["close_month"]) for r in fvset]
        st2 = clustered_t(rmp)
        emit(f"- Mean (realized_touch - entry): {st2['mean']:+.4f} "
             f"(month-clustered t={st2['t']:.2f})  "
             f"[>0 => Kalshi underpriced touch; <0 => overpriced]")
        # realized touch minus FV (was the smart model right?)
        rmf = [(r["touched"] - r["fv"], r["close_month"]) for r in fvset]
        st3 = clustered_t(rmf)
        emit(f"- Mean (realized_touch - FV): {st3['mean']:+.4f} "
             f"(month-clustered t={st3['t']:.2f})  "
             f"[<0 => reflection-FV OVER-predicted touch]")
    emit("")

    # ---- TEST 3: tradeable, market-weighted vs trade-weighted
    emit("## Test 3 - Tradeable PnL: MARKET-weighted vs TRADE-weighted\n")
    emit("Strategy from the hypothesis: when FV > entry (model says touch is "
         "underpriced) we BUY YES(touch); when FV < entry we BUY NO(sell touch). "
         "Simulate being the taker on that side at each real fill on that side, "
         "net of Kalshi taker fee. Settlement: YES pays 1 if touched else 0; "
         "NO pays the complement.\n")

    def market_pnl(r):
        """One PnL/contract per market at the entry VWAP (market-weighted)."""
        if r["fv"] is None or r["entry_yes"] is None: return None, None
        if r["fv"] >= r["entry_yes"]:
            side = "YES"; p = r["entry_yes"]; settle = r["touched"]
        else:
            side = "NO"; p = 1.0 - r["entry_yes"]; settle = 1 - r["touched"]
        return settle - p - kfee(p), side

    def trade_pnl(r):
        """PnL/contract fill-weighted over the REAL taker trades on the chosen
        side, within first-half-of-life (causal entry window)."""
        if r["fv"] is None or r["entry_yes"] is None: return None, 0.0
        buy_yes = r["fv"] >= r["entry_yes"]
        mid = r["open_dt"] + (r["close_dt"] - r["open_dt"]) / 2
        num = 0.0; den = 0.0
        for t in r["trades"]:
            ct = dt(t["created_time"])
            if not (r["open_dt"] <= ct <= mid):
                continue
            # a taker buying YES has taker_side 'yes'; buying NO has 'no'
            tside = t.get("taker_side")
            cnt = float(t["count_fp"])
            if buy_yes and tside == "yes":
                p = float(t["yes_price_dollars"]); settle = r["touched"]
            elif (not buy_yes) and tside == "no":
                p = float(t["no_price_dollars"]); settle = 1 - r["touched"]
            else:
                continue
            pnl = settle - p - kfee(p)
            num += cnt * pnl; den += cnt
        if den == 0: return None, 0.0
        return num / den, den

    mw = []; tw = []
    for r in fvset:
        mp, side = market_pnl(r)
        if mp is not None:
            mw.append((mp, r["close_month"]))
        tp, vol = trade_pnl(r)
        if tp is not None:
            # trade-weighted: each market contributes its fill-weighted PnL,
            # but we also report the volume weights so no single market dominates
            tw.append((tp, r["close_month"], vol))

    if mw:
        st = clustered_t(mw)
        emit(f"- MARKET-weighted PnL/contract: {st['mean']:+.4f} "
             f"(month-clustered t={st['t']:.2f}, n={st['n']}, {st['clusters']} clusters)")
    if tw:
        # equal-across-market mean of fill-weighted PnL
        st_eq = clustered_t([(p, m) for p, m, _ in tw])
        emit(f"- TRADE-weighted PnL/contract (fill-weighted within market, "
             f"equal across markets): {st_eq['mean']:+.4f} "
             f"(month-clustered t={st_eq['t']:.2f}, n={st_eq['n']})")
        # fully volume-weighted (every real contract counts once) -- the honest
        # 'what a taker following the signal actually earned' number
        tot_num = sum(p * v for p, m, v in tw)
        tot_den = sum(v for p, m, v in tw)
        vw_mean = tot_num / tot_den if tot_den else float("nan")
        # cluster-robust t on the fully-volume-weighted mean, clustering by month
        cl = {}
        for p, m, v in tw:
            cl.setdefault(m, []).append((p, v))
        gsum = 0.0
        for m, lst in cl.items():
            gsum += (sum(v * (p - vw_mean) for p, v in lst)) ** 2
        vw_se = math.sqrt(gsum) / tot_den if tot_den else float("nan")
        vw_t = vw_mean / vw_se if vw_se and vw_se > 0 else float("nan")
        emit(f"- TRADE-weighted PnL/contract (ALL real contracts, "
             f"volume-weighted): {vw_mean:+.4f} "
             f"(month-clustered t={vw_t:.2f}, total contracts={tot_den:.0f})")
    emit("")

    # ---- TEST 4: adverse selection
    emit("## Test 4 - Adverse selection (touch-rate: market- vs volume-weighted)\n")
    # over ALL settled markets (genuine + trivial) and over genuine only
    for label, subset in [("genuine only", genuine), ("all settled", rows)]:
        mkt_rate = sum(r["touched"] for r in subset) / len(subset)
        vw_num = sum(r["touched"] * r["volume"] for r in subset)
        vw_den = sum(r["volume"] for r in subset)
        vw_rate = vw_num / vw_den if vw_den else float("nan")
        emit(f"- {label}: market-weighted touch-rate={mkt_rate:.3f}, "
             f"volume-weighted touch-rate={vw_rate:.3f} "
             f"(n={len(subset)})")
    emit("  (volume-weighted >> market-weighted would indicate buyers piling "
         "into soon-to-touch barriers; here compare the two.)")
    emit("")

    # ---- structural caveat + verdict
    per_month = {}
    for r in genuine:
        per_month.setdefault(r["close_month"], []).append(r)
    emit("## Structural caveat (READ BEFORE the verdict)\n")
    for mm in sorted(per_month):
        sub = per_month[mm]
        emit(f"- {mm}: {len(sub)} settled genuine markets, "
             f"{sum(x['touched'] for x in sub)} touched.")
    emit("- July contributes only ONE settled market (the 65000 strike that "
         "touched and closed early); the rest of the July ladder is still "
         "active/unsettled. So the effective sample is TWO full monthly BTC "
         "path draws (May, Jun, both all-NO) + one early-touch July point + "
         "two ETH ladders sharing the same two months. This is ~2-3 correlated "
         "macro draws, NOT 30 independent bets.")
    emit("")
    emit("## VERDICT\n")
    emit("NULL / NEGATIVE for the stated hypothesis, and severely underpowered.\n")
    emit("- Retail did NOT systematically underprice touch. Realized_touch - "
         "entry = -0.067 (t=-2.07): if anything Kalshi's traded price was ABOVE "
         "the realized touch frequency (touch happened LESS than priced).")
    emit("- The driftless reflection 'fair value' OVER-predicted touch badly "
         "(realized - FV = -0.101, t=-3.21). Ignoring drift/mean-reversion, "
         "2*N(...) overstated upside-barrier probability during a falling BTC "
         "market. The 'smart' FV was the LESS accurate of the two.")
    emit("- Trading the FV-vs-price signal LOSES money at every weighting: "
         "market-weighted -0.020/contract, fill-weighted -0.021, "
         "fully volume-weighted -0.047. No market-vs-trade divergence that "
         "hides an edge; trade-weighting makes it WORSE, exactly the adverse-"
         "selection signature (volume-weighted touch-rate 0.115 >> "
         "market-weighted 0.033).")
    emit("- Power: 3 close-months, effectively ~2 independent BTC monthly "
         "paths. All upside barriers in May & June missed simply because BTC "
         "fell. No t-stat here is trustworthy; a 3-month all-NO run is a "
         "path realization, not a harvestable edge.")
    emit("- CONCLUSION: There is NO real, cost-surviving, trade-weighted "
         "one-touch mispricing edge detectable in the liquid monthly Kalshi "
         "crypto barriers. The longer-horizon markets look as efficient (given "
         "sampling noise) as the 15-minute ones. Do not deploy.")
    emit("")

    with open("/home/user/Codex-playground-/kalshi_onetouch_report.md", "w") as f:
        f.write("\n".join(out))
    print("\n[written kalshi_onetouch_report.md]")

if __name__ == "__main__":
    main()
