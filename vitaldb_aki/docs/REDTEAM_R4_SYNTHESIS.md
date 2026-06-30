# Red-team Round 4 — synthesis (the occult-dependence finding, final reckoning)

Round 4 attacked the Round-3-hardened/reframed finding with three adversaries (a code-running "crux"
skeptic whose job was to COLLAPSE it to VIS+tautology, a within-stratum confounding/MICE auditor, and
a CCM editor writing the would-be abstract). Per-reviewer docs: REDTEAM_R4_{CRUX,CONFOUND,EDITOR}.md.

## Verdict: REAL but INCREMENTAL — the standalone top-tier claim does not survive
The finding does not collapse, but the headline that made it feel top-tier ("the information gap doubles
when MAP is at goal") is **72% a restriction-of-range artifact** and is retired. What remains is a real,
hardened, but **incremental** secondary-analysis finding — CCM/ICM-tier as a *supporting* analysis in a
broader dose–severity paper, not the standalone Anesthesiology-tier-or-above finding the goal sought.

### The crux (decisive, code-run)
Requirement-alone mortality AUC: full 0.723, not-at-target 0.712, **at-target 0.743**. The at-target gain
is real but small (+0.031 [0.012, 0.051]); both values sit inside the known VIS range (0.70–0.76). The
gap widening 0.156→0.268 decomposes **72% MAP-restriction / 28% genuine requirement signal**. → "gap
doubles" retired; the load-bearing quantity is the at-target requirement AUC 0.743 (stable across age,
survives MICE, severity-invariant), not the gap.

### What is hardened and survives (the real finding)
- Among normal-MAP ICU patients, the first-24h vasopressor dose stratifies post-24h mortality (Q1 3.1%→Q4
  27.8%; AUC 0.74) while MAP does not (≈0.50, partly by construction).
- Fully adjusted: MICE OR **2.04 [1.85, 2.24]**, **E-value 3.01/2.74** (corrected up from 2.5).
- Within-severity persistence inside at-target: 3/3 lactate tertiles OR>1 (2.30/3.27/2.72).
- Collider test passed (interaction p=0.072); invasive-only stronger (3.10); reproduces exactly; MICE valid.
- Control-theory premise documents tight ICU MAP regulation (CV 0.125) — but is partly a regulation
  identity, not causal proof (Round-3 correction).

### What does NOT survive
- "The information gap doubles at goal" (72% artifact) — RETIRED.
- "Standalone novel top-tier finding" — it is incremental vs VIS/VDI (dose÷MAP)/BPRI (MAP÷VIS); the only
  genuinely new move (at-target conditioning) buys +0.031 AUC.
- "Closes the control-theory causal gap" — withdrawn (Round 3).

### Remaining pre-submission items (if pursued as a CCM/ICM paper)
1. CRITICAL-R4-2 (partly open): single-pressor / sepsis-only restriction WITHIN at-target (the lactate-
   strata half is done: 3/3 tertiles).
2. MODERATE: mechanical ventilation / sedation (GCS) unadjusted — the most plausible residual confounder;
   E-value 2.74 could be approached. Disclose; ideally adjust (needs ventilation flag from chartevents).
3. Single-cohort MIMIC-IV — eICU external replication is the editor's top de-risking step (and the bar
   Shen/BPRI 2026 set), but it would confirm an *incremental* finding, not elevate the tier.

## Bottom line against the goal
Four adversarial rounds converted a flashy "occult dependence / information-gap" claim into an honest,
bulletproofed, but **incremental** result. The genuinely novel content (at-target conditioning) is small
(+0.031 AUC); the rest is the known VIS/VDI/BPRI dose–mortality relationship plus a restriction artifact.
This is a solid CCM/ICM *supporting* analysis, not the standalone Anesthesiology-tier-or-above finding the
goal asked for. The red-team succeeded: it found the ceiling before a journal did.

Cross-ref: REDTEAM_R4_{CRUX,CONFOUND,EDITOR}.md, ICU_OCCULT_DEPENDENCE.md, REDTEAM_R3_SYNTHESIS.md,
RED_TEAM_ROUND2_SYNTHESIS.md, IDEAS_LEDGER.md.
