# BOUND RESOLUTION — pre-registered spec (REGISTERED 2026-10-27, before any price or outcome is read)

## Why this exists: my frozen decision rule in SETTLEMENT_OBSERVABILITY_SPEC asked the wrong question

That measurement returned **OBSERVABLE-BUT-NOT-LIVE** and that verdict stands — I am not overriding
it or moving its thresholds. But it evaluated rate and timing on the **pooled** feed, and pooling
hid the only cell that matters. From its own pre-registered tables (HIGH/LOW split and per-station
stratification were both required by that spec's anchors, so these are registered outputs, not a
post-hoc slice):

**Feed 3A — 6-hour METAR group tiling — on HIGH markets, by station offset:**

| offset | stations | 3A HIGH accuracy | days final ≥30 min before close | median lead |
|---|---|---|---|---|
| UTC−5 | 9 | 98.5% (n=1,045) | **100%** | **307 min** |
| UTC−7 | 2 | 98.9% (n=285) | **100%** | 69 min |
| UTC−8 | 5 | 99.7% (n=662) | **100%** | 126 min |
| UTC−6 | 8 | 99.8% (n=1,191) | 0% | 7 min |

So for the **16 non-CST stations on HIGH markets, the reconstruction is 98.5–99.7% accurate and
available a median of 69–307 minutes before close, on 100% of days.** The observability report's
summary line — "no variant is both accurate and early" — is true pooled and true for LOW, and
false for exactly this cell.

**Two errors in my own frozen rule produced that masking, and both were predictable in advance:**

1. **Pooling HIGH and LOW.** The hours the 6-hr tiling fails to cover are the *late-night edge
   hours*. Those can never contain a daily maximum and frequently contain a daily minimum. So the
   tiling is structurally near-complete for HIGH and structurally broken for LOW (86.5%). Pooling
   averaged a good feed with a broken one. I should have split the bar, not merely the reporting.
2. **Demanding the final extreme.** A trading rule never needs the day's final extreme. The running
   max over the 6-hr groups published *so far* is a **settlement-consistent lower bound** on the
   official value. A lower bound alone resolves **NO on every rung lying entirely below it.** You do
   not need to know where the max ends up to know that a `[87,88]` rung is dead once the bound reads
   91. That is strictly weaker than what I asked for, and it is available at **every** synoptic
   hour rather than only the last one. The observability report notes this obliquely: using only the
   group containing the extreme, 3A is final ≥30 min before close on **98.3%** of days.

This spec tests that weaker, correct question. It is not a re-run with relaxed bars: **every
statistical bar below is carried over verbatim from `TERMINAL_FINALITY_SPEC.md`.** Only the input
feed and the signal's logical form change.

## The signal — monotone bound resolution (obs-only, no price, no outcome)

For a station-day, walk the routine METARs in time order. Maintain:

- `BMAX(t)` = max over all decoded 6-hr max groups (`1STTT`) whose 6-hour window closed at or
  before `t` and lies inside the LST day. Non-decreasing in `t`.
- `BMIN(t)` = min over the corresponding 6-hr min groups (`2STTT`). Non-increasing in `t`.

These are lower/upper bounds on the official daily max/min **in the settlement source's own
units**, because NWS builds the CLI from these recorded extremes.

At each `t`, declare **RESOLVED-NO** on a still-open rung `[lo, hi]` when:

- **HIGH market**: `BMAX(t) >= hi + 1` — the recorded max has already exceeded the rung's cap, so no
  value inside `[lo,hi]` can be the day's max. (`+1` because the official value is a whole degree
  and `hi` itself settles YES.)
- **LOW market**: `BMIN(t) <= lo - 1` — symmetric.

No YES claim is made and no never-arrival claim is made. **Overshoot only.** This is deliberate:
overshoot is the only direction a monotone bound can settle without knowing the future, and the
asymmetry is the whole point of the idea.

**Sign-flip guard, registered as part of the signal:** a RESOLVED-NO fires only if the decoded group
is corroborated by the station's own routine spot temperatures — at least one spot observation
within the group's 6-hour window within 5 °F of the group value, in the same direction. See the
sensor-fault section; this guard is part of the rule, not a filter applied after seeing results.

Grid (frozen): corroboration slack `S ∈ {3, 5, 8}` °F · minimum margin `D ∈ {1, 2}` °F beyond the
cap · **no other free parameters**. 6 cells. Primary cell declared now: `S=5, D=1`.

**Universe, frozen:** HIGH markets (`KXHIGH*`) only, at the **16 non-CST stations** (UTC offsets
−5, −7, −8). Both restrictions are declared here *because they are mechanistic, not fitted*: LOW is
excluded because the uncovered hours are the night hours that contain minima, and CST is excluded
because its tiling completes only 7 minutes before close. Reported alongside, as pre-declared
secondary arms that **cannot produce a PASS**: LOW markets, and CST stations.

## Latency

Signal timestamp = the METAR report time carrying the last group used, **+ 10 minutes** (MADIS
publication lag). Arms `L ∈ {10, 20}` reported; **`L=10` decides deployability.** `L=0` is not run —
the observability study established the group's publication time, so a zero-latency arm would be
fiction.

## Entry

A RESOLVED-NO fire buys **NO**, so its executable cost is **`100 − yes_bid`** — never
`100 − yes_ask`, which is the NO bid and unfillable by a buyer. This error has already invalidated
work in this repo. First candlestick at/after the latency-adjusted signal with cost ≤98c and
fee-inclusive net > 0; fee `ceil(7·p·(1−p))` at the crossing price. No qualifying minute ⇒
**UNTRADEABLE**, counted, never back-filled from a better print. One contract per fire, held to
settlement. Outcome = Kalshi official `result` only.

## The sensor-fault headwind, quantified before testing

The observability study found station sensor faults that the official value **rejects**: DEN
reported a 24 °F daily minimum in June in *both* its 6-hr and 24-hr groups while the official value
was 56 °F. The independent decoder agreed on all 37,545 groups, so this is the station transmitting
garbage and NWS QC discarding it — not a decode bug. Any decoder inherits it.

This matters more than the headline accuracy: at a 98c entry, EV `= 100(1−f) − p − fee`, so
break-even false-lock `f ≈ 1%`. A ~0.7% fault rate consumes most of the entire error budget before
any other error source. **This is the most likely cause of death for this spec and it is stated
before the test, not after.** The corroboration guard above is the registered attempt to remove it;
the report must state the guard's measured effect on both false-lock rate and fire count, because a
guard that removes the faults by removing the trades is not a fix.

## PASS / KILL — carried over verbatim from TERMINAL_FINALITY_SPEC, no bar relaxed

Bonferroni over 6 cells × 2 arms = **12 comparisons**; two-sided α = 0.05/12 = 0.00417 ⇒ bar is the
exact Student-t quantile at p=0.99792 on realised day-count df. **Signed** t: a negative t clearing
the magnitude is evidence for KILL, never PASS.

**PASS** requires ALL, in the `L=10` arm, in ≥1 cell, on the frozen HIGH / non-CST universe:
1. false-lock rate ≤ **2%** with Wilson 95% upper ≤ **5%**
2. volume-weighted **and** equal-weight fee-inclusive EV ≥ **+2.0c/contract** (both weightings, the
   stricter reading)
3. signed day-clustered t ≥ the exact Bonferroni bar
4. n ≥ **100** priced fires across ≥ **40** distinct days and ≥ **10** stations
5. untradeable fraction ≤ **70%**

**KILL** if: false-lock > 5% in the primary cell; or the `L=10` best one-sided 97.9% upper bound on
EV < +0.5c; or every EV>0 cell misses its n floor.

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) Monotonicity of the bound.** `BMAX` non-decreasing, `BMIN` non-increasing within the LST
  day, asserted on every day walked. A violation means the group-window attribution is wrong.
- **(b) Bound validity.** On every day, the final `BMAX` must be ≤ the official value + 0 and the
  final `BMIN` ≥ official − 0 **in the direction the bound claims** (i.e. `BMAX ≤ official_max`).
  Report every violation with its station and date — these are precisely the sensor faults, and
  their rate is the irreducible false-lock floor. **If the violation rate exceeds 2%, the spec
  self-kills before any price is read**, because no entry rule can beat its own bound's error rate.
- **(c) No look-ahead.** The decision at `t` reads only METARs with report time `< t`. Re-run each
  fire on the truncated prefix and under adversarial replacement of all later observations; abort
  on any disagreement.
- **(d) Day window.** Reuse the LST day window and `close_time` assertion already proven in
  `finality_B.py` and re-verified by `settlement_observability.py`. Do not re-derive.
- **(e) Overshoot-only disclosure.** Report fire counts against the *deployed* bot's existing
  cap-overshoot path. If this rule fires on the same rungs the deployed rule already catches, the
  finding is an execution improvement, not a new population — say which it is.

No bar in this document may move after 2026-10-27. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract live canary.
