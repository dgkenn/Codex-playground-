# Forward review 2026-09-30 — two more questions closed, both negative; no winner

Seven weeks of accumulation since 2026-08-10. **No winning strategy.** The batch did something more
useful than confirm old kills: it closed the last two genuinely open questions in the program, both
negatively, and it exposed an error in my own August fix.

## My August cron fix did not work — and the reason is my error

**GitHub Actions honors `schedule:` only from the default branch.** On 2026-08-10 I commented out the
forecast cron on `claude/coding-bot-ab-test-results-ffmhxw`. That has no effect on scheduling. Main's
copy kept the active cron, so the sleeve ran for another seven weeks and accrued **1,914 further
rows** on something already closed four ways.

I had written this exact fact into `LIP_PILOT_README.md` myself ("cron requires the file on the
default branch") and still edited the wrong copy. Now fixed on **main** (commit `4f06c14`), which is
the copy that governs it.

Worth noting for anyone auditing this repo: **main carries nine workflows, more than the code
branch**, including `kwx-digest`, `kwx-marketwatch`, `kwx-synoptic-trial`, `kwx-telegram` and
`kwx-watchdog` — none of which appear on the code branch. Any future "disable the fleet" work has to
be done against main.

## The disarm held — the trading path is genuinely inert

| | 08-10 | now |
|---|---|---|
| `KWX_SWITCH` | off | **off** |
| Near-misses | 1,213 | **1,213** (zero new) |
| Order attempts (`kwx_exec_log`) | 4 | **4** (zero new) |
| Scored fires (`kwx_forward_settled`) | 0 | **0** (phantom purge held) |

Verified the mechanism rather than assuming it: main's `kwx-live.yml` checks out
`BRANCH: claude/coding-bot-ab-test-results-ffmhxw` and reads `KWX_SWITCH` from that checkout, so the
scheduled job still gates on the disarmed file. It spins up every 20 minutes and exits inert.

## Kill #43 — early-lock is now a measured loss, not merely underpowered

The sleeve reached **n=14** and finally has economic content. Previously all its fires had entered at
100c, so P&L was structurally $0 and the only honest verdict was "underpowered."

| | |
|---|---|
| Settled fires | 14 over 12 days |
| Outcome | **11 losses, 3 wins** |
| The 3 "wins" | all entered at **100c** → paid exactly **$0** |
| Mean | **−0.18/contract** |
| Total | **−$2.54** |
| Entry prices taken | 1c, 4c, 6c, 8c, 9c, 27c, 38c, 50c, 87c, 100c |

It took genuinely cheap entries this time — and lost them. Its gate (win ≥99%, EV ≥ +1.1c/ct, t ≥ 3,
n ≥ 30) is unreachable from 21% wins at −18c/ct. **This is the first time early-lock has been
measured rather than starved**, and it is negative. The historical prior (`wx_earlylock_deep_study`,
NULL) is now corroborated forward.

## depth_adaptive — RESOLVED by its own pre-registered rule: DO NOT ADOPT

This was the last `IN-VALIDATION` item in `RESEARCH_LEDGER.md`, waiting since July on a
15-distinct-calendar-day gate it could not meet (86 rows were 3 sweeps of one day).

**The gate is now met**: 4,396 snapshots across **15 distinct days** (2026-09-15 .. 09-29).
The rule was frozen in July as: *if station-median depth swings ≥2× sweep-to-sweep, do NOT adopt —
stay on fixed `DEPTH_CAP=25` permanently.*

**40 of 40 stations swing ≥2×. Median swing ratio 38.9×; maximum 804×.**

```
KXHIGHCHI   12 days   median depth  25 → 3,617   ratio 144.7×
KXHIGHNY    14 days   median depth  44 → 5,491   ratio 124.8×
KXLOWTNOLA  14 days   median depth  17 → 2,577   ratio 151.6×
... 40/40 exceed the threshold
```

**Verdict: DO NOT ADOPT — keep fixed `DEPTH_CAP=25` permanently.** No bar was moved; the rule
pre-dates the data by two months. Reproduce with `depth_adaptive_validation.py`.

## One refinement that goes the other way, stated honestly

That same data resolves a caveat I had flagged as *the* binding uncertainty in `EDGE_SIZING_RESULT.md`:
I said depth was unknown and traded volume was only an upper-bound proxy for size.

Real depth is **median 506 contracts at ≤98c** (p25 208, p75 1,421, max 15,049) — roughly **5× the
98-contract volume proxy** the sizing study used. So **depth was never the constraint.** Substituting
it would lift the oracle ceiling ~5× and move "realistic" capacity from ~$15/mo to roughly ~$75/mo,
which technically crosses into the spec's `50_to_500` canary-only band.

It does not change the verdict, and I want to be precise about why rather than hand-wave it: the
20-minute-latency conversion was **0 of 140**, so at any honest live feed latency the number is **$0**
regardless of how deep the book is. The binding constraint is the **1-in-140 lock-rule conversion**,
not size. The retire call stands on the conversion rate and the structural asymmetry, both untouched
by this.

## The LIP window closed unfunded

**2026-09-01 passed.** The Liquidity Incentive Program was the one contractual-revenue line with a
genuine sign-unknown upside (−$100 to +$300/mo). The pilot was built, registered, safety-reviewed and
shipped switch-off; it needed funding and a markets file that only the operator could author. It
lapsed. Recorded as expired, not as refuted — it was never tested.

## Running total: 43 tested, 43 closed without a deployable edge

The pattern that has held all year held again: **the sleeve that looked merely underpowered turned
out to be losing once it had enough fires to measure.** That happened to the forecast sleeve in July,
and to early-lock now. It is the strongest argument against treating "not yet significant" as
"promising."

## Still armed on main, and now pointless

Both of these have had their questions answered today and are still on cron:

- **`kwx-earlylock`** (3 cron blocks) — measured negative at n=14
- **`kwx-depthprobe`** (3 cron blocks) — its validation question is now resolved

Disabling them on main would leave only `kwx-live` (inert tripwire) and `kwx-watchdog` running.
Flagged rather than done: turning off two more workflows on the default branch is the operator's
call, and unlike the forecast sleeve I was not previously asked to.

---

# CORRECTION (same day, after the n=2,914 analysis completed)

The forecast re-analysis finished after the above was written, and it **falsifies two statements I
made earlier in this program.** Both corrections weaken kills I had called firm. Recording them
prominently because the whole value of this record is that it does not round in its own favour.

## The numbers

Scored 2,695 of 2,914 rows against Kalshi's **official** settlement at executable prices (219 not yet
settled). Split at 2026-08-06, when the corrected `bracket_prob` went live:

| arm | n | days | win | EV/contract | day-clustered t |
|---|---:|---:|---:|---:|---:|
| Pre-fix (buggy model) | 620 | 14 | 39.7% | **−0.0407** | **−4.32** |
| **Post-fix (corrected, forward)** | **2,075** | **51** | 36.3% | **−0.0054** | **+0.10** |
| All | 2,695 | 65 | 37.1% | −0.0135 | −0.51 |

Post-fix arm, day-clustered: mean **+0.0019/ct**, se 0.0188, **95% CI [−0.0351, +0.0388]** — straddles
zero.

## Correction 1 — the corrected model is NOT significantly negative

On 2026-08-10, from a 3-day post-fix arm (n=161, EV −0.0416, t=−1.27), I wrote that the forward data
*"confirmed the counterfactual"* and that fixing the model *"does not rescue the sleeve."*

With 13× more post-fix data the point estimate moved from **−0.0416 to −0.0054** and the t from −1.27
to **+0.10**. The corrected sleeve is **indistinguishable from zero**, not measurably losing. My
earlier claim rested on 3 days of data and did not survive 51. I should not have called an
underpowered arm a confirmation — that is precisely the error this program has documented in others.

## Correction 2 — the bracket bug WAS costing real money

On 2026-08-06 I wrote: *"The bracket bug was a real accounting defect worth fixing — it was never the
reason the sleeve lost money."*

Pre-fix −0.0407 (t=−4.32, significant) versus post-fix −0.0054 (flat) says the opposite: **removing
the bug removed roughly 3.5c/contract of loss.** That is most of it.

**The honest caveat, which matters:** these are different calendar periods, not a randomised A/B. The
improvement could be regime (different season, different market conditions) rather than the fix. What
argues for the fix being causal is that the post-hoc counterfactual I ran *on the pre-fix data itself*
predicted −0.0363 for a corrected model and the realised forward value is −0.0054 — so the
counterfactual was simply wrong, which is itself evidence that re-scoring historical rows under a new
rule does not reliably predict live behaviour under it. Either way, one of my two statements has to
give, and both point to my having been too confident.

## What does NOT change: this is still not a winning strategy

- **EV is still negative** (−0.0054/ct point estimate). Break-even-minus-fees is not an edge.
- **The model still has no skill.** Post-fix Brier: model **0.2719** vs market **0.1578**, against a
  constant base-rate predictor at **0.2131**. The model remains *worse than a constant*. A no-skill
  model trading at fair executable prices should earn approximately zero minus fees — which is
  exactly what −0.0054 looks like. Flat is the signature of no edge, not of a latent one.
- **No exploratory subset rescues it** (uncorrected, not pre-registered, reported for completeness):
  |edge| 0.15–0.25 → −0.0187 (t=−0.32); 0.25–0.40 → +0.0077 (t=+0.80); 0.40–0.60 → −0.0018 (t=−1.53);
  0.60+ → −0.0052 (t=+0.26); side=yes → −0.0087 (t=+0.26); side=no → −0.0024 (t=−0.10). Nothing
  approaches significance in either direction.

## Does the cron disable still stand?

Yes, but **the reason I put in the commit message is now stale and wrong.** I justified it as
"corrected EV about −0.04/contract at t about −4.9" — that was the all-sample figure at n=1,000, and
at n=2,695 the all-sample figure is −0.0135 at t=−0.51. The defensible justification is different and
weaker:

> The sleeve has **no measurable edge and no mechanism to expect one** — its model is worse than a
> constant base-rate predictor, so break-even-minus-fees is the best it should be expected to do.
> Disabling stops indefinite accrual on a sleeve with a negative point estimate and no skill; it is
> not justified by a statistically significant loss, because at n=2,695 there no longer is one.

A defender of the sleeve could reasonably ask for it to keep running to resolve whether the true
value is slightly positive or slightly negative. I would decline on the Brier evidence, not on the
EV — but that is a judgement call, not a measurement, and the operator should know it is one.
