# Directional edges in the 15-min markets — the systematic scans

## DEEP-HISTORY VERDICT (5,749 windows / 60 days — `fetch_history.py` + `directional_deep.py`)

Polymarket's public APIs retain ~240 days of these markets (predictable Gamma slugs + CLOB
`prices-history` at 1-minute fidelity + Coinbase 1m spot). At **5,749 BTC windows** (13× the
collector's n), with sign learned on the first 60% and confirmed on the last 40%:

**NO directional edge exists.** And the path to that answer is the most instructive part:

- The first run showed **12 apparent edges** (spot momentum / recent-spot move / model-market gap,
  test-t up to +8.9, "taker-viable"). All of it was a **60-second measurement artifact**: a 1m candle
  stamped `t` closes at `t+60`, so "spot at minute k" was up to a minute *fresher* than the mid —
  manufacturing "spot predicts the mid's error". With spot shifted one bar back (strictly stale vs
  the mid — conservative), every correlation collapses to ~0.00–0.03, nothing significant, all
  taker tiers negative. **The market absorbs spot information within one minute.**
- What remains inside that minute is the sub-minute book staleness the maker stack already knows:
  it is the *toxicity* the deployed gate dodges defensively, and the offensive version was already
  tested live-shaped and lost to fees (`lag_taker`, discontinued).
- **Favorite-longshot at scale:** max |z| 2.4 in one of ten bucket×time cells, sign not replicated
  across decision times, magnitude ~2¢ < costs. Rejected at n≈5,700.
- Serial (prev outcome/error), token momentum, |mid−0.5|, and UTC time-of-day seasonality: nothing,
  at every decision time.

This also retro-explains the collector-data near-miss below (`gap_model`, test-t≈1.9 at n=45): noise.
The small-n scan's promotion trigger is hereby resolved — **do not promote**; re-run only if the
market's structure visibly changes. The 15-minute markets are efficient after costs at every horizon
≥1 minute; **the only durable edge is the maker seat** (rebate + adverse-selection avoidance), now
established on two independent datasets and ~6,200 total windows.

---

# The collector-data scan (437 windows — `directional_scan.py`, superseded by the above)

**Question:** is there ANY data-backed directional edge (predicting the market's pricing error), or
is the only real edge the maker rebate + toxicity avoidance?

**Data:** every resolved tick window collected to date — 437 windows (135 BTC + ETH/SOL/XRP),
~1Hz mid+spot paths, June 7–10. **Method:** target = residual `res_up − mid(t)` (predicting the
*error*, not the outcome — the price already predicts the outcome); 8 decision-time features × 4
decision times; sign/threshold learned on the first 60% of windows ONLY, confirmed on the last 40%;
tradeability scored in three tiers (maker-skew fee-free / taker net of half-spread / taker net of
half-spread + fee). Bar to call something an edge: |t|≥2.5 train AND same-sign |t|≥2 test.

## Verdict: NO directional edge clears the bar (0 of 32 tests)

The 15-minute pricing is consistent with efficient-after-costs. The features tested: token momentum,
spot momentum (open + recent), realized vol, model-market gap, favorite-longshot shape, previous
window outcome and previous window error (serial). This RE-CONFIRMS the project's standing
conclusion on ~4× the data of the original rejection.

### Near-misses, honestly reported

1. **`gap_model` — late-window model-vs-market disagreement (BTC): the one candidate worth tracking.**
   `fair_up(S_t, S_0, σ_realized, τ) − mid` correlates POSITIVELY with the market's error at every
   decision time, growing late in the window (t_in=690s: corr +0.26 train → +0.31 test, test-t 1.9
   vs the 2.0 bar). Point estimates are cost-positive (+0.07–0.12/win even after taker fee), and the
   effect **survives the shared-mid-noise artifact control** (scoring against the mid 60s AFTER the
   signal: +0.06–0.07 net). Mechanism is plausible: the binary's fair value steepens near expiry
   while the book updates slowly — the same staleness the maker gate dodges, viewed from the taker
   side (the minutes-horizon cousin of the discontinued 2s `lag_taker`, which lost to fees at that
   horizon). **But test-half t ≈ 1.3–1.9 at n=34–45 windows: NOT significant.**
   **Promotion trigger:** re-run `directional_scan.py` when BTC windows ≥ ~400 (the rebuilt
   collector gathers ~3.4× faster, with per-asset spot so the test extends to alts); promote to a
   shadow taker variant only if the test-half t clears 2.5 with the same sign.
2. **15-min serial reversal** (`prev_out`): negative correlation at every decision time (previous
   window's winner tends to revert) but never significant (best train-t −2.1, test −1.6). Maker-skew
   payoff ~+0.03/win if real — too small to matter even then.
3. **Favorite-longshot, revisited:** at t=450s the classic shape appears (longshots over-resolve
   +0.05, favorites under-resolve −0.09, |z| up to 2.5) — but it does NOT replicate at t=810s in the
   same data. One time-slice alone = noise; the original rejection stands. Re-check at bigger n.

### Why this doesn't contradict the maker edge
The maker's profit is *not* directional: it's the rebate plus avoiding being on the wrong side of
the very staleness `gap_model` hints at. A taker needs the mispricing to exceed half-spread + fee
(~0.022 at p≈0.5); a maker harvests with neither cost. Every "near-miss" above, if it firms up,
deploys as a **ladder skew tilt** (maker expression, fee-free) long before it justifies taking.

Re-run anytime: `python directional_scan.py` (auto-includes all new collector data, both tick eras).
