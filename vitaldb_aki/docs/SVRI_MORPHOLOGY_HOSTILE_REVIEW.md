# Pivot 2 hostile review: SVR-free waveform estimate of measured SVRI

N (direct-EV1000-SVR cases, physiologic SVRI) = 221. The one finding that survived the outcome-confounding battery (targets MEASURED physiology, not a confounded outcome) -- here stress-tested with the same hostility.

- **A. Circularity:** strict NON-pressure morphology incremental R^2 over ALL pressure scalars (direct-SVR) = **0.1109** -> PASS (not just re-reading MAP).
- **B. Overfitting:** OOF r 0.4561 vs permutation null mean 0.0745 (95th 0.1749), perm p = **0.005** -> PASS.
- **C. Body-size:** morphology incremental R^2 over pressure+weight/BSA/age/sex = **0.0556** -> PASS.
- **D. Mechanism:** tau (diastolic decay ~ R*C) partial-Spearman vs SVRI given MAP = **0.1613** (raw 0.1643).
- **E. Stability:** OOF r 0.4561, bootstrap CI [0.3753, 0.6182].

## Verdict: PASSES hostile review -- strict non-pressure morphology predicts DIRECT-measured SVRI beyond all pressure scalars (incr R2 0.1109), beats permutation null (p=0.005), survives body-size adjustment (incr R2 0.0556); tau partial-vs-SVRI given MAP = 0.1613.

Limitations: single-centre; EV1000/Vigileo CO-monitor subset (selected); SVRI is CO-derived (noisy); modest N. PASS here means the SVR-free morphology signal is real, non-circular, not overfit, and not a body-size proxy -- a defensible MEASUREMENT claim (no outcome, so no outcome-confounding), and the basis for Phase 2e.
