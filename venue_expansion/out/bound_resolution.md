# Bound resolution -- measurement report

Spec: `BOUND_RESOLUTION_SPEC.md` (registered 2026-10-27, before any price or outcome was read). Code: `venue_expansion/bound_resolution.py`. Data: `out/bound_resolution.json`. No bar was moved, the universe was not widened, no subset was searched. Prices were read only after anchor (b) passed.

## 1. ANCHOR (b) -- bound validity (run first, before any price)

Rule: for every station-day, final `BMAX <= official max` (HIGH) / final `BMIN >= official min` (LOW). A violation is a case where the station's own reported group went beyond what NWS certified = a sensor fault that would have caused a false RESOLVED-NO. **Spec: if the violation rate exceeds 2% the study self-kills before any price is read.** BMAX is in integer degF (group tenths-C -> F -> round half-up), compared with the whole-degree `expiration_value`.

### **Self-kill: NO.** Primary arm (HIGH x 16 non-CST stations), registered rule (S=5): **1 violation(s) in 2037 station-days = 0.049%**, Wilson 95% [0.009%, 0.278%]. Threshold 2%. Unguarded: 1/2037. No variant (unguarded, S=3, 5, 8) exceeds 2%.

**Primary arm -- violation rate and fires retained, by guard setting** (fires = rung-level RESOLVED-NO fires; false lock = a fire on a rung that settled YES; fires counted from observations + official `result` only, no price):

| bound | station-days with a bound | violations | violation rate [Wilson 95%] | fires D=1 | false locks D=1 | fires D=2 | false locks D=2 |
|---|---|---|---|---|---|---|---|
| unguarded (no corroboration) | 2037 | 1 | 0.05% [0.01, 0.28] (1/2037) | 2855 (100.0% of unguarded) | 0 | 2069 (100.0%) | 0 |
| S=3 F | 2036 | 1 | 0.05% [0.01, 0.28] (1/2036) | 2806 (98.3% of unguarded) | 0 | 2024 (97.8%) | 0 |
| S=5 F | 2037 | 1 | 0.05% [0.01, 0.28] (1/2037) | 2850 (99.8% of unguarded) | 0 | 2065 (99.8%) | 0 |
| S=8 F | 2037 | 1 | 0.05% [0.01, 0.28] (1/2037) | 2854 (100.0% of unguarded) | 0 | 2069 (100.0%) | 0 |

**Does the guard remove faults by removing trades?** On the primary arm the guard is nearly irrelevant: it removes 0 of 1 fault(s) at S=5 and cuts D=1 fires by 0.2% (S=3: 1.7%). The one primary-arm fault passes the corroboration guard at every S (a real, corroborated 81 F group where NWS certified 77 F). The guard is not what makes this arm safe -- the arm is safe because HIGH groups at these stations are almost never wrong. The guard earns its keep only on the LOW arms (tables below), where it removes most faults at a modest fire cost.

**Secondary arms (cannot PASS) -- same table, shown because the guard question is only answerable there:**

| arm | bound | station-days | violations | violation rate [Wilson 95%] | fires D=1 | false locks D=1 |
|---|---|---|---|---|---|---|
| SECONDARY_LOW_nonCST | unguarded (no corroboration) | 2035 | 7 | 0.34% [0.17, 0.71] (7/2035) | 1106 | 6 |
| SECONDARY_LOW_nonCST | S=3 F | 2034 | 1 | 0.05% [0.01, 0.28] (1/2034) | 981 | 0 |
| SECONDARY_LOW_nonCST | S=5 F | 2035 | 2 | 0.10% [0.03, 0.36] (2/2035) | 1031 | 1 |
| SECONDARY_LOW_nonCST | S=8 F | 2035 | 5 | 0.25% [0.10, 0.57] (5/2035) | 1078 | 4 |
| SECONDARY_HIGH_CST | unguarded (no corroboration) | 1208 | 1 | 0.08% [0.01, 0.47] (1/1208) | 1356 | 1 |
| SECONDARY_HIGH_CST | S=3 F | 1208 | 0 | 0.00% [0.00, 0.32] (0/1208) | 1338 | 0 |
| SECONDARY_HIGH_CST | S=5 F | 1208 | 0 | 0.00% [0.00, 0.32] (0/1208) | 1351 | 0 |
| SECONDARY_HIGH_CST | S=8 F | 1208 | 0 | 0.00% [0.00, 0.32] (0/1208) | 1354 | 0 |
| SECONDARY_LOW_CST | unguarded (no corroboration) | 1208 | 2 | 0.17% [0.05, 0.60] (2/1208) | 945 | 0 |
| SECONDARY_LOW_CST | S=3 F | 1208 | 2 | 0.17% [0.05, 0.60] (2/1208) | 930 | 0 |
| SECONDARY_LOW_CST | S=5 F | 1208 | 2 | 0.17% [0.05, 0.60] (2/1208) | 945 | 0 |
| SECONDARY_LOW_CST | S=8 F | 1208 | 2 | 0.17% [0.05, 0.60] (2/1208) | 945 | 0 |

**Every violation (all arms, unguarded bound), with station and date.** `excess` = degF by which the station's own bound lies beyond the official value. `corroborated@S` = whether the offending group had a spot temperature within S degF in its 6-hour window; `survives` = whether the day still violates after the guard.

| arm | station | kind | LST date | official | final bound | excess | offending group (report UTC, F) | corroborated @3/5/8 | day still violates @3/5/8 |
|---|---|---|---|---|---|---|---|---|---|
| PRIMARY_HIGH_nonCST | NYC | HIGH | 2026-08-27 | 77 | 81 | 4 | 08-27 23:51Z, 80.96 | True/True/True | True/True/True |
| SECONDARY_HIGH_CST | OKC | HIGH | 2026-06-14 | 79 | 82 | 3 | 06-14 11:52Z, 82.04 | False/False/False | False/False/False |
| SECONDARY_LOW_CST | MSY | LOW | 2026-08-30 | 82 | 81 | 1 | 08-30 11:53Z, 80.96 | True/True/True | True/True/True |
| SECONDARY_LOW_CST | HOU | LOW | 2026-10-12 | 76 | 75 | 1 | 10-12 11:53Z, 75.02 | True/True/True | True/True/True |
| SECONDARY_LOW_nonCST | DEN | LOW | 2026-06-26 | 56 | 24 | 32 | 06-26 17:53Z, 24.08 | False/False/False | False/False/False |
| SECONDARY_LOW_nonCST | DEN | LOW | 2026-07-11 | 57 | 55 | 2 | 07-11 17:53Z, 55.4 | False/False/False | False/False/False |
| SECONDARY_LOW_nonCST | DEN | LOW | 2026-09-05 | 64 | 61 | 3 | 09-05 17:53Z, 60.98 | False/False/True | False/False/True |
| SECONDARY_LOW_nonCST | NYC | LOW | 2026-09-19 | 63 | 55 | 8 | 09-19 11:51Z, 55.04 | False/False/True | False/False/True |
| SECONDARY_LOW_nonCST | NYC | LOW | 2026-09-22 | 59 | 55 | 4 | 09-22 11:51Z, 55.04 | False/True/True | False/True/True |
| SECONDARY_LOW_nonCST | DCA | LOW | 2026-09-26 | 58 | 53 | 5 | 09-26 23:53Z, 52.52 | False/False/True | False/False/True |
| SECONDARY_LOW_nonCST | MIA | LOW | 2026-09-28 | 80 | 75 | 5 | 09-28 11:53Z, 75.02 | True/True/True | True/True/True |

**Known example reproduced (DEN LOW, LST 2026-06-26):** the decoder reads the 06-26 17:53Z 6-hr min group `21044` = -4.4 C = 24.08 F -> 24 F; official is 56 F; the unguarded BMIN is 24 F (violation of 32 F). Corroboration at S=3/5/8 = False/False/False: the guard rejects this fault at every S (no spot temperature in that window is within 8 F of 24 F). This is a LOW-arm fault, so it is outside the primary arm.

Anchor (a) monotonicity of the bound, asserted on every day walked (6488 station-days x 4 bound variants): **0 violations**.

### 1b. Plausibility filter vs corroboration guard, and the two known-bad observation days (coordinator request; no threshold touched)

The METAR-group decoder carries a physical-plausibility filter inherited from `settlement_observability.index_groups`: groups with |T| > 60 C are rejected. Measured effect on this data: **0 groups rejected in the whole May-Oct 2026 record** -- the filter never fires. Violation counts below are identical with and without it, so the guard's contribution and the filter's are separable: the filter's is zero.

| arm | bound | violations / station-days WITH +-60C filter | WITHOUT any filter |
|---|---|---|---|
| PRIMARY_HIGH_nonCST | unguarded (no corroboration) | 1/2037 | 1/2037 |
| PRIMARY_HIGH_nonCST | S=3 F | 1/2036 | 1/2036 |
| PRIMARY_HIGH_nonCST | S=5 F | 1/2037 | 1/2037 |
| PRIMARY_HIGH_nonCST | S=8 F | 1/2037 | 1/2037 |
| SECONDARY_LOW_nonCST | unguarded (no corroboration) | 7/2035 | 7/2035 |
| SECONDARY_LOW_nonCST | S=3 F | 1/2034 | 1/2034 |
| SECONDARY_LOW_nonCST | S=5 F | 2/2035 | 2/2035 |
| SECONDARY_LOW_nonCST | S=8 F | 5/2035 | 5/2035 |
| SECONDARY_HIGH_CST | unguarded (no corroboration) | 1/1208 | 1/1208 |
| SECONDARY_HIGH_CST | S=3 F | 0/1208 | 0/1208 |
| SECONDARY_HIGH_CST | S=5 F | 0/1208 | 0/1208 |
| SECONDARY_HIGH_CST | S=8 F | 0/1208 | 0/1208 |
| SECONDARY_LOW_CST | unguarded (no corroboration) | 2/1208 | 2/1208 |
| SECONDARY_LOW_CST | S=3 F | 2/1208 | 2/1208 |
| SECONDARY_LOW_CST | S=5 F | 2/1208 | 2/1208 |
| SECONDARY_LOW_CST | S=8 F | 2/1208 | 2/1208 |

Fire counts with and without the filter are identical in all arms and cells (checked: True).

**Known-bad days (all four are in the universe).** The faults the verifier found (LAX 2026-05-24: 120 F max / -29 F min; MDW 2026-07-07: -1 F min) are in the IEM **1-minute** feed. They are **not in the METAR 6-hr groups this study uses**: the groups on those days are clean and the bound is valid on all four station-kind-days, guarded or not. So the guard was NOT exercised by these cases -- it is stated plainly that they do not test it. (A corrupted 1-minute stream does pin a running extreme computed from it; a bound built from 6-hr groups is a different data path.)

| station | date | kind | arm | official | IEM 1-min extreme (the faulty feed) | IEM routine extreme | METAR spot range (F) | 6-hr groups (report, F) | final bound unguarded / S=3/5/8 | violates? |
|---|---|---|---|---|---|---|---|---|---|---|
| LAX | 2026-05-24 | HIGH | PRIMARY_HIGH_nonCST | 68 | 120.0 | 68.0 | [60.1, 68.0] | 17:53Z 64.04; 23:53Z 68.0; 05:53Z 66.92 | 68 / 68/68/68 | False |
| LAX | 2026-05-24 | LOW | SECONDARY_LOW_nonCST | 60 | -29.0 | 60.0 | [60.1, 68.0] | 17:53Z 60.08; 23:53Z 62.96; 05:53Z 60.98 | 60 / 60/60/60 | False |
| MDW | 2026-07-07 | HIGH | SECONDARY_HIGH_CST | 84 | 85.0 | 84.0 | [66.9, 84.0] | 11:53Z 69.98; 17:53Z 84.02; 23:53Z 84.02; 05:53Z 82.94 | 84 / 84/84/84 | False |
| MDW | 2026-07-07 | LOW | SECONDARY_LOW_CST | 66 | -1.0 | 67.0 | [66.9, 84.0] | 11:53Z 66.02; 17:53Z 68.0; 23:53Z 82.04; 05:53Z 73.94 | 66 / 66/66/66 | False |

**Synthetic known-answer test of the guard** (NOT data: the coordinator's fault values injected into the real METAR group stream of those days; a 120 F / -1 F / -29 F group all pass the +-60 C plausibility filter, so only the guard can stop them):

| station | date | kind | injected group (F) | official | corroborated @S=3/5/8 | final bound unguarded | final bound guarded S=3/5/8 |
|---|---|---|---|---|---|---|---|
| LAX | 2026-05-24 | max | 120.0 | 68 | [False, False, False] | 120 | [68, 68, 68] |
| MDW | 2026-07-07 | min | -0.9 | 66 | [False, False, False] | -1 | [66, 66, 66] |
| LAX | 2026-05-24 | min | -29.0 | 60 | [False, False, False] | -29 | [61, 61, 61] |

Result: the guard rejects all three injected faults at every S (no spot reading within 8 F), the unguarded bound would be pinned at 120 / -1 / -29 F and would fire false RESOLVED-NO on every rung below/above it. That is the case for the guard; it is a confirmation of mechanism, not a measured rate. The real-data fault rate stays 1/2037 on the primary arm.

## 2. VERDICT (frozen PASS/KILL rule, applied verbatim to the primary arm at L=10)

# **KILL**

Candle coverage of the primary arm: 2854/2854 fired tickers = 100.0% (completed prefix of the seeded shuffled work order, seed 20261027, never re-sorted -- so any prefix is a uniform random subsample).

**PASS bars vs measured, every cell (L=10, primary arm).** A cell must satisfy ALL rows. Both EV weightings and both signed-t readings are required (the stricter reading).

| bar | S=3,D=1 | S=3,D=2 | S=5,D=1 | S=5,D=2 | S=8,D=1 | S=8,D=2 |
|---|---|---|---|---|---|---|
| 1. false-lock <= 2% and Wilson UB <= 5% (all fires) | 0.00% (0/2806), UB 0.14% | 0.00% (0/2024), UB 0.19% | 0.00% (0/2850), UB 0.13% | 0.00% (0/2065), UB 0.19% | 0.00% (0/2854), UB 0.13% | 0.00% (0/2069), UB 0.19% |
| 2. EV volume-weighted >= +2.0c | +2.96c | +1.00c | +2.58c | +1.00c | +2.29c | +1.00c |
| 2b. EV equal-weight >= +2.0c | +7.14c | +1.00c | +6.50c | +1.00c | +5.89c | +1.00c |
| 3. signed day-clustered t (vw) >= Bonferroni bar | t=+1.91 vs bar 4.49 (G=7) | n/a | t=+2.62 vs bar 4.17 (G=8) | n/a | t=+2.71 vs bar 3.96 (G=9) | n/a |
| 3b. signed day-clustered t (eq) >= Bonferroni bar | t=+1.33 vs bar 4.49 (G=7) | n/a | t=+1.39 vs bar 4.17 (G=8) | n/a | t=+1.41 vs bar 3.96 (G=9) | n/a |
| 4. n priced >= 100, days >= 40, stations >= 10 | n=7, days=7, stations=5 | n=1, days=1, stations=1 | n=8, days=8, stations=6 | n=1, days=1, stations=1 | n=9, days=9, stations=6 | n=1, days=1, stations=1 |
| 5. untradeable fraction <= 70% | 99.8% (2799/2806) | 100.0% (2023/2024) | 99.7% (2842/2850) | 100.0% (2064/2065) | 99.7% (2845/2854) | 100.0% (2068/2069) |
| **all bars met?** | NO | NO | NO | NO | NO | NO |

**KILL clauses vs measured:**

| KILL if | measured | triggered? |
|---|---|---|
| false-lock > 5% in the primary cell (S=5,D=1) | 0.00% (0/2850), Wilson UB 0.13% | no |
| L=10 best one-sided 97.9% upper bound on EV < +0.5c | best UB (volume-weighted, equal-weight fallback) = 6.96c; equal-weight reading = 20.94c | no |
| every EV>0 cell misses its n floor (n>=100) | 6 cell(s) with EV>0 | YES |

PASS cells: none.

**Reading, blunt.** The bound is valid and the signal is real; the trade does not exist. (1) Bound validity (anchor b) is excellent: 1 violation in 2,037 primary station-days, **0 false locks in 2850 primary-cell fires** (Wilson UB 0.13%, vs the 2% / 5% bars). The sensor-fault headwind the spec named as the likely cause of death did not materialise on the primary arm. (2) What kills it is price. After a rung is provably dead, the market has already pushed its YES bid to zero: at the first candle at/after signal+10 min the YES bid is 0 on 2779 of 2850 fires (97.5%), so the NO costs 100c and cannot be bought at <= 98c. Only **8 of 2850 fires (0.28%) have any qualifying minute -> untradeable fraction 99.72%** against the 70% bar. The 6-hr group is a lagged digest of temperatures the market priced from live observations before the group was published.

**How the frozen rule lands.** PASS is impossible: bar 4 (n priced >= 100) and bar 5 (untradeable <= 70%) fail by two orders of magnitude in every cell (primary cell: n=8, 8 days, 6 stations; D=2 cell: n=1). KILL is triggered by the clause 'every EV>0 cell misses its n floor' (all 6 EV>0 cells have n<100). The other two KILL clauses do NOT fire: false-lock 0% (not > 5%), and the best one-sided 97.9% EV upper bound is 6.96c (not < +0.5c) -- it is that wide only because n is single digits. So the label is KILL by the letter of the rule, but its evidential content is 'the population is ~99.7% unbuyable', not 'EV is negative'. The EV on the 8 priced entries (volume-weighted +2.58c (t=2.62, bar=4.17, G=8); equal-weight +6.50c (t=1.39, bar=4.17, G=8)) is statistically indistinguishable from zero and sits on 8 observations: the signed t-statistics are below the Bonferroni bar in every L=10 cell, so even the positive point estimates cannot support a PASS. Mean entry cost 92.38c; at 97-98c the maximum possible net per contract is 1-2c after fee, so the +2.0c EV bar is nearly unreachable at those prices even with zero losses.

**Zero-volume entry minutes (stated outright, treated as doubtful fills).** Primary cell S=5,D=1,L=10: 1 of 8 priced entry minutes have ZERO traded volume (12%); the volume-weighted statistic therefore rests on 7 observation(s). Per-cell counts are in the last column of section 3. The +2.0c EV bars (2 and 2b) are nominally met in the L=10 D=1 cells on these 7-9 entries, but PASS still fails on t, n and untradeable fraction, so this does not change the verdict; it does mean even the 8 'priced' entries include quote-only minutes that may not be fillable.

**Caveat that cannot rescue it.** Candle rows exist only for minutes in which the book changed; no back-fill/carry-forward is applied (spec: never back-fill). 69 of 2850 primary fires (2.4%) have no candle row at/after signal+10 min, so a quiet standing bid could in principle be hiding there. Even if **every one** of those became tradeable the untradeable fraction would still be >= 97.3%, far above the 70% bar. Also, the candle window starts at each rung's first signal, so the pre-signal price path is not observed (the repricing time cannot be dated; only that it had happened by signal+10).

## 3. All 6 cells x 2 latency arms

Bonferroni: 6 cells x 2 arms = 12 comparisons, two-sided alpha = 0.05/12 = 0.00417, bar = exact Student-t quantile at p = 0.99792 on realised day-count df (G-1, G = distinct LST days with a priced fire). Signed t: a negative t clearing the magnitude is evidence for KILL, never PASS. EV is fee-inclusive cents/contract, one contract held to settlement, NO bought at `100 - yes_bid`, outcome = Kalshi `result` only. False-lock denominators use EVERY fire (observations + official result); EV uses the priced candle sample. Entries are the first candle row at/after signal+L with cost <= 98c and net > 0 -- if no such row exists the fire is UNTRADEABLE, never back-filled.

### PRIMARY: HIGH markets x 16 non-CST stations (the only PASS-eligible arm)

Candle coverage: 2854/2854 fired tickers (100.0%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | ZERO-volume entry minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 2806 | 0/2806 = 0.00%, UB 0.14% | 2806 | 7 | 99.8% | 7 / 5 | +2.96c (t=1.91, bar=4.49, G=7) | +7.14c (t=1.33, bar=4.49, G=7) | 91.71 | 1 of 7 (14%) |
| 3,1 | 20 | 2806 | 0/2806 = 0.00%, UB 0.14% | 2806 | 6 | 99.8% | 6 / 4 | +1.43c (t=2.80, bar=4.98, G=6) | +1.67c (t=2.50, bar=4.98, G=6) | 97.33 | 1 of 6 (17%) |
| 3,2 | 10 | 2024 | 0/2024 = 0.00%, UB 0.19% | 2024 | 1 | 100.0% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 0 of 1 (0%) |
| 3,2 | 20 | 2024 | 0/2024 = 0.00%, UB 0.19% | 2024 | 1 | 100.0% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 0 of 1 (0%) |
| 5,1 (primary) | 10 | 2850 | 0/2850 = 0.00%, UB 0.13% | 2850 | 8 | 99.7% | 8 / 6 | +2.58c (t=2.62, bar=4.17, G=8) | +6.50c (t=1.39, bar=4.17, G=8) | 92.38 | 1 of 8 (12%) |
| 5,1 (primary) | 20 | 2850 | 0/2850 = 0.00%, UB 0.13% | 2850 | 7 | 99.8% | 7 / 5 | +1.71c (t=4.95, bar=4.49, G=7) | +1.71c (t=3.03, bar=4.49, G=7) | 97.29 | 1 of 7 (14%) |
| 5,2 | 10 | 2065 | 0/2065 = 0.00%, UB 0.19% | 2065 | 1 | 100.0% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 0 of 1 (0%) |
| 5,2 | 20 | 2065 | 0/2065 = 0.00%, UB 0.19% | 2065 | 1 | 100.0% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 0 of 1 (0%) |
| 8,1 | 10 | 2854 | 0/2854 = 0.00%, UB 0.13% | 2854 | 9 | 99.7% | 9 / 6 | +2.29c (t=2.71, bar=3.96, G=9) | +5.89c (t=1.41, bar=3.96, G=9) | 93.00 | 1 of 9 (11%) |
| 8,1 | 20 | 2854 | 0/2854 = 0.00%, UB 0.13% | 2854 | 8 | 99.7% | 8 / 5 | +1.55c (t=5.02, bar=4.17, G=8) | +1.62c (t=3.26, bar=4.17, G=8) | 97.38 | 1 of 8 (12%) |
| 8,2 | 10 | 2069 | 0/2069 = 0.00%, UB 0.19% | 2069 | 1 | 100.0% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 0 of 1 (0%) |
| 8,2 | 20 | 2069 | 0/2069 = 0.00%, UB 0.19% | 2069 | 1 | 100.0% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 0 of 1 (0%) |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 2773, 'no_candles': 63, 'no_candle_after_signal': 6}. State of the first candle at/after signal+10 min: {'yes_bid=0': 2779, 'no_candle_at_or_after_signal': 69, 'yes_bid>=2': 2}.

Entry cost histogram (c), S=5,D=1, L=10: {59: 1, 93: 1, 97: 1, 98: 5}.

### SECONDARY (cannot PASS): LOW markets x 16 non-CST stations

Candle coverage: 1078/1078 fired tickers (100.0%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | ZERO-volume entry minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 981 | 0/981 = 0.00%, UB 0.39% | 981 | 5 | 99.5% | 4 / 4 | +2.16c (t=9.64, bar=7.94, G=4) | +1.80c (t=4.59, bar=7.94, G=4) | 97.20 | 2 of 5 (40%) |
| 3,1 | 20 | 981 | 0/981 = 0.00%, UB 0.39% | 981 | 5 | 99.5% | 4 / 4 | +2.70c (t=7.80, bar=7.94, G=4) | +1.80c (t=4.59, bar=7.94, G=4) | 97.20 | 3 of 5 (60%) |
| 3,2 | 10 | 607 | 0/607 = 0.00%, UB 0.63% | 607 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 3,2 | 20 | 607 | 0/607 = 0.00%, UB 0.63% | 607 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 5,1 (primary) | 10 | 1031 | 1/1031 = 0.10%, UB 0.55% | 1031 | 9 | 99.1% | 7 / 5 | -24.47c (t=-1.13, bar=4.49, G=7) | -9.44c (t=-0.92, bar=4.49, G=7) | 97.33 | 2 of 9 (22%) |
| 5,1 (primary) | 20 | 1031 | 1/1031 = 0.10%, UB 0.55% | 1031 | 9 | 99.1% | 7 / 5 | +2.43c (t=7.35, bar=4.49, G=7) | -9.33c (t=-0.92, bar=4.49, G=7) | 97.22 | 5 of 9 (56%) |
| 5,2 | 10 | 642 | 1/642 = 0.16%, UB 0.88% | 642 | 3 | 99.5% | 2 / 1 | -55.34c (t=-3.29, bar=152.79, G=2) | -31.67c (t=-1.41, bar=152.79, G=2) | 97.33 | 0 of 3 (0%) |
| 5,2 | 20 | 642 | 1/642 = 0.16%, UB 0.88% | 642 | 3 | 99.5% | 2 / 1 | +2.00c (t=n/a, bar=152.79, G=2) | -31.33c (t=-1.41, bar=152.79, G=2) | 97.00 | 2 of 3 (67%) |
| 8,1 | 10 | 1078 | 4/1078 = 0.37%, UB 0.95% | 1078 | 18 | 98.3% | 12 / 6 | -17.20c (t=-1.00, bar=3.60, G=12) | -19.72c (t=-2.60, bar=3.60, G=12) | 96.50 | 7 of 18 (39%) |
| 8,1 | 20 | 1078 | 4/1078 = 0.37%, UB 0.95% | 1078 | 18 | 98.3% | 12 / 6 | +5.32c (t=2.46, bar=3.60, G=12) | -18.00c (t=-2.36, bar=3.60, G=12) | 94.72 | 11 of 18 (61%) |
| 8,2 | 10 | 683 | 4/683 = 0.59%, UB 1.50% | 683 | 10 | 98.5% | 5 / 3 | -32.00c (t=-1.35, bar=5.89, G=5) | -37.10c (t=-3.43, bar=5.89, G=5) | 96.10 | 4 of 10 (40%) |
| 8,2 | 20 | 683 | 4/683 = 0.59%, UB 1.50% | 683 | 10 | 98.5% | 5 / 3 | +6.85c (t=2.53, bar=5.89, G=5) | -33.70c (t=-2.67, bar=5.89, G=5) | 92.60 | 7 of 10 (70%) |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 1000, 'no_candles': 17, 'no_candle_after_signal': 5}. State of the first candle at/after signal+10 min: {'yes_bid=0': 1005, 'no_candle_at_or_after_signal': 22, 'yes_bid>=2': 3, 'yes_bid=1': 1}.

Entry cost histogram (c), S=5,D=1, L=10: {96: 1, 97: 4, 98: 4}.

### SECONDARY (cannot PASS): HIGH markets x 8 CST (UTC-6) stations

Candle coverage: 1354/1354 fired tickers (100.0%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | ZERO-volume entry minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 1338 | 0/1338 = 0.00%, UB 0.29% | 1338 | 2 | 99.9% | 2 / 2 | n/a | +11.50c (t=23.00, bar=152.79, G=2) | 87.50 | 2 of 2 (100%) |
| 3,1 | 20 | 1338 | 0/1338 = 0.00%, UB 0.29% | 1338 | 2 | 99.9% | 2 / 2 | +11.00c (t=n/a, bar=152.79, G=2) | +11.50c (t=23.00, bar=152.79, G=2) | 87.50 | 1 of 2 (50%) |
| 3,2 | 10 | 889 | 0/889 = 0.00%, UB 0.43% | 889 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 3,2 | 20 | 889 | 0/889 = 0.00%, UB 0.43% | 889 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 5,1 (primary) | 10 | 1351 | 0/1351 = 0.00%, UB 0.28% | 1351 | 2 | 99.9% | 2 / 2 | n/a | +11.50c (t=23.00, bar=152.79, G=2) | 87.50 | 2 of 2 (100%) |
| 5,1 (primary) | 20 | 1351 | 0/1351 = 0.00%, UB 0.28% | 1351 | 2 | 99.9% | 2 / 2 | +11.00c (t=n/a, bar=152.79, G=2) | +11.50c (t=23.00, bar=152.79, G=2) | 87.50 | 1 of 2 (50%) |
| 5,2 | 10 | 896 | 0/896 = 0.00%, UB 0.43% | 896 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 5,2 | 20 | 896 | 0/896 = 0.00%, UB 0.43% | 896 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 8,1 | 10 | 1354 | 0/1354 = 0.00%, UB 0.28% | 1354 | 2 | 99.9% | 2 / 2 | n/a | +11.50c (t=23.00, bar=152.79, G=2) | 87.50 | 2 of 2 (100%) |
| 8,1 | 20 | 1354 | 0/1354 = 0.00%, UB 0.28% | 1354 | 2 | 99.9% | 2 / 2 | +11.00c (t=n/a, bar=152.79, G=2) | +11.50c (t=23.00, bar=152.79, G=2) | 87.50 | 1 of 2 (50%) |
| 8,2 | 10 | 898 | 0/898 = 0.00%, UB 0.43% | 898 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 8,2 | 20 | 898 | 0/898 = 0.00%, UB 0.43% | 898 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 1335, 'no_candles': 13, 'no_candle_after_signal': 1}. State of the first candle at/after signal+10 min: {'yes_bid=0': 1334, 'no_candle_at_or_after_signal': 14, 'yes_bid=1': 1, 'yes_bid>=2': 2}.

Entry cost histogram (c), S=5,D=1, L=10: {87: 1, 88: 1}.

### SECONDARY (cannot PASS): LOW markets x 8 CST (UTC-6) stations

Candle coverage: 945/945 fired tickers (100.0%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | ZERO-volume entry minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 930 | 0/930 = 0.00%, UB 0.41% | 930 | 19 | 98.0% | 19 / 7 | +4.58c (t=1.10, bar=3.28, G=19) | +6.63c (t=1.54, bar=3.28, G=19) | 92.32 | 7 of 19 (37%) |
| 3,1 | 20 | 930 | 0/930 = 0.00%, UB 0.41% | 930 | 15 | 98.4% | 15 / 7 | +1.09c (t=9.97, bar=3.42, G=15) | +2.60c (t=2.96, bar=3.42, G=15) | 96.40 | 6 of 15 (40%) |
| 3,2 | 10 | 597 | 0/597 = 0.00%, UB 0.64% | 597 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 3,2 | 20 | 597 | 0/597 = 0.00%, UB 0.64% | 597 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 5,1 (primary) | 10 | 945 | 0/945 = 0.00%, UB 0.40% | 945 | 19 | 98.0% | 19 / 7 | +4.58c (t=1.10, bar=3.28, G=19) | +6.63c (t=1.54, bar=3.28, G=19) | 92.32 | 7 of 19 (37%) |
| 5,1 (primary) | 20 | 945 | 0/945 = 0.00%, UB 0.40% | 945 | 15 | 98.4% | 15 / 7 | +1.09c (t=9.97, bar=3.42, G=15) | +2.60c (t=2.96, bar=3.42, G=15) | 96.40 | 6 of 15 (40%) |
| 5,2 | 10 | 609 | 0/609 = 0.00%, UB 0.63% | 609 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 5,2 | 20 | 609 | 0/609 = 0.00%, UB 0.63% | 609 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 8,1 | 10 | 945 | 0/945 = 0.00%, UB 0.40% | 945 | 19 | 98.0% | 19 / 7 | +4.58c (t=1.10, bar=3.28, G=19) | +6.63c (t=1.54, bar=3.28, G=19) | 92.32 | 7 of 19 (37%) |
| 8,1 | 20 | 945 | 0/945 = 0.00%, UB 0.40% | 945 | 15 | 98.4% | 15 / 7 | +1.09c (t=9.97, bar=3.42, G=15) | +2.60c (t=2.96, bar=3.42, G=15) | 96.40 | 6 of 15 (40%) |
| 8,2 | 10 | 609 | 0/609 = 0.00%, UB 0.63% | 609 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |
| 8,2 | 20 | 609 | 0/609 = 0.00%, UB 0.63% | 609 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 of 0 (0%) |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 808, 'no_candle_after_signal': 75, 'no_candles': 43}. State of the first candle at/after signal+10 min: {'yes_bid=0': 808, 'no_candle_at_or_after_signal': 118, 'yes_bid=1': 9, 'yes_bid>=2': 10}.

Entry cost histogram (c), S=5,D=1, L=10: {17: 1, 79: 1, 94: 1, 96: 1, 97: 2, 98: 13}.

## 4. Anchors (a), (c), (d), (e)

**(a) Monotonicity** -- see section 1: 0 violations on 6,488 station-days x 4 bound variants. (Note: an earlier draft that applied the observability study's 'latest report wins' rule to duplicate/COR groups produced 2 non-monotone guarded bounds on one LOW day (DCA 2026-09-26); the spec's literal definition -- max over ALL decoded groups -- is non-decreasing by construction and is what is used.)

**(c) No look-ahead** -- every fire in every cell and every arm was re-run (31051 (rung, cell) fires over 4352 distinct (station-day, firing-report) pairs) three ways: (1) on the truncated prefix of reports with report time < signal time (report time + 10 min), the bound path and the fire are identical; (2) on reports strictly before the firing report the rung does NOT yet fire (firstness); (3) with every report at/after the signal time replaced by garbage (6-hr max/min groups at +-60 C in random directions, spot temperatures at +-60 C, fabricated groups on reports that had none) the bound path up to the firing event and the fire are identical. Disagreements: **0** (the code asserts and would have aborted).

**(d) Day window** -- reused, not re-derived: `finality_B.build_universe()` day window `[close rounded to the hour - 24h, close]` and the close-hour == LST-midnight filter; re-asserted on all 25952 rungs ((day_end hour) == (-UTC offset) mod 24, window = 86,400 s, max |close_time - LST midnight| = 60 s). Independent consistency check: rung `result` vs `expiration_value` in [lo,hi] disagrees on 0 of 25952 rungs. 6-hr groups are attributed only if their whole 6-hour window `[nominal-6h, nominal]` lies inside the LST day (the 3A rule from the observability study).

**(e) Overshoot-only disclosure -- do these fires land on rungs the DEPLOYED bot already catches?**

Method: the deployed cap-overshoot path (`locked_orders`, margin 1.0 F, KPHX 2.0 F, strict `extreme > cap + margin`, on the glitch-filtered `sustained_extreme` running extreme) was replayed on historical observations: (i) IEM 1-minute data (the best a real-time feed could deliver; only on days with >=1000 1-min obs) and (ii) IEM routine hourly METAR spot temperatures (the runner's default feed). `kwx_runner.py` was read, never imported or modified. 'Deployed locks' = the replay ever reaches the lock condition on that rung during the LST day; 'locked at/before bound signal' = at or before report time + 10 min.

| arm | cell | bound fires | feed | fires with feed | deployed ever locks | deployed never locks | deployed locked at/before the bound signal | >=30 min before the bound signal | median minutes the bound signal trails the deployed lock |
|---|---|---|---|---|---|---|---|---|---|
| PRIMARY_HIGH_nonCST | S,D=5,1 | 2850 | 1-min feed | 1661 | 1108 | 553 | 969 | 879 | 140 |
| PRIMARY_HIGH_nonCST | S,D=5,1 | 2850 | hourly METAR (deployed default) | 2850 | 1012 | 1838 | 618 | 442 | 10 |
| PRIMARY_HIGH_nonCST | S,D=5,2 | 2065 | 1-min feed | 1193 | 1102 | 91 | 1075 | 1009 | 187 |
| PRIMARY_HIGH_nonCST | S,D=5,2 | 2065 | hourly METAR (deployed default) | 2065 | 1011 | 1054 | 729 | 553 | 70 |
| SECONDARY_LOW_nonCST | S,D=5,1 | 1031 | 1-min feed | 609 | 404 | 205 | 374 | 359 | 312 |
| SECONDARY_LOW_nonCST | S,D=5,1 | 1031 | hourly METAR (deployed default) | 1031 | 420 | 611 | 349 | 332 | 250 |
| SECONDARY_LOW_nonCST | S,D=5,2 | 642 | 1-min feed | 383 | 365 | 18 | 364 | 351 | 314 |
| SECONDARY_LOW_nonCST | S,D=5,2 | 642 | hourly METAR (deployed default) | 642 | 399 | 243 | 359 | 339 | 292 |
| SECONDARY_HIGH_CST | S,D=5,1 | 1351 | 1-min feed | 853 | 531 | 322 | 462 | 429 | 197 |
| SECONDARY_HIGH_CST | S,D=5,1 | 1351 | hourly METAR (deployed default) | 1351 | 436 | 915 | 277 | 257 | 70 |
| SECONDARY_HIGH_CST | S,D=5,2 | 896 | 1-min feed | 547 | 523 | 24 | 521 | 499 | 231 |
| SECONDARY_HIGH_CST | S,D=5,2 | 896 | hourly METAR (deployed default) | 896 | 433 | 463 | 352 | 330 | 130 |
| SECONDARY_LOW_CST | S,D=5,1 | 945 | 1-min feed | 632 | 395 | 237 | 368 | 337 | 143 |
| SECONDARY_LOW_CST | S,D=5,1 | 945 | hourly METAR (deployed default) | 945 | 368 | 577 | 322 | 268 | 130 |
| SECONDARY_LOW_CST | S,D=5,2 | 609 | 1-min feed | 404 | 391 | 13 | 388 | 361 | 163 |
| SECONDARY_LOW_CST | S,D=5,2 | 609 | hourly METAR (deployed default) | 609 | 367 | 242 | 336 | 279 | 130 |

**Which is it? An execution/timing improvement on a largely known population, not a new discovery -- with two narrow caveats.** Primary cell S=5,D=1: against a deployed rule on a 1-minute feed, 1108 of 1661 fires (67%) are on rungs the deployed rule also locks, and it locks 879 of them >= 30 min BEFORE the bound can be published (median 140 min earlier): the 6-hr group is slower than the deployed path, not faster. At D=2 the overlap is 92% (1102/1193). Caveat 1 (D=1 only): the other 553 fires (33%) are rungs overshot by only ~1 F (integer bound = cap+1, i.e. group >= cap+0.5 F), which the deployed margin (extreme > cap + 1.0 F, continuous) never reaches. Caveat 2: against the deployed bot's DEFAULT feed (hourly METAR spots) 1838 of 2850 fires (64%) are never locked, because the peak fell between hourly reports and only the 6-hr group saw it -- the bound sees more than the default feed. But on this slice the market is no more generous: the first post-signal YES bid is 0 on 97.5% of fires. Of the 8 priced primary entries, 1 came after a deployed 1-min lock and 0 before one (the rest had no 1-min coverage or no deployed lock). The single standout (SFO 2026-06-28, rung [72,73], group 73.94 F -> 74 F, YES bid still ~28-32c at the signal, NO bought at 59c, settled NO) is a rounding-ambiguity case at the D=1 boundary; one observation in 2,850 is an anecdote, not an edge.

## 5. Every exclusion (count, reason)

| count | reason |
|---|---|
| 35582 | universe rung level (inherited from `finality_B.build_universe`): not_bracket_rung(T_threshold) |
| 39259 | universe rung level (inherited from `finality_B.build_universe`): close_outside_2026-05-23..2026-10-20 |
| 420 | universe rung level (inherited from `finality_B.build_universe`): series_not_in_verified_US_station_map |
| 27 | universe rung level (inherited from `finality_B.build_universe`): no_official_yes_no_result |
| 25956 | universe_rungs_in_scope(bracket rungs, closes 2026-05-23..2026-10-20) |
| 6489 | events_(series,LST-day) after dedupe of rungs |
| 0 | rungs_of_an_event_disagreeing_on_expiration_value |
| 1 | EXCLUDED day: expiration_value not a whole number (e.g. text range '58° to 59°') |
| 4 | rung dropped: rung_on_excluded_day(expiration_value not whole number / duplicate series) |
| 0 | PRIMARY_HIGH_nonCST: station-days with no decoded in-window 6-hr group (no bound; cannot fire) |
| 1 | PRIMARY_HIGH_nonCST: station-days with no CORROBORATED group at S=3 (guard leaves no bound) |
| 0 | SECONDARY_LOW_nonCST: station-days with no decoded in-window 6-hr group (no bound; cannot fire) |
| 1 | SECONDARY_LOW_nonCST: station-days with no CORROBORATED group at S=3 (guard leaves no bound) |
| 0 | SECONDARY_HIGH_CST: station-days with no decoded in-window 6-hr group (no bound; cannot fire) |
| 0 | SECONDARY_HIGH_CST: station-days with no CORROBORATED group at S=3 (guard leaves no bound) |
| 0 | SECONDARY_LOW_CST: station-days with no decoded in-window 6-hr group (no bound; cannot fire) |
| 0 | SECONDARY_LOW_CST: station-days with no CORROBORATED group at S=3 (guard leaves no bound) |
| {'hist|None': 3603, 'live|None': 2571, 'none|hist:HTTPError:404': 27, 'none|live:HTTPError:404': 30} | candle fetch outcomes by source|error (a 404 on both endpoints = no candles = counted UNTRADEABLE, never dropped) |
| 0 | PRIMARY_HIGH_nonCST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 100.0%) |
| 0 | SECONDARY_LOW_nonCST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 100.0%) |
| 0 | SECONDARY_HIGH_CST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 100.0%) |
| 0 | SECONDARY_LOW_CST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 100.0%) |
| 0 | days dropped for the value of the official outcome (none were) |

UNTRADEABLE fires are not exclusions: they stay in the denominator of the untradeable fraction (breakdown in section 3). Violating station-days (anchor b) are NOT excluded from fire or EV counts either; they sit in the false-lock numerator whenever they produce a fire on a YES rung.

## 6. Findings that contradict or qualify the spec's premises

1. **The sensor-fault headwind is not the cause of death.** The spec predicted faults as the most likely killer. On the frozen primary arm the final-bound violation rate is 1/2,037 (0.05%, Wilson UB 0.28%) and there are 0 false locks in all six cells (UB 0.13-0.19%). The famous DEN 24 F fault is a LOW-market fault (DEN LOW 2026-06-26), outside the HIGH-only primary arm; the guard rejects it at every S. A 2% false-lock bar is NOT unreachable for HIGH/non-CST. Faults concentrate in the LOW arms (unguarded 7/2,035 non-CST LOW days), where the guard cuts them to 1-2 at S=3-5 for a 7-11% fire cost.
2. **The guard is nearly irrelevant on the primary arm** (removes 0 of 1 fault; cuts 0.2-1.7% of fires) and **the +-60 C plausibility filter never fires** (0 rejected groups in the whole record). The only primary-arm fault (NYC 2026-08-27: station group 81 F, corroborated by spot temperatures, NWS certified 77 F) also contradicts the spec's statement that NWS builds the CLI from these recorded extremes -- in at least one case it did not. That fault produced no false lock only because the YES rung [76,77] is not in the universe for that day.
3. **'Known hours before close' is true and is not an edge.** The bound is available a median of 486 min (8.1 h; p10 307 min, p90 669 min) before close on primary-cell fires (it is published at the synoptic reports), as the spec says. The market, however, had priced the dead rungs to a zero bid by then: the information in a 6-hr group is a lagged summary of live observations. The spec's break-even arithmetic (f ~ 1% at 98c) never mattered because there are almost no sub-98c entries to be wrong on.
4. **The 6-hr group is slower than the deployed path**, so this is an execution/timing question on a known population (anchor e), not a new population.
5. **Interpretation choices made where the spec was silent (disclosed):** (a) BMAX/BMIN are integer degF (tenths-C -> F -> round half-up) and compared to the whole-degree official value; (b) the corroboration guard is two-sided |spot - group| <= S over reports in [nominal-6h, the group's own report time] (the only reading that cannot look ahead); (c) the guarded bound is the running max/min over corroborated groups only; (d) duplicate/COR groups each count as a decoded group (spec-literal; makes the bound monotone by construction -- the observability study's 'latest wins' rule produced 2 non-monotone guarded bounds on one LOW day and was rejected for that reason); (e) the 'violation rate' used for the self-kill is the primary arm at the registered S=5, with all other variants shown (none exceeds 2% either, so the choice is immaterial); (f) the KILL clause 'best one-sided 97.9% UB < +0.5c' uses the volume-weighted reading (Build-B precedent) with equal-weight as fallback; the equal-weight reading is also shown and gives the same verdict.
6. **Secondary arms (cannot PASS)**: LOW non-CST, HIGH CST, LOW CST are reported in section 3. They show the same price wall (untradeable >= 97%). CST arms also fail structurally: their last tiling group is published ~7 min before close, so fires on that final group have signal+10 min after close. Their positive-looking EVs rest on 2-19 entries, mostly zero-volume or 97-98c, and are not evidence of anything.
7. **Process notes.** Candle fetch used `/historical/markets/{ticker}/candlesticks` before 2026-08-28 and live `/series/.../candlesticks` after (historical rows use `close`, aliased by `finality_B._adapt`); 57 tickers returned 404 on both endpoints (no candles; counted UNTRADEABLE). All 6,231 fired tickers were fetched (100% coverage), in a seeded shuffled order (seed 20261027) that was never re-sorted. No file in `cache/finality/` or `cache/settlement_obs/` was written, and no live-trading file was touched. `finality_B.py` carries uncommitted edits from another study; it is imported but was not modified or committed here.

