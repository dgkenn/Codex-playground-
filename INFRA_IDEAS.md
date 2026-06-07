# Best ideas distilled from the open-source repos (reviewed, tested, adopted/rejected)

Reviewed the recommended repos' actual approaches, extracted concrete techniques, and
tested the strategy-level ones on our historical data. **Key conclusion: the repos'
*strategy* ideas don't add alpha in *our* market (tight 1-tick, near-binary 15m — the
structural vig + inventory skew is already near the ceiling); their *infrastructure*
ideas are what level us up.**

## Strategy ideas — TESTED, REJECTED for this market
| Idea (source) | Result on our data | Verdict |
|---|---|---|
| Per-side EWMA markout toxicity (hyperliquid-mm-bot) | gross t 8.6→0.5, $18.5k→$0.3k as pull tightens | **hurts** (breaks 2-sided vig; overfits noise) |
| Flow-imbalance filter | marginal OOS +0.4 at −16% volume | reject (skew already absorbs it) |
| Trained toxicity model (our combo_maker) | selecting "best" fills worse OOS | reject (chases toxic vig) |
| Near-0.5 price filter | reduces net | reject |
| VWAP-anchored FV / A-S spread optimization (Hummingbot/quantpylib) | n/a: spread is pinned at 1 tick → no room to set our own quote prices | not applicable |
Why: these are built for wider-spread, directional perp/crypto books. Our market is
1-tick and the edge is *structural* (capture the overround on matched 2-sided flow +
rebate, stay flat via skew). "Smart" pulling/widening just cuts the structural capture.

## Strategy ideas — ALREADY in our bot
- Inventory skew to flatten (Avellaneda-Stoikov-lite) — adopted; tighter skew = better.
- 2-sided quoting / overround capture — the core edge.

## Infrastructure ideas — ADOPTED
- **Real-time WebSocket market feed** (nevuamarkets/poly-websockets, tribeca): replaced
  6s polling with the CLOB market channel (wss://ws-subscriptions-clob.polymarket.com/ws/market)
  → event-driven fills. `paper_trader_ws.py`.
- **Reconnect-within-window robustness** (poly-websockets): MM state persists across
  socket drops; auto-resubscribe. Added to `paper_trader_ws.py`.
- **Per-side markout LOGGING** (hyperliquid): we still log per-fill mid + per-side fill
  counts for offline adverse-selection audit (we just don't *act* on it — tested, hurts).

## Infrastructure ideas — QUEUED for the LIVE build (in live_trader.py / a real OMS)
- **30s sync lifecycle + diff-orders + SIGTERM cancel-all** (Polymarket/poly-market-maker):
  the order-management loop — compute desired quotes, diff vs open, cancel/replace, and
  always cancel-all on shutdown. Adopt for `live_trader.py`.
- **Bands / multi-level quoting** (poly-market-maker): post at several levels, not just the
  touch — more depth/volume. Optional once single-level fills are confirmed live.
- **Position merging** (warproxxx/poly-maker `poly_merger`): redeem complementary Up+Down
  pairs for $1 to free collateral + cut gas → capital efficiency. Important at scale.
- **EIP-712 / POLY_1271 order signing** (polymarket-cpp-client): the auth signing path
  (the official py-clob-client-v2 handles this; reference for a custom client).
- **Retry w/ exponential backoff + rate limiting** (CCXT): already partially in our fetch
  layer; apply to the live order path.
- **Pre-trade risk checks / deterministic matching** (nanobook): a risk gate before every
  order (max notional, position, loss kill-switch) — our live_trader has the rails; nanobook
  is the pattern if we want a Rust execution kernel later.

## For the eventual LIVE deploy (not run here)
Use the official **Polymarket/py-clob-client-v2** for execution; consider **Hummingbot**
or **NautilusTrader** (community Polymarket adapter) as the OMS shell rather than
hand-rolling. The decisive lever remains **fill rate / queue priority** (latency), per
all the research — that's what the tiny-live pilot must measure.
