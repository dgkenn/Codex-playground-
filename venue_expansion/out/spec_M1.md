# spec_M1 -- macro-surprise pass-through drift into next-meeting Fed-decision market

Run: 2026-07-29T15:01:11.098255+00:00

## Data
- Shards read: all 16 (tape cached locally after a single shared filtered pass over all 16 HF trade shards)
- Local cached tape: 895660 trades, 2213 distinct tickers, span 2021-07-01 14:53:38.613666+00:00 .. 2026-01-28 23:59:36.702572+00:00
- Window: t0 in [2023-04-07, 2026-01-28]; FIT = release_date < 2025-01-01, VALIDATION = release_date >= that date (calendar split, frozen; #29's original 2026-04-01 TEST start is outside the archive entirely and unreachable, exactly as declared up front in the spec).
- FIT release events: 40; VALIDATION release events: 72
- Outcomes: Kalshi's own `result` field in the archived markets table (GROUNDING.md states this IS Kalshi's official settled outcome). Live reconciliation via GET /trade-api/v2/markets/{ticker} was attempted for every rung with a blank archive result, and separately spot-checked against a handful of settled family/Fed rungs spanning all 6 families -- **every single archived-era ticker 404s** on the live endpoint (a live KXHIGH weather ticker from the current week returns fine, confirming the endpoint itself works). This is the same live-API retention wall documented in REOPENABLE.md for /events; it blocks the spec's literal 'reconcile against GET /markets' instruction for anything in the archive window. DIVERGENCE, reported per non-negotiable 1: settlement truth for this run is the archive's `result` field alone; live reconciliation could not be performed on any archived-era ticker.
- Executable prices: entry = first trade with taker_side on our required side inside [t0+5m,t0+20m] (that trade's own yes_price/no_price, i.e. the price the taker actually paid, never mid, never best-in-window). Exit = first trade with the opposite taker_side inside [t0+60m,t0+120m], priced via the spec's own complement formula. Missing exit -> marked out at entry cost, both fees still charged, logged.

## Interpretive constructions required by the frozen spec text (documented, not bar-moving)
1. **Multi-ladder event collapse.** The spec defines a release EVENT as (family, calendar date) and explicitly gives EMPLOYMENT per-sub-series hawkish signs (payrolls +1, KXU3 -1), which only makes sense if multiple sub-ladders can be live for one event. The spec's u/z/x formulas are written per-event (singular), so this run computes u/z/x per LADDER (per exact series-month), then sets the event's x(e) = mean of the available per-ladder x_i(e). sigma_family remains a single pooled FIT MAD per family (all ladders in that family, as literally specified).
2. **Fee-inclusive breakeven for clause 5.** The spec names this without a formula. Implemented as breakeven_win_rate = mean(entry_price) + mean(entry_fee), both in dollars per contract -- the cost basis of acquiring the position, matching the clause's own text ('implied by the MEAN ENTRY PRICE'). Note fee(p) = fee(1-p) exactly (the formula is symmetric), so which literal print-side price is used for the exit leg's fee does not change any number in this run.

## FIT theta selection
- sigma_family (1.4826*MAD of FIT u, per family): {'CPI': 0.05189100000000004, 'EMPLOYMENT': 68866.76999999999, 'JOBLESS': None, 'PCE': None, 'GDP': 0.24388770000000012, 'ISM': None}
- FIT u sample sizes per family: {'CPI': 3, 'EMPLOYMENT': 2, 'JOBLESS': 0, 'PCE': 0, 'GDP': 4, 'ISM': 0}
- **sigma UNDEFINED for**: [('JOBLESS', 'zero or one FIT observation', 0), ('PCE', 'zero or one FIT observation', 0), ('ISM', 'zero or one FIT observation', 0)] -- these families have zero or one FIT-window release event in the archive (JOBLESS: legacy `JOBLESS` series ends 2022-12-01, `KXJOBLESSCLAIMS` does not start until 2025-06-12 -- there is a dead zone spanning the entire FIT window; ISM's `KXISMPMI` does not start until 2025-04-01, also entirely after FIT ends). **DIVERGENCE, reported per non-negotiable 1**: the frozen entry_rule requires sigma_family estimated ON FIT ONLY, with no fallback specified. Per the frozen rule, x(e) and hence the trigger are UNDEFINED for JOBLESS and ISM events -- every JOBLESS/ISM validation event is skipped for this reason, not improvised around with a pooled or validation-window sigma.
  - theta=0.5: n_trades=2, n_clusters=2, mean_net_c=-3, t=-3.0
  - theta=1.0: n_trades=1, n_clusters=1, mean_net_c=-2, t=None
  - theta=1.5: n_trades=0, n_clusters=0, mean_net_c=None, t=None
  - theta=2.0: n_trades=0, n_clusters=0, mean_net_c=None, t=None

**SELF-KILL: all FIT theta cells have day-clustered t <= 0 (self-kill); validation not opened.**


## VERDICT: NULL
Reason: all FIT theta cells have day-clustered t <= 0 (self-kill); validation not opened.

## Skip ledger (mandatory -- every dropped release event, with reason)
VALIDATION was never opened (self-kill fired at the FIT stage, per kill_conditions -- reading validation after a self-kill would itself be a non-negotiable-1 violation). The ledger below is every FIT-phase drop across all four theta trials (theta grid re-run means the same event can appear once per theta cell it was tried against).
Total skip-ledger entries: 140
By reason: {'ladder strikes unparseable': 4, 'no executable entry print': 9, 'no pre-t0 ladder print': 124, 'no exit print': 3}

<details><summary>full skip ledger</summary>

```
{"event": "ladder:JOBLESS-22APR02", "reason": "ladder strikes unparseable", "extra": {"event_ticker": "JOBLESS-22APR02", "n_bad": 1, "n_total": 1}}
{"event": "ladder:JOBLESS-22JUL23", "reason": "ladder strikes unparseable", "extra": {"event_ticker": "JOBLESS-22JUL23", "n_bad": 1, "n_total": 1}}
{"event": "ladder:JOBLESS-22SEP10", "reason": "ladder strikes unparseable", "extra": {"event_ticker": "JOBLESS-22SEP10", "n_bad": 1, "n_total": 1}}
{"event": "ladder:KXGDP-26JAN30", "reason": "ladder strikes unparseable", "extra": {"event_ticker": "KXGDP-26JAN30", "n_bad": 1, "n_total": 16}}
{"event": "CPI:2023-04-12", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23MAY-H25", "side": "no"}}
{"event": "CPI:2023-05-10", "reason": "no usable ladder (CPI-23APR:no pre-t0 ladder print; CPIYOY-23APR:no pre-t0 ladder print; CPICORE-23APR:no pre-t0 ladder print; CPICOREYOY-23APR:no pre-t0 ladder print)"}
{"event": "CPI:2023-06-13", "reason": "no usable ladder (CPI-23MAY:no pre-t0 ladder print; CPIYOY-23MAY:no pre-t0 ladder print; CPICORE-23MAY:no pre-t0 ladder print; CPICOREYOY-23MAY:no pre-t0 ladder print)"}
{"event": "CPI:2023-07-12", "reason": "no usable ladder (CPI-23JUN:no pre-t0 ladder print; CPIYOY-23JUN:no pre-t0 ladder print; CPICORE-23JUN:no pre-t0 ladder print; CPICOREYOY-23JUN:no pre-t0 ladder print)"}
{"event": "GDP:2023-07-27", "reason": "no exit print in [t0+60m,t0+120m]", "extra": {"target": "FEDDECISION-23SEP-H25", "side": "yes"}}
{"event": "CPI:2023-08-10", "reason": "no usable ladder (CPI-23JUL:no pre-t0 ladder print; CPIYOY-23JUL:no pre-t0 ladder print; CPICORE-23JUL:no pre-t0 ladder print; CPICOREYOY-23JUL:no pre-t0 ladder print)"}
{"event": "CPI:2023-09-13", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23SEP-H25", "side": "no"}}
{"event": "CPI:2023-10-12", "reason": "no usable ladder (CPI-23SEP:no pre-t0 ladder print; CPIYOY-23SEP:no pre-t0 ladder print; CPICORE-23SEP:no pre-t0 ladder print; CPICOREYOY-23SEP:no pre-t0 ladder print)"}
{"event": "GDP:2023-10-26", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23NOV-H25", "side": "yes"}}
{"event": "PCE:2023-10-27", "reason": "no usable ladder (PCECORE-23SEP:no pre-t0 ladder print)"}
{"event": "CPI:2023-11-14", "reason": "no usable ladder (CPI-23OCT:no pre-t0 ladder print; CPIYOY-23OCT:no pre-t0 ladder print; CPICORE-23OCT:no pre-t0 ladder print; CPICOREYOY-23OCT:no pre-t0 ladder print)"}
{"event": "CPI:2023-12-12", "reason": "no usable ladder (CPI-23NOV:no pre-t0 ladder print; CPIYOY-23NOV:no pre-t0 ladder print; CPICORE-23NOV:no pre-t0 ladder print; CPICOREYOY-23NOV:no pre-t0 ladder print)"}
{"event": "CPI:2024-01-11", "reason": "no usable ladder (CPI-23DEC:no pre-t0 ladder print; CPICORE-23DEC:no pre-t0 ladder print; CPIYOY-23DEC:no pre-t0 ladder print; CPICOREYOY-23DEC:no pre-t0 ladder print)"}
{"event": "GDP:2024-01-25", "reason": "no usable ladder (GDP-24JAN26:no pre-t0 ladder print)"}
{"event": "CPI:2024-02-13", "reason": "no usable ladder (CPI-24JAN:no pre-t0 ladder print; CPICORE-24JAN:no pre-t0 ladder print; CPIYOY-24JAN:no pre-t0 ladder print; CPICOREYOY-24JAN:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-03-08", "reason": "no usable ladder (PAYROLLS-24FEB:no pre-t0 ladder print)"}
{"event": "CPI:2024-03-12", "reason": "no usable ladder (CPI-24FEB:no pre-t0 ladder print; CPIYOY-24FEB:no pre-t0 ladder print; CPICORE-24FEB:no pre-t0 ladder print; CPICOREYOY-24FEB:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-04-05", "reason": "no usable ladder (PAYROLLS-24MAR:no pre-t0 ladder print)"}
{"event": "CPI:2024-04-10", "reason": "no usable ladder (CPI-24MAR:no pre-t0 ladder print; CPICORE-24MAR:no pre-t0 ladder print; CPIYOY-24MAR:no pre-t0 ladder print; CPICOREYOY-24MAR:no pre-t0 ladder print)"}
{"event": "GDP:2024-04-25", "reason": "no usable ladder (GDP-24APR25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-05-03", "reason": "no usable ladder (PAYROLLS-24APR:no pre-t0 ladder print)"}
{"event": "CPI:2024-05-15", "reason": "no usable ladder (CPIYOY-24APR:no pre-t0 ladder print; CPICOREYOY-24APR:no pre-t0 ladder print; CPI-24APR:no pre-t0 ladder print; CPICORE-24APR:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-06-07", "reason": "no usable ladder (PAYROLLS-24MAY:no pre-t0 ladder print)"}
{"event": "CPI:2024-06-12", "reason": "no usable ladder (CPIYOY-24MAY:no pre-t0 ladder print; CPICOREYOY-24MAY:no pre-t0 ladder print; CPI-24MAY:no pre-t0 ladder print; CPICORE-24MAY:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-07-05", "reason": "no usable ladder (PAYROLLS-24JUN:no pre-t0 ladder print)"}
{"event": "CPI:2024-07-11", "reason": "no usable ladder (CPIYOY-24JUN:no pre-t0 ladder print; CPICOREYOY-24JUN:no pre-t0 ladder print; CPI-24JUN:no pre-t0 ladder print; CPICORE-24JUN:no pre-t0 ladder print)"}
{"event": "GDP:2024-07-25", "reason": "no usable ladder (GDP-24JUL25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-08-02", "reason": "no usable ladder (PAYROLLS-24JUL:no pre-t0 ladder print)"}
{"event": "CPI:2024-08-14", "reason": "no usable ladder (CPIYOY-24JUL:no pre-t0 ladder print; CPICOREYOY-24JUL:no pre-t0 ladder print; CPI-24JUL:no pre-t0 ladder print; CPICORE-24JUL:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-09-06", "reason": "no usable ladder (PAYROLLS-24AUG:no pre-t0 ladder print)"}
{"event": "CPI:2024-09-11", "reason": "no usable ladder (CPIYOY-24AUG:no pre-t0 ladder print; CPICOREYOY-24AUG:no pre-t0 ladder print; CPI-24AUG:no pre-t0 ladder print; CPICORE-24AUG:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-10-04", "reason": "no usable ladder (PAYROLLS-24SEP:no pre-t0 ladder print)"}
{"event": "CPI:2024-10-10", "reason": "no usable ladder (CPIYOY-24SEP:no pre-t0 ladder print; CPICOREYOY-24SEP:no pre-t0 ladder print; CPI-24SEP:no pre-t0 ladder print; CPICORE-24SEP:no pre-t0 ladder print)"}
{"event": "GDP:2024-10-30", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-24NOV-C26", "side": "yes"}}
{"event": "EMPLOYMENT:2024-11-01", "reason": "no exit print in [t0+60m,t0+120m]", "extra": {"target": "FEDDECISION-24NOV-C26", "side": "yes"}}
{"event": "CPI:2024-11-13", "reason": "no usable ladder (CPIYOY-24OCT:no pre-t0 ladder print; CPICOREYOY-24OCT:no pre-t0 ladder print; CPI-24OCT:no pre-t0 ladder print; CPICORE-24OCT:no pre-t0 ladder print)"}
{"event": "PCE:2024-12-20", "reason": "no usable ladder (KXPCECORE-24NOV:no pre-t0 ladder print)"}
{"event": "CPI:2023-04-12", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23MAY-H25", "side": "no"}}
{"event": "CPI:2023-05-10", "reason": "no usable ladder (CPI-23APR:no pre-t0 ladder print; CPIYOY-23APR:no pre-t0 ladder print; CPICORE-23APR:no pre-t0 ladder print; CPICOREYOY-23APR:no pre-t0 ladder print)"}
{"event": "CPI:2023-06-13", "reason": "no usable ladder (CPI-23MAY:no pre-t0 ladder print; CPIYOY-23MAY:no pre-t0 ladder print; CPICORE-23MAY:no pre-t0 ladder print; CPICOREYOY-23MAY:no pre-t0 ladder print)"}
{"event": "CPI:2023-07-12", "reason": "no usable ladder (CPI-23JUN:no pre-t0 ladder print; CPIYOY-23JUN:no pre-t0 ladder print; CPICORE-23JUN:no pre-t0 ladder print; CPICOREYOY-23JUN:no pre-t0 ladder print)"}
{"event": "CPI:2023-08-10", "reason": "no usable ladder (CPI-23JUL:no pre-t0 ladder print; CPIYOY-23JUL:no pre-t0 ladder print; CPICORE-23JUL:no pre-t0 ladder print; CPICOREYOY-23JUL:no pre-t0 ladder print)"}
{"event": "CPI:2023-10-12", "reason": "no usable ladder (CPI-23SEP:no pre-t0 ladder print; CPIYOY-23SEP:no pre-t0 ladder print; CPICORE-23SEP:no pre-t0 ladder print; CPICOREYOY-23SEP:no pre-t0 ladder print)"}
{"event": "GDP:2023-10-26", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23NOV-H25", "side": "yes"}}
{"event": "PCE:2023-10-27", "reason": "no usable ladder (PCECORE-23SEP:no pre-t0 ladder print)"}
{"event": "CPI:2023-11-14", "reason": "no usable ladder (CPI-23OCT:no pre-t0 ladder print; CPIYOY-23OCT:no pre-t0 ladder print; CPICORE-23OCT:no pre-t0 ladder print; CPICOREYOY-23OCT:no pre-t0 ladder print)"}
{"event": "CPI:2023-12-12", "reason": "no usable ladder (CPI-23NOV:no pre-t0 ladder print; CPIYOY-23NOV:no pre-t0 ladder print; CPICORE-23NOV:no pre-t0 ladder print; CPICOREYOY-23NOV:no pre-t0 ladder print)"}
{"event": "CPI:2024-01-11", "reason": "no usable ladder (CPI-23DEC:no pre-t0 ladder print; CPICORE-23DEC:no pre-t0 ladder print; CPIYOY-23DEC:no pre-t0 ladder print; CPICOREYOY-23DEC:no pre-t0 ladder print)"}
{"event": "GDP:2024-01-25", "reason": "no usable ladder (GDP-24JAN26:no pre-t0 ladder print)"}
{"event": "CPI:2024-02-13", "reason": "no usable ladder (CPI-24JAN:no pre-t0 ladder print; CPICORE-24JAN:no pre-t0 ladder print; CPIYOY-24JAN:no pre-t0 ladder print; CPICOREYOY-24JAN:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-03-08", "reason": "no usable ladder (PAYROLLS-24FEB:no pre-t0 ladder print)"}
{"event": "CPI:2024-03-12", "reason": "no usable ladder (CPI-24FEB:no pre-t0 ladder print; CPIYOY-24FEB:no pre-t0 ladder print; CPICORE-24FEB:no pre-t0 ladder print; CPICOREYOY-24FEB:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-04-05", "reason": "no usable ladder (PAYROLLS-24MAR:no pre-t0 ladder print)"}
{"event": "CPI:2024-04-10", "reason": "no usable ladder (CPI-24MAR:no pre-t0 ladder print; CPICORE-24MAR:no pre-t0 ladder print; CPIYOY-24MAR:no pre-t0 ladder print; CPICOREYOY-24MAR:no pre-t0 ladder print)"}
{"event": "GDP:2024-04-25", "reason": "no usable ladder (GDP-24APR25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-05-03", "reason": "no usable ladder (PAYROLLS-24APR:no pre-t0 ladder print)"}
{"event": "CPI:2024-05-15", "reason": "no usable ladder (CPIYOY-24APR:no pre-t0 ladder print; CPICOREYOY-24APR:no pre-t0 ladder print; CPI-24APR:no pre-t0 ladder print; CPICORE-24APR:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-06-07", "reason": "no usable ladder (PAYROLLS-24MAY:no pre-t0 ladder print)"}
{"event": "CPI:2024-06-12", "reason": "no usable ladder (CPIYOY-24MAY:no pre-t0 ladder print; CPICOREYOY-24MAY:no pre-t0 ladder print; CPI-24MAY:no pre-t0 ladder print; CPICORE-24MAY:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-07-05", "reason": "no usable ladder (PAYROLLS-24JUN:no pre-t0 ladder print)"}
{"event": "CPI:2024-07-11", "reason": "no usable ladder (CPIYOY-24JUN:no pre-t0 ladder print; CPICOREYOY-24JUN:no pre-t0 ladder print; CPI-24JUN:no pre-t0 ladder print; CPICORE-24JUN:no pre-t0 ladder print)"}
{"event": "GDP:2024-07-25", "reason": "no usable ladder (GDP-24JUL25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-08-02", "reason": "no usable ladder (PAYROLLS-24JUL:no pre-t0 ladder print)"}
{"event": "CPI:2024-08-14", "reason": "no usable ladder (CPIYOY-24JUL:no pre-t0 ladder print; CPICOREYOY-24JUL:no pre-t0 ladder print; CPI-24JUL:no pre-t0 ladder print; CPICORE-24JUL:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-09-06", "reason": "no usable ladder (PAYROLLS-24AUG:no pre-t0 ladder print)"}
{"event": "CPI:2024-09-11", "reason": "no usable ladder (CPIYOY-24AUG:no pre-t0 ladder print; CPICOREYOY-24AUG:no pre-t0 ladder print; CPI-24AUG:no pre-t0 ladder print; CPICORE-24AUG:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-10-04", "reason": "no usable ladder (PAYROLLS-24SEP:no pre-t0 ladder print)"}
{"event": "CPI:2024-10-10", "reason": "no usable ladder (CPIYOY-24SEP:no pre-t0 ladder print; CPICOREYOY-24SEP:no pre-t0 ladder print; CPI-24SEP:no pre-t0 ladder print; CPICORE-24SEP:no pre-t0 ladder print)"}
{"event": "GDP:2024-10-30", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-24NOV-C26", "side": "yes"}}
{"event": "EMPLOYMENT:2024-11-01", "reason": "no exit print in [t0+60m,t0+120m]", "extra": {"target": "FEDDECISION-24NOV-C26", "side": "yes"}}
{"event": "CPI:2024-11-13", "reason": "no usable ladder (CPIYOY-24OCT:no pre-t0 ladder print; CPICOREYOY-24OCT:no pre-t0 ladder print; CPI-24OCT:no pre-t0 ladder print; CPICORE-24OCT:no pre-t0 ladder print)"}
{"event": "PCE:2024-12-20", "reason": "no usable ladder (KXPCECORE-24NOV:no pre-t0 ladder print)"}
{"event": "CPI:2023-04-12", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23MAY-H25", "side": "no"}}
{"event": "CPI:2023-05-10", "reason": "no usable ladder (CPI-23APR:no pre-t0 ladder print; CPIYOY-23APR:no pre-t0 ladder print; CPICORE-23APR:no pre-t0 ladder print; CPICOREYOY-23APR:no pre-t0 ladder print)"}
{"event": "CPI:2023-06-13", "reason": "no usable ladder (CPI-23MAY:no pre-t0 ladder print; CPIYOY-23MAY:no pre-t0 ladder print; CPICORE-23MAY:no pre-t0 ladder print; CPICOREYOY-23MAY:no pre-t0 ladder print)"}
{"event": "CPI:2023-07-12", "reason": "no usable ladder (CPI-23JUN:no pre-t0 ladder print; CPIYOY-23JUN:no pre-t0 ladder print; CPICORE-23JUN:no pre-t0 ladder print; CPICOREYOY-23JUN:no pre-t0 ladder print)"}
{"event": "CPI:2023-08-10", "reason": "no usable ladder (CPI-23JUL:no pre-t0 ladder print; CPIYOY-23JUL:no pre-t0 ladder print; CPICORE-23JUL:no pre-t0 ladder print; CPICOREYOY-23JUL:no pre-t0 ladder print)"}
{"event": "CPI:2023-10-12", "reason": "no usable ladder (CPI-23SEP:no pre-t0 ladder print; CPIYOY-23SEP:no pre-t0 ladder print; CPICORE-23SEP:no pre-t0 ladder print; CPICOREYOY-23SEP:no pre-t0 ladder print)"}
{"event": "PCE:2023-10-27", "reason": "no usable ladder (PCECORE-23SEP:no pre-t0 ladder print)"}
{"event": "CPI:2023-11-14", "reason": "no usable ladder (CPI-23OCT:no pre-t0 ladder print; CPIYOY-23OCT:no pre-t0 ladder print; CPICORE-23OCT:no pre-t0 ladder print; CPICOREYOY-23OCT:no pre-t0 ladder print)"}
{"event": "CPI:2023-12-12", "reason": "no usable ladder (CPI-23NOV:no pre-t0 ladder print; CPIYOY-23NOV:no pre-t0 ladder print; CPICORE-23NOV:no pre-t0 ladder print; CPICOREYOY-23NOV:no pre-t0 ladder print)"}
{"event": "CPI:2024-01-11", "reason": "no usable ladder (CPI-23DEC:no pre-t0 ladder print; CPICORE-23DEC:no pre-t0 ladder print; CPIYOY-23DEC:no pre-t0 ladder print; CPICOREYOY-23DEC:no pre-t0 ladder print)"}
{"event": "GDP:2024-01-25", "reason": "no usable ladder (GDP-24JAN26:no pre-t0 ladder print)"}
{"event": "CPI:2024-02-13", "reason": "no usable ladder (CPI-24JAN:no pre-t0 ladder print; CPICORE-24JAN:no pre-t0 ladder print; CPIYOY-24JAN:no pre-t0 ladder print; CPICOREYOY-24JAN:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-03-08", "reason": "no usable ladder (PAYROLLS-24FEB:no pre-t0 ladder print)"}
{"event": "CPI:2024-03-12", "reason": "no usable ladder (CPI-24FEB:no pre-t0 ladder print; CPIYOY-24FEB:no pre-t0 ladder print; CPICORE-24FEB:no pre-t0 ladder print; CPICOREYOY-24FEB:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-04-05", "reason": "no usable ladder (PAYROLLS-24MAR:no pre-t0 ladder print)"}
{"event": "CPI:2024-04-10", "reason": "no usable ladder (CPI-24MAR:no pre-t0 ladder print; CPICORE-24MAR:no pre-t0 ladder print; CPIYOY-24MAR:no pre-t0 ladder print; CPICOREYOY-24MAR:no pre-t0 ladder print)"}
{"event": "GDP:2024-04-25", "reason": "no usable ladder (GDP-24APR25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-05-03", "reason": "no usable ladder (PAYROLLS-24APR:no pre-t0 ladder print)"}
{"event": "CPI:2024-05-15", "reason": "no usable ladder (CPIYOY-24APR:no pre-t0 ladder print; CPICOREYOY-24APR:no pre-t0 ladder print; CPI-24APR:no pre-t0 ladder print; CPICORE-24APR:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-06-07", "reason": "no usable ladder (PAYROLLS-24MAY:no pre-t0 ladder print)"}
{"event": "CPI:2024-06-12", "reason": "no usable ladder (CPIYOY-24MAY:no pre-t0 ladder print; CPICOREYOY-24MAY:no pre-t0 ladder print; CPI-24MAY:no pre-t0 ladder print; CPICORE-24MAY:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-07-05", "reason": "no usable ladder (PAYROLLS-24JUN:no pre-t0 ladder print)"}
{"event": "CPI:2024-07-11", "reason": "no usable ladder (CPIYOY-24JUN:no pre-t0 ladder print; CPICOREYOY-24JUN:no pre-t0 ladder print; CPI-24JUN:no pre-t0 ladder print; CPICORE-24JUN:no pre-t0 ladder print)"}
{"event": "GDP:2024-07-25", "reason": "no usable ladder (GDP-24JUL25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-08-02", "reason": "no usable ladder (PAYROLLS-24JUL:no pre-t0 ladder print)"}
{"event": "CPI:2024-08-14", "reason": "no usable ladder (CPIYOY-24JUL:no pre-t0 ladder print; CPICOREYOY-24JUL:no pre-t0 ladder print; CPI-24JUL:no pre-t0 ladder print; CPICORE-24JUL:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-09-06", "reason": "no usable ladder (PAYROLLS-24AUG:no pre-t0 ladder print)"}
{"event": "CPI:2024-09-11", "reason": "no usable ladder (CPIYOY-24AUG:no pre-t0 ladder print; CPICOREYOY-24AUG:no pre-t0 ladder print; CPI-24AUG:no pre-t0 ladder print; CPICORE-24AUG:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-10-04", "reason": "no usable ladder (PAYROLLS-24SEP:no pre-t0 ladder print)"}
{"event": "CPI:2024-10-10", "reason": "no usable ladder (CPIYOY-24SEP:no pre-t0 ladder print; CPICOREYOY-24SEP:no pre-t0 ladder print; CPI-24SEP:no pre-t0 ladder print; CPICORE-24SEP:no pre-t0 ladder print)"}
{"event": "CPI:2024-11-13", "reason": "no usable ladder (CPIYOY-24OCT:no pre-t0 ladder print; CPICOREYOY-24OCT:no pre-t0 ladder print; CPI-24OCT:no pre-t0 ladder print; CPICORE-24OCT:no pre-t0 ladder print)"}
{"event": "PCE:2024-12-20", "reason": "no usable ladder (KXPCECORE-24NOV:no pre-t0 ladder print)"}
{"event": "CPI:2023-04-12", "reason": "no executable entry print in [t0+5m,t0+20m]", "extra": {"target": "FEDDECISION-23MAY-H25", "side": "no"}}
{"event": "CPI:2023-05-10", "reason": "no usable ladder (CPI-23APR:no pre-t0 ladder print; CPIYOY-23APR:no pre-t0 ladder print; CPICORE-23APR:no pre-t0 ladder print; CPICOREYOY-23APR:no pre-t0 ladder print)"}
{"event": "CPI:2023-06-13", "reason": "no usable ladder (CPI-23MAY:no pre-t0 ladder print; CPIYOY-23MAY:no pre-t0 ladder print; CPICORE-23MAY:no pre-t0 ladder print; CPICOREYOY-23MAY:no pre-t0 ladder print)"}
{"event": "CPI:2023-07-12", "reason": "no usable ladder (CPI-23JUN:no pre-t0 ladder print; CPIYOY-23JUN:no pre-t0 ladder print; CPICORE-23JUN:no pre-t0 ladder print; CPICOREYOY-23JUN:no pre-t0 ladder print)"}
{"event": "CPI:2023-08-10", "reason": "no usable ladder (CPI-23JUL:no pre-t0 ladder print; CPIYOY-23JUL:no pre-t0 ladder print; CPICORE-23JUL:no pre-t0 ladder print; CPICOREYOY-23JUL:no pre-t0 ladder print)"}
{"event": "CPI:2023-10-12", "reason": "no usable ladder (CPI-23SEP:no pre-t0 ladder print; CPIYOY-23SEP:no pre-t0 ladder print; CPICORE-23SEP:no pre-t0 ladder print; CPICOREYOY-23SEP:no pre-t0 ladder print)"}
{"event": "PCE:2023-10-27", "reason": "no usable ladder (PCECORE-23SEP:no pre-t0 ladder print)"}
{"event": "CPI:2023-11-14", "reason": "no usable ladder (CPI-23OCT:no pre-t0 ladder print; CPIYOY-23OCT:no pre-t0 ladder print; CPICORE-23OCT:no pre-t0 ladder print; CPICOREYOY-23OCT:no pre-t0 ladder print)"}
{"event": "CPI:2023-12-12", "reason": "no usable ladder (CPI-23NOV:no pre-t0 ladder print; CPIYOY-23NOV:no pre-t0 ladder print; CPICORE-23NOV:no pre-t0 ladder print; CPICOREYOY-23NOV:no pre-t0 ladder print)"}
{"event": "CPI:2024-01-11", "reason": "no usable ladder (CPI-23DEC:no pre-t0 ladder print; CPICORE-23DEC:no pre-t0 ladder print; CPIYOY-23DEC:no pre-t0 ladder print; CPICOREYOY-23DEC:no pre-t0 ladder print)"}
{"event": "GDP:2024-01-25", "reason": "no usable ladder (GDP-24JAN26:no pre-t0 ladder print)"}
{"event": "CPI:2024-02-13", "reason": "no usable ladder (CPI-24JAN:no pre-t0 ladder print; CPICORE-24JAN:no pre-t0 ladder print; CPIYOY-24JAN:no pre-t0 ladder print; CPICOREYOY-24JAN:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-03-08", "reason": "no usable ladder (PAYROLLS-24FEB:no pre-t0 ladder print)"}
{"event": "CPI:2024-03-12", "reason": "no usable ladder (CPI-24FEB:no pre-t0 ladder print; CPIYOY-24FEB:no pre-t0 ladder print; CPICORE-24FEB:no pre-t0 ladder print; CPICOREYOY-24FEB:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-04-05", "reason": "no usable ladder (PAYROLLS-24MAR:no pre-t0 ladder print)"}
{"event": "CPI:2024-04-10", "reason": "no usable ladder (CPI-24MAR:no pre-t0 ladder print; CPICORE-24MAR:no pre-t0 ladder print; CPIYOY-24MAR:no pre-t0 ladder print; CPICOREYOY-24MAR:no pre-t0 ladder print)"}
{"event": "GDP:2024-04-25", "reason": "no usable ladder (GDP-24APR25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-05-03", "reason": "no usable ladder (PAYROLLS-24APR:no pre-t0 ladder print)"}
{"event": "CPI:2024-05-15", "reason": "no usable ladder (CPIYOY-24APR:no pre-t0 ladder print; CPICOREYOY-24APR:no pre-t0 ladder print; CPI-24APR:no pre-t0 ladder print; CPICORE-24APR:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-06-07", "reason": "no usable ladder (PAYROLLS-24MAY:no pre-t0 ladder print)"}
{"event": "CPI:2024-06-12", "reason": "no usable ladder (CPIYOY-24MAY:no pre-t0 ladder print; CPICOREYOY-24MAY:no pre-t0 ladder print; CPI-24MAY:no pre-t0 ladder print; CPICORE-24MAY:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-07-05", "reason": "no usable ladder (PAYROLLS-24JUN:no pre-t0 ladder print)"}
{"event": "CPI:2024-07-11", "reason": "no usable ladder (CPIYOY-24JUN:no pre-t0 ladder print; CPICOREYOY-24JUN:no pre-t0 ladder print; CPI-24JUN:no pre-t0 ladder print; CPICORE-24JUN:no pre-t0 ladder print)"}
{"event": "GDP:2024-07-25", "reason": "no usable ladder (GDP-24JUL25:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-08-02", "reason": "no usable ladder (PAYROLLS-24JUL:no pre-t0 ladder print)"}
{"event": "CPI:2024-08-14", "reason": "no usable ladder (CPIYOY-24JUL:no pre-t0 ladder print; CPICOREYOY-24JUL:no pre-t0 ladder print; CPI-24JUL:no pre-t0 ladder print; CPICORE-24JUL:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-09-06", "reason": "no usable ladder (PAYROLLS-24AUG:no pre-t0 ladder print)"}
{"event": "CPI:2024-09-11", "reason": "no usable ladder (CPIYOY-24AUG:no pre-t0 ladder print; CPICOREYOY-24AUG:no pre-t0 ladder print; CPI-24AUG:no pre-t0 ladder print; CPICORE-24AUG:no pre-t0 ladder print)"}
{"event": "EMPLOYMENT:2024-10-04", "reason": "no usable ladder (PAYROLLS-24SEP:no pre-t0 ladder print)"}
{"event": "CPI:2024-10-10", "reason": "no usable ladder (CPIYOY-24SEP:no pre-t0 ladder print; CPICOREYOY-24SEP:no pre-t0 ladder print; CPI-24SEP:no pre-t0 ladder print; CPICORE-24SEP:no pre-t0 ladder print)"}
{"event": "CPI:2024-11-13", "reason": "no usable ladder (CPIYOY-24OCT:no pre-t0 ladder print; CPICOREYOY-24OCT:no pre-t0 ladder print; CPI-24OCT:no pre-t0 ladder print; CPICORE-24OCT:no pre-t0 ladder print)"}
{"event": "PCE:2024-12-20", "reason": "no usable ladder (KXPCECORE-24NOV:no pre-t0 ladder print)"}
```
</details>

## Reproduce
```
python venue_expansion/cache/prereg/m1_markets_pull.py   # -> cache/M1/markets_universe.json
python venue_expansion/cache/prereg/m1_build_events.py   # -> cache/M1/events.json
python venue_expansion/cache/prereg/m1_tape_pull.py      # -> cache/prereg/tape/shard-*.parquet (all 16)
python venue_expansion/spec_M1.py                        # -> out/spec_M1.json, out/spec_M1.md
```