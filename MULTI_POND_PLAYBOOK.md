# Multi-pond trading operation — the operator playbook (2026-06-21)

The single source of truth. Goal: a multi-strategy bot harvesting SEVERAL small uncontested "ponds"
(alpha) + a scalable risk-premium portfolio (backbone), targeting ~$500/mo long-term.

## The thesis (why this shape)
- **Law (proven across options/sports/CFTC venues/15m): uncontested <=> small.** The liquidity-provider
  premium is real everywhere but accrues to whoever holds the seat; every SCALABLE pool has a pro in it
  (PFOF wholesalers, SIG, co-lo MMs). We can only hold the seat where the pool is too small for a pro.
- So: **alpha = a handful of small uncontested ponds** (each ~$30-150/mo, high Sharpe); **scale = risk
  premia** (the portfolio, which pays everyone who bears risk -- no seat to win). Don't hunt for a
  scalable-uncontested-maker edge; it's structurally near-impossible (`LIQUIDITY_PROVIDER_MAP.md`).

## Honest $500/mo arithmetic
| Source | Realistic recurring | Notes |
|---|---|---|
| Pond 1: Kalshi soft-longshot | $30-150/mo | built/optimized/audited; flow-capped |
| Pond 2: Polymarket-US QCEX | **$0 -- NOT viable** | DEAD: gated maker API + MA-excluded (operator's state) AND edge null/wrong-signed on the soft tail (`QCEX_PORTABILITY.md`) |
| Promo extraction | lumpy $1-5k one-time + re-ups | `SPORTS_PROMO_EV.md` |
| Portfolio (backbone) | scales with bankroll | the path to the bulk of $500 as capital compounds |
- **HONEST RECKONING (2026-06-21, after exhaustive pond search):** there is exactly ONE deployable
  uncontested pond -- Kalshi soft-longshot (~$30-150/mo). Every other candidate is pro-contested (options
  via PFOF / sports exchanges / all 2026 CFTC venues), too fast (15m), or inaccessible to a MA-based US
  retail trader (QCEX = gated API + MA-excluded + edge doesn't port). **The 'several ponds summing to $500'
  vision is sound in theory but the ponds don't exist accessibly.** So: the longshot pond is a real
  high-Sharpe SUPPLEMENT (~$30-150/mo), and **the $500/mo engine is the PORTFOLIO** (risk premia +
  contributions + compounding toward ~$70k), NOT pond-aggregation. Don't keep hunting ponds -- confirmed empty.

## Architecture: one core engine + thin per-venue adapters
Core (venue-agnostic, built in `kalshi_longshot_bot.py`): scan overpriced longshots -> flow-toxicity gates
(take-tail-trim + one-sided-flow, `KALSHI_LONGSHOT_ABXFER.md`) -> fractional-Kelly sizing across uncorrelated
themes (`KALSHI_LONGSHOT_SIZING.md`) -> decision audit -> settle/reconcile. Per-pond adapter maps a venue's
API to scan->quote->fill->settle. Adding a pond = ~100-line adapter, not a new strategy.

## ===== POND 1: KALSHI SOFT-LONGSHOT (deploy now) =====
Edge: sell overpriced YES longshots (maker NO) p in [0.05,0.15) on zero-maker-fee soft series; net +5.45c/ctr
event-clustered (`KALSHI_LONGSHOT_OPTIMAL.md`). Optimized config baked into `kalshi_longshot_bot.py`.
**Deploy sequence:**
1. Keys: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH` (Kalshi Settings -> API).
2. **Always dry-run first:** `LONGSHOT_LIVE=0 python kalshi_longshot_bot.py` -- read what it WOULD place +
   the audit JSONL. Reconcile with `python kalshi_longshot_audit.py longshot_audit.jsonl`.
3. **$10 plumbing test (go live tiny):** `LONGSHOT_LIVE=1 LONGSHOT_CLIP=1`. Purpose: confirm auth/place/fill/
   settle work AND the audit log matches reality. NOT for income (~$1/mo at $10, variance-dominated).
4. **GO-LIVE GATE (the Becker arbiter):** scale real money ONLY after the forward paper-track + audit show
   realized sell-YES edge POSITIVE, event-clustered, and MATCHING the +5.45c backtest (if a pro MM is our
   counterparty, fills will be adverse and won't match -> stop). `longshot_settled.csv` needs weeks to fill.
5. **Sizing (max Sharpe):** tiny equal clips; MAX_THEME=3 (breadth across uncorrelated themes = Sharpe lever);
   MAX_NOTIONAL ~= 25-50% of bankroll (fractional-Kelly for the negative-skew tail). Scale toward ~$300-500
   working capital = the pond's full ~$30-150/mo; beyond that it flatlines (flow-capped).
6. **Monitor:** Telegram alerts on every live run + remote on/off kill-switch (`LONGSHOT_SWITCH`,
   `telegram_control.py`); `kalshi_longshot_report.py` for realized edge/fills.

## ===== POND 2: POLYMARKET-US QCEX -- TESTED, NOT VIABLE =====
DEAD (`QCEX_PORTABILITY.md`): (1) maker API gated (no public API) + **not available in Massachusetts** (the
operator's state); (2) the edge does NOT port -- soft-tail sell-YES is null/wrong-signed (Polymarket users
are sharper; only sports replicates). Re-test ONLY if a public QCEX maker API opens AND MA is permitted AND
a fresh measurement on QCEX's own settled soft books shows the bias. Not a pond today.

## ===== BACKBONE: THE PORTFOLIO (deploy in parallel) =====
Trend-overlaid all-weather (SPY/TLT/GLD/BIL 25% each, 12m trend overlay, annual rebalance; ~6.8%/yr, -10% DD)
+ optional 20% trend-timed crypto barbell (~12.6%/yr, -21% DD). `allweather_live.py`, `START_HERE.md`,
`PROJECT_VERDICT.md`. This is the scalable engine: contribute + compound toward the ~$70k that throws off
$500/mo, while the ponds add high-Sharpe alpha on top. Paper-tracked weekly (etf-paper -> gha-data/paper/).

## Forward evidence now accruing (watch these)
- `gha-data:gha_data/longshot/` -- daily paper-track snapshots; `longshot_settled.csv` is THE go-live arbiter
  (empty until soft longshots resolve over the coming weeks).
- `gha-data:gha_data/paper/` -- weekly portfolio paper-tracks (conservative + growth).
- Decision audit (`longshot_audit.jsonl`) once live -- reconcile gates vs settlement with `kalshi_longshot_audit.py`.

## Do-now checklist
[ ] dry-run the Kalshi bot, eyeball decisions + audit
[ ] add Kalshi keys, run the $10 plumbing test, confirm audit==reality
[ ] set TELEGRAM_* for alerts + remote kill
[ ] open the portfolio (IRA), start contributions + the trend overlay
[ ] WAIT for longshot_settled.csv to confirm the edge forward, THEN scale pond 1 toward $300-500
[ ] integrate QCEX as pond 2 if the portability test passes
[ ] keep opportunistically hunting small uncontested ponds
