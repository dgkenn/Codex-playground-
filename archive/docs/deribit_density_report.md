# Deribit implied density vs Polymarket longshot pricing — strike selection

_Generated 2026-07-18T05:18:01.621423+00:00. Deribit spot: BTC 63894.8, ETH 1842.27._

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

- mean Polymarket mid p = **0.5525**, mean bid = 0.5454, mean P_deribit = **0.5501**

- signal (p_mid - P_deribit): mean **0.00241**, median 0.00038, std 0.01453, expiry/asset-clustered t = **3.79**

- corr(p_mid, P_deribit) = **0.9996**

- regress P_deribit ~ p_mid: slope **1.0183** (t=287.49), intercept -0.0125, residual std **0.01208** (residual std = independent info Deribit adds beyond p)

### Longshot region (mid in [0.05,0.35]) (n=8, clusters=6)

- mean Polymarket mid p = **0.1553**, mean bid = 0.1467, mean P_deribit = **0.1249**

- signal (p_mid - P_deribit): mean **0.03041**, median 0.03338, std 0.01345, expiry/asset-clustered t = **7.56**

- corr(p_mid, P_deribit) = **0.9873**

- regress P_deribit ~ p_mid: slope **0.9465** (t=15.23), intercept -0.0221, residual std **0.01269** (residual std = independent info Deribit adds beyond p)

### Longshot band (mid in [0.15,0.30]) (n=2, clusters=2)

- mean Polymarket mid p = **0.2275**, mean bid = 0.22, mean P_deribit = **0.1955**

- signal (p_mid - P_deribit): mean **0.03202**, median 0.03202, std 0.00096, expiry/asset-clustered t = **33.53**

- corr(p_mid, P_deribit) = **None**

### Is the signal independent of p? (collinearity)

- regress (p - P_deribit) ~ p over region (n=8): slope 0.0535 (t=0.86), R^2 = **0.11**, residual std **0.01269**. residual std = signal info orthogonal to p (the only thing that could sharpen selection beyond the price itself)

- Low R^2 here means the signal is NOT explained by p; combined with its small within-region dispersion it is a near-CONSTANT positive offset -> agrees longshots are overpriced but does not discriminate WHICH strike to prefer.

## Calibration anchor (the crux)

- Documented realized in-band YES rate: **0.105**

- Mean Polymarket price in band: **0.1553** (gap to realized: 0.0503)

- Mean Deribit prob in band: **0.1249** (gap to realized: 0.0199)

- **Deribit prob sits closer to the realized band rate than to the Polymarket price: Deribit density is nearer-physical in LEVEL. NOTE this is a calibration (level) fact, not selection power — sharpening WHICH strike to sell needs cross-strike dispersion in the signal, which is near-zero (see collinearity).**

## Forward realized test (deferred)

- forward pairs recorded: 62, resolved: 0

- insufficient resolved forward pairs for regression/Brier


## Verdict

**The sharpening hypothesis is essentially NULL.** Across all aligned strikes the Deribit risk-neutral prob tracks the Polymarket price almost perfectly (corr=0.9996, slope~1.0, residual std ~0.01208): Polymarket price ~= the options-implied risk-neutral density. In the longshot region the signal (p - P_deribit) is consistently POSITIVE (mean +0.03041, expiry/asset-clustered t=7.56) — Deribit AGREES the longshots are overpriced, confirming the short-vol direction — but the magnitude is only ~3 cents versus the ~0.12 edge. P_deribit (0.1249) sits between the Polymarket price (0.1553) and the realized band rate (0.105); it captures only a minority-to-moderate part of the overpricing (~0.27 on the strict n=2 band, ~0.62 on the wider, lower-priced region) — the bulk is a shared tail-risk premium BOTH markets carry and a risk-neutral density cannot see. Crucially, the signal is nearly CONSTANT across strikes (regressed on p: R^2=0.11, slope t=0.86 n.s.; within-region dispersion std ~0.01269). A roughly flat +3 cent signal gives almost no basis to rank one longshot strike as more overpriced than another, so it CANNOT sharpen selection enough to beat the blanket +0.12/ct. Any 'top-signal' ordering is ~1 cent of unvalidated noise. Realized incremental-predictive power (outcome ~ p + P_deribit), Brier(deribit) vs Brier(poly), and top-vs-bottom PnL are DEFERRED to the forward settle (n_resolved=0 now) — historical Deribit density is not retrievable from the public API, so a settled-market backtest is infeasible.
