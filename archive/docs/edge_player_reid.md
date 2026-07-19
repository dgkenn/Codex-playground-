# Edge via player re-identification — Kalshi 15m crypto binaries (btc/eth/sol)

**Node:** PLAYER-REID · **Scope:** offline, archived data only (`origin/gha-data`, `gha_data/<day>/`).
**Propose-only. No orders, no live changes.** Kalshi is anonymous; every "player" below is a
*behavioral cohort*, never a named actor.

**Operator hypothesis tested:** recurring players leave repeatable behavioral signatures →
re-identify them → follow the signatures that persistently WIN out-of-sample (OOS).
**Verdict: NULL.** The re-ID handles that exist in this tape do not isolate a persistent actor, and
no re-identified signature predicts settlement OOS.

Scripts (scratchpad, uncommitted): `reid.py` (loader + settlement), `accumulate.py` (per-cohort
per-(asset,day) stats), `analyze2.py` (screen + OOS backtest), `handle_check.py` (fingerprint
quality). Re-runnable by the lead.

**Data used (post-restart, sampled to stay tractable):** trades tape for **14 days** spanning the
train/test wall — train `06-11,06-14,06-17,06-20,06-23,06-26,06-29`; test
`07-02,07-04,07-06,07-08,07-10,07-12,07-14` — for **btc/eth/sol**. Within each asset-day I sampled
**every 4th run file** (~8 of 33 runs), deduped by `tid`. Total **4.50M trades, 1,027 settled
15m windows, 42 asset-days.** Train = days ≤ 2026-06-30, Test = days > 2026-06-30.

---

## 1. Field inventory & which RE-ID handles actually exist

Per **print** in `trades_kalshi_<asset>15m_*.jsonl.gz`:

| field | meaning | re-ID value |
|---|---|---|
| `tid` | per-print **UUID** | **none** — unique per print, not linkable across trades; no account/order id |
| `ts_exch` | exchange timestamp, **ms precision** | timing cadence / sub-second phase (tested §3) |
| `t` | recorder timestamp | fallback when `ts_exch` missing |
| `ws` | window-start (unix s) → identifies the 15m window | grouping key |
| `up` | contract = "up/above-strike"; **always 1** in the tape | — (only the up leg is recorded) |
| `side` | **aggressor** BUY/SELL of the up contract | directional flow |
| `p` | trade price 0–1 | price-offset / band habit |
| `sz` | size in contracts (**often fractional**, e.g. 2.87, 11.34) | exact-size fingerprint (tested §2–3) |

**No order id, no account id, no counterparty tag.** Parent sweeps *can* be reconstructed (group
prints on identical `ts_exch`+`side`+`up`+`ws`; child-count tail runs to 10+). Settlement is
reconstructable from the tape alone: last trade price per `ws` (require max t≥600 s) → `settle_up =
1[p_last>0.5]`; **validated exactly against `ticks_*` terminal mid** (1,1,0,0 on the check window).

**Confidence in the handles: LOW.** The only persistence-capable handles are (a) exact `sz` and
(b) `ts_exch` timing phase. Neither survives scrutiny as an actor fingerprint (§3): sizes are shared
across both sides / all hours / all price bands, and timing phase is uniform. `fills_*` (our own
box-maker flow) were **excluded** throughout.

---

## 2. Synthetic-player definition & OOS backtest

**Player construct:** each exact size value `round(sz,2)` = one candidate "synthetic player" (the
strongest recurring handle available). **Follow-return per contract** = trade the cohort's own side,
fill at the printed price `p`, hold to settlement, net Kalshi fee `0.07·p·(1−p)`:
BUY → `settle_up − p − fee`; SELL → `p − settle_up − fee`. WIN metrics: mean net $/ct, directional
hit-rate, and **edge = hit-rate − price-implied prob** (`p` for buys, `1−p` for sells). Day-clustered
t uses per-(asset,day) means.

**Anti-overfit protocol (the whole ballgame):** pick winners on **TRAIN only** (mean net > 0 AND
train day-clustered t ≥ 2), then test the *same* size signatures OOS. Persistence across the wall is
the only valid evidence.

**Activity gate:** train n≥200 over ≥6 asset-days AND test n≥80 over ≥4 asset-days.
**Cohorts screened = 1,115** (this is the multiple-testing count).

### Train-winners and their OOS fate

**13 of 1,115** cohorts were in-sample winners (train t≥2, positive). Their OOS results:

| size | trN | tr t | tr net | tr edge | teN | **te t** | **te net** | te edge | te pos-days |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1.20 | 912 | 2.66 | +0.020 | +0.029 | 1096 | 0.15 | **−0.023** | −0.013 | 11/21 |
| 22.06 | 203 | 2.63 | +0.034 | +0.042 | 325 | 0.32 | −0.001 | +0.007 | 9/17 |
| 11.34 | 271 | 2.24 | +0.043 | +0.057 | 385 | 1.16 | −0.019 | −0.005 | 9/18 |
| 24.08 | 288 | 2.12 | +0.052 | +0.061 | 302 | −0.12 | −0.008 | +0.002 | 10/19 |
| 0.60 | 3274 | 2.11 | +0.037 | +0.043 | 1638 | 0.15 | −0.003 | +0.010 | 10/21 |
| 9.01 | 209 | 2.05 | +0.049 | +0.059 | 304 | −0.26 | −0.011 | 0.000 | 6/19 |
| … (7 more) | | ≥2.0 | >0 | >0 | | mixed | mostly <0 | | |

**OOS follow-through: 2/13 stay positive OOS; 0/13 reach OOS t≥2.** Under the null a coin flip gives
~6.5/13 positive — the winners did *worse* than chance OOS. And **13 in-sample winners across 1,115
tests is at/below the ~25–41 false positives expected by chance** (one-sided t≥2), i.e. the
in-sample winners are **not even enriched above noise** before we get to the OOS wall. Pure
data-mining the top-OOS cohorts (table in `analyze2.py`) shows no train/test coherence either
(their train t's scatter around 0, several negative).

**In-sample-only, therefore overfit. No OOS-winning player.**

---

## 3. Why the handles fail — the size cohorts are not actors

`handle_check.py` characterizes the recurring odd-size cohorts (the best re-ID candidates):

| size | n | asset-days | **phase R** | side split | price band | hours |
|--:|--:|--:|--:|--|--|--|
| 22.06 | 264 | 17 | **0.09** | 116B / 148S | fav & mid & long | 20/24 |
| 24.08 | 230 | 16 | **0.11** | 116B / 114S | fav & mid & long | 20/24 |
| 11.34 | 345 | 17 | **0.01** | 183B / 162S | mid-heavy | 21/24 |
| 20.43 | 318 | 18 | **0.05** | 183B / 135S | fav & mid | 21/24 |
| 25.0 | 51 829 | 21 | 0.02 | ~53/47 | all | 21/24 |
| 500.0 | 17 393 | 21 | 0.05 | ~52/48 | all | 21/24 |

`phase R` = resultant length of the `ts_exch` sub-second phase (0 = uniform, 1 = single-phase bot).
Every cohort sits at **R ≈ 0.01–0.11 → effectively uniform**: no fixed sub-second cadence, so no bot
timing fingerprint. Each size is used on **both sides ~50/50**, in **all price bands**, across
**20–21 of 24 hours** — the exact opposite of a coherent single actor (which would be side-,
band-, and session-consistent). **An exact size does not carry one behavioral player.** Round sizes
(25, 500) are trivially shared by tens of thousands of prints. The fractional sizes are plausibly a
feed/aggregation artifact, not a deliberate per-trader signature.

This is the honest re-ID ceiling: the tape is anonymous, and the two persistence-capable handles
(exact size, timing phase) each fail to isolate an actor. Re-ID confidence **LOW**.

---

## 4. Whale follow/fade baseline

| cohort | TRAIN net (t) | TEST net (t) | read |
|---|---|---|---|
| whale (≥5 000 ct) | −0.020 (t=−2.64) | +0.017 (t=−0.61) | sign flips, never significant |
| whale (≥2 000 ct) | −0.002 (t=−0.10) | +0.004 (t=−1.92) | null |

Whale-**follow** is negative/insignificant in train and does not hold OOS; whale-**fade** is the
mirror and is eroded further by fees. Consistent with the prior finding (`participant_fingerprint.md`
§4) that the informed whale tail is *rare* (there ~11 near-expiry fills, markout-to-settle −0.083):
too rare and noisy to trade as a signature. **No whale edge.**

Sanity baselines: **all-flow** aggressor net = −0.011 train / −0.013 test (t = −6.7 / −11.9);
integer-lot and fractional-lot aggregates both ≈ −0.011 to −0.015. The aggregate taker pays the
spread+fee and loses on **0/21** positive test asset-days — the tape is efficient at the population
level, as it should be.

---

## 5. Correlation with FAVLONG

A crude FAVLONG-shaped cohort — near-expiry (t≥600 s) favorite BUYs (`p≥0.60`) — is **also null**
here: train net +0.047 but t=0.14 (enormous day variance), test net **−0.034**. This does **not**
contradict FAVLONG: FAVLONG additionally conditions on **wide/dislocated books + a fair-value edge +
train-only isotonic calibration**, none of which this unconditional favorite-buy proxy applies; the
proxy just shows raw favorite-buying is not an edge. Correlations between the (spurious) train-winner
cohorts' daily net and the favorite-buy daily net are small and **mixed sign** (−0.27 … +0.32 across
32–42 asset-days); whale-vs-favorite daily corr = −0.22. **No coherent linkage between any
re-identified signature and the FAVLONG environment.**

---

## 6. Verdict & honesty ledger

**VERDICT: NULL.** No repeatable behavioral signature persistently wins OOS.
- Re-ID handles present: exact `sz`, `ts_exch` ms-phase, aggressor `side`, price `p`, parent-sweep
  grouping. **No account/order id.** Handle confidence **LOW** — sizes are shared across sides/hours/
  bands and timing phase is uniform, so no handle isolates a persistent actor.
- Players screened: **1,115** exact-size cohorts (+ whale/whale2k/favbuy/all/int/frac baselines).
- OOS-winning player: **none.** 13/1,115 in-sample winners (≤ the 25–41 expected by chance);
  **0/13 reach OOS t≥2, only 2/13 even stay positive OOS** (vs ~6.5 by chance).
- Best "follow" OOS result: no signature clears a day-clustered t≥2 OOS; the highest OOS mean $/ct
  cohorts have random (often negative) train t — data-mined noise.
- FAVLONG correlation: small, mixed-sign, no linkage.

**Honesty ledger.** (1) Anonymity is binding — no true player identification or count; the
"synthetic player = exact size" construct is a weak proxy that the data (§3) shows does not hold one
actor. (2) Sampling: every-4th run file over 14 days; adds noise to per-cohort day means (some
cohorts n≈200–400 in test) but the result is a *clean* null, not a marginal one, so denser sampling
would not rescue it. (3) Settlement is reconstructed from the tape's last trade price (validated vs
ticks), which can mislabel a window with no trade after t=600 s (dropped, not guessed). (4) Multiple
testing is reported and dominates: with 1,115 cohorts, any "winner" must be judged against ~25–41
chance false positives — and none survived the OOS wall. An honest null was the expected base-rate
outcome, and this is one.
