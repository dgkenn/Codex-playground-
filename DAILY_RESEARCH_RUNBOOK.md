# DAILY RESEARCH RUNBOOK — autonomous bot-improvement cycle

**This is the single entry point for the once-a-day autonomous research run.** A scheduled
trigger fires a FRESH session each day whose only instruction is: *"read
DAILY_RESEARCH_RUNBOOK.md on branch `claude/coding-bot-ab-test-results-ffmhxw` and execute
today's cycle exactly."* Session memory dies at the end of each run — **git is the only
memory.** Everything you conclude must be committed the same cycle or it never happened.

This runbook is executable and self-contained. It supersedes nothing in `BOT_CHARTER.md` —
the charter holds the *governance* (rails, promotion gate, factory philosophy); this runbook
is the *operational procedure* that carries them out. When the two ever disagree, the charter's
rails win and you fix the runbook.

---

## 0. THE PRIME DIRECTIVE
Maximize **realized, risk-adjusted EV** of the live Kalshi 15-minute BTC box maker, measured
on day-clustered stats over **forward** data. AUC / strand-rate / fill-rate are diagnostics,
never objectives. When a proxy and realized EV disagree, realized EV wins. One honest verdict
per day beats a broad sweep — the dataset only grows ~1 day per cycle.

---

## 1. SAFETY RAILS — read every run, never violate
1. **NEVER edit `live.yml`, `LIVE_SWITCH`, loss limits, or any live sizing/quoting flag
   autonomously.** Live changes are **PROPOSE-ONLY**: prepare the diff on a branch, write the
   proposal into the scoreboard + DECISION_MAP, stop. The operator's word is required to deploy.
2. **Promotion gate** (calling anything "deploy-ready"): day-clustered **t ≥ 2** vs the live
   arm over **≥ 10 FORWARD days** (data the arm's design never saw), train-select on earlier
   data / test-validate on the held-out subset. In-sample or replay results are *hypotheses*.
3. **2b — the gate applies to FIXES too.** A compelling mechanism story is not evidence.
   Manufacture the missing population if the corpus lacks it (e.g. re-run the replay with the
   architectural condition imposed) and validate against the standard gates.
4. **Replication gate:** any result that would feed a live deploy must reproduce on an
   independent re-implementation before promotion. Two matching numbers or it isn't real.
5. **Early promotion** is allowed ONLY via the always-valid confidence sequence
   (`avseq.py`, surfaced by `box_shadow_report.py`'s early-promotion flag) — NEVER by a naive
   "first day t>2" peek (optional-stopping inflates false-positives to ~22%). Honest caveat:
   for a stack-strength effect (~t2.8) avseq typically fires ~day 14 > 10, so the fixed gate is
   usually the faster path anyway. Early-eligible only means "prepare the proposal now."
6. **De-risking exception:** only *reverting to a previously-validated config* or *stopping
   trading entirely* may proceed on operator word alone. Re-risking always needs a study.
7. **Volume-cut artifact** (the recurring trap): on a negative-mean replay, skipping ANY set
   of windows raises per-window EV. A veto/skip/sizing result is meaningless without a
   **volume-matched null** (does it skip the *worst* windows beyond chance?) or forward data.
   Always report veto-rate alongside EV. See DECISION_MAP node K and OV-ORTHO for worked cases.
7b. **REALIZED-P&L MANDATE** (node METRIC-INVALID, 2026-07-14): score strategies on REALIZED box
   settlement P&L reconciled to the BALANCE — never on markout, paper-shadow "net/win", or any
   mark/estimate proxy. The month-long av_stoikov "winner" was scored on markout-Δ-vs-baseline
   (rebate-inclusive, per-win units, simulated fills): it rated a *losing* live baseline at +6.9/win
   while the account bled. `window_mark` == paired-box realized ONLY for truly-complete boxes; it
   still ignores strand settlement variance, fractional residuals, and open-position marks. Run
   `python realized_pnl.py --start ... --end ...` (research branch) every cycle; if telemetry and
   balance diverge, the balance wins and the strategy is NOT a winner. Box_shadow's `locked` field
   (box economics) is an acceptable proxy for the negative-width leak specifically, but absolute
   claims still require the balance reconciliation.
8. **Token budget ~100k per cycle.** Prefer local python over subagents. One focused question.
9. **No new external accounts/services.** Public read-only APIs only (Kalshi, data.binance.vision,
   Deribit public). No new paid infra.
10. **Commit everything to `claude/coding-bot-ab-test-results-ffmhxw` the same cycle.** Append to
    DECISION_MAP verdicts in place; never rewrite history. Every commit ends with the standard
    co-author + Claude-Session trailer.

---

## 2. BOOT SEQUENCE (context load — do this first, every run)
```
git fetch origin claude/coding-bot-ab-test-results-ffmhxw claude/polymarket-bot-live-ready-vw7ut5 live-state gha-data main
```
Then READ, in order (they are the accumulated memory):
1. `DAILY_RESEARCH_RUNBOOK.md` (this file) — the procedure.
2. `BOT_CHARTER.md` — governance, standing context, research queue, do-not-study list.
3. `DECISION_MAP.md` — the verdict registry (every choice + status). **The source of truth.**
4. `FORWARD_LEDGER.md` — forward evidence table + daily entries + promotion gate dates.
5. `PAIRING_FINDINGS.md` — methodology / older study detail (skim as needed).

### Branch & data map
| what | branch | path |
|---|---|---|
| research memory (this doc, DECISION_MAP, ledger, charter) | `claude/coding-bot-ab-test-results-ffmhxw` | repo root |
| bot code + scoring tools (box_shadow.py, box_shadow_report.py, avseq.py, notify.py, kalshi_trader.py) | `claude/polymarket-bot-live-ready-vw7ut5` | repo root |
| live telemetry | `live-state` | `live_state/<YYYY-MM-DD>/` |
| market data + forward arm rows + hires ws | `gha-data` | `gha_data/<YYYY-MM-DD>/` |
| live workflow (NEVER auto-edit) | `main` | `.github/workflows/live.yml` |

Key files: `live_state/<d>/kalshi_winrec_btc15m.jsonl` (per-window live outcomes),
`live_state/<d>/live_metrics_kalshi_btc15m.jsonl` (balance/switch),
`gha_data/<d>/box_shadow_btc15m.jsonl` (forward arm rows, one per window×arm),
`gha_data/<d>/hires_{kalshi,spot}_btc_*.jsonl.gz` (sub-second ws tapes, node P1).

---

## 3. STEP 1 — HEALTH (fail-closed; alert operator on anomaly, else silent)
From the latest `live-state` day:
- **LIVE_SWITCH** on? kill sentinel absent? If the switch is OFF or a kill sentinel exists,
  that is intentional or an incident — do NOT re-enable (rail 1). Note it and alert.
- **Balance trend & floor:** read `live_metrics_kalshi_btc15m.jsonl` last row. Alert if
  balance < **$55** (the pnl_guard floor) or dropped > ~$3 since the prior day.
- **Telemetry freshness:** last winrec age. Healthy runs persist in a batch at the END of each
  ~46-min live session, so up to ~50 min of staleness is normal — only alarm at > ~60 min AND
  no in-progress `live.yml` run (check Actions). (This is the false-positive that bit the
  watchdog on 2026-07-14 — don't repeat it.)
- **F14 fractional-residual scan** (node F14): scan the day's winrec for any window with
  `abs_strand` in (0, 0.5] that escaped the strand machinery, and for `frac_flatten_count > 0`
  (the first successful `count_fp` flatten — a milestone to record). Accumulate the settle-P&L
  drag; flag if running drag > ~5% of EV.

**Alerting:** surface every anomaly prominently in the final scoreboard (that text becomes the
operator's push/email notification). For a genuine bot-health emergency (floor breach, switch
flipped unexpectedly, multi-hour stall) you MAY additionally call `notify.alert_sync(...)` from
the bot branch's `notify.py` if Telegram creds are present in env; otherwise the scoreboard is
the channel. Never take a live action to "fix" it — escalate to the operator.

---

## 4. STEP 2 — INGEST (append the new day to the forward ledger)
- Pull the new day's `gha_data` (box_shadow rows) and `live_state` (winrec/metrics).
- Score the forward arms TWO ways, realized first:
  (a) `python live_anchor.py --days <all live days>` (research branch) — entry-veto arms scored on
  ACTUAL realized P&L (tested==live by construction; node LIVE-ANCHOR). THIS is the promotion
  currency for veto arms; box_shadow deltas are advisory only (fill model is fiction — SIM-LIVE-GAP).
  (b) on the bot branch, run `box_shadow_report.py` over the gha-data
  box_shadow rows to get, **per arm**: day-clustered mean EV/window and t vs the `live` arm,
  strand%, and the **risk benchmark** (variance, CVaR5, worst window/day, day-Sharpe, max
  drawdown). Risk reduction is a first-class promotion criterion — an arm may promote on a
  significant risk cut at EV-neutral (same t≥2 bar on the risk metric).
- Append a dated entry to `FORWARD_LEDGER.md`: per-arm net/window for the day, live realized EV,
  strand rate, and the risk table. Note how many FORWARD days each arm now has (gate = 10).

---

## 5. STEP 3 — VALIDATE (move every open item on the evidence)
For every arm/node currently `forward-testing` in DECISION_MAP + FORWARD_LEDGER:
- Recompute day-clustered stats over its FORWARD days only.
- **Reaches the gate** (t ≥ 2 over ≥ 10 forward days, or avseq early-promo, or a t≥2 risk cut):
  mark `PROMOTED` in DECISION_MAP, **prepare the deploy diff on a branch**, and write the
  proposal into the scoreboard for the operator. Do NOT deploy (rail 1).
- **Goes dead** (t < 0 after ≥ 10 forward days, or byte-identical to live ≥ 10 days): mark dead
  in DECISION_MAP, log the retirement in FORWARD_LEDGER with the stats that justified it, and
  (for box_shadow arms) set it up for pruning + promote the next backlog arm into the slot.
- **Roster hygiene:** the box_shadow ARMS roster should stay ≤ ~10 live arms. If > 10, the
  weakest/inert arms (currently retire-watch: `cell_veto`, `givecap15`) get pruned once they hit
  the 10-forward-day bar. Additions need a one-line replay prior; nothing skips forward
  validation regardless of in-sample t.

### Current forward cohort & gate dates (update as it evolves)
- **07-13 cohort** (hazard_stop, thickbook_veto, cell_veto, givecap15, combined, stack_full,
  stack_lean, c3_share, back2, eth sleeve): first gate decision ~**2026-07-23**.
- **07-14 cohort** (volgate, nsmove): first gate decision ~**2026-07-24**.
- **combined + volgate** (OV-ORTHO): do NOT build as an arm; at the gate, SYNTHESIZE it from the
  individual arms' forward rows and re-run the volume-matched test.
- **F14** (`--flatten-fractional 0.1`): DEPLOYED live; watch for the first `frac_flatten_count>0`
  (confirms the `count_fp` API path). Not a promotion item — a live milestone to record.

---

## 6. STEP 4 — ONE RESEARCH QUESTION (the highest-value open node the new data can move)
Pick the single most valuable `❓`/open node from DECISION_MAP's research queue (Section 8 below
mirrors it). Run it under the **honest study protocol**:
1. **Power check first.** Compute the minimum days/events to detect the hypothesized effect at
   t≥2. If the data can't support a verdict, don't run it — say so and pick another (saves tokens,
   prevents false negatives). (n=6-style provisional results get labeled provisional, not promoted.)
2. **Pre-name the metric and a kill criterion** before looking.
3. **Train-select / test-validate**, day-clustered. In-sample screens on ~13 days overfit fast
   (G7/G8 died this way) — a held-out test is mandatory.
4. **Guard the volume-cut artifact** (rail 7): any skip/veto/sizing lever needs a volume-matched
   null or it doesn't count.
5. **Falsification control** where possible (e.g. a far-leg or wrong-asset mirror that should NOT
   show the effect — back2-on-BTC is the template).
6. Fold the verdict into DECISION_MAP (new node or status change), positive OR negative. Negative
   results are assets — they go in the do-not-study list so they're never re-litigated.

Prefer local python (numpy/sklearn/scipy are available). Subagents only for genuinely parallel
independent sweeps, with `OMP_NUM_THREADS=2`, no timeout wrappers, and numbers-in-the-final-message.

---

## 7. STEP 5 — COMMIT + SCOREBOARD (the daily deliverable)
Commit every changed file to `claude/coding-bot-ab-test-results-ffmhxw` (DECISION_MAP,
FORWARD_LEDGER, any study outputs, this runbook if you improved it). Standard trailer.

End the run with the **5-line scoreboard** (this becomes the operator's notification):
```
1. Live P&L yesterday: <$ / strand% / #windows>  (+ any HEALTH anomaly, bold)
2. Top arm deltas (forward): <arm +Xc t=Y (Nd)>, ...
3. Promotions / deaths / proposals: <what reached the gate; what died; any deploy diff awaiting operator word>
4. Today's verdict: <the one research question + its answer>
5. Tomorrow's question: <the next highest-value node>
```

---

## 8. RESEARCH BACKLOG (EV-ranked; work the top movable one each day)
Mirror of the charter's queue; re-rank as data arrives.
1. **Forward-gate the disposal stack** — the highest-value standing item. Get hazard_stop /
   thickbook / combined / c3_share / stack_* through the ~07-23 gate; prepare deploy proposals.
2. **volgate vs nsmove forward head-to-head** (OV-VOLGATE / OV-2POP-ARM): does the targeted
   near-strike×movement veto beat the broad vol veto on the big-loss subset? Gate ~07-24.
3. **Validate the OV-2POP big-loss predictor forward** (leading |drift| AUC 0.875 was n=6 —
   accumulate the big-loss subset; is it real?). If it holds, iterate nsmove from *veto* to
   *defensive-complete* (mechanistically preferred — the loss mode is adverse completion).
4. **Hires sub-second pre-window analysis** (node P1; ~5 days of ws data ≈ 2026-07-18): the real
   shot at beating the window-level ~0.65 AUC ceiling — sub-second book imbalance / spot vol in
   the seconds before a window opens. C1 at-fill ceiling, L1.5 pre-fill lead, F10 sub-2.4s pool.
5. **ETH tailored wide-quote sleeve** (F1b / back2): forward-validate ETH box economics; a
   potential second sleeve. Judge on ETH day-clustered t vs eth-live, BTC control non-positive.
6. **Fill-model calibration vs live tape** — fit the replay fill model to order_lifecycle × fills
   × book context; collapses opt/pess uncertainty, upgrades all future replays to absolute EV.
7. **OV-ROUND liquidity-cliff** — PARKED; re-run `strike_liquidity_probe.py` only once the tick
   corpus spans ≥ 12 distinct $1000 bands (many weeks of wider BTC range).
8. **Cross-venue Kalshi↔Polymarket box persistence** — new pool, real engineering lift; after 1-6.

---

## 9. DO-NOT-STUDY LIST (closed honestly — do NOT re-litigate)
Window/calendar/hour/cell selection; BTC box-count levers (F4/F4b/F4c/F4d/F-size); disposal
micro-optimization within ~1c of floor (L3); width-gated pairing (F11); stale-quote sniping at
≥2.4s (F10); near-strike ENTRY rules (NS-DISP/NS-QUIET/NS-QUOTE — all 5 approaches exhausted, the
disposal stack is the only strand lever); strike round-number PLACEMENT (OV-ROUND — Kalshi sets
strike at spot); persistent-market-regime as the streak cause (OV-STATE — states don't persist).

---

## 10. FAILURE HANDLING
- **Missing/late data** (new day not on gha-data/live-state yet): note it, run HEALTH + VALIDATE on
  what exists, defer the research question, and say so in the scoreboard. Don't fabricate.
- **Study can't be powered:** don't run it (rail-adjacent to §6.1). Pick the next node or spend the
  cycle deepening the ledger/risk tables.
- **Disk full** ("no space left"): delete stale worktrees/caches/large study outputs; a fresh clone
  is not needed. Deletes succeed even when writes fail.
- **Container restart mid-run:** git is the memory — re-fetch, re-read this runbook, resume from the
  last committed step.
- **A tool needs interactive approval** (e.g. some MCP calls): note it couldn't run unattended and
  surface it for the operator rather than blocking.

---

## 11. FACTORY SELF-IMPROVEMENT (do one, as the §6 slot, when no data-question is more urgent)
From lessons learned: (a) a checked-in STUDY TEMPLATE.md; (b) enforce the replication gate in code;
(c) power-check before every study; (d) keep DECISION_MAP the single verdict registry; (e) monthly
FACTORY META-METRICS in the ledger (time-to-verdict, kill rate, false-promotion rate, token/verdict);
(f) extend the same gates+ledger to the other paper sleeves (weather/sports/etf/macro/wti) so capital
allocation across sleeves becomes a factory output, not a vibe. Improve THIS runbook when you find a
gap — it is versioned in §13.

---

## 12. HOW THIS RUN IS SCHEDULED (for the operator; the run itself doesn't touch this)
- Mechanism: a **claude-code-remote Routine** (`create_trigger`, `create_new_session_on_fire=true`)
  firing **daily at 05:00 UTC** — after the prior day's ticks are committed and box-shadow.yml has
  processed them (its cron is `47 */3 * * *`), so the new forward rows exist.
- Trigger prompt (minimal, self-bootstrapping):
  > *"You are the autonomous daily research cycle for the Kalshi 15m BTC box-maker. `git fetch` the
  > research branch `claude/coding-bot-ab-test-results-ffmhxw` and read `DAILY_RESEARCH_RUNBOOK.md`
  > at its root, then execute today's cycle exactly as written, honoring every safety rail. Commit
  > findings to that branch and end with the 5-line scoreboard."*
- Notifications: enable **push + email** on the Routine so the daily scoreboard and any deploy
  proposals reach the operator. A promotion/anomaly line in the scoreboard = the action prompt.
- The operator remains the only actor for live changes (rail 1). The Routine only *prepares* them.

---

## 13. RUNBOOK CHANGELOG
- **2026-07-14 (v1):** created. Consolidates BOT_CHARTER daily cycle + rails + factory roadmap into
  an executable unattended procedure; adds branch/data map, health false-positive guard, volume-cut
  guard, current forward cohorts/gate dates, failure handling, and the trigger spec.
