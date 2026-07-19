# Polymarket wallet P&L — smart/dumb follow-fade edge (btc-updown-5m)

Node: EDGE-POLYMARKET-WALLETS (2026-07-15). Offline research, propose-only, read-only external API.
No live action, no orders. Data pulled live from Polymarket public APIs + our quote archive slugs.

## TL;DR verdict
- **Wallet-level trade history: FULLY OBTAINABLE.** Polymarket's public `data-api` returns every
  fill with the proxy-wallet address; Gamma returns each market's clean 0/1 resolution. Built real
  per-wallet realized P&L over **632 btc-updown-5m markets, 2.53M trades, 30,761 wallets** (35 days).
- **Skill persistence: REAL (rank-wise).** Winning wallets in TRAIN keep winning in TEST — Spearman
  train→test ROI = 0.16–0.18 (z ≈ 6–8), robust across activity thresholds. Top train-ROI decile
  earns +11% ROI OOS; bottom decile stays negative.
- **A tradeable follow/fade edge: NO (honest NULL).** Every apparent dollar edge is **tail-
  concentrated** and cannot be captured ex-ante. FOLLOW-smart (+$28.7k, t=2.08 @0.5c) collapses to
  −$2.1k when the top-10 whale wallets are dropped. FADE-new (+$82.7k, t=4.82 @0.5c) reverses to
  −$64k (t=−5.71) when the worst-200 of 9,607 new wallets are dropped — 88% of the "edge" is 50
  blow-up accounts you cannot identify in advance. A **capacity-friendly, size-independent
  directional signal clears nothing** (best t=1.89, < 2, and that ignores the spread you cross).
- **FADE-dumb: NULL** after cost. **Root cause** = the prior finding holds: these books are
  tight/deep/efficient, so net "smart" flow does not predict the 5-min outcome beyond noise; the
  money that changes hands is thin liquidity-provision to a few idiosyncratic blow-ups.

---

## Phase A — Feasibility (VERDICT: data is obtainable and rich)

**Endpoints that work (HTTP 200, no auth, via agent proxy):**
- Trades: `https://data-api.polymarket.com/trades?market=<conditionId>&limit=1000&offset=<n>&takerOnly=false`
  → per fill: `proxyWallet`, `side` (BUY/SELL), `asset` (ERC1155 token id = outcome leg),
  `conditionId`, `size`, `price`, `timestamp`, `outcome` (Up/Down), `transactionHash`, pseudonym.
- Resolution + token map: `https://gamma-api.polymarket.com/markets?slug=<slug>&closed=true`
  → `conditionId`, `clobTokenIds` [Up,Down], `outcomePrices` (["1","0"]=Up won / ["0","1"]=Down won),
  `umaResolutionStatus`, `volumeNum`. **All 632 sampled slugs resolved cleanly (definitive 0/1).**

**Slug→market map:** archive slug `btc-updown-5m-<epoch>` (epoch = window start) maps 1:1 to a Gamma
market; the epoch itself yields window `[start, start+300]`. `closed=true` is required to see them.

**Volume (this IS a real, liquid lab):**
- ~2,159 taker fills/market (≈4,001 incl. maker legs) for a single 5-min market; median market
  **$80k** notional, sample total **$56M** over 632 markets; ~285 markets/day exist.
- **445+ unique wallets in the first 1,000 fills of one market**; 30,761 distinct wallets in sample;
  16,360 wallets active in ≥5 markets, 6,251 in ≥20.

**Accounting validated (zero-sum):** with `takerOnly=false` both legs of every match appear, so
summing my reconstructed per-wallet realized P&L across a market ≈ **0** (median residual **0.0038%**
of gross). This confirms the fills are complete and the P&L math is correct.

**Cost model (stated explicitly):** Polymarket CLOB maker/taker **fee = 0** (gasless off-chain
matching; on-chain settlement gas subsidized by the operator's relayer). The only real cost is
**crossing the spread**, which on these near-expiry books is a **median of 1c** (from the quote
archive). I score net of slippage ∈ {0, 0.5c, 1.0c} per share.

**Wash/self-trade guard:** realized P&L is inherently wash-resistant (a self-trade nets ≈0 P&L, so it
cannot manufacture a track record). Inspecting the 12 highest-gross wallets: all show the classic
**market-maker** signature — huge gross ($0.25M–$1.55M), hundreds of markets, ROI pinned near
**±0.5%** — i.e., legitimate thin-margin liquidity provision, not P&L-faking wash.

## Realized P&L reconstruction (method)
Per (wallet, market, outcome-token): `net_shares = ΣBUY − ΣSELL`, `cash = −Σ(buy·px)+Σ(sell·px)`.
Terminal value = `net_shares × (1 if token won else 0)`. Wallet-market P&L = `cash + terminal`.
This is realized-to-settlement and correctly handles early exits and short (SELL) legs.
TRAIN = days ≤ 2026-06-30 (June, 359 markets); TEST = ≥ 2026-07-01 (July, 273 markets).

---

## Phase B — Wallet P&L distribution (30,761 wallets, whole sample)

| pct | net P&L |
|---|---|
| min | −$16,482 |
| p1 | −$537 |
| p10 | −$38.7 |
| median | −$0.31 |
| p90 | +$34.7 |
| p99 | +$518 |
| max | +$68,567 |

- **47.5% of wallets net-positive**; heavy two-sided tails. Top wallet +$68.6k on $250k gross
  (ROI 27%, 110 markets); the single most active wallet (631 markets) is −$16.5k (a MM run over by
  informed flow). The distribution is real, skewed, and not dominated by wash.

---

## Phase C — Persistence + follow/fade OOS (the crux)

### C1. Skill persistence — REAL (rank-wise), robust
Wallets with ≥K markets in BOTH periods, Spearman(train_ROI, test_ROI):

| K (min markets each period) | n wallets | Spearman | approx z |
|---|---|---|---|
| ≥10 | 2,811 | **0.159** | 8.4 |
| ≥20 | 1,611 | 0.172 | 6.9 |
| ≥30 | 1,083 | 0.178 | 5.9 |

Decile split (rank by train ROI, score realized TEST): **top train-decile → TEST ROI +0.113,
$/mkt +3.62; bottom decile → TEST ROI −0.018.** Winners persist; losers persist. This part is solid.

### C2. FOLLOW smart / FADE dumb — NOT tradeable (tail-concentrated)
Smart/dumb = top/bottom train-ROI decile among train_n≥10 (705 wallets each). Score = clone their
TEST net position at their price minus slippage; market-clustered t.

| strategy | slip 0 | slip 0.5c | slip 1.0c |
|---|---|---|---|
| FOLLOW smart (total / t) | +$34.2k / +2.46 | +$28.8k / **+2.08** | +$23.3k / +1.70 |
| FADE dumb (total / t) | +$1.7k / +0.37 | −$1.2k / −0.26 | −$4.0k / −0.88 |

- **FADE-dumb is a NULL** (doesn't survive any cost).
- **FOLLOW-smart looks positive but is a whale artifact:** drop the top-10 smart wallets by TEST
  gross → **+$28.8k becomes −$2.1k (t=−0.28)**. The edge is 10 specific accounts, not a broad
  "follow the smart crowd" signal — n=10 is untrustworthy OOS and capacity/latency-bound (5-min
  window, must react after their fill prints).

### C3. FADE new / low-history wallets — looks strongest, also a tail artifact
No-train-history wallets (9,607 wallets, 81,861 TEST rows) collectively lose **−$115k (ROI −4.3%)**.
Fading them: **+$82.7k (t=4.82) @0.5c, +$50.4k (t=2.94) @1.0c, 13/15 TEST days positive.** BUT:

- worst **10** new wallets = **46%** of the loss; worst **50** = **88%**; the remaining ~9,400 new
  wallets are collectively **positive**.
- Drop the worst-200 new wallets → fade-new **reverses to −$64.7k (t=−5.71) @0.5c**.
- You cannot know ex-ante which newcomer becomes one of the ~50 blow-ups. Fading the *typical* new
  wallet loses. The aggregate is survivorship of a few disasters, i.e., the market-making /
  adverse-selection capture that a handful of incumbent MMs already harvest at ~0.5% ROI.

### C4. Capacity-friendly directional signal — clears NOTHING
Fixed unit bet on the *net direction* of a group's flow (removes size/tail dominance), TEST markets:

| signal | markets | winrate | t |
|---|---|---|---|
| follow SMART (vote) | 272 | 0.471 | −0.97 |
| follow SMART (net shares) | 273 | 0.509 | +0.30 |
| fade NEW (vote) | 273 | 0.527 | +0.91 |
| fade NEW (net shares) | 273 | 0.557 | **+1.89** |
| follow ALL flow (net shares) | 273 | 0.473 | −0.91 |

Nothing reaches t=2; the best (fade-new net-shares, t=1.89) still **ignores the ~1c spread you must
cross**, which erases it. **As a scalable directional signal, the edge does not exist.**

---

## Phase D — Behavioral signatures + Kalshi transfer

Size-weighted TEST features by cohort:

| cohort | avg trade sz | trades/mkt | timing (frac into 5-min window) | avg entry px | held-to-settle | mkt win-rate |
|---|---|---|---|---|---|---|
| SMART (top train ROI) | 42.9 | 2.9 | **0.83 (late)** | **0.268 (cheap)** | 0.97 | 0.339 |
| DUMB (bottom train ROI) | 25.2 | 2.8 | 0.84 | 0.197 | 0.97 | 0.258 |
| NEW (no history) | 27.6 | 3.2 | 0.76 (earlier) | 0.371 | 0.91 | 0.569 |
| ALL | 25.1 | 4.4 | 0.78 | 0.513 | 0.94 | 0.604 |

**Signature read:** SMART wallets buy **cheap** (avg 0.27), in **larger** size, **late** in the window
(~83% of the way to expiry, when spot has revealed more), and **hold to settlement** — they win few
markets but win big (positive skew). NEW/crowd wallets buy **richer favorites** (0.37–0.51), earlier,
win *more* markets but *lose money* (small wins, occasional big losses). This is a coherent "informed
longshot-value vs. uninformed favorite-chasing" split — but note it did **not** translate into a
tradeable signal above (efficient books).

**Transfer to Kalshi (preliminary, skeptical):**
- Kalshi is anonymous — **no wallet re-ID** (already established infeasible in `edge_player_reid.md`),
  so the identity-based ranking cannot port. Only the *anonymized trade-level* signature (size × price
  level × timing-in-window) could in principle be detected in `trades_kalshi`.
- **But the honest blocker:** even *with* full wallet identity, the signal is **not tradeable on
  Polymarket** (tail-concentrated / null directionally). An anonymized, necessarily-weaker version on
  Kalshi is very unlikely to do better, and it must additionally clear Kalshi's ~1.3c fee that already
  killed the dumb-flow-fade edge.
- **Population-transfer risk is high:** Polymarket = crypto-degen wallets on a 0-fee 5-min CLOB;
  Kalshi = US-retail on a 15-min fee'd market. Different tenor, cost, and trader mix. Low priority.

---

## Overall verdict
Wallet data is **fully obtainable** and the lab is genuinely liquid — this is exactly the clean,
persistent-ID, near-zero-fee environment the big idea called for. Wallet **skill is real and persists
OOS in rank terms** (winners keep winning, z≈6–8). But **no follow/fade strategy clears out-of-sample
as a capacity-realistic edge:** every positive dollar result is concentrated in <10–50 extreme wallets
(whales on the win side, blow-ups on the lose side) that cannot be identified ex-ante, and the
size-independent directional signal is null (best t=1.89, and that is before crossing the 1c spread).
FADE-dumb is a clean null. This corroborates the prior `newedge_polymarket` finding: the btc-updown
books are tight/deep/efficient, so even zero fees do not open a fadeable behavioral mispricing — the
only money is thin liquidity-provision that incumbent MMs already earn. **Recommendation: do NOT build
a follow/fade wallet strategy on these markets; the rigorous outcome is a NULL despite excellent data.**

### Caveats / limits
- 632-market sample (~18/day) not the full ~285/day universe; persistence z's are robust but the
  follow/fade nulls could be revisited on a fuller pull — though the tail-concentration mechanism is
  structural, not sample-size-driven.
- "Follow at their price minus slippage" is an optimistic upper bound (ignores latency to react
  inside a 5-min window and market impact of cloning). Real execution would be worse, reinforcing NULL.
- Resolution taken from Gamma `outcomePrices`/UMA status (Polymarket's own settlement) — the correct
  payout label, not a foreign spot proxy.
