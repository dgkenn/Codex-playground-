# Day-1 live-data mining — 10 high-leverage improvements

Three parallel analyses on the first full day of live + rich-collector data:
profitability forensics, adverse-selection markouts, and rich-stream completion
predictors. **Standing caveat: live n is tiny (6–17 windows, 30–228 markout rows).**
Live findings are HYPOTHESES — they either corroborate the 20,318-fill tape or must be
validated on it before becoming money-path gates. The single coherent picture across all
three: **the entire risk is the unpaired leg.** Completed boxes are locked and immune to
markout; everything that loses is a leg that never paired and rode to settlement.

## The $16->$11 giveback
Was **−$0.94 concentrated in 2 windows** (12:15Z, 12:45Z) — noise-level at ±$1–2/window
natural variance, NOT a regime break. Both losses were unpaired directional inventory
settling wrong. Cancel-fails did NOT cause them (they correlate +0.22 with PnL).

## The 10, ranked by leverage × confidence

### Deployed this session
1. **Tau-scaled completion** [inventory/PnL] — the actual bug: the `tau_guard` blocked ALL
   late-window placement *including the completing leg*, so unpaired legs were forbidden
   from pairing in the last 150s and rode to settlement (−66¢/−31¢). Fix: completing quotes
   (that reduce |net|) now bypass tau_guard, and the min-lock floor ramps from 0 toward
   −`close_max_give` (4¢) as tau→0 — a bounded certain lock beats the directional tail.
   Confidence HIGH (risk-reducing, addresses the only real losses). `--close-flatten-tau 120`.

### Deploy-ready (tape-backed / low risk) — next
2. **Second-leg queue priority** [completion/exec] — passive open, but improve to FRONT of
   the completing side's queue once one leg fills, floored at a positive lock. Tape:
   front-of-queue worth +4.7¢/win. Raises P(complete | one filled) without paying up.
3. **Reprice-to-complete hung legs** [completion] — walk the unfilled leg toward the moved
   touch (min-lock floored, cancel-batched) instead of leaving it stranded.

### Validate-first on the 20k tape (live n too small for a money-path gate)
4. **Bilateral-thinness entry gate** [completion] — thin BOTH books (top-5 depth <~5.5k) →
   ~75% completion; thick → ~0% (live r≈−0.69, n=14). Strongest new completion signal, and
   intuitive (thin book = takers sweep to our bids). Wire the depth feature, confirm on tape.
5. **OI-churn gate** [completion/adverse-sel] — rising open-interest windows (informed
   one-sided positioning) complete slower/worse (live r=+0.97 vs time-to-complete, n=6 — big
   effect, tiny sample). Flat/falling OI = benign churn = completes.
6. **Price-bucket gate 0.60–0.80** [adverse-sel] — 60s markout −6.9¢ there (n=5). May be a
   single-day trend artifact (0.6–0.8 = directionally-leaning = same as the trend); validate.
7. **YES/NO asymmetry** [adverse-sel] — yes fills −2.2¢ vs no +2.9¢ @60s (n=11 each). Almost
   certainly this-day BTC drift, NOT structural. Do NOT hard-code a side penalty; test
   whether it persists across multiple days/assets first.
8. **1¢-book reconsideration** [exec] — captured half-spread ≈ −0.02¢ on 1¢ books (56% of
   fills negative); +3.5¢ on 2¢ books. The `--min-spread 0.01` deploy is marginal — but only
   because 1¢-book value lives entirely in COMPLETION (a completed 1¢ box still locks 1¢;
   an unpaired one is toxic). A/B 0.01 vs 0.02 on the tape *under the new completion logic*.

### Ops / instrumentation
9. **Cancel reliability** [exec/ops] — 35 cancel-fails; pairing efficiency fell 100%→88%
   post-deploy as stray orders became unpaired legs. Harden cancel confirm/retry.
10. **Stale-quote refresh / mid-anchoring** [adverse-sel/market-impact] — fills at 60–300s
    into the window decay to ~0 then −2.8¢ by 300s; re-center quotes on mid moves before they
    go stale (also helps completion by keeping both legs near the touch).

## Markout curve (carried-inventory adverse selection, all fills)
5s −1.0¢ · 30s +0.9¢ · 60s +0.4¢ · **300s −2.8¢** — benign at the horizons a box completes
in (median time-to-complete 82s), toxic only for legs carried long. Reinforces #1–#5:
complete fast or don't carry.

## Rich-stream completion predictors (the newly-collected, now-actionable data)
| signal | direction | live r | n |
|---|---|---|---|
| bilateral book thinness | thin → completes | −0.69 | 14 |
| rising open interest | rising → slow/incomplete | +0.97 (TTC) | 6 |
| early flow volume | high → slow (one-sided) | +0.75 (TTC) | 7 |
| RTT median | ~54ms, in-region | — | 15 |

Median time-to-complete 82s; thin-book windows complete ~75% vs deep-book ~0%.
