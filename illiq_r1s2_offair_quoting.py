#!/usr/bin/env python3
"""
Spec #2 pre-registered backtest: OFF-AIR PASSIVE QUOTING, MENTIONS
Series: KXFEDMENTION, KXHANNITYMENTION.

Pre-registered mechanics (verbatim from task):
  - Broadcast windows hardcoded from public schedules (Fed presser calendar; Hannity
    weeknights 9pm ET) -- no external feed dependency.
  - Simulated resting quotes from trade prints only (no book history): rest bid at
    (last print - k) and ask at (last print + k), k in {5,8,12} cents, fit-set only.
  - Quotes live/considered inside window [air-2h, air+3h].
  - Fill rule (conservative): a later print strictly through our price, size capped
    at printed size. Maker fee 0 unless the series fee schedule says otherwise
    (verify, include if nonzero).
  - Exit: hold to settlement.
  - Fit/validation: chronological event split (first 40% = fit, last 60% =
    validation), same convention as Spec 1.
  - Min n: >=40 simulated fills across >=10 event-days, else INCONCLUSIVE.
  - Adverse-selection check (mandatory): markout = settlement value - fill price,
    computed separately for fills in the 24h pre-air vs earlier. FAIL if pre-air
    markout negative, or if >70% of fills land on the eventually-losing side.
  - Pass bar: clustered mean markout > +3c/contract, one-sided p<0.05 Bonferroni x10,
    both adverse-selection sub-checks passed.

DATA-AVAILABILITY FINDING (see results.md for full discussion): the public Kalshi
markets endpoint only serves settled-market detail for the MOST RECENT completed
event per series; older events listed by /events exist as metadata shells with zero
retrievable nested markets. Real accessible event-days: KXFEDMENTION 1/12
(26JUN2026), KXHANNITYMENTION 2/2 (26MAY19, 26MAY21). Total = 3 event-days versus
the pre-registered minimum of 10. This alone forces INCONCLUSIVE regardless of the
point estimate; the mechanics below are still executed in full on the accessible
data for honest, transparent numbers.
"""
import json, math, os, sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

CACHE = os.path.dirname(os.path.abspath(__file__)) + "/cache"
OUT = os.path.dirname(os.path.abspath(__file__))

def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def load_json(fp):
    return json.load(open(fp))

# ---------------------------------------------------------------------------
# 1. Load market metadata (accessible events only) and assign air times.
# ---------------------------------------------------------------------------

def load_fed_markets():
    d = load_json(f"{CACHE}/markets_fed_KXFEDMENTION-26JUN.json")
    ms = d["markets"]
    # air time = median of the clustered occurrence_datetime values, excluding the
    # placeholder sentinel equal to expiration_time (words never said default to
    # expiration_time, not a real occurrence).
    expiry = ms[0]["expiration_time"]
    real_occ = sorted(parse_ts(m["occurrence_datetime"]) for m in ms if m["occurrence_datetime"] != expiry)
    air = real_occ[len(real_occ) // 2]
    for m in ms:
        m["_event"] = "KXFEDMENTION-26JUN"
        m["_air"] = air
        m["_series"] = "KXFEDMENTION"
    return ms

def load_hannity_markets():
    out = []
    for ev, date_str in [("KXHANNITYMENTION-26MAY19", "2026-05-19"),
                          ("KXHANNITYMENTION-26MAY21", "2026-05-21")]:
        fname = f"{CACHE}/markets_han_{ev}.json"
        d = load_json(fname)
        ms = d["markets"]
        y, mo, day = (int(x) for x in date_str.split("-"))
        air_et = datetime(y, mo, day, 21, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        air = air_et.astimezone(timezone.utc)
        for m in ms:
            m["_event"] = ev
            m["_air"] = air
            m["_series"] = "KXHANNITYMENTION"
        out.extend(ms)
    return out

ALL_MARKETS = load_fed_markets() + load_hannity_markets()
print(f"Loaded {len(ALL_MARKETS)} markets across "
      f"{len(set(m['_event'] for m in ALL_MARKETS))} events", file=sys.stderr)

# ---------------------------------------------------------------------------
# 2. Load trades, restrict to window [air-2h, air+3h], simulate maker quoting.
# ---------------------------------------------------------------------------

def load_trades(ticker):
    fp = f"{CACHE}/trades_{ticker}.json"
    trades = load_json(fp)
    for t in trades:
        t["_ts"] = parse_ts(t["created_time"])
        t["_yes_px"] = float(t["yes_price_dollars"])
        t["_size"] = float(t["count_fp"])
    trades.sort(key=lambda t: t["_ts"])
    return trades

def fee_per_contract(p):
    # ceil(7*p*(1-p)) cents -> dollars. p in [0,1].
    return math.ceil(7.0 * p * (1.0 - p)) / 100.0

def settlement_value(market):
    r = market.get("result", "")
    return 1.0 if r == "yes" else 0.0

def simulate_market(market, k):
    """Simulate passive quoting for one market at spread k (dollars).
    Returns list of fill dicts."""
    air = market["_air"]
    win_start = air - timedelta(hours=2)
    win_end = air + timedelta(hours=3)
    trades = load_trades(market["ticker"])
    if not trades:
        return []

    # seed reference price = last print at/before window start; else first print
    # inside the window (no fills possible before a reference exists).
    last_print = None
    for t in trades:
        if t["_ts"] <= win_start:
            last_print = t["_yes_px"]
        else:
            break

    win_trades = [t for t in trades if win_start < t["_ts"] <= win_end]
    fills = []
    sval = settlement_value(market)
    result = market.get("result", "")
    for t in win_trades:
        if last_print is not None:
            bid = round(last_print - k, 4)
            ask = round(last_print + k, 4)
            px = t["_yes_px"]
            size = t["_size"]
            fill = None
            if px < bid - 1e-9:
                # print traded through our bid -> our resting buy (long YES) filled at bid
                fill = {"side": "buy", "price": bid, "size": min(size, size)}
            elif px > ask + 1e-9:
                # print traded through our ask -> our resting sell (short YES) filled at ask
                fill = {"side": "sell", "price": ask, "size": min(size, size)}
            if fill is not None:
                fee = fee_per_contract(fill["price"])
                if fill["side"] == "buy":
                    raw_markout = sval - fill["price"]
                    lost = (result != "yes")
                else:
                    raw_markout = fill["price"] - sval
                    lost = (result == "yes")
                net_markout = raw_markout - fee
                hours_to_air = (air - t["_ts"]).total_seconds() / 3600.0
                fills.append({
                    "ticker": market["ticker"],
                    "event": market["_event"],
                    "series": market["_series"],
                    "side": fill["side"],
                    "fill_price": fill["price"],
                    "size": fill["size"],
                    "settlement_value": sval,
                    "result": result,
                    "fee": fee,
                    "raw_markout": raw_markout,
                    "net_markout": net_markout,
                    "lost": lost,
                    "trade_ts": t["created_time"],
                    "hours_before_air": hours_to_air,
                    "pre_air_24h": 0 <= hours_to_air <= 24,
                })
        last_print = t["_yes_px"]
    return fills

# ---------------------------------------------------------------------------
# 3. Fit/validation split (chronological, per series; first 40% = fit).
# ---------------------------------------------------------------------------

fed_events = sorted(set(m["_event"] for m in ALL_MARKETS if m["_series"] == "KXFEDMENTION"))
han_events = sorted(set(m["_event"] for m in ALL_MARKETS if m["_series"] == "KXHANNITYMENTION"),
                     key=lambda e: e)  # 26MAY19 < 26MAY21 lexically already

# Hannity: 2 events -> first 40% = ceil(0.4*2)=1 event fit, remainder validation.
han_fit = set(han_events[:1])
han_val = set(han_events[1:])
# Fed: only 1 accessible event -> cannot hold out validation data for Fed alone
# (would require lookahead-free split with >=2 events). Treated as fit-only /
# descriptive; excluded from the formal validation statistic.
fed_fit = set(fed_events)
fed_val = set()

FIT_EVENTS = fed_fit | han_fit
VAL_EVENTS = fed_val | han_val
print(f"fit events: {FIT_EVENTS}", file=sys.stderr)
print(f"validation events: {VAL_EVENTS}", file=sys.stderr)

# ---------------------------------------------------------------------------
# 4. Grid search k in {5,8,12} cents on FIT events only; pick per-series best by
#    mean net markout on fit fills (ties broken toward smaller k).
# ---------------------------------------------------------------------------

K_GRID = [0.05, 0.08, 0.12]

def fills_for_events(events, k):
    out = []
    for m in ALL_MARKETS:
        if m["_event"] in events:
            out.extend(simulate_market(m, k))
    return out

best_k = {}
for series, fit_ev in [("KXFEDMENTION", fed_fit), ("KXHANNITYMENTION", han_fit)]:
    scores = {}
    for k in K_GRID:
        evs = {e for e in fit_ev}
        fills = [f for f in fills_for_events(evs, k) if f["series"] == series]
        mean_m = sum(f["net_markout"] for f in fills) / len(fills) if fills else float("-inf")
        scores[k] = (mean_m, len(fills))
    chosen = max(scores.items(), key=lambda kv: kv[1][0])[0]
    best_k[series] = chosen
    print(f"{series} fit-set k grid: {scores}  -> chosen k={chosen}", file=sys.stderr)

# ---------------------------------------------------------------------------
# 5. Apply chosen k out-of-sample to validation events; also compute full-sample
#    (fit+validation, i.e. all accessible data) descriptive numbers since
#    validation alone is far below the pre-registered min n.
# ---------------------------------------------------------------------------

def collect(events, per_series_k):
    out = []
    for m in ALL_MARKETS:
        if m["_event"] in events:
            k = per_series_k[m["_series"]]
            out.extend(simulate_market(m, k))
    return out

val_fills = collect(VAL_EVENTS, best_k)
fit_fills = collect(FIT_EVENTS, best_k)
all_fills = val_fills + fit_fills

def wilson_ci(successes, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    phat = successes / n
    denom = 1 + z**2 / n
    center = phat + z*z/(2*n)
    adj = z * math.sqrt((phat*(1-phat) + z*z/(4*n)) / n)
    lo = (center - adj) / denom
    hi = (center + adj) / denom
    return (lo, hi)

def day_clustered_ttest(fills, value_key="net_markout"):
    """One-sided t-test (H1: mean>0) clustered by event day."""
    by_day = defaultdict(list)
    for f in fills:
        by_day[f["event"]].append(f[value_key])
    day_means = {d: sum(v)/len(v) for d, v in by_day.items()}
    n_days = len(day_means)
    vals = list(day_means.values())
    if n_days < 2:
        return {"n_days": n_days, "day_means": day_means, "t": None, "p": None,
                "note": "insufficient clusters (<2) for a valid clustered SE / t-test"}
    mean = sum(vals) / n_days
    var = sum((v-mean)**2 for v in vals) / (n_days - 1)
    se = math.sqrt(var / n_days) if var > 0 else 0.0
    if se == 0:
        t = float("inf") if mean > 0 else 0.0
    else:
        t = mean / se
    # one-sided p via t-distribution CDF approx (Abramowitz-Stegun / use math.erf
    # normal approx for simplicity given tiny df -- flagged as approximate)
    # Use a simple Student-t survival function via incomplete beta if scipy absent.
    p = student_t_sf(t, n_days - 1) if se > 0 else (0.0 if mean > 0 else 1.0)
    return {"n_days": n_days, "day_means": day_means, "mean": mean, "se": se,
            "t": t, "p_onesided": p}

def student_t_sf(t, df):
    """One-sided survival function P(T>t) for Student-t, df degrees of freedom,
    via the regularized incomplete beta function (no scipy dependency)."""
    if df <= 0:
        return float("nan")
    if t <= 0:
        # symmetric; P(T>t) > 0.5
        x = df / (df + t*t)
        ib = betainc(df/2.0, 0.5, x)
        return 1 - 0.5*ib
    x = df / (df + t*t)
    ib = betainc(df/2.0, 0.5, x)
    return 0.5 * ib

def betainc(a, b, x, iters=200):
    """Regularized incomplete beta via continued fraction (Numerical Recipes)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b) + a*math.log(x) + b*math.log(1-x)
    front = math.exp(lbeta) / a
    if x < (a+1)/(a+b+2):
        return front * betacf(a, b, x, iters)
    else:
        return 1 - (math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b) + b*math.log(1-x) + a*math.log(x))/b) * betacf(b, a, 1-x, iters)

def betacf(a, b, x, iters):
    FPMIN = 1e-30
    qab = a+b; qap = a+1; qam = a-1
    c = 1.0; d = 1.0 - qab*x/qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0/d
    h = d
    for m in range(1, iters+1):
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
        delta = d*c
        h *= delta
        if abs(delta-1.0) < 3e-10:
            break
    return h

# ---------------------------------------------------------------------------
# 6. Adverse-selection checks (mandatory) -- run on ALL accessible fills (fit+val
#    pooled) since validation alone has too few fills to check sub-70%/pre-air
#    reliably, and also reported for validation-only where n allows.
# ---------------------------------------------------------------------------

def adverse_selection(fills):
    pre = [f for f in fills if f["pre_air_24h"]]
    early = [f for f in fills if not f["pre_air_24h"]]
    pre_markout = sum(f["net_markout"] for f in pre)/len(pre) if pre else None
    early_markout = sum(f["net_markout"] for f in early)/len(early) if early else None
    n_lost = sum(1 for f in fills if f["lost"])
    pct_lost = n_lost/len(fills) if fills else None
    check1_pass = (pre_markout is not None and pre_markout >= 0)
    check2_pass = (pct_lost is not None and pct_lost <= 0.70)
    return {
        "n_pre_air_24h": len(pre), "pre_air_24h_mean_net_markout": pre_markout,
        "n_earlier": len(early), "earlier_mean_net_markout": early_markout,
        "pct_fills_on_losing_side": pct_lost,
        "check1_pre_air_nonneg_pass": check1_pass,
        "check2_le70pct_losing_pass": check2_pass,
        "both_pass": bool(check1_pass and check2_pass) if (pre_markout is not None and pct_lost is not None) else None,
    }

# ---------------------------------------------------------------------------
# 7. Assemble results
# ---------------------------------------------------------------------------

MIN_FILLS = 40
MIN_EVENT_DAYS = 10
PASS_BAR_MARKOUT = 0.03  # 3 cents net
ALPHA_BONFERRONI = 0.05 / 10

def summarize(fills, label):
    n = len(fills)
    n_days = len(set(f["event"] for f in fills))
    mean_net = sum(f["net_markout"] for f in fills)/n if n else None
    mean_raw = sum(f["raw_markout"] for f in fills)/n if n else None
    n_win = sum(1 for f in fills if not f["lost"])
    wilson = wilson_ci(n_win, n) if n else (None, None)
    ttest = day_clustered_ttest(fills) if n else {"note": "no fills"}
    adv = adverse_selection(fills) if n else {}
    return {
        "label": label, "n_fills": n, "n_event_days": n_days,
        "mean_net_markout": mean_net, "mean_raw_markout": mean_raw,
        "win_rate": (n_win/n if n else None), "wilson_95ci": wilson,
        "clustered_ttest": ttest, "adverse_selection": adv,
    }

val_summary = summarize(val_fills, "validation_only")
all_summary = summarize(all_fills, "all_accessible_fit+validation_pooled")
fed_all = [f for f in all_fills if f["series"] == "KXFEDMENTION"]
han_all = [f for f in all_fills if f["series"] == "KXHANNITYMENTION"]
fed_summary = summarize(fed_all, "KXFEDMENTION_all_accessible")
han_summary = summarize(han_all, "KXHANNITYMENTION_all_accessible")

n_event_days_total = len(set(m["_event"] for m in ALL_MARKETS))
min_n_met = (val_summary["n_fills"] >= MIN_FILLS) and (n_event_days_total >= MIN_EVENT_DAYS)

# Verdict logic (validation-based, pre-registered)
verdict = "INCONCLUSIVE"
verdict_reason = []
if not min_n_met:
    verdict_reason.append(
        f"Pre-registered minimum n not met: need >=40 validation fills across >=10 "
        f"event-days; accessible data has only {n_event_days_total} event-days total "
        f"(validation set has {val_summary['n_fills']} fills across "
        f"{val_summary['n_event_days']} event-days). Public Kalshi API only serves "
        f"nested market/trade detail for the single most-recent settled event per "
        f"series (see DATA-AVAILABILITY FINDING); 11 of 12 KXFEDMENTION events are "
        f"listed as metadata shells with zero retrievable markets."
    )
else:
    adv = val_summary["adverse_selection"]
    mean_net = val_summary["mean_net_markout"] or 0
    tt = val_summary["clustered_ttest"]
    p = tt.get("p_onesided")
    passed = (mean_net > PASS_BAR_MARKOUT and p is not None and p < ALPHA_BONFERRONI
              and adv.get("both_pass") is True)
    verdict = "PASS" if passed else "FAIL"
    verdict_reason.append("Evaluated against numeric pass bar on validation set.")

results = {
    "spec": "Spec 2 - OFF-AIR PASSIVE QUOTING, MENTIONS",
    "pre_registered_pass_bar": {
        "mean_net_markout_gt": PASS_BAR_MARKOUT,
        "one_sided_p_lt_bonferroni10": ALPHA_BONFERRONI,
        "adverse_selection_both_subchecks_pass": True,
        "min_fills": MIN_FILLS, "min_event_days": MIN_EVENT_DAYS,
    },
    "data_availability": {
        "kxfedmention_events_listed": 12,
        "kxfedmention_events_with_retrievable_markets": 1,
        "kxhannitymention_events_listed": 2,
        "kxhannitymention_events_with_retrievable_markets": 2,
        "total_accessible_event_days": n_event_days_total,
        "total_accessible_markets": len(ALL_MARKETS),
    },
    "fee_schedule_verification": {
        "series_fee_type": "quadratic", "series_fee_multiplier": 1,
        "resolution": "nonzero fee_multiplier -> maker fee NOT assumed zero; applied "
                       "ceil(7*p*(1-p))/100 per contract to every simulated fill at "
                       "the fill price, consistent with house convention that fees "
                       "enter all EV math.",
    },
    "chosen_k_per_series_cents": {k: v*100 for k, v in best_k.items()},
    "fit_events": sorted(FIT_EVENTS),
    "validation_events": sorted(VAL_EVENTS),
    "validation_summary": val_summary,
    "all_accessible_pooled_summary": all_summary,
    "by_series_all_accessible": {"KXFEDMENTION": fed_summary, "KXHANNITYMENTION": han_summary},
    "min_n_met": min_n_met,
    "verdict": verdict,
    "verdict_reason": verdict_reason,
}

with open(f"{OUT}/results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print(json.dumps(results, indent=2, default=str))
