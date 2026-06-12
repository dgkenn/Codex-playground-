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

## NEW fingerprint: taker SIZE-toxicity gradient (2026-06-12, 2.1M trades, OOS-STABLE)
Profiling the AGGRESSOR (taker) side, not just the resting MM, the maker's settle-edge facing each
taker-size is a clean, monotone, OOS-stable signal:
- **small takes (1-11 ct): +0.55c IS / +0.46c OOS** (n=1.3M) -- NAIVE RETAIL, our bread-and-butter
  spread capture (taker win rate <50%).
- **mid (12-50): -0.84c / -0.08c** -- toxic-ish.
- **large (50+): -1.42c / -2.21c** -- consistently INFORMED/toxic both halves.
- specific signature: **size-19 takes = -3.14c IS / -3.35c OOS** (n=447/360) -- a persistent informed
  algo. (Also size-14 toxic; 20/30/50 noisier.)
**Interpretation:** taker SIZE is a toxicity proxy -- informed flow is large flow (Glosten-Milgrom).
This is the WHY behind VPIN/flow gating working. **Already wired:** VPIN spikes exactly when large
takes hit, so t32 (VPIN open gate) captures this signal -- no separate size-gate needed (and the
collector vs parquet sz-unit difference makes a raw-size threshold risky). The finding strengthens the
toxicity thesis: small=naive (profit), large=informed (avoid), and t32/t06/t18 are the deployed levers.

## Size-19 taker forensic: plausibly INFORMED, but NOT copyable (the signal is invisible to us)
Deep profile (n=807, 531 windows, 99% BTC): size-19 is the most credible informed-actor signature found.
- **Beats the price-implied win rate in EVERY bucket** (realized vs implied: longshots 42% vs 40%, mid
  56% vs 49%, favorites 46% vs 43%) -- it's not just longshot variance.
- **Edge is broad-based, not fat-tailed:** top-5 trades = only 18% of total edge; median trade -0.10c.
  On calibrated MID contracts (0.3-0.7) it earns +7.0c, wins 56% vs 49% implied (t=1.9, n=161).
- Neighbors are NULL (size-18 -0.0c) / weak (size-20 +1.3c), so 19 is a distinct signature.
**CAN WE COPY IT? No.** Its trades have NO observable trigger in our data: 51% buy-YES (no directional
bias), no spot-momentum tilt (52% buy on spot-up vs 48% on spot-down), all minutes (mean k=9.4), all
prices. It wins 56% on ~50/50 contracts via a signal WE CANNOT SEE (faster spot feed / order-flow read
/ cross-market / news). You can't replicate an informational edge whose conditioning variable is
invisible. FOLLOWING it (piggyback its public takes) is fee-killed: its ~3c gross edge minus the ~2c
TAKER fee = ~1c, and we'd be late + we're a maker (can't take). 
**The actionable response is what we ALREADY do: AVOID being its counterparty** -- being the maker it
picks off is exactly the loss the toxicity/VPIN gate (t32) and the size-toxicity finding defend against.
Caveat: even "it's informed" is marginal (clean-subset t=1.9). Net: a real informed taker, uncopyable,
already defended against. Don't chase it; the edge stays counterparty-avoidance, not imitation.

## Cross-asset + presence dive: the complete participant census (2026-06-12)
~3 real systematic participants per market; the genuinely-NEW findings (all on ~34 windows -- BELOW
the 300-window bar, so MEASURE forward, do not deploy):
1. **Each asset has its OWN distinct MM** -- BTC 265/250, ETH 20/21, SOL 30/31, XRP 10/11. The 265/250
   ladder is BTC-EXCLUSIVE (the same entity does NOT quote the alts). So no multi-market actor to
   exploit. BUT cross-asset depth-DROPS are correlated (0.45-0.63, co-drop 2-2.3x vs independence) =
   a shared RISK-OFF trigger (spot vol). Candidate regime gate: simultaneous >30% depth collapse
   across BTC+ETH+SOL = toxic, pause quoting (live-computable, not yet wired).
2. **HOUR 22 UTC: the BTC ladder-MM is systematically ABSENT** (median ladder depth = 0 that hour;
   15-18k all other hours), while takers stay active. The headline new finding -- a thin-competition
   window. Sign UNKNOWN: thin = easier queue (less competition) OR more adverse (no MM to absorb
   toxicity). Conflicts with our competition test (MM-dominated windows paired 96%). MUST measure our
   live markout/pairing in hour 22 vs others before acting -- can't sign a gate yet.
3. **Settlement-minute takers (SOL/XRP)**: 25% of trades in last 120s (vs 13% uniform), +40-56% size
   -- but it's the known size-toxicity population concentrated at expiry, not a new actor. Moot for
   us (we trade BTC, where it's BELOW baseline at 11%).
NOISE (not distinct actors): cadence slow-quoters (1.6%, too sparse), block quotes (structural far-OTM
ladder rungs of the same MM), ladder geometry (density-weighted but reactive not predictive).
**Net: the book is ONE dominant mechanical MM + retail + the occasional informed taker (size-19
class). No new copyable/exploitable participant. The two forward-MEASURE candidates are hour-22 and
the cross-asset risk-off gate; everything else is the toxicity thesis we already gate on (t32).**

## Informed-flow detectors that BEAT VPIN-alone (2026-06-12, informed_detectors.py)
The "more ways to find informed flow" dive. Built 9 causal pre-k detectors and tested whether each
ADDS predictive power over the VPIN incumbent for the toxic-window label (settle-loss), IS/OOS split.
- **VPIN-alone OOS AUC = 0.619.** Detectors that add (OOS AUC of VPIN+detector):
  `take_n` +0.080 → 0.699 (more pre-k takes = informed pressure); `d1_maxrun` +0.064 → 0.683
  (longest one-directional aggressor run = persistent informed); `d2_lambda` (Kyle price-impact)
  +0.052 → 0.671; `d1_nruns` +0.036 (few runs = persistent); `d4_roundfrac` +0.032 (algo size
  footprint); `d5_sweep` +0.018 (urgency sweeps). `d3_burst_cv`, `d4_topsize_rep` add ~0.
- **BEST COMBINED: VPIN + all detectors OOS AUC = 0.700 (gain +0.081 over VPIN-alone).** At equal
  keep fraction the combined score cuts the stranded-leg rate to **0.179 vs VPIN-alone 0.254**
  (frozen-fit OOS, freeze_combo_tox.py over 3,383 windows) — a materially better OPEN gate than the
  VPIN-only t32. → wired as **t35_combo_tox_gate** (frozen logistic, coefficients distilled from this
  fit, NOT tuned forward; THRESH=0.366 matches t32's keep fraction).
- **What actually drives the lift (honest joint-fit reading):** in the 7-feature logistic the
  DOMINANT term is `take_n` with a NEGATIVE coefficient (−0.93 std) — i.e. LOW window trade-volume
  (thin/illiquid windows) is what strands legs; VPIN (+0.14) and Kyle's λ `d2_lambda` (+0.18) are
  secondary positive toxicity signals. The univariate AUC adds from the persistence detectors
  (`d1_maxrun`/`d1_nruns`) are largely COLLINEAR with take_n and shrink to ~0 in the joint fit, so
  do NOT read the gate as an "aggressor-persistence" detector — it is mostly a thin-window/volume
  gate with a VPIN+λ tilt. Mechanism check: a thin window with one informed take strands the far leg;
  a high-volume window pairs. This is consistent with the older thin-book completion work (t04).

## Toxicity PERSISTENCE (2026-06-12, box_tox_persist.py) — regime is real but weakly tradable
- VPIN is **autocorrelated**: lag-1 r=+0.341 (t=15.4), persists to lag-5 → toxicity comes in regimes,
  not i.i.d. P(toxic | prev window toxic) = 0.323 vs 0.247 base (1.30× lift).
- BUT strand outcomes themselves do NOT autocorrelate (~0), and worst-hour ranking is unstable
  (spearman +0.10 across halves) — so a static hour gate isn't justified.
- Session gate "skip M windows after a toxic strand" (optimal M=8): OOS kept pnl/win −0.045 vs
  skipped −0.116 (t=+2.06) but skips 56% of volume. Marginal — MEASURE forward, don't deploy.
  The persistent-regime fact is better exploited by the live per-window combo gate (t35) than by a
  blunt cool-down.
