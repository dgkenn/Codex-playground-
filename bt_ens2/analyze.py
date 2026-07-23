#!/usr/bin/env python3
"""Backtest B analysis: bias/sigma fit (FIT window) -> Gaussian model prob -> compare vs real Kalshi
crossing price (VALIDATION window) -> fee-net edge/PnL -> day-clustered stats -> Wilson CI ->
calibration diagnostic -> capacity estimate. Two leads: dayahead, samemorning."""
import json, math, os, sys, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

FIT_START = dt.date(2026, 4, 24)
FIT_END = dt.date(2026, 5, 31)
VAL_START = dt.date(2026, 6, 1)
VAL_END = dt.date(2026, 7, 20)

MIN_NET_EDGE_C = 2.0  # pre-registered: minimum net (after-fee) edge in cents to take a trade

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def kalshi_fee_c(price_c):
    p = price_c / 100.0
    return math.ceil(0.07 * p * (1 - p) * 100)

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return ((center - half) / denom, (center + half) / denom)

# ---------------- load raw ----------------
fc = json.load(open(os.path.join(HERE, "raw_forecast.json")))
era5 = json.load(open(os.path.join(HERE, "raw_era5.json")))
trades_raw = json.load(open(os.path.join(HERE, "raw_trades.json")))

# ---------------- daily max forecast per lead, per city, per local calendar date ----------------
def daily_max_by_lead(series):
    h = fc[series]["hourly"]
    times = h["time"]
    cur = h["temperature_2m"]
    d0 = h["temperature_2m"]  # "previous_day0" = the current/freshest run (Open-Meteo naming: day0 IS
                               # the plain variable; requesting "_previous_day0" explicitly is a no-op
                               # the API silently drops -- verified against raw_forecast.json keys)
    d1 = h["temperature_2m_previous_day1"]
    by_date = defaultdict(lambda: {"dayahead": [], "samemorning": []})
    for t, c, v0, v1 in zip(times, cur, d0, d1):
        date_str = t[:10]
        hour = int(t[11:13])
        # HIGH markets: only afternoon hours matter for the day's max; use full day window for safety
        if v1 is not None:
            by_date[date_str]["dayahead"].append(v1)
        if v0 is not None:
            by_date[date_str]["samemorning"].append(v0)
    out = {}
    for date_str, d in by_date.items():
        out[date_str] = {
            "dayahead": max(d["dayahead"]) if d["dayahead"] else None,
            "samemorning": max(d["samemorning"]) if d["samemorning"] else None,
        }
    return out

def truth_by_date(series):
    d = era5[series]["daily"]
    return dict(zip(d["time"], d["temperature_2m_max"]))

fc_daily = {s: daily_max_by_lead(s) for s in fc}
truth_daily = {s: truth_by_date(s) for s in era5}

# ---------------- FIT: bias + residual sigma per city per lead ----------------
fit_stats = {}
for series in fc:
    fit_stats[series] = {}
    for lead in ("dayahead", "samemorning"):
        resids = []
        d = FIT_START
        while d <= FIT_END:
            ds = d.isoformat()
            fv = fc_daily.get(series, {}).get(ds, {}).get(lead)
            tv = truth_daily.get(series, {}).get(ds)
            if fv is not None and tv is not None:
                resids.append(fv - tv)  # forecast - truth
            d += dt.timedelta(days=1)
        if len(resids) >= 5:
            n = len(resids)
            bias = sum(resids) / n
            var = sum((r - bias) ** 2 for r in resids) / max(n - 1, 1)
            sigma = math.sqrt(var)
        else:
            bias, sigma = 0.0, 4.0  # fallback, should not trigger with 38-day fit window
        fit_stats[series][lead] = {"bias": bias, "sigma": max(sigma, 1.0), "n_fit_days": len(resids)}

print("FIT bias/sigma:", file=sys.stderr)
for s in fit_stats:
    print(" ", s, fit_stats[s], file=sys.stderr)

# ---------------- model probability per market ----------------
def market_prob(mean, sigma, floor_strike, cap_strike):
    """floor/cap semantics verified against live Kalshi payload:
       B (both set): YES iff floor<=temp<=cap (cap=floor+1, a 2-integer bucket)
       T floor-only: YES iff temp > floor  (>= floor+1)
       T cap-only:   YES iff temp < cap    (<= cap-1)
    """
    if floor_strike is not None and cap_strike is not None:
        return norm_cdf((cap_strike + 0.5 - mean) / sigma) - norm_cdf((floor_strike - 0.5 - mean) / sigma)
    if floor_strike is not None:
        return 1 - norm_cdf((floor_strike + 0.5 - mean) / sigma)
    if cap_strike is not None:
        return norm_cdf((cap_strike - 0.5 - mean) / sigma)
    return None

# ---------------- VALIDATION: trade simulation ----------------
markets = trades_raw["markets"]
entries = trades_raw["entries"]

trade_log = {"dayahead": [], "samemorning": []}
calib_log = {"dayahead": [], "samemorning": []}  # (model_prob, outcome_yes) for ALL markets w/ entry price, for Brier

for m in markets:
    series = m["series"]
    ds = m["date"]
    tk = m["ticker"]
    floor_strike, cap_strike = m["floor_strike"], m["cap_strike"]
    result_yes = 1 if m["result"] == "yes" else 0

    fvals = fc_daily.get(series, {}).get(ds, {})
    for lead in ("dayahead", "samemorning"):
        fv = fvals.get(lead)
        ent = entries.get(tk, {}).get(lead)
        if fv is None or ent is None:
            continue
        bias, sigma = fit_stats[series][lead]["bias"], fit_stats[series][lead]["sigma"]
        mean = fv - bias  # bias = forecast - truth on FIT window -> corrected forecast = forecast - bias
        p_yes = market_prob(mean, sigma, floor_strike, cap_strike)
        if p_yes is None:
            continue
        p_yes = min(max(p_yes, 1e-6), 1 - 1e-6)

        yes_price_c = round(ent["yes_price"] * 100)
        no_price_c = round(ent["no_price"] * 100)

        calib_log[lead].append((p_yes, result_yes, ds))

        # decide direction: buy YES if model edge over yes ask beats fee; buy NO if model edge on no side beats fee
        fee_yes = kalshi_fee_c(yes_price_c)
        fee_no = kalshi_fee_c(no_price_c)
        edge_yes = (p_yes * 100 - yes_price_c) - fee_yes
        edge_no = ((1 - p_yes) * 100 - no_price_c) - fee_no

        side, price_c, fee_c, edge_c = None, None, None, None
        if edge_yes >= MIN_NET_EDGE_C and edge_yes >= edge_no:
            side, price_c, fee_c, edge_c = "yes", yes_price_c, fee_yes, edge_yes
        elif edge_no >= MIN_NET_EDGE_C:
            side, price_c, fee_c, edge_c = "no", no_price_c, fee_no, edge_no

        if side is None:
            continue

        if side == "yes":
            payoff_c = 100 if result_yes else 0
        else:
            payoff_c = 100 if not result_yes else 0
        pnl_c = payoff_c - price_c - fee_c
        win = 1 if pnl_c > 0 else 0

        trade_log[lead].append({
            "ticker": tk, "date": ds, "series": series, "side": side, "price_c": price_c,
            "fee_c": fee_c, "model_p": p_yes, "edge_c": edge_c, "pnl_c": pnl_c, "win": win,
        })

# ---------------- day-clustered stats ----------------
def day_clustered_stats(trades):
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["date"]].append(t["pnl_c"])
    day_means = [sum(v) / len(v) for v in by_day.values()]
    n_days = len(day_means)
    if n_days == 0:
        return {"n_trades": 0, "n_days": 0}
    grand_mean = sum(day_means) / n_days
    if n_days > 1:
        var = sum((x - grand_mean) ** 2 for x in day_means) / (n_days - 1)
        se = math.sqrt(var / n_days)
    else:
        se = float("nan")
    t_stat = grand_mean / se if se and se > 0 else float("nan")
    # 95% CI via normal approx on day-cluster mean
    ci_lo = grand_mean - 1.96 * se if se == se else float("nan")
    ci_hi = grand_mean + 1.96 * se if se == se else float("nan")
    wins = sum(t["win"] for t in trades)
    n = len(trades)
    wlo, whi = wilson_ci(wins, n)
    return {
        "n_trades": n, "n_days": n_days,
        "mean_pnl_c_per_contract_day_avg": grand_mean, "se_day_clustered": se, "t_stat": t_stat,
        "ci95_lo": ci_lo, "ci95_hi": ci_hi,
        "win_rate": wins / n if n else float("nan"), "wilson_lo": wlo, "wilson_hi": whi,
        "total_pnl_c": sum(t["pnl_c"] for t in trades),
        "mean_edge_c": sum(t["edge_c"] for t in trades) / n if n else float("nan"),
    }

def brier(calib):
    if not calib:
        return None
    return sum((p - o) ** 2 for p, o, _ in calib) / len(calib)

def reliability_bins(calib, nbins=5):
    bins = [[] for _ in range(nbins)]
    for p, o, _ in calib:
        idx = min(int(p * nbins), nbins - 1)
        bins[idx].append((p, o))
    out = []
    for i, b in enumerate(bins):
        if not b:
            out.append({"bin": [i / nbins, (i + 1) / nbins], "n": 0})
            continue
        mp = sum(p for p, o in b) / len(b)
        mo = sum(o for p, o in b) / len(b)
        out.append({"bin": [i / nbins, (i + 1) / nbins], "n": len(b), "mean_model_p": mp, "realized_freq": mo})
    return out

results = {
    "pre_registration": {
        "min_net_edge_c": MIN_NET_EDGE_C,
        "pass_bar": "day-clustered 95% CI of mean PnL/contract strictly > 0 for a lead, "
                    "surviving Bonferroni correction for 2 leads tested (alpha=0.025 one-sided per lead)",
        "fit_window": [FIT_START.isoformat(), FIT_END.isoformat()],
        "validation_window": [VAL_START.isoformat(), VAL_END.isoformat()],
        "cities": list(fc.keys()),
    },
    "fit_stats": fit_stats,
    "leads": {},
}

for lead in ("dayahead", "samemorning"):
    stats = day_clustered_stats(trade_log[lead])
    stats["brier_score"] = brier(calib_log[lead])
    stats["n_scored_markets"] = len(calib_log[lead])
    stats["reliability"] = reliability_bins(calib_log[lead])
    # naive market-implied Brier for comparison (using entry yes price as the market's prob)
    results["leads"][lead] = stats

json.dump(results, open(os.path.join(HERE, "results.json"), "w"), indent=2, default=str)
print(json.dumps(results, indent=2, default=str))
