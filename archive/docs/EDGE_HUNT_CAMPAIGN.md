# Edge-Hunt Campaign — push the achievable frontier as high as real edges allow

**Reframed objective (2026-07-18):** the operator pushed back on stopping — correctly. Sustained *compounded*
10%/day is arithmetic-impossible (frontier docs), but the *height of the achievable frontier is not settled*:
11 killed candidates ≠ exhausted. This campaign relentlessly hunts edges that **raise the frontier** —
primarily by (a) **sharpening** the one confirmed edge or (b) **stacking** uncorrelated edges — using the
multi-year datasets (Binance Vision futures/metrics/funding, Deribit options/DVOL, Polymarket/Kalshi).

**Rules (non-negotiable):** every positive is independently recomputed before belief; walk-forward / clustered
t / multiple-testing haircuts; executable prices; nulls recorded honestly in `DECISION_MAP.md`; no fabrication;
PROPOSE-ONLY. Confirmed edges plug into `portfolio.py`/`sizing.py` and forward-gate before any sizing.

**Why "sharpen or stack" and not random ideas:** the frontier rises when Sharpe rises. Sharpen the confirmed
edge (higher edge/ct) or add uncorrelated sleeves (lower portfolio variance) — both lift return at fixed risk.
Random directional bets on efficient markets have repeatedly returned null; these waves target the mechanisms
most likely to actually move the number.

## Scoreboard

| # | Hypothesis | Raises frontier via | Status | Verdict |
|---|---|---|---|---|
| W1-a | Deribit implied density → sharpen weekly longshot strike selection | sharpen edge/ct | **DONE** | NULL — density=price (corr 0.9996); residual is flat +3c, no cross-strike ranking power |
| W1-b | Extend short-vol to more underlyings (SOL/XRP/DOGE…) | stack + frequency | **DONE** | NULL-of-benefit — only SOL/XRP exist & they're 0.6-0.8 corr w/ BTC/ETH (no diversification; +capacity only) |
| W1-c | Binance funding/basis/OI → weekly directional signal | stack (uncorrelated) | **DONE** | NULL — AUC 0.66 is regime-autocorr illusion (tradeable t=0.40, placebos confirm); priced |
| W1-d | VRP-regime timing → size up in high-premium weeks | sharpen (Sharpe via sizing) | **DONE** | NULL — regime timing lowers Sharpe; edge is unconditional (baseline re-confirmed t=4.27) |
| W2-a | Cross-category longshot premium (sports/politics/pop/sci) + corr | stack (non-crypto uncorrelated) | **DONE** | NULL-of-lift — no large non-crypto twin; best diversifier=ECON (uncorr -0.05 but small $3.5k/wk, nominal t=2.59) |
| W3-a | Kalshi-native longshot premium + structural arb (net of fees) | stack (separate venue) | **DONE** | NULL — no premium even gross (Kalshi well-calibrated); edge is Polymarket-retail-specific |
| W3-b | Maker-rebate + optimal-strike LIFT on the confirmed edge | capture more of real edge | **DONE** | rebate +0.24c/ct (~+2%, real, no min-size); strike selection NULL; rule: REST never cross (taker=-11%) |

## Confirmed so far (the baseline to beat)
- **Polymarket weekly BTC/ETH short-vol longshot premium**: +0.12/ct, week-clustered t~4.6, maker (survives
  new `crypto_fees_v2` taker-only fee). Sound frontier at ¼–1× leverage ≈ 0.3–1.1%/day, P(ruin)≈0.

## Killed (11, see DECISION_MAP): 
exo-momentum, OFI, book-depth, cross-venue convergence, wallet-copy, informed-flow, weather-info,
sportsbook-lines, parlay-tax, settlement-latency, logical-arb, daily-shortvol (freq lever), conditional-slice,
LP-rewards (real but latency-bound MM). 

## Next waves (queued if W1 lands anything or to keep breadth)
- W2: liquidation-cascade short-horizon reversal; on-chain/stablecoin-flow direction; Kalshi new-listing
  mispricing; cross-underlying dispersion (sell rich-vol, buy cheap-vol longshots).
- W3: whatever W1/W2 winners suggest (e.g. combine density + regime; multi-underlying stacked sizing).
- Iterate until marginal waves return only nulls (then the frontier height is empirically established).


## Interim synthesis (after 16+ candidates, 5 this round all null)
The accessible public-data edge universe is now firmly mapped: **crypto short-vol (engine, +0.12/ct) + ECON
(uncorrelated diversifier, small ~$3.5k/wk, nominal) + biz (marginal)**. Ruled out with discipline: options-density
sharpening, vol-regime timing, cross-crypto stacking (correlated), 8 non-crypto categories (only ECON survives),
funding/basis/OI direction (autocorr illusion), daily frequency, LP-reward farming. No directional signal, no
sharpening, no LARGE uncorrelated diversifier exists in the public data. Wave 3 tests the last two real levers
(a separate venue = Kalshi; capturing MORE of the confirmed edge via rebate/strike). After wave 3, the honest
highest-value work shifts from NEW-edge discovery to (a) maturing the live forward gates and (b) maximizing capture
of the confirmed edge — the frontier height (~0.3-1%/day sound) is empirically established, not assumed.
