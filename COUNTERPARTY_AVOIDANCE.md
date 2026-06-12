# Counterparty avoidance — the optimal policy (deep dive 2026-06-12, 20k fills, markout-targeted)

## The reframe that mattered
Counterparty toxicity = ADVERSE SELECTION (markout<0), NOT per-leg settle (one leg of every YES+NO
box mechanically settles to 0 -- gating on that gates the box itself). Target = markout + stranding.

## The findings
1. **The prize is modest and adverse selection is near-random.** P(markout<0)=0.50, best single-feature
   AUC only 0.546 (sig_adv, the pre-fill spot move). Realistic avoidable prize: ~+0.1-0.3c/fill of kept
   volume, NOT the ~9c oracle. We cannot dramatically improve -- per-fill toxicity is mostly noise.
2. **t31 (face-contrarian) is the OPTIMAL gate, and it's already deployed + now VALIDATED on 20k fills**
   (was the n=19 exciting lead): contrarian-side fills +0.233c/fill OOS vs the momentum side it excludes
   -0.182c = a genuine **+0.41c/fill adverse-selection spread**, the largest of any gate. Beats t29
   (+0.154), t32, t18.
3. **The take-size feature does NOT improve the fitted model** (dAUC~0.000) and is uncorrelated with VPIN
   (corr 0.008) -- but a >100-contract TAIL-TRIM is a clean monotone add-on (+0.05-0.10c/fill, keeps
   ~92% volume). Wired as t33 (trim alone) and t34 (face-contrarian + trim = the dive's best combined
   point, +0.341c/fill on 45% of volume). 
4. **The fitted combined LOGIT gate is OVERFIT** -- its +1.52c/win settle gain went NEGATIVE on the
   honest markout target (non-monotone frontier). NOT deployed (a false positive caught by targeting
   markout instead of settle).
5. **The earlier fingerprint size-toxicity (-2.2c facing 50+ takes) was SETTLE-based** = those takers
   win the DIRECTION (informed about the outcome), but they do NOT pick us off on 1-min MARKOUT (large
   takes had slightly POSITIVE markout here). So size helps the directional/settle story, not the
   markout-avoidance gate -- consistent, just different toxicity definitions.

## Deployed decision
- **t31 is the primary counterparty gate (validated). t34 (t31 + take-tail-trim) is the optimal
  combined policy -- both accumulating in the A/B vs the n>=300 bar.** No new model; the consolidated
  gate is what we already have. The honest incremental gain from the new feature is small (+0.05-0.10c)
  but clean. Do NOT deploy a fitted toxicity LOGIT on the settle metric (overfit).
- Bottom line: counterparty avoidance is a real but SMALL edge (adverse selection is ~random per fill);
  t31 captures most of it; we're already near the frontier.
