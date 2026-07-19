# K-WX profitability review — toward $4k/month (2026-07-19)

Full code + workflow + research-artifact review of the Kalshi weather-nowcast bot
(code lives on `claude/coding-bot-ab-test-results-ffmhxw`; orchestration on `main`).

## Where the bot stands today

- The live chain **is running** (self-chaining ~17-min GitHub Actions legs, switch `on`,
  secrets present), in **paper mode**: the gate is accruing toward
  `win>=99%, EV>=+0.12, t>=3, n>=30` with **0 settled fires so far**.
- The early-lock paper sleeve was added to the cron **today**; it has no rows yet.
- The forecast sleeve is calibrated but paper-only, no settled rows.

## The $4k/month math (honest)

$4k/mo ≈ $920/wk. Validated numbers from the repo's own studies:

| stage | modeled profit |
|---|---|
| mechanical lock, free feed (~10–20 min latency) | ~$900/mo |
| + Synoptic 1-min feed (~2× fires, better EV/ct) | ~$2,280/mo |
| measured depth ceiling of the whole edge | ~$1.1–1.6k/wk ≈ $4.4–6.4k/mo |

So **$4k/mo sits at ~80% of the edge's total measured capacity**. It is reachable, but
only with: the paid fast feed, a persistent host, DEPTH_CAP raised if the live probe
justifies it, and at least one additional sleeve (early-lock is the best candidate:
if early rungs are buyable ≤92c it is ~4× the baseline EV/ct). Free-feed GH-Actions
mode alone tops out around ~$1k/mo. Also requires ~$1–2k of bankroll once compounded —
below that, capacity isn't the binding constraint, bankroll is.

## Bugs found (fix before trusting the gate or going live)

1. **State persistence is broken — the paper gate can never accrue as deployed.**
   `kwx-live.yml` runs
   `git add -f kwx_runner_plan.jsonl kwx_forward_settled.jsonl kwx_exec_log.jsonl kwx_gate_status.txt kwx_runner_state.json .kwx_heartbeat`.
   `git add` **aborts the entire batch** if any one pathspec matches nothing (verified:
   exit 128, nothing staged). Several of these files don't exist until a fire/settle has
   happened, so on most legs *nothing* is committed — confirmed in the 04:15 UTC run log
   (`.kwx_heartbeat` left untracked, "nothing to commit"). Consequences:
   - paper fires recorded in a leg are **lost** when the runner is recycled → n never reaches 30;
   - `kwx_runner_state.json` (the `fired` dedup set + daily/per-city cap accumulators)
     **resets every ~17 min** → in live mode the same lock would be re-bought every leg and
     the daily-deploy cap would never actually bind across a day;
   - the heartbeat never lands → the watchdog's staleness signal is meaningless.
   Fix: `for f in …; do [ -f "$f" ] && git add -f "$f"; done`.

2. **The documented sustain=3-min filter is not implemented.** `sustained_extreme()`
   (`kwx_runner.py:325-351`) does glitch bounds + >8°F spike rejection, then just takes
   max/min — it never checks persistence and never reads timestamps. The 0.4% all-season
   conditional-loss tail number was validated *assuming* sustain3; the deployed code fires
   on a single non-spike reading, so live tail risk is understated versus the study.

3. **Adaptive cadence is dead in production.** The workflow loops
   `kwx_paper_gate.py --once` + hardcoded `sleep 30`; the runner's 5s/20s near-strike
   polling (`kwx_runner.py:309-321`) is computed and discarded. Moot while the free feed
   is 10–20 min latent, but it must be restored (use the `--loop` mode) before a fast feed
   is wired or the feed money is wasted.

4. **Paper fills are fantasy fills.** Dry-run assumes 100% fill at the cap price
   (`kalshi_exec.py:170`), while the orderbook study measured **21% of books empty at the
   fire instant** and median best-ask size ~13 contracts. The gate's "live==tested" claim
   can't be trusted at face value; expect live EV/fill to come in under paper. Add a
   depth-aware fill model (read the book at fire time, fill min(size, displayed)).

5. **Sizing inconsistencies** (matter once bankroll > $10): bankroll is a hardcoded
   constant, never synced to account equity; Kelly uses a constant p=0.9965 with no fee
   term (fees only exist in the offline sims and settlement); conviction fires don't get
   the p-bump the sim assumes; `MAX_PAY_CENTS=98` admits ~2c-gross entries that are
   ~0/negative EV after the ~1c quadratic fee — consider a fee-aware floor (~96c).

6. **No IOC retry.** If the ask moves between quote fetch and order, the IOC dies and the
   fire is abandoned (dedup marks it fired). One re-poll + re-price attempt is cheap EV.

7. Minor: `WX_CONTACT` defaults to a placeholder email — weather.gov/MADIS throttle on
   bad User-Agents; set the secret. NYC runs quorum=1 (single feed, no cross-check).

## Ordered roadmap

**Phase 0 — correctness (this week, free):** fix the `git add` batch bug; implement real
sustain (or re-run the tail study under "no sustain" and accept the measured number);
persist/restore state every cycle, not just leg-end; set `WX_CONTACT`.

**Phase 1 — let the gate actually run (1–2 weeks, free):** with persistence fixed, the
paper gate can accrue its n≥30 through the US afternoon windows. Don't touch strategy
params meanwhile — the repo's own conclusion ("OPTIMIZATION FRONTIER REACHED") is right:
the next lever is forward data, not more in-sample tuning.

**Phase 2 — latency + realism (~$5–20/mo):** move the runner to a tiny persistent host
(any $5 VPS; kills the whole pre-chain/self-chain/watchdog complexity and the 60–90s
inter-leg gaps); take the 14-day Synoptic trial to *measure* the fast-band upside before
paying; wire the adaptive cadence; add the depth-aware paper fill model and a forward L2
poller that snapshots the book at the fire instant.

**Phase 3 — go-live per the existing runbook:** paper gate → $10 canary → $50 → scale on
realized PnL. No changes recommended to that sequence.

**Phase 4 — capacity (the actual path to $4k/mo):**
- **Early-lock sleeve** — biggest known candidate. Predictability is proven (~96.9% win,
  ~60 min early); the paper price-logger just started. Decision rule already coded:
  deploy only if early rungs settle ≤95.3c with n≥20. Extend to LOWS (unstudied).
- **DEPTH_CAP live probe** — run `wx_capacity_probe.py` during fire windows; raise 25 if
  the measured deep-fire depth supports it (this is "THE lever on the monthly ceiling").
- **Per-station derate softening** — KPHX/KLAX/KMIA/KPHL/KSEA derates were set from the
  raw-1min failure mode that sustain3 removes; small-cushion fires carry ~3× EV, so
  re-measuring under the deployed rule may recover real EV.
- **Predexon L2 backfill** — key already unlocked; replays the whole backtest against real
  depth, converting "assumed fill" EV into measured EV.

## Other angles worth studying (not yet in the repo)

- **Maker-side execution**: post resting bids at 94–97c on rungs *approaching* lock
  instead of paying the ask after the lock — captures the spread and queue priority in
  exactly the thin books that cap this edge. Needs a study of adverse selection on the
  never-locks.
- **Fee-aware fire filter**: skip fires whose gap ≤ fee + 1c; the 98c ceiling currently
  wastes fills on dead rungs.
- **New-market watcher**: `wx_market_coverage.py` as a cron alert so new Kalshi cities /
  weather series (each new city ≈ proportional capacity) are captured on listing day.
- **Winter forward validation**: all live-price evidence is May–July; the tail study says
  winter is fine on *settlement* risk, but gap sizes/liquidity in winter are unmeasured.
- **Sell-side of the ladder was already studied and killed** (SELL99 lowers median growth;
  hold-to-settlement confirmed) — don't revisit.
- Note: the repo is **public**, so the strategy, params, switch state, and fire logs are
  visible to anyone — including other Kalshi traders. Consider making it private (Actions
  minutes then bill, another nudge toward the $5 VPS).

## Bottom line

The edge is real, validated, and safety-engineered well beyond its size — but the deployed
pipeline currently cannot prove it (state-persistence bug) and understates live risk
(sustain filter missing) and overstates live fills (paper fill model). Fix Phase 0, let the
gate accrue, then spend money only on the two things the studies say matter: a fast feed
and a persistent host. $4k/mo needs essentially the full stack — mechanical lock at the
raised depth cap + Synoptic + early-lock sleeve — and even then it's the top of the
validated range; $2–3k/mo is the defensible central estimate for this edge alone.
