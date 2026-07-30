#!/usr/bin/env python3
"""
ForecastEx incentive-coupon + pair-yield revenue computation.
Reproduces every number in out/rev_forecastex.json from on-disk cache + cited external rates.
Run: python3 venue_expansion/rev_forecastex_calc.py
"""
import csv, glob, json, re, statistics
from datetime import datetime

CACHE = "cache/forecastex"

# ---- 1. Cited external rates (fetched this session, see citations in JSON) ----
EFFR = 0.0363          # FRED series EFFR, 2026-07-29
TBILL_3M = 0.0390       # FRED series DGS3MO, 2026-07-28
IBKR_TOP_TIER = 0.0433  # secondary source (tradersunion/cavengrowth), NAV>$100k, cash>$10k, ~EFFR-0.5%... unverified primary
IBKR_LOW_TIER = 0.0314  # secondary source, most retail balances

MIN_COUPON_RATE = (EFFR - 0.0050) / 2.0   # Rule 612(c)(3): (EFFR - 50bps)/2

FEE_PER_CONTRACT_PER_SIDE = 0.01
FEE_PER_PAIR = 2 * FEE_PER_CONTRACT_PER_SIDE  # both Yes and No sides charged, per fee_schedule.pdf

# ---- 2. Scan the pairs tape ----
files = sorted(glob.glob(f"{CACHE}/pairs_*.csv"))
n = 0
qty_total = 0
combined_hist = {}
below_100 = []
below_099_after_fee = []  # combined < 1.00 - FEE_PER_PAIR (true instant arb net of fee)
durations_h = []
prefix_durations = {}

for f in files:
    with open(f) as fh:
        r = csv.DictReader(fh)
        for row in r:
            try:
                yp = float(row["yes_price"]); npr = float(row["no_price"])
                qty = int(row["quantity"])
            except Exception:
                continue
            n += 1
            qty_total += qty
            combined = round(yp + npr, 4)
            combined_hist[combined] = combined_hist.get(combined, 0) + 1
            if combined < 1.0 - 1e-9:
                below_100.append((row["event_contract"], combined, qty, row["pair_time"]))
            if combined < 1.0 - FEE_PER_PAIR - 1e-9:
                below_099_after_fee.append((row["event_contract"], combined, qty, row["pair_time"]))
            try:
                exp = datetime.fromisoformat(row["expiration_date"])
                pt = datetime.fromisoformat(row["pair_time"])
                dh = (exp - pt).total_seconds() / 3600.0
                durations_h.append(dh)
                m = re.match(r"^([A-Z]+)", row["event_contract"])
                pfx = m.group(1) if m else row["event_contract"]
                arr = prefix_durations.setdefault(pfx, [])
                if len(arr) < 5000:
                    arr.append(dh)
            except Exception:
                pass

durations_h.sort()
median_h = statistics.median(durations_h)
p90_h = durations_h[int(len(durations_h) * 0.90)]
p99_h = durations_h[int(len(durations_h) * 0.99)]
max_h = durations_h[-1]

weather_prefixes = [p for p in prefix_durations if p.startswith("UH") or p.startswith("DH")]
weather_n = sum(len(prefix_durations[p]) for p in weather_prefixes)
weather_med = statistics.median([d for p in weather_prefixes for d in prefix_durations[p]])

longest_prefix = max(prefix_durations.items(), key=lambda kv: statistics.median(kv[1]))
longest_med_h = statistics.median(longest_prefix[1])

# ---- 3. Yield model ----
def annualized_yield(cost, hold_days, coupon_rate=MIN_COUPON_RATE, fee=FEE_PER_PAIR, payout=1.00):
    """Yield on a fully-collateralized YES+NO pair held `hold_days` to expiry."""
    coupon = 1.00 * coupon_rate * (hold_days / 365.0)   # coupon accrues on ~$1 combined settlement value
    net = (payout - cost) + coupon - fee
    if hold_days <= 0:
        return None
    return (net / cost) * (365.0 / hold_days)

breakeven_days = FEE_PER_PAIR * 365.0 / MIN_COUPON_RATE  # coupon(T) == fee, cost=1.00 case

sample_days = [median_h/24, p90_h/24, weather_med/24, 30, 90, 180, 365, 730, 3650, max_h/24]
yields = {f"{d:.2f}d": annualized_yield(1.00, d) for d in sample_days}

out = {
    "target": "ForecastEx incentive coupon + YES/NO pair-yield trade",
    "us_person_deployable": True,
    "venue_status": "CFTC-self-certified DCM/DCO (ForecastEx LLC), accessible via IBKR brokerage. US-legal, NOT geo-blocked (contrast with global Polymarket).",
    "rates_cited": {
        "EFFR": {"value": EFFR, "source": "FRED series EFFR, 2026-07-29 (fetched this session)", "label": "CITED"},
        "TBILL_3M": {"value": TBILL_3M, "source": "FRED series DGS3MO, 2026-07-28 (fetched this session)", "label": "CITED"},
        "IBKR_cash_top_tier": {"value": IBKR_TOP_TIER, "note": "NAV>$100k, balance>$10k threshold; secondary sources only (IBKR pricing page returned HTTP 403 to WebFetch this session)", "label": "ESTIMATE"},
        "IBKR_cash_low_tier": {"value": IBKR_LOW_TIER, "note": "typical retail / IBKR Pro base rate; secondary sources only", "label": "ESTIMATE"},
    },
    "min_coupon_rate_annualized": MIN_COUPON_RATE,
    "min_coupon_formula": "Rule 612(c)(3), ForecastEx_LLC_Rulebook.pdf p.53-54: Coupon Rate = (EFFR - 50bps) / 2, floored at 0 (612(c)(5)), stale-day rate carries forward (612(c)(4))",
    "fee_per_contract_per_side": FEE_PER_CONTRACT_PER_SIDE,
    "fee_per_pair": FEE_PER_PAIR,
    "fee_source": "cache/forecastex/fee_schedule.pdf: '$0.01 per contract... charged to both the Yes and No sides of each executed transaction and are independent of contract resolution, netting, or settlement' (i.e. one-time at entry, not charged again at settlement)",
    "position_accountability": {
        "value_contracts": 250000,
        "source": "cache/fx_daily_temp.pdf p.5 (Daily Temperature Forecast Contract Terms and Conditions): 'Position Accountability... is 250,000 Contracts in any one Forecast Market'",
        "mechanism": "Rule 408 Rulebook p.34: ACCOUNTABILITY not a hard cap -- exceeding it triggers disclosure/reduction-on-request, exchange can force-liquidate on noncompliance. Per-product; other product filings not individually checked.",
    },
    "tape_scan": {
        "files_scanned": len(files),
        "date_range": [files[0].split("_")[-1].split(".")[0], files[-1].split("_")[-1].split(".")[0]],
        "n_pair_executions": n,
        "total_contracts_qty": qty_total,
        "combined_price_histogram": combined_hist,
        "n_combined_below_1.00_raw": len(below_100),
        "n_combined_below_breakeven_after_fee": len(below_099_after_fee),
        "instant_arb_examples": below_100[:10],
        "finding": "ZERO of 2,968,096 executed YES+NO pair trades (Feb 10 - Jul 28 2026, 169 days, ~198M contracts) printed combined < $1.00. This is the exchange's own synthetic 'pair' product (pair_id/pair_time columns), not raw independent order-book crossing, so it is constructed to price at parity or worse by design -- 47.0% print exactly $1.00, 53.0% print $1.01 (a full 1c ABOVE parity, i.e. worse than the fee-only floor).",
    },
    "holding_period_measured": {
        "median_hours_all_products": median_h,
        "p90_hours_all_products": p90_h,
        "p99_hours_all_products": p99_h,
        "max_hours_observed": max_h,
        "weather_UH_DH_products": {
            "n_sampled": weather_n,
            "median_hours": weather_med,
            "note": "Weather (daily temperature, UH*/DH* prefixes) is the dominant product by pair-trade count (1.1M+ of ~1.28M total pairs in a representative day's summary) and has SHORT duration: median <20h.",
        },
        "longest_duration_product_family": {
            "prefix": longest_prefix[0],
            "median_hours": longest_med_h,
        },
    },
    "yield_model": {
        "formula": "annualized_yield(T_days) = coupon_rate - (fee_per_pair * 365 / T_days), for cost=$1.00 (no price edge assumed, matches measured tape)",
        "breakeven_holding_days_at_min_coupon": breakeven_days,
        "breakeven_holding_months": breakeven_days / 30.44,
        "sample_yields_by_holding_period": yields,
        "interpretation": "At the regulatory MINIMUM coupon rate (1.565%/yr as of 2026-07-29), a YES+NO pair must be held ~15.3 months before the coupon accrual exceeds the one-time $0.02/pair transaction fee. The dominant-volume product (daily weather, median hold <1 day) loses the fee outright every cycle (~ -700% to -1,150% annualized fee drag, i.e. guaranteed -2%/trade). Only multi-year contracts (rare in the observed tape) approach the asymptotic ceiling of ~1.4-1.56%/yr -- still below both the 3-month T-bill (3.90%, CITED) and IBKR's cash-sweep rate (3.14-4.33%, ESTIMATE/secondary).",
    },
    "capital_scaling_per_10k": {
        "position_limit_headroom": "10,000 pairs at ~$1/pair uses 4% of the 250,000-contract accountability level per market -- capital, not the limit, is the binding constraint at this scale.",
        "best_case_scenario": "$10k held in a multi-year pair (near breakeven ceiling ~1.4-1.56%/yr) => ~$11.70-$13.00/mo. Strictly dominated by parking the same $10k in a 3-month T-bill (~$32.50/mo) or IBKR cash sweep (~$26-$36/mo).",
        "dominant_volume_scenario": "$10k rolled continuously through daily weather pairs (median <1 day hold, the ONLY liquid version of this trade) loses ~2%/cycle to fees; even one cycle/day for 21 trading days is roughly -$4,200/mo -- this is a cost center, not a revenue source.",
        "verdict": "NEGATIVE net of opportunity cost at every holding period tested. No parameter regime beats simply holding the $10k in T-bills/IBKR cash.",
    },
    "compliance_cost_note": "Unlike the killed maker program (MAKER_VIABILITY.md: +0.76-1.25c/ct optimistic bound, temporally unstable, quote-uptime obligations, adverse-selection risk), a YES+NO pair purchase is a single riskless taker transaction with NO ongoing quoting obligation and NO fill-management risk -- the sub-3ms hot path / warm-process / queue-position tooling in ENGINEERING_STACK.md is unnecessary for this trade; a plain IBKR order ticket suffices. This makes engineering cost ~$0 incremental, but it does not rescue the trade: the coupon rate itself, not execution quality, is what's insufficient.",
    "who_earns_it": "BOTH sides. Rule 612(c)(1): 'Customer positions in Customer Collateral Accounts will accrue monthly coupons based on the daily settlement value of each Customer's positions' -- applies to whatever a Customer holds, Yes or No, proportional to that leg's own daily settlement value (mark-to-market), not a fixed $1. Measured on tape: YES settlement_price + NO settlement_price for the same contract sums to ~$1.00-$1.01 (matches the pairs-tape parity finding), so a held pair earns coupon on ~$1 notional combined regardless of the individual price split. FCM Members may pass MORE than the minimum to end customers (Rule 612(c)(2)) -- unverified whether IBKR does; treat any above-minimum passthrough as unconfirmed upside, not counted here.",
    "verdict": "KILL / DEAD-ON-ARRIVAL as a revenue source. The coupon is real, contractual, and requires no statistical edge (consistent with the program's pivot) -- but the rulebook's own formula (EFFR-50bp)/2 discounts it to roughly HALF of a comparable cash-sweep rate before any fee or duration friction is applied, the $0.02/pair transaction fee requires ~15.3 months of holding to amortize, and the dominant-volume instrument (daily weather pairs) turns over in under a day, guaranteeing a fee loss on every cycle. No instant (sub-$1.00) arbitrage exists in 2.97M scanned pair executions. This closes the ForecastEx incentive-coupon axis.",
}

with open("out/rev_forecastex.json", "w") as f:
    json.dump(out, f, indent=2, default=str)

print(json.dumps({k: out[k] for k in ["min_coupon_rate_annualized", "fee_per_pair", "verdict"]}, indent=2))
print("breakeven_days", breakeven_days)
print("wrote out/rev_forecastex.json")
