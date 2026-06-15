# US sports-betting EXCHANGES as a small-bankroll edge (2026-06-15)

Follow-up to `SPORTS_BETTING.md`. That study found the sports edge is **real on soft books but they
ban winners**, the sharp venues that don't ban (Pinnacle/Betfair) are **US-illegal**, and **Kalshi**
sports can't ban you but its liquid games are **SIG-priced/efficient**. The open question it did not
answer: do **US-regulated betting exchanges** (Sporttrade, Prophet X, et al.) — maker/two-sided,
recreational flow, no incentive to ban — close the loop?

**TL;DR VERDICT (details §6): DEAD END as of June 2026 — killed by VENUE COLLAPSE, not by signal.**
The exchanges genuinely **escape the ban wall** (peer-to-peer; the operator earns commission on volume,
so a winner is an asset, not a threat — they explicitly market "no limits on winners"). That part is
real and is the one thing soft books can't offer. **But every other leg of the brutal bar fails right
now:**

1. **Sporttrade — the one true CFTC-track regulated real-money exchange — is SHUTTING DOWN.** It
   announced (May 15, 2026) it is **exiting US real-money sports betting**: New Jersey access ended
   **May 25, 2026**; AZ/CO/IA/VA have until **June 25, 2026** to withdraw funds, all access gone
   **June 26, 2026**. It is awaiting CFTC Designated Contract Market approval to relaunch as a
   prediction market — timeline "months to years," nothing tradable today.
   ([gambling.com](https://www.gambling.com/us/news/sporttrade-exits-us-sports-betting-market-in-pivot-to-prediction-markets),
   [Finance Magnates](https://www.financemagnates.com/forex/sporttrade-exits-sports-betting-to-rebuild-around-prediction-markets-under-cftc-oversight/),
   [Sportico](https://www.sportico.com/business/sports-betting/2026/sporttrade-prediction-market-regulation-state-cftc-1234882662/))
2. **Prophet X / Novig / BetOpenly are SWEEPSTAKES models, not regulated real-money exchanges** — and
   the sweepstakes model is **being dismantled state-by-state** (cease-and-desist in AZ, banned in CA
   eff. Jan 1 2026, blocked in NY, restricted in NJ/CT/MT). They are all also racing for CFTC approval
   and plan to phase out sweepstakes. ([Sportico/ProphetX-CFTC](https://www.sportico.com/business/sports-betting/2025/prophetx-prediction-market-cftc-sweepstakes-1234876170/),
   [Yogonet NY ban](https://www.yogonet.com/international/news/2025/12/08/116669-new-york-imposes-prohibition-on-sweepstakes-casinos-and-sportsbooks),
   [Closing Line AZ C&D](https://closingline.substack.com/p/news-arizona-sends-cease-and-desist-sweepstakes))
3. **Liquidity is thin off the flagship leagues** on every one of them — the same soft↔thin / deep↔sharp
   wall the Kalshi study hit.

So the structure that *would* have unlocked the edge (regulated exchange that can't ban you) **existed
in Sporttrade and is being decommissioned this very month**; the survivors are legally fragile
sweepstakes that may be banned in your state by the time you build anything. **Not deployable now.**
The only thing worth watching is the **CFTC-regulated relaunches** (Sporttrade/Novig/ProphetX as DCMs),
which would land in the *same regulatory bucket as Kalshi* — and Kalshi sports is already shown
efficient. **Net: the ban wall is escapable, but there is no surviving venue + edge + liquidity + legal
access combination in mid-2026.**

---

## 1. STRUCTURE & ACCESS, per exchange

### Sporttrade (the only genuine state-regulated real-money exchange) — NOW EXITING
- **Mechanism:** stock-exchange-style. Contracts priced **0–100** ("probability odds"); each winning
  share pays $100, so a $42 price = 42% implied prob, $58 profit if it hits. **Limit orders**
  supported (set a price, fill only if reached); two-sided (buy/sell a position before settlement to
  lock gains or cut losses). Markets: moneyline/spread/totals on the major US leagues (NFL/NBA/MLB/NHL)
  plus some others. ([oddsassist](https://oddsassist.com/sports-betting/sportsbooks/sporttrade/),
  [sportshandle](https://sportshandle.com/sporttrade/), [Sporttrade Advantage](https://new.getsporttrade.com/sporttrade-advantage))
- **Fee:** **2% commission on profitable trades only** (none on losers). Tighter lines than soft books —
  ~10c lines at ~−105 vs the typical 20c at −110. ([oddsassist fees](https://oddsassist.com/sports-betting/sportsbooks/sporttrade-fees/))
- **States (while live):** NJ (Sept 2022), CO (Aug 2023), AZ + VA (2024), IA. Min first deposit ~$5.
  ([Sporttrade where-available](https://sporttrade.zendesk.com/hc/en-us/articles/4410576091675-Where-Sporttrade-is-available),
  [rotowire](https://www.rotowire.com/betting/sporttrade-promo-code))
- **STATUS (decisive):** announced exit May 15 2026. **NJ closed May 25 2026; AZ/CO/IA/VA withdrawal
  deadline June 25, all access gone June 26 2026.** CEO Alex Kane: the state-by-state regulated model
  "really hurt the business … pinned our business down." Filed CFTC DCM + DCO applications Feb 2026;
  CFTC posted them Feb 4 2026; approval "could take months — if not years." Until then there is
  **nothing to trade.** ([gambling.com](https://www.gambling.com/us/news/sporttrade-exits-us-sports-betting-market-in-pivot-to-prediction-markets),
  [Yogonet](https://www.yogonet.com/international/news/2026/05/19/121042-sporttrade-to-exit-us-online-sports-betting-markets-while-awaiting-cftc-decision),
  [Sportico](https://www.sportico.com/business/sports-betting/2026/sporttrade-prediction-market-regulation-state-cftc-1234882662/))

### Prophet X — SWEEPSTAKES exchange (not regulated real-money)
- **Mechanism:** peer-to-peer matching; users post or accept offers, **back-and-lay** supported. Pricing
  adjusted with +/− buttons (not a clean limit-order book) in **American odds**, not 0–100.
  **Sweepstakes wrapper:** you buy "Prophet Cash"; winnings redeemed as sweepstakes prizes — "since
  you're never placing a direct real-money wager, the entire experience is treated as a sweepstakes."
  ([oddsassist ProphetX](https://oddsassist.com/prediction-markets/prophetx/),
  [oddsshopper](https://www.oddsshopper.com/articles/betting-101/what-is-prophetx-sports-betting-what-to-know-about-prophet-x-y10))
- **Fee:** **2–3% commission on net winnings only**; no payout fees, no vig in odds.
- **"States":** marketed as ~39–40+ states via the sweepstakes structure — but **excluded/ceased** in
  AZ (cease-and-desist), CA (banned Jan 1 2026), CT, ID, LA, MI, MT, NV, NJ, NY (access blocked), TN, WA.
- **Ban policy:** does **not** restrict/ban winners (peer-to-peer). ([legalsportsreport](https://www.legalsportsreport.com/prediction-markets/prophetx-promo-code/))
- **STATUS:** applied for CFTC approval, "expects to ditch sweepstakes," undecided on timing.
  ([Sportico](https://www.sportico.com/business/sports-betting/2025/prophetx-prediction-market-cftc-sweepstakes-1234876170/))

### Novig — SWEEPSTAKES exchange transitioning to CFTC
- Peer-to-peer; Novig Coins (free) / Novig Cash (redeemable for real money). **Commission ~1–4% when
  acting as maker.** Explicitly markets **"no limits on winners."** ~42 states + DC under sweepstakes.
- Raised $75M Series B (Pantera); claims **$4B annual trading volume, 100k+ users** (10× YoY) — the
  most liquid of the sweepstakes set. Filed CFTC DCM application; plans to phase out sweepstakes within
  ~6 months pending approval. ([legalsportsreport Novig](https://www.legalsportsreport.com/prediction-markets/novig-promo-code/),
  [DeFi Rate](https://defirate.com/news/novig-raises-75m-positions-cftc-regulated-exchange-as-future-of-sports-betting/),
  [Covers](https://www.covers.com/industry/novig-seeks-cftc-approval-to-operate-prediction-markets-jan-26-2026))

### BetOpenly — real-money peer-to-peer, ~1% fee, 45+ states; small/early. Fliff — sweepstakes, 5–10%
vig (essentially a soft book in sweeps clothing — no edge). ([bettoredge roundup](https://www.bettoredge.com/post/best-betting-exchanges-in-the-us))

---

## 2. THE BAN-POLICY FINDING (the one thing that works)

**Exchanges genuinely do not ban/limit winners — confirmed across sources, and the economics back it.**
On a peer-to-peer exchange a winner's profit comes from the **counterparty**, not the house; the
operator earns **commission on volume**, and sharp money *improves* prices, attracts counterparty flow,
and deepens the book — "for a bookmaker your profitability is a threat; for an exchange it is an asset."
Sporttrade ("will never limit you"), Novig ("no limits on winners"), and ProphetX ("does not restrict
successful traders") all market this explicitly.
([gamblinginsider](https://www.gamblinginsider.com/in-depth/104635/what-is-a-betting-exchange),
[darkhorseodds Sporttrade](https://about.darkhorseodds.com/articles/sportsbooks/sporttrade),
[SX Bet blog](https://blog.sx.bet/sports-betting/guides/betting-exchange-vs-sportsbook/))

**This is the real unlock the prior study was missing** — and it is decisive *in the positive
direction* on leg (the ban wall). It is exactly why these venues are interesting in principle. **But a
ban-proof venue is necessary, not sufficient** (the same lesson as Kalshi), and the *other three legs
of the bar all fail in mid-2026 — see below.**

---

## 3. LIQUIDITY & FLOW

- **Flow is recreational/soft** by design — these platforms target retail bettors who want better
  prices, and Novig's own pitch is recreational growth. That is the *good* news for a value-bettor: the
  counterparty is the soft side. But (a) recreational flow concentrates on the same flagship games where
  sharp counterparties and the consensus also live, and (b) sharp money flowing in is precisely what the
  exchange *wants* and what drives prices to fair — so a persistent lag is competed away faster than on
  a captive soft book.
- **Depth is bimodal/thin:** "liquidity drops off fast once you move past the major leagues and main
  markets" (ProphetX); Sporttrade "focused on high-demand events with potentially limited selection."
  Novig is the deepest ($4B claimed annual volume) but that is still a fraction of FanDuel/DraftKings,
  and it is sweepstakes. Off-flagship books are **thin → low capacity** for a small bankroll, which is
  fine for tiny size but caps any scaling and widens the spread you must cross.
  ([oddsassist ProphetX](https://oddsassist.com/prediction-markets/prophetx/),
  [bettoredge](https://www.bettoredge.com/post/best-betting-exchanges-in-the-us))

So the flow is the right *kind* (soft), but the **microstructure is the same trap as Kalshi**: deep
where it's efficient (flagship), soft where it's thin (off-flagship).

---

## 4. THE EDGE: do exchange prices LAG the sharp reference?

There is **no public, measured CLV study of these exchanges vs Pinnacle**, and — critically — **the
primary regulated venue (Sporttrade) is going offline this month**, so any edge measured now expires
before it can be deployed. On structure alone:

- **Plausible mechanism:** if a contract is priced by recreational flow and lags Pinnacle's de-vigged
  fair, a value-bettor reading Pinnacle could **take the mispriced side as a taker, or post a maker
  limit order at fair**, harvest the gap, and (uniquely) **not get banned**. This is the legitimately
  attractive shape.
- **But the edge has to clear:** the spread (10c lines on Sporttrade ≈ ~2.4% half-spread equivalent vs
  Pinnacle's ~2% hold; wider off-flagship) **plus** the 2–3% win-commission. A canonical Pinnacle-anchored
  value edge is only ~**2–4% ROI** ([14-season study: 3.6% ROI vs Pinnacle pre-close](https://www.sportstradingnetwork.com/article/pinnacle-versus-fivethirtyeight-a-comparison-of-predictive-success/)).
  Sporttrade's own claim is that tighter lines make it cheaper *despite* the 2% — meaning the book is
  already near-fair on flagship games, so the residual lag to harvest is small and the 2% commission
  eats much of a 2–4% gross edge. **On flagship games the after-fee edge is ~0 to low-single-digit and
  unproven.** Off-flagship, the lag may be larger but the spread+thinness hurdle is larger too — the
  Kalshi-illiquid story exactly.
- **Capacity:** small. Suits a small bankroll, but is not a printer and won't scale.

Honest read: **the lag-vs-sharp edge is plausible but unmeasured, likely thin after the
spread+commission, and — fatally — has no surviving regulated venue to run it on.**

---

## 5. FEES / FRICTION (the +EV-after-friction test)

| Venue | Commission | When charged | Withdrawal | Spread vs soft book |
|---|---|---|---|---|
| Sporttrade | **2%** | on profitable trades only | low/free | ~10c lines (~−105) vs 20c (−110) — tighter |
| Prophet X | **2–3%** | on net winnings only | no payout fee | tighter than soft books |
| Novig | **~1–4%** | maker commission | redemption | tighter |
| BetOpenly | **~1%** (free up to a monthly cap) | on bets | — | tightest fee, smallest venue |
| Fliff | 5–10% vig | in odds | — | soft-book-like — no edge |

Fee model is **genuinely favorable** (1–3% on wins only, no vig in odds, tighter lines than soft books).
**Friction is the one leg besides ban-policy that passes** — but only relative to soft books; against
the **~2–4% Pinnacle value edge** a 2–3% win-commission still claims a large share of the gross, leaving
a slim after-fee margin that must then also beat the spread. **Net after friction: marginal at best on
flagship; unproven off-flagship.**

---

## 6. COMPARISON

| Dimension | Soft books (DK/FD) | Kalshi sports | Sporttrade (regulated exch.) | Prophet X / Novig (sweeps exch.) |
|---|---|---|---|---|
| Can ban winners? | **YES — kills it** | No (exchange) ✅ | **No (exchange)** ✅ | **No (exchange)** ✅ |
| Real-money + regulated? | Yes | Yes (CFTC) | Yes (state) — **but exiting** | **No — sweepstakes, legally fragile** |
| Fee/friction | 4.5% vig | ~1.75c take + spread | **2% on wins, tight lines** ✅ | 2–4% on wins ✅ |
| Flow | soft (you) | SIG-sharp (liquid) | soft/recreational ✅ | soft/recreational ✅ |
| Lag vs sharp to harvest | yes (but banned) | ~0 liquid / thin illiquid | plausible, **unmeasured, thin after fee** | plausible, unmeasured |
| Liquidity | deep | deep flagship / thin else | thin off-flagship | thin off-flagship (Novig deepest) |
| Legal access (your state) | broad | nationwide (CFTC) | **5 states, ending June 26 2026** | **shrinking; banned in many states** |
| Deployable now? | No (ban) | Marginal (efficient/thin) | **NO — venue closing this month** | **NO — sweeps illegal/at-risk, thin** |

**The exchanges beat both prior dead-ends on the axes that killed them** — they can't ban you (beats soft
books) and their flow is soft/recreational, not SIG-sharp (beats Kalshi's liquid side). **That is real.**
But they lose on the axes that matter for *deployment today*: Sporttrade has **no live venue**, and the
sweepstakes survivors have **no durable legal access** and **thin off-flagship liquidity**.

---

## 7. VALIDATION PLAN (if/when a CFTC-regulated exchange relaunches)

Do **not** deploy now. The only future worth a measured test is a **CFTC-regulated relaunch** (Sporttrade
DCM, Novig DCM, or ProphetX DCM) that is live, real-money, and legal in the operator's state. If one
launches:

1. **Markets:** off-flagship listings where recreational flow sets price (secondary leagues, props,
   futures) — that is where any lag-vs-sharp survives; flagship games will be near-fair.
2. **Sharp reference feed:** Pinnacle de-vigged h2h. **the-odds-api free tier no longer includes
   Pinnacle** (Pinnacle + history is on the $99/mo Business tier; free tier is 25 req/day, NBA/MLB h2h
   only). A cheaper path is **OddsPapi**, whose free tier reportedly includes Pinnacle + Betfair with
   historical odds and no 10× penalty — verify before relying on it.
   ([theoddsapi pricing](https://oddspapi.io/blog/odds-api-pricing-2026-comparison/),
   [oddspapi free](https://oddspapi.io/blog/free-odds-api-350-bookmakers/))
3. **CLV measurement:** for ~**300–500 events over several weeks**, log (exchange entry price after
   2–3% commission, de-vigged Pinnacle fair at entry, exchange settlement). Compute mean
   |exchange − Pinnacle| deviation, count of signals clearing **spread + commission**, and realized
   **net CLV vs settlement.** Reuse the existing `kalshi_vs_sharp.py` harness pattern (same de-vig +
   hurdle logic) pointed at the new exchange's book API.
4. **Decision rule:** deploy only if **net-of-fee CLV is positive and stable** at meaningful frequency.
   Expected prior, given the ~2–4% gross edge and 2–3% commission + spread: **thin, low-capacity, maybe
   marginally +EV** — a small sleeve at best, capped by the thin liquidity that creates it.

---

## 8. VERDICT

**Do US-regulated sports exchanges escape the ban wall with a real, deployable edge? NO — not in
June 2026 — but for a reason that could change.**

- **They DO escape the ban wall.** Peer-to-peer economics make a winner an asset; Sporttrade/Novig/
  ProphetX explicitly do not limit winners. This is the genuine unlock the prior study missed, and it
  beats both soft books (which ban) and Kalshi's liquid side (which is SIG-efficient).
- **But the venue collapsed underneath the edge.** The **only true state-regulated real-money exchange,
  Sporttrade, is shutting down its sports markets this month** (NJ done May 25; AZ/CO/IA/VA gone
  June 26, 2026) to chase CFTC approval — **nothing tradable today.** The survivors (Prophet X, Novig,
  BetOpenly) are **sweepstakes** models being **banned state-by-state** (CA, NY, AZ, NJ, CT, MT) and are
  themselves pivoting to CFTC. So **leg (d) legal access fails** for a stable real-money venue, and
  **leg (b) liquidity is thin** off-flagship.
- **The edge itself (leg a/c) is plausible but unmeasured and likely thin:** a ~2–4% Pinnacle-anchored
  value edge against a 2–3% win-commission + spread leaves a slim after-fee margin, with small capacity.

**Killer constraints, ranked:** (1) **Sporttrade — the only regulated real-money exchange — is
decommissioning its tradable markets right now** (no venue); (2) the alternatives are **sweepstakes
with crumbling state legality** (no durable access); (3) **thin off-flagship liquidity** (no capacity);
(4) the after-fee edge is **plausible but unproven and likely marginal**. Ban-policy and fee model both
pass — but a ban-proof, low-fee venue with no legal market and no liquidity is not deployable.

**Bottom line:** Same family of dead-end as Kalshi sports and the crypto box — *the edge exists where you
can't reach it (a regulated exchange that's closing) and the reachable venues are illegal-fragile or
efficient.* **The single thing to monitor: a CFTC-regulated exchange relaunch (Sporttrade/Novig DCM).
That would put a ban-proof, real-money, nationwide exchange on the board — at which point run the CLV
test in §7 before sizing.** Until then: not deployable.

---

### Sources
- Sporttrade exit: [gambling.com](https://www.gambling.com/us/news/sporttrade-exits-us-sports-betting-market-in-pivot-to-prediction-markets),
  [Finance Magnates](https://www.financemagnates.com/forex/sporttrade-exits-sports-betting-to-rebuild-around-prediction-markets-under-cftc-oversight/),
  [Yogonet](https://www.yogonet.com/international/news/2026/05/19/121042-sporttrade-to-exit-us-online-sports-betting-markets-while-awaiting-cftc-decision),
  [Sportico](https://www.sportico.com/business/sports-betting/2026/sporttrade-prediction-market-regulation-state-cftc-1234882662/),
  [Sports Betting Dime](https://www.sportsbettingdime.com/news/betting/sporttrade-to-halt-online-sports-betting-markets-by-june/)
- Sporttrade structure/fees/states: [oddsassist review](https://oddsassist.com/sports-betting/sportsbooks/sporttrade/),
  [oddsassist fees](https://oddsassist.com/sports-betting/sportsbooks/sporttrade-fees/),
  [sportshandle](https://sportshandle.com/sporttrade/),
  [Sporttrade where-available](https://sporttrade.zendesk.com/hc/en-us/articles/4410576091675-Where-Sporttrade-is-available)
- ProphetX: [legalsportsreport](https://www.legalsportsreport.com/prediction-markets/prophetx-promo-code/),
  [oddsassist](https://oddsassist.com/prediction-markets/prophetx/),
  [oddsshopper](https://www.oddsshopper.com/articles/betting-101/what-is-prophetx-sports-betting-what-to-know-about-prophet-x-y10),
  [Sportico CFTC](https://www.sportico.com/business/sports-betting/2025/prophetx-prediction-market-cftc-sweepstakes-1234876170/)
- Novig: [legalsportsreport](https://www.legalsportsreport.com/prediction-markets/novig-promo-code/),
  [DeFi Rate](https://defirate.com/news/novig-raises-75m-positions-cftc-regulated-exchange-as-future-of-sports-betting/),
  [Covers](https://www.covers.com/industry/novig-seeks-cftc-approval-to-operate-prediction-markets-jan-26-2026)
- Sweepstakes legal pressure: [Yogonet NY ban](https://www.yogonet.com/international/news/2025/12/08/116669-new-york-imposes-prohibition-on-sweepstakes-casinos-and-sportsbooks),
  [Closing Line AZ C&D](https://closingline.substack.com/p/news-arizona-sends-cease-and-desist-sweepstakes)
- Exchange ban-policy / economics: [Gambling Insider](https://www.gamblinginsider.com/in-depth/104635/what-is-a-betting-exchange),
  [SX Bet](https://blog.sx.bet/sports-betting/guides/betting-exchange-vs-sportsbook/),
  [DarkHorse Sporttrade](https://about.darkhorseodds.com/articles/sportsbooks/sporttrade)
- Exchange roundup / fees: [bettoredge](https://www.bettoredge.com/post/best-betting-exchanges-in-the-us)
- Pinnacle edge / value-bet ROI: [Sports Trading Network 3.6% study](https://www.sportstradingnetwork.com/article/pinnacle-versus-fivethirtyeight-a-comparison-of-predictive-success/)
- Validation feeds: [Odds API pricing](https://oddspapi.io/blog/odds-api-pricing-2026-comparison/),
  [OddsPapi free Pinnacle](https://oddspapi.io/blog/free-odds-api-350-bookmakers/)
</content>
</invoke>
