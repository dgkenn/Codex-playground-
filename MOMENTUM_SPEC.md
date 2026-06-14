# Cross-sectional crypto momentum — LOCKED best-version spec (2026-06-14)

Synthesis of the full research program (/goal: "keep researching until sure of the best version").
Six independent agents, each held to the same brutal bar: IS-only param choice, recent 12–18mo HARD
holdout, recent-regime numbers, deployable-liquid universe, plateau-not-spike, realistic costs.
Backtests SCREEN (daily OHLCV, survivorship-biased UP); nothing is live until the paper bar below clears.

Source docs: MOM_SIGNAL.md (signal) · MOM_REGIME.md (regime gate) · MOM_EXECUTION.md (cadence/cost/
capacity) · MOM_MULTIFACTOR.md (single- vs multi-factor) · CRYPTO_MOMENTUM.md + MOMENTUM_DEPLOY.md
(origin + de-risk). Commits: eaa9641, 22517b5, 83717c0, 55244b4, a8e79a4, e189a1c.

---

## THE LOCKED SPEC

| Component | Locked choice | Why (and what lost) |
|---|---|---|
| **Signal** | **Risk-adjusted ~10d momentum** = trailing 10d return / trailing 10d vol | Plain-14d is fragile (recent ~0.1–0.3); risk-adjusting + shortening to 8–13d is a robust PLATEAU. Skip-recent, multi-lookback ensembles, beta-stripped residual momentum all FAILED OOS. |
| **Universe** | **Top-15 liquid USDT perps** | >15 dilutes into thin alts; <BTC/ETH excluded fails. 15 is the liquidity/breadth knee. |
| **Construction** | Rank cross-sectionally, **equal-weight**, **dollar-neutral**, long top-30% / short bottom-30% | Signal-proportional & inverse-vol weighting FAILED. Rank/equal is the robust winner. |
| **Rebalance** | **WEEKLY** | Decisive. Daily is cost-dead (gross 1.15→net 0.20); 2×/wk goes negative on independent windows; biweekly/monthly lose the 10d signal to decay. |
| **Turnover control** | **Partial-rebalance 0.7** (move 70% toward target) | Turnover 2.43→1.74 (−28%) while *raising* the robust independent-window Sharpe (PREV12 1.37→1.61). |
| **Regime gate** | **Run the book only when BTC ≥ its 50–100d MA** (+ optional: 10d cross-sectional dispersion ≥ rolling 20th pctile) | Momentum's conditional Sharpe is **−0.30/−0.42 below the MA vs +1.80/+1.87 above** — the gate skips a genuinely dead regime, not random weeks. Plateau across MA length & threshold; beats 94% of random equal-exposure gates. |
| **Execution** | Plan as **TAKER** (passive-first-then-chase shaves only ~1–3 bps) | Adverse selection + non-fill force taker at weekly cadence; maker is not a capacity unlock. |
| **Factors** | **Momentum ONLY** | Carry (OOS −0.70), low-vol (−0.16), size (−0.10), long-horizon reversal (+0.25) all fail/too-weak OOS. Near-orthogonal but ~0-return → blending only DILUTES the one edge. The data's own inverse-vol blend collapses to 100% momentum. |

---

## HONEST PERFORMANCE EXPECTATION

The headline numbers spread by universe/window; reconciled, the **deployable forward expectation is
Sharpe ~1.0 (range ~0.6–1.5)**, NOT the 2.0 that the best single recent window showed:

- Signal agent: risk-adjusted 10d / top-15 → recent-12mo OOS ~2.0 (flagged: lucky window + survivorship-biased UP).
- Execution agent: every turnover smoother LOWERS the rich REC12 (~2.0) but RAISES the independent PREV12
  (1.37→1.61) → forward ~1.0–1.5 is the honest read, not 2.0.
- Multi-factor agent: plain-14d OOS 1.17, **recent-18mo 0.85** (decay is real but still leads everything).
- De-risk agent: plain-return 6-coin → 0.3–0.6 (narrower/weaker variant; the risk-adjusted top-15 recovers most of this gap).

**With the BTC-trend regime gate:** Sharpe +0.1–0.2, and — the real prize — **OOS maxDD −31% → −13/−15%**
(full-sample −57% → −35%). It roughly HALVES the crowding drawdown, at the cost of sitting ~30–50% in cash.

**Crowding is the live risk.** Partial-2026 went negative for every ungated config — the regime gate is
the primary defense, but the edge is decaying and must be monitored, not assumed.

---

## CAPACITY & COST (the binding deployment constraint)

- **Real cost ≈ 23 bps round-trip at small size**, NOT the 7–12 bps assumed — equal-dollar weighting forces
  equal size into THIN alts (TON ~20 bps @ $100k; NEAR/FIL/ADA 7–11 bps; BTC/ETH <1 bp). Thin alts set the price.
- **Capacity:** net Sharpe **halves at ~$3.4M** AUM, **zero at ~$6M** (raw); partial-0.7 extends to
  **halve@$4.5M, zero@$7.8M**. Two independent methods (live order-book walk + historical) agree on **$3–6M**.
- **Deployable size: $1–3M, hard cap ~$5M.** Binding coins are the thin alts (TON/NEAR/FIL/XLM/ADA/BCH), not BTC/ETH.

**Implication for THIS project:** momentum is a *real-capital* strategy ($1–3M to matter). It is NOT runnable
on the live Kalshi bot's $10–100 bankroll. It is a separate, larger-capital opportunity — worth standing up a
paper test now, but it does not compete with or replace the Kalshi box at current bankroll.

---

## GO-LIVE BAR (do not deploy real capital before this clears)

1. **Paper-trade 3–6 months** at weekly cadence on the locked spec (risk-adjusted 10d, top-15, equal/dollar-neutral,
   partial-0.7, BTC-trend gate), booking realistic 23 bps taker cost and funding paid/earned.
2. **Rolling out-of-sample Sharpe ≥ 0.5** sustained over the paper window (not a single rich month).
3. **Crowding watch:** if the regime-gated book is net-negative over any rolling 8-week window, halve size; two
   consecutive negative quarters → stand down (the decay thesis won).
4. **Capacity discipline:** cap AUM at $3M initially; the thin-alt slippage is the first thing that breaks at scale.

---

## WHAT WAS REJECTED (so we don't relitigate)

- Multi-factor blends (carry/low-vol/size/reversal) — none pays OOS; combining overfits.
- Plain (non-risk-adjusted) 14d momentum — fragile in the recent regime.
- Skip-recent, multi-lookback ensembles, residual/beta-stripped momentum, signal-proportional & inverse-vol weighting.
- Daily / 2×-week / biweekly / monthly rebalance — weekly is the cost/decay optimum.
- Own-equity "turn off after a losing streak" timing — FAILS (momentum rebounds after its own drawdowns).
- Maker execution as a capacity unlock — marginal (~1–3 bps).
- Funding-stress regime filter — UNTESTABLE on non-geo-blocked venues (OKX funding history only ~94 days).

## VERDICT
The best version of cross-sectional crypto momentum is a **single-factor, risk-adjusted ~10d, top-15-perp,
equal-weight dollar-neutral, weekly, partial-0.7 book gated to BTC-uptrend regimes**, forward Sharpe ~1.0
(maxDD ~13–15% gated), capacity $1–3M, ~23 bps cost. It is a real-capital strategy gated behind a 3–6mo
paper bar — distinct from the live Kalshi box, which remains the product at current bankroll.
