# E270–E279 — third battery. **7 of 9 met, and E273 reverses E251.**

*2026-08-07. Predictions committed before any statistic existed. PERI = 2,589 cases peri-landmark;
CTRL = 740 cases at maintenance (arms 249/244/247, analytic null₉₅ ≈ 0.0511).*

---

## 1. E260's reversal is confirmed, quantitatively

**E270.** Same 19 candidates, same state-tracking axis, leakage measured in two places:

    Spearman(PERI leakage, state) = -0.1807      (E250's number, reproduced exactly)
    Spearman(CTRL leakage, state) = +0.4123

    E261's corner at CTRL: -0.0267 against subset null 95th -0.0124,  p = 0.0968

The correlation **flips sign**, and the corner that scored p = 0.0003 on peri-landmark leakage no longer
beats its own null. Prediction MET. E250's dissociation and E261's corner are withdrawn, not weakened.

## 2. The leakage-versus-depth curve — new, clean, and monotone in 6 of 6

**E271.** Stratifying CTRL cases on their own control-window median BIS into terciles
(≤ 36.7 / ≤ 42.6 / above, n ≈ 242 each):

| candidate | deep | mid | light |
|---|---|---|---|
| `whole_head_exponent` | **0.4733** | 0.4123 | 0.3060 |
| `multiscale_entropy_slope` | **0.4728** | 0.4504 | 0.2895 |
| `emg_beta_gamma_fraction` | **0.4684** | 0.3888 | 0.2273 |
| `critical_slowing_ar1` | **0.4604** | 0.4293 | 0.3237 |
| `exponent_low` | **0.4459** | 0.3953 | 0.2738 |
| `alpha_peak_hz` | **0.3825** | 0.3672 | 0.3228 |

**Monotone deep ≥ mid ≥ light in 6 of 6.** Agent identity scales with anaesthetic depth. This is the
quantity Challenge A's minimisation criterion actually needs and nothing in this programme had it.

## 3. Most of the leakage is a location shift — which is constructive

**E272.** Subtracting each arm's own median from that arm removes **51–98 %** of leakage, above 80 % in
most cells (`whole_head_exponent` sevo/ppf 0.352 → 0.006, −98 %). Prediction MET.

The arms differ mainly in *where the measure sits*, not in spread or shape. That is the most tractable
form the problem could take: a per-drug calibration constant would remove most of it. It also closes the
loop with E254 (leakage in the level, not the change) using a different method.

## 4. **E273 REVERSES E251, AND THAT IS THIS BATTERY'S MOST IMPORTANT RESULT**

Two turns ago I reported, as a headline, that BIS leaks *more* agent identity than our panel's median in
all three pairs. At maintenance:

| pair | BIS | median candidate | |
|---|---|---|---|
| sevo vs des | 0.0747 | 0.0918 | **BIS below** |
| sevo vs ppf | 0.0469 | 0.2241 | **BIS below** |
| des vs ppf | 0.1218 | 0.2077 | **BIS below** |

**BIS is MORE agent-invariant than our median candidate in all three pairs, by a wide margin in two.**
Prediction NOT MET, and the failure is the finding.

E251's claim was a peri-landmark artefact — **the identical error E260 caught in the corner, running in
the opposite direction.** I registered E273 precisely to catch that, and it did. The correction:

* **Withdrawn:** "the commercial incumbent is less agent-invariant than our panel", and E269's
  "among the worst in the panel" ranking.
* **Stands:** E262's mechanism — BIS's leakage, wherever measured, is largely reducible to the panel's
  own spectral content (79.5 / 50.4 / 96.2 % reduction). That was always a within-state comparison.
* **The honest sentence is now the opposite of the one I gave you:** at the depth where anaesthesia
  actually operates, BIS carries *less* drug identity than the median measure in our panel. It is a
  better-behaved incumbent than this programme had assumed, not a worse one.

## 5. The ranking does not transport either

**E274.** Spearman between each candidate's PERI and CTRL leakage rank: **+0.3684 / +0.2860 / +0.3474**.
Prediction MET. So it is not merely that levels shift — the *ordering* of which measures leak most is
weakly preserved at best. A candidate-selection procedure run at one state does not select the same
candidates at another, which is the practical form of E260's lesson.

## 6. Two more, and one is uncomfortable

**E275 — muscle is the MOST stable measure across states, not the least.** Prediction NOT MET.
`emg_kurtosis` correlates **+0.9465** between the two states 40 minutes apart; the aperiodic/complexity
median is +0.5458 against a muscle median of +0.6901. Muscle measures behave like a **patient trait** —
which is exactly why they can look like good low-leakage candidates and exactly the trap E22, E70 and
E100 each fell into.

**E277 / E278 — CTRL leakage is robust.** High-SQI restriction leaves it within tolerance (often slightly
higher), and trimming to common age/BMI/duration support retains it (`whole_head_exponent` des/ppf
0.379 → 0.378 on 224 of 491 cases). Both MET. The maintenance leakage is not a sensor artefact and not a
case-mix artefact.

## 7. E279 — the Challenge A screen, and the survivor is the artefact channel

Requiring above-median state tracking AND below-median leakage at **both** states:

    medians: state 0.1799 | PERI leakage 0.1046 | CTRL leakage 0.2950
    SURVIVORS: ['emg_index']

Prediction MET ("empty or at most one"), and the letter of the result understates it. **The sole survivor
is the muscle index** — not a brain-state measure, and the very quantity three prior experiments in this
programme mistook for one. Every genuine EEG candidate fails at one state or the other:
`whole_head_exponent` passes at PERI (0.0668) and fails badly at CTRL (0.3788).

**So Challenge A's candidate shortlist on this deposit is empty.** That is a clean, well-supported
negative, and it is worth more than the corner I reported two turns ago, which was an artefact.

## 8. E276 — BLOCKED, and recorded rather than fudged

The registered item was a literature check on the direction of the propofol/volatile spectral difference.
PubMed search returned two candidate records (PMIDs 30297992, 23695090), **but the metadata tool requires
interactive approval unavailable in this session, so neither could be verified from its MEDLINE record.**
Rule 25 forbids citing what has not been verified that way, and rule 39 extends it to any record. **No
citation is made and no direction is claimed.** Owed to a session that can fetch them.

## 9. What a successor owes

1. **Quote the depth-stratified leakage curve, never a single number.** E271 makes this concrete and
   E274 shows the ranking does not transport either.
2. **Re-examine every leakage claim in this programme for the state it was measured in** — E251 and E261
   both fell to this in one session, in opposite directions.
3. **Test the per-drug calibration E272 implies**: if a location shift explains 80–98 %, a candidate that
   is invariant *after* per-drug centring may exist even though none is invariant before it. That is a
   different and much more promising screen than E279's.
4. **Treat any low-leakage muscle measure as disqualified on its face** (E275, E279).
