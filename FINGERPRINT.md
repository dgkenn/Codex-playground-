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

## UPDATE (2026-06-12, adequate-sample deep dive + causality test)
### The "one-sided pull predicts direction" signal is NOT tradeable — it's reactive, not leading
One agent found pull→direction at corr -0.47 (n=109), which looked like a discovery. But that was a
WHOLE-WINDOW pull vs WHOLE-WINDOW move correlation = COINCIDENT (the MM pulls a side BECAUSE it's
being hit by a move already underway). The decisive causality test (early-window pull, min 0-7 ->
LATER move, min 8-15, strict temporal separation, n=106):
- coincident (whole-window): corr -0.087, t=-0.9 (already weak when measured cleanly)
- **LEADING (early pull -> late move): IS corr -0.068 (p=0.60), OOS -0.084 (p=0.59) -- NULL.**
The pull has ZERO predictive power for the subsequent move. The MM reprices reactively (74% of levels
stale within 3s of a spot move; 1.2s mechanical heartbeat). Do NOT trade ladder-pull as a directional
signal. (7th directional null.)

### What IS robust (trade-tape Test A-C, proper 2779-window sample, IS/OOS)
- **VPIN -> pairing: OOS r=-0.346.** High-toxicity windows pair worse. Confirmed on big sample.
- **High-VPIN windows strand a leg 9.7x more often (6.8% vs 0.7%).** A real, EARLY (causal) prevention
  signal -- VPIN is computed from flow-so-far, so it's tradeable, unlike the pull.
- **Counterparty-mix clusters:** MM-dominated low-vol windows pair 96.1%; directional high-vol windows
  (4.2% of windows) pair 77.4% and cause most strands. VPIN is the early proxy for which cluster.
- **NET: this validates the toxicity/VPIN gate we ALREADY have (t13/t18) on a large sample -- not a
  new edge, a confirmation of the deployed one.**

### The one genuinely NEW actionable item: execution timing vs the mechanical MM
The ladder-MM is purely MECHANICAL (1.2s heartbeat, symmetric, cancel/add~=1.0, no info skew) and
SLOW to reprice (74% stale 3s post-move). That's a QUEUE-TIMING opportunity (not direction): when spot
moves, WE can refresh our quote to the new fair level BEFORE the mechanical MM catches up (~1-3s
window), landing front-of-queue at the right price. This is execution alpha, consistent with the
"queue position is first-order" finding -- worth a live experiment (tie requote timing to spot ticks).
Fingerprint verdict: real & mechanical, NO directional alpha, but reinforces toxicity-gating + gives a
concrete execution-timing refinement.
