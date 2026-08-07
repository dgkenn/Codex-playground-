# E248 first-pass note — the run is `NOT INTERPRETABLE` under its own branch (d)

*2026-08-07. Written because a correction that is not auditable is not a correction (SOP: bugs are fixed
and re-run, not narrated). The P1 numbers below were reported to the investigator in conversation as a
result before this was noticed; that report was wrong and this note is the record of it.*

---

## 1. What happened

The extraction was resumed from its 2026-08-04 pause and finished: **56,731 of 56,731 windows**, 56,237
`ok`, 494 `error` in three deterministic classes, 56,731 unique `recording_id`s with zero duplicates.
`e248_agent_leakage_at_scale.py` was then run on the finished table, printed three pairwise leakage
tables, and wrote `e248_agent_leakage.json`.

**It printed no verdict, because it contains no verdict branch.** That absence was read as "the
experiment measures rather than adjudicates" — which is what E248's framing had led me to expect (its
own docstring says the unclaimed thing is *the measurement*). The framing is right and the inference
from it was not: the registration also names two primaries and four gates, and adjudicates on them.

## 2. What is missing, verified by grep rather than by reading the prose

| registered object | in code? |
|---|---|
| **P1** agent leakage, patient-level permutation null | **yes** — the only thing implemented |
| **P2** within-patient state tracking | **no** |
| **G1** the phenomenon exists (state axis alive) | **no** |
| **G2** nuisance placebo | **yes**, computed; only its NaN-refusal is wired to a branch |
| **G3** capability, both directions (synthetic positive + independent Gaussian negative) | **no** |
| **G4** support: `>= 300` in smaller arm, `>= 15` windows/patient | **half** — `MIN_ARM = 300` is defined at line 171 and **never referenced**; `MIN_WIN = 15` is applied at line 300 as a silent cohort filter |
| Holm correction across candidates | **no** — named three times in the docstring |
| verdict branch | **no** — the file ends after `json.dump` |

The registered rule is unambiguous: **"(d) NOT INTERPRETABLE — G1, G3 or G4 fails."** Here they were not
evaluated at all, which rule 31 makes *absent*, not negative, and absent is the weaker state.

## 3. What the run does license

**G2 — the gate E154 failed, and the reason this design exists — PASSES in all three pairs.** The rule is
a comparison against the candidates, never an absolute threshold (rule 34):

| pair | median candidate | `opdur_s` | `age` | `bmi` |
|---|---|---|---|---|
| sevo vs des | 0.0758 | 0.0152 | 0.0070 | 0.0505 |
| sevo vs ppf | 0.0581 | 0.0348 | 0.0174 | 0.0161 |
| des vs ppf | 0.0814 | 0.0136 | 0.0257 | 0.0359 |

G4's arm-size half also passes on inspection (412 / 903 / 412, all `>= 300`), though not in code.

**P1, as a measurement with no licence attached:**

| pair | n | null₉₅ | above null | max |
|---|---|---|---|---|
| sevo vs des | 1274 / 412 | 0.0321 | 13 / 22 | `relative_alpha_power` 0.1442 |
| sevo vs ppf | 1274 / 903 | 0.0246 | 18 / 22 | `alpha_peak_hz` 0.2059 |
| des vs ppf | 412 / 903 | 0.0337 | 16 / 22 | `alpha_peak_hz` 0.2922 |

20,000 patient-level permutations; empirical and analytic nulls agree to the third decimal. `emg_index`
is at the null in all three pairs, so whatever this is, it is not the muscle artefact that E22, E70 and
E100 turned out to be measuring.

**None of that is claimable yet**, and G1 is the specific reason. Its own words: *"if nothing tracks the
ventilation transition, a leakage comparison at matched state is a comparison between two cohorts, not
two agents."* That is rule 32, which this project has already paid for once, written into the design in
advance by someone who knew it — and then not implemented.

## 4. Two registered numbers that came in lower, and they are not rounding

* **Arms are 1,274 / 412 / 903 (2,589 cases)**, against a registered 1,474 / 460 / 996 (2,930).
  **CORRECTED 2026-08-07 by E249, which counted it:** the 341-case gap is *not* what this note first
  said. It is **330 landmarked cases with NO usable window in the table at all**, plus only **11**
  dropped by `MIN_WIN >= 15`. Those are different failures — the first is extraction coverage, the
  second is the registered support criterion — and attributing the whole gap to `MIN_WIN` overstated
  what the gate discarded by a factor of thirty.
  **The drop is mildly one-sided and the direction is worth recording**: by arm it runs
  **sevo 13.57 % / des 10.43 % / ppf 9.34 %**, a spread of 4.23 points against sevoflurane. E249 labels
  that "even across arms" on a 0.05 threshold **which was invented for the occasion and is exactly what
  rule 63 forbids** — the honest statement is the three rates, not the label.
* **Floors are 0.0321 / 0.0246 / 0.0337** against a registered 0.0302 / 0.0232 / 0.0319, which follows
  from the smaller arms. The design's central claim — that the floor falls from E154's 0.1904 to the
  0.02–0.03 range — survives intact. `CLAUDE.md` quotes 415 for `des`; it is 412.

## 5. What the successor must do

1. **Implement P2, G1 and G3 with the registered thresholds unchanged**, and Holm across candidates.
2. **Record that P1 was seen before those gates were written.** Completing a gate that was never coded
   is not goalpost-moving — the threshold is not being moved, it is being applied for the first time —
   but the ordering is a fact the reader is owed, and G1/G3 are independent of P1's outcome in a way
   that makes the claim checkable: neither can be tuned to make P1 pass.
3. **Report the 341-case `MIN_WIN` exclusion** and test whether it is arm-related. If desflurane cases
   are shorter, the drop is not innocent.
4. **Do not re-run P1.** It is computed, its null is calibrated, and re-running it after the gates exist
   would invite exactly the suspicion this note is written to avoid.
