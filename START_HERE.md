# START HERE — the operator's playbook (2026-06-14)

The one followable guide. Distills ~37 research studies into what to actually DO. Full evidence trail
+ the graveyard is in PROJECT_VERDICT.md; the runnable tools are listed at the bottom.

## THE ONE-LINE ANSWER
There is no high-return-on-small-capital trading edge here (we proved it exhaustively). The genuine,
deployable answer is a **simple, robust, US-legal, tax-efficient portfolio** that you GROW with monthly
contributions. $500/month is a ~$70k-bankroll outcome, reached in ~6-7 years from $5k + $500/mo — it is
a savings-and-compounding goal, not a strategy goal.

## WHAT TO DO (pick your effort/risk tier)

### Tier 0 — Lazy (zero effort, near-best risk-adjusted)
Hold a **Permanent Portfolio: 25% each SPY / TLT / GLD / cash(BIL)**. Rebalance **once a year**.
Sharpe ~1.0, maxDD ~-18%. That's it. Most people should do this and stop.

### Tier 1 — Best risk-adjusted (light monthly effort) ★ RECOMMENDED CORE
**Trend-overlaid all-weather:** the Permanent Portfolio base, but each sleeve (SPY/TLT/GLD) is held only
when it's above its ~12-month trend (price > 12m moving average); if a sleeve is below trend, that slice
goes to **cash (BIL)**. **Rebalance annually** (the trend check can be monthly; the weight-rebalance is
annual — this lifted Sharpe 0.94->1.17 and cut turnover ~75%). Sharpe ~1.4 long-history, maxDD ~-8 to -10%,
robust through 2008 / 2022 / the 1970s. US-legal, IRA-able (no tax drag), fractional-share-deployable from
~$500. Run `python allweather_live.py` for this month's exact targets.

### Tier 2 — Growth engine (medium risk, for a SMALL account compounding up)
`python allweather_live.py --growth`. Overweights the trend-gated equity/momentum sleeves + a small
trend-timed crypto slice, less bonds. ~13-17%/yr, maxDD -30 to -40% (medium risk). Use this to GROW a
small account (do NOT withdraw); switch to Tier 1 once you hit the income base.

### Tier 3 — High-risk, data-informed asymmetric upside (the smart "swing")
A **CONVEX BARBELL**: ~70-80% Tier-1/Tier-2 base + **20-30% trend-timed CRYPTO BASKET** (BTC+ETH+SOL,
each held only above its 200-day SMA, else cash; via IBIT/ETHA spot ETFs in an IRA). The crypto slice is
the rare positive-skew AND +EV object — it gives disproportionate upside (on the slice: 5yr P(2x)=46%,
P(5x)=23%) while the safe base + contributions keep P(total ruin)≈0. Blend: CAGR ~12.6%, maxDD ~-21%.
**Two hard rules from the data:** (1) NEVER lever crypto (the trend gate can't cap its left tail — 2x/3x
= -93%/-99% DD; diversify the basket instead). (2) Lever the BASE only modestly (1.25-1.5x) and only if
NOT contributing — contributions move the timeline far more than leverage does.

## THE $500/MONTH PLAN (the honest path)
1. Open a **commission-free brokerage with FRACTIONAL shares** (Fidelity / Schwab / Robinhood / M1).
   Use an **IRA** for tax-efficiency where possible (crypto via IBIT/ETHA).
2. Deploy Tier 2 (growth) with your starting capital. **Do not withdraw.**
3. **Contribute every month** — this is the dominant lever, far more than the trading edge.
4. Rebalance annually; run `allweather_live.py` to get targets; place the trades; done.
5. At ~$70k, switch to Tier 1 (conservative) and draw ~$500/mo (~10%/yr, sustainable).
Timeline: from $5k + $500/mo at ~10-13% → **median ~6-7 years** to the $70k base (`growth_planner.py`).
Faster only via bigger contributions (the math: +$1k/mo from $10k ≈ 4 yrs; +$2k/mo ≈ 2 yrs).

## THE GRAVEYARD (proven dead — do not relitigate)
- **Kalshi 15-min crypto box** — structurally last-in-queue behind a co-located 1.2s market-maker; strand
  can't reach the 4.4% break-even from cloud infra. RETIRED (LIVE_SWITCH off).
- **Kalshi weather** — the warm-tail "edge" was MODEL ERROR (the calibrated model only works for the
  center, which Kalshi prices efficiently; the tail it can't call). No edge.
- **Fair-value taker / sports / Kalshi macro** — markets efficient or access-gated (books ban winners;
  Kalshi liquid = sharp-priced).
- **Stocks predicting bitcoin** — null; BTC leads its proxies, no equity->BTC timing edge.
- **Standalone crypto momentum** — loses to just holding BTC ~62% of paths; crypto belongs only as the
  gated trend-timed slice above.
- **Funding carry / stat-arb / ETH-SOL-XRP boxes / multi-factor / calendar anomalies / VRP / individual-
  stock momentum / global diversification / leverage-the-base** — each tested, none earns its place.
- **The meta-lesson:** every high-return-on-small-capital edge is dead, access-walled, or capacity-capped.
  Deployable edges are systematic RISK-PREMIA (low %, need a big base), not speed/mispricing plays.

## THE TOOLS (on this branch)
- `allweather_live.py [--growth] [--capital N]` — this month's exact target allocation (the thing you run).
- `growth_planner.py` — your personal years-to-$70k timeline for a given start + monthly contribution.
- `PROJECT_VERDICT.md` — the full evidence + every study's verdict.
- Forward paper-tracks accruing automatically (GitHub Actions, no action needed):
  `etf-paper.yml` (the recommended portfolio's live forward record) and `kalshi-weather.yml` (a cheap
  final null-check on weather). Pull: `git fetch origin gha-data && git checkout origin/gha-data -- gha_data/`.

## GO-LIVE DISCIPLINE
Before real money on any active tier: let the paper-track run ~3-6 months and confirm the live forward
Sharpe is in range (>=0.6-0.7). Size the convex crypto slice so a -50% slice loss is a tolerable % of net
worth (~20-30% of the book). The base + contributions are what get you there; the rest is patience.
