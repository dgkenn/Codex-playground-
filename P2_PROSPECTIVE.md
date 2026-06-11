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

## Pre-registered decision rule (FROZEN 2026-06-11 — do not tune to the data)
Scored by `box_policy_ab.py` on forward collector windows (ws on/after the freeze date). Deploy P2
to live **iff ALL hold**:
1. **n ≥ 300** forward windows scored, AND
2. paired diff (P2−P0) **t-stat > 3.0** (clearly positive, well past the 2-sigma in-sample level), AND
3. **P2 max-drawdown ≤ 1.25 × P0 max-drawdown** (the risk-of-ruin guard — P2's whole risk is that
   it re-introduces directional variance; if its drawdown balloons, we reject even if the mean wins).

If n ≥ 300 and the bar is NOT cleared → **keep P0**; P2 is retired as a shadow hypothesis.
The decision is the operator's, brought when `box_policy_ab.py` prints `*** P2 CLEARS THE BAR ***`.

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
