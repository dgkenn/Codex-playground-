# Settlement observability -- measurement report

Spec: `SETTLEMENT_OBSERVABILITY_SPEC.md` (frozen 2026-10-27). Code: `venue_expansion/settlement_observability.py`. Per-day records: `out/settlement_observability.json`. No prices, no trading rule, no parameters tuned against the official value.

## 1. VERDICT (spec decision rule, applied verbatim)

# **OBSERVABLE-BUT-NOT-LIVE**

| spec threshold (frozen) | measured |
|---|---|
| (3) or (4) exact-integer >= 99.0%, Wilson lower >= 98.0% | best (3) variant = **f3B**: 99.29% (Wilson lower 99.05%, n=6460); (3C primary) 99.27% (lower 99.04%); (3A) 92.88%; (3B) 99.29%; (4) 99.85% (lower 99.72%, n=6488) |
| and, for (3), reconstruction final >= 30 min before close on >= 80% of days | 3A: 62.6% ; 3B: 0.0% ; 3C: 0.2% |
| (3) best rate in 95.0-99.0% -> APPROACHABLE | not applicable: best (3) = 99.29% is above the band |
| (3) best rate < 95.0% -> RETIRED | not applicable to best (3) = 99.29%; it would apply only to the strict-tiling variant 3A = 92.88% read in isolation, but see below |
| (4) alone passes -> OBSERVABLE-BUT-NOT-LIVE | (4) = 99.85%, Wilson lower 99.72%: passes |

**How the rule was applied.** (i) The registered feed (3) is defined as tile-with-6-hr-groups *and reconcile with the 24-hr group*; that is variant 3C, declared as primary in code before any official value was read. 3C passes the rate gate (>= 99.0%, Wilson lower >= 98.0%) but fails the timing gate (final >= 30 min before close on >= 80% of days) by a wide margin, so it cannot be REVIVED. (ii) The spec has no named branch for 'rate passes, timing fails' on (3); the nearest rule is its (4) clause: a pass that proves observability without a deployable path is OBSERVABLE-BUT-NOT-LIVE. (4) independently passes the rate gate, so the label is the same under either reading. (iii) APPROACHABLE and RETIRED are not triggered: they apply to a best (3) rate below 99%, and the best (3) variant is above it. If someone insisted on reading (3) as 3A alone (92.9%), the RETIRED band would nominally apply, but the spec's explicit rule that a (4) pass must be labelled OBSERVABLE-BUT-NOT-LIVE overrides it. No threshold was moved.

**Blunt reading.** Daily temperature settlement IS observable to ~99% at the 2-F granularity from public data, so the 'permanently retired' conclusion is wrong. But the feed that gets there (the 24-hr METAR group, ~99.3%) appears a median ~7 min (range 4-12) before close, 0% of days >= 30 min, and the only feed that is higher (IEM daily.json, 99.85%) is an after-the-fact value. Nothing registered here is a live signal. Feed (3A), the only variant available early (62.6% of days, entirely non-UTC-6 stations), is 92.9% accurate and 86.5% on LOW markets because it ignores 6 edge hours of the day.


Exploratory (NOT a registered feed, not used in the verdict): 3D = 3A plus hourly METAR spot temperatures in the uncovered edges of the day reaches 96.40% (n=6362).

## 2. Scope, units, conventions

* **Unit of observation**: one (series, LST-day) event with a whole-number official `expiration_value` -- 6488 days (3245 HIGH, 3243 LOW) across **24 stations**, closes 2026-05-23 .. 2026-10-20. Rungs of the same event share one official value (checked: 0 disagreements), so rungs are collapsed to events; T-threshold markets share the event's value and add no information.
* **Reused, not re-derived (anchor a)**: `finality_B.build_universe()` (live `/markets?status=settled` UNION `/historical/markets`), its verified station->standard-offset map, its `close_time == LST midnight` check, its LST day window `[day_start, day_end]`, and its cached IEM 1-minute / routine observations. **Reproduction check**: the incumbent feed exactly as Build B's tz-diagnostic uses it (1-minute else routine fallback) gives 3777/6486 = 58.23% within 0.5 F -- Build B reported 0.5823 on n=6,486. Same window, same data, same number.
* **Coverage**: all 24 stations, 100% of eligible days. Nothing was truncated, so the sampling-order caveat is moot; for the record the METAR / daily.json fetch order was a seeded shuffle (seed 20261027) and was never re-sorted: `SEA, LAX, BOS, MDW, MSP, PHL, DFW, SFO, PHX, LAS, MIA, SAN, OKC, NYC, ATL, HOU, DCA, MSY, SDF, SAT, EWR, TTN, AUS, DEN`.
* **METAR text**: IEM `asos.py?data=metar&report_type=3&report_type=4`, one request per station-month, sequential, 1.2 s spacing, retry/backoff, User-Agent set. 6-hour groups `1STTT`/`2STTT` and the 24-hour group `4SxxxSnnn` are matched as anchored whitespace-delimited tokens after the first `RMK` only. `5xxxx`, `T0289 0194`, `SLP` etc. are never matched. An independent slice-based decoder re-decoded every candidate token: 37545 groups checked, 0 mismatches, 12 negative-temperature groups in the data.
* **Feed (3) variants (declared in code before any official value was read)**: **3A** = max/min over the 6-hr groups whose 6-hour window `[nominal-6h, nominal]` lies wholly inside the LST day (a day with any needed group missing is excluded from 3A); **3B** = the 24-hr group in the report that closes the LST day (report within 75 min of LST midnight; observed ~7 min before); **3C** = reconcile: the 24-hr group where present, else 3A (this is the registered feed (3): tile with 6-hr groups, reconcile with the 24-hr group). Contradiction = for tiling-aligned stations, 3A != 24-hr value; for non-aligned stations, 3A beyond the 24-hr value in the extreme direction (impossible if both were right). **3D** is exploratory only and not used in the verdict.
* **Rounding**: C -> F as `c*9/5+32` in exact rational arithmetic (tenths of C integers), then **round half-up** (`floor(x+1/2)`). Banker's rounding was computed in parallel for every feed (section 3b).
* **Exact** = rounded feed value == official. **Within 0.5 F** = |raw feed value - official| <= 0.5 on the unrounded value. Because the official value is a whole number, within-0.5 is mathematically identical to exact except at exact .5 ties, so the two columns are nearly always equal; this is a property of the metric, not a bug.
* **Feed availability** (exclusions are per feed, so n differs): (1) needs >=1000 one-minute obs and >=65 in the final 130 min (Build B's rule), (2) needs >=6 routine obs and >=2 in the final 130 min, (3A) needs every inside-window 6-hr group, (3B) needs the 24-hr group, (4) needs a daily.json row with `tmpf_est=false`.

## 3. Headline: exact-integer and within-0.5 F match rate (Wilson 95%), pooled over all stations

| feed | stratum | n | exact-integer [Wilson 95%] | within 0.5 F [Wilson 95%] |
|---|---|---|---|---|
| (1) IEM 1-minute extreme | ALL | 4028 | 64.4% [63.0, 65.9] (n=4028) | 64.4% [63.0, 65.9] (n=4028) |
| (1) IEM 1-minute extreme | HIGH | 2015 | 46.4% [44.2, 48.6] (n=2015) | 46.4% [44.2, 48.6] (n=2015) |
| (1) IEM 1-minute extreme | LOW | 2013 | 82.5% [80.8, 84.1] (n=2013) | 82.5% [80.8, 84.1] (n=2013) |
| (2) routine hourly METAR spot extreme | ALL | 6484 | 48.1% [46.9, 49.3] (n=6484) | 48.1% [46.9, 49.3] (n=6484) |
| (2) routine hourly METAR spot extreme | HIGH | 3243 | 33.8% [32.2, 35.4] (n=3243) | 33.8% [32.2, 35.4] (n=3243) |
| (2) routine hourly METAR spot extreme | LOW | 3241 | 62.4% [60.8, 64.1] (n=3241) | 62.4% [60.8, 64.1] (n=3241) |
| (3A) 6-hr groups, strict tiling of the LST day | ALL | 6362 | 92.9% [92.2, 93.5] (n=6362) | 92.9% [92.2, 93.5] (n=6362) |
| (3A) 6-hr groups, strict tiling of the LST day | HIGH | 3183 | 99.3% [98.9, 99.5] (n=3183) | 99.3% [98.9, 99.5] (n=3183) |
| (3A) 6-hr groups, strict tiling of the LST day | LOW | 3179 | 86.5% [85.2, 87.6] (n=3179) | 86.5% [85.2, 87.6] (n=3179) |
| (3B) 24-hr group at LST midnight | ALL | 6460 | 99.3% [99.1, 99.5] (n=6460) | 99.3% [99.1, 99.5] (n=6460) |
| (3B) 24-hr group at LST midnight | HIGH | 3231 | 99.9% [99.7, 100.0] (n=3231) | 99.9% [99.7, 100.0] (n=3231) |
| (3B) 24-hr group at LST midnight | LOW | 3229 | 98.7% [98.2, 99.0] (n=3229) | 98.7% [98.2, 99.0] (n=3229) |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | ALL | 6474 | 99.3% [99.0, 99.5] (n=6474) | 99.3% [99.0, 99.5] (n=6474) |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | HIGH | 3238 | 99.9% [99.7, 100.0] (n=3238) | 99.9% [99.7, 100.0] (n=3238) |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | LOW | 3236 | 98.6% [98.2, 99.0] (n=3236) | 98.6% [98.2, 99.0] (n=3236) |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | ALL | 6362 | 96.4% [95.9, 96.8] (n=6362) | 96.4% [95.9, 96.8] (n=6362) |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | HIGH | 3183 | 99.3% [99.0, 99.6] (n=3183) | 99.3% [99.0, 99.6] (n=3183) |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | LOW | 3179 | 93.5% [92.5, 94.3] (n=3179) | 93.5% [92.5, 94.3] (n=3179) |
| (4) IEM daily.json (tmpf_est=false only) | ALL | 6488 | 99.8% [99.7, 99.9] (n=6488) | 99.8% [99.7, 99.9] (n=6488) |
| (4) IEM daily.json (tmpf_est=false only) | HIGH | 3245 | 99.8% [99.6, 99.9] (n=3245) | 99.8% [99.6, 99.9] (n=3245) |
| (4) IEM daily.json (tmpf_est=false only) | LOW | 3243 | 99.9% [99.7, 100.0] (n=3243) | 99.9% [99.7, 100.0] (n=3243) |

**3b. Rounding sensitivity (exact-integer count, half-up vs banker's):**

| feed | half-up | banker's | difference (pp) |
|---|---|---|---|
| (1) IEM 1-minute extreme | 2596/4028 = 64.45% | 2596/4028 = 64.45% | +0.000 |
| (2) routine hourly METAR spot extreme | 3119/6484 = 48.10% | 3119/6484 = 48.10% | +0.000 |
| (3A) 6-hr groups, strict tiling of the LST day | 5909/6362 = 92.88% | 5909/6362 = 92.88% | +0.000 |
| (3B) 24-hr group at LST midnight | 6414/6460 = 99.29% | 6414/6460 = 99.29% | +0.000 |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | 6427/6474 = 99.27% | 6427/6474 = 99.27% | +0.000 |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | 6133/6362 = 96.40% | 6133/6362 = 96.40% | +0.000 |
| (4) IEM daily.json (tmpf_est=false only) | 6478/6488 = 99.85% | 6478/6488 = 99.85% | +0.000 |

The convention does not move any headline (bound: 0.5 pp).

**3c. Common support** (days where feeds 1, 2, 3A, 3B and 4 are all available, n=3948) -- apples-to-apples denominators:

| feed | ALL | HIGH | LOW |
|---|---|---|---|
| (1) IEM 1-minute extreme | 64.6% (n=3948) | 46.6% (n=1976) | 82.6% (n=1972) |
| (2) routine hourly METAR spot extreme | 48.1% (n=3948) | 33.8% (n=1976) | 62.4% (n=1972) |
| (3A) 6-hr groups, strict tiling of the LST day | 93.2% (n=3948) | 99.1% (n=1976) | 87.3% (n=1972) |
| (3B) 24-hr group at LST midnight | 99.3% (n=3948) | 99.9% (n=1976) | 98.6% (n=1972) |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | 99.3% (n=3948) | 99.9% (n=1976) | 98.6% (n=1972) |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | 96.3% (n=3948) | 99.1% (n=1976) | 93.5% (n=1972) |
| (4) IEM daily.json (tmpf_est=false only) | 99.8% (n=3948) | 99.7% (n=1976) | 99.8% (n=1972) |

Feed (4) `tmpf_est=true` rows: 0 (none occurred, so nothing needed to be reported separately).

**3d. Why 3A is weak: the 6-hr windows tile the LST day only for UTC-6 stations.** Synoptic windows are 00/06/12/18Z; the LST day starts at 06Z (CST), 05Z (EST), 07Z (MST), 08Z (PST). Strictly-inside windows cover 24 h for CST but only 18 h otherwise (the other 6 h are edge hours no group covers).

| UTC offset | stations | 3A HIGH | 3A LOW | 3B HIGH | 3B LOW | 3C ALL | (4) ALL |
|---|---|---|---|---|---|---|---|
| -5 | 9 | 98.5% (n=1045) | 82.1% (n=1043) | 99.8% (n=1064) | 98.0% (n=1063) | 98.9% (n=2135) | 99.9% (n=2137) |
| -6 | 8 | 99.8% (n=1191) | 98.9% (n=1190) | 100.0% (n=1204) | 99.1% (n=1204) | 99.5% (n=2410) | 99.8% (n=2416) |
| -7 | 2 | 98.9% (n=285) | 67.7% (n=285) | 99.7% (n=299) | 99.0% (n=299) | 99.3% (n=598) | 100.0% (n=604) |
| -8 | 5 | 99.7% (n=662) | 79.1% (n=661) | 100.0% (n=664) | 98.8% (n=663) | 99.4% (n=1331) | 99.8% (n=1331) |

## 4. Signed error histograms (official minus feed, whole F; negative = feed ABOVE official)

| feed | kind | <-4 | -4 | -3 | -2 | -1 | 0 | +1 | +2 | +3 | +4 | >+4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (1) IEM 1-minute extreme | HIGH | 3 | 0 | 0 | 26 | 1003 | 935 | 34 | 11 | 2 | 0 | 1 |
| (1) IEM 1-minute extreme | LOW | 0 | 2 | 5 | 16 | 47 | 1661 | 265 | 1 | 3 | 2 | 11 |
| (2) routine hourly METAR spot extreme | HIGH | 0 | 0 | 1 | 0 | 5 | 1095 | 1772 | 326 | 39 | 3 | 2 |
| (2) routine hourly METAR spot extreme | LOW | 1 | 5 | 23 | 108 | 1058 | 2024 | 21 | 0 | 0 | 1 | 0 |
| (3A) 6-hr groups, strict tiling of the LST day | HIGH | 0 | 1 | 1 | 0 | 0 | 3160 | 12 | 2 | 4 | 2 | 1 |
| (3A) 6-hr groups, strict tiling of the LST day | LOW | 32 | 30 | 47 | 82 | 231 | 2749 | 2 | 1 | 1 | 1 | 3 |
| (3B) 24-hr group at LST midnight | HIGH | 0 | 1 | 0 | 2 | 0 | 3228 | 0 | 0 | 0 | 0 | 0 |
| (3B) 24-hr group at LST midnight | LOW | 0 | 0 | 1 | 0 | 34 | 3186 | 0 | 1 | 0 | 1 | 6 |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | HIGH | 0 | 1 | 0 | 2 | 0 | 3235 | 0 | 0 | 0 | 0 | 0 |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | LOW | 0 | 0 | 1 | 1 | 34 | 3192 | 0 | 1 | 0 | 1 | 6 |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | HIGH | 0 | 1 | 1 | 0 | 0 | 3162 | 13 | 1 | 3 | 1 | 1 |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | LOW | 1 | 0 | 9 | 14 | 170 | 2971 | 8 | 1 | 1 | 1 | 3 |
| (4) IEM daily.json (tmpf_est=false only) | HIGH | 0 | 0 | 0 | 0 | 0 | 3239 | 0 | 2 | 1 | 2 | 1 |
| (4) IEM daily.json (tmpf_est=false only) | LOW | 0 | 0 | 1 | 0 | 1 | 3239 | 1 | 1 | 0 | 0 | 0 |

The incumbent's one-sidedness is confirmed: the 1-minute HIGH extreme sits above official (mass at -1), the routine-hourly HIGH extreme below (mass at +1). Feeds (3B)/(3C)/(4) are centred on 0 with only isolated gross outliers (section 8).

## 5. Feed (3) timing: `close_time - timestamp of the last group needed` (minutes)

The timestamp is the METAR report time carrying the last required group. 3A: last inside 6-hr window's group. 3B/3C: the report carrying the 24-hr group.

| variant | n | min | p10 | median | p90 | max | **final >= 30 min before close** |
|---|---|---|---|---|---|---|---|
| (3A) 6-hr groups, strict tiling of the LST day | 6362 | 6 | 7 | 124 | 308 | 309 | 62.6% [61.4, 63.8] (n=6362) |
| (3B) 24-hr group at LST midnight | 6460 | 4 | 4 | 7 | 9 | 12 | 0.0% [0.0, 0.1] (n=6460) |
| (3C) reconciled: 24-hr group if present else 3A  [registered (3) primary] | 6474 | 4 | 4 | 7 | 9 | 307 | 0.2% [0.1, 0.3] (n=6474) |
| (3D) EXPLORATORY: 3A + hourly spot temps in the uncovered edges | 6362 | 0 | 4 | 7 | 9 | 127 | 0.1% [0.0, 0.2] (n=6362) |

Buckets (minutes before close):

| variant | <0 | 0-15 | 15-30 | 30-60 | 60-120 | 120-240 | >=240 |
|---|---|---|---|---|---|---|---|
| f3A | 0 | 2381 | 0 | 0 | 570 | 1323 | 2088 |
| f3B | 0 | 6460 | 0 | 0 | 0 | 0 | 0 |
| f3C | 0 | 6462 | 0 | 0 | 0 | 4 | 8 |
| f3D | 0 | 6356 | 0 | 0 | 4 | 2 | 0 |

By station UTC offset (fraction of days final >= 30 min before close; median minutes):

| offset | 3A n | 3A frac>=30 | 3A median | 3B/3C frac>=30 | 3B median |
|---|---|---|---|---|---|
| -5 | 2088 | 100% | 307 | 0% | 7 |
| -6 | 2381 | 0% | 7 | 0% | 7 |
| -7 | 570 | 100% | 69 | 0% | 9 |
| -8 | 1323 | 100% | 126 | 0% | 6 |

Informational: using only the 6-hr group that contains the extreme (not all needed groups), 3A final >= 30 min before close on 98.3% of days -- but that is not what the spec defines and the extreme is unknowable in advance.

**Reading**: the 24-hour group (which is what gives ~99%) is transmitted in the `H:53` METAR immediately preceding LST midnight, i.e. a median ~7 min before the market's close. The strictly-inside 6-hr tiling is available earlier for non-CST stations only because those stations' tilings simply stop 1-5 h before midnight and ignore the edge of the day -- that is exactly why 3A is only ~93% accurate. No variant is both accurate and early.

## 6. Per-station table (anchor d: every station, no selection) -- exact-integer match, k/n

| station | UTC off | kind | days | (1) 1-min | (2) hourly | (3A) tiling | (3B) 24-h grp | (3C) reconciled | (4) daily.json |
|---|---|---|---|---|---|---|---|---|---|
| ATL | -5 | HIGH | 151 | 50.0% (54/108) | 32.5% (49/151) | 99.3% (150/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| ATL | -5 | LOW | 151 | 85.2% (92/108) | 72.8% (110/151) | 86.8% (131/151) | 99.3% (150/151) | 99.3% (150/151) | 100.0% (151/151) |
| AUS | -6 | HIGH | 151 | 52.4% (33/63) | 32.7% (49/150) | 100.0% (146/146) | 100.0% (150/150) | 100.0% (150/150) | 100.0% (151/151) |
| AUS | -6 | LOW | 151 | 71.4% (45/63) | 52.0% (78/150) | 99.3% (145/146) | 99.3% (149/150) | 99.3% (149/150) | 100.0% (151/151) |
| BOS | -5 | HIGH | 151 | 46.3% (44/95) | 34.4% (52/151) | 97.1% (133/137) | 99.3% (148/149) | 99.3% (150/151) | 100.0% (151/151) |
| BOS | -5 | LOW | 151 | 75.8% (72/95) | 62.3% (94/151) | 81.8% (112/137) | 96.0% (143/149) | 95.4% (144/151) | 99.3% (150/151) |
| DCA | -5 | HIGH | 151 | 62.3% (48/77) | 39.1% (59/151) | 98.7% (148/150) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| DCA | -5 | LOW | 151 | 85.7% (66/77) | 66.2% (100/151) | 82.0% (123/150) | 98.7% (149/151) | 98.7% (149/151) | 100.0% (151/151) |
| DEN | -7 | HIGH | 151 | 34.2% (39/114) | 27.2% (41/151) | 99.3% (136/137) | 100.0% (148/148) | 100.0% (148/148) | 100.0% (151/151) |
| DEN | -7 | LOW | 151 | 77.2% (88/114) | 42.4% (64/151) | 48.9% (68/139) | 98.6% (146/148) | 98.6% (146/148) | 100.0% (151/151) |
| DFW | -6 | HIGH | 151 | 35.9% (37/103) | 33.8% (51/151) | 100.0% (145/145) | 100.0% (150/150) | 100.0% (150/150) | 100.0% (151/151) |
| DFW | -6 | LOW | 151 | 87.4% (90/103) | 68.2% (103/151) | 99.3% (144/145) | 99.3% (149/150) | 99.3% (149/150) | 100.0% (151/151) |
| EWR | -5 | HIGH | 55 | 56.5% (13/23) | 47.3% (26/55) | 96.4% (53/55) | 100.0% (55/55) | 100.0% (55/55) | 100.0% (55/55) |
| EWR | -5 | LOW | 55 | 78.3% (18/23) | 65.5% (36/55) | 81.8% (45/55) | 98.2% (54/55) | 98.2% (54/55) | 100.0% (55/55) |
| HOU | -6 | HIGH | 151 | 53.1% (69/130) | 35.8% (54/151) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) | 96.7% (146/151) |
| HOU | -6 | LOW | 151 | 88.5% (115/130) | 65.6% (99/151) | 98.0% (147/150) | 98.7% (149/151) | 98.7% (149/151) | 100.0% (151/151) |
| LAS | -8 | HIGH | 151 | 33.7% (32/95) | 32.5% (49/151) | 100.0% (149/149) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) |
| LAS | -8 | LOW | 151 | 88.4% (84/95) | 52.3% (79/151) | 94.0% (140/149) | 98.7% (148/150) | 98.7% (149/151) | 99.3% (150/151) |
| LAX | -8 | HIGH | 151 | 17.7% (11/62) | 34.4% (52/151) | 99.3% (150/151) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) |
| LAX | -8 | LOW | 151 | 69.4% (43/62) | 73.5% (111/151) | 76.8% (116/151) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) |
| MDW | -6 | HIGH | 151 | 65.4% (87/133) | 40.4% (61/151) | 99.3% (149/150) | 100.0% (150/150) | 100.0% (150/150) | 100.0% (151/151) |
| MDW | -6 | LOW | 151 | 82.0% (109/133) | 60.9% (92/151) | 98.7% (148/150) | 98.7% (148/150) | 98.7% (148/150) | 100.0% (151/151) |
| MIA | -5 | HIGH | 151 | 40.3% (29/72) | 35.1% (53/151) | 99.3% (142/143) | 100.0% (150/150) | 100.0% (150/150) | 99.3% (150/151) |
| MIA | -5 | LOW | 150 | 80.3% (57/71) | 48.7% (73/150) | 81.6% (115/141) | 98.7% (147/149) | 98.7% (147/149) | 100.0% (150/150) |
| MSP | -6 | HIGH | 151 | 46.8% (37/79) | 37.7% (57/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| MSP | -6 | LOW | 151 | 81.0% (64/79) | 64.2% (97/151) | 96.7% (146/151) | 96.7% (146/151) | 96.7% (146/151) | 100.0% (151/151) |
| MSY | -6 | HIGH | 151 | 48.5% (48/99) | 34.4% (52/151) | 100.0% (148/148) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| MSY | -6 | LOW | 151 | 78.8% (78/99) | 62.9% (95/151) | 99.3% (147/148) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| NYC | -5 | HIGH | 151 | 51.9% (56/108) | 36.4% (55/151) | 97.3% (146/150) | 99.3% (150/151) | 99.3% (150/151) | 100.0% (151/151) |
| NYC | -5 | LOW | 151 | 82.4% (89/108) | 64.2% (97/151) | 78.0% (117/150) | 98.0% (148/151) | 98.0% (148/151) | 100.0% (151/151) |
| OKC | -6 | HIGH | 151 | 44.9% (48/107) | 35.1% (53/151) | 99.3% (150/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| OKC | -6 | LOW | 151 | 85.0% (91/107) | 53.0% (80/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| PHL | -5 | HIGH | 151 | 49.3% (35/71) | 34.4% (52/151) | 99.3% (150/151) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) |
| PHL | -5 | LOW | 151 | 78.9% (56/71) | 70.2% (106/151) | 80.8% (122/151) | 98.0% (147/150) | 98.0% (148/151) | 100.0% (151/151) |
| PHX | -7 | HIGH | 151 | 37.0% (27/73) | 19.9% (30/151) | 98.6% (146/148) | 99.3% (150/151) | 99.3% (150/151) | 100.0% (151/151) |
| PHX | -7 | LOW | 151 | 93.2% (68/73) | 58.3% (88/151) | 85.6% (125/146) | 99.3% (150/151) | 99.3% (150/151) | 100.0% (151/151) |
| SAN | -8 | HIGH | 62 | 25.0% (8/32) | 48.4% (30/62) | 100.0% (62/62) | 100.0% (62/62) | 100.0% (62/62) | 100.0% (62/62) |
| SAN | -8 | LOW | 62 | 81.2% (26/32) | 69.4% (43/62) | 77.4% (48/62) | 100.0% (62/62) | 100.0% (62/62) | 100.0% (62/62) |
| SAT | -6 | HIGH | 151 | 62.0% (62/100) | 33.8% (51/151) | 100.0% (150/150) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) |
| SAT | -6 | LOW | 151 | 85.0% (85/100) | 69.5% (105/151) | 100.0% (149/149) | 100.0% (150/150) | 100.0% (151/151) | 100.0% (151/151) |
| SDF | -5 | HIGH | 53 | 42.1% (8/19) | 30.2% (16/53) | 100.0% (53/53) | 100.0% (53/53) | 100.0% (53/53) | 100.0% (53/53) |
| SDF | -5 | LOW | 53 | 68.4% (13/19) | 66.0% (35/53) | 86.8% (46/53) | 100.0% (53/53) | 100.0% (53/53) | 100.0% (53/53) |
| SEA | -8 | HIGH | 151 | 34.9% (37/106) | 33.1% (50/151) | 99.3% (148/149) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| SEA | -8 | LOW | 151 | 80.2% (85/106) | 60.3% (91/151) | 69.8% (104/149) | 96.7% (146/151) | 96.7% (146/151) | 98.7% (149/151) |
| SFO | -8 | HIGH | 151 | 40.8% (40/98) | 21.2% (32/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) | 100.0% (151/151) |
| SFO | -8 | LOW | 150 | 88.7% (86/97) | 80.0% (120/150) | 76.7% (115/150) | 99.3% (149/150) | 99.3% (149/150) | 100.0% (150/150) |
| TTN | -5 | HIGH | 55 | 68.8% (33/48) | 38.9% (21/54) | 98.2% (54/55) | 100.0% (54/54) | 100.0% (55/55) | 100.0% (55/55) |
| TTN | -5 | LOW | 55 | 85.4% (41/48) | 51.9% (28/54) | 81.8% (45/55) | 94.4% (51/54) | 94.5% (52/55) | 100.0% (55/55) |

Lowest stations pooled HIGH+LOW: 3C TTN 97.3%, BOS 97.4%, MSP 98.3%; (4) HOU 98.3%, SEA 99.3%, MIA 99.7%. Minimum single-station-kind rate: 3C 94.5% (TTN|LOW), (4) 96.7% (HOU|HIGH); no station-kind is at 0%, and the pooled result is not carried by a few stations.

## 7. Anchor (c): ten worked decodes

Selection never looks at official values or at match/mismatch: the first and the last negative-temperature groups used in a tiling (chronological), a seeded-random contradiction day, then seeded-random aligned / non-aligned days. (Decode 1 is a June sensor-fault group at DEN, i.e. a negative group in summer; the genuine cold-weather negative group is the later DEN October one. The decoder also asserts `21017` -> -1.7 C.) Arithmetic: `TTT tenths C (sign digit 0:+, 1:-)` -> C -> `C*9/5+32` -> round half-up.

**Decode 1 -- FIRST negative-temperature 6-hr group used in a tiling (chronological).** DEN MIN 2026-06-26 (LST day 06-26 07:00Z..06-27 07:00Z, NON-aligned: edge hours uncovered)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 06-26 12:00Z..06-26 18:00Z | 06-26 17:53Z | `21044` | -4.4 C -> -4.4*9/5+32 = 24.08 F | 24.08 |
| 06-26 18:00Z..06-27 00:00Z | 06-26 23:53Z | `20283` | +28.3 C -> +28.3*9/5+32 = 82.94 F | 82.94 |
| 06-27 00:00Z..06-27 06:00Z | 06-27 05:53Z | `20189` | +18.9 C -> +18.9*9/5+32 = 66.02 F | 66.02 |

-> min over groups = -4.4 C = 24.08 F -> **24 F** (3A).
 24-hr group `403171044` (report 06-27 06:53Z): max +31.7 C / min -4.4 C -> using the min -4.4 C = 24.08 F -> **24 F** (3B).
 Official `expiration_value` = **56**; IEM 1-minute extreme = 56.

**Decode 2 -- LAST negative-temperature 6-hr group used in a tiling (chronological).** DEN MIN 2026-10-16 (LST day 10-16 07:00Z..10-17 07:00Z, NON-aligned: edge hours uncovered)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 10-16 12:00Z..10-16 18:00Z | 10-16 17:53Z | `21022` | -2.2 C -> -2.2*9/5+32 = 28.04 F | 28.04 |
| 10-16 18:00Z..10-17 00:00Z | 10-16 23:53Z | `20083` | +8.3 C -> +8.3*9/5+32 = 46.94 F | 46.94 |
| 10-17 00:00Z..10-17 06:00Z | 10-17 05:53Z | `20022` | +2.2 C -> +2.2*9/5+32 = 35.96 F | 35.96 |

-> min over groups = -2.2 C = 28.04 F -> **28 F** (3A).
 24-hr group `401391022` (report 10-17 06:53Z): max +13.9 C / min -2.2 C -> using the min -2.2 C = 28.04 F -> **28 F** (3B).
 Official `expiration_value` = **28**; IEM 1-minute extreme = 28.

**Decode 3 -- 24-hr group contradicts the 6-hr groups.** MDW MAX 2026-07-03 (LST day 07-03 06:00Z..07-04 06:00Z, tiling-aligned)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 07-03 06:00Z..07-03 12:00Z | 07-03 11:53Z | `10233` | +23.3 C -> +23.3*9/5+32 = 73.94 F | 73.94 |
| 07-03 12:00Z..07-03 18:00Z | 07-03 17:53Z | `10322` | +32.2 C -> +32.2*9/5+32 = 89.96 F | 89.96 |
| 07-03 18:00Z..07-04 00:00Z | 07-03 23:53Z | `10289` | +28.9 C -> +28.9*9/5+32 = 84.02 F | 84.02 |
| 07-04 00:00Z..07-04 06:00Z | 07-04 05:53Z | `10289` | +28.9 C -> +28.9*9/5+32 = 84.02 F | 84.02 |

-> max over groups = +32.2 C = 89.96 F -> **90 F** (3A).
 24-hr group `403280211` (report 07-04 05:53Z): max +32.8 C / min +21.1 C -> using the max +32.8 C = 91.04 F -> **91 F** (3B).
 Official `expiration_value` = **91**; IEM 1-minute extreme = 92.

**Decode 4 -- random aligned (UTC-6) station.** HOU MAX 2026-06-04 (LST day 06-04 06:00Z..06-05 06:00Z, tiling-aligned)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 06-04 06:00Z..06-04 12:00Z | 06-04 11:53Z | `10239` | +23.9 C -> +23.9*9/5+32 = 75.02 F | 75.02 |
| 06-04 12:00Z..06-04 18:00Z | 06-04 17:53Z | `10278` | +27.8 C -> +27.8*9/5+32 = 82.04 F | 82.04 |
| 06-04 18:00Z..06-05 00:00Z | 06-04 23:53Z | `10300` | +30.0 C -> +30.0*9/5+32 = 86.00 F | 86.00 |
| 06-05 00:00Z..06-05 06:00Z | 06-05 05:53Z | `10278` | +27.8 C -> +27.8*9/5+32 = 82.04 F | 82.04 |

-> max over groups = +30.0 C = 86.00 F -> **86 F** (3A).
 24-hr group `403000233` (report 06-05 05:53Z): max +30.0 C / min +23.3 C -> using the max +30.0 C = 86.00 F -> **86 F** (3B).
 Official `expiration_value` = **86**; IEM 1-minute extreme = 86.

**Decode 5 -- random aligned (UTC-6) station.** AUS MAX 2026-06-25 (LST day 06-25 06:00Z..06-26 06:00Z, tiling-aligned)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 06-25 06:00Z..06-25 12:00Z | 06-25 11:53Z | `10244` | +24.4 C -> +24.4*9/5+32 = 75.92 F | 75.92 |
| 06-25 12:00Z..06-25 18:00Z | 06-25 17:53Z | `10317` | +31.7 C -> +31.7*9/5+32 = 89.06 F | 89.06 |
| 06-25 18:00Z..06-26 00:00Z | 06-25 23:53Z | `10339` | +33.9 C -> +33.9*9/5+32 = 93.02 F | 93.02 |
| 06-26 00:00Z..06-26 06:00Z | 06-26 05:53Z | `10328` | +32.8 C -> +32.8*9/5+32 = 91.04 F | 91.04 |

-> max over groups = +33.9 C = 93.02 F -> **93 F** (3A).
 24-hr group `403390211` (report 06-26 05:53Z): max +33.9 C / min +21.1 C -> using the max +33.9 C = 93.02 F -> **93 F** (3B).
 Official `expiration_value` = **93**; (1-minute coverage insufficient).

**Decode 6 -- random aligned (UTC-6) station.** MSY MIN 2026-07-10 (LST day 07-10 06:00Z..07-11 06:00Z, tiling-aligned)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 07-10 06:00Z..07-10 12:00Z | 07-10 11:53Z | `20261` | +26.1 C -> +26.1*9/5+32 = 78.98 F | 78.98 |
| 07-10 12:00Z..07-10 18:00Z | 07-10 17:53Z | `20272` | +27.2 C -> +27.2*9/5+32 = 80.96 F | 80.96 |
| 07-10 18:00Z..07-11 00:00Z | 07-10 23:53Z | `20267` | +26.7 C -> +26.7*9/5+32 = 80.06 F | 80.06 |
| 07-11 00:00Z..07-11 06:00Z | 07-11 05:53Z | `20267` | +26.7 C -> +26.7*9/5+32 = 80.06 F | 80.06 |

-> min over groups = +26.1 C = 78.98 F -> **79 F** (3A).
 24-hr group `403220261` (report 07-11 05:53Z): max +32.2 C / min +26.1 C -> using the min +26.1 C = 78.98 F -> **79 F** (3B).
 Official `expiration_value` = **79**; IEM 1-minute extreme = 78.

**Decode 7 -- random non-aligned station.** EWR MIN 2026-09-01 (LST day 09-01 05:00Z..09-02 05:00Z, NON-aligned: edge hours uncovered)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 09-01 06:00Z..09-01 12:00Z | 09-01 11:51Z | `20222` | +22.2 C -> +22.2*9/5+32 = 71.96 F | 71.96 |
| 09-01 12:00Z..09-01 18:00Z | 09-01 17:51Z | `20228` | +22.8 C -> +22.8*9/5+32 = 73.04 F | 73.04 |
| 09-01 18:00Z..09-02 00:00Z | 09-01 23:51Z | `20233` | +23.3 C -> +23.3*9/5+32 = 73.94 F | 73.94 |

-> min over groups = +22.2 C = 71.96 F -> **72 F** (3A).
 24-hr group `403060206` (report 09-02 04:51Z): max +30.6 C / min +20.6 C -> using the min +20.6 C = 69.08 F -> **69 F** (3B).
 Official `expiration_value` = **69**; (1-minute coverage insufficient).

**Decode 8 -- random non-aligned station.** LAX MAX 2026-06-23 (LST day 06-23 08:00Z..06-24 08:00Z, NON-aligned: edge hours uncovered)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 06-23 12:00Z..06-23 18:00Z | 06-23 17:53Z | `10194` | +19.4 C -> +19.4*9/5+32 = 66.92 F | 66.92 |
| 06-23 18:00Z..06-24 00:00Z | 06-23 23:53Z | `10222` | +22.2 C -> +22.2*9/5+32 = 71.96 F | 71.96 |
| 06-24 00:00Z..06-24 06:00Z | 06-24 05:53Z | `10211` | +21.1 C -> +21.1*9/5+32 = 69.98 F | 69.98 |

-> max over groups = +22.2 C = 71.96 F -> **72 F** (3A).
 24-hr group `402220172` (report 06-24 07:53Z): max +22.2 C / min +17.2 C -> using the max +22.2 C = 71.96 F -> **72 F** (3B).
 Official `expiration_value` = **72**; (1-minute coverage insufficient).

**Decode 9 -- random non-aligned station.** BOS MAX 2026-08-01 (LST day 08-01 05:00Z..08-02 05:00Z, NON-aligned: edge hours uncovered)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 08-01 06:00Z..08-01 12:00Z | 08-01 11:54Z | `10239` | +23.9 C -> +23.9*9/5+32 = 75.02 F | 75.02 |
| 08-01 12:00Z..08-01 18:00Z | 08-01 17:54Z | `10278` | +27.8 C -> +27.8*9/5+32 = 82.04 F | 82.04 |
| 08-01 18:00Z..08-02 00:00Z | 08-01 23:54Z | `10294` | +29.4 C -> +29.4*9/5+32 = 84.92 F | 84.92 |

-> max over groups = +29.4 C = 84.92 F -> **85 F** (3A).
 24-hr group `402940206` (report 08-02 04:54Z): max +29.4 C / min +20.6 C -> using the max +29.4 C = 84.92 F -> **85 F** (3B).
 Official `expiration_value` = **85**; IEM 1-minute extreme = 86.

**Decode 10 -- random non-aligned station.** LAX MAX 2026-06-08 (LST day 06-08 08:00Z..06-09 08:00Z, NON-aligned: edge hours uncovered)

| 6-hr window (UTC) | report | raw group | decode | F |
|---|---|---|---|---|
| 06-08 12:00Z..06-08 18:00Z | 06-08 17:53Z | `10211` | +21.1 C -> +21.1*9/5+32 = 69.98 F | 69.98 |
| 06-08 18:00Z..06-09 00:00Z | 06-08 23:53Z | `10222` | +22.2 C -> +22.2*9/5+32 = 71.96 F | 71.96 |
| 06-09 00:00Z..06-09 06:00Z | 06-09 05:53Z | `10200` | +20.0 C -> +20.0*9/5+32 = 68.00 F | 68.00 |

-> max over groups = +22.2 C = 71.96 F -> **72 F** (3A).
 24-hr group `402220167` (report 06-09 07:53Z): max +22.2 C / min +16.7 C -> using the max +22.2 C = 71.96 F -> **72 F** (3B).
 Official `expiration_value` = **72**; IEM 1-minute extreme = 73.

Decoder self-tests (asserted at run time): `10306` -> +30.6 C -> 87.08 F; `21017` -> -1.7 C -> 28.94 F; `402780206` -> max +27.8 / min +20.6 C; `55003`, `58004`, `T02890194` are NOT decoded as extreme groups.

## 8. 24-hour vs 6-hour contradictions, and the residual misses of (3B)/(4)

* Days with both a complete 3A tiling and a 24-hr group: 6348. Contradictions: 7 (of which 4 on tiling-aligned stations, where the two must be identical if both are right; aligned days compared: 2379). So the 6-hr and 24-hr groups almost never disagree with each other -- on UTC-6 stations 3A and 3B are the same number.
* The residual misses of 3B/3C are not decoding errors (the independent decoder agrees on every group). They are days where the *station's own recorded extreme* differs from the NWS-published CLI value by a large amount, e.g. a 24-hr min of 24 F on a June day in Denver (official 56) that appears in both the 24-hr and the 6-hr group. This is consistent with NWS quality-controlling sensor faults out of the CLI while the METAR groups carry the raw sensor value (not verified). A screen against hourly temperatures would likely recover most of these, but that screen was not registered and is **not** applied or counted here.
* Small residual of LOW days where official minus 24-hr-group = -1 F (34 days): the station-recorded min is 1 F *above* what NWS published. Cause not investigated.

## 9. Every exclusion (count, reason)

| count | reason |
|---|---|
| 35582 | universe (rung level, inherited from finality_B.build_universe): not_bracket_rung(T_threshold) |
| 39259 | universe (rung level, inherited from finality_B.build_universe): close_outside_2026-05-23..2026-10-20 |
| 420 | universe (rung level, inherited from finality_B.build_universe): series_not_in_verified_US_station_map |
| 27 | universe (rung level, inherited from finality_B.build_universe): no_official_yes_no_result |
| 25956 | universe_rungs_in_scope(bracket rungs, closes 2026-05-23..2026-10-20) |
| 6489 | events_(series,LST-day) after dedupe of rungs |
| 0 | rungs_of_an_event_disagreeing_on_expiration_value |
| 1 | EXCLUDED day: expiration_value not a whole number (e.g. text range '58° to 59°') |
| 2460 | f1 EXCLUDED: 1-minute coverage insufficient (<1000 obs or <65 in final 130 min) |
| 4 | f2 EXCLUDED: routine coverage insufficient (<6 obs or <2 in final 130 min) |
| 126 | f3A EXCLUDED: >=1 needed 6-hr group missing from METAR feed |
| 28 | f3B EXCLUDED: no 24-hr group at the LST-midnight report |
| 14 | f3C EXCLUDED: neither 24-hr group nor complete 6-hr tiling |
| 1 | METAR decode: 6h_group_duplicate_conflict(latest_kept) |

METAR reports parsed: 116076. Expiration value is the measurement target only; no day was excluded on its value (anchor b). The 1-minute feed's 2460 exclusions are the days the IEM 1-minute archive lacks coverage -- that is the known reason Build B fell back to routine obs for ~38% of rungs.

## 10. Findings that contradict or qualify the spec's premises

1. **"Published hours before a daily market closes" is false for the number that works.** The 24-hr group that reproduces the official value is in the last METAR before LST midnight (median ~7 min, max 12 min before close, 0 of 6460 days >= 30 min). The 6-hr groups are also at the :53 report of each synoptic hour; the last one needed is the same report.
2. **The 6-hr groups do not tile the local day for 16 of 24 stations.** Only UTC-6 stations (AUS, DFW, HOU, MDW, MSP, MSY, OKC, SAT) have synoptic windows aligned to the LST day; everyone else has 6 uncovered hours. Strict 6-hr tiling alone is therefore the wrong construct (92.9%); the 24-hr group is the right one.
3. **Chicago is MDW (Midway), not ORD**, in this program's verified map (KXHIGHCHI -> MDW); the spec's ORD example is only an illustration of the encoding.
4. **Feed (4) is the best feed and (3B) is a close second** -- the settlement variable *is* observable at 2-F granularity; 44 studies did read the wrong field. The earlier false-lock rate (~24%) is a feed problem, not an irreducible one.
5. Feed (1) here is 46.4% HIGH / 82.5% LOW on days with 1-minute coverage, vs the spec's 43.1% / 76.9% from Build A's own pipeline (denominator and per-day source selection not reproduced here; the Build B tz-diagnostic number IS reproduced exactly, see section 2). Direction of bias matches the spec.
6. **Feed (4) may simply be the CLI republished.** IEM's daily summary for these stations likely ingests the NWS climate report, so its 99.85% shows the official value is retrievable after the fact, not that it is independently estimable. This was not verified. Likewise, when IEM publishes the value for day D was not tested: when IEM publishes the daily.json value for day D (the spec says next morning, i.e. after close); this measurement fetched it on 2026-10-27 for past days and says nothing about latency.

## 11. Provenance

`venue_expansion/settlement_observability.py fetch` then `analyze`; cache `venue_expansion/cache/settlement_obs/{metar,daily}/`; nothing written to `cache/finality/*`; no live-trading file touched.
