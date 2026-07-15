# FORWARD VALIDATION LEDGER

Daily forward evidence for the pre-registered decision-layer arms. Arms are produced
by box_shadow.py — one row per (window, arm) in gha_data/<day>/box_shadow_<asset>15m.jsonl.

**CORRECTION 2026-07-13 (evening audit):** the box_shadow.py CODE was committed
04:42Z (31454af35) + STACK arms wired 161cd2e73, but NO workflow ever RAN it — so
from deploy until this correction, ZERO forward rows existed and the "accruing"
status below was aspirational, not real. Fixed: box-shadow.yml (main cd736e2a9)
now runs the replay daily at 02:47 UTC over a trailing 7-day window of collected
ticks. Harness verified locally (8 arms/window, ~5000 windows 07-06..07-12).
FORWARD CLOCK THEREFORE STARTS 2026-07-14 (first full post-deploy day the scheduled
job processes); the ~10-day gate opens ~2026-07-24, not 07-23. Pre-deploy replay
over 07-06..07-12 only reproduces the priors (that era is the arms' own test set).

## Promotion gate (from charter — do not relax)
Promote an arm when: day-clustered t >= 2 vs the live arm over >= 10 FORWARD days
(days after 2026-07-13, i.e. data the arm's design never saw), evaluated on the
gate-passed subset for entry vetoes / all events for disposal arms. Kill when t < 0
after 10+ forward days.

## Arms under forward test (pre-registered 2026-07-13, replay priors attached)
| arm | replay prior (test, day-clustered) | forward status |
|---|---|---|
| hazard_stop | +0.57c t=2.36 (gate +1.11c t=2.64); re-impl sensitivity noted (J) | accruing from 2026-07-13 |
| thickbook_veto | avoided 1.25c/event t=10.1 (in-sample) | accruing |
| cell_veto | +0.124c/window t=2.77 (train->test) | accruing |
| givecap15 | flat mean, tail cut (disposal study) | accruing |
| combined | untested as a stack | accruing |
| stack_full / stack_lean | replay: EV +1.47c t=2.84, strand 6.73→2.14%, CVaR5 halved (STRAND_DEFENSE stack test) | accruing from 2026-07-14 (box-shadow.yml) |
| c3_share (added 2026-07-13, 17514ec87) | +1.42c t=5.15 marginal beyond thickbook (in-sample; large-skip artifact known — forward is the only valid sizing). NOTE: observed veto rate 39-49% of windows, higher than the 'mild' label implied; investigated at wiring (real property of depth-share stat, values span full range; thickbook 18-22% in same runs confirms harness). Judge on gate-passed forward deltas only | accruing from 2026-07-14 |
| eth 'live' sleeve (added 2026-07-13) | node F1b viability: ETH pair 87.6%, 30% of fills at 2-3c spread | accruing from 2026-07-14 |
| back2 (added 2026-07-13, 0f5bdf4ac; runs BOTH assets) | HONEST triangulated prior: +0.2-0.4c/window on ETH (study t=8.96 did NOT survive replication — F1b-repl; three implementations agree weak-positive). BTC = falsification control (L0.5: back-quoting toxic). Deploy bar: ETH day-clustered t>=2 vs eth-live over >=10 forward days AND BTC control non-positive | accruing from 2026-07-14 |
| volgate (added 2026-07-14, 70ed86897; node OV-VOLGATE) | vol-regime ENTRY veto: skip when prior-window realized vol in top quartile of trailing regime. Replay prior (06-10..13): +0.96c/win t=1.59, strand 7.6→4.9% (46 vetoes). Streak study: vol lag-1 autocorr 0.58; prior-window vol AUC 0.655 (>prior-outcome 0.619). Fidelity caveat: harness uses Kalshi-mid vol, weaker than study's spot vol. Deploy bar: day-clustered t>=2 vs live over >=10 fwd days | accruing from first box-shadow run after 2026-07-14 ~14:47Z |
| nsmove (added 2026-07-14, bot-branch; node OV-2POP-ARM) | near-strike × movement veto: STRICT SUBSET of volgate — veto only when volgate fires AND entry near-strike (|p1-0.5|<0.15). Targets the drift-driven BIG-loss population (leading |drift| AUC 0.875 provisional, n=6). Replay prior (06-10..13): +0.55c/win t=0.79, strand 7.6→6.5% (29 vetoes) — weaker than volgate here because motivating population is in the overnight sample. Head-to-head vs volgate is the forward question. Deploy bar: t>=2 vs live over >=10 fwd days | accruing from first box-shadow run after 2026-07-14 ~14:47Z |

## FAVLONG near-expiry taker (added 2026-07-14; nodes FAVLONG + 07-15 follow-ups) — NEW STRATEGY FAMILY
**First validated positive edge of the program.** A TAKER strategy (not the maker box bot): in the
last ~2-3 min of each Kalshi 15m window, take the side the executable price underprices per a
fair-value model. Scored on reconstructed SETTLEMENT, not markout. Tool: `favlongshot_edge.py`;
calibrated model `favlong_model_v2.py`.
- Backtest priors (35 days, +Kalshi fees, clean market-settlement labels, latency-robust):
  raw model POOLED clustered t=3.99/105 asset-days; tuned (720/edge0.03/sigma0.8) OOS pooled t=3.97.
  **CALIBRATED model (isotonic, train-fit) OOS pooled t=7.70, +$0.059/ct, all 3 assets clear t>=2
  individually (btc 5.58 eth 3.84 sol 4.09)** — the recommended variant.
- **CORRECTED characterization (07-15, supersedes the 'favorite-longshot / buy-cheap-underdog'
  framing, RETRACTED):** it is a repricing lag in WIDE/dislocated books, MID-vol regimes, concentrated
  on the NEAR-ATM-TO-FAVORITE side (entry>=0.40; deep-underdog <0.15 has NO OOS edge). No archive decay.
  Box-maker cannibalization LOW (edge ~0 in tight/deep books). No second independent edge found.
- **Universe: btc/eth/sol ONLY. XRP is a NULL (OOS t=-0.32) — excluded.**
- Caveats: small (~2-6c/ct); ~62% asset-days positive; TAKER = new execution; calibration map is a
  fitted component (needs periodic refit, can decay).
- **Deploy bar (charter gate): day-clustered t>=2 vs zero over >=10 FORWARD days, POOLED across
  btc/eth/sol** (per-asset underpowered; xrp excluded). Recommend forward-tracking BOTH the raw
  (control) and the calibrated model (pre-registered now, before any forward data exists — ungameable).
  PROPOSE-ONLY: no live sizing without operator word. Forward clock starts at first tick-archive day
  after 2026-07-14; gate opens ~2026-07-25.

### Forward-validation harness (node C, 2026-07-14)
`favlong_forward.py` scores each COMPLETE forward day (btc/eth/sol) with the validated config, appends
idempotently to `favlong_forward_log.jsonl`, and prints the running POOLED gate (PASS >=10d & t>=2;
KILL >=10d & t<0). Daily GHA `.github/workflows/favlong-forward.yml` at 06:33 UTC (stdlib-only, default
token). `--report` prints status without re-fetching. Enabling the Action (or a claude-code-remote
Routine at a fixed UTC time) starts automated accrual. Current: CLOCK-NOT-STARTED (first forward day
07-15 in progress).

### Forward-validation harness (added 2026-07-15)
- **Tool:** `favlong_forward.py` (imports `favlongshot_edge.build_asset`/`.score`; does not
  duplicate the math). Run `python favlong_forward.py` to fetch the gha-data branch, score every
  new COMPLETE forward day (strictly after 2026-07-14 and strictly before today UTC, so logged
  days are final) for btc/eth/sol with the validated config (decision_t=720, edge=0.05, +Kalshi
  fees, no fill lag), append per-(asset,day) rows, and print the pooled gate status.
  `python favlong_forward.py --report` prints the gate from the log without re-fetching.
- **Log:** `favlong_forward_log.jsonl` (repo root). One JSON record per (asset, day):
  asset, day, n_trades, mean_ct ($/contract), day_pnl, winrate, config. Idempotent, keyed on
  (asset, day); already-logged days are skipped and n_trades=0 days are marked so they aren't
  re-scanned.
- **Gate (headline):** pooled per-(asset,day) day-clustered t over the traded forward rows.
  PASSED = >=10 forward days AND pooled t>=2; FAILED = >=10 forward days AND pooled t<0 (kill per
  charter); otherwise not-yet (clock not started / too few days / 0<=t<2).
- **Automated accrual:** enabling `.github/workflows/favlong-forward.yml` (daily 06:33 UTC; commits
  the updated log back to this code branch) OR a claude-code-remote daily Routine that runs
  `python favlong_forward.py` at a fixed UTC time starts hands-off accrual. Until one is enabled,
  the log only advances on a manual run. As of 2026-07-15 the clock has NOT started (07-15 is the
  first forward day and is still in progress); the first complete forward day is 2026-07-15,
  scored on the 2026-07-16 run.

## Daily entries
### 2026-07-13 (day 0 — deployment day)
- Live: SWITCH=on, no kill sentinel, telemetry fresh. Size-2 experiment day 2.
  BTC overnight windows quoted 0 orders (low-liquidity hours + gates); realized $0.
  Live edge sample remains tiny (4 trading days total) — see 2026-07-19 eval plan.
- box_shadow deployed 04:42Z; first arm rows expected from the next paper-collect
  run. Fidelity gate at deploy: live-arm correlation 1.00000 vs study values
  (682/682 exact) on 2026-06-25 + 2026-07-05.
- No forward stats yet (day 0). First promotion decision possible ~2026-07-23.

### 2026-07-14 (day 1)
- Live: SWITCH=on, no kill, balance ~$59-61 (above $55 floor), overnight net positive
  (+~4c mark on 97 windows). F14 (--flatten-fractional 0.1) confirmed DEPLOYED live
  since 2cd9ae62c; 0 fires (no >0.1 fractional residual has occurred during a live ON
  session yet — armed, awaiting first triggering event to exercise the count_fp path).
- Arms ADDED this cycle: volgate (70ed86897), nsmove (bot-branch). Both accrue from the
  first box-shadow run after ~14:47Z (the 05:56/08:54/11:11Z runs predate the pushes;
  next scheduled run backfills 07-07..07-13 via per-arm dedup-append). Verify new-arm
  rows land on gha-data after that run.
- ROSTER now 12 arms (>10). RETIRE-WATCH (charter arm-lifecycle): cell_veto (t≈-1.0,
  inert/slightly-neg) and givecap15 (byte-identical to live) — neither yet meets the
  retire bar (byte-identical/t<-2 over >=10 FORWARD days); revisit at the ~07-24 gate.
- Research this cycle (committed to DECISION_MAP): OV-CLUSTER (streaks real, perm p=0.033),
  OV-VOLGATE, OV-STATE (unsupervised GMM+Markov: bad state = tight-spread/illiquid, contemp
  AUC 0.76, but does NOT persist → not the streak cause), OV-2POP (two loss populations:
  big=drift-driven leading AUC 0.875 provisional, small=driftless noise), OV-STRIKE (loss
  pegged to price-vs-strike + movement), OV-ROUND (strike round-number REFUTED; liquidity-
  cliff suggestive-underpowered, parked). Strategy scoreboard: top-10 tiered.
- No forward stats yet for volgate/nsmove (day 0 for them). First promotion decision for
  the 07-13 cohort possible ~2026-07-23; for volgate/nsmove ~2026-07-24.
