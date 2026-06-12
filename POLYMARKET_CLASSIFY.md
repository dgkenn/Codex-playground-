# Polymarket trader-classification → Kalshi transfer — feasibility verdict (2026-06-12)

The operator's idea: Polymarket is on-chain, so we can see WHO trades (wallet addresses) and classify
incoming flow by trader — identify wallets whose presence predicts pairing/strands and any directional
edge — then transfer those hypotheses to anonymous Kalshi.

## What's TRUE (verified against the live Polymarket API)
- **Wallet-level data is real and free.** `data-api.polymarket.com/trades` returns per-trade
  `proxyWallet` (on-chain address), side, size, price, timestamp, tx hash, even a pseudonym. Filters
  `market=<conditionId>`, `user=<wallet>`, `offset=`, `limit=` all work (probe: `pmkt_wallets.py`).
  So on Polymarket we genuinely CAN build per-wallet histories and score directional accuracy.
- **A 2-hour all-asset probe** pulled 24 resolved up/down markets, 1,769 trades, 661 distinct wallets;
  mean per-wallet directional accuracy 58%. But the "top" wallets were all n=2 (100% on two trades =
  noise). Only ~22 wallets cleared 55% over ≥10 trades. Signal is plausible but unproven at this n.

## The TWO hard problems (why this is a slow, speculative line — not a near-term lever)

### 1. Identity cannot transfer. Kalshi is anonymous.
Kalshi's tape carries no trader/wallet ID. Even if we perfectly classify Polymarket wallets, we can
NEVER tag an incoming Kalshi order by trader. So the original framing — "classify incoming orders by
the trader" — is impossible ON KALSHI. The only thing that can transfer is a **behavioral signature**
(size, aggressor-run pattern, burst timing, sweep depth, round-lot footprint) — i.e. exactly the
anonymous-observable detectors we already built (`informed_detectors.py`: VPIN, d1–d5, take_n) and
just wired as the t35 toxicity gate. Polymarket's only possible value-add is **labeled ground truth**:
wallet realized P&L tells us which signatures mark informed/toxic flow, which we then apply to Kalshi.

### 2. The same-tenor (BTC-15m) Polymarket data is thin and forward-only.
The operator (correctly) wanted BTC-15m only, to match KXBTC15M and drop cross-asset/5m noise. Reality:
- BTC-15m markets **DO exist** on Polymarket (verified live: `btc-updown-15m-<unix>` on 900s
  boundaries; one window carried ~$4,984 volume) — the haiku agent's "they don't exist" was wrong.
- BUT only the **current/near** windows are queryable by slug; **resolved 15m history drops out of the
  Gamma index**, so there is NO bulk retrospective to mine. A 72h slug-walk found 0 resolved.
- And the 15m series is **THIN**: ~$5k/window vs the 5-min series' $100k–273k. Few wallets, slow
  accumulation. To study BTC-15m wallets we must **COLLECT FORWARD** (capture trades+wallets live),
  and it will accumulate slowly.

## The strategic verdict
This is a **speculative, slow-payoff research line, not a near-term edge**, because:
1. We ALREADY have a working Kalshi-native toxicity classifier (t35, OOS AUC 0.700) trained on Kalshi's
   own settle labels — Polymarket's "better labels" advantage is marginal and slow to materialize.
2. BTC-15m Poly data is thin + forward-only; getting enough wallet history to identify *persistently*
   informed wallets is weeks of collection, and even then it only yields a behavioral signature we can
   already estimate from Kalshi directly.
3. The 5-min series is 20–50× deeper and the wallet population is largely the SAME Polymarket
   crypto-momentum traders — but it's a different tenor (the operator's noise concern is real).

## Concrete options (the decision is the operator's — it changes what we collect)
- **A. Forward BTC-15m trade+wallet collector** (same tenor, clean transfer, but thin → weeks to
  signal). Extend `pmkt_collect.py` to also hit `/trades` and log `proxyWallet` on the live 15m window.
- **B. Forward BTC-5m trade+wallet collector** (deep, fast wallet stats; validate that informed-wallet
  *signatures* — size/timing/aggressor pattern — match Kalshi's toxic-flow detectors; tenor differs).
- **C. Don't invest.** Keep improving the Kalshi-native detector (t35) which already does the job the
  Polymarket labels were meant to bootstrap. Re-open only if a deeper edge is needed at scale.

Recommendation: **B as a one-off labeled-data study** (fast, proves whether informed-wallet signatures
even match our Kalshi detectors), and only graduate to **A** if that link is real and worth the slow
same-tenor collection. `pmkt_wallets.py` is the re-runnable scoring tool for either.

## Operator chose B (2026-06-12). Verified data reality + execution path.
DIRECT verification (not an agent's claim): BTC-5m markets are LIVE and busy right now (822 trades
across 4 windows in the rolling feed; 96 of the last 500 global trades are btc-updown-5m), but
Polymarket serves **NO bulk resolved history** — the data-api/trades feed is only a ~30-min rolling
window and resolved short-tenor windows drop from the Gamma index within ~10 min of close (a window
10 min old already returned empty by conditionId). So a one-off RETROSPECTIVE is impossible; B must be
run on a short FORWARD capture. (Three delegated agents each wrongly concluded "BTC-5m doesn't exist"
— that is a slug-walk discovery artifact; the markets exist, the HISTORY doesn't.)
- **`pmkt_5m_collect.py`** (NEW): forward collector. Polls the trades feed, dedupes by tx, keeps
  btc-updown-5m trades (wallet/size/price/side/outcome/window), and records each window's RESOLUTION
  (winner from `outcomePrices`→0/1) ~90s after close while still indexed. Smoke-tested: 508 trades /
  323 wallets / 1 resolved in 20s (it backfills the rolling feed on start). Launched for ~3h.
- **`pmkt_signature_study.py`** (REWRITTEN): reads the collected trades+resolution, scores each wallet's
  realized directional accuracy, splits INFORMED (acc≥58%, meaningful sample) vs NOISE (~50%), and
  compares their trade SIZE / LATE-fraction / CONVICTION against the Kalshi fingerprint (bigger+later+
  one-sided = informed). Prints a 4-row match table + verdict. Runs on whatever has accumulated.
- **The decisive test:** if informed Poly wallets replicate the Kalshi size/late/conviction signature
  → external validation of our anonymous detectors (t35), maybe a refined feature. If they look like
  noise on those features → the behavioral transfer is dead and we drop the line, keeping t35. Result
  pending ~3h collection.
