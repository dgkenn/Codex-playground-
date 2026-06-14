# CRYPTO CROSS-VENUE / POLYMARKET SCOPE

**Question:** Is there a *realistic* path to a meaningfully bigger crypto edge than the
capacity-capped Kalshi 15-min BTC maker box (~$10–27/day ceiling) for OUR setup (cloud bot,
seconds latency, small capital, Kalshi + Polymarket API keys, no colocation)?

**VERDICT (one line):** **No.** Polymarket `btc-updown-5m` is *not* a deeper book — its headline
"depth" is a liquidity-mining mirage; executable touch depth is **~$5–60** and per-window volume is
**~$50**, an order of magnitude *thinner* than Kalshi. The cross-venue spread is not a clean,
capturable mispricing (different payoffs). This does not clear the realism bar; the Kalshi sleeve
remains the better vehicle. Concrete next step below.

Data: 93 snapshot files, **156,116 book snapshots across 794 5-min windows, 66 h span**
(2026-06-11 → 06-14), + live API probes on 2026-06-14. Backtests SCREEN only.

---

## 1. Polymarket `btc-updown-5m` characterization

| Metric | Value | Note |
|---|---|---|
| Tenor | 5 min | 3× faster cycle than Kalshi 15m |
| Tick | $0.01 | confirmed via Gamma `orderPriceMinTickSize` |
| Min order | 5 shares (~$2.5) | `orderMinSize`=5; rewards need `rewardsMinSize`=50 |
| UP spread | **median 1.0c**, mean 1.11c, 95.5% sit at exactly 1 tick | as tight as a 1c-tick market can be |
| Taker box cost (up_ask+down_ask) | mean **1.0111**, median 1.010, min 0.62 | overround ~1.1c |
| — frac < $1.00 (free arb) | **1.6%** | rare, tiny, and momentary |
| Maker box (sum of bids if BOTH fill) | mean **0.9889**, implied gross edge **~1.1c/box** | structurally identical to the Kalshi maker box |
| — frac sum_bids > 1.0 (crossed/neg) | 1.6% | |
| Headline "depth" up_bsz / up_asz | median **~40,000** / 39,500 shares | **MISLEADING — see below** |
| **Executable TOUCH depth (live probe)** | **best bid $5–63, median ~$11–27; best ask $5–42** | the real number |
| Per-window volume24hr (live) | **~$50–64** | the market barely trades |
| Fees | maker = **0** (rebate-eligible); taker ≈ 7% · p·(1−p) ≈ **1.75c** at p=0.5 | `fees.py`; gas on Polygon ≈ cents |

### The "deep book" is a liquidity-mining illusion (decisive finding)
The snapshot field `up_bsz`/`up_asz` is, per `pmkt_collect.book_top()`, the **SUM of size across ALL
book levels** (45–54 levels deep). It is **not** top-of-book. Live `/book` pulls show the touch holds
only **tens to a few hundred shares ($5–$63)**, while the whole-book sum is 6k–123k shares spread
across dozens of penny levels far from mid — classic Polymarket **reward-farming** behavior
(`rewardsMaxSpread`=4.5c, `rewardsMinSize`=50: bots park size to earn LP rewards, not to trade).

So the premise "deeper than Kalshi's ~33k" is **false at the level that matters**. Kalshi's 33k is
genuine top-of-book queue; Polymarket's ~40k is a stack of un-hittable far-from-touch quotes.
**Executable size: Polymarket ≪ Kalshi.**

### Does the Polymarket maker box have edge?
Mechanically yes — same ~1.1c gross structure as Kalshi, with the *advantage* of 0 maker fees. But
edge realization needs **both** legs to fill at the touch *without* adverse selection, and:
- Touch depth ~$11–27 per side ⟹ a filled box is ~$10–25 notional, *worse* than Kalshi's per-box size.
- Volume ~$50/window ⟹ ~1–2 boxes worth of natural taker flow per 5-min window to fill *against*.
- The 1.6% "free-arb" boxes are momentary and will be taken by faster bots before our seconds-latency
  cloud bot can act.

---

## 2. Cross-venue mispricing (Kalshi 15m vs Polymarket 5m)

| Measure | Result |
|---|---|
| Wall-clock overlap (staged) | ~40 h overlap exists |
| Matched pairs (±30s, mid-vs-mid) | 52,102 |
| Spread P_pm − P_k | mean **+2.4c**, std **31.8c**, \|mean\| **24.6c** |

**This is NOT a capturable mispricing.** The 24.6c \|spread\| and 31.8c std are not an arb signal —
they are an artifact of comparing **two different contracts**:
- **Kalshi 15m**: BTC settles *above a fixed strike* at the 15-min close.
- **Polymarket 5m**: BTC *up vs the window-open price* at the 5-min close.

Different reference price, different horizon, different moneyness ⟹ their implied P(up) legitimately
differ by tens of cents. There is no replicating portfolio that locks the difference, and the std
(32c) swamps any tradable edge after both venues' costs (Kalshi taker fee + Polymarket taker
~1.75c + gas + on-chain settlement latency). **No persistent, hedgeable cross-venue spread found.**

A true cross-venue lock would require *matched payoffs* (same strike, same close) — which these two
products do not share, and the Polymarket touch depth ($/window ~$50) could not support at scale even
if they did.

---

## 3. Polymarket 5m directional / fair-value efficiency

Using a terminal-mid outcome proxy (no settlement feed retrievable — Gamma drops settled `btc-updown-5m`
slugs, so real outcomes for our staged windows are unavailable), early-mid vs realized buckets look
roughly calibrated near 0.5 with apparent tails — but the apparent "gap" is dominated by the
mid-proxy bias (terminal mid pulled to extremes) and is **not** a clean favorite-longshot signal.
Even if a 2–5c taker edge existed at 0 fees, the **$11–27 touch depth and ~$50/window volume** cap any
directional taker strategy at nickels. Verdict: **mid is ~efficient; no exploitable taker gap at our
latency/size.** (Flagged: untestable rigorously without a settlement feed — see next step.)

---

## 4. Feasibility / capacity table

Assume best case = Polymarket maker box, 1.1c gross/box, 0 maker fees, but **constrained by touch
depth (~$20/side) and ~38 windows/day** (matching Kalshi's active-window count). Realistic fill of
*both* legs without adverse selection is generous at ~1 box/window.

| Bankroll | Kalshi 15m box (known) | Polymarket 5m box (this study) | Cross-venue arb |
|---|---|---|---|
| $100 | ~$10–27/day (saturates here) | **<$5/day** (depth/vol-capped) | ~$0 (no clean lock) |
| $1,000 | ~$27/day ceiling | **<$5–10/day** (same cap; capital can't be deployed) | ~$0 |
| $10,000 | ~$27/day (capital-idle) | **<$10/day** (capital-idle; touch can't absorb) | ~$0 |

Polymarket adds **frictions** Kalshi lacks: USDC-on-Polygon, gas per action, on-chain settlement
latency (seconds–minutes), and the 5-min cycle means more gas events per dollar of edge. Net: the
Polymarket box is a **smaller nickel sleeve than Kalshi**, not a bigger path. It does NOT clear the
$27/day Kalshi ceiling.

---

## 5. VERDICT + concrete next step

**There is no realistic *bigger* crypto edge here for our setup.** The attractive headline numbers
(40k "depth", 0 fees) evaporate under scrutiny: the depth is reward-farming quotes far from touch,
real touch depth is ~$11–27 and per-window volume ~$50, and the "cross-venue spread" is an
artifact of two non-matching payoffs, not an arb. Every Polymarket/cross-venue idea screened here
is **≤ a smaller nickel sleeve** than the Kalshi box, with added gas/settlement friction.

**What WOULD change the answer (concrete next step, in priority order):**
1. **Collect TOUCH depth + trade prints, not book sums.** Modify the collector to log
   best-bid/ask *size* and the CLOB `/trades` (or websocket fills) for each window. The single
   decisive unknown is *how much actually executes at the touch per window* — this study can only
   bound it from sparse live probes. ~1 week of touch+trade data answers "is there ANY scalable
   maker fill flow" definitively. **(Highest value, lowest cost.)**
2. **If (and only if) touch flow is materially > $50/window**, build a maker-box paper-trader with a
   real settlement feed (subscribe to the resolution / pull `outcomePrices` *before* slugs expire) to
   measure realized box edge after adverse selection and gas.
3. Do **not** pursue the Kalshi↔Polymarket "arb" — the payoffs don't match; it is not lockable.

**Recommendation:** Keep scaling the validated Kalshi box **by markets/windows, not by size or by
Polymarket.** Polymarket `btc-updown-5m` is a *signal* candidate at best (read-only toxicity proxy,
the original purpose of `pmkt_collect.py`), not a tradable scale path.
