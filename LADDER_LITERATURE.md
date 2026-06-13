# Strand-Handling Escalation Ladder — Literature Map, Gaps, Novel Rungs & Sequencing Principles

*Prepared 2026-06-13. Companion to LADDER_LOCKDOWN.md and PREVENT_BAD_TRADES.md.*

---

## 0. Framing: what the literature calls our problem

A Kalshi maker-box bot's "strand" is a **legged spread** (one leg of a two-leg position fills, the other doesn't), producing involuntary directional inventory. In the broader market-making literature this is studied under at least five overlapping lenses:

| Literature lens | Core question | Maps to our rung |
|---|---|---|
| Inventory management / dealer models (Ho-Stoll 1981, Avellaneda-Stoikov 2008, Guéant-Lehalle-Tapia 2013) | How should a market maker skew quotes and size positions to control inventory risk? | PREVENT + COMPLETE |
| Optimal execution / legging risk (Almgren-Chriss 2001, simultaneous combo orders) | How do you execute a multi-leg trade without absorbing directional risk between legs? | PREVENT (structural) |
| Adverse-selection / toxicity detection (Glosten-Milgrom 1985, VPIN/Easley-López de Prado 2011) | How do you identify and avoid informed flow before it picks you off? | PREDICT/GATE |
| Digital/binary option hedging (Stoikov-Saglam 2009, Baldacci-Bergault 2019) | How do you hedge residual directional exposure when replication is incomplete? | HEDGE |
| Prediction-market microstructure (Adverse Selection in Prediction Markets—Kalshi, Stanford Law 2026) | What are the specific fill and adverse-selection dynamics of binary event contracts? | all rungs |

---

## 1. Literature Survey — Strategies & Sequencing Principles per Lens

### 1.1 Inventory Management / Dealer Models

**Ho & Stoll (1981)** — "Optimal Dealer Pricing Under Transactions and Return Uncertainty," *Journal of Financial Economics*

The canonical inventory-control model derives optimal bid/ask quotes as a function of dealer risk aversion, inventory level, and volatility. Key principles:

- **Quote skewing (reservation-price skew):** The market maker shifts the midpoint of its quotes toward the side that reduces inventory. If the dealer is long (e.g., has a stranded YES leg), it lowers both bid and ask to attract sells. Skew magnitude scales with inventory size and volatility.
- **Prevention precedes reaction:** The dealer optimally adjusts quotes *before* accumulating inventory (preventive skew at order entry), not only after.
- **Spread widening:** Under high-volatility regimes, optimal spreads widen to reduce fill probability; under low-volatility, spreads tighten.
- **Size limits:** Optimal dealer stops quoting one side above an inventory threshold (equivalent to our max-net=1 rule, but continuously calibrated).

**Avellaneda & Stoikov (2008)** — "High-frequency trading in a limit order book," *Quantitative Finance*

Stochastic control formulation; closed-form reservation price and optimal spread:

- **Reservation price:** r(s,q,t) = s − q·γ·σ²·(T−t). With a strand (q≠0), the reservation price departs from mid. The key principle: **the moment inventory is non-zero, quote symmetry should break.** We should quote the completing side more aggressively than passive re-quote.
- **Optimal spread:** δ = γσ²(T−t) + (2/γ)·ln(1 + γ/k). Spread should widen with time-to-settlement and volatility—directly applicable to Kalshi contracts near expiry.
- **Inventory penalty:** Holding inventory costs γσ²q(T−t) per unit of time; this is the "strand cost clock" running from the moment of a strand—motivating urgency of completion over waiting.

**Guéant, Lehalle & Fernandez-Tapia (2013)** — "Dealing with the Inventory Risk: A solution to the market making problem," *Mathematics and Financial Economics*

Closed-form ODE solution with inventory boundaries:

- **Hard inventory limits** (quote withdrawal at ±N): When inventory hits the boundary, the market maker stops quoting the side that would increase it. In our context: after a strand, **immediately suppress further opens** on the same leg direction until the strand is resolved.
- **Size-dependent spread:** Optimal spread is approximately δ* ≈ γσ²(T−t) + O(q²), so **sizing should decrease quadratically with current inventory** (strand exposure).
- **Terminal urgency:** Near settlement (T−t → 0), the inventory cost dominates and the maker should cross the spread aggressively to flatten—confirming our "force-complete" escalation.

**Practical implication not in our ladder:** All three models implement **inventory-aware sizing** (position size ∝ 1/current_strand_exposure) as a continuous control, not a discrete streak-guard. We use a binary streak-guard; the literature suggests a continuous quadratic size reduction as a rung between PREVENT and COOL-OFF.

---

### 1.2 Optimal Execution and Legging Risk

**Almgren & Chriss (2001)** — "Optimal execution of portfolio transactions," *Journal of Risk*

The Almgren-Chriss framework decomposes execution cost into permanent impact, temporary impact, and timing risk. For a two-leg spread:

- **Simultaneous IOC execution eliminates legging risk by construction.** Futures and options exchanges routinely offer combo/spread orders that execute both legs atomically at the net price. If one leg doesn't fill, the entire combo is cancelled—no strand.
- **Sequential leg-by-leg entry exposes the trader to the full price-risk variance of the inter-leg delay.**
- **Urgency trades off:** Executing the completing leg faster reduces timing risk but increases market-impact cost. Almgren-Chriss gives the optimal speed schedule (TWAP/implementation-shortfall blends).

**Industry practice (Quantitative Brokers "Legger," patents 20150154701 / 20210224904):**

Practitioners solve legging risk by:
1. **Combo/spread orders (atomic):** Route both legs as a single net-price order; exchange matches them simultaneously. Zero legging window.
2. **IOC combo:** Immediate-or-cancel on the entire spread; if not filled at the net price instantly, cancel everything. No partial fills.
3. **Conditional second leg:** Fill first leg, immediately fire IOC/MKT for second leg, with pre-committed max slippage; if second leg misses by more than the slippage cap, immediately liquidate the first leg.

**Missing from our ladder:** Structural rung 0 exists in our brainstorm but is not formalized as a rung. The literature shows **simultaneous marketable (IOC combo) entry** is the industry's primary answer to legging risk—more powerful than any predictive gate, because it eliminates the legging window rather than predicting it.

---

### 1.3 Adverse Selection / Toxicity Detection

**Glosten & Milgrom (1985)** — "Bid, ask and transaction prices in a specialist market with heterogeneously informed traders," *Journal of Financial Economics*

The canonical adverse-selection model shows that:

- **Informed flow widens spreads to a break-even level.** Practitioners price in the adverse-selection cost; they don't try to "gate" every informed trade—they make the spread wide enough to profit on average even when sometimes picked off.
- **Quote withdrawal (not prediction) is the primary HFT response:** Modern HFT market makers cancel outstanding quotes within microseconds when they detect toxic flow (price momentum, sweep patterns), rather than predicting informativeness before the fact.
- **Selection vs. prediction:** The literature emphasizes that pre-trade prediction of which order is informed has very low accuracy. Post-detection cancellation is more reliable and faster.

**Easley, López de Prado & O'Hara (2011, 2012)** — "The microstructure of the 'Flash Crash'"; "Flow toxicity and liquidity in a high-frequency world," *Review of Financial Studies*

VPIN (Volume-Synchronized Probability of Informed Trading):

- **VPIN as a real-time toxicity signal:** Order imbalance computed over volume buckets. High VPIN → high adverse-selection probability → market maker should widen spreads, reduce size, or withdraw.
- **Regime-dependent response:** At low VPIN (normal market), provide full liquidity. At high VPIN, widen spread. At extreme VPIN, withdraw. This is a **three-state regime machine**, not a binary gate.
- **Applied to strands:** Our empirical finding that strands are autocorrelated (lag-1 = 2.6×, p=0.025) is consistent with VPIN's finding that adverse-selection episodes cluster. The streak guard is an approximation to a VPIN-style regime sensor; a proper flow-imbalance measure would be more continuous and earlier.
- **Key principle:** Quote adaptation should be *continuous and proportional* to toxicity, not a binary on/off gate.

**"Adverse Selection in Prediction Markets: Evidence from Kalshi" (Stanford Law 2026)**

Recent empirical work specific to Kalshi finds:
- Market makers earn twice as much per contract in single-name markets as in macro markets.
- The behavioral surplus (YES-overbet in markets that settle NO) cross-subsidizes adverse-selection losses.
- **Implication for box-makers:** Box arbitrage is less exposed to informed-flow adverse selection than directional market-making, because the payoff is bounded (box ≤ $1). However, the strand converts the box into a directional position, which IS fully exposed to adverse selection. Thus **strand prevention is also adverse-selection prevention in disguise.**

---

### 1.4 Digital/Binary Option Hedging

**Stoikov & Saglam (2009)** — "Option market making under inventory risk," *Review of Derivatives Research*

Three scenarios for residual risk in options market-making:

1. **Complete market (continuous delta hedge):** No inventory risk if you can delta-hedge continuously. Optimal quotes are independent of inventory.
2. **Illiquid underlying:** Cannot hedge continuously. Optimal quotes depend on net delta of inventory. The market maker must charge an illiquidity premium (wider spread) and skew quotes toward flattening delta.
3. **Incomplete market (stochastic vol, jumps):** Residual Vega and Gamma exposure remain. Optimal quotes depend on inventory's net Greeks.

**Applied to binary Kalshi contracts:** A stranded YES leg at price p has delta = p/(1-p) in terms of the binary payoff. The "delta" of a Kalshi binary at p=0.30 is fully 1 (either you gain $0.30 or lose $0.70 depending on settlement). Delta hedging with a correlated instrument (BTC perp) only hedges the BTC-correlated component of settlement, leaving the idiosyncratic event risk unhedged (basis risk). This explains our empirical finding that BTC explains only 1.7% of strand-loss variance—a direct prediction of the incomplete-market framework.

**DeltaQuants / practitioner overhedge:** Digital options are routinely "overhedged" via call spreads at 3–8% beyond the digital payoff level. The analogue for our bot: a **prophylactic overhedge** (hedge-before-strand, not after) would cost an expected premium in quiet markets but bound the tail loss. This is the "prophylactic vs. reactive hedge" distinction in our brainstorm.

**Baldacci & Bergault (2019)** — "Algorithmic Market Making for Options," *arXiv:1907.12433*

Options market makers solve a joint inventory-hedging control problem:
- **Hedge and quote jointly:** The optimal strategy skews quotes AND hedges residually—sequentially (skew first, hedge residual) in continuous time.
- **Hedge only when quote skew is insufficient:** If the underlying is liquid enough to hedge cheaply, hedge first; if expensive, skew quotes until natural offsetting flow arrives.
- **Regime dependence:** In illiquid regimes (wide underlying spread), rely more on quote skew; in liquid regimes, rely more on delta hedging.

---

### 1.5 Prediction Market Microstructure

**"A Microstructure Perspective on Prediction Markets"** (*ResearchGate 2024*)

Binary contracts' unique microstructure features:
- **Bounded payoff [0, $1]:** Unlike stocks, the position's maximum loss is known at entry. This caps inventory risk but makes the loss *absorbing* at settlement.
- **No continuous replication:** A binary option cannot be dynamically replicated without a correlated asset. The market maker must use **static hedges** (other contracts on the same event at adjacent strikes, cross-tenor, or cross-event).
- **Event clustering:** Binary contracts on related events (all BTC-related, all macro dates) cluster adverse-selection events. A "toxicity episode" hits the entire correlated book simultaneously.

**"The Mathematical Execution Behind Prediction Market Alpha" (Bawa, Substack)**

- Prediction market makers must manage **settlement-date inventory separately** from intraday inventory: holding a position to settlement converts a trading position into a binary bet.
- The optimal completion strategy is: **cross the spread to complete immediately if E[settle|strand] is adverse, hold if E[settle|strand] is unknown**—which maps to our finding that completing beats holding-to-settle in 74% of cases.

**"Trading Strategies for Prediction Markets" (Frenzy Capital, 2026)**

- Box spread (YES@k + NO@k) is the dominant maker strategy because it eliminates directional event risk.
- When a box is stranded, the residual is equivalent to a **long/short binary** with full event exposure.
- The correct response when stranded: (1) complete immediately if the completing price allows a net-positive or near-zero lock; (2) hedge with an adjacent strike if available; (3) cross entirely to flat.

---

## 2. Gap Analysis: What the Literature Suggests We're Missing

### Gap 1: QUOTE-SKEW / RESERVATION-PRICE as a Distinct Rung (between PREVENT and COMPLETE)

**What theory says:** Avellaneda-Stoikov, Ho-Stoll, and Guéant-Lehalle-Tapia all establish that **the moment inventory is nonzero, both bid and ask prices should shift asymmetrically** toward the completing side. This is a *continuous, proportional* control that operates simultaneously with quoting.

**What we have:** Our ladder has PREVENT (don't open) then COMPLETE (chase completion). We have no rung for *continuously skewing the completing quote more aggressively as a function of strand age and magnitude*, independent of the completion-chase mechanism.

**What's different from COMPLETE:** COMPLETE is about *how hard we chase* the second leg. Quote-skew/reservation-price is about *how we price our next box open* while the strand ages—skewing the new-open side to attract natural offsetting flow or reduce further same-side exposure.

**Proposed new rung:** **SKEW** — while a strand ages, adjust the reservation price for any new opens on the same side (don't open more same-direction; bias new opens toward the natural hedge side). This is distinct from PREVENT (which is binary) and from COMPLETE (which acts on the existing leg).

---

### Gap 2: CONTINUOUS INVENTORY-AWARE SIZING (between COMPLETE and COOL-OFF)

**What theory says:** Guéant-Lehalle-Tapia show that optimal size scales quadratically with current inventory level. Our streak-guard is a discrete 3-step binary (0.75→0.5→0.25) triggered by count, not by current exposure.

**What's missing:** A continuous sizing function: size_multiplier = f(current_strand_exposure, σ, τ), where size drops smoothly as outstanding strand exposure grows—not only after a fixed streak count. A single large strand should immediately reduce size; the current logic only acts after two or more strands.

**Proposed addition to COOL-OFF rung or as a distinct RESIZE rung:** Real-time exposure-aware sizing, e.g., size ∝ max(0.1, 1 − λ · |strand_exposure_¢|), calibrated to the variance of strand settlement outcomes.

---

### Gap 3: SIMULTANEOUS IOC ENTRY as a Structural Rung 0 (before PREVENT)

**What theory and practice say:** The entire options and futures industry solves legging risk with simultaneous combo/spread orders (IOC or exchange-matched). Our brainstorm lists "simultaneous two-sided marketable/IOC entry" as a structural candidate but it has not been elevated to a numbered ladder rung with a testing plan.

**Why it's higher-priority than a predictive gate:** A predictive gate with AUC 0.72 at best leaves 28% of strands unpredicted. Simultaneous entry reduces the legging *window* toward zero—no prediction needed.

**Kalshi-specific constraint:** Kalshi's API may not support native combo orders. But the bot can approximate by: (a) firing both legs within the same millisecond batch; (b) using IOC flags (cancel-if-not-filled-immediately) on both legs; (c) on a fill of leg 1, fire leg 2 as a market-order IOC immediately. If leg 2 misses, unwind leg 1 immediately rather than holding a strand.

**Proposed new rung 0:** **ATOMIC-ENTRY** — attempt IOC-combo entry (both legs simultaneously or within <10ms, with immediate unwind if the completing leg misses within N ms). This rung sits *before* PREVENT and would eliminate a large fraction of strands by shrinking the legging window.

---

### Gap 4: ADAPTIVE SPREAD-WIDENING / QUOTE-WITHDRAWAL as a VPIN-Gated Rung (between PREDICT and COMPLETE)

**What theory says:** Glosten-Milgrom and VPIN literature show that the proper response to detected toxicity is *proportional spread widening* (not binary withdrawal). In high-VPIN regimes, the maker widens spreads until the adverse-selection cost is covered; they don't simply stop quoting.

**What we have:** Our PREDICT rung is a binary gate (open or don't open). There is no rung for *spread widening proportional to real-time toxicity* (e.g., widen the box's edge requirement as a function of flow imbalance).

**Proposed new rung between PREDICT and COMPLETE:** **WIDEN** — when flow-imbalance / VPIN proxy exceeds a threshold (but below the full-gate threshold), widen the required lock margin before opening (e.g., require a 3¢ lock instead of the standard 1¢). This is a softer intervention than a gate and captures the continuous nature of adversity detection.

---

### Gap 5: CROSS-STRIKE / ADJACENT-CONTRACT HEDGE (inside HEDGE rung)

**What theory says:** Stoikov-Saglam (2009) and the binary option hedging literature both show that when the underlying hedge is unavailable or has high basis risk (BTC explains only 1.7% of variance), a **static hedge using adjacent-strike or cross-tenor contracts on the same event** is the correct alternative. A call spread (digital approximated by call spread) hedges the binary event payoff far better than a correlated continuous underlying.

**What we have:** Our HEDGE rung considers only BTC-perp. The cross-strike Kalshi hedge is mentioned in the brainstorm (section 5) but not analyzed or elevated.

**Proposed addition:** Within the HEDGE rung, implement a **cross-strike spread hedge**: on a stranded YES@k leg, sell YES@(k+1) or buy NO@(k+1) on the same contract. This creates a bull-spread cap on the stranded directional exposure at the cost of a small premium. Basis risk drops to near zero because both legs settle on the same binary event.

---

### Gap 6: OPTIMAL-STOPPING COMPLETION DEADLINE (inside COMPLETE rung)

**What theory says:** Optimal stopping theory (applied to execution: Almgren-Chriss, and the "negative drift of a limit order fill" literature) establishes that there exists a critical time T* beyond which the cost of waiting for a passive fill exceeds the cost of crossing the spread. We implement an escalating give, but have no formally derived T* for when to force-complete.

**What's missing:** A data-calibrated T* (time-since-strand → mandatory force-complete threshold) derived from the settlement hazard rate. As τ (time to settlement) shrinks, the inventory-holding cost in the Avellaneda-Stoikov formula rises sharply, and force-complete becomes unambiguously optimal.

**Proposed addition to COMPLETE rung:** Parameterize `--force-complete-age` = T* derived from: E[adverse settlement | strand age > T*] + E[completion cost at T*] < E[adverse settlement | hold to T+1]. Can be calibrated from the existing 323-window settlement tape.

---

## 3. Novel Ideas (beyond literature extrapolation)

### Novel Idea A: Strand-Side Asymmetric Completion (directional-aware COMPLETE)

The literature treats inventory as a scalar. But in our binary market, **the direction of the strand matters asymmetrically:** a stranded YES leg at p=0.30 faces expected loss of 0.70 if it settles YES and gain of 0 if it settles NO (net: losing position). A stranded NO leg at p=0.70 faces different odds. 

Novel proposal: **Condition completion urgency on the current implied settlement probability.** If p_strand < 0.5 (favorite strand—the stranded leg is the YES side and it's the underdog), the expected adverse settlement is p × $1, which is low → lower urgency, can wait for passive fill. If p_strand > 0.5 (favorite strand—the stranded YES has high implied probability), urgency is high → force-complete aggressively. This is a directional completion policy not present in the literature (which treats all inventory as symmetric).

### Novel Idea B: Autocorrelation-Weighted Kelly Sizing

Our finding that strands are autocorrelated (lag-1 = 2.6×) is directly usable in Kelly sizing. If the strand-probability conditional on the prior window being a strand is 2.6× baseline, then the Kelly-optimal bet size for the *next* window after a strand should be reduced by factor ≈ 1/2.6 ≈ 0.38, independent of the streak count. This is more nuanced than a streak guard (which uses count, not probability) and has a formal theoretical basis in Kelly (1956) / fractional Kelly.

**Proposed implementation:** Replace the fixed-step streak guard with a Bayesian posterior over P(strand | history), and set size = base_size × (1 − P_posterior). Resets naturally as the posterior decays on clean windows.

### Novel Idea C: Settlement-Hazard Triage (within COMPLETE rung)

Rather than treating all stranded legs as equally urgent to complete, triage by **time-to-settlement hazard rate**. Contracts near settlement (τ < 5 min) have high hazard; contracts with τ > 30 min have low hazard. Allocate completion-chasing resources (give budget, taker crosses) proportionally. This is implicit in Avellaneda-Stoikov's (T−t) factor but has not been operationalized in our bot.

### Novel Idea D: Strand Clustering / Venue-Level Pause

Our brainstorm and VPIN literature both note toxicity clustering. Novel proposal: track a **session-level strand rate** (strands per 10 windows). If session strand rate exceeds 3× the baseline (currently ~3.36%), trigger a full pause (no new opens for N windows), not just a scale-down. This is more aggressive than streak-guard (which scales down but continues) and directly analogous to exchange circuit breakers triggered by toxicity metrics.

### Novel Idea E: Predictive-Completion vs. Reactive-Completion Split

Current COMPLETE rung is purely reactive (fires after a strand is confirmed). Novel idea: **pre-warm the completing side** by placing a resting limit order on the completing leg *simultaneously with the opening leg*, with a price that would only fill if the spread moves adversely (i.e., the completing leg becomes achievable as a lock). This converts the strand-recovery problem into a conditional-simultaneous problem: if the opening leg fills AND the resting completing order fills, we have a full box. If only the opening leg fills, the resting order is still live and working. This is essentially the "quote BOTH legs improved" idea from the brainstorm but elevated to a principled strategy: it reduces the legging window for the *second* leg to near-zero because the completing order is already in the book.

---

## 4. Sequencing Principles: Is Prevent → Predict → Complete → Cool-Off → Hedge the Right Order?

### 4.1 Theory's verdict on the hierarchy

The literature is consistent on the priority hierarchy:

**Tier 1 (Structural):** Eliminate the legging window. Prevention by construction (atomic entry, both legs simultaneously) is dominant over all other rungs because it has *zero ongoing prediction cost* and eliminates the root cause rather than managing its consequences. Theory: Almgren-Chriss, combo-order literature.

**Tier 2 (Entry Selection):** Given that you cannot always enter atomically, entry selection (PREVENT + PREDICT) is next. Glosten-Milgrom and VPIN show that pre-trade information about toxicity is limited but real; using available signals (spread, flow, VPIN proxy) to gate entry is cheaper than all post-entry mitigations.

**Tier 3 (Continuous Inventory Adaptation):** Once in a strand, continuous inventory adaptation (SKEW + RESIZE, derived from Avellaneda-Stoikov / Ho-Stoll) is the cheapest post-entry response. These require no external hedging venue and operate within the same instrument.

**Tier 4 (Completion):** Active completion (COMPLETE) is the primary post-strand action confirmed by our data (complete beats hold 74% of the time). This maps to the Almgren-Chriss urgency schedule: the longer you hold inventory, the higher the timing risk, so cross the spread before settlement.

**Tier 5 (Risk control):** COOL-OFF / streak guard is pure risk control, not alpha. Theory (Kelly, VPIN regime-switching) suggests making it continuous/Bayesian rather than discrete. It belongs here because it doesn't reduce expected loss—it reduces variance of consecutive losses.

**Tier 6 (External Hedge):** External hedging (BTC perp, cross-strike) is the last resort because: (a) basis risk means it doesn't fully cover loss; (b) it requires an external venue and has its own execution risk; (c) at current size, Stoikov-Saglam theory predicts the hedge only pays when the underlying correlation is high and the hedge is liquid—both questionable for BTC perp as a proxy for Kalshi binary settlement.

### 4.2 Should any rungs MERGE?

**PREVENT and PREDICT should merge (or PREDICT should demote to a sub-strategy of PREVENT).** Both are entry-selection mechanisms operating before a position is opened. The distinction is signal-type (hard rule vs. model score), not lifecycle stage. The literature has one "entry selection" block that contains both rule-based and model-based filters in parallel.

**COOL-OFF and RESIZE should merge into a single RISK-CONTROL rung.** Both act after a strand to limit further exposure. Making them separate rungs overstates their independence; they should be parameterized jointly (streak count AND current exposure → combined size multiplier).

### 4.3 Should any rungs SPLIT?

**COMPLETE should split into two sub-rungs:**
- **COMPLETE-PASSIVE** (re-quote completing side, front-of-queue; ages 0–T*)
- **COMPLETE-ACTIVE** (force-cross at age T*; taker order at lock floor)

These have different cost profiles and the split forces explicit calibration of T*.

**HEDGE should split into:**
- **HEDGE-CROSS-STRIKE** (same instrument, near-zero basis risk, usable now)
- **HEDGE-PERP** (external venue, 1.7% variance explained, deferred to scale)

### 4.4 Regime-dependence: should order differ by regime?

**Yes, with two key regime splits:**

| Regime | Optimal emphasis |
|---|---|
| High-VPIN / high flow imbalance | PREVENT dominates; do not open at all; PREDICT gate tightens |
| Low-VPIN / thin spread / low σ | ATOMIC-ENTRY viable; open more freely; COMPLETE can be passive |
| Near-settlement (τ < 5 min) | COMPLETE-ACTIVE dominates; force-complete regardless of give; COOL-OFF irrelevant |
| Streak-in-progress | COOL-OFF + RESIZE dominate; PREVENT threshold tightens |
| Scale (>100 contracts/day) | HEDGE-PERP becomes cost-effective; add to bottom of ladder |

The theory does not support a single fixed ladder order across all regimes. However, the general priority (structural > entry-selection > continuous-adaptation > completion > risk-control > external-hedge) is robust across regimes; only *thresholds* within each rung shift by regime.

---

## 5. Ranked Testable Recommendations (feed to data phase)

Ranked by: (1) expected marginal gain over current baseline, (2) data availability, (3) implementation cost.

### Rank 1 — ATOMIC-ENTRY (Structural Rung 0): IOC Combo Approximation

**Rationale:** Eliminates legging window rather than predicting it. Almgren-Chriss / combo-order literature: the highest-value structural intervention. Even a 100ms reduction in the inter-leg window matters if strand-triggering moves happen on that timescale.

**Test spec:** Measure strand_rate and P(strand) as a function of inter-leg fill latency (leg1_fill_time − leg2_submit_time, in ms). Hypothesis: strand rate decreases monotonically with inter-leg latency. If confirmed, implement IOC both legs within <50ms batch, with immediate unwind if leg 2 misses by >N ms.

**Data needed:** Per-fill timestamp of leg1 vs leg2 submit/fill. Already in telemetry if we log fill timestamps at ms resolution.

---

### Rank 2 — CROSS-STRIKE HEDGE: Adjacent-Strike Kalshi Hedge for Stranded Leg

**Rationale:** Basis risk is near-zero (same event, same settlement). Stoikov-Saglam incomplete-market framework: when the underlying hedge has near-zero correlation with the residual risk, the correct hedge is a static position in the same event at an adjacent strike. Dramatically better than BTC perp (1.7% variance explained).

**Test spec:** On a simulated strand event, immediately sell YES@(k+1) or buy NO@k on the same Kalshi contract. Measure: net settlement P&L of (stranded YES@k + hedge NO@k or YES@(k+1)) vs. baseline unhedged strand. Hypothesis: cross-strike hedge reduces settlement-loss magnitude by >50% (vs. BTC perp's <5%). Back-test on the 323-window tape using recorded Kalshi book data.

**Data needed:** Simultaneous book snapshots for adjacent strike contracts at time of strand.

---

### Rank 3 — RESERVATION-PRICE SKEW RUNG (SKEW): Avellaneda-Stoikov Quote Asymmetry while Strand Ages

**Rationale:** Direct application of Avellaneda-Stoikov inventory skew. While a strand ages, skew new-open quotes to attract natural offsets: (a) suppress new opens on the strand side (already partially done by t36); (b) *actively improve quotes on the opposite side* to attract completing flow without chasing. This is the continuous-control analogue of our binary PREVENT gate.

**Test spec:** When a strand is active (age > 0), for any new open opportunity on the opposite-leg side, accept a 1–2¢ worse lock (lower profit threshold) vs. the standard gate. Measure: completion-rate of strands vs. control; net P&L impact of the incremental box fills at reduced margin. Hypothesis: skew-assisted completions increase strand-resolution rate by >20% without materially reducing net lock per box.

---

### Rank 4 — CONTINUOUS INVENTORY-AWARE SIZING (RESIZE Rung): Replace Discrete Streak Guard

**Rationale:** Guéant-Lehalle-Tapia ODE solution + Kelly framework. A continuous size function (size ∝ 1 − λ·|strand_exposure_¢|) is theoretically superior to a 3-step streak guard. Reacts to a single large strand immediately; recovers smoothly after resolution.

**Test spec:** Replace the fixed streak-guard steps (0.75/0.5/0.25) with size_mult = max(0.10, 1 − strand_exposure_¢ / exposure_cap_¢), where strand_exposure_¢ is the mark-to-mid value of current unresolved strands. Backtest: compare Sortino, max drawdown, and strand-streak loss distribution vs. current streak guard on the 323-window tape. Hypothesis: continuous RESIZE reduces max consecutive-strand drawdown by >15% vs. discrete streak guard.

---

### Rank 5 — BAYESIAN AUTOCORRELATION-WEIGHTED SIZE (Novel idea B, enhancement to RESIZE)

**Rationale:** Our empirical strand autocorrelation (lag-1 = 2.6×, p=0.025) provides a direct input to Kelly sizing. Using P_posterior(strand | history) as the sizing multiplier is more principled than a streak count.

**Test spec:** Implement an exponential-decay Bayesian posterior: P_post(t) = α · I(strand at t-1) + (1-α) · P_prior, with P_prior = strand_base_rate ≈ 0.034. Set size_mult = 1 − P_post(t)/P_prior_max. Backtest vs. current streak guard on 323-window tape. Hypothesis: Bayesian size achieves similar drawdown reduction with less volume lost on streaks that don't materialize.

---

### Rank 6 — T* FORCE-COMPLETE DEADLINE (Calibrated Optimal Stopping for COMPLETE rung)

**Rationale:** Almgren-Chriss urgency schedule + Avellaneda-Stoikov terminal urgency. The cost of holding a strand grows with decreasing time-to-settlement. There exists a calibratable T* (strand age in minutes) after which force-complete dominates waiting.

**Test spec:** From the 323-window tape, compute conditional E[settlement | strand_age = t] and E[completion_cost at give = g | strand_age = t] for t ∈ {0, 1, 2, 5, 10} minutes post-strand. Find T* = argmin_t E[settlement loss | hold to t+1] − E[completion_cost | force at t]. Hypothesis: T* exists and is in the range 2–5 minutes. If so, parameterize `--force-complete-age = T*` and test vs. current unbounded completion policy.

---

### Rank 7 — ADAPTIVE WIDEN (VPIN-Gated Spread Widening): Continuous Toxicity Response

**Rationale:** Glosten-Milgrom + VPIN literature. The continuous-toxicity response (proportional spread widening, not binary gate) is theoretically more efficient than a binary entry gate. It allows some opens in high-VPIN environments at a wider lock, rather than shutting down entirely.

**Test spec:** Compute a VPIN proxy (rolling 20-volume-bucket buy/sell imbalance) from the Kalshi order flow telemetry. When VPIN proxy > μ + 1σ, require lock_min = standard + 1¢; when > μ + 2σ, require + 2¢; when > μ + 3σ, apply full gate. Backtest: compare volume*edge vs. current binary gate on ≥300 windows with book-depth data. Hypothesis: adaptive widen captures 10–20% of opens currently blocked by the binary gate with no increase in strand rate.

---

### Rank 8 — SESSION-LEVEL STRAND-RATE CIRCUIT BREAKER (Novel Idea D)

**Rationale:** VPIN toxicity clustering + exchange circuit-breaker analogy. A session-level pause when strand rate > 3× baseline prevents correlated consecutive-strand losses from systematic market regime shifts (not just streak bad luck).

**Test spec:** Compute rolling 10-window strand rate. If > 3× base rate (>10%), pause all new opens for the next N windows (calibrate N). Measure: drawdown on "bad" sessions (strand rate > 10%) vs. control. Hypothesis: circuit breaker eliminates the fat left tail of session P&L without materially reducing total volume.

---

## 6. Revised Ladder Schematic (proposed)

```
Rung 0:  ATOMIC-ENTRY     — simultaneous IOC both legs; unwind if completing leg misses
Rung 1:  PREVENT          — t36 guarded-opener + hard entry rules (spread-floor, flow-gate)
Rung 1b: PREDICT/GATE     — GBM model gate (AUC 0.72, pending n≥300 forward deploy)
Rung 1c: WIDEN            — VPIN-proxy adaptive lock margin widening (continuous toxicity)
Rung 2:  SKEW             — Avellaneda-Stoikov quote asymmetry while strand ages
Rung 3:  COMPLETE         — completion-chase escalation ladder with calibrated T*
  3a: COMPLETE-PASSIVE    — re-quote completing side at front of queue (age 0 → T*)
  3b: COMPLETE-ACTIVE     — force-cross at T* (give sweep; taker IOC)
Rung 4:  RISK-CONTROL     — merged COOL-OFF + continuous RESIZE + Bayesian size
Rung 5:  HEDGE            — two sub-rungs:
  5a: HEDGE-CROSS-STRIKE  — adjacent Kalshi strike (near-zero basis, deploy now)
  5b: HEDGE-PERP          — BTC perp (deferred; only cost-effective at scale)
```

**Order verdict:** The general Prevent → Complete → Risk-Control → Hedge ordering is correct on first principles (prevention cheapest → completion avoids holding cost → risk-control bounds variance → hedging is last resort with basis risk). The key *additions* are Rung 0 (Atomic-Entry, which the literature says dominates all prediction-based approaches) and the SKEW rung (continuous inventory adaptation, which theory says should be continuously active throughout a strand). The PREDICT rung belongs inside PREVENT (both are entry-selection), not as an independent tier between PREVENT and COMPLETE.

---

## 7. Key Citations

1. **Avellaneda, M. & Stoikov, S. (2008).** "High-frequency trading in a limit order book." *Quantitative Finance*, 8(3), 217–224. — Reservation price formula; inventory skew; terminal urgency principle.

2. **Guéant, O., Lehalle, C.-A. & Fernandez-Tapia, J. (2013).** "Dealing with the inventory risk: a solution to the market making problem." *Mathematics and Financial Economics*, 7(4), 477–507. [arXiv:1105.3115] — Closed-form ODE with hard inventory limits; quadratic size reduction; quote withdrawal at boundaries.

3. **Easley, D., López de Prado, M. & O'Hara, M. (2012).** "Flow toxicity and liquidity in a high-frequency world." *Review of Financial Studies*, 25(5), 1457–1493. — VPIN real-time toxicity; regime-dependent liquidity withdrawal; clustering of adverse-selection episodes.

4. **Almgren, R. & Chriss, N. (2001).** "Optimal execution of portfolio transactions." *Journal of Risk*, 3(2), 5–39. — Legging risk decomposition; urgency vs. impact tradeoff; motivation for simultaneous combo execution.

5. **Stoikov, S. & Saglam, M. (2009).** "Option market making under inventory risk." *Review of Derivatives Research*, 12(1), 55–79. — Incomplete-market residual risk; basis risk of cross-instrument hedges; joint hedge+quote skew optimality.

6. **Glosten, L. & Milgrom, P. (1985).** "Bid, ask and transaction prices in a specialist market with heterogeneously informed traders." *Journal of Financial Economics*, 14(1), 71–100. — Adverse-selection spread; quote withdrawal as primary defense; information asymmetry not fully predictable pre-trade.

7. **"Adverse Selection in Prediction Markets: Evidence from Kalshi."** Stanford Law School, Legal Aggregate, April 2026. — Kalshi-specific: behavioral YES-bias surplus; twice the per-contract earnings; strand = conversion of box to fully adversely-selected directional position.

8. **Glosten, L. & Milgrom, P. / DeltaQuants practitioner note on digital overhedging.** http://www.deltaquants.com/managing-risks-of-digital-payoffs-overhedging — 3–8% overhedge for digitals; call-spread approximation; cross-strike is preferred to delta hedge for binaries.

9. **Quantitative Brokers "Legger" / Patents US20150154701 & US20210224904.** — Industry-standard simultaneous combo execution; IOC spread orders; conditional second-leg market order.

---

*Document ends. Feed ranked recommendations (§5) to the data-phase backtesting queue in LADDER_LOCKDOWN.md Phase B/C.*

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
