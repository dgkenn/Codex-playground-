# Deribit implied density vs Polymarket longshot pricing — strike selection

_Generated 2026-07-18T05:16:10.309048+00:00. Deribit spot: BTC 63892.16, ETH 1842.21._

## Question

Can the Deribit options-implied risk-neutral density identify WHICH weekly Polymarket 'above $X' longshots are most overpriced, so a selective sell beats the blanket short-vol edge of +0.12/contract?

## Data constraint (blunt)

Deribit's public API serves only the **current** option chain — no historical marks. The only Polymarket 'above $X on <date>' markets whose close date aligns with a current Deribit expiry are **open/unresolved**. A historical realized-PnL backtest of the Deribit signal is therefore **infeasible** with public data (cannot rebuild the density that existed at a settled weekly's close). This run delivers a **live paired cross-sectional** study plus **forward recording** for the realized regression/Brier once these resolve.

## Alignment

- Open weekly strike-markets found: **105**

- Aligned to a same-date Deribit expiry: **62** (unmatched close-dates: 43)

- Deribit expiries (BTC): ['2026-07-18', '2026-07-19', '2026-07-20', '2026-07-21', '2026-07-24', '2026-07-31', '2026-08-07', '2026-08-28', '2026-09-25', '2026-12-25', '2027-03-26', '2027-06-25']

- Polymarket close dates: ['2026-07-20', '2026-07-21', '2026-07-22', '2026-07-23', '2026-07-24']

- Aligned close dates used: ['2026-07-20', '2026-07-21', '2026-07-24']

- Timing note: Polymarket ladders close 16:00 UTC vs Deribit 08:00 UTC same date; density evaluated at T = time-to-Polymarket-close using the Deribit smile (~8h horizon offset absorbed).

## Cross-sectional deviation (live)

### All aligned strikes (n=62, clusters=6)

- mean Polymarket mid p = **0.5531**, mean bid = 0.546, mean P_deribit = **0.55**

- signal (p_mid - P_deribit): mean **0.00312**, median 0.00107, std 0.01445, expiry/asset-clustered t = **5.9**

- corr(p_mid, P_deribit) = **0.9996**

- regress P_deribit ~ p_mid: slope **1.0184** (t=290.21), intercept -0.0133, residual std **0.01197** (residual std = independent info Deribit adds beyond p)

### Longshot region (mid in [0.05,0.35]) (n=8, clusters=6)

- mean Polymarket mid p = **0.1557**, mean bid = 0.1475, mean P_deribit = **0.1243**

- signal (p_mid - P_deribit): mean **0.03139**, median 0.03449, std 0.01396, expiry/asset-clustered t = **7.52**

- corr(p_mid, P_deribit) = **0.9861**

- regress P_deribit ~ p_mid: slope **0.9459** (t=14.55), intercept -0.023, residual std **0.01322** (residual std = independent info Deribit adds beyond p)

### Longshot band (mid in [0.15,0.30]) (n=2, clusters=2)

- mean Polymarket mid p = **0.2275**, mean bid = 0.22, mean P_deribit = **0.1944**

- signal (p_mid - P_deribit): mean **0.0331**, median 0.0331, std 0.00099, expiry/asset-clustered t = **33.27**

- corr(p_mid, P_deribit) = **None**

### Is the signal independent of p? (collinearity)

- regress (p - P_deribit) ~ p over region (n=8): slope 0.0541 (t=0.83), R^2 = **0.104**, residual std **0.01322**. residual std = signal info orthogonal to p (the only thing that could sharpen selection beyond the price itself)

## Calibration anchor (the crux)

- Documented realized in-band YES rate: **0.105**

- Mean Polymarket price in band: **0.1557** (gap to realized: 0.0507)

- Mean Deribit prob in band: **0.1243** (gap to realized: 0.0193)

- **Deribit prob sits closer to the realized band rate than to the Polymarket price: Deribit density is nearer-physical and COULD sharpen selection.**

## Forward realized test (deferred)

- forward pairs recorded: 62, resolved: 0

- insufficient resolved forward pairs for regression/Brier


## Verdict

**Mechanism is essentially NULL.** Across all aligned strikes the Deribit risk-neutral prob tracks the Polymarket price almost perfectly (corr=0.9996, slope~1.0, residual std ~0.01197): Polymarket price ~= the options-implied risk-neutral density, so the density adds little beyond p. In the longshot region P_deribit (0.1243) sits between the Polymarket price (0.1557) and the realized band rate (0.105), capturing only ~0.619 of the overpricing — the bulk is a shared tail-risk premium BOTH markets carry and a risk-neutral density cannot see. The signal (p - P_deribit) is largely a function of p itself (R^2=0.104 on p), leaving only ~0.01322 of orthogonal variation — too little in-band dispersion to rank strikes independently of the price. It does NOT plausibly beat the blanket +0.12/ct; any directional sharpening is a few cents at most and collinear with 'more OTM', which p already encodes. Realized incremental-predictive power (outcome ~ p + P_deribit), Brier, and top-vs-bottom PnL are DEFERRED to the forward settle (n_resolved=0 now) — historical Deribit density is not retrievable from the public API.
