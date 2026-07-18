# PMKT-SHORTVOL — Polymarket longshot short-volatility risk premium (FORWARD paper gate)

**Status:** PROPOSE-ONLY. Paper only. NO orders, NO capital, no live flag/switch/size ever touched.
This document PRE-REGISTERS a frozen rule and gate so the forward paper record is an honest test of the
charter gate: *tested performance must match live.* Nothing below is retuned after the clock starts.

## The edge
On zero-fee Polymarket, **SELLING far-OTM weekly "Will BTC/ETH be above $X on `<date>`?" longshots**
earns a short-volatility / lottery risk premium. Backtest evidence (7000 settled markets, 50 weeks):

- The robust entry band is **YES price in [0.15, 0.30]**. It survives conservative volume-weighting
  (**week-clustered t = 2.26**) and calibration is solid: band longshots **settle YES ~10.5%** while
  priced **~22%** — a persistent overpricing the seller harvests.
- This is a **RISK PREMIUM, not arbitrage.** A Deribit cross-market (options-implied) check was null,
  so there is no hedge/lock — you are paid to *bear* tail risk, not to arb it away.
- **Real tail risk:** worst backtest week was **-0.43 / contract**, and **~25% of weeks were negative.**
  Therefore the harness tracks TAIL metrics (per-week PnL, worst-week, max drawdown), not just the mean,
  and sizing must be **fractional and capital-bounded** — never let uncapped sizing drive the headline.

## Frozen rule (DO NOT retune)
- **Universe:** Polymarket weekly binary markets "Will BTC (or ETH) be above $X on `<date>`?" (terminal,
  ~7-day horizon). Weeklies are isolated with a **horizon filter of [4, 10] days** (start→resolution),
  which excludes the intraday ("…10AM ET") and 4h multistrike variants that share the same title stem.
- **Entry:** each run, for every OPEN such market still in the **FIRST HALF of its life**
  (`now <= start + 0.5*(start→resolution)`), if the YES **mid = (best_bid+best_ask)/2 ∈ [0.15, 0.30]**
  AND `best_bid > 0` AND not already held: record a paper **SELL of 1 YES unit** at the executable
  price = **best_bid** (conservative taker; Polymarket is zero-fee). Log the estimated **half-spread**
  `(best_ask-best_bid)/2` at entry.
- **Exit:** hold to **UMA resolution**. **PnL/unit = sell_price − outcome** (outcome = 1 if resolved YES,
  else 0). **Zero fee.**
- **Sizing overlays reported side by side:**
  - **Flat 1-unit** (the HEADLINE): equal-weight, one contract per qualifying market.
  - **Fractional-Kelly (0.10), capital-bounded:** per position, stake fraction
    `min(0.25, 0.10 · f*)` of bankroll where `f* = (1−q) − q·(1−s)/s`, `q = 0.105` (frozen backtest
    calibration), `s = sell_price`; total weekly stake capped at **25% of bankroll**; contracts =
    stake / (1−s). Reported only as an illustrative, capital-bounded overlay — it never drives the gate.

## Metrics tracked
Per-resolution-week PnL; **worst-week** (min weekly mean PnL/unit); **running max drawdown** of the flat
cumulative-PnL curve; **week-clustered t** (mean of per-week means ÷ (sd/√k)); win rate (a SELL wins when
the market settles NO); and the fractional-Kelly capital-bounded equity curve (final multiple + max DD).

## Gate (pre-registered)
- **PASS** = week-clustered **t ≥ 2** over **≥ 8 forward resolution-weeks** AND **mean PnL/unit > 0**
  AND **worst single-week mean PnL/unit ≥ −0.50/unit** (stated tail tolerance, ~ the −0.43 backtest worst
  week with margin).
- **KILL** = week-clustered **t < 0** after **≥ 8 forward weeks**.
- Otherwise **ACCRUING** (keep the clock running).

## Honest framing
This is a **tail-risk-bearing risk premium**, not a free lunch. Expected value is positive and calibration
was clean in-sample, but the payoff is negatively skewed: many small wins (markets settle NO) punctuated by
occasional full −(1−s) losses when the longshot prints. **Size fractionally and bound capital.** The forward
gate must reproduce the backtest's mean AND keep the worst week inside tolerance before any sizing is
discussed — and even a PASS is only a license to paper-size fractionally, never to deploy capital here.

## Files & usage
- `pmkt_shortvol_paper.py` — subcommands `snapshot | settle | report` (no arg = all three).
- `pmkt_shortvol_positions.jsonl` — open paper SELLs (idempotent, keyed on market id).
- `pmkt_shortvol_settled.jsonl` — resolved positions with PnL (idempotent, keyed on market id).

## Data sources (Polymarket public, no auth)
- `gamma-api.polymarket.com/public-search?q=bitcoin above&events_status=active` → active "above" events.
- `gamma-api.polymarket.com/events?slug=…` → fresh per-market `bestBid/bestAsk`, `startDate/endDate`,
  `clobTokenIds`, `question/slug`.
- `gamma-api.polymarket.com/markets/{id}` → settlement: `closed`, `umaResolutionStatus == "resolved"`,
  `outcomePrices` (`["1","0"]` = YES won, `["0","1"]` = NO won).
- `clob.polymarket.com/book?token_id=…` available as a book fallback if gamma bid/ask is missing.

## MATURATION (2026-07-18) — fee regime, maker-only execution, rebate

The edge-hunt campaign (DECISION_MAP nodes W1-a..W3-b) validated and hardened this sleeve:
- **Fee regime changed:** Polymarket crypto markets now carry `crypto_fees_v2` = `{rate 0.07, takerOnly, rebateRate 0.2}`.
  The frozen paper rule fills at the BID (a *taker*), which under this regime now costs `0.07·p(1−p)` (~1.2¢/ct ≈ **−11% of the edge**).
- **LIVE EXECUTION RULE — MAKER-ONLY, NEVER CROSS THE SPREAD.** Resting as a maker pays no fee and earns the 0.2
  rebate (`0.014·p(1−p)` ≈ +0.24¢/ct ≈ **+2%**). The paper harness now records `pnl_taker_net` (pessimistic, if crossing)
  and `pnl_maker_net` (intended live, resting + rebate) alongside the frozen `pnl`; the report prints both brackets.
- **Entry rule UNCHANGED** (charter: do not retune) — only the accounting/reporting matured.
- **Selection does NOT help:** strike sub-band, entry-timing, moneyness, and vol-regime conditioning are all NULL
  (~60 cumulative conditioning tests). **Trade the blanket [0.15,0.30] band unconditionally.**
- **Diversification map:** this is a crypto-BETA bet; SOL/XRP are 0.6–0.8 correlated (capacity, not diversification).
  ECON is the only validated non-crypto diversifier (corr −0.05, small). No larger uncorrelated sleeve exists in public data.
- **Durability:** the premium is a *participant* effect (Polymarket retail overpaying the wing); it does not exist on
  Kalshi (pros arb it to calibration). It persists as long as Polymarket retail lottery-flow does — monitor the forward
  calibration (band should keep settling YES ~10.5% vs ~22% priced) as the live health check.
