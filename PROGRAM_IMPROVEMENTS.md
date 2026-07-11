# Program improvements toward a constantly profitable strategy

Companion to `WINNING_STRATEGY.md` (the 32-day verdict) and the updated `strategies.py`
(new ensemble arms + forward-verdict pruning). These are not hypotheticals — each item below
is a gap the month of data actually exposed, ordered by expected impact.

## 1. The meta-lesson the month taught: only forward data counts here

Every lab-validated winner failed forward:

| variant | lab evidence | 32-day forward |
|---|---|---|
| micro_gate | "THE deployed edge (+4.8/win)" | Δ = +0.000 every day (gate never fires) |
| micro_strict | gate_lab t=+6.2 | −4.47/win, positive 0/32 days (dead last) |
| micro_asym | gate_lab t=+7.5 ("highest") | −0.52/win, t=−3.09 |
| ufat_band | combo_lab best IS+OOS | −3.47/win, t=−6.10 |
| ufat_skew15 | replay holdout Calmar 40.6 vs 31.0 | −3.81/win, t=−7.07 |

Meanwhile the two forward winners (`av_stoikov`, `mo_size`) came from *principled mechanisms*
(inventory variance penalty; continuous adverse-selection sizing), not fitted gates.
**Institutionalize it:** no strategy goes live off replay/lab stats alone; the pre-registered
forward bar in `strategies.py` (≥14 days, day-clustered t≥3, gross+ ≥80% of days) is the only
promotion path. This is now written into the roster file so it survives us.

## 2. Deployed-edge decay alarm (the most expensive silent failure)

`micro_gate` ran as THE deployed strategy for a month while its shadow twin printed
Δ=+0.000 vs baseline **every single day** — and nothing alerted. `strategy-alert.yml` only
fires when a *candidate* crosses +2σ; nothing watches the *incumbent*.

**Add:** in the hourly alert job, compute the deployed variant's rolling 14-day edge vs
baseline; alert if |Δ|≈0 (inert) or t<−2 (decayed). An edge that stops working should page
you the same week, not be discovered in a month-end review.

## 3. Content-validity checks, not just freshness checks

`health_check.py` verifies streams are *fresh*, so `copy_multi_results/` passed health for a
month while writing literally `{}` in all 10 files.

**Add to health_check:** per-stream minimum-payload assertions (non-empty JSON, ≥N rows for
jsonl, expected keys present). Fix or retire the `copy_multi` collector itself.

## 4. Statistical power: more windows/day

8–12 de-duped windows/day meant single-day paired-t was almost never decisive; the verdict
needed a full month. To cut promote cycles from ~30 days toward ~10:
- collect more windows per cycle (more market windows per hour; the 15m markets give 4/hr each),
- extend the shadow comparison to the other collected assets (eth/sol/xrp streams already land
  on gha-data; the SUMMARY currently reflects far fewer files than the collectors produce),
- report **day-clustered** t everywhere (windows within a day are correlated; the current
  ≥100-window |t|>2 bar is anti-conservative — the same-day windows share regime).

## 5. Regime features per window (the baseline drifted +0.55 → +27/win)

Absolute P&L was mostly regime, not skill, this month. Tag every shadow window record with:
realized spot vol, average spread, taker-flow intensity, time-of-day, distance-to-close
profile. Then:
- conditional leaderboards ("does av_stoikov hold in low-vol?"),
- a regime-switching ensemble becomes testable: `mo_size` won all 3 days `av_stoikov` lost —
  if those days share a signature (likely choppy/low-vol), a switcher beats both. That is the
  most credible path from "usually profitable" to "constantly profitable".

## 6. Fill realism before real money

Shadow fills assume 1-tick-at-the-touch with queue modeling. Before sizing up, reconcile
shadow fills against the *actual* fills stream (already collected per-asset on gha-data):
fill-rate, queue-position error, adverse-selection difference. A strategy that is +4.7/win in
shadow but can't get filled in reality is still a zero.

## 7. Rebate sensitivity / venue portability

Both winners are gross-positive 32/32 days — the edge is NOT pure rebate harvesting — but
quantify the no-rebate case explicitly (Kalshi gearing): publish the month leaderboard on
GROSS alone. Note the a-priori Kalshi hypothesis in `strategies.py` ("stricter gates likely
win without rebates") is already refuted by the forward data; the A-S mechanism is the
portable one, and the running kalshi collectors can feed the same shadow A/B to confirm.

## 8. Roster hygiene done in this change (compounding benefits)

Pruning 25→8 live variants: ~3× less shadow compute per cycle, cleaner SUMMARY tables,
and no multiple-comparisons haircut across 22 mostly-dead arms. The 2×2 ablation
(skew99 / av_stoikov / mo_skew99 / as_markout) tells us *which knob* carries the edge, so the
next iteration tunes the right parameter (AS_K, MO_K) instead of breeding more gates.

## Sequence

1. **Now:** apply the updated `strategies.py` to the collector branch
   (`claude/polymarket-btc-backtest-XZkKI`) so the ensemble arms start accumulating forward
   windows tonight. (Zero engine changes needed — gate and size_mode compose orthogonally.)
2. **This week:** decay alarm (#2), health payload checks (#3), day-clustered t (#4).
3. **Next 2 weeks:** regime tagging (#5) while `as_markout` accumulates its ≥14 days.
4. **On promotion:** fill-realism reconciliation (#6), then move the deployment off
   `micro_gate` to the winner.

---
## Status (2026-07-11)

- **DONE — roster deployed**: updated `strategies.py` pushed to the live collector branch
  (`claude/polymarket-bot-live-ready-vw7ut5`, the branch `collect.yml` actually checks out).
  Live arms (8): baseline, av_stoikov, mo_size, as_markout, mo_skew99, skew99, as_cap100,
  micro_gate (decay watch). New forward windows accumulate from the next collect cycle.
- **Brainstorm verdicts**: ADDED `as_cap100` (capacity probe — cap was only ever tested down;
  scaling real money needs the up direction). PRUNED `fv_size` (negative after a full month,
  dominated by markout sizing). NOT adding more gates (0-for-19), tighter inventory (all
  decisively negative), or BTC-lag arms (all negative).
- **IN PROGRESS (delegated)**: day-clustered stats + micro_gate decay alert in
  `aggregate_shadow.py`; empty-payload content checks in `health_check.py` — same branch.
