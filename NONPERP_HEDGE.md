# Non-Perp Hedge Study: BTC 15-min Maker-Box Strand (2026-06-13)

*Companion to LADDER_LOCKDOWN.md (HEDGE-RUNG PIVOT) and PERP_HEDGE.md*

---

## Structural Reality (stated)

**KXBTC15M is a SINGLE-STRIKE up/down binary per 15-min window.** There is NO same-event adjacent
strike, so a same-event vertical/cross-strike hedge is structurally IMPOSSIBLE. The literature's
cross-strike "digital replicated by call spread" (Stoikov-Saglam; DeltaQuants) does not apply.

The BTC perp R^2 vs strand loss is only **1.7%** — it hedges the smooth spot move, but the strand
loss is dominated by the **binary settlement jump** (res = 0 or 1), not the continuous BTC drift.
This is the core analytical challenge: no correlated continuous instrument reliably predicts a
single Bernoulli outcome.

---

## Data Used

| Dataset | Count |
|---|---|
| BTC 15-min windows (hist + trades) | 920 common |
| ETH 15-min windows (hist + trades) | 2,385 common |
| BTC+ETH aligned windows | 574 |
| BTC strand events (total) | 579 (YES: 321, NO: 258) |
| BTC strands with concurrent ETH | 354 valid |

Unhedged strand baseline: **mean = −12.90¢/strand, std = 37.41¢, total = −7,470¢**

---

## Candidate Enumeration

### Candidate 1 — Cross-Asset Binary: ETH 15-min (PRIMARY)

**Hypothesis:** BTC/ETH spot correlation (~0.85) implies their 15-min binary settlements are
co-directional more often than random. When a BTC strand occurs (BTC settled adversely),
placing an ETH binary position in the SAME window in the co-directional direction should
generate an offsetting payoff.

**Mechanics:**
- YES-strand (bought BTC-YES, BTC settled DOWN): → buy ETH-NO on concurrent ETH 15-min
- NO-strand (sold BTC-YES = bought BTC-NO, BTC settled UP): → buy ETH-YES on concurrent ETH 15-min
- Size: h_opt = 0.368 of position ($5 ETH binary on a $5 BTC strand)
- Entry: taker-cross at k+1 minute; hold to same-window settlement

**Test results (n=354 strand events with concurrent ETH data):**

```
Metric                          Value
----------------------------------------
ETH/BTC co-directional rate     69.2% (random baseline: 50%, theory ~82% at ρ=0.85)
R^2 (ETH binary vs BTC loss)    18.63%     [vs perp: 1.7%]
Regression p-value              < 0.0001
Optimal hedge ratio h_opt       0.368
```

**Hedge ratio sweep (at h_opt = 0.368):**

| h     | Mean residual | Std residual | Std reduction | Mean reduction |
|-------|--------------|-------------|--------------|----------------|
| 0.000 | −11.26¢      | 36.41¢      | 0.0%         | 0.0%           |
| 0.250 | −8.04¢       | 33.23¢      | 8.7%         | 28.6%          |
| 0.368 | −6.52¢       | 32.85¢      | **9.8%**     | **42.1%**      |
| 0.500 | −4.81¢       | 33.33¢      | 8.5%         | 57.2%          |
| 0.750 | −1.59¢       | 36.69¢      | −0.8%        | 85.9%          |
| 1.000 | +1.63¢       | 42.54¢      | −16.8%       | n/a (overshoots mean) |

h=1.0 flips sign (over-hedges, adds variance); h_opt=0.37 is the sweet spot.

**By strand side:**

| Side      | n   | Unhedged mean | ETH hedge mean | Corr(ETH_pnl, BTC_loss) | Hedged mean (@h_opt) |
|-----------|-----|--------------|---------------|--------------------------|----------------------|
| YES-strand| 182 | −11.76¢      | +12.22¢       | −0.366                   | −7.27¢               |
| NO-strand | 172 | −10.72¢      | +13.59¢       | −0.499                   | −5.73¢               |

**IS/OOS split (60/40):**

| Split | n   | R^2    | Std reduction |
|-------|-----|--------|---------------|
| IS    | 212 | 19.44% | 10.2%         |
| OOS   | 142 | 16.23% | 8.3%          |

OOS holds up at 8.3% std reduction — not a pure in-sample artifact.

**Cost:**
- ETH bid-ask spread: mean 2.12¢, median 2.00¢
- Taker half-spread (entry cost): ~1.06¢ per $1 ETH position
- $5 ETH hedge position: entry cost ~5.30¢
- Strand mean loss: −12.90¢ (unhedged), −7.70¢ (hedged @ h_opt)
- Net benefit per strand: ~4.7¢ improvement in mean − 5.3¢ entry cost = **~−0.6¢ net after cost**
- At h=0.25 (smaller position): entry cost ~2.65¢, benefit ~3.2¢ = **~+0.5¢ net** (marginally positive)

---

### Candidate 2 — Cross-Tenor / Daily KXBTC Ladder

**Method:** Analytical from spot_path data. Model daily/hourly binary settlement correlation
with the 15-min binary that caused the strand.

**Results:**

```
Tenor            P(align with 15m strand)   Expected R^2
Daily BTC binary       54.1%               ~0.66%   (WORSE than perp)
Hourly BTC binary      69.1%               ~14.66%  (model, not directly tradeable)
Daily KXBTC ladder     <54% (different settlement)  ~0.1%
```

**Key finding:** R^2(15-min spot move vs strand loss) = **0.13%**, confirming the strand loss
is almost entirely in the binary jump (not the spot drift). The daily binary settles on the FULL
day's move; a single 15-min event has negligible effect on daily settlement. Cross-tenor hedges
have **WORSE basis than the perp**.

**Verdict: NOT VIABLE.** Daily binary basis is nearly random (54% alignment = only 4% above chance).

---

### Candidate 3 — Other Intra-Kalshi Offsets

| Option | Assessment |
|---|---|
| Same-event adjacent strike (vertical) | **STRUCTURALLY IMPOSSIBLE** — KXBTC15M is single-strike |
| SOL/XRP 15-min binary | SOL/XRP strand rate 40-106%; creates new strand risk; worse correlation than ETH |
| Kalshi macro binary (Fed, S&P) | Different event; correlation << 0.85; worse than ETH by factor 10x+ |
| Cross-venue (Polymarket, Manifold) | Venue arbitrage, not hedge; same basis problem; latency |
| BTC Perp (reference) | R^2=1.7%, scale-gated ($6 min vs $5 box) — see PERP_HEDGE.md |

---

## Basis Table — All Candidates

| Candidate                | Basis R^2 | Std-Reduc% | Mean-Reduc% | Entry cost ($5) | Feasible@$5? |
|--------------------------|-----------|------------|-------------|-----------------|--------------|
| ETH 15m binary (h=0.368) | **18.63%**| **9.8%**   | **42.1%**   | ~5.3¢           | YES          |
| ETH 15m binary (h=0.25)  | 18.63%    | 8.7%       | 28.6%       | ~2.65¢          | YES          |
| Cross-tenor hourly        | ~14.7%    | <2%        | <2%         | N/A (not available) | NO     |
| Cross-tenor daily         | ~0.7%     | <1%        | <1%         | N/A             | NO           |
| Daily ladder spread       | ~0.1%     | <1%        | <1%         | N/A             | NO           |
| Same-event adjacent strike| N/A       | N/A        | N/A         | N/A             | **IMPOSSIBLE** |
| SOL/XRP 15m binary       | <10%      | negative   | negative    | spreads wider   | NO           |
| Macro binary              | <1%       | <1%        | <1%         | N/A             | NO           |
| BTC Perp (**reference**)  | 1.7%      | <5%        | <5%         | ~$0 (0% fees)   | NO ($6 min)  |

---

## Optimal Non-Perp Hedge

**VERDICT: ETH 15-min binary is the OPTIMAL non-perp hedge.**

- R^2 = **18.63%** vs perp's 1.7% → **11× better basis than perp**
- Std reduction = **9.8% (IS: 10.2%, OOS: 8.3%)** vs perp's <5% → **~2× better than perp**
- Structurally sound: binary-to-binary, same timeframe, Kalshi-native, no venue build needed
- IS/OOS stable: R^2 decays only modestly IS→OOS (19.4% → 16.2%)

**Why it works better than the perp:** The ETH binary payoff directly captures part of the
binary settlement event (co-directional 69.2% of the time). The perp only captures the
continuous spot move, which explains <2% of the binary settlement jump.

**Why it's still limited:** The 69.2% co-directional rate (vs 82% theoretical from ρ=0.85
via binary copula) reflects genuine divergence — the strand-triggering event is often a
BTC-idiosyncratic move. The residual 30.8% of windows where ETH goes the "wrong way" creates
a HEDGING LOSS that counteracts the 69.2% benefit.

---

## Does ETH Hedge Beat the Perp?

| Metric | ETH 15m Binary (h=0.368) | BTC Perp (reference) |
|--------|--------------------------|----------------------|
| R^2 | **18.63%** | 1.7% |
| Std reduction | **9.8% (OOS: 8.3%)** | <5% |
| Mean reduction | **42.1%** | <5% |
| IS/OOS stability | OOS = 16.2% R^2 | n/a (deferred) |
| Entry cost ($5 hedge) | ~5.3¢ (taker) | ~$0 (0% fees) |
| Net benefit after cost | ~−0.6¢/strand @h_opt; **+0.5¢ @h=0.25** | positive @scale |
| Feasible at $5 size? | YES | NO ($6 min) |

**ETH binary BEATS the perp on all basis metrics (R^2, std reduction).** The perp's advantage
is zero entry cost; the ETH binary has a ~2¢ spread cost per $1 position.

---

## Net-Cost-After-Hedge Analysis

```
At h=0.368 ($5 ETH position):
  Mean strand loss (unhedged):  −12.90¢
  ETH hedge mean benefit:       +4.74¢ (mean improvement @ h_opt)
  ETH entry cost:                −5.30¢ (taker half-spread × 5)
  Net after hedge cost:         −0.56¢  [MARGINAL, essentially break-even]

At h=0.25 ($2.50 ETH position):
  Mean strand loss (unhedged):  −12.90¢
  ETH hedge mean benefit:       +3.22¢ (benefit @ h=0.25)
  ETH entry cost:                −1.33¢ (taker half-spread × 2.5)
  Net after hedge cost:         +1.89¢ per strand  [POSITIVE but small]

At h=0.25, assuming ETH maker fill (half-spread cost = 0):
  Net benefit:                  +3.22¢ per strand  [CLEARLY POSITIVE]
```

**Key insight:** At h=0.25 with maker execution on ETH, the ETH binary hedge is
**net-positive**. At current taker prices, it is marginal. The ETH maker spread
(~1¢/side) matters crucially.

---

## Deploy Rule at Current ~$5 Size

**Trigger:** BTC strand detected (one box leg fills, other does not, within the fill minute).

**Hedge execution:**

```
IF YES-strand (BTC-YES filled, BTC settled/settling DOWN):
    => Enter ETH-NO on the current ETH 15-min window
    => Price: maker bid on ETH-YES (NO = 1 - YES) OR taker-cross if ETH-NO ask available
    => Size: min(2 contracts, available ETH liquidity) at $1 min per contract
    => Hold to ETH 15-min window settlement

IF NO-strand (BTC-YES sold/BTC-NO filled, BTC settled/settling UP):
    => Enter ETH-YES on the current ETH 15-min window
    => Price: maker ask on ETH-YES OR taker-cross if ETH-YES bid available
    => Size: min(2 contracts, available ETH liquidity) at $1 min per contract
    => Hold to ETH 15-min window settlement
```

**Sizing rule:** h=0.25 (hedge 25% of strand notional = 1-2 ETH contracts on a $5 strand).
This balances hedge benefit vs entry cost. At h_opt=0.368, the benefit is slightly higher but
entry cost at taker prices makes it marginal. Use maker orders when possible.

**Preconditions:**
1. ETH 15-min market must be ACTIVE in same window (ws must exist in ETH data)
2. ETH quote must be valid at k+1 minute (mid in [0.03, 0.97])
3. ETH market must have available liquidity for $1-2 contracts
4. BTC strand must be detected EARLY in the window (k ≤ 10) — too late to hedge at k=12+

**Operational constraints:**
- Not every BTC window has concurrent ETH activity (574 of 920 BTC windows = 62% overlap)
- ETH thin-market risk: ETH strand rate is ~40% (multi_asset_study.py) — taking an ETH
  position also exposes us to ETH binary risk (but at only 1-2 contracts, contained)
- Net ETH position (from hedge) may itself become a new "strand" if ETH is thin

---

## Honest Limitations

1. **Hedge partially works but doesn't neutralize:** R^2=18.6% means 81.4% of strand-loss
   variance is UNHEDGED. The std reduction is only ~10%. The binary settlement jump remains
   fundamentally hard to hedge across correlated events.

2. **Cost sensitivity:** ETH's 2¢ spread makes the hedge marginal at taker prices. Only viable
   as a consistent strategy if ETH maker fills are achievable (the ETH book is thinner than BTC).

3. **ETH strand exposure:** The hedge position itself (ETH binary) could strand if ETH market
   is thin. This is a secondary risk to manage (keep ETH hedge size small, ≤2 contracts).

4. **No same-event adjacent strike:** The highest-R^2 theoretical hedge (same binary event,
   adjacent strike) is structurally impossible. ETH is the best available substitute.

5. **OOS decay:** IS R^2=19.4% → OOS R^2=16.2%. Small but measurable degradation. Monitor.

---

## Final Conclusion

| Verdict | Recommendation |
|---------|---------------|
| **Optimal non-perp hedge** | **ETH 15-min binary at h=0.25 with maker orders** |
| Beats perp R^2? | **YES: 18.63% vs 1.7%** (11× better) |
| Beats perp std-reduction? | **YES: 9.8% vs <5%** (~2× better) |
| Net-positive after cost? | YES at h=0.25 with maker execution; break-even at taker |
| Deploy at $5 now? | **CONDITIONAL YES** — only when ETH window is concurrent and liquid |
| Cross-tenor viable? | **NO** — daily R^2 < 0.7%, worse than perp |
| Same-event vertical? | **IMPOSSIBLE** — single-strike instrument |
| Better than PREVENT/COMPLETE? | **NO** — ETH hedge is a partial residual reducer; PREVENT (t36) + COMPLETE (give=0.02) + RISK-CONTROL (streak guard) remain the primary rungs |

**The ETH binary hedge is the correct Rung 5a (non-perp, deployable now) to add to the
ladder when BTC strand events align with concurrent ETH windows.** It does not replace the
prevent/complete/risk-control stack — it reduces the residual loss for the ~62% of strands
that have a concurrent ETH market, by ~10% in variance and ~42% in mean at h_opt (or ~28%
mean at h=0.25 with lower entry cost).

**The BTC perp (Rung 5b) remains the at-scale option** — lower cost (0% fees), better
size-matching at scale — but is scale-gated at current $5 size.

---

*Study: nonperp_hedge_study.py | Data: hist/trades_kalshi_{btc,eth}15m.parquet | n=354 strand events*

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
