# Literature review — unpaired-leg management for the Kalshi box-maker

Five-angle search of the academic + practitioner literature, each mapped to our setting and, where
possible, tested on our data. **The big picture: the academic work on Kalshi *specifically*
validates nearly everything we found empirically, and hands us three genuinely new techniques.**

## What the literature VALIDATES (independent confirmation of our findings)

| Our empirical finding | Literature confirmation |
|---|---|
| Passive box-making is ~break-even-to-positive | Kalshi makers earn **+1.12%**, takers −1.12% across 72M trades (Whelan, GWU WP 2026-001; Becker 2026). Making is positively-expected; the edge is being competed down by professional makers post-2024. |
| Cheap unpaired legs are toxic (sell them) | **Favorite-longshot bias**, quantified on Kalshi: 1¢ YES wins 0.43% (−57% mispriced), 5¢ wins 4.18% (−16%). Cheap legs carry lottery-buyer overpricing **and** the worst adverse selection. (Becker 2026.) Matches our calibration: 25¢→22%. |
| Unpaired YES toxic, unpaired NO favorable (we feared period-specific) | **STRUCTURAL, not period-specific.** NO outperforms YES at 69/99 price levels; cheap-YES is where lottery-seekers park. (Becker 2026.) This de-risks deploying t08_hold_no. |
| Late-window fills adverse (tau-guard) | Informed traders **cluster in the final minutes** to maximize private-info value (arXiv:2509.14645); binary gamma ∝ 1/√T explodes near expiry. Optimal quoting window is minutes 3–12. |
| BTC15M single-name, real adverse selection | Single-name markets have far higher informed price impact than broad-based; behavioral subsidy (longshot bias) is what keeps making positive (Bartlett & O'Hara, Stanford 2026). |

## NEW techniques — ranked by value, with our test results

### 1. ⭐ Delta-hedge the unpaired leg with a BTC perp (TESTED — eliminates the loss)
Legging-risk literature (Talos multi-leg algos; ETF AP basis books; Kalshi institutional desks): when
one leg fills and the other won't, **hedge the directional exposure with a correlated instrument**
rather than sell or hold. We tested it on 580 unpaired legs using the BTC spot path:

| BTC hedge size | mean ¢/leg | t |
|---|---|---|
| none (hold) | −3.31 | −3.4 |
| **delta-neutral (h≈100)** | **−0.05** | −0.1 |
| over-hedged (h=200) | +3.21 | +2.8 |

The delta-neutral hedge **removes the −3.3¢/leg bleed** — the unpaired leg, which is the *entire*
risk of the strategy, becomes ~flat. (Over-hedging turns positive because stranded legs predict
continued BTC moves — a real but *directional, higher-variance* momentum bet, not the conservative
hedge.) Kalshi launched **BTCPERP** (June 2026), so this could be on-venue.
**Cost/caveats:** needs perp trading infra + funding/fees; hedge ratio (binary delta) must be
calibrated and re-hedged near expiry (gamma); in-sample. **This is the highest-value next build.**
Rule: on YES fill, short `P_YES · notional / BTC_price` of BTC perp; unwind on completion or settle.

### 2. ⭐ VPIN / toxicity-conditioned exit (resolves the stop-loss question)
Our plain stop-loss lost because most fills are noise that mean-reverts. The liquidation/stopping
literature (Easley–López de Prado–O'Hara VPIN; Cartea–Jaimungal signal-conditioned execution;
Lou–Wang) says a stop is +EV **only for the informed subset** — and VPIN (volume-bucket order-flow
toxicity) detects it in real time. Rule: **sell the unpaired leg only when the fill's toxicity
signal was high** (informed → move continues → cut it); hold otherwise (noise → reverts → keep it).
Wired as a trial (`t13_sell_unpaired_toxic`) using our flow/spot-signal toxicity proxy; under
prospective test. The proper version computes VPIN on a volume clock — a feature to add.

### 3. Avellaneda-Stoikov inventory lean (quote-skew toward completion)
After an unpaired fill, don't rest the completing leg at the touch — **skew both quotes** toward
flattening by `q · γ · σ² · (T−t)`. For a binary, use belief variance `σ² = p(1−p)` so the lean
naturally stays strong on genuine coin-flips near expiry and fades on decided markets. Lowers the
completing-leg price (fills faster) and the same-side re-entry (discourages piling on). The
counterintuitive theory result: the lean *shrinks* with time-to-expiry, it does **not** ramp up.
Testable as a quote-skew in the live bot.

### 4. Completion-probability MODEL (upgrade t09 from heuristic to fitted)
Fill-probability literature (Huang–Lehalle–Rosenbaum queue-reactive; Stoikov microprice; "Negative
Drift of a Limit Order Fill"; "Market Maker's Dilemma"). Fit a logistic/GBM on the label "did the
box pair?" using features we don't yet use:
- **absolute near-queue AND opposite-queue size separately** (not just imbalance/ratio — R²=0.95 from these)
- **cancellation rate at best bid/ask** (queue instability → imminent reprice)
- **vol-normalized distance** `δ / σ_30s`
- **multi-timescale OFI** (fast-vs-slow OFI divergence = reversal)
- **opposite-leg queue asymmetry** (YES rank-1 but NO rank-50 → box won't complete)
All observable at quote time; the collector already captures depth/flow, so most are addable.

### 5. Hard-leg-first ordering & price/time chase budget (legging discipline)
- **Quote the harder-to-fill leg first** (thinner book / wider spread), then the easy leg — "make the
  hard trade first." Wrong ordering costs 12–50 bps (Talos). For us: snapshot YES vs NO books, post
  the thinner side first.
- **Pre-committed chase budget**: if the completing leg's price worsens past a threshold (Pariflow's
  0.5¢; Talos 30–60s passive then 2–5 bps payup), stop chasing. We already do completion-floored.

### 6. Reduce size near expiry (gamma) + NO-leg preference + YES+NO deviation entry
- Binary gamma ∝ 1/√T → scale resting size by `√(T_remaining/T_initial)` in the final minutes.
- The NO side is structurally cleaner (no lottery-buyers) — lean toward making NO.
- Only engage when `1 − (yes_bid + no_bid)` exceeds the cost floor (a live entry gate).

## What to do next (priority order)
1. **Prototype the BTC-perp hedge** of unpaired legs — biggest, cleanest EV/risk win (removes the
   −3.3¢/leg loss). Needs a perp execution module; validate forward before sizing.
2. **t13_sell_unpaired_toxic** accumulating in the prospective tester (done).
3. **Completion-probability model** — fit on the accumulating live book-stream data; replace the
   t09 heuristic. The features are being collected now.
4. **A-S inventory lean** — add as a live quote-skew once the perp hedge is in (they compose).

## Sources (selected)
Avellaneda & Stoikov 2008; Guéant-Lehalle-Fernandez-Tapia 2011 (arXiv:1105.3115); Cartea-Jaimungal-
Penalva 2015; Fodra-Labadie 2012 (arXiv:1206.4810); "Toward Black-Scholes for Prediction Markets"
2025 (arXiv:2510.15205); Almgren-Chriss 2001; Cartea-Donnelly-Jaimungal 2015 (SSRN 2668277);
Lou-Wang 2015 (arXiv:1411.5062); Easley-López de Prado-O'Hara 2012 (VPIN, SSRN 1695596); Huang-
Lehalle-Rosenbaum 2015 (arXiv:1312.0563); Stoikov 2018 micro-price (SSRN 2970694); "Negative Drift
of a Limit Order Fill" 2024 (arXiv:2407.16527); "Market Maker's Dilemma" 2025 (arXiv:2502.18625);
Whelan/GWU "Makers and Takers" WP 2026-001; Becker 2026 (jbecker.dev); Bartlett & O'Hara, Stanford
2026 (SSRN 6615739); Talos multi-leg algos; Pariflow prediction-market arbitrage guide; arXiv:
2509.14645 (last-minute parimutuel dynamics).
