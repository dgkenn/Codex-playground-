#!/usr/bin/env python3
"""
kalshi_theta_decay.py
======================
OOS candidate K9: THETA / temporal-decay curve mispricing (idea sourced from
braedonsaunders/homerun's TemporalDecayStrategy, description only -- no source
code available to us, so this is OUR OWN reconstruction and OUR OWN code).

MECHANISM
---------
A binary contract's price should, absent new information, follow a theoretical
"theta" decay path toward whichever side (0 or 1) it currently favors as
resolution approaches -- exactly like an option's extrinsic value bleeding off
as time-to-expiry shrinks. homerun's description: expected_price = initial *
ratio^decay_rate, "a sqrt-time-ish decay". Taken completely literally that
formula only decays toward 0, so we generalize it (symmetrically, in the only
way that is dimensionally sane and matches "toward 0 or 1"):

    r(t)      = (close_time - t) / (close_time - open_time)      remaining life fraction, r in [0,1]
    target    = 1.0 if initial_price >= 0.5 else 0.0             the side the market favors AT ENTRY (causal, fixed once)
    theo(t)   = target + (initial_price - target) * r(t) ** k

  * k = 0.5  -> "sqrt-time" curve (homerun form): convex, most of the decay
               happens LATE (near resolution). This is our best-effort
               reconstruction of "ratio^decay_rate" with decay_rate=0.5.
  * k = 1.0  -> "linear" baseline: theo decays linearly in remaining time.

Both curves use ONLY the first observed candle's price as "initial" (a single
causal anchor fixed at t~open) and calendar time -- NO look-ahead, NO use of
the true resolution value anywhere in curve construction. `target` is which
side the market ALREADY favors at entry, not the true outcome.

SIGNAL: at every later candle t, if actual price deviates from theo(t) by more
than a threshold (5% / 7% / 10% tested), trade TOWARD the curve:
  actual < theo  -> BUY  YES  (bet price reverts UP to the curve)
  actual > theo  -> SELL YES  (economically: BUY NO; bet price reverts DOWN)
Hold for horizon H (in candle-steps: 1, 3, 6) or to RESOLUTION, then close.

FEES: Kalshi fee = ceil_to_cent(0.07*p*(1-p)), min 1c, charged on EVERY taker
trade. Horizon exits are a real closing trade -> fee paid at BOTH entry and
exit (round-trip). Resolution-hold exits are a free settlement -> fee ONLY at
entry. This mirrors orthostack_shock_reversion.py's round_trip_pnl convention.

ANTI-ARTIFACT DISCIPLINE (mirrors the ~21 killed candidates, esp. VRP/timing
which was NULL):
  * NO lookahead: theo(t) is built only from the first candle's price and
    calendar time; target is "which side the market already favors", never
    the true outcome.
  * Per-market NON-OVERLAPPING trade selection: after a signal fires we skip
    the scan pointer past the exit candle before looking for the next signal
    in the SAME market, so trades aren't pseudo-replicated ticks of one path.
  * Day-clustered t (not per-trade) on the trade-level PnL.
  * TRAIN (first 70% by entry date) / TEST (last 30%) split; the *headline*
    config is chosen on TRAIN only and re-evaluated OOS on TEST.
  * Multiple-testing count reported: curves(2) x thresholds(3) x horizons(4) = 24.
  * CRITICAL CHECK: is "deviation from the decay curve" just a relabeled
    moneyness (price-level) or momentum (recent price change) bet -- both of
    which we've already killed elsewhere? We report corr(signal, price level)
    and corr(signal, recent price change) explicitly.

Data: public Kalshi API (no auth). /series?category=... to discover series,
/markets?series_ticker=...&status=settled to get resolved markets + result,
/series/{s}/markets/{t}/candlesticks for the full price path.

Outputs: kalshi_theta_decay_report.md, kalshi_theta_decay_summary.json
Raw candlestick/market cache under scratchpad/theta_raw/ (cheap re-runs).
"""
import os, sys, json, time, math, statistics, datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "scratchpad", "theta_raw")
os.makedirs(RAW, exist_ok=True)

BASE = "https://api.elections.kalshi.com/trade-api/v2"

CATEGORIES = [
    "Economics", "Financials", "Climate and Weather", "Sports",
    "Politics", "Crypto", "Entertainment",
]
MAX_SERIES_PER_CAT = 12       # cap # of series scanned per category
MAX_MKTS_PER_SERIES = 80      # cap settled markets pulled per series (most recent first)
MAX_QUAL_PER_CAT = 220        # cap qualifying (volume+life OK) markets kept per category
MIN_VOLUME = 15.0             # lifetime volume floor (some real trading happened)
MIN_CANDLES = 8               # spec requirement
WORKERS = 20

THRESHOLDS = [0.05, 0.07, 0.10]
HORIZONS = [1, 3, 6, "resolution"]     # candle-steps ahead, or hold to settlement
CURVES = {"sqrt": 0.5, "linear": 1.0}

TRAIN_FRAC = 0.70

_session_lock = {}


def get_json(url, tries=5, timeout=30):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            last = str(e)
            time.sleep(0.5 * (i + 1))
    return {"__err": last}


def parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fee(p):
    """Kalshi taker fee per contract at price p, rounded UP to next cent, min 1c."""
    if p is None:
        return 0.0
    p = max(0.0, min(1.0, p))
    raw = 0.07 * p * (1.0 - p)
    return max(0.01, math.ceil(raw * 100.0 - 1e-9) / 100.0)


# ------------------------------------------------------------------ discovery
def list_series(category):
    out, cursor, pages = [], None, 0
    while pages < 5:
        u = f"{BASE}/series?category={category.replace(' ', '%20')}&limit=200"
        if cursor:
            u += f"&cursor={cursor}"
        d = get_json(u)
        if "__err" in d:
            break
        ss = d.get("series", [])
        out.extend(ss)
        cursor = d.get("cursor")
        pages += 1
        if not cursor or not ss:
            break
    return out


def list_settled(series_ticker, cap):
    out, cursor, pages = [], None, 0
    while pages < 6:
        u = f"{BASE}/markets?series_ticker={series_ticker}&status=settled&limit=1000"
        if cursor:
            u += f"&cursor={cursor}"
        d = get_json(u)
        if "__err" in d:
            break
        ms = d.get("markets", [])
        out.extend(ms)
        cursor = d.get("cursor")
        pages += 1
        if not cursor or not ms or len(out) >= cap:
            break
    return out[:cap]


def qualifies(m):
    if m.get("market_type") != "binary":
        return False
    if m.get("result") not in ("yes", "no"):
        return False
    try:
        vol = float(m.get("volume_fp", "0"))
    except Exception:
        return False
    if vol <= MIN_VOLUME:
        return False
    ot, ct = parse_ts(m.get("open_time")), parse_ts(m.get("close_time"))
    if ot is None or ct is None or ct <= ot:
        return False
    return True


def choose_interval(life_sec):
    if life_sec <= 6 * 3600:
        return 1
    if life_sec <= 21 * 86400:
        return 60
    return 1440


def fetch_candles(series_ticker, ticker, ot, ct, interval):
    fn = os.path.join(RAW, f"cs__{ticker}__{interval}.json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn))
        except Exception:
            pass
    u = (f"{BASE}/series/{series_ticker}/markets/{ticker}/candlesticks"
         f"?start_ts={int(ot.timestamp())}&end_ts={int(ct.timestamp())}&period_interval={interval}")
    d = get_json(u, tries=4)
    cs = d.get("candlesticks", []) if isinstance(d, dict) else []
    out = []
    for cd in cs:
        try:
            yb = cd["yes_bid"].get("close_dollars")
            ya = cd["yes_ask"].get("close_dollars")
            if yb is None or ya is None:
                continue
            yb, ya = float(yb), float(ya)
            if ya < yb:
                yb, ya = ya, yb
            out.append({"ts": int(cd["end_period_ts"]), "bid": yb, "ask": ya,
                        "mid": (yb + ya) / 2.0})
        except Exception:
            continue
    out.sort(key=lambda x: x["ts"])
    try:
        json.dump(out, open(fn, "w"))
    except Exception:
        pass
    return out


def collect_series_markets(cat, s):
    tk = s["ticker"]
    mkts = list_settled(tk, MAX_MKTS_PER_SERIES)
    keep = []
    for m in mkts:
        if not qualifies(m):
            continue
        ot, ct = parse_ts(m["open_time"]), parse_ts(m["close_time"])
        life = (ct - ot).total_seconds()
        interval = choose_interval(life)
        keep.append((cat, tk, m, ot, ct, interval))
    return keep


def build_market_record(cat, series_ticker, m, ot, ct, interval):
    cs = fetch_candles(series_ticker, m["ticker"], ot, ct, interval)
    if len(cs) < MIN_CANDLES:
        return None
    outcome = 1.0 if m["result"] == "yes" else 0.0
    return {
        "cat": cat, "series": series_ticker, "ticker": m["ticker"],
        "open_ts": int(ot.timestamp()), "close_ts": int(ct.timestamp()),
        "outcome": outcome, "candles": cs,
        "close_date": ct.date().isoformat(),
    }


def collect():
    manifest_fn = os.path.join(RAW, "_manifest.json")
    if os.path.exists(manifest_fn):
        print("[collect] manifest cached, loading", flush=True)
        return json.load(open(manifest_fn))

    print("[collect] discovering series per category...", flush=True)
    candidates = []
    for cat in CATEGORIES:
        ss = list_series(cat)
        ss = ss[:MAX_SERIES_PER_CAT]
        print(f"  {cat}: {len(ss)} series scanned", flush=True)
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(collect_series_markets, cat, s): s for s in ss}
            cat_keep = []
            for f in as_completed(futs):
                try:
                    cat_keep.extend(f.result())
                except Exception:
                    pass
        cat_keep.sort(key=lambda x: x[4], reverse=True)  # most recent close_time first
        candidates.extend(cat_keep[:MAX_QUAL_PER_CAT])
        print(f"  {cat}: {min(len(cat_keep), MAX_QUAL_PER_CAT)} qualifying markets kept", flush=True)

    print(f"[collect] {len(candidates)} candidate markets, pulling candlesticks...", flush=True)
    records = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(build_market_record, *c): c for c in candidates}
        for f in as_completed(futs):
            done += 1
            try:
                r = f.result()
            except Exception:
                r = None
            if r is not None:
                records.append(r)
            if done % 100 == 0:
                print(f"  {done}/{len(candidates)} processed, {len(records)} usable", flush=True)

    json.dump(records, open(manifest_fn, "w"))
    print(f"[collect] done: {len(records)} usable markets with >= {MIN_CANDLES} candles", flush=True)
    return records


# ------------------------------------------------------------------ signal / trades
def theo_curve(initial, r, k):
    target = 1.0 if initial >= 0.5 else 0.0
    return target + (initial - target) * (max(0.0, min(1.0, r)) ** k)


def build_trades_for_market(rec, curve_name, k, threshold, horizon):
    """Non-overlapping trade scan for ONE (market, curve, threshold, horizon) config."""
    cs = rec["candles"]
    n = len(cs)
    if n < MIN_CANDLES:
        return []
    ot, ct = rec["open_ts"], rec["close_ts"]
    life = ct - ot
    if life <= 0:
        return []
    initial = cs[0]["mid"]
    trades = []
    i = 1
    prev_mid = cs[0]["mid"]
    while i < n:
        t = cs[i]["ts"]
        r = (ct - t) / life
        if r <= 0 or r >= 1:
            i += 1
            continue
        theo = theo_curve(initial, r, k)
        actual = cs[i]["mid"]
        deviation = actual - theo
        recent_change = actual - prev_mid
        if abs(deviation) > threshold:
            side = "BUY" if deviation < 0 else "SELL"
            if horizon == "resolution":
                exit_fill = rec["outcome"]
                exit_fee = 0.0
                exit_idx = n - 1
            else:
                exit_idx = i + horizon
                if exit_idx >= n:
                    i += 1
                    continue
                exit_c = cs[exit_idx]
                exit_fill = exit_c["bid"] if side == "BUY" else exit_c["ask"]
                exit_fee = fee(exit_fill)
            if side == "BUY":
                entry_fill = cs[i]["ask"]
                pnl = exit_fill - entry_fill - fee(entry_fill) - exit_fee
            else:
                entry_fill = cs[i]["bid"]
                pnl = entry_fill - exit_fill - fee(entry_fill) - exit_fee
            entry_date = dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).date().isoformat()
            trades.append({
                "cat": rec["cat"], "ticker": rec["ticker"], "curve": curve_name,
                "threshold": threshold, "horizon": horizon, "side": side,
                "pnl": pnl, "entry_date": entry_date, "close_date": rec["close_date"],
                "deviation": deviation, "abs_deviation": abs(deviation),
                "price_level": actual, "recent_change": recent_change,
                "theo": theo, "r": r,
            })
            prev_mid = actual
            i = exit_idx + 1
        else:
            prev_mid = actual
            i += 1
    return trades


def cluster_stats(values, clusters):
    n = len(values)
    if n == 0:
        return dict(mean=float("nan"), se=float("nan"), t=float("nan"), n=0, groups=0)
    mean = sum(values) / n
    groups = {}
    for v, c in zip(values, clusters):
        groups.setdefault(c, []).append(v)
    G = len(groups)
    ss = 0.0
    for c, vs in groups.items():
        gsum = sum((v - mean) for v in vs)
        ss += gsum * gsum
    if G > 1:
        var = (G / (G - 1.0)) * ss / (n * n)
        se = math.sqrt(var) if var == var and var >= 0 else float("nan")
        t = mean / se if se and se == se and se > 0 else float("nan")
    else:
        se, t = float("nan"), float("nan")
    return dict(mean=mean, se=se, t=t, n=n, groups=G)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def analyze(records):
    records.sort(key=lambda r: r["close_date"])
    n_train = int(len(records) * TRAIN_FRAC)
    train_recs = records[:n_train]
    test_recs = records[n_train:]
    train_dates = (train_recs[0]["close_date"], train_recs[-1]["close_date"]) if train_recs else (None, None)
    test_dates = (test_recs[0]["close_date"], test_recs[-1]["close_date"]) if test_recs else (None, None)

    configs = [(cn, k, thr, h) for cn, k in CURVES.items() for thr in THRESHOLDS for h in HORIZONS]
    mt_count = len(configs)
    print(f"[analyze] {len(records)} markets ({len(train_recs)} train / {len(test_recs)} test), "
          f"{mt_count} configs (curves x thresholds x horizons)", flush=True)

    def run_config_on(recs, cn, k, thr, h):
        trades = []
        for rec in recs:
            trades.extend(build_trades_for_market(rec, cn, k, thr, h))
        return trades

    train_results = {}
    for cn, k, thr, h in configs:
        trades = run_config_on(train_recs, cn, k, thr, h)
        pnls = [tr["pnl"] for tr in trades]
        clusters = [tr["entry_date"] for tr in trades]
        st = cluster_stats(pnls, clusters)
        train_results[(cn, thr, h)] = dict(trades=trades, stats=st)

    # pick headline config on TRAIN: require n>=30, day-groups>=8, then max day-clustered t
    ranked = []
    for key, res in train_results.items():
        st = res["stats"]
        if st["n"] >= 30 and st["groups"] >= 8 and st["t"] == st["t"]:
            ranked.append((st["t"], key, st))
    ranked.sort(key=lambda x: x[0], reverse=True)

    best_key = ranked[0][1] if ranked else None
    best_train_stats = ranked[0][2] if ranked else None

    # re-evaluate the chosen config OOS on TEST
    test_eval = None
    if best_key is not None:
        cn, thr, h = best_key
        k = CURVES[cn]
        test_trades = run_config_on(test_recs, cn, k, thr, h)
        pnls = [tr["pnl"] for tr in test_trades]
        clusters = [tr["entry_date"] for tr in test_trades]
        test_st = cluster_stats(pnls, clusters)
        test_eval = dict(trades=test_trades, stats=test_st)

    # also run the SAME config over the FULL sample (train+test) for headline reporting
    pooled_eval = None
    if best_key is not None:
        cn, thr, h = best_key
        k = CURVES[cn]
        pooled_trades = run_config_on(records, cn, k, thr, h)
        pnls = [tr["pnl"] for tr in pooled_trades]
        clusters = [tr["entry_date"] for tr in pooled_trades]
        pooled_st = cluster_stats(pnls, clusters)
        pooled_eval = dict(trades=pooled_trades, stats=pooled_st)

    # worst period (worst day-mean) on pooled trades of headline config
    worst_period = None
    if pooled_eval and pooled_eval["trades"]:
        by_day = {}
        for tr in pooled_eval["trades"]:
            by_day.setdefault(tr["entry_date"], []).append(tr["pnl"])
        day_means = {d: sum(v) / len(v) for d, v in by_day.items()}
        wd = min(day_means, key=day_means.get)
        worst_period = (wd, day_means[wd], len(by_day[wd]))

    # win rate + calibration on pooled headline trades
    winrate = None
    if pooled_eval and pooled_eval["trades"]:
        wins = sum(1 for tr in pooled_eval["trades"] if tr["pnl"] > 0)
        winrate = wins / len(pooled_eval["trades"])

    # ---- CRITICAL: novelty check -- correlate the RAW SIGNAL (deviation) with
    # price level and recent price change, using ALL candle-level observations
    # (not just ones that cleared a threshold) from a representative curve (sqrt),
    # so the correlation isn't itself gated by the very threshold we're testing.
    sig_price, sig_change, sig_abs_dev = [], [], []
    for rec in records:
        cs = rec["candles"]
        n = len(cs)
        if n < MIN_CANDLES:
            continue
        ot, ct = rec["open_ts"], rec["close_ts"]
        life = ct - ot
        if life <= 0:
            continue
        initial = cs[0]["mid"]
        prev_mid = cs[0]["mid"]
        for i in range(1, n):
            t = cs[i]["ts"]
            r = (ct - t) / life
            if r <= 0 or r >= 1:
                continue
            theo = theo_curve(initial, r, 0.5)
            actual = cs[i]["mid"]
            dev = actual - theo
            sig_price.append(actual)
            sig_change.append(actual - prev_mid)
            sig_abs_dev.append(abs(dev))
            prev_mid = actual

    corr_dev_price = pearson(sig_abs_dev, sig_price)
    corr_dev_momentum = pearson(sig_abs_dev, sig_change)
    # also signed deviation vs signed momentum (is a big recent up-move -> mechanically
    # "actual pulls above curve", i.e. deviation is literally decomposable from momentum?)
    sig_dev_signed = []
    idx = 0
    for rec in records:
        cs = rec["candles"]
        n = len(cs)
        if n < MIN_CANDLES:
            continue
        ot, ct = rec["open_ts"], rec["close_ts"]
        life = ct - ot
        if life <= 0:
            continue
        initial = cs[0]["mid"]
        for i in range(1, n):
            t = cs[i]["ts"]
            r = (ct - t) / life
            if r <= 0 or r >= 1:
                continue
            theo = theo_curve(initial, r, 0.5)
            actual = cs[i]["mid"]
            sig_dev_signed.append(actual - theo)
    corr_dev_signed_momentum = pearson(sig_dev_signed, sig_change) if len(sig_dev_signed) == len(sig_change) else float("nan")

    # per-category breakdown of the headline config (pooled)
    cat_break = {}
    if pooled_eval:
        by_cat = {}
        for tr in pooled_eval["trades"]:
            by_cat.setdefault(tr["cat"], []).append(tr)
        for cat, trs in by_cat.items():
            pnls = [t["pnl"] for t in trs]
            clusters = [t["entry_date"] for t in trs]
            st = cluster_stats(pnls, clusters)
            cat_break[cat] = dict(n=st["n"], groups=st["groups"], mean=st["mean"], t=st["t"])

    return dict(
        n_markets=len(records), n_train=len(train_recs), n_test=len(test_recs),
        train_date_range=train_dates, test_date_range=test_dates,
        mt_count=mt_count, configs_tested=len(configs),
        best_key=best_key, best_train_stats=best_train_stats,
        test_eval=test_eval, pooled_eval=pooled_eval,
        worst_period=worst_period, winrate=winrate,
        corr_dev_price=corr_dev_price, corr_dev_momentum=corr_dev_momentum,
        corr_dev_signed_momentum=corr_dev_signed_momentum,
        n_signal_obs=len(sig_price),
        cat_break=cat_break,
        train_results=train_results,
        top5_train=ranked[:5],
    )


# ------------------------------------------------------------------ report
def fmt_key(key):
    if key is None:
        return "n/a"
    cn, thr, h = key
    hstr = "resolution" if h == "resolution" else f"{h} candle-steps"
    return f"curve={cn}, threshold={thr*100:.0f}%, horizon={hstr}"


def write_report(res):
    fn = os.path.join(HERE, "kalshi_theta_decay_report.md")
    lines = []
    w = lines.append
    w("# K9: Kalshi THETA / temporal-decay curve mispricing\n")
    w(f"_generated {dt.datetime.now(dt.timezone.utc).isoformat()}_\n")

    best_key = res["best_key"]
    pooled = res["pooled_eval"]
    test_eval = res["test_eval"]
    train_st = res["best_train_stats"]

    verdict_real = False
    if best_key is not None and test_eval is not None:
        tst = test_eval["stats"]
        pst = pooled["stats"]
        verdict_real = (
            tst["n"] >= 20 and tst["mean"] == tst["mean"] and tst["mean"] > 0
            and tst["t"] == tst["t"] and tst["t"] >= 2.0
            and pst["mean"] > 0 and pst["t"] >= 2.0
        )

    w("## VERDICT (blunt)\n")
    if verdict_real:
        w("**Signal present net of fees in this sample -- but treat with caution "
          "given the multiple-testing count below; see novelty check before trusting it.**\n")
    else:
        w("**NULL / PRICED.** No curve x threshold x horizon configuration produces a "
          "fee-surviving, day-clustered-significant edge that replicates out-of-sample. "
          "This is consistent with the program's prior: Kalshi is efficiently priced "
          "against naive path-shape signals, mirroring the VRP/timing NULL.\n")

    w(f"\n- Markets used: **{res['n_markets']}** settled Kalshi markets across "
      f"{len(CATEGORIES)} categories ({', '.join(CATEGORIES)}), TRAIN={res['n_train']} "
      f"(close {res['train_date_range'][0]}..{res['train_date_range'][1]}), "
      f"TEST={res['n_test']} (close {res['test_date_range'][0]}..{res['test_date_range'][1]}).")
    w(f"- Multiple-testing count: **{res['mt_count']}** configs "
      f"(curves={len(CURVES)} x thresholds={len(THRESHOLDS)} x horizons={len(HORIZONS)}). "
      f"Headline config selected by MAX day-clustered t on TRAIN ONLY, "
      f"then re-evaluated on held-out TEST -- the number below is what survives that filter, "
      f"not a cherry-pick over the full sample.")
    w(f"- Headline config (TRAIN-selected): **{fmt_key(best_key)}**")
    if train_st:
        w(f"  - TRAIN: n={train_st['n']}, day-groups={train_st['groups']}, "
          f"mean net PnL/ct={train_st['mean']:+.4f}, day-clustered t={train_st['t']:+.2f}")
    if test_eval:
        tst = test_eval["stats"]
        w(f"  - TEST (OOS): n={tst['n']}, day-groups={tst['groups']}, "
          f"mean net PnL/ct={tst['mean']:+.4f}, day-clustered t={tst['t']:+.2f}")
    if pooled:
        pst = pooled["stats"]
        w(f"  - POOLED (train+test, same config): n={pst['n']}, day-groups={pst['groups']}, "
          f"mean net PnL/ct={pst['mean']:+.4f}, day-clustered t={pst['t']:+.2f}, "
          f"win rate={res['winrate']*100:.1f}%" if res['winrate'] is not None else "")
    if res["worst_period"]:
        wd, wm, wc = res["worst_period"]
        w(f"  - Worst single day (pooled headline config): {wd}, mean {wm:+.4f}/ct over {wc} trades")

    w("\n## Novelty check: is this just relabeled moneyness/momentum? (CRITICAL)\n")
    w(f"- corr(|deviation from theoretical curve|, price level): **{res['corr_dev_price']:+.3f}**")
    w(f"- corr(|deviation from theoretical curve|, recent price change [momentum]): **{res['corr_dev_momentum']:+.3f}**")
    w(f"- corr(SIGNED deviation, SIGNED recent price change): **{res['corr_dev_signed_momentum']:+.3f}**")
    w(f"- computed over {res['n_signal_obs']} candle-level observations (sqrt curve, all markets, no threshold gate).")
    w("\nInterpretation: |corr| >= 0.3 with price level means the 'decay deviation' is largely just "
      "moneyness (how far from 0.5) in disguise -- the exact structure already killed under favorite-longshot/"
      "calibration work. |corr| >= 0.3 with recent price change (especially the SIGNED version) means the "
      "'reversion to curve' bet is largely a same-direction restatement of a momentum/mean-reversion signal "
      "already tested elsewhere (a sign-flip of momentum is exactly what the reversion trade would look like "
      "if the curve is doing no real path-specific work).\n")

    w("\n## Per-category breakdown (headline config, pooled)\n")
    if res["cat_break"]:
        w("| category | n | day-groups | mean net PnL/ct | day-clustered t |")
        w("|---|--:|--:|--:|--:|")
        for cat, d in sorted(res["cat_break"].items(), key=lambda kv: -kv[1]["n"]):
            w(f"| {cat} | {d['n']} | {d['groups']} | {d['mean']:+.4f} | "
              f"{d['t']:+.2f}" if d['t'] == d['t'] else f"| {cat} | {d['n']} | {d['groups']} | {d['mean']:+.4f} | n/a |")
    else:
        w("_no trades in headline config._")

    w("\n## Top 5 configs by TRAIN day-clustered t (for transparency on the search)\n")
    w("| curve | threshold | horizon | n | day-groups | mean net PnL/ct | day-clustered t |")
    w("|---|--:|--:|--:|--:|--:|--:|")
    for t, key, st in res["top5_train"]:
        cn, thr, h = key
        hstr = "resolution" if h == "resolution" else f"{h} steps"
        w(f"| {cn} | {thr*100:.0f}% | {hstr} | {st['n']} | {st['groups']} | {st['mean']:+.4f} | {st['t']:+.2f} |")

    w("\n## Method notes\n")
    w("- Theoretical curve: `theo(t) = target + (initial - target) * r(t)**k`, r=remaining life "
      "fraction, target=nearest boundary (0/1) to the FIRST observed candle's mid (fixed once, causal), "
      "k=0.5 (homerun sqrt-time reconstruction) or k=1.0 (linear baseline). No use of the true resolution "
      "value anywhere in curve construction.")
    w("- Fee: ceil_to_cent(0.07*p*(1-p)), min 1c, charged on EVERY taker trade -- horizon exits pay "
      "entry+exit fee (real round-trip close); resolution-hold exits pay entry fee only (free settlement).")
    w("- Trades are NON-OVERLAPPING per market: after a signal fires, the scan pointer advances past "
      "the trade's exit candle before the next signal in that market is considered.")
    w("- Day-clustered t on trade-level net PnL (entry calendar date = cluster key), not per-trade t.")
    w(f"- Volume floor {MIN_VOLUME}, min candles {MIN_CANDLES}, TRAIN/TEST split {TRAIN_FRAC:.0%}/{1-TRAIN_FRAC:.0%} by close date.")
    w("- Data: public Kalshi API, no auth, read-only.")

    open(fn, "w").write("\n".join(lines) + "\n")
    print(f"[report] wrote {fn}", flush=True)
    return fn


def write_summary(res):
    fn = os.path.join(HERE, "kalshi_theta_decay_summary.json")

    def sanitize(o):
        if isinstance(o, dict):
            return {str(k): sanitize(v) for k, v in o.items()}
        if isinstance(o, list) or isinstance(o, tuple):
            return [sanitize(v) for v in o]
        if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
            return None
        return o

    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_markets": res["n_markets"], "n_train": res["n_train"], "n_test": res["n_test"],
        "train_date_range": res["train_date_range"], "test_date_range": res["test_date_range"],
        "categories": CATEGORIES,
        "mt_count": res["mt_count"], "curves": list(CURVES.keys()),
        "thresholds": THRESHOLDS,
        "horizons": [h if h == "resolution" else h for h in HORIZONS],
        "fee_model": "ceil_to_cent(0.07*p*(1-p)), entry always, exit only on horizon close (not resolution)",
        "headline_config": None if res["best_key"] is None else {
            "curve": res["best_key"][0], "threshold": res["best_key"][1], "horizon": res["best_key"][2],
        },
        "train_stats": res["best_train_stats"],
        "test_stats": res["test_eval"]["stats"] if res["test_eval"] else None,
        "pooled_stats": res["pooled_eval"]["stats"] if res["pooled_eval"] else None,
        "win_rate_pooled": res["winrate"],
        "worst_period": res["worst_period"],
        "novelty_check": {
            "corr_abs_deviation_vs_price_level": res["corr_dev_price"],
            "corr_abs_deviation_vs_recent_change": res["corr_dev_momentum"],
            "corr_signed_deviation_vs_signed_recent_change": res["corr_dev_signed_momentum"],
            "n_signal_obs": res["n_signal_obs"],
        },
        "category_breakdown": res["cat_break"],
        "top5_train_configs": [
            {"t": t, "curve": key[0], "threshold": key[1], "horizon": key[2], "stats": st}
            for t, key, st in res["top5_train"]
        ],
    }
    json.dump(sanitize(out), open(fn, "w"), indent=2)
    print(f"[summary] wrote {fn}", flush=True)
    return fn


def main():
    t0 = time.time()
    records = collect()
    if len(records) < 30:
        print(f"[FATAL] only {len(records)} usable markets, aborting", flush=True)
        sys.exit(1)
    res = analyze(records)
    write_report(res)
    write_summary(res)
    print(f"[done] {time.time()-t0:.0f}s total", flush=True)


if __name__ == "__main__":
    main()
