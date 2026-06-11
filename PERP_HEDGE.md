# BTCPERP hedge — feasibility scoping

**Verdict: the API works and our credentials authenticate, but the minimum perp contract is
~10–1000× too large to hedge a 1-contract binary leg. The perp hedge is a tool for a much larger
book, not for a $11–100 account trading 1 contract at a time. Shelved until scale justifies it.**

## What's confirmed (all tested live against the real API)
- **API + auth: YES.** Kalshi perps live at `https://external-api.kalshi.com/trade-api/v2` (demo:
  `external-api.demo.kalshi.co`). Same RSA-key signing as our binary bot — our existing key
  authenticated cleanly (`/margin/markets` returned 200). Full surface: `/margin/markets[/orderbook]`,
  `/margin/orders` (+amend/decrease/cancel), `/margin/positions`, `/margin/balance`, `/margin/risk`
  (leverage + liquidation), `/margin/funding_rates/estimate`, `/margin/funding_history`,
  `/portfolio/intra_exchange_instance_transfer` (fund the margin sub-account from the binary account).
- **Product mechanics (good for hedging):** BTCPERP is cash-settled USD, **never expires**, tracks
  the CF Benchmarks BRTI (updates every second), **8-hour funding** (negligible for our ≤15-min
  holds — we'd rarely cross a funding stamp), **0% fees** currently. US-regulated — the only
  US-legal crypto-perp option (Binance/Bybit are geo-blocked for a US user).
- **Live market snapshot:** BTCPERP bid 2.0410 / ask 2.0421, `contract_size 0.01`,
  `leverage_estimate ~3x`, `fractional_trading_enabled: false`, liquidation price tracked.

## The two blockers
1. **Margin not enabled on the account.** `/margin/enabled` → `{"enabled": false}`. Perps are a
   margin product requiring a one-time opt-in/agreement in the Kalshi UI. That's a user action I
   can't do — but it's not the real problem.
2. **THE KILLER — minimum size mismatch.** One perp contract = `contract_size 0.01` BTC ≈ **~$1,000
   notional** (the leverage tiers are keyed at $1k/$10k/$100k/$1M, confirming the scale), and
   **fractional trading is disabled** — you cannot trade less than one contract. But the hedge our
   backtest wanted for *one* unpaired binary contract is only ~$100 of BTC delta (the delta-neutral
   `h=100` ≈ $1 per 1% move ≈ $100 notional). So the smallest perp you can place **over-hedges a
   single binary leg by ~10×**, and over-hedging is exactly what the backtest flagged as a
   high-variance directional bet (the `h=200–300` rows), not a hedge.

## Why this is fundamental, not a tuning issue
The binary leg's entire payout is $1, so its dollar delta is at most ~$1; the appropriate hedge is
tens of dollars of BTC notional. The perp's minimum tradeable unit is ~$1,000 notional. To make one
perp contract an *appropriately-sized* hedge you'd need to be carrying roughly **10+ unpaired binary
contracts** of net delta at once — which is precisely the concentrated directional exposure the
`--max-net 1` clamp exists to prevent, and which these thin 15-min markets can't absorb anyway
(capacity-limited). So the hedge and our risk discipline are at odds at this size.

## When it WOULD make sense
If the book ever runs at ~$10k+ of capital with clip sizes of tens of contracts, the aggregate
net-unpaired delta could reach ~0.01 BTC, and *then* one perp contract is a sensible hedge — at
which point this scoping (auth works, endpoints mapped, funding negligible) means it's a
~1–2 day build: a small `external-api.kalshi.com` margin client, fund the sub-account, compute the
binary delta, fire/​unwind the hedge on unpaired fills, monitor `/margin/risk` for liquidation.

## Recommendation
- **Don't build it now.** At 1-contract size it can't be sized correctly and would add leverage,
  liquidation risk, capital-splitting, and a whole second system — to *worsen* risk, not reduce it.
- **The clamp fix is the right risk control at this scale** (bounds an unpaired leg to ~$0.50).
- Re-evaluate the perp hedge only if/when the book scales to where ~0.01 BTC of hedge is appropriate.
- Keep `t14_perp_hedge_unpaired` in the A/B tester as the *theoretical* benchmark — it tells us how
  much the unpaired-leg loss *could* be removed if a correctly-sized hedge were available, which is
  useful for valuing scale.

## Sources
- [Kalshi API docs](https://docs.kalshi.com/welcome) + the `perps_openapi.yaml` spec (base URL, auth, endpoints — verified live)
- [What perpetuals are available on Kalshi (Help Center)](https://help.kalshi.com/en/articles/15357566-what-perpetuals-are-available-on-kalshi)
- [Kalshi Launches First U.S.-Regulated Bitcoin Perpetuals (BanklessTimes)](https://www.banklesstimes.com/articles/2026/06/04/kalshi-launches-first-u-s-regulated-bitcoin-perpetuals/)
- [Kalshi moves into crypto perpetuals (CNBC)](https://www.cnbc.com/2026/05/29/kalshi-is-moving-beyond-prediction-markets-and-into-one-of-cryptos-biggest-trading-lanes.html)
