# ED triage under-triage disparity (Stanford MC-MED) — LIVE LEAD (passed first robustness gate)

**Status:** first two analytic passes done + robustness-adjusted; **survived** (unlike the session's other post-C8
leads). Fresh, previously-untouched dataset. Single-center — external replication is the key open requirement.

## Design (measurement-reclassification applied to triage)
- **Deployed measure:** ESI acuity (1–5), a *subjective* triage-nurse assignment that gates door-to-room time and
  resource intensity. High-acuity = ESI 1–2.
- **Independent reference:** (a) objective triage-vitals early-warning score (MEWS-like abnormal-vital count, measured
  at the door, pre-treatment); (b) hard eventual outcome (ICU admission / death). RTM-safe: condition on the
  reference, compare ESI by race/ethnicity.
- **Consequence:** among patients discharged from the ED, 72-hour return visit (recognized premature-discharge /
  missed-severity safety metric).
- **Cohort:** MC-MED, 118,385 adult ED visits; race White 44k / Hispanic 32k / Asian 19k / Black 7.5k / Other.

## Findings
**Under-triage** — logistic P(high-acuity ESI 1–2) ~ MEWS + age + sex + race [+ payor + EMS arrival]:
- MEWS OR 3.0 (anchor validated). At matched severity:
  - **Hispanic OR 0.86 [0.80–0.93]** (base 0.84; strengthens with payor/EMS adjustment)
  - **Black OR 0.89 [0.79–0.99]** (becomes significant after payor/EMS adjustment)
  - Asian OR ~1.09 (slightly higher); Pacific-Islander/Other NS.
- Descriptive: at objective MEWS≥2, high-acuity rate White 73% vs Hispanic 69%, meanMEWS matched (~2.45).

**Consequence** — 72h-return | ED-discharged ~ race + age + MEWS + payor + sex (n=69,561, base 5.6%):
- **Black OR 1.60 [1.42–1.80]** — large, robust ~60% higher bounce-back.
- Hispanic OR 0.95 [0.87–1.03] — **null after adjustment** (crude elevation was confounded; only under-triage holds).
- Asian OR 0.83 (lower).

**Coherent signal (strongest, Black patients):** under-triaged relative to objective severity AND markedly higher
72h return — a measurement→consequence chain that survives insurance/access adjustment.

## Threats / hardening needed (before any top-tier claim)
- **Single center** — external replication required (candidates: MIMIC-IV-ED, or another ED dataset). This is the #1 gate.
- **MEWS is a crude objective anchor** — ESI legitimately uses chief complaint + predicted resource use; at the
  hard-outcome anchor (ICU/death) the gaps shrink (Black 71% vs White 74%), so part of the MEWS-based gap may be MEWS
  imperfection. Report both anchors; do not over-claim.
- **72h return is a soft outcome** — add harder endpoints where available (return-with-admission, return-with-ICU,
  post-discharge death). Return-visit capture may be incomplete (only 58k have Hours_to_next_visit).
- **Language / interpreter need** for Hispanic under-triage is an unmeasured mechanism (could be actionable, not just
  bias) — flag as limitation; the Black finding is not language-confounded.
- **Chief-complaint case-mix** — adjust for CC category / presenting complaint in the next pass.

## Realistic tier
Solid health-equity contribution (JAMA Netw Open / JAMA IM / Annals of Emergency Medicine). Not obviously NEJM/Nature
on one center, but the objective-severity-anchored + adjusted-consequence design is cleaner than much prior triage-
disparity work. A convincing **external replication** + harder outcome would raise the ceiling.

## Next steps
1. External replication in a second ED dataset (MIMIC-IV-ED has triage acuity + vitals + race + ED dispo).
2. Harder outcomes (return-with-admission, post-discharge mortality); adjust for chief-complaint category.
3. Adversarial red-team (sonnet): is the objective anchor fair? is under-triage the right causal frame vs case-mix?
4. Quantify the door-to-room *time* disparity (a more direct mechanism than acuity label) if timestamps support it.

## EXTERNAL REPLICATION — MIMIC-IV-ED (BIDMC Boston, 398,622 stays) [added this session]
Independent health system, same design. **Under-triage REPLICATES and strengthens** (MEWS anchor OR 3.79):
- Black **OR 0.78 [0.75–0.81]**, Hispanic **OR 0.72 [0.68–0.76]**, Asian **OR 0.83 [0.77–0.89]** — all significant,
  all stronger than MC-MED.
**72h-return consequence replicates:** Black **OR 1.19 [1.14–1.24]** (MC-MED 1.60); Hispanic null (0.99) and Asian
lower (0.83) — both identical in direction to MC-MED. The Hispanic-return null replicating in BOTH centers indicates
a disciplined signal (under-triage is real for Hispanic; the return-consequence is specifically a Black-patient
signal in both systems).

**Two-center status:** ~500k ED visits, Stanford (CA) + BIDMC (MA). Core under-triage disparity is now externally
replicated with an objective severity anchor — the #1 gate is cleared. Remaining: chief-complaint case-mix
adjustment, door-to-room *time* mechanism, harder outcome (30-day post-discharge mortality via dod did not populate
sufficiently among discharged — needs better mortality linkage), adversarial red-team. Tier raised toward JAMA/JAMA IM.
