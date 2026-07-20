# K-WX: staged, gated roadmap from $10 canary to ~$4k/month

Generated 2026-07-20 from `wx_path_to_4k.py` + `p4k_params.json` (repo `Codex-playground-` @
`claude/coding-bot-ab-test-results-ffmhxw`), re-run this session. Every $/month number below is
that model's actual output, not a vibe. Every stage-advance gate is a bar already written into the repo
(`kwx_paper_gate.PASS`, `wx_scaling_schedule.md`'s bankroll rungs, or a sleeve's own `gate` block in
`p4k_params.json`) -- this doc adds no new thresholds, it only sequences the ones that exist.

> **2026-07-20 evening update:** three levers this doc still models as open are now closed by
> adversarially-verified studies, and one it models as pending is already deployed. See
> [GOAL RECALIBRATION](#goal-recalibration-2026-07-20-evening) at the bottom — it supersedes the
> maker/early-lock rows of the stage table and operator actions #2 and #6.

## REVISION NOTICE (post two-judge review)

This document and its underlying model went through an independent two-judge review. **Verdict: REVISE.**
Both judges agreed the earlier draft's arithmetic reproduced faithfully from its own code, but the code
itself had three independently fatal problems in how it computed the headline "$2,000 -> $5,576/mo"
claim. All are now fixed in `wx_path_to_4k.py` / `p4k_params.json`, and **the corrected model's headline
conclusion changes**: $4k/month is **not reachable** at any tested bankroll under any scenario, including
optimistic. What follows is the corrected roadmap. The fixes, in order of severity:

1. **[FATAL, fixed] Wrong depth distribution gated `depth_adaptive` sizing.** The prior model sized
   depth-adaptive fires off the *pooled* book-depth array (median 369.5ct, including deep-ITM rungs a
   fire never actually touches). The fire-relevant near-lock/touch-price depth
   (`depth_within_2c`/`best_ask_size` from `kalshi_weather_orderbook_summary.json`'s depth_report,
   largest-n blocks: median 65.5ct / 13ct) is much thinner. The model now takes the **pessimistic** of
   `alpha * pooled_bootstrap_sample` and `alpha * fire_conditional_median` per fire (see
   `depth_fire_conditional_ct` in `p4k_params.json`).
2. **[FATAL, fixed] Zero market-impact/slippage on large orders.** The repo's own Q2 depth-adaptive
   study measured a 16% EV/ct haircut at a mean order of 236ct ($196.66 -> $165.18). The prior model
   applied the flat backtest EV/ct at up to ~1,457ct/fire with no impact term. A per-fire impact haircut
   now scales with order size relative to that 236ct reference (see `market_impact` in
   `p4k_params.json`), capped at 60%.
3. **[FATAL, fixed] Uncertainty bands were decoration.** The code and this doc both claimed inputs got
   "a wide uncertainty multiplier" but every input (win_rate, EV/ct, unfillable_frac) was point-fixed
   per scenario across all 1500 trials -- the p10-p90 spread was pure Bernoulli/count sampling noise at
   a single fixed input, not genuine parameter uncertainty. `win_rate`, `ev_per_ct`, and `unfillable_frac`
   are now redrawn once per simulated month from an explicit uncertainty band (see `param_uncertainty`
   in `p4k_params.json`), so the printed bands now reflect real input uncertainty in addition to outcome
   noise.
4. **[MAJOR, fixed] Conservative scenario contradicted tonight's live evidence.** 0 fires from 39
   near-misses tonight (all logged `ask>98`, i.e. observed live fillable rate 0/39, Wilson95 upper bound
   ~9%) versus the conservative scenario's backtest-derived 79% fillable assumption. Added a
   `conservative_live` scenario alongside conservative/base/optimistic that forces `unfillable_frac` to
   the live-observed rate. It is dramatically worse than backtest-conservative -- see the stage table.
5. **[MAJOR, fixed] Unreconciled 40x spread in fires/day across the repo's own sources, silently
   resolved to the favorable one.** wx_ev_concentration.md: 25.7/day (used for the capacity arithmetic);
   wx_scaling_schedule.md's own gate-ETA math: 10.4/day; phase2_tier1: 58.95/day; KXHIGH-only cut of
   kalshi_weather_expand_summary.json: 4.39/week (flagged unreconciled in that file itself). These are
   NOT reconciled to each other in this repo. `wx_path_to_4k.py` now prints an explicit sensitivity row
   at the 10.4/day gate-basis rate alongside the headline 25.7/day figure so the ~50% gap this creates
   is visible instead of hidden.
6. **[MAJOR, fixed] Price/PnL decoupling double-counted the edge and used the wrong price
   distribution.** Prices were sampled `uniform(0.55,0.97)` (mean 0.76) while the params claimed
   "centered near median [0.89]" -- ignoring the median inflated contracts-per-budget ~17% wherever
   budget-bound. Separately, the derived win magnitude could exceed the physical maximum payout
   (1-price) for fires priced above ~0.81 -- the majority at the claimed median 0.89 -- an impossible
   per-fire cash flow even though the scenario mean was pinned correctly. Prices now sample from a
   triangular distribution with mode=median, and every fire's win magnitude is capped at
   `(1-price) - fee(price)`, the actual maximum a contract can pay out.
7. **[MAJOR, fixed] Sleeve gates auto-pass on assumed accrual with no conditionality marker on the
   output.** Every base/optimistic $/mo figure that depends on at least one ASSUMED-quality sleeve gate
   (book_watch, maker, depth_adaptive, station_derate_relax deploy timing, early_lock) is now printed
   with a trailing `+` marker and an explicit legend line. The digest block below now says explicitly
   that none of those assumed accrual rates have been observed live yet.
8. **[MAJOR, fixed/flagged] Depth sample pseudo-replication.** n=86 rows are 3 sweeps of ~29 distinct
   markets on 1 calendar day, not 86 independent draws -- and same-day fires are not independent depth
   draws either. `wx_path_to_4k.py` now prints an explicit caveat whenever depth-adaptive-cap binds,
   naming the true row/sweep/day counts and stating that any such figure is PENDING the repo's own
   15-distinct-calendar-day gate, the same way Polymarket figures are excluded pending its study.
9. **[MINOR, fixed] The strong "honest bottom line" warning only ever printed when *optimistic* missed
   $4k, never when *conservative* did (optimistic hit $4k in the old model, so the anodyne branch always
   printed).** The warning is now gated on the conservative scenario -- the deployment-relevant
   condition -- not optimistic.
10. **[MINOR, fixed] `rng.triangular(min, max, mean)` passed the stated MEAN as the distribution's MODE**
    (its third argument), silently shifting the simulated mean below the stated 25.7/day. The mode is
    now derived analytically (`mode = 3*mean - min - max`) so the simulated mean matches the stated
    mean field.
11. **[MINOR, addressed] `kwx_goal_status.py` correctness.** (a) missed-fire counting is now
    schema-flexible instead of assuming one specific `{key: value}` shape; for the actual current
    `kwx_runner_state.json` schema (`{ticker: date}`) it already counted correctly (39 missed tonight),
    but the flexible version won't silently break if the schema changes. (b) near-miss date matching now
    falls back to a timestamp-derived date if the `date` field is absent. (c) NEXT GATE now advances past
    the paper gate using `p4k_params.json`'s `bankroll_rungs` once n_fired clears 30, instead of always
    printing the Stage-0 text. (d) the script now resolves its companion files (`kwx_gate_status.txt`,
    `kwx_runner_state.json`, `kwx_near_miss.jsonl`, `.kwx_halt`, `p4k_params.json`) against a repo root
    (via `--repo`, `$KWX_REPO_ROOT`, or walking up from its own directory) instead of always its own
    directory, so it prints honest numbers when vendored into a build/scratch directory rather than
    misleading zeros.
12. **[MINOR, noted, not modeled] In-sample selection haircut.** Cell 1_3 was the selected grid cell
    (t=37 in-sample) behind the +0.207/ct optimistic ceiling. The conservative EV of +0.15/ct haircuts
    latency but not selection/survivorship bias from having picked the best-performing cell after the
    fact. The paper gate (n>=30 live settled fires) is the real control for this, but even the
    "conservative" EV number should be read as carrying unquantified selection optimism until live
    n>=30 confirms it independently.

## How to read the bands

The model runs four scenarios, all Monte-Carlo over the SAME edge, differing only in which sleeves are
gate-open by the scenario's horizon and (for `conservative_live`) the live-observed fill rate:

| Scenario | Horizon | What's "on" | Meaning |
|---|---|---|---|
| **conservative** | 0 days | taker_mechanical + stacking only (already deployed today); unfillable_frac = 0.21 (BACKTEST) | what bankroll X earns **right now** under the backtest fill-rate assumption |
| **conservative_live** | 0 days | same sleeves as conservative; unfillable_frac forced to **tonight's live-observed rate** (0 fills / 39 near-misses, Wilson95 upper bound ~9% fillable) | what bankroll X earns **right now** if tonight's live fill evidence, not the backtest fill rate, is what actually holds |
| **base** | 30 days | + station_derate_relax, book_watch, maker, depth_adaptive (their gates clear inside 30d IF their assumed accrual rates hold) | what bankroll X could earn **if this month's data-accrual goes as assumed** (figures marked `+`) |
| **optimistic** | 90 days | + early_lock | same, 90-day horizon, edge held at the in-sample +0.207/ct ceiling before the per-fire market-impact haircut (figures marked `+`) |

**Base and optimistic are conditional, not scheduled** — every sleeve except taker_mechanical/stacking is
`ASSUMED`-quality and ungated only in the model's arithmetic, not in reality; every $/mo figure that
depends on one is marked `+`. Real accrual is 0 fires today (`kwx_runner_state.json`: `fired={}`) despite
`KWX_SWITCH=on`. Treat `+`-marked bands as "the prize IF the gates below actually clear," never as a
forecast of *when* — and treat `conservative_live`, not `conservative`, as the honest read of "what does
this earn tonight."

Bands (p10/median/p90) now reflect two sources of spread, not one: (a) within-scenario Monte-Carlo outcome
noise (win/loss draws, fire-count draws) at fixed inputs, and (b) genuine per-trial resampling of
win_rate/EV-per-ct/unfillable_frac from an explicit uncertainty range (`param_uncertainty` in
`p4k_params.json`) — previously only (a) existed despite this doc and the code's own comments claiming
otherwise (fix #3 above).

## Stage table

| Stage | Bankroll | Gate to ENTER (numeric) | $/mo band (quality) | Calendar honesty | Kill criterion |
|---|---|---|---|---|---|
| **0. Paper gate** | $0 (dry-run) | `kwx_paper_gate.PASS`: win≥99%, EV/ct≥+0.12, day-clustered t≥3, **n≥30 settled fires** (bar vs backtest ~99.6% win / ~+0.20 EV) | n/a (not deployed) | n≥30 needs fires to *exist* first. wx_scaling_schedule.md's own gate-ETA math cites 10.4 fires/day (unreconciled against the 25.7/day capacity-model rate, see revision #5) → ~3 days to n=30 IF that rate holds. **Currently observed: 0 fires in >1 day live**, 39 near-misses/day all logged `ask>98` (repriced before capture) — neither assumed rate has been demonstrated live. | If n<30 after **21 days** live with `KWX_SWITCH=on` and near-misses continuing to accrue at ~39/day, the bottleneck is detection/fill latency, not weather quietness — stop assuming either fires/day rate and re-diagnose `kwx_book_watcher` / feed latency before touching bankroll. |
| **1. $10 canary** | $10 | README/KWX_DEPLOY sequence: paper gate READY-FOR-CANARY → switch on, 1ct/fire (~$0.80/fire), ~1wk, worst realistic day ≈ −$5 | conservative $8/mo · conservative_live $1/mo · base $10+/mo · optimistic $13+/mo (0.0–0.3% of goal — **by design**, this stage is a fill/behavior check, not a money stage) | Same n≥30 dependency as Stage 0; this stage and Stage 0 are really one clock. | If the canary logs live fires but win rate's Wilson95 lower bound comes back <97% (materially below the 99.2–99.4% backtest LB) or a single-day drawdown >20%, halt (`.kwx_halt`) and re-open Phase-2 Track A validity before any further deploy — live has diverged from tested. |
| **2. Rung1→Rung2** ($10→$50→$200) | $50–$200 | `wx_scaling_schedule.md` Rung1: **n_live_fires≥100** (~1–2wk @10.4/day, or faster/slower — see revision #5 reconciliation) AND EV/ct 95%-CI lower bound>0 AND live fill ratio≥90% AND no single-day drawdown>20%. Rung2: **n_live_fires≥400–500** (~4–6wk) AND ≥10 distinct-day depth-probe sweeps. | conservative $50→$117/mo, $200→$472/mo (2.9–11.8% of goal); conservative_live $50→$20/mo, $200→$85/mo (0.5–2.1%); base $50→$143+/mo, $200→$545+/mo (3.6–13.6%) | Deploy `station_derate_relax` immediately at Stage 2 start — it's a same-day config flip (KMIA/KLAX/KPHL/KSEA off their 0.5x derate, Wilson95 upper bounds 0.55–0.89% all clear the 1.39% bar), not gated on data accrual. Modeled as an 8% aggregate size multiplier, essentially free once flipped. | If live fill ratio stays <90% past n=100 fires (i.e., the book isn't there when the runner tries to buy), the `unfillable_frac` assumption (10–21% backtest) is being beaten by reality — freeze bankroll at $50 and re-run `wx_scaling_schedule.md`'s Q1 with the real observed unfillable rate before advancing. Tonight's 0/39 evidence already suggests this may be the live reality; `conservative_live` above is the honest current read. |
| **3. Rung2→Rung3, data-accrual window** ($200→$500) | $200–$500 | Rung3 gate = **policy decision on `depth_adaptive`**, itself gated on ≥15 distinct calendar days of `wx_book_snapshots.jsonl` (currently 1 day, accrual 1/day → ~14 more days minimum) AND ≥300 rows AND top-5-EV-station (KDEN/KMIA/KMSY/KOKC/KSEA) medians stable <2x sweep-to-sweep. Concurrently: `book_watch` gate n_attributed_fires≥30 (assumed 7.8/day); `maker` gate usable_rows_per_cell≥30 (assumed 2.0/day/cell). | conservative $200→$472/mo, $500→$1,047/mo (11.8–26.2% of goal, binding shifts to fixed **DEPTH_CAP=25** at $500); base $200→$545+/mo, $500→$863+/mo (13.6–21.6%, binding is already the pessimistic depth-adaptive cap from $250 up, see revision #1) | ~14–15 calendar days is the *floor* set by the depth-snapshot gate alone (it cannot pass faster no matter how much bankroll or fire volume exists) — this is the pacing stage of the whole roadmap. The n=86-row sample behind depth_adaptive is 3 sweeps of ~29 markets on ONE calendar day (revision #8) — treat any depth-adaptive figure as pending that 15-day sample regardless of what this table shows today. | **depth_adaptive**: if station-median depth swings ≥2x sweep-to-sweep once 15 days accrue, do **not** adopt — stay on fixed DEPTH_CAP=25 permanently; the pure-bankroll path then hard-caps near $1,047–$1,318/mo (conservative-scenario ceiling, see Stage 4) regardless of deposits. **book_watch**: if n_attributed_fires is still 0 after 4x the assumed time-to-30 (~16 days), the 7.8/day conversion assumption is wrong — zero out its EV bump in all forward planning. **maker**: if the fill-rate bracket `[definite, definite+ambiguous]` fails to beat the +1.1c/ct taker baseline at n=30/cell, or any adverse-selection signal appears, kill — never rest live bids. |
| **4. Rung3→Rung4 + structural ceiling** ($500→$1,000+) | $500–$1,000+ | Rung4 gate: `depth_cap_resolution_or_more_volume` — either depth_adaptive (Stage 3) passed, or fire-volume sleeves (book_watch/stacking/early_lock) have measurably raised fires/day. **Synoptic decision point**: modeled uplift is a separate, ASSUMED-quality estimate not incorporated into this model's bands — decide only after `wx_synoptic_trial.py`'s 14-day free-trial latency measurement lands. | conservative $500→$1,047/mo, $1,000→$1,316/mo, $2,000→$1,318/mo (26.2–33.0% of goal — **flat past $500, DEPTH_CAP=25 binding for every larger bankroll tested up to $50,000**); base $500→$863+/mo, $1,000→$879+/mo, $2,000→$885+/mo (21.6–22.1%, **flat past $250, pessimistic depth-adaptive-cap binding**); optimistic ceiling $1,173+/mo (29.3%) even at $50,000 bankroll, 90-day horizon, every sleeve gate open | Synoptic trial is a fixed 14-day clock, independent of fire-rate luck — schedule the go/no-go review for trial_start+14d regardless of other stages' progress. | **This IS the structural ceiling, corrected.** Under the fixed model errors from the earlier draft (revisions #1–#3), NO scenario — conservative, conservative_live, base, or optimistic — clears $4k/month at ANY bankroll tested up to $50,000. Conservative tops out ~$1,318/mo (33%), base ~$885+/mo (22%, and that's `+`-marked — depends on ASSUMED sleeve gates none of which have cleared live), optimistic ~$1,173+/mo (29%). More bankroll past ~$500–$2,000 buys essentially $0 extra profit under current levers: declare the pure-bankroll-scaling path **structurally capped well below $4k/mo** until at least one of depth_adaptive (validated on a real ≥15-day, non-pseudoreplicated sample), Polymarket, or a fire-rate-growth sleeve produces a measured (not assumed) capacity increase. Do not keep depositing past $2,000 expecting more return from bankroll alone. |
| **5. Not reachable under current levers (corrected)** | n/a | The prior draft's "REACHABLE at $2,000" claim (median $5,576/mo) does not survive the corrected depth-conditioning, market-impact haircut, and uncertainty-propagation fixes (revisions #1–#3). Recomputed: base scenario, $2,000 bankroll, all near-term sleeve gates modeled as open (still `+`-marked, none observed live) → **median $885/mo (22% of goal)**, binding constraint is the pessimistic depth-adaptive cap. | **No scenario in the corrected model reaches $4k/mo at any tested bankroll.** Best across all four scenarios: optimistic at $50,000 → median $1,173+/mo (29%). | This stage is retired. What would have to be true for a future run to legitimately show REACHABLE: (a) depth_adaptive validated on a real ≥15-distinct-calendar-day, non-pseudoreplicated sample with the fire-conditional (not pooled) depth measure holding up; (b) Polymarket's basis-risk/reprice-speed study clears and adds real capacity; (c) book_watch/early_lock's assumed accrual rates are confirmed by live fires, not just elapsed calendar time; (d) the market-impact haircut at the resulting order sizes is remeasured, not assumed flat. None of these has happened yet. | If any future revision of this model again claims a scenario clears $4k/mo, re-run the same judge-review checklist (depth-distribution conditioning, market-impact scaling, parameter-uncertainty propagation, live-fill consistency, fires/day source reconciliation, price/EV joint distribution, ASSUMED-gate conditionality marking, depth-sample independence) before trusting the number. |
| **6. Polymarket (speculative, excluded from headline)** | n/a until validated | gate = `basis_risk_and_reprice_study_complete`, **not time-accruable** (no ETA — needs a from-scratch Wunderground-basis-risk + Polymarket-reprice-speed + custody study) | not included in any $/mo figure above; if validated, `fires_per_day_mult_if_validated=1.5` (ASSUMED, wide prior) would scale whichever stage's band is then active | No calendar estimate exists or should be invented — this is explicitly excluded from all four scenarios in the model. | If the basis-risk study finds settlement disagreement risk vs Kalshi's own feed, or measured Polymarket reprice speed matches/beats the ~3.3min gap half-life, kill before ever funding a Polymarket account — do not paper-trade past that finding hoping it improves. |

## Operator action list

1. **Now**: confirm Stage 0/1 clock is actually running — if 0 fires persist much past the 21-day kill window in Stage 0, stop and diagnose before any deposit. Use `conservative_live`, not `conservative`, as tonight's honest earnings read (0/39 fills observed).
2. **At Rung1 pass** (n_live_fires≥100 — timing uncertain, see revision #5's unreconciled fires/day sources): deposit to $50; same day, flip `station_derate_relax` config (KMIA/KLAX/KPHL/KSEA) — no data-accrual dependency.
3. **At Rung2 pass** (n_live_fires≥400–500): deposit to $200.
4. **~15 calendar days after depth-snapshot accrual starts** (independent of fire count): review `depth_adaptive` gate (≥300 rows, ≥15 days, station-median stability, AND a fire-conditional — not pooled — depth remeasurement per revision #1). Pass → proceed toward $500 sizing with alpha=0.25 against the pessimistic depth measure. Fail → apply Stage 3/4 kill criterion, freeze bankroll scaling.
5. **Synoptic decision**: run out the 14-day free trial (`wx_synoptic_trial.py`), then decide on the paid tier using its *measured* latency uplift — no modeled figure for this exists in the current bands.
6. **Maker activation**: only after usable_rows_per_cell≥30 (~15d at assumed 2/day/cell) AND the fill-rate bracket clears the +1.1c/ct taker baseline with no adverse-selection red flag — activate as a live sleeve; otherwise leave it OFF permanently (it is OFF in the conservative scenario by construction).
7. **$2,000 deposit**: do **not** treat this as "Stage 5, first stage clearing $4k/mo" anymore — the corrected model shows $2,000 base-scenario median is $885+/mo (22% of goal), not $5,576/mo. Only deposit to $2,000 once the bankroll-rung table's own `authorized_today` is True for the relevant rung AND you have independently re-verified whichever sleeve gates you're counting on, understanding the ceiling there is well under $4k under current levers.
8. **Polymarket**: no capital, ever, before the basis-risk/reprice-speed study exists and clears. Not on this roadmap's critical path.

---

## CURRENT STAGE / NEXT GATE / BLOCKING ON
*(paste into the daily digest — recomputed live by `kwx_goal_status.py`)*

```
=== K-WX GOAL STATUS ($4k/mo path) ===
CURRENT STAGE : 0 -- pre-canary paper gate (KWX_SWITCH=on, kwx_paper_gate: no settled fires yet)
NEXT GATE     : n>=30 settled fires, win>=99%, EV/ct>=+0.12, t>=3   [kwx_paper_gate.PASS]
BLOCKING ON   : 0 settled fires so far; 39 near-misses today (all "ask>98", repriced before capture),
                39 missed tickers logged, 0 fired -- neither the 25.7/day nor the 10.4/day assumed
                accrual rate has yet been demonstrated live (these two repo sources are themselves
                unreconciled, see revision #5). Kill-switch: off. Book-watcher: idle (no hot set).
CEILING TODAY (conservative, no further sleeves): $1,047-$1,318/mo max across ANY bankroll tested
                (flat past $500, capped by fixed DEPTH_CAP=25). CONSERVATIVE_LIVE (tonight's actual
                0/39 fill evidence, not the backtest 79%-fillable assumption): $147-$149/mo max --
                a >85% haircut off the backtest-conservative number.
$4K STATUS    : NOT REACHABLE in the corrected model at ANY bankroll up to $50,000, in ANY scenario
                (conservative, conservative_live, base, or optimistic). Best across all four:
                optimistic at $50,000 bankroll -> median $1,173/mo (29% of goal), and that figure is
                marked "+" -- IF all assumed accrual rates and sleeve EV bumps (book_watch, maker,
                depth_adaptive, early_lock) survive live validation. None have yet: 0 fires observed
                live as of this run. Reaching $4k/mo requires a measured (not assumed) capacity
                increase from depth_adaptive, Polymarket, and/or fire-rate growth -- not simply more
                bankroll or more elapsed calendar time.
```

---

## GOAL RECALIBRATION (2026-07-20 evening)

Written after the overnight research program completed. Four facts change how the roadmap above
should be read; the stage table's numbers stand, but its optionality has narrowed.

**Closed levers (do not model, do not wait on):**
1. **Maker sleeve: REFUTED** (`wx_maker_deep_study.md`, merged). The +7c/ct headline was simulated
   limit orders that would actually have crossed the spread; genuine maker fills happen 2-3 times
   per 65 days x 20 stations. Operator action #6 is void — the maker gate can never accrue to a
   deployable state as specified. `p4k_params.json` now carries it at zero EV in every scenario.
2. **Early-lock sleeve: NULL** (`wx_earlylock_deep_study.md`, merged). 5,415 matched historical
   rows, no cell clears Bonferroni, headline cell sign-flips across sample halves. The forward
   paper harness keeps running (costless) but gets zero capacity credit until it actually PASSES
   against this null prior.
3. **Directional/timing sleeve: NULL** (`WX_DIRECTIONAL.md`, merged). Eight pre-registered specs,
   four funnel rounds, zero survivors; SPECs 2/4/5/6 decisively dead on n=815-2,109. Closed unless
   a genuinely different signal class is proposed; specs 1/3/7 reopen only with market history
   (see reopen calendar below).

**Already deployed (stop modeling as pending):**
4. **station_derate_relax is LIVE** — the 2026-07-18 recalibration in `kwx_runner.py` already
   removed the KLAX/KMIA/KPHL/KSEA derates (only KPHX retains 0.5x). Operator action #2's "flip
   the config at Rung1" is already done; `p4k_params.json` now marks the sleeve deployed.

**Revised bankroll guidance:** the conservative curve is flat past ~$500 (DEPTH_CAP binding), so
**$500-$1,000 captures essentially the entire current opportunity (~$1.0-1.3k/mo ceiling)**. Do
not deposit beyond ~$1,000 expecting more return; incremental capital past that point earns ~$0
under every scenario tested to $50,000.

**The only remaining paths to $4k/mo, in order of evidence-weighted realism:**
- **Fill conversion** (Stage 0's own blocking problem): all 52 recent near-misses show ask=100 at
  first sight — diagnosis of the latency chain (obs publication vs leg coverage vs market speed)
  is in progress; until settled fires exist, nothing else on this roadmap advances.
- **New market families with the same mechanical-lock structure** (recon in progress → will land
  as `WX_EXPANSION.md`): the edge is structural, not meteorological; other Kalshi families with
  observable, irreversible deciding stats are the one axis tonight's studies did NOT close.
- **depth_adaptive** (unchanged from Stage 3/4: needs its honest 15-distinct-day sample).
- **Calendar reopens** (scheduled, see below): specs killed only by the market family's youth
  (67 days, one season) get one honest re-run each when history deepens.

**Reopen calendar (Routines are armed for these):**
- ~2026-11-15 (first cool-season data): re-run directional SPECs 1/3/7 + the season-conditional
  nowcast redesign (SPEC 4's documented weakness); weekly gate-check Routine also active.
- ~2027-05-15 (full year of history, two warm-season starts): full directional re-run eligibility;
  also re-check the R4-1 lead-time ceiling (only reopens if Kalshi lists markets earlier).
