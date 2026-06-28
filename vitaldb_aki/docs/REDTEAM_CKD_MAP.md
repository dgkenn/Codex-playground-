# Red-team: CKD personalized-MAP-target finding (INSPIRE 131k)

Adversarial stress-tests. Each round mounts the strongest attack a skeptical reviewer/biostatistician would make and tests it empirically. SURVIVES = the finding withstands; WEAKENED/BREAKS = honest downgrade.

## round1: RR non-collapsibility -- does CKD excess survive on the ADDITIVE (RD) scale?

```json
{
 "attack": "RR non-collapsibility -- does CKD excess survive on the ADDITIVE (RD) scale?",
 "strata": {
  "ckd": {
   "n": 8011,
   "events": 1020,
   "base_risk_unexposed": 0.0876,
   "crude_RD": 0.1221,
   "crude_RR": 2.393,
   "adj_RD": 0.0608,
   "adj_RD_ci": [
    0.0451,
    0.0774
   ],
   "adj_RR": 1.585
  },
  "non_ckd": {
   "n": 82235,
   "events": 3477,
   "base_risk_unexposed": 0.0291,
   "crude_RD": 0.0567,
   "crude_RR": 2.946,
   "adj_RD": 0.0151,
   "adj_RD_ci": [
    0.0118,
    0.0181
   ],
   "adj_RR": 1.409
  }
 },
 "additive_interaction_RD_ckd_minus_RD_nonckd": 0.0457,
 "multiplicative_ratio_RR_ckd_over_RR_nonckd": 1.125,
 "verdict": "SURVIVES on the additive scale (CKD adj-RD > non-CKD adj-RD AND CKD adj-RD CI excludes 0) -- the excess is real, not just RR non-collapsibility"
}
```
**Verdict:** SURVIVES on the additive scale (CKD adj-RD > non-CKD adj-RD AND CKD adj-RD CI excludes 0) -- the excess is real, not just RR non-collapsibility

