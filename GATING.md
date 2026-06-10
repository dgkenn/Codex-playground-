# World-class toxicity gating / benign-finding

The edge is the maker rebate; the only thing that erodes it is **adverse selection** (getting filled right
before the price moves against you). So the gating function's whole job is: **keep benign fills, drop toxic
ones.** This documents the data-driven rebuild of that function.

## Method (why these are trustworthy, not just more knobs)
`gate_lab.py` backtests every candidate gate on the **56,082 recorded ungated fills across 141 windows**
(the `baseline` variant logs every fill it *would* take, with the full feature vector + realized markout).

**The critical fix in the objective.** Markout-to-resolution (`mo_res`) conflates two things: adverse
selection (what a maker controls) and the **directional outcome** (BTC momentum → who wins). Optimizing
`mo_res` produces gates that *pick winners* — directional betting that breaks delta-neutrality and overfits
realized BTC paths (a naive ensemble scored an impossible **+0.77/share**, i.e. pure direction). A market
maker holding balanced sets to $1 has the directional part cancel; what it actually controls is
**short-horizon markout (`mo5`)** — did the touch move against us right after the fill. So **toxicity is
judged on `mo5`**, and `mo_res` is shown only to expose directional overfit.

## The 10 improvements, judged on real fills (mo5, vs deployed `micro`)
| # | improvement | result | verdict |
|---|---|---|---|
| 1 | markout-calibrated threshold | `tox ≤ −0.003`: **+2691, t=+6.19** | ✅ `micro_strict` |
| 2 | spread/price-adaptive margin | below micro (t=−5.3) | ✗ discard |
| 3 | tau-scaled strictness | +2169, t=+3.23 | ◐ modest (folded into ensemble) |
| 4 | flow-confirmed gate | below micro (t=−7.7) | ✗ discard |
| 5 | VPIN-style flow toxicity | below micro (t=−5.8) | ✗ discard |
| 6 | BTC lead-lag (30s) | **+3345, t=+6.21** | ✅ `lead30` |
| 7 | queue-position-conditional | below micro (t=−8.5) | ✗ discard |
| 8 | trade-size toxicity | below micro (t=−8.6) | ✗ discard |
| 9 | asymmetric side thresholds | **+2500, t=+7.50 (highest)** | ✅ `micro_asym` |
| 10 | **calibrated ensemble** | **OOS +1307 vs micro +731** (+79%) | ✅ `micro_cal` |

Consistent with this project's whole history: **most complexity loses** (flow/VPIN/queue/size/adaptive all
underperform plain micro). Four things genuinely help, and they're now live-A/B variants.

## The four winners (shadow variants now A/B-testing live)
- **`micro_strict`** — require the microprice edge in our favor by ≥ `STRICT_MARGIN` (0.003). The deployed
  `micro` (threshold 0) keeps mildly-adverse fills; on the toxicity horizon, stricter wins.
- **`micro_asym`** — the SELL side is more toxic; gate ASK stricter than BID. Most significant single change.
- **`lead30`** — pull the side BTC moved against over **30s** (the deployed `spot_react` uses 2s; the 30s
  horizon dominates). Real short-horizon toxicity, not just direction (it wins on `mo5`, t=+6.2).
- **`micro_cal`** — the synthesis: a ridge model (`gate_model.json`, fit on 56k fills, OOS-tested) predicts
  short-horizon markout from the book features; **keep a fill iff `predicted_markout + maker_rebate(p) > 0`.**
  The microprice term dominates (−0.75) with small p-fatness / asymmetry / lead contributions.

## Why `micro_cal` is the world-class form
The optimal toxicity threshold is **not a constant — it depends on the rebate** (keep iff the rebate beats
the expected adverse selection). `micro_cal` encodes exactly that decision rule, so it **auto-adapts the
cutoff to the realized rebate** — which is the pilot's #1 unknown (`PAPER_VS_LIVE.md` A1). When the live
rebate is confirmed, re-fit `gate_lab.py` and `micro_cal` retunes itself; no hand-tuning.

This **updates** the older `WINNER_TWEAKS` conclusion ("keep mildly-toxic, `tox>0.002`"): that optimized
*resolution* net (rebate volume); on true adverse selection, stricter wins, and the right point is
rebate-dependent — which is exactly what `micro_cal` solves.

## Honest boundary / next step
These win on the toxicity horizon (`mo5`). On **deployable resolution-net** (4-day prospective, `leaderboard`
+ `combo_lab`), the winner is **`ufat`** and the best combo is **`ufat_band`** (`ufat` + skip the 0.30–0.55
zone) — see `INSIGHTS_4DAY.md`.

**Now deployed:** `live_trader.py --gate` defaults to **`ufat`** (the p-adaptive margin), with `--mid-skip`
available for the full `ufat_band` combo (opt-in until the live A/B confirms it). `micro_cal` remains the
long-run gate — it auto-tunes the threshold to the **real rebate** once the pilot confirms it
(`PAPER_VS_LIVE.md` A1). All variants run in the live multi-asset A/B; promote default changes only after
live confirmation. Re-fit anytime: `python gate_lab.py` (updates `gate_model.json`); combos: `python combo_lab.py`.
