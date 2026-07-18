#!/usr/bin/env python3
"""
VRP-REGIME: does a VOLATILITY-REGIME signal known at ENTRY separate high-premium
weeks from low/negative ones for the confirmed Polymarket short-vol longshot edge?

Confirmed edge (unconditional): SELL far-OTM weekly "BTC/ETH above $X on <date>"
longshots at YES mid in [0.15,0.30] on zero-fee Polymarket -> +~0.12/ct, week-
clustered t~4.6. Seller PnL/ct (conservative bid fill) = (entry - half_spread) - yes_win.

Hypothesis: the premium is BIGGER when the vol-risk-premium is high (implied DVOL >>
trailing realized vol) and SMALLER/negative when realized vol spikes. If we can flag
high-premium weeks EX-ANTE we size up in them -> Sharpe improvement without more
average risk. Prior NULL (LONGSHOT-CONDITIONAL) found moneyness/demand conditioning
did NOT sharpen per-trade EV, so the bar here is a SHARPE improvement via timing/sizing.

Data (all public, no auth):
  - Realized vol: Binance Vision spot daily klines (BTCUSDT, ETHUSDT).
  - Implied vol : Deribit DVOL index (BTC, ETH), 12h resolution.
  - Funding     : Binance Vision futures fundingRate (BTCUSDT, ETHUSDT).
  - Longshots   : scratchpad/advsel_rows.json (601 settled longshots, 49 weeks,
                  built earlier for the LONGSHOT-CONDITIONAL null; entry in [0.15,0.30]).

No lookahead: every regime feature is observed as-of the market START (= end - horizon),
which is strictly BEFORE the (first-half) entry. Walk-forward: regime thresholds/fits use
PAST weeks only. Week-clustered t throughout. Multiple-testing count reported.
"""
import json, math, io, zipfile, urllib.request, time, datetime as dt, os
from collections import defaultdict

HERE = "/home/user/Codex-playground-"
SCRATCH = f"{HERE}/scratchpad"
CACHE = f"{SCRATCH}/vrp_regime_cache"
os.makedirs(CACHE, exist_ok=True)
ROWS_PATH = f"{SCRATCH}/advsel_rows.json"

# ----------------------------------------------------------------- fetch helpers
def _get(url, tries=4, timeout=90):
    last = None
    for i in range(tries):
        try:
            r = urllib.request.urlopen(url, timeout=timeout)
            return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e; time.sleep(1.2*(i+1))
        except Exception as e:
            last = e; time.sleep(1.2*(i+1))
    raise RuntimeError(f"fetch failed {url}: {last}")

def _cache_json(name, builder):
    p = f"{CACHE}/{name}"
    if os.path.exists(p):
        return json.load(open(p))
    obj = builder()
    json.dump(obj, open(p, "w"))
    return obj

# ----------------------------------------------------------------- realized vol (spot daily)
def spot_daily_closes(sym):
    """Return sorted list of (day_epoch_utc_midnight, close) from Binance Vision spot 1d."""
    def build():
        out = {}
        for (y, m) in _months(2025, 5, 2026, 7):
            mm = f"{y:04d}-{m:02d}"
            url = f"https://data.binance.vision/data/spot/monthly/klines/{sym}/1d/{sym}-1d-{mm}.zip"
            content = _get(url)
            if content is None:
                continue
            z = zipfile.ZipFile(io.BytesIO(content))
            raw = z.read(z.namelist()[0]).decode()
            for line in raw.strip().split("\n"):
                f = line.split(",")
                ot = int(f[0])
                # Binance sometimes emits micro (16-digit) vs milli (13-digit) timestamps
                if ot > 1e15:
                    ot //= 1000  # us -> ms
                sec = ot // 1000
                out[sec] = float(f[4])  # close
        return out
    d = _cache_json(f"spot_{sym}.json", build)
    return sorted((int(k), v) for k, v in d.items())

def _months(y0, m0, y1, m1):
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield (y, m)
        m += 1
        if m > 12:
            m = 1; y += 1

def build_rv_series(sym):
    """Daily RV features. Returns list of dicts sorted by 'close_time' (epoch sec, end of that
    UTC day). Each dict: close_time, rv7, rv30, rv_trend(=rv7-rv30), trend30, drawdown30.
    Annualized vol in PERCENT (to match DVOL units)."""
    closes = spot_daily_closes(sym)          # [(day_open_sec, close)]
    days = [c[0] for c in closes]
    px = [c[1] for c in closes]
    logret = [math.nan]
    for i in range(1, len(px)):
        logret.append(math.log(px[i]/px[i-1]))
    out = []
    ANN = math.sqrt(365.0)
    for i in range(len(px)):
        # close_time = end of day i (day_open + 86400); feature is known AFTER this day closes
        close_time = days[i] + 86400
        def rv(win):
            if i+1 < win+1:  # need `win` returns (returns index 1..i)
                return math.nan
            seg = logret[i-win+1:i+1]
            seg = [r for r in seg if r == r]
            if len(seg) < win:
                return math.nan
            mu = sum(seg)/len(seg)
            var = sum((r-mu)**2 for r in seg)/(len(seg)-1)
            return math.sqrt(var)*ANN*100.0
        rv7 = rv(7); rv30 = rv(30)
        trend30 = (px[i]/px[i-30]-1.0)*100.0 if i >= 30 else math.nan
        if i >= 30:
            hi = max(px[i-30:i+1])
            drawdown30 = (px[i]/hi - 1.0)*100.0
        else:
            drawdown30 = math.nan
        rv_trend = (rv7 - rv30) if (rv7==rv7 and rv30==rv30) else math.nan
        out.append(dict(close_time=close_time, rv7=rv7, rv30=rv30,
                        rv_trend=rv_trend, trend30=trend30, drawdown30=drawdown30))
    return out

# ----------------------------------------------------------------- implied vol (DVOL)
def build_dvol_series(cur):
    """Return sorted list of (ts_sec, dvol_close) for the currency, 12h resolution."""
    def build():
        start = int(dt.datetime(2025,5,1).timestamp()*1000)
        end = int(dt.datetime(2026,7,18).timestamp()*1000)
        url = (f"https://www.deribit.com/api/v2/public/get_volatility_index_data?"
               f"currency={cur}&start_timestamp={start}&end_timestamp={end}&resolution=43200")
        d = json.loads(_get(url))
        return d["result"]["data"]  # [[ts_ms, o,h,l,c], ...]
    data = _cache_json(f"dvol_{cur}.json", build)
    return sorted((int(r[0])//1000, float(r[4])) for r in data)

# ----------------------------------------------------------------- funding
def build_funding_series(sym):
    """Return sorted list of (ts_sec, rate) 8h funding for the perp."""
    def build():
        out = {}
        for (y, m) in _months(2025, 5, 2026, 7):
            mm = f"{y:04d}-{m:02d}"
            url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{mm}.zip"
            content = _get(url)
            if content is None:
                continue
            z = zipfile.ZipFile(io.BytesIO(content))
            raw = z.read(z.namelist()[0]).decode()
            for line in raw.strip().split("\n"):
                f = line.split(",")
                try:
                    ct = int(f[0]); rate = float(f[-1])
                except ValueError:
                    continue  # header
                if ct > 1e15:
                    ct //= 1000
                out[ct//1000] = rate
        return out
    d = _cache_json(f"funding_{sym}.json", build)
    return sorted((int(k), v) for k, v in d.items())

# ----------------------------------------------------------------- asof lookups
def asof(series, t, key_idx=0):
    """Last element of `series` (list of tuples) with element[key_idx] <= t. Binary search."""
    lo, hi, res = 0, len(series)-1, None
    while lo <= hi:
        mid = (lo+hi)//2
        if series[mid][key_idx] <= t:
            res = series[mid]; lo = mid+1
        else:
            hi = mid-1
    return res

def asof_dict(series, t):
    """series: list of dicts with 'close_time'; return last dict with close_time <= t."""
    lo, hi, res = 0, len(series)-1, None
    while lo <= hi:
        mid = (lo+hi)//2
        if series[mid]['close_time'] <= t:
            res = series[mid]; lo = mid+1
        else:
            hi = mid-1
    return res

def trailing_funding(fund, t, win_days=7):
    """Mean funding rate over [t-win, t] (annualized approx * 3*365)."""
    lo = t - win_days*86400
    vals = [r for (ts, r) in fund if lo <= ts <= t]
    if not vals:
        return math.nan
    return sum(vals)/len(vals) * 3*365*100.0  # -> annualized %

# ----------------------------------------------------------------- build feature rows
def week_key(ts):
    iso = dt.datetime.utcfromtimestamp(ts).isocalendar()
    return (iso[0], iso[1])

def seller_pnl(r):
    return (r['entry'] - r['half_spread']) - r['yes_win']

def build_rows():
    rows = json.load(open(ROWS_PATH))
    rv = {'BTC': build_rv_series('BTCUSDT'), 'ETH': build_rv_series('ETHUSDT')}
    dvol = {'BTC': build_dvol_series('BTC'), 'ETH': build_dvol_series('ETH')}
    fund = {'BTC': build_funding_series('BTCUSDT'), 'ETH': build_funding_series('ETHUSDT')}
    out = []
    skipped = 0
    for r in rows:
        a = r['asset']
        entry_time = r['end'] - r['horizon_days']*86400.0   # market start; strictly before entry
        rvf = asof_dict(rv[a], entry_time)
        dv = asof(dvol[a], entry_time)
        if rvf is None or dv is None or rvf['rv7'] != rvf['rv7'] or rvf['rv30'] != rvf['rv30']:
            skipped += 1; continue
        fnd = trailing_funding(fund[a], entry_time)
        d = dict(
            asset=a, wk=week_key(r['end']), end=r['end'], entry_time=entry_time,
            pnl=seller_pnl(r), entry=r['entry'], yes_win=r['yes_win'],
            rv7=rvf['rv7'], rv30=rvf['rv30'], rv_trend=rvf['rv_trend'],
            trend30=rvf['trend30'], drawdown30=rvf['drawdown30'],
            dvol=dv[1],
            vrp7=dv[1]-rvf['rv7'], vrp30=dv[1]-rvf['rv30'],
            funding=fnd,
        )
        out.append(d)
    return out, skipped

# ----------------------------------------------------------------- stats
def cluster_stats(rows):
    """(mean, week-clustered t, n) for equal-weight mean of pnl, clustered by week."""
    if not rows:
        return (math.nan, math.nan, 0)
    n = len(rows)
    beta = sum(r['pnl'] for r in rows)/n
    scores = defaultdict(float)
    for r in rows:
        scores[r['wk']] += (r['pnl'] - beta)
    G = len(scores)
    ss = sum(s*s for s in scores.values())
    var = ss/(n*n)
    if G > 1:
        var *= G/(G-1)
    se = math.sqrt(var) if var > 0 else math.nan
    t = beta/se if (se==se and se>0) else math.nan
    return (beta, t, n)

def diff_cluster_t(hi_rows, lo_rows):
    """Week-clustered t for the difference in mean pnl (hi - lo).
    Pooled OLS of pnl on a HIGH dummy with cluster-robust (by week) SE."""
    rows = [(r, 1.0) for r in hi_rows] + [(r, 0.0) for r in lo_rows]
    n = len(rows)
    if n < 4:
        return (math.nan, math.nan)
    xbar = sum(x for _, x in rows)/n
    ybar = sum(r['pnl'] for r, _ in rows)/n
    sxx = sum((x-xbar)**2 for _, x in rows)
    if sxx <= 0:
        return (math.nan, math.nan)
    beta = sum((x-xbar)*(r['pnl']-ybar) for r, x in rows)/sxx
    alpha = ybar - beta*xbar
    # cluster-robust SE (CR1) by week
    scores = defaultdict(float)
    for r, x in rows:
        resid = r['pnl'] - (alpha + beta*x)
        scores[r['wk']] += (x-xbar)*resid
    G = len(scores)
    meat = sum(s*s for s in scores.values())
    var = meat/(sxx*sxx)
    if G > 1:
        var *= G/(G-1)
    se = math.sqrt(var) if var > 0 else math.nan
    t = beta/se if (se==se and se>0) else math.nan
    return (beta, t)

def tertile_split(rows, key):
    """Split rows into (low, mid, high) terciles by feature `key` (in-sample thresholds)."""
    vals = sorted(r[key] for r in rows if r[key] == r[key])
    if len(vals) < 6:
        return [], [], []
    lo_t = vals[len(vals)//3]; hi_t = vals[2*len(vals)//3]
    lo = [r for r in rows if r[key] == r[key] and r[key] <= lo_t]
    hi = [r for r in rows if r[key] == r[key] and r[key] >= hi_t]
    mid = [r for r in rows if r[key] == r[key] and lo_t < r[key] < hi_t]
    return lo, mid, hi

# ----------------------------------------------------------------- weekly aggregation
def weekly_series(rows):
    """Return dict wk -> {pnl (equal-wt mean/ct that week), n, and mean of each signal}."""
    byw = defaultdict(list)
    for r in rows:
        byw[r['wk']].append(r)
    out = {}
    sig_keys = ['vrp7','vrp30','dvol','rv7','rv30','rv_trend','trend30','drawdown30','funding']
    for wk, rs in byw.items():
        d = dict(pnl=sum(x['pnl'] for x in rs)/len(rs), n=len(rs), end=min(x['end'] for x in rs))
        for k in sig_keys:
            vv = [x[k] for x in rs if x[k]==x[k]]
            d[k] = (sum(vv)/len(vv)) if vv else math.nan
        out[wk] = d
    return out

def sharpe(series):
    xs = [x for x in series if x==x]
    if len(xs) < 3:
        return math.nan
    m = sum(xs)/len(xs)
    v = sum((x-m)**2 for x in xs)/(len(xs)-1)
    sd = math.sqrt(v)
    return (m/sd) if sd > 0 else math.nan

def mean(xs):
    xs=[x for x in xs if x==x]
    return sum(xs)/len(xs) if xs else math.nan
def sd(xs):
    xs=[x for x in xs if x==x]
    if len(xs)<2: return math.nan
    m=sum(xs)/len(xs); return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))

# ================================================================= MAIN
def main():
    rows, skipped = build_rows()
    print(f"feature rows built: {len(rows)}  (skipped {skipped} for missing features)")
    weeks = sorted(set(r['wk'] for r in rows))
    print(f"weeks: {len(weeks)}  ({weeks[0]} .. {weeks[-1]})")

    base = cluster_stats(rows)
    print(f"\nUNCONDITIONAL baseline: mean={base[0]*100:+.2f}c  week-clustered t={base[1]:.2f}  n={base[2]}")

    SIGNALS = ['vrp7','vrp30','dvol','rv7','rv30','rv_trend','trend30','drawdown30','funding']
    # theoretical prior: seller premium LARGER when vrp high, dvol high; SMALLER when rv/rv_trend high
    EXPECT = {'vrp7':'+','vrp30':'+','dvol':'+','rv7':'-','rv30':'-',
              'rv_trend':'-','trend30':'?','drawdown30':'?','funding':'?'}

    report = {'baseline': dict(mean=base[0], t=base[1], n=base[2]),
              'signals': {}, 'walkforward': {}}

    # ---- 1. per-regime (tertile) split, in-sample descriptive + clustered diff ----
    print("\n" + "="*96)
    print("PER-REGIME TERCILE SPLIT (in-sample, descriptive) + week-clustered HIGH-minus-LOW spread")
    print("="*96)
    hdr = f"{'signal':11s} {'exp':3s} | {'LOW tercile':>22s} | {'HIGH tercile':>22s} | {'HIGH-LOW spread':>22s}"
    print(hdr); print("-"*len(hdr))
    for s in SIGNALS:
        lo, mid, hi = tertile_split(rows, s)
        if not lo or not hi:
            continue
        ls = cluster_stats(lo); hs = cluster_stats(hi)
        spread, spread_t = diff_cluster_t(hi, lo)
        print(f"{s:11s} {EXPECT[s]:3s} | "
              f"{ls[0]*100:+6.2f}c t{ls[1]:5.2f} n{ls[2]:4d} | "
              f"{hs[0]*100:+6.2f}c t{hs[1]:5.2f} n{hs[2]:4d} | "
              f"{spread*100:+6.2f}c t{spread_t:5.2f}")
        report['signals'][s] = dict(
            expect=EXPECT[s],
            low=dict(mean=ls[0], t=ls[1], n=ls[2]),
            high=dict(mean=hs[0], t=hs[1], n=hs[2]),
            spread=spread, spread_t=spread_t)

    # ---- 2. WALK-FORWARD sizing rules vs unconditional (Sharpe) --------------------
    ws = weekly_series(rows)
    wk_order = sorted(ws.keys(), key=lambda w: ws[w]['end'])
    WARMUP = 16   # weeks of history before applying any rule (need a stable trailing dist)
    applied = wk_order[WARMUP:]
    print("\n" + "="*96)
    print(f"WALK-FORWARD SIZING (warmup={WARMUP} wk, applied weeks={len(applied)})")
    print("Regime threshold = trailing MEDIAN of the weekly signal over weeks strictly BEFORE t.")
    print("="*96)

    # weekly pnl series over the applied window (this is the UNCONDITIONAL blanket sell)
    unc = [ws[w]['pnl'] for w in applied]
    unc_sharpe = sharpe(unc)
    unc_mean = mean(unc)

    print(f"\nUNCONDITIONAL (applied window): mean/wk={unc_mean*100:+.2f}c  "
          f"sd={sd(unc)*100:.2f}c  weekly-Sharpe={unc_sharpe:.3f}  annualized={unc_sharpe*math.sqrt(52):.2f}")

    wf_results = {}
    RULE_TYPES = ['binary_top','proportional_rank']
    for s in SIGNALS:
        for rule in RULE_TYPES:
            sizes = []
            for i, w in enumerate(applied):
                past = wk_order[:WARMUP+i]  # weeks strictly before w
                hist = [ws[pw][s] for pw in past if ws[pw][s]==ws[pw][s]]
                cur = ws[w][s]
                if len(hist) < 8 or cur != cur:
                    sizes.append(1.0)  # insufficient history -> neutral (blanket)
                    continue
                hist_sorted = sorted(hist)
                med = hist_sorted[len(hist_sorted)//2]
                if rule == 'binary_top':
                    # size 1 if this week's signal on the 'premium-rich' side, else 0
                    rich = (cur >= med) if EXPECT[s] in ('+','?') else (cur <= med)
                    sizes.append(1.0 if rich else 0.0)
                else:  # proportional_rank: size in [0,2] by trailing percentile rank, oriented
                    rank = sum(1 for h in hist if h <= cur)/len(hist)  # 0..1
                    if EXPECT[s] == '-':
                        rank = 1.0 - rank
                    sizes.append(2.0*rank)  # mean ~1 by construction
            # normalize sizes to mean 1 over applied weeks (same average capital)
            msz = mean(sizes)
            if msz is None or msz != msz or msz <= 0:
                continue
            nsz = [x/msz for x in sizes]
            cond = [z*p for z, p in zip(nsz, unc)]
            csh = sharpe(cond); cmn = mean(cond)
            wf_results[(s, rule)] = dict(sharpe=csh, mean=cmn,
                                         n_traded=sum(1 for z in sizes if z>0),
                                         avg_size=msz)

    print(f"\n{'signal':11s} {'rule':16s} | {'cond mean/wk':>13s} | {'cond Sharpe':>11s} | "
          f"{'d Sharpe':>9s} | {'d ann':>7s} | traded")
    print("-"*92)
    # sort by conditional sharpe descending
    for (s, rule), d in sorted(wf_results.items(), key=lambda kv: -(kv[1]['sharpe'] if kv[1]['sharpe']==kv[1]['sharpe'] else -9)):
        dS = d['sharpe'] - unc_sharpe
        print(f"{s:11s} {rule:16s} | {d['mean']*100:+11.2f}c | {d['sharpe']:11.3f} | "
              f"{dS:+9.3f} | {dS*math.sqrt(52):+7.2f} | {d['n_traded']}/{len(applied)}")

    # ---- 2b. SIGN-MINED robustness: best of BOTH orientations, still walk-forward --
    # Granting the adversary the empirically-favored sign (chosen with hindsight),
    # does ANY walk-forward rule beat the unconditional Sharpe? (bulletproofing the null)
    best_of_both = {}
    for s in SIGNALS:
        for rule in RULE_TYPES:
            best_sh = -9.0
            for orient in ('+','-'):
                sizes = []
                for i, w in enumerate(applied):
                    past = wk_order[:WARMUP+i]
                    hist = [ws[pw][s] for pw in past if ws[pw][s]==ws[pw][s]]
                    cur = ws[w][s]
                    if len(hist) < 8 or cur != cur:
                        sizes.append(1.0); continue
                    hist_sorted = sorted(hist); med = hist_sorted[len(hist_sorted)//2]
                    if rule == 'binary_top':
                        rich = (cur >= med) if orient=='+' else (cur <= med)
                        sizes.append(1.0 if rich else 0.0)
                    else:
                        rank = sum(1 for h in hist if h <= cur)/len(hist)
                        if orient=='-': rank = 1.0-rank
                        sizes.append(2.0*rank)
                msz = mean(sizes)
                if not msz or msz!=msz or msz<=0: continue
                nsz=[x/msz for x in sizes]
                sh = sharpe([z*p for z,p in zip(nsz, unc)])
                if sh==sh and sh>best_sh: best_sh=sh
            best_of_both[(s,rule)] = best_sh
    n_beat = sum(1 for v in best_of_both.values() if v > unc_sharpe)
    print("\n" + "-"*96)
    print("SIGN-MINED robustness (best of BOTH orientations per rule, still walk-forward):")
    print(f"  rules where best-of-both-signs Sharpe > unconditional ({unc_sharpe:.3f}): "
          f"{n_beat} / {len(best_of_both)}")
    print(f"  max best-of-both Sharpe across all rules = {max(best_of_both.values()):.3f}")
    report['sign_mined_best_of_both'] = dict(
        n_rules_beating_unconditional=n_beat, n_rules=len(best_of_both),
        max_sharpe=max(best_of_both.values()), unconditional_sharpe=unc_sharpe)

    report['walkforward'] = dict(
        warmup=WARMUP, n_applied=len(applied),
        unconditional=dict(mean=unc_mean, sharpe=unc_sharpe, sharpe_ann=unc_sharpe*math.sqrt(52)),
        rules={f"{s}|{rule}": dict(sharpe=d['sharpe'], mean=d['mean'],
                                   d_sharpe=d['sharpe']-unc_sharpe, n_traded=d['n_traded'])
               for (s, rule), d in wf_results.items()})

    # ---- 3. multiple-testing accounting -------------------------------------------
    n_signals = len(SIGNALS)
    n_perregime_tests = n_signals            # one HIGH-LOW spread test per signal
    n_wf_rules = len(wf_results)             # signal x rule-type
    n_total = n_perregime_tests + n_wf_rules
    report['multiple_testing'] = dict(
        n_signals=n_signals, n_perregime_spread_tests=n_perregime_tests,
        n_walkforward_rules=n_wf_rules, n_total_tests=n_total,
        bonferroni_t_for_0p05=None)
    # two-sided Bonferroni-adjusted t threshold (normal approx) for the family
    import statistics
    # crude: alpha/n, z = Phi^-1(1-alpha/2n)
    def z_for(p):
        # Beasley-Springer/Moro inverse normal (upper tail)
        # use simple bisection on erfc
        from math import erfc, sqrt
        lo, hi = 0.0, 8.0
        for _ in range(100):
            mid = (lo+hi)/2
            if 0.5*erfc(mid/sqrt(2)) > p/2:
                lo = mid
            else:
                hi = mid
        return (lo+hi)/2
    zt = z_for(0.05/n_total)
    report['multiple_testing']['bonferroni_t_for_0p05'] = zt
    print("\n" + "="*96)
    print(f"MULTIPLE TESTING: {n_signals} signals; {n_perregime_tests} per-regime spread tests + "
          f"{n_wf_rules} walk-forward rules = {n_total} tests.")
    print(f"Bonferroni |t| threshold for family-wise 0.05 (normal approx): {zt:.2f}")
    print("="*96)

    # ---- verdict data: best walk-forward rule and whether it clears the bar -------
    best = max(wf_results.items(), key=lambda kv: (kv[1]['sharpe'] if kv[1]['sharpe']==kv[1]['sharpe'] else -9))
    report['best_wf_rule'] = dict(signal=best[0][0], rule=best[0][1],
                                  sharpe=best[1]['sharpe'], d_sharpe=best[1]['sharpe']-unc_sharpe)
    # primary pre-registered signal = vrp7 (implied - realized), binary_top rule
    prim = wf_results.get(('vrp7','binary_top'))
    report['primary_vrp7_binary'] = (dict(sharpe=prim['sharpe'], d_sharpe=prim['sharpe']-unc_sharpe,
                                          n_traded=prim['n_traded']) if prim else None)

    json.dump(report, open(f"{HERE}/vrp_regime_summary.json","w"), indent=2, default=str)
    print(f"\nsaved {HERE}/vrp_regime_summary.json")
    return report

if __name__ == "__main__":
    main()
