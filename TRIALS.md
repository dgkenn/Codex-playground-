# Trial strategies under prospective A/B test

Every strategy here is scored vs the live **P0 (always-pair, ungated)** baseline on FORWARD
collector windows by `box_policy_ab.py`, and held to the two-tier rule in `P2_PROSPECTIVE.md`
(2-sigma Telegram alert → review; 3-sigma + drawdown guard over n≥300 → deploy decision).
Nothing here touches live money until it clears the bar. To add one, append to the `TRIALS`
registry in `box_policy_ab.py`; it auto-enrolls in the accumulation, the metrics, and the alert.

## Data each trial needs — and where it comes from (all collected live)
The collector reconstructs, per fill, the full decision-time feature set from streams it already
records (verified captured):

| feature | meaning | source stream |
|---|---|---|
| `p` | YES-equiv price of the leg | book (best bid/ask) |
| `spread` | a−b at that minute | book |
| `k`, `tau` | minute in window / fraction left | window clock |
| `sig` | 3-min spot move, signed +=adverse to the side | book `spot` + Binance feed |
| `flow` | prior-minute taker imbalance (signed contracts) | trades tape |
| `depth` | min of top-5 displayed size each side | book (full depth) |
| `oi` | window open-interest slope | stat (OI — fixed 2026-06-11) |
| `settle` | realized $/contract held to settlement | shadow_windows result |

## The 10 new strategies (+ the original P2)

### Toxicity / price gates — skip opening adverse legs
- **t01_deep_tail_skip** — don't open a leg whose YES-equiv price is <0.15 or >0.85.
  *Grounding:* tape, deep-tail [0,0.20) settles −1.49¢/fill (t=−3.52).
- **t02_yes_caution** — YES-side opens require spread ≥0.02; NO opens unrestricted.
  *Grounding:* tape, YES fills −1.3¢ vs NO +1.3¢, structural across all three time-thirds (H7 survived).
- **t03_early_window** — only open in the first 8 minutes (k≤8).
  *Grounding:* live, minute-0–1 fills +3.24¢/fill; fills past 60s decay to ~0 then −2.8¢ by 300s.
- **t07_spot_gate** — don't open the side a >8 bps/3-min spot move runs against (sig>8).
  *Grounding:* queue-replay spot8 gate; the side a trend runs over is the toxic unpaired leg.

### Completion-aware opening — *target legs that will PAIR; exclude likely orphans* (your idea)
- **t04_thin_book** — open only when min top-5 depth < 5,500.
  *Grounding:* rich-stream, thin bilateral book → ~75% completion vs ~0% thick (r≈−0.69).
- **t05_flat_oi** — skip opening when window OI slope > 0.5 (rising = informed one-sided).
  *Grounding:* rich-stream, rising OI → slow/incomplete completion (r=+0.97 vs time-to-complete).
- **t06_balanced_flow** — open only when |prior-minute flow| < 250 contracts.
  *Grounding:* rich-stream, directional early flow → one-sided; balanced → two-sided completion.
- **t09_completion_target** — open only when a composite completion score ≥2 (thin book + balanced
  flow + flat OI + 1¢ spread). *Directly* the idea: predict which legs will get paired and take those.
  *Early read (n=16, noise):* drawdown 4¢ vs P0's 59¢, win 81% — orphan-avoidance compresses risk.

### Selective holding of favorable unpaired legs
- **t08_hold_no** — hold an unpaired NO leg to settlement (don't pair); pair YES immediately.
  *Grounding:* H7, unpaired NO settles +1.3¢ (favorable), unpaired YES −1.3¢ (toxic).
- **t10_target_and_hold** — t09's completion-target opening + hold favorable (sig≤0) unpaired legs.
  Combines "take pairable legs" with "let the good orphans run."
- **p2_signal_hold** *(original tie-breaker)* — hold any unpaired leg whose entry signal was favorable.

## Metrics tracked per strategy (the report)
net/win, **OOS net**, **OOS Calmar**, **max-drawdown**, **win%**, **per-fill**, and the **paired
t-stat vs P0**. The live bot itself is tracked separately and more deeply by `kalshi_scorecard.py`
(settlement PnL decomposition, 5s/30s/60s/300s markout curve, effective spread, calibration,
pairing efficiency, inventory). Together: the A/B says *which idea is better*; the scorecard says
*whether the deployed bot is healthy*.

## Your idea, stated plainly
"Target legs likely to become paired / exclude ones unlikely to" = **t04, t06, t09 (target) and
the orphan-exclusion they encode.** The completion score is the live, forward-validated predictor of
pairing; if it holds up to n≥300 it both raises net and — more importantly for risk — collapses
drawdown by never opening the legs that strand. That's the most promising family in the batch.
