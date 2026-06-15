# Sports arbitrage — cross-book + Kalshi-vs-sportsbook (2026-06-15)

Can a US small bankroll lock guaranteed profit via cross-book "sure betting" or Kalshi-vs-sportsbook
arb/middling? Verdict: **cross-book arb is real but limiting-killed and tiny; Kalshi-vs-book is a small
+EV VALUE edge (Kalshi is structurally cheaper), NOT a reliable locked arb — marginal after fees/thinness.
The can't-ban Kalshi leg helps structurally but does not create capacity. Promo extraction dominates.**

## Cross-book sure-betting
- Real arbs appear (1-3%, occasionally larger), but **close in minutes** and require bots/tools ($59-99/mo OddsJam/ArbBets).
- **Arbers are detected fast** (win-rate >50%, oddly-specific stake sizes e.g. $102.57, frequent dep/withdraw, post-bet line moves, shared cross-operator integrity servers) -> max stakes "drastically reduced," accounts limited/voided **within days-to-weeks**.
- Realistic: a few hundred $/month before limiting on the soft-book leg; **not sustainable** (same wall as value-betting). The biggest % arbs live in niche markets = the LOWEST limits.

## Kalshi-vs-sportsbook (the novel can't-ban angle)
- **Kalshi is structurally CHEAPER**: measured ~0.85% effective vig vs 4-8% sportsbook hold; Kalshi normalizes to ~100% (no embedded margin) vs books' 104-108%. So there are frequent **small +EV "buy-Kalshi" edges (2-6c)** where Kalshi's price is below the de-vigged book consensus.
- **BUT that's a VALUE bet, not a locked arb** — and it's the same thing SHARP_VS_KALSHI.md found: on LIQUID games Kalshi is SIG-priced/efficient (1-3c spread), so the "edge" is largely the vig difference already in the price; the deviation rarely clears the spread+fee as a true lock.
- **True both-sides locked arb is rare/thin/fee-eaten**: a 3% gross arb -> 1-2% net or a LOSS after Kalshi's fee (peaks ~1.75% near 50c, exactly where moneylines trade) + book spread; **partial fills are the #1 failure mode** (Kalshi fills 60/100, the book leg dries up -> you're naked directional). Vendors selling Kalshi arb/middle tools (OddsAssist $19.99/mo, ArbBets $59/mo) conspicuously **refuse to publish ROI** and post profitability disclaimers — a strong tell.
- **The can't-ban Kalshi leg is genuine** (exchange/fee model; no documented ban-for-winning) — you keep the winning Kalshi side while the book limits the other leg. BUT: capacity is thin (~$10k/order on liquid, $25k default position limit), and there's a **settlement-carveout counter-risk** (Khamenei "death carveout" ~$54M case voided correct directional holders).
- Reality check both ways: the Knicks Game-4 comeback showed retail CAN beat the SIG makers on a big swing (makers lost ~$22M) — but that's **variance, not a systematic edge**.

## Trait scores (1-5, 5 favorable)
Recreational-flow **2** · ¬HFT **3** · fair-value/skill **3** · access **4** · ¬ban **4** (Kalshi leg) /**1** (book leg) · small-cap **3** · **+EV-net 2** (fees + partial-fill + limiting + thinness).

## VERDICT
Not a deployable income edge for a small bankroll. Cross-book arb is real but the soft-book leg gets you
limited within weeks; Kalshi-vs-book is a small value edge (buy the structurally-cheaper Kalshi side) more
than a locked arb, and it's marginal after fees, thin capacity, and partial-fill risk. Kalshi's can't-ban
property is a genuine structural plus but doesn't manufacture capacity or clear the cost on liquid games.
Within sports, **promo extraction (SPORTS_PROMO_EV.md) dominates** as the one deployable play; the one
forward experiment remains the Kalshi maker timing-lag (collector armed, SPORTS_CLV_SETUP.md).
