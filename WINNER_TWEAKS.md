# 10 more learnings from the winning bots → tweaks → backtest confirmation

> _Historical — superseded by the gating validation + 4-day multi-asset data. Kept for provenance; where this disagrees with current docs, **README.md / GATING.md / INSIGHTS_4DAY.md win**._

Mined from the winners' tape + 35k recorded paper fills + the shadow backtest. Each learning is tied to a
number, and the net effect is backtest-confirmed below.

## 10 learnings (round 3)
1. **The edge is REBATE, not gross.** Even the winners' gross markout is slightly negative; net is
   positive only via the 20% maker rebate (gross −106 vs net +86 on the optimal fill set). → optimize for
   fee-eligible fill VOLUME, never chase gross.
2. **Optimal toxicity gate = `tox > 0.002`, not 0.** Sweeping the gate on 10k real fills: net peaks at
   threshold **0.002 (+85.9)** vs micro_gate's 0 (+83.1) — keep mildly-toxic fills (their rebate beats
   their tiny gross loss); cut only strongly-toxic. +3%. (Applied: `SOFT_MARGIN=0.002`, `micro_soft`.)
3. **Over-gating is the #1 killer.** Stricter thresholds collapse net (tox>−0.002 → **−89.6**; `graded`
   −2.2; `gross_max` +0.5) by shedding rebate-positive fills. Gate the worst ~16%, keep the rest.
4. **No gate = a LOSING bot.** Baseline (no toxicity gate) nets **−70.8** on the same fills; the gate is
   what flips it positive (+83). The single most important component.
5. **Breadth multiplies P&L** (rebate ∝ fills across markets; `corr(pnl,#markets)=+0.59`). One book on 8
   `{btc,eth,sol,xrp}×{15m,5m}` markets ≈ 6–8× the rebate at the same per-fill edge. (Applied: `live_multi.py`.)
6. **100% passive, 0% taker.** The winners never cross the spread; offensive taking (`lag_taker`) backtests
   −8.66. → pure resting maker, no aggression.
7. **Tiny clips (~$2–6).** The winners' median; minimizes per-fill adverse selection/impact. (Our `--post`
   is small; keep it.)
8. **Hold balanced sets to resolution + redeem (no merge gas).** Winners don't actively flatten — a balanced
   Up+Down set settles to $1 for free; avoids flatten churn/fees.
9. **Two-sided ~50/50, delta-neutral, tiny inventory.** Carrying inventory is variance not edge
   (`hedged_big` −47.8); the rebate comes from balanced two-sided flow.
10. **Quote near the touch, not wide.** Winners' fills cluster within a few ticks of the touch; wide quoting
    (`band_p`, restricting to mid) backtests **gross −13.77** (the p≈0.5 mid-band is the most toxic). Tight
    follow-the-touch ladder only.

## The tweaks applied
- **`SOFT_MARGIN=0.002`** — the backtest-optimal gate threshold (`micro_soft` variant); A/B-ing live before
  it replaces `micro_gate` as the deployed default (rigor: don't change money config on a +3% offline edge
  until live-confirmed).
- **Breadth** via `live_multi.py` (8 markets) — already wired.
- Confirmed our deployed core (`live_trader` = `micro_gate`) is the validated edge; complexity (unions,
  bands, big inventory, taking) all backtested worse and are retired.

## BACKTEST — is our bot more profitable than before? YES (two independent confirmations)
**1. Per-window shadow backtest (n=68 live windows), net/win vs the "previous version":**
```
previous (baseline, no gate):   -0.57 /win   (loses)
our bot   (micro_gate):         +4.76 /win   (paired t = +6.80 vs baseline)   <- gross-positive <edge>
```
→ **+5.33/win improvement, t=6.80 (overwhelmingly significant).**

**2. Offline gate sweep on 35k recorded fills (net = markout + rebate over kept fills):**
```
previous (no gate):    -70.8     our bot (micro_gate, tox>0):   +83.1     tuned (tox>0.002):  +85.9
```
→ the gate turns a **losing** bot **profitable** (+154 swing); the tuned threshold adds **+3%**.

**3. Breadth (not in per-window numbers):** running the same edge on 8 markets instead of 1 multiplies the
rebate-driven P&L ~6–8× (`corr(pnl,#markets)=+0.59`).

## Verdict
**Confirmed more profitable.** Our bot = `micro_gate` (tuning to `tox>0.002`) + tiny two-sided clips +
hold-to-resolution + breadth — which is exactly the winners' reverse-engineered playbook. It backtests at
**+4.76/win, t=6.80** vs a **losing** baseline, and the threshold + breadth tweaks add further on top. The
deployable bot is `live_trader` (micro_gate, breadth-ready) + `live_multi.py`; live-pilot per `DEPLOY.md`.
