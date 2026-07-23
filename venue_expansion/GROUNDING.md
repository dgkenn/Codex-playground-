# VENUE EXPANSION HUNT — GROUNDING (read this first, 2026-07-23)

## Mission
Kalshi is measured-efficient against every strategy class this repo can run at GitHub-Actions
speed (37 tested strategies, all killed — see `ref/RESEARCH_LEDGER.md` §3 graveyard). The one
mechanism PROVEN to work (backtest +1.1c/ct, ~99.6% win) is the **mechanical weather lock**:
a sustained, margin-cleared temperature extreme confirms a settlement outcome before the
market fully reprices. The hunt now expands to OTHER venues and OTHER feeds, not new
mechanisms on Kalshi.

## What is already known about Polymarket (do NOT redo)
Three completed studies (`ref/pmkt_settlement_basis.md`, `ref/pmkt_gap_study.md`,
`ref/pmkt_final_verdict.md`) established, on the global venue's public Gamma/CLOB APIs:
- 51-city daily temperature bracket-ladders exist; 6-city basis-sound whitelist:
  Chicago KORD, London EGLC, Paris LFPB, São Paulo SBGR, Tokyo RJTT, Mexico City MMMX.
  (Denver/NYC/Miami excluded — settlement basis unsound; Hong Kong settles on HKO, unchecked.)
- Deployed-rule false-lock rate on whitelist: **0/745** (Wilson upper 0.513%) — Kalshi-grade.
- Loss-inclusive reweighted EV: **+0.43c/ct** (n=31 priced fires — thin, unproven, plausible).
- Taker fee = `shares * 0.05 * p * (1-p)`, taker-only, no per-cent round-up (verified from
  live `feeSchedule`). Cheaper than Kalshi's `ceil(7*p*(1-p))/100`.
- VERDICT: STILL-BLOCKED on **signal coverage** (26.4% pooled): hourly METAR (only free feed
  for the 5 non-US cities) under-reports the diurnal peak by ~1h of temperature change, and
  margin (1°F/0.5°C) eats a dead zone out of narrow brackets (2°F US / 1°C intl).
- Written GO-paths (`ref/pmkt_final_verdict.md` §5): (1) Chicago-only rerun on its TRUE
  1-minute ASOS feed (KORD is in IEM's 1-min network; fetcher already written in
  `ref/pmkt_gap_study.py`); (2) a genuinely finer free feed for the international cities
  from their national met agencies (never checked); (3) larger EV sample wherever coverage
  clears; (4) historical CLOB book snapshots (no public endpoint found as of 07-19).

## Non-negotiables (each has killed a real false positive — violating any = auto-refute)
1. Pre-register success bars BEFORE reading test data; never move goalposts.
2. Entry prices from the executable ask AT/AFTER signal time — never best-in-window, never mid.
   (For Polymarket, last-trade at/after signal + half live spread is the accepted proxy;
   label it as a proxy.)
3. Fee-inclusive EV at the crossing price. Kalshi: `ceil(7*p*(1-p))/100`. Polymarket weather:
   `0.05*p*(1-p)`, taker-only.
4. Lock/signal detection must NOT condition on the outcome or on market price ("ask>=98"
   as a signal is the answer leaking in).
5. Feed latency is part of the signal definition. IEM asos1min publishes 22–34h late
   (backtest-only feed — fine for measuring coverage, be explicit that live needs
   MADIS ~10min / Synoptic ~1–5min or the agency's own real-time cadence).
6. Day-clustered t-stats, Wilson CIs, strict fit/validation split where a parameter is
   tuned; Bonferroni across every spec the funnel tests.
7. A rising day visits many rungs: "currently-in-bracket" is wrong 93% of the time (measured).
   Only sustained margin-cleared extremes inside the settled bracket's qualifying sub-range
   count (the `sustained_extreme` / sustain-3 discipline in `ref/pmkt_final_verdict.py`).
8. Cache-then-delete politeness on free APIs; no hammering. Cache under
   `venue_expansion/cache/` (gitignored).
9. A dry/negative result is a valid, publishable answer. Report it plainly.

## Graveyard summary — dead mechanism classes (do NOT re-propose on any venue without a
   NEW structural reason the kill doesn't transfer)
- Maker/resting-bid capture (marketability flaw; adverse selection) — killed twice.
- Favorite-longshot fade/buy, taker AND maker — killed at universe scale.
- Stale last_price / long-tail passive spread / calibration fade — stale-print artifacts.
- Sharp-forecast-vs-market (weather point+ensemble, NFL vs Vegas+Elo) — markets price it.
- Latency race on crypto up/down — flat no-edge curve 1s–300s.
- Cross-venue lead-lag Kalshi↔Polymarket crypto — no reconcilable instruments.
- Event-expansion families (sports totals, earthquakes, commodities, FDA) — frequency/latency walls.

## Output conventions
- Every agent writes machine-readable results to `venue_expansion/out/<agent>.json` AND
  returns a compact structured summary. Scripts go in `venue_expansion/` (repo-committed,
  read-only studies; never touch live-path files).
- Live paths `kwx_runner.py`, `kwx_paper_gate.py`, `kalshi_exec.py` are off-limits (they
  live on another branch anyway — this branch is research-only).
- Legal/deployment note: global Polymarket remains geo-blocked to US persons (operator is
  likely US); Polymarket US (QCX) is the regulated product but weather-ladder listing there
  is UNVERIFIED. Studies here are measurement only; deployment is an operator decision.
  Flag, don't decide.
