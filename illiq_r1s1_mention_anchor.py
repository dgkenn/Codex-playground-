#!/usr/bin/env python3
"""
Spec 1 (pre-registered): MENTION-OPEN BASE-RATE ANCHOR
Series: KXFEDMENTION, KXHANNITYMENTION
Data: real Kalshi public API pulls, cached under ./cache (deleted after run).

Entry: at first trade print of each finalized market, compute expanding-window
same-series base rate p_hat (fraction of prior same-series settled markets that
resolved YES, using only markets settled strictly before the entry timestamp).
If |first_print - p_hat| > theta (theta in {10,15,20} cents, selected on FIT set
only), take the side toward p_hat at the observed print price (taker).
Exit: hold to settlement.
EV/contract = (win ? 1-p : -p) - ceil(7*p*(1-p))/100   [p = price paid, 0-1 dollars]

Fit/validation: chronological by event, first 40% of events = fit (floor),
remainder = validation.

Adverse-selection check (mandatory): compare realized YES-rate of signal-fired
markets vs non-fired same-series markets in matched entry-price buckets.

Multiple comparisons: funnel-wide Bonferroni x10 fixed pre-registration-wide.
"""
import json, os, math
from datetime import datetime, timezone
from collections import defaultdict

CACHE = "/tmp/claude-0/-home-user-Codex-playground-/a1344cbd-0d6d-5d88-b275-43c6164c3448/scratchpad/illiq/bt1/cache"
OUTDIR = "/tmp/claude-0/-home-user-Codex-playground-/a1344cbd-0d6d-5d88-b275-43c6164c3448/scratchpad/illiq/bt1"

THETAS_CENTS = [10, 15, 20]
BONFERRONI_M = 10          # funnel-wide budget, fixed pre-registration
ALPHA = 0.05
MIN_VALIDATION_N = 30
MIN_VALIDATION_EVENT_DAYS = 8

def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def fee_dollars(p):
    # Kalshi taker fee: ceil(7*p*(1-p)) cents, converted to dollars, per contract
    return math.ceil(7.0 * p * (1.0 - p)) / 100.0

def wilson_ci(k, n, z=1.959963985):
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z*z/n
    center = phat + z*z/(2*n)
    half = z * math.sqrt((phat*(1-phat) + z*z/(4*n)) / n)
    lo = (center - half) / denom
    hi = (center + half) / denom
    return (lo, hi)

def clustered_ttest_onesided(values_by_cluster):
    """
    Day/event-clustered one-sided t-test, H1: mean > 0.
    Cluster means -> one-sample t-test on cluster-mean vector.
    """
    cluster_means = [sum(v)/len(v) for v in values_by_cluster.values() if len(v) > 0]
    n = len(cluster_means)
    if n < 2:
        return {"n_clusters": n, "t_stat": float("nan"), "p_one_sided": float("nan"),
                "mean": (cluster_means[0] if n == 1 else float("nan"))}
    mean = sum(cluster_means) / n
    var = sum((x-mean)**2 for x in cluster_means) / (n-1)
    se = math.sqrt(var / n) if var > 0 else 0.0
    if se == 0:
        t_stat = float("inf") if mean > 0 else (float("-inf") if mean < 0 else 0.0)
    else:
        t_stat = mean / se
    # one-sided p via Student t survival function using regularized incomplete beta
    p_one_sided = student_t_sf(t_stat, n-1)
    return {"n_clusters": n, "t_stat": t_stat, "p_one_sided": p_one_sided, "mean": mean}

def student_t_sf(t, df):
    if math.isinf(t):
        return 0.0 if t > 0 else 1.0
    if df <= 0:
        return float("nan")
    x = df / (df + t*t)
    ib = incomplete_beta(x, df/2.0, 0.5)
    if t > 0:
        return 0.5 * ib
    else:
        return 1.0 - 0.5 * ib

def incomplete_beta(x, a, b):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a*math.log(x) + b*math.log(1-x))
    if x < (a+1)/(a+b+2):
        return front * betacf(x, a, b) / a
    else:
        return 1.0 - front * betacf(1-x, b, a) / b

def betacf(x, a, b):
    MAXIT, EPS, FPMIN = 200, 3e-14, 1e-300
    qab, qap, qam = a+b, a+1, a-1
    c = 1.0
    d = 1.0 - qab*x/qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0/d
    h = d
    for m in range(1, MAXIT+1):
        m2 = 2*m
        aa = m*(b-m)*x/((qam+m2)*(a+m2))
        d = 1.0 + aa*d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa/c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0/d
        h *= d*c
        aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d = 1.0 + aa*d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa/c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0/d
        delv = d*c
        h *= delv
        if abs(delv-1.0) < EPS:
            break
    return h

# ---------- Load markets ----------
fed = json.load(open(f"{CACHE}/KXFEDMENTION_markets_byevent.json"))
han = json.load(open(f"{CACHE}/KXHANNITYMENTION_markets_byevent.json"))
fed_fin = [m for m in fed if m.get("status") == "finalized"]
han_fin = [m for m in han if m.get("status") == "finalized"]

markets = []
for series, lst in [("KXFEDMENTION", fed_fin), ("KXHANNITYMENTION", han_fin)]:
    for m in lst:
        tkr = m["ticker"]
        tpath = f"{CACHE}/trades_{tkr}.json"
        trades = json.load(open(tpath))
        if not trades:
            continue  # no trades ever printed -> can't establish first print, exclude
        trades_sorted = sorted(trades, key=lambda t: parse_ts(t["created_time"]))
        first = trades_sorted[0]
        first_print = float(first["yes_price_dollars"])
        first_ts = parse_ts(first["created_time"])
        settlement_ts = parse_ts(m["settlement_ts"]) if m.get("settlement_ts") else parse_ts(m["close_time"])
        result_yes = 1 if m.get("result") == "yes" else 0
        markets.append({
            "series": series,
            "event_ticker": m["event_ticker"],
            "ticker": tkr,
            "first_print": first_print,
            "first_ts": first_ts,
            "settlement_ts": settlement_ts,
            "result_yes": result_yes,
            "n_trades": len(trades),
        })

print(f"Loaded {len(markets)} finalized markets with >=1 trade "
      f"(FED {sum(1 for x in markets if x['series']=='KXFEDMENTION')}, "
      f"HAN {sum(1 for x in markets if x['series']=='KXHANNITYMENTION')})")

# ---------- Event chronology / fit-validation split ----------
event_date = {}
for m in markets:
    et = m["event_ticker"]
    event_date[et] = min(event_date.get(et, m["settlement_ts"]), m["settlement_ts"])

events_sorted = sorted(event_date.keys(), key=lambda e: event_date[e])
n_events = len(events_sorted)
n_fit_events = max(1, math.floor(0.4 * n_events)) if n_events > 0 else 0
fit_events = set(events_sorted[:n_fit_events])
val_events = set(events_sorted[n_fit_events:])

print(f"Events chronological: {events_sorted}")
print(f"n_events={n_events}  fit_events={fit_events}  val_events={val_events}")

# ---------- Expanding-window per-series base rate at each entry ----------
by_series = defaultdict(list)
for m in markets:
    by_series[m["series"]].append(m)
for s in by_series:
    by_series[s].sort(key=lambda m: m["first_ts"])

def compute_phat(series, entry_ts):
    """Expanding window: fraction of same-series markets with settlement_ts < entry_ts."""
    prior = [m for m in by_series[series] if m["settlement_ts"] < entry_ts]
    if not prior:
        return None
    return sum(m["result_yes"] for m in prior) / len(prior), len(prior)

for m in markets:
    r = compute_phat(m["series"], m["first_ts"])
    if r is None:
        m["phat"] = None
        m["n_prior"] = 0
    else:
        m["phat"], m["n_prior"] = r

n_with_phat = sum(1 for m in markets if m["phat"] is not None)
print(f"Markets with a defined expanding-window p_hat (nonzero prior history): {n_with_phat} / {len(markets)}")

# ---------- Signal + trade construction for a given theta ----------
def build_trades(theta_dollars):
    trades = []
    for m in markets:
        if m["phat"] is None:
            continue
        divergence = m["first_print"] - m["phat"]
        if abs(divergence) <= theta_dollars:
            continue
        # take side TOWARD p_hat
        if m["phat"] > m["first_print"]:
            side = "YES"
            price = m["first_print"]
            win = (m["result_yes"] == 1)
        else:
            side = "NO"
            price = 1.0 - m["first_print"]
            win = (m["result_yes"] == 0)
        fee = fee_dollars(price)
        net_ev = (1 - price if win else -price) - fee
        trades.append({
            "ticker": m["ticker"], "series": m["series"], "event_ticker": m["event_ticker"],
            "first_print": m["first_print"], "phat": m["phat"], "n_prior": m["n_prior"],
            "divergence": divergence, "side": side, "price": price, "win": win,
            "fee": fee, "net_ev": net_ev, "settlement_ts": m["settlement_ts"].isoformat(),
            "in_fit": m["event_ticker"] in fit_events,
        })
    return trades

theta_scan = {}
for th_cents in THETAS_CENTS:
    theta = th_cents / 100.0
    all_trades = build_trades(theta)
    fit_trades = [t for t in all_trades if t["in_fit"]]
    val_trades = [t for t in all_trades if not t["in_fit"]]
    fit_mean_ev = (sum(t["net_ev"] for t in fit_trades) / len(fit_trades)) if fit_trades else None
    theta_scan[th_cents] = {
        "n_fit": len(fit_trades), "n_val": len(val_trades),
        "fit_mean_net_ev": fit_mean_ev,
    }
    print(f"theta={th_cents}c  n_fit={len(fit_trades)} n_val={len(val_trades)} fit_mean_net_ev={fit_mean_ev}")

# Select theta maximizing FIT-set mean net EV among thetas with >=1 fit trade;
# if no theta has any fit trade, document and fall back to the pre-registered
# median grid point (15c) as the least-arbitrary default (documented limitation).
candidates = {k: v for k, v in theta_scan.items() if v["n_fit"] > 0 and v["fit_mean_net_ev"] is not None}
if candidates:
    selected_theta = max(candidates, key=lambda k: candidates[k]["fit_mean_net_ev"])
    selection_method = "max fit-set mean net EV"
else:
    selected_theta = 15
    selection_method = "FALLBACK: no theta produced any fit-set entry (insufficient fit-period history); defaulted to median grid point 15c"

print(f"Selected theta = {selected_theta}c  ({selection_method})")

final_trades = build_trades(selected_theta / 100.0)
val_trades = [t for t in final_trades if not t["in_fit"]]
fit_trades = [t for t in final_trades if t["in_fit"]]

# ---------- Validation-set stats ----------
n_val = len(val_trades)
wins = sum(1 for t in val_trades if t["win"])
win_rate = wins / n_val if n_val else float("nan")
mean_net_ev = (sum(t["net_ev"] for t in val_trades) / n_val) if n_val else float("nan")
wilson_lo, wilson_hi = wilson_ci(wins, n_val) if n_val else (float("nan"), float("nan"))

# breakeven win rate given avg entry price paid (fee-inclusive) -- approx via avg price
avg_price = (sum(t["price"] for t in val_trades) / n_val) if n_val else float("nan")
avg_fee = (sum(t["fee"] for t in val_trades) / n_val) if n_val else float("nan")
# breakeven: win_rate*(1-p) - (1-win_rate)*p - fee = 0  =>  win_rate = p + fee
breakeven_win_rate = (avg_price + avg_fee) if n_val else float("nan")

val_event_days = set(t["event_ticker"] for t in val_trades)
by_cluster = defaultdict(list)
for t in val_trades:
    by_cluster[t["event_ticker"]].append(t["net_ev"])
tstat_res = clustered_ttest_onesided(by_cluster)
p_raw = tstat_res["p_one_sided"]
p_bonf = min(1.0, p_raw * BONFERRONI_M) if not math.isnan(p_raw) else float("nan")

min_n_met = (n_val >= MIN_VALIDATION_N) and (len(val_event_days) >= MIN_VALIDATION_EVENT_DAYS)

# ---------- Adverse-selection check ----------
# Compare realized correct-direction rate of FIRED (signal) markets vs NON-FIRED
# same-series markets, matched by first_print price bucket (nearest 10c), using
# ALL markets with a defined p_hat (fit+validation pooled, since this is a
# structural adverse-selection diagnostic, not a return estimate).
def bucket(price):
    return round(price * 10) / 10.0  # nearest 10c

fired_tickers = set(t["ticker"] for t in final_trades)
pool = [m for m in markets if m["phat"] is not None]

fired_by_bucket = defaultdict(list)   # bucket -> list of (predicted_side_correct)
nonfired_by_bucket = defaultdict(list)

for m in pool:
    b = bucket(m["first_print"])
    if m["ticker"] in fired_tickers:
        t = next(t for t in final_trades if t["ticker"] == m["ticker"])
        fired_by_bucket[b].append(1 if t["win"] else 0)
    else:
        # "predicted" side for a non-fired market: toward phat vs first_print anyway (weak signal direction)
        if m["phat"] is None:
            continue
        pred_yes = m["phat"] >= m["first_print"]
        correct = (m["result_yes"] == 1) if pred_yes else (m["result_yes"] == 0)
        nonfired_by_bucket[b].append(1 if correct else 0)

common_buckets = set(fired_by_bucket) & set(nonfired_by_bucket)
matched_fired_rate = None
matched_nonfired_rate = None
if common_buckets:
    f_all = [x for b in common_buckets for x in fired_by_bucket[b]]
    nf_all = [x for b in common_buckets for x in nonfired_by_bucket[b]]
    matched_fired_rate = sum(f_all)/len(f_all) if f_all else None
    matched_nonfired_rate = sum(nf_all)/len(nf_all) if nf_all else None

quoted_divergence_edge = (sum(abs(t["divergence"]) for t in final_trades) / len(final_trades)) if final_trades else None

if matched_fired_rate is not None and matched_nonfired_rate is not None:
    realized_edge = matched_fired_rate - matched_nonfired_rate  # in "correct-direction rate" units
else:
    realized_edge = None

adverse_selection_note = ""
adverse_selection_pass = None
if not common_buckets or len(fired_tickers) == 0:
    adverse_selection_pass = None
    adverse_selection_note = "INSUFFICIENT DATA: no overlapping price buckets between fired and non-fired same-series markets (n too small)."
else:
    if realized_edge is None or quoted_divergence_edge is None or quoted_divergence_edge == 0:
        adverse_selection_pass = None
        adverse_selection_note = "INSUFFICIENT DATA to compute quoted-vs-realized edge ratio."
    else:
        ratio = realized_edge / quoted_divergence_edge  # not perfectly comparable units but directional proxy
        adverse_selection_pass = realized_edge > 0  # minimum bar: fired trades must beat non-fired at all
        adverse_selection_note = (f"matched_fired_correct_rate={matched_fired_rate:.3f} "
                                   f"matched_nonfired_correct_rate={matched_nonfired_rate:.3f} "
                                   f"realized_edge={realized_edge:+.3f} vs quoted_divergence_edge={quoted_divergence_edge:.3f} "
                                   f"(n_fired_matched={len(f_all)}, n_nonfired_matched={len(nf_all)})")

# ---------- Verdict ----------
pass_stat = (not math.isnan(mean_net_ev)) and (mean_net_ev > 0) and (not math.isnan(p_bonf)) and (p_bonf < ALPHA)
pass_wilson = (not math.isnan(wilson_lo)) and (not math.isnan(breakeven_win_rate)) and (wilson_lo > breakeven_win_rate)
pass_adverse = (adverse_selection_pass is True)

if not min_n_met:
    verdict = "INCONCLUSIVE"
    verdict_reason = (f"Pre-registered minimum n gate NOT met: validation entries={n_val} "
                       f"(need >=30), distinct validation event-days={len(val_event_days)} "
                       f"(need >=8). This is a pre-registered stop condition, not a goalpost move.")
else:
    verdict = "PASS" if (pass_stat and pass_wilson and pass_adverse) else "FAIL"
    verdict_reason = f"stat_pass={pass_stat} wilson_pass={pass_wilson} adverse_selection_pass={pass_adverse}"

# ---------- Capacity estimate (honest, order-of-magnitude) ----------
# Only meaningful if there is a real signal; with INCONCLUSIVE/FAIL this is nominal.
if n_val > 0 and mean_net_ev > 0 and min_n_met:
    # crude: entries observed per validation event-day * $ notional per contract * events/month
    entries_per_eventday = n_val / max(1, len(val_event_days))
    est_events_per_month = 4  # ~weekly broadcast-style cadence assumption, stated explicitly
    est_contracts_per_month = entries_per_eventday * est_events_per_month
    capacity_usd_month = est_contracts_per_month * mean_net_ev * 50  # assume ~$50 avg size/contract cap, stated
else:
    capacity_usd_month = 0.0

result = {
    "spec": "Spec 1: mention-open base-rate anchor",
    "data_reality_check": {
        "note": ("Pre-registration assumed KXFEDMENTION=45 settled/12 events, "
                 "KXHANNITYMENTION=29 settled/2 events. Kalshi's public markets API "
                 "only returns markets for the two most recent events per series "
                 "(current + most recently finalized); older events return 0 markets "
                 "even though the /events listing shows them. Actual retrievable data: "
                 "KXFEDMENTION=45 settled markets but ALL from a SINGLE event/broadcast-day "
                 "(2026-06-17); KXHANNITYMENTION=29 settled/2 events, matching pre-registration. "
                 "Total distinct broadcast-event-days available across both series: "
                 f"{n_events} ({events_sorted})."),
        "n_events_total": n_events,
        "events_chronological": events_sorted,
    },
    "fit_validation_split": {
        "fit_events": sorted(fit_events),
        "validation_events": sorted(val_events),
        "split_rule": "chronological by event; first floor(0.4*n_events) events = fit, remainder = validation",
    },
    "theta_selection": {
        "grid_cents": THETAS_CENTS,
        "scan": theta_scan,
        "selected_theta_cents": selected_theta,
        "method": selection_method,
    },
    "validation_results": {
        "n_val": n_val,
        "wins": wins,
        "win_rate": win_rate,
        "wilson_95_ci": [wilson_lo, wilson_hi],
        "avg_price_paid": avg_price,
        "avg_fee": avg_fee,
        "breakeven_win_rate_fee_inclusive": breakeven_win_rate,
        "mean_net_ev_per_contract": mean_net_ev,
        "n_distinct_validation_event_days": len(val_event_days),
        "validation_event_days": sorted(val_event_days),
        "event_day_clustered_ttest": tstat_res,
        "p_raw_one_sided": p_raw,
        "p_bonferroni_x10": p_bonf,
    },
    "adverse_selection_check": {
        "matched_fired_correct_rate": matched_fired_rate,
        "matched_nonfired_correct_rate": matched_nonfired_rate,
        "quoted_divergence_edge_abs_mean": quoted_divergence_edge,
        "realized_edge": realized_edge,
        "pass": adverse_selection_pass,
        "note": adverse_selection_note,
    },
    "min_n_gate": {
        "required_n": MIN_VALIDATION_N,
        "required_event_days": MIN_VALIDATION_EVENT_DAYS,
        "met": min_n_met,
    },
    "verdict": verdict,
    "verdict_reason": verdict_reason,
    "capacity_usd_per_month_estimate": capacity_usd_month,
    "all_fired_trades_fit_and_validation": final_trades,
    "n_markets_total_finalized_with_trades": len(markets),
    "n_markets_with_defined_phat": n_with_phat,
}

with open(f"{OUTDIR}/results.json", "w") as f:
    json.dump(result, f, indent=2, default=str)

print(json.dumps({k: v for k, v in result.items() if k not in ("all_fired_trades_fit_and_validation",)}, indent=2, default=str))
