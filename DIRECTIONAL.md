# Directional edges in the 15-min markets — the systematic scan (`directional_scan.py`)

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
