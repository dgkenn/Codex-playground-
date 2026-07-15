# Polymarket copy-trade — tail-robust harvest of persistent wallet skill (btc-updown-5m)

Node: EDGE-POLYMARKET-COPYTRADE (2026-07-15). Offline research, propose-only, read-only public API.
No live action, no orders. Builds directly on `edge_polymarket_wallets.md` (skill persists OOS,
z≈6-8; but naive follow/fade was tail-dominated and failed). This node asks the sharper question:
**is there a TAIL-ROBUST, FIXED-SIZE, spread-clearing OOS construction that harvests the persistent
skill, or does none exist?**

## TL;DR verdict
- **Copying the SMART wallets' direction: NULL (definitive).** Every count-based / quorum / consensus
  construction that takes the *smart* side is either negative net-of-spread, or positive only because
  the smart side coincides with the **market favorite**. When the smart lean **diverges** from the
  favorite it is **wrong 94-97% of the time** (Control E: smart-vs-favorite, 50 test mkts, win 6%,
  t=-3.59). Crossing the ~1c spread to copy their late cheap-longshot buys loses. The persistent
  **skill is real but is not a copyable directional signal** — it lives in fill quality / longshot
  selection, not in a side a follower can take after the fact.
- **A tail-robust, fixed-size, spread-clearing OOS edge DOES exist — but it is NOT skill-copy.**
  It is a **conditional favorite-underpricing / fade-late-underdog-flow** effect: when ≥2 tracked
  wallets are **buying the underdog** late in the window, the **favorite is underpriced and wins ~97%**.
  Buying the favorite fixed-size at the ask (spread crossed) at T=180s: **OOS mean +0.124/contract,
  day-clustered t = +5.5** (t=+7.2 market-clustered), **survives every jackknife** (drop top-5 markets
  t_day +3.7; drop top-20 contributing wallets t_day +5.8; drop best day t_day +4.2; 5% trim t_day +8.3),
  and is **stable across entry times** (Toff 120-240s all positive).
- **The edge is IDENTITY-INDEPENDENT** → it is not the wallet skill. Gating on *persistent-SMART*
  wallets buying the underdog works just as well (t_day +5.8) as *persistent-DUMB* (t_day +5.5). What
  carries the signal is **late contrarian/underdog flow of any kind**, i.e., the classic
  favorite-longshot bias + liquidity provision to noise — the same structural money the prior node
  attributed to incumbent MMs. Unconditional favorite-buying is a clean NULL (t=+0.05); the
  *conditioning on late underdog flow* is what creates it.
- **Net:** the **skill-copy thesis is NULL**; a **real but adjacent** fade-underdog/buy-favorite edge
  clears robustly. It overlaps the repo's existing FAVLONG theme and must be de-duped against it, and
  its capacity is thin (~5-7 fixed-size fills/day, entry ~0.85, bounded by favorite ask depth) before
  any deployment.

---

## Data & method
- **Reuse:** `wallet_market.jsonl` (632 btc-updown-5m markets, 563k wallet-market rows, 35 days) from
  the prior node. Train = days ≤ 2026-06-30 (20 test-usable days of activity); Test = ≥ 2026-07-01
  (15 days). Smart / dumb = top / bottom train-ROI decile among wallets with ≥10 train markets
  (705 each), fixed ex-ante on TRAIN.
- **Order books:** `pmkt_cache/*.pkl` — per-market Up/Down bid/ask time series (~200 quotes/market),
  covering **all 632 markets**. Median top-of-book spread ≈ **1c**. Entry is modeled by **paying the
  ASK** (i.e., crossing the spread) — this *is* the cost. Extra +0.5c slippage also reported.
- **Cost model (explicit):** Polymarket CLOB fee = 0. Only cost = crossing the ~1c spread, charged by
  buying at the ask. Fixed size = **1 contract per triggered market** (structurally tail-robust: each
  market contributes payoff ∈ [-entry, 1-entry], no whale can dominate).
- **CRITICAL causality fix:** the first-pass constructions used each wallet's *final settled* position
  to pick the side, then priced entry at T=180s. Smart wallets act late (size-wt avg timing 0.85,
  median 0.90 ≈ 270s), so **172/225 of their qualifying trades post-date T=180** → the naive signal
  had **lookahead leak** (it "knew" the last-60s move; entry printed 0.50 while win-rate 0.87).
  Fix: **re-pulled 158k raw smart/dumb trades** (`causal_trades.pkl`) and rebuilt every side signal
  from **as-of-T positions only** (trades with ts ≤ T), pricing at the same T. All results below are
  causal. The leak was material (causal entry rose 0.50 → 0.75; the causal edge is real but ~3× smaller).

---

## Construction 1 — QUORUM COPY (count-based, one-vote-per-wallet, fixed size)
Copy the side that ≥N persistent-smart wallets hold as-of-T; enter at ask. Sweep N, timing, min-lean
on TRAIN (30 configs), single OOS.

| version | OOS n | wr | entry | mean | t_mkt | t_day |
|---|---|---|---|---|---|---|
| naive (final-position signal, leaked) | 154 | 0.15 | 0.20 | -0.050 | -2.82 | -0.94 |
| **causal (as-of-T=180, N=5)** | 77 | 0.66 | 0.57 | +0.093 | **+4.38** | +4.31 |

Causal quorum-copy looks positive — **but the control (below) shows it is buying the favorite**, not
harvesting skill. The naive version is negative because copying at the ask on cheap longshots loses.

## Construction 2 — SMART-vs-DUMB DISAGREEMENT (take the smart side, fixed size)
Markets where smart and dumb majorities are on opposite sides as-of-T; take the smart side at ask.
Best TRAIN config (Toff=180, min-lean=10, min-smart=2; 30 configs swept):

| OOS eval | n | wr | entry | mean | t_mkt | t_day |
|---|---|---|---|---|---|---|
| at ASK (spread crossed) | 44 | 0.841 | 0.750 | +0.091 | +3.36 | **+3.99** |
| ASK +0.5c | 44 | 0.841 | 0.750 | +0.086 | +3.17 | +3.80 |
| jackknife drop top-5 mkts | 39 | 0.821 | 0.758 | +0.063 | +2.29 | +2.92 |
| drop top-10 contributor wallets | 29 | 0.759 | 0.693 | +0.066 | +1.70 | +2.32 |

Positive and survives jackknife — **but the control demolishes the skill interpretation.**

## Construction 3 — CONSENSUS STRENGTH (does smart-fraction beat market price?)
Buy the side where (smart-fraction − Up-price) exceeds a threshold (i.e., where smart lean disagrees
with the price, usually the *cheap* side). Best TRAIN (Toff=210, min-smart=3, thr=0.10; 36 configs):

| OOS eval | n | wr | entry | mean | t_mkt | t_day |
|---|---|---|---|---|---|---|
| at ASK | 153 | 0.170 | 0.211 | -0.042 | -1.80 | -2.54 |
| drop top-5 mkts | 148 | 0.142 | 0.213 | -0.071 | -3.66 | -4.60 |

**NULL / negative.** Buying the side smart money leans toward *beyond the price* (the cheap longshot)
loses and gets worse under jackknife — the mirror image of "smart-against-favorite is wrong."

---

## The control that settles it — is any of this SKILL, or just the favorite?
Buy the T=180s **favorite** at the ask, fixed size:

| gate (TEST) | n | wr | entry | mean | t_mkt | t_day |
|---|---|---|---|---|---|---|
| **A. unconditional favorite (pure favlong)** | 268 | 0.750 | 0.749 | +0.001 | +0.05 | +0.08 |
| B. ≥1 dumb wallet on underdog | 131 | 0.885 | 0.815 | +0.071 | +2.99 | +2.78 |
| **C. ≥2 dumb wallets on underdog** | 100 | 0.970 | 0.846 | +0.124 | +7.20 | **+5.53** |
| D. ≥2 smart wallets on favorite | 82 | 0.939 | 0.831 | +0.108 | +4.80 | +4.68 |
| within disagreement mkts, **smart side == favorite** | 39/44 | 0.949 | 0.834 | +0.115 | +4.06 | +5.17 |
| within disagreement mkts, **smart side ≠ favorite** | 5/44 | **0.000** | 0.096 | -0.096 | -6.84 | -13.06 |
| **E. ALL mkts where smart leans AGAINST favorite** | 50 | **0.060** | 0.172 | -0.112 | -3.59 | -2.31 |

Reading:
1. **Unconditional favorite = NULL** (favorites at 0.749 win 75.0% — calibrated). So this is not a
   generic favlong result; a specific selection creates the edge.
2. In every "positive smart" construction, **smart side == favorite** (39/44). The positive P&L is the
   favorite, not the wallet.
3. **When smart diverges from the favorite it is wrong 94-97%** (rows E and "smart side ≠ favorite").
   The persistent skill provides **no exploitable directional signal beyond the price.**
4. The gate that actually carries the edge is **dumb money on the underdog** (row C, t_day +5.5),
   *stronger* than the smart-on-favorite gate (row D). The mechanism is **fade the late underdog flow.**

### Identity is irrelevant — proof it is not the skill
Buy-favorite at Toff=180, TEST, by which tracked wallets are late-buying the underdog:

| gate | n | wr | entry | mean | t_day |
|---|---|---|---|---|---|
| ≥2 persistent-DUMB on underdog | 100 | 0.970 | 0.846 | +0.124 | +5.53 |
| ≥2 persistent-SMART on underdog | 82 | 0.951 | 0.838 | +0.114 | **+5.83** |
| ≥2 ANY tracked wallet on underdog | 122 | 0.918 | 0.822 | +0.096 | +4.26 |
| ≥3 persistent-DUMB on underdog | 74 | **1.000** | 0.873 | +0.127 | +7.94 |

Smart-on-underdog signals the favorite just as well as dumb-on-underdog. **The wallet skill/identity
does not matter — late underdog buying (from anyone) marks an underpriced favorite.** This is
favorite-longshot bias / liquidity provision to noise, not a harvest of persistent skill.

---

## Tail-robustness of the one real edge (fade-underdog / buy-favorite, gate C, Toff=180)
All net of the ~1c spread (entry at ask), fixed size:

| stress | n | wr | mean | t_day |
|---|---|---|---|---|
| baseline | 100 | 0.970 | +0.124 | +5.53 |
| drop top-1 / top-3 / top-5 markets | 99/97/95 | — | +0.099/+0.090/+0.083 | +4.86/+5.02/+3.72 |
| drop top-5 / top-10 / top-20 underdog-wallets | 86/80/63 | 0.96-0.98 | +0.121/+0.113/+0.117 | +4.94/+4.67/+5.76 |
| drop best day | 68 | 0.941 | +0.095 | +4.15 |
| 5% trim both tails | 70 | 0.986 | +0.118 | +8.26 |
| entry time Toff = 120/150/180/210/240 | 50-173 | 0.92-0.97 | +0.043..+0.124 | +5.06/+3.83/+5.53/+4.71/+2.03 |

This is exactly the **tail-robustness bar the prior node's naive harvest failed**: fixed-size,
survives dropping the top-K contributing markets/wallets, clears the spread OOS, and does not depend
on any handful of whales/blow-ups. It holds.

## Multiple-testing disclosure
~180 configurations examined across all constructions (C1 naive 36 + causal 30; C2 9 + 30; C3 18 + 36;
controls/attribution ~15; Toff/identity/jackknife sweeps ~20). The **surviving** effect is not a lucky
config: it is positive across **all 5 entry times, both wallet identities, and every jackknife/trim** —
the opposite of a single overfit point. The SMART-COPY constructions, conversely, are consistently
null-or-negative once the favorite is controlled for.

## Capacity (of the adjacent real edge, if pursued)
- Direction: **BUY the favorite** (the ~0.85 side) at the ask, hold to settlement, 1 contract fixed.
- Frequency: ~**5-7 triggers/test-day** (gate C), i.e. a few % of the ~285 daily markets.
- Economics: pay ≈0.846 to collect 1.0 with p≈0.97 → **+0.12/contract net of spread**, ~14% per trade
  on capital at risk; but you are lifting a **rich favorite from limited sellers** — capacity is bounded
  by the favorite ask depth at ~0.85 (thin; likely low-$k notional/market before you move the price into
  your own edge). This is the **thin liquidity-provision** slice incumbent MMs already work; a copier
  crossing the spread captures only what survives that competition. **Live ask-depth measurement is
  required before sizing** — the backtest assumes fills at the posted ask.

## Verdict
- **Harvesting the persistent wallet SKILL by copying direction (quorum / disagreement / consensus):
  NULL.** The skill persists rank-wise (prior node) but is not a takeable side — smart direction is not
  predictive beyond the market price, and is actively wrong when it disagrees with the favorite.
- **A tail-robust, fixed-size, spread-clearing OOS edge nonetheless EXISTS** via the disagreement/dumb
  route reframed correctly as **"buy the underpriced favorite when ≥2 wallets late-buy the underdog":**
  OOS **day-clustered t ≈ +5.5 net of the 1c spread, survives all jackknives**, stable across timing.
  It is a **favorite-longshot / fade-noise-flow microstructure effect, identity-independent**, not a
  skill copy — and it overlaps existing FAVLONG work. **Recommendation:** do NOT build a "follow the
  smart wallets" strategy (null); the only deployable signal here is fade-late-underdog-flow, which
  should be **de-duplicated against the repo's FAVLONG models** and its thin, competitive capacity
  validated with live order-book depth before it is treated as incremental.

### Caveats
- Copy/entry assumes fills at the posted ask at T with no latency and no market impact — optimistic;
  real execution (reacting after the underdog prints, lifting a thin favorite offer) is worse.
- 632-market / 15-test-day sample; the fade-underdog effect is strong and consistent but n_triggers is
  ~100 OOS — capacity and live depth are the binding unknowns, not statistical significance.
- Resolution from Gamma/UMA (the correct payout label). Persistence of the smart/dumb *rankings* is
  reused from the prior node and not re-derived here.
