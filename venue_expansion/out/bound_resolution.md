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

## 2. VERDICT (frozen PASS/KILL rule, applied verbatim to the primary arm at L=10)

# **KILL**

Candle coverage of the primary arm: 287/2854 fired tickers = 10.1% (completed prefix of the seeded shuffled work order, seed 20261027, never re-sorted -- so any prefix is a uniform random subsample).

**PASS bars vs measured, every cell (L=10, primary arm).** A cell must satisfy ALL rows. Both EV weightings and both signed-t readings are required (the stricter reading).

| bar | S=3,D=1 | S=3,D=2 | S=5,D=1 | S=5,D=2 | S=8,D=1 | S=8,D=2 |
|---|---|---|---|---|---|---|
| 1. false-lock <= 2% and Wilson UB <= 5% (all fires) | 0.00% (0/2806), UB 0.14% | 0.00% (0/2024), UB 0.19% | 0.00% (0/2850), UB 0.13% | 0.00% (0/2065), UB 0.19% | 0.00% (0/2854), UB 0.13% | 0.00% (0/2069), UB 0.19% |
| 2. EV volume-weighted >= +2.0c | +8.60c | n/a | +8.60c | n/a | +8.60c | n/a |
| 2b. EV equal-weight >= +2.0c | +20.00c | n/a | +20.00c | n/a | +20.00c | n/a |
| 3. signed day-clustered t (vw) >= Bonferroni bar | t=+0.71 vs bar 152.79 (G=2) | n/a | t=+0.71 vs bar 152.79 (G=2) | n/a | t=+0.71 vs bar 152.79 (G=2) | n/a |
| 3b. signed day-clustered t (eq) >= Bonferroni bar | t=+1.05 vs bar 152.79 (G=2) | n/a | t=+1.05 vs bar 152.79 (G=2) | n/a | t=+1.05 vs bar 152.79 (G=2) | n/a |
| 4. n priced >= 100, days >= 40, stations >= 10 | n=2, days=2, stations=2 | n=0, days=0, stations=0 | n=2, days=2, stations=2 | n=0, days=0, stations=0 | n=2, days=2, stations=2 | n=0, days=0, stations=0 |
| 5. untradeable fraction <= 70% | 99.3% (274/276) | 100.0% (196/196) | 99.3% (284/286) | 100.0% (204/204) | 99.3% (285/287) | 100.0% (205/205) |
| **all bars met?** | NO | NO | NO | NO | NO | NO |

**KILL clauses vs measured:**

| KILL if | measured | triggered? |
|---|---|---|
| false-lock > 5% in the primary cell (S=5,D=1) | 0.00% (0/2850), Wilson UB 0.13% | no |
| L=10 best one-sided 97.9% upper bound on EV < +0.5c | best UB (volume-weighted, equal-weight fallback) = 192.65c; equal-weight reading = 307.58c | no |
| every EV>0 cell misses its n floor (n>=100) | 3 cell(s) with EV>0 | YES |

PASS cells: none.

## 3. All 6 cells x 2 latency arms

Bonferroni: 6 cells x 2 arms = 12 comparisons, two-sided alpha = 0.05/12 = 0.00417, bar = exact Student-t quantile at p = 0.99792 on realised day-count df (G-1, G = distinct LST days with a priced fire). Signed t: a negative t clearing the magnitude is evidence for KILL, never PASS. EV is fee-inclusive cents/contract, one contract held to settlement, NO bought at `100 - yes_bid`, outcome = Kalshi `result` only. False-lock denominators use EVERY fire (observations + official result); EV uses the priced candle sample. Entries are the first candle row at/after signal+L with cost <= 98c and net > 0 -- if no such row exists the fire is UNTRADEABLE, never back-filled.

### PRIMARY: HIGH markets x 16 non-CST stations (the only PASS-eligible arm)

Candle coverage: 287/2854 fired tickers (10.1%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | entries with traded volume>0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 2806 | 0/2806 = 0.00%, UB 0.14% | 276 | 2 | 99.3% | 2 / 2 | +8.60c (t=0.71, bar=152.79, G=2) | +20.00c (t=1.05, bar=152.79, G=2) | 78.50 | 2 |
| 3,1 | 20 | 2806 | 0/2806 = 0.00%, UB 0.14% | 276 | 1 | 99.6% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 1 |
| 3,2 | 10 | 2024 | 0/2024 = 0.00%, UB 0.19% | 196 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 20 | 2024 | 0/2024 = 0.00%, UB 0.19% | 196 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 10 | 2850 | 0/2850 = 0.00%, UB 0.13% | 286 | 2 | 99.3% | 2 / 2 | +8.60c (t=0.71, bar=152.79, G=2) | +20.00c (t=1.05, bar=152.79, G=2) | 78.50 | 2 |
| 5,1 (primary) | 20 | 2850 | 0/2850 = 0.00%, UB 0.13% | 286 | 1 | 99.7% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 1 |
| 5,2 | 10 | 2065 | 0/2065 = 0.00%, UB 0.19% | 204 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 20 | 2065 | 0/2065 = 0.00%, UB 0.19% | 204 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 10 | 2854 | 0/2854 = 0.00%, UB 0.13% | 287 | 2 | 99.3% | 2 / 2 | +8.60c (t=0.71, bar=152.79, G=2) | +20.00c (t=1.05, bar=152.79, G=2) | 78.50 | 2 |
| 8,1 | 20 | 2854 | 0/2854 = 0.00%, UB 0.13% | 287 | 1 | 99.7% | 1 / 1 | +1.00c (t=n/a, bar=n/a, G=1) | +1.00c (t=n/a, bar=n/a, G=1) | 98.00 | 1 |
| 8,2 | 10 | 2069 | 0/2069 = 0.00%, UB 0.19% | 205 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 20 | 2069 | 0/2069 = 0.00%, UB 0.19% | 205 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 271, 'no_candles': 12, 'no_candle_after_signal': 1}. State of the first candle at/after signal+10 min: {'yes_bid=0': 272, 'no_candle_at_or_after_signal': 13, 'yes_bid>=2': 1}.

Entry cost histogram (c), S=5,D=1, L=10: {59: 1, 98: 1}.

### SECONDARY (cannot PASS): LOW markets x 16 non-CST stations

Candle coverage: 47/1078 fired tickers (4.4%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | entries with traded volume>0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 981 | 0/981 = 0.00%, UB 0.39% | 42 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,1 | 20 | 981 | 0/981 = 0.00%, UB 0.39% | 42 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 10 | 607 | 0/607 = 0.00%, UB 0.63% | 31 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 20 | 607 | 0/607 = 0.00%, UB 0.63% | 31 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 10 | 1031 | 1/1031 = 0.10%, UB 0.55% | 43 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 20 | 1031 | 1/1031 = 0.10%, UB 0.55% | 43 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 10 | 642 | 1/642 = 0.16%, UB 0.88% | 32 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 20 | 642 | 1/642 = 0.16%, UB 0.88% | 32 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 10 | 1078 | 4/1078 = 0.37%, UB 0.95% | 47 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 20 | 1078 | 4/1078 = 0.37%, UB 0.95% | 47 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 10 | 683 | 4/683 = 0.59%, UB 1.50% | 35 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 20 | 683 | 4/683 = 0.59%, UB 1.50% | 35 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 41, 'no_candles': 1, 'no_candle_after_signal': 1}. State of the first candle at/after signal+10 min: {'yes_bid=0': 41, 'no_candle_at_or_after_signal': 2}.

### SECONDARY (cannot PASS): HIGH markets x 8 CST (UTC-6) stations

Candle coverage: 219/1354 fired tickers (16.2%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | entries with traded volume>0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 1338 | 0/1338 = 0.00%, UB 0.29% | 218 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,1 | 20 | 1338 | 0/1338 = 0.00%, UB 0.29% | 218 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 10 | 889 | 0/889 = 0.00%, UB 0.43% | 140 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 20 | 889 | 0/889 = 0.00%, UB 0.43% | 140 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 10 | 1351 | 0/1351 = 0.00%, UB 0.28% | 219 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 20 | 1351 | 0/1351 = 0.00%, UB 0.28% | 219 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 10 | 896 | 0/896 = 0.00%, UB 0.43% | 140 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 20 | 896 | 0/896 = 0.00%, UB 0.43% | 140 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 10 | 1354 | 0/1354 = 0.00%, UB 0.28% | 219 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 20 | 1354 | 0/1354 = 0.00%, UB 0.28% | 219 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 10 | 898 | 0/898 = 0.00%, UB 0.43% | 140 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 20 | 898 | 0/898 = 0.00%, UB 0.43% | 140 | 0 | 100.0% | 0 / 0 | n/a | n/a | n/a | 0 |

Untradeable breakdown, cell S=5,D=1, L=10: {'no_qualifying_candle': 215, 'no_candles': 4}. State of the first candle at/after signal+10 min: {'yes_bid=0': 215, 'no_candle_at_or_after_signal': 4}.

### SECONDARY (cannot PASS): LOW markets x 8 CST (UTC-6) stations

Candle coverage: 0/945 fired tickers (0.0%), seeded-shuffle prefix.

| S,D | L | fires | false locks (rate, Wilson UB) | fires sampled | priced | untradeable | days / stations | EV vol-wt | EV equal-wt | mean cost | entries with traded volume>0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3,1 | 10 | 930 | 0/930 = 0.00%, UB 0.41% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,1 | 20 | 930 | 0/930 = 0.00%, UB 0.41% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 10 | 597 | 0/597 = 0.00%, UB 0.64% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 3,2 | 20 | 597 | 0/597 = 0.00%, UB 0.64% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 10 | 945 | 0/945 = 0.00%, UB 0.40% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,1 (primary) | 20 | 945 | 0/945 = 0.00%, UB 0.40% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 10 | 609 | 0/609 = 0.00%, UB 0.63% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 5,2 | 20 | 609 | 0/609 = 0.00%, UB 0.63% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 10 | 945 | 0/945 = 0.00%, UB 0.40% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,1 | 20 | 945 | 0/945 = 0.00%, UB 0.40% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 10 | 609 | 0/609 = 0.00%, UB 0.63% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |
| 8,2 | 20 | 609 | 0/609 = 0.00%, UB 0.63% | 0 | 0 | n/a | 0 / 0 | n/a | n/a | n/a | 0 |

Untradeable breakdown, cell S=5,D=1, L=10: {}. State of the first candle at/after signal+10 min: {}.

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
| {'live|None': 238, 'hist|None': 304, 'none|hist:HTTPError:404': 4, 'none|live:HTTPError:404': 7} | candle fetch outcomes by source|error (a 404 on both endpoints = no candles = counted UNTRADEABLE, never dropped) |
| 2567 | PRIMARY_HIGH_nonCST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 10.1%) |
| 1031 | SECONDARY_LOW_nonCST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 4.4%) |
| 1135 | SECONDARY_HIGH_CST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 16.2%) |
| 945 | SECONDARY_LOW_CST: fired tickers outside the completed prefix of the seeded shuffled candle work order (not priced; fraction priced = 0.0%) |
| 0 | days dropped for the value of the official outcome (none were) |

UNTRADEABLE fires are not exclusions: they stay in the denominator of the untradeable fraction (breakdown in section 3). Violating station-days (anchor b) are NOT excluded from fire or EV counts either; they sit in the false-lock numerator whenever they produce a fire on a YES rung.

