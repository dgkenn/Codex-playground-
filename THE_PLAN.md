# The clear, statically-sound plan (honest — 2026-07-18)

Goal stated: ~10%/day while minimizing risk. This is the honest, evidence-based plan after full validation.

## What IS sound and deployable (the real deliverable)
**Kalshi temperature settlement-nowcast (K-WX)** — buy the ladder rung once the observed station temperature has
mechanically locked the daily high/low, before slow retail reprices. High + low, all ~20 cities, full 6-rung ladder.

- **Edge (validated):** deployable +0.207/ct in-sample (t=37); +0.15–0.17/ct at realistic 2–5 min feed latency.
- **Tail (validated, 6 years, all seasons):** 0.4% conditional loss with glitch+sustain3/margin1; winter not worse.
- **Feeds (validated):** free api.weather.gov + METAR agree with official CLI (METAR r=0.992), all bias the SAFE way.
- **Sizing (Monte-Carlo optimized):** quarter-Kelly × 5% per-fire cap × 17.5% per-city cap; ruin ≈ 0.
- **On $50: ~5%/day median in-sim** (optimistic — assumes backtest holds live; the paper gate confirms).
- **Capacity ceiling: ~$1–1.6k/week of profit** (thin books). This is a SMALL-CAPITAL edge.

### Growth path on a small stake (realistic)
$50 → compounding ~5%/day → approaches the ~$1–1.6k/week capacity ceiling in ~6–8 weeks → then FLAT (depth-capped).
So the honest trajectory is: fast % growth while tiny, plateauing at ~$1–1.6k/week of absolute profit.

### Go-live gates (all still required; nothing is live yet)
1. Paper gate (`kwx_forward.py`) shows live == tested (win ≈99.6%, EV ≈+0.20, n≥30). **Hard gate.**
2. $10 canary (1 ct/fire) ~1 week to shake out execution. 3. $50 full. 4. Scale on realized PnL to the ceiling.
Credentials already exist (inherited from the box strategy's env vars); `KWX_LIVE=1` is the deliberate switch.

## What is NOT soundly achievable (proven, not assumed)
**~10%/day on MEANINGFUL (5-figure+) capital.** Established early with `daily_return_frontier.py`: it needs ~49×
leverage → ~100% ruin. No sound path exists. Confirmed by exhausting the alternatives:
- Deep-book Kalshi categories (politics, sports, index brackets, crypto) are EFFICIENT — all tested NULL or calibrated.
  The lesson is structural: **depth and efficiency arrive together**; the edge lives in thin, ignored corners.
- Rain/snow nowcast: NULL (slow accumulation → market reprices before the lock is observable).
- No wind market exists; the weather nowcast family is exhausted at high+low temperature.
- ~25 other candidates killed across the program (longshot, structural arb, theta, new-listing, earnings, etc.).

## The realistic frontier (what "doing whatever it takes" actually yields)
This is a **portfolio-of-small-edges** business, not a 10%/day-on-big-capital machine:
1. Deploy K-WX at its capacity (~$1–1.6k/week), confirmed via the paper gate. High % on small capital, near-zero ruin.
2. Opportunistically add more SMALL orthogonal edges as found — accepting most hunts return NULL (Kalshi is efficient).
   Each new sleeve is small; several uncorrelated ones together raise aggregate throughput slowly.
3. The binding constraint on absolute daily $ is CAPACITY, not the edge. More $ requires MORE independent edges,
   each capacity-capped — there is no single lever that delivers 10%/day at scale without unacceptable ruin risk.

## Bottom line
A statically-sound plan for **~5%/day on a small stake (≈$50–500), ruin ≈ 0** exists, is fully built, and is one
paper-gate away from live. A statically-sound plan for **~10%/day on meaningful capital does NOT exist** — not for
lack of effort, but because it is mathematically inconsistent with minimizing risk. The honest recommendation:
deploy the small-capital edge now (after the paper gate), harvest its ~$1–1.6k/week, and keep hunting small
uncorrelated sleeves to stack — while treating "10%/day on large capital, low risk" as the impossibility it is.
