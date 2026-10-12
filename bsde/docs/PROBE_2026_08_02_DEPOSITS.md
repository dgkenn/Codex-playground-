# Two feasibility probes, 2026-08-02 — one deposit refused, three found

*Both probes were run BEFORE any registration (rule 41). Every number below was recomputed by Opus against
the raw source; delegated agents produced them first. Where my recomputation disagreed with the agent's, my
number is the one recorded and the disagreement is stated.*

---

## 1. ds004541 is REFUSED as a Challenge C replication cohort — its incumbent is dead

E208 burned the Chennu deposit by computing a secondary arm before gating its incumbent's aliveness. E209
fixed the process by probing first. This is that process working as intended: **the probe refused the
deposit, so nothing was spent and nothing was contaminated.**

**No candidate column was correlated with any label.** `multiscale_entropy_slope`, `whole_head_exponent`,
`relative_alpha_power` and `pac_slow_alpha` were checked for existence and finite count only;
`wpli_theta` is not in this deposit's panel at all. ds004541 remains a clean, unused replication cohort for
any future design that brings a *different* incumbent.

### What the deposit contains

`bsde/results/ds004541_v2.csv`, 125 rows of which **124 have `status=ok`** (one lost to a transient
`URLError` during extraction), **8 subjects**, 32 columns. `ds004541_loc.csv` is a strict subset from an
earlier partial run and is not authoritative.

The recording ids encode a signed offset around loss of consciousness, which catalogue rule 61 warns must be
PARSED rather than substring-matched — `loc` matches `@loc-300`, 300 seconds *before* the event. Parsing
`^sub-\d+@(baseline|start|loc|roc)([+-]\d+)?$` resolves **124 of 124** ids, and the parsed offset agrees with
the deposit's own `meta_offset_s` column on **all 124 rows, 0 mismatches**. A five-level ordered depth label
is constructible from `meta_phase`:

| level | phase | n |
|---|---|---|
| 0 | baseline + awake_pre_drug | 27 |
| 1 | pre_loc | 42 |
| 2 | post_loc | 41 |
| 3 | pre_roc | 7 |
| 4 | post_roc | 7 |

Mean recording time rises monotonically across those phases, so the ordering is real and not an artefact of
the label construction.

### Why it is refused

**The declared incumbent, `spectral_edge_95`, does not predict that label.**

| quantity | value |
|---|---|
| Spearman(`spectral_edge_95`, ordered label) | **−0.0170** |
| within-subject label permutation null, 500 draws, 95th percentile of \|rho\| | **0.1561** |
| incumbent alive? | **NO** |

Rule 53, and E208's grave: *if the incumbent cannot predict the transition at all, beating it is not a
result.* The same gate that killed E208 on Chennu refuses ds004541 here — but this time **before** any
candidate was touched.

*Disagreement recorded:* the delegated probe reported this correlation as −0.0791 against a null p95 of
0.1475. My independent recomputation on the 124 `status=ok` rows gives −0.0170 against 0.1561. The verdict
is identical under either number — both are far inside the null — and mine is the one recorded.

### Two further reasons not to reach for this deposit

* **8 subjects**, one of whom (`sub-11`) has only three level-0 rows and is therefore invariant under
  within-subject permutation, contributing nothing to any within-subject test.
* Levels 3 and 4 hold **7 rows each**. Any test of the deep end is 7 observations over 7 subjects.

**No artefact gradient** was found (Spearman(`emg_index`, label) = +0.057, no monotone trend across deciles)
and **no sentinel values** — every feature column is 100 % finite and no single value holds more than 1.6 %
of any column. So the refusal is specifically about the incumbent, not about data quality.

---

## 2. Three open deposits with a graded depth label — and the one that looked best is disqualified

E211 recorded a blocker rather than working around it: *a genuine FORWARD test of the reference
recommendation on a new cohort is not available with local data.* This probe looked for one. Method was
`curl` plus a parser against OpenNeuro's GraphQL API, its S3 listings and PhysioNet's `SHA256SUMS.txt` and
`RECORDS` files — never a WebFetch summary of a manifest, which rule 39 records this project has already
been burned by once.

### sleep-edfx — DISQUALIFIED, and the reason matters

The search returned PhysioNet's Sleep-EDF Expanded (100 subjects, seven ordered stages, 8.1 GB, Open Data
Commons licence, unauthenticated download confirmed by `curl` returning HTTP 200 on its `RECORDS` file).

**It cannot serve as the forward test, because it is already the evaluation cohort.** E95's
`sleep_stages()` reads `sleep_edfx_five_stage.csv`, so the sleep ladder E198 and E211 resolve *is*
sleep-edfx. Testing the recommendation on it would be the circularity E211 explicitly declined.

This is worth recording because the deposit looks ideal on every axis a search scores, and only the
project's own record disqualifies it — catalogue rule 50's corollary: **an internal record is a source like
any other, and it has to be searched before a finding is called new.**

### The two that do qualify

| deposit | subjects | label | size | licence |
|---|---|---|---|---|
| **`capslpdb`** (PhysioNet, CAP Sleep Database v1.0.0) | **108**, across 8 diagnostic groups plus controls | `SLEEP-S0…S4`, `SLEEP-REM` per 30 s epoch, in a per-record `.txt` scoring export | 40.1 GB | ODC-By 1.0, unauthenticated |
| **`ds006695`** (OpenNeuro, forehead-patch sleep staging) | 19 | 5-level AASM hypnogram, embedded in the EEGLAB `.set` struct as `EEG.VisualHypnogram` | 9.4 GB, 84 files | CC0 |

**`capslpdb` is the better forward test and it is not close.** A normative reference's whole claim is that it
transports to people who were not in it, and capslpdb's 108 subjects span bruxism, insomnia, narcolepsy,
NFLE, PLM, RBD and sleep-disordered breathing alongside healthy controls — a clinically heterogeneous
population, which is the hard case rather than the convenient one. `ds006695` is a useful second check but
its three forehead channels make `whole_head_exponent` a different measurement, not the same one elsewhere.

**Cost, stated honestly:** the forward test needs `whole_head_exponent` extracted on capslpdb, which is a
40 GB streaming pass. Its label is a text table and needs no binary parsing, unlike ds006695 whose
hypnogram lives inside an EEGLAB struct.

**What did NOT qualify**, from an exhaustive pass over all 447 public OpenNeuro EEG datasets: 13 matched on
keywords, and after excluding ds005620 and ds004541 the rest failed the three-ordered-levels test —
ds005273 and ds001785 are binary perceptual contrasts, ds004572 is sham hypnosis with no depth scale,
ds004902 is single-state resting EEG, ds006576 and ds005530 are REM-only manipulations, ds003380 is a pig
model. `ds005429` matched only because "loc" appears inside "local–global" — rule 61's trap, discarded on
sight.
