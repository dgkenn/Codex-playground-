# Trader fingerprinting on anonymous Kalshi — feasibility + verdict (2026-06-12)

## The reframe: proxies ARE buildable (earlier "infeasible" was too pessimistic)
The first research pass assumed trade-tape only. We actually collect **full-depth book snapshots
~1.2s apart** (verified: 120 YES levels / 82 NO levels, [price,size] each, + spot + rtt_ms). Diffing
consecutive snapshots recovers the signals the literature calls "impossible without order messages":
- **Cancellation intensity** — per-level size DECREASE between snapshots minus executed volume = cancels.
- **Add/trade ratio** — size appearing vs traded (heavy-quoting / HFT signature).
- **Quote churn** — Σ|per-level size change| per interval.
- **The ladder-MM fingerprint (VISIBLE IN RAW DATA):** one MM ladders the whole book at a FIXED
  per-level size (e.g. YES=265, NO=250 contracts repeated across dozens of levels). Modal-size
  detection isolates this single actor; its depth and PULL events are trackable.
`fingerprint_proxies.py` builds all of these. Feasibility: CONFIRMED. The user's instinct was right —
1Hz full-depth snapshots are a strong proxy for the missing order-level stream (recovers ~the cancel
signal, loses sub-second precision + true order IDs).

## The test verdict: no deployable signal in available data (underpowered, low prior)
Decisive hypothesis — does early-window ladder-PULL / quote-churn predict the HARD (big-move,
leg-stranding) windows (a LEADING prevention signal)? On the 34 windows with local book snapshots:
corr(early_pull, move) = -0.17 (p=0.48); high-pull windows move 21bps vs 18bps (t=0.4). **No signal.**
n=34 is far too small to be definitive, BUT it joins 6+ consecutive microstructure/directional nulls
(efficient-market wall), so the prior is low.

## The disciplined next step (NOT a backtest on sparse data)
Don't force-fetch the whole book archive to chase a low-prior backtest. Instead WIRE the proxies as
FORWARD features: the live collector already records full-depth book, so compute cancel-intensity /
ladder-pull / churn per fill going forward and feed them to (a) the toxicity model (a genuinely new
adverse-selection feature, distinct from VPIN/flow) and (b) the A/B as a regime gate. They accumulate
with proper sample size and get scored prospectively like everything else — no overfit. If the
ladder-pull-as-leading-strand-signal is real, it surfaces there. Until then: feasibility proven,
no deployable edge yet, consistent with the calibrated-market finding.
