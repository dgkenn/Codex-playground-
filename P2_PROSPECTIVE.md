# P2 (signal-selective hold) — pre-registered prospective test

**Status: UNDER PROSPECTIVE TEST. Live trading uses P0 (always-pair). No P2 decision until the
frozen rule below is met on forward data.**

## Why this exists
On the 20,318-fill historical tape, "selectively HOLD a favorable unpaired leg to settlement
instead of pairing it" looked tempting but ambiguous: two independent backtests disagreed, and the
best variant (P2) achieved its Calmar edge by becoming a ~50%-win-rate directional bet with only a
2-sigma in-sample t-stat. That is the classic shape of an in-sample artifact, and it conflicts with
the standing low-risk-of-ruin mandate. So we do **not** decide on the tape it was found on. We let
the live shadow collector accumulate brand-new windows and score P0 vs P2 on data collected AFTER
today, then decide only if a frozen bar is cleared.

## The two policies (scored on the same reconstructed maker fills, held to settlement, |net|<=1)
- **P0 ALWAYS-PAIR** — the live default. Complete the box as soon as the opposite leg fills.
- **P2 SIGNAL-HOLD** — when an unpaired leg's decision-time spot signal was favorable (`sig_adv<=0`),
  HOLD it to settlement instead of pairing; otherwise pair. The candidate "tie-breaker."

## This is a framework: ALL trial strategies follow the same rule
P2 is the first entry in the `TRIALS` registry in `box_policy_ab.py`. Any future policy idea added
there is scored vs the live P0 baseline on forward data and inherits the two tiers below
automatically — no special-casing, same discipline for everything.

## Pre-registered rule (FROZEN 2026-06-11 — do not tune to the data), two tiers
Scored by `box_policy_ab.py` on forward collector windows (ws on/after the freeze date):

**TIER 1 — 2-SIGMA ALERT (be made aware, take action).** When a trial's paired diff (trial−P0)
crosses **|t| > 2.0 over ≥ 100 forward windows**, the hourly `strategy-alert` workflow pushes a
**Telegram alert + GitHub warning** (and appends `STRATEGY_ALERTS.txt`). This is a heads-up to
review — not an auto-deploy — because across many trials a 2-sigma hit happens by chance.

**TIER 2 — DEPLOY BAR (operator decision).** Recommend bringing a trial to live **iff ALL hold**:
1. **n ≥ 300** forward windows, AND
2. paired diff t-stat **> 3.0** (positive; past the in-sample 2-sigma that made P2 untrustworthy), AND
3. **trial max-drawdown ≤ 1.25 × P0 max-drawdown** (risk-of-ruin guard — these trials re-introduce
   directional variance; if drawdown balloons we reject even when the mean wins).

If n ≥ 300 and Tier 2 is NOT cleared → **keep P0**; the trial is retired. The deploy decision is the
operator's, surfaced when `box_policy_ab.py` prints `*** … CLEARS THE DEPLOY BAR ***`.

## How it runs (prospective, automatic)
- The collector workflow scores each freshly collected batch and commits a run-scoped ledger
  fragment (`gha_data/box_policy_ledger_btc_r<runid>.jsonl`) to the `gha-data` branch — so the A/B
  accumulates in the cloud with no extra state.
- Check progress anytime:
  ```
  git fetch origin gha-data && git checkout origin/gha-data -- gha_data/   # pull the fragments
  python box_policy_ab.py --report --asset btc --dir gha_data
  ```
- First read (n=14, smoke test): P2 was BEHIND (−0.93¢ vs +0.55¢/win, t=−0.09) — noise, but a early
  reminder the tape's Calmar edge may not replicate. The rule waits for n≥300.

## What would change live if P2 clears the bar
`kalshi_trader.py` would gain a `--signal-hold` mode: when holding an unpaired leg whose entry
signal was favorable, defer pairing (within the `--max-net 1` cap and the `--close-flatten-tau`
force-flatten) instead of completing immediately. Until then the flag does not exist and P0 stands.

## ADDENDUM (2026-06-13): RISK-IMPROVEMENT deploy track (operator-approved)
The original bar (t>3 vs live AND n>=300, DD guard) is the NET-EDGE gate. It is correctly strict --
t>3 is ~the one-sided Bonferroni threshold for our ~56 trials, so it controls the family-wise
false-deploy rate near 5% on real money. We keep it unchanged for "this beats live on PnL" claims.
BUT most of our research produces net-NEUTRAL, RISK-reducing changes (the R0 spread buffer, edge-
select k5-9/mid-vol, the streak-guard removal). Demanding a positive net t>3 from a change that does
not claim a net edge is a category error -- it can never clear. So we add an ORTHOGONAL track:
  RISK-IMPROVEMENT DEPLOY (all required, frozen; do not tune to data):
    (1) data sufficiency: n >= MIN_WINDOWS (300), same as the net bar;
    (2) net NON-INFERIORITY: lower 95% CI bound of per-window (trial - live_current) net > -0.2c/win
        (NONINF_EPS) -- we are confident it does not hurt net by more than 0.2c;
    (3) MATERIAL tail-risk reduction vs live: MaxDD <= 0.80 * live MaxDD (RISK_DD_FRAC) AND
        CVaR95(trial) < CVaR95(live).
A trial clearing this (but not the net bar) raises a RISK-UPGRADE-READY event (Telegram + annotation
+ STRATEGY_ALERTS trail), promoted ONE at a time per SCALE_GATE like any deploy. t>3 stays the bar
for net-edge claims; this is the safe-upgrade lane. (Implemented in box_policy_ab.py: NONINF_EPS,
RISK_DD_FRAC, risk_ready.) Considered but NOT adopted: effective-n (count acting windows) and lowering
n to 200 -- left for later if the calendar-window count proves too blunt.
