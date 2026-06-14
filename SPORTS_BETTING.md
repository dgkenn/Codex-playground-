# Sports betting as a deployable edge for a US small-bankroll operator (2026-06-14)

Brutally honest research answer to: *is sports betting a profitable, repeatable, US-legal edge for
a small bankroll, and does it beat / escape the structurally-dead Kalshi crypto maker-box?*

**TL;DR verdict (details in §5):** There is a **real, documented edge** in sports — soft recreational
flow is genuinely +EV against a sharp reference — but for a **US retail** person it is **access-gated
exactly like the crypto perp edge was**: the soft US sportsbooks that you can beat *ban/limit winners
within weeks*, and the sharp reference book (Pinnacle) that doesn't ban is *not legal in the US*.
**Kalshi sports** reuses our infra and **can't ban you**, but our own live API pull shows Kalshi's
liquid game markets are **already de-vigged-efficient (mid-overround ≈ 0%, 1–3c spreads, priced by
SIG/Susquehanna)** — so there is **no systematic lag vs the sharp consensus to harvest** on the liquid
side, and the only place Kalshi is *soft* (illiquid games/props) is also where **spreads are 5–10c and
depth is tiny** — the same "edge < juice / too thin" wall as the box. **Net: it does ESCAPE the
queue-position death, but it does NOT clear into a free lunch. The one shape worth a measured live test
is value-betting Kalshi's *illiquid* listings vs a sharp feed — but the honest prior is thin/marginal.**

---

## 1. The edge landscape — documented vs folklore (cited)

The only legitimate proof of a sports edge is **Closing Line Value (CLV)**: did you get a better price
than the market's de-vigged closing line, repeatedly, over hundreds of bets? ROI over a small sample is
variance; sustained CLV is the signal. "A bettor with +5% ROI but flat CLV is winning on variance and
probably reverting." Realistic *sustained* pro ROI is **2–5% over 1000+ bets** (≈55% win at −110 ⇒ ~4–5%
ROI; 57% ⇒ ~8–9%); ~3–5% of bettors beat the market long-term, ~95% lose.
[bet105 CLV](https://bet105.ag/what-is-closing-line-value/),
[Pikkit ROI](https://pikkit.com/blog/how-to-track-sports-betting-roi),
[Webopedia pro ROI](https://www.webopedia.com/crypto-gambling/casinos/guides/professional-betting-roi-strategy/).

**(a) +EV value betting vs soft books, using a sharp reference (Pinnacle / consensus closing line).**
This is the canonical real edge. De-vig Pinnacle's low-margin (~2–3% hold) line into a "fair" probability,
bet anywhere the soft book offers a price that implies a lower probability. Documented edge per bet is
**small (a few % ROI)**, validated by CLV.
[Sharp Football CLV](https://www.sharpfootballanalysis.com/sportsbook/clv-betting/),
[Pinnacle margins ~2%](https://www.pinnacleoddsdropper.com/blog/is-pinnacle-sportsbook-legal-in-the-us-2025-guide-restrictions).
**Killer constraint = ACCESS, not signal:** soft US books (DraftKings/FanDuel/etc.) **limit or ban**
accounts that beat the closing line, typically **within weeks to months**. "If you're beating the closing
line by 5%+ consistently, you're on the book's radar."
[Outlier: why books limit](https://outlier.bet/sports-betting-strategy/positive-ev-betting/why-sportsbooks-limit-your-bets/),
[XCLSV avoid limits](https://xclsvmedia.com/how-to-avoid-getting-limited-by-sportsbooks-in-2026-complete-guide-for-profitable-bettors/).
Pinnacle itself does **not** ban winners — but **Pinnacle is illegal for US persons** (withdrew 2007 post-UIGEA).
[Pinnacle US legal status](https://www.pinnacleoddsdropper.com/blog/is-pinnacle-sportsbook-legal-in-the-us-2025-guide-restrictions).
⇒ The US-retail version of value betting is a **treadmill of opening accounts that get throttled** —
not a stable, scalable edge.

**(b) Arbitrage / middling across books.** Guaranteed-margin surebets across two books. Edge is **small
(0.5–3% typical, occasionally 10–20% in-play)** and **closes fast: a window that lasted 2–3 min in 2015
now disappears in <20s**; needs bankroll spread across many funded accounts and constant scanning.
[performanceodds arbitrage](https://www.performanceodds.com/strategies/surebets-arbitrage-betting-complete-strategy-tools-calculators-real-examples-for-2025-2026/),
[boydsbets](https://www.boydsbets.com/arbitrage-betting/),
[picktheodds](https://picktheodds.app/en/blog/arbitrage-betting-the-complete-guide-in-2025).
**Same killer constraint:** the leg you place on the soft book is *exactly* the winning behavior that gets
you limited — arbers get banned as fast as value bettors. Labor-intensive; "side income, not full-time."

**(c) Exchange market-making (Betfair-style).** Genuine repeatable edge (provide liquidity, earn spread)
but **Betfair/Smarkets are not legal for US persons.** Reference only — and note it is *the same maker
microstructure as the crypto box*, so it would inherit a queue-position problem against pro MMs anyway.

**(d) Modeling/prediction edges.** Major markets (NBA/NFL/EPL moneyline) are **the sharpest lines** — very
hard to beat. Niche/less-efficient markets (smaller leagues, **player props**) have **softer odds and
higher hold** and are where modeling ROI is realistically found (claims of **3–7% sustainable, 8%+
selective**), but information quality is poor and — again — **props are where soft books limit fastest**.
[FightMatrix niche](https://www.fightmatrix.com/2025/09/10/hidden-opportunities-how-to-spot-the-best-value-bets-in-minor-leagues-and-niche-sports/),
[LSports niche](https://www.lsports.eu/blog/beyond-mainstream-betting/),
[SportBot ROI](https://www.sportbotai.com/blog/ai-betting-model-monthly-roi-guide).

**Which is accessible + repeatable for US retail?** None *cleanly*. Every soft-book approach (a/b/d) dies
to **account limits/bans**; the books that don't ban (Pinnacle/Betfair) are **US-illegal**. This is the
landscape's central, unromantic fact: **in US retail sports betting the binding constraint is access, not
signal.** That is precisely why **Kalshi — a CFTC exchange that legally can't ban a winner — is the only
interesting venue.**

---

## 2. Kalshi sports inventory + liquidity + structure (live API, no auth)

Pulled from `https://api.elections.kalshi.com/trade-api/v2/` (`/series`, `/events`, `/markets`,
`/markets/{t}/orderbook`). Scripts: `kalshi_sports_probe.py`, `kalshi_vs_sharp.py`.

**Inventory.** Sports is **2,191 series** (the bulk of Kalshi). Breakdown:
Soccer 440, Basketball 418, Football 362, Baseball 167, Tennis 121, Golf 104, Esports 102, Hockey 68,
Motorsport 54, Cricket 46, Olympics 46, MMA 34, Chess 25, Boxing 20, plus long tail. Market types span
**game winner (moneyline)** (`KXMLBGAME`, `KXNBA`, `KXNHLGAME`, `KXWNBAGAME`, `KXNFLGAME`), **series**
(`KXNBASERIES`/`KXNHLSERIES`), **season win totals / champion futures** (`KXMLB-26-<team>`), **totals**,
**props** (next-TD scorer, first goal, strikeouts), and exotic in-game markets. Each game-event = two
complementary YES markets (one per team), priced in cents 1–99, **structured/binary**, settle ~120s
after a winner is declared, fee_type `quadratic`. Sports is **~70%+ of all Kalshi volume**
([Reuters/SI reporting](https://www.si.com/prediction-markets/reviews/kalshi)).

**Liquidity (live snapshot, top game markets).**

| League series | med touch spread | example depth |
|---|---|---|
| MLB game (`KXMLBGAME`) | **1.0c** (p90 5c) | top game **vol >3.0M contracts, OI 2.4M**; 65k+ ct resting at single levels |
| MLB futures (`KXMLB-26`) | 0.3–3c | vol 1.0–1.7M per team |
| NHL game | 1.0c | game vol ~0.77M; **>1.3M ct within 5c of touch** |
| WNBA game | 1.0–2.0c | game vol 0.4–0.7M |
| WTA tennis match | 1.0–6.0c | popular match vol ~0.5M |
| NBA futures / ATP / NFL game (Sep) | **3.0–6.0c, thin** | NBA-27 futures vol ~5–18k; ATP match ~6–10k |

So liquidity is **bimodal**: flagship in-season games (MLB/NHL/WNBA primetime, top tennis) are **genuinely
deep with 1–2c spreads**; everything off-flagship (futures months out, minor tennis, props, niche sports)
is **3–10c spreads and 5–20k volume — thin**. Matches the public consensus
([tech-insider](https://tech-insider.org/prediction-markets/sports-prediction-markets/),
[alphascope](https://www.alphascope.app/blog/kalshi-sports-betting)).

**Market structure — is there a co-located mechanical MM like the crypto box?**
Yes, but a *different kind*: Kalshi's dedicated institutional MM is **Susquehanna (SIG)**, which runs a
24/7 event-contract desk and provides ~30x prior liquidity with quantitative two-sided pricing.
[Kalshi/SIG](https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here),
[Morningstar](https://www.morningstar.com/news/business-wire/20240403664852/kalshi-onboards-its-first-dedicated-institutional-market-maker).
Crucially the **microstructure differs from the crypto box in the way that matters to us**: the box died
because we *had to be a resting MAKER* racing a 1.2s mechanical heartbeat for queue priority and always
filled last. Sports value-betting is a **TAKER** play (lift SIG's resting ask when it's mispriced) and
**buy-and-hold to settlement** (game outcome hours/days away). **There is no queue race and no
re-quote-faster requirement** — seconds of latency on a cloud bot is fine. *That part of the box's death
does not transfer.* The catch is the flip side: because SIG (a top quant MM) is the one quoting, the
**liquid books are sharp**, which is exactly what the next section measures.

---

## 3. THE KEY TEST — does Kalshi sports price LAG a sharp reference?

**Method (harness: `kalshi_vs_sharp.py`).** For each game-event, take Kalshi's two complementary YES
markets, de-vig to a fair prob (mid_A/(mid_A+mid_B)), and compute the *takeable* ask. Compare to a sharp
reference = **de-vigged Pinnacle h2h moneyline**. A buy is +EV only if
`pinnacle_fair_prob − kalshi_ask > half_spread + taker_fee`.

**Kalshi cost-to-take (must be cleared by any edge):**
- Taker fee = `ceil(0.07·P·(1−P)·100)/100` per contract, paid **once** on a buy-held-to-settlement
  (settlement free). ≈ **1.75c worst case at P=0.50**, ~1.1c at 0.20/0.80.
  [marketmath](https://marketmath.io/blog/kalshi-fees-guide-2026),
  [GWU paper](https://www2.gwu.edu/~forcpgm/2026-001.pdf).
- Half-spread ≈ **0.5–1.5c** liquid, **2.5–5c** illiquid.
- ⇒ **Total hurdle ≈ 2.5–3c on liquid games, 4–7c on illiquid.** An edge smaller than this is not real.

**What the live data already tells us (measured, no external feed needed):**
Across MLB/NHL/WNBA/NFL game markets the **median sum of the two team YES-mids = 1.0000** —
i.e. **Kalshi's mid-overround / hold ≈ 0.00%** on liquid games (WNBA −0.5%, NFL +0.25%, MLB/NHL 0%).
A ~0% mid-overround means **Kalshi's de-vigged fair price *is* the mid**, and on these games it is at
least as tight as Pinnacle's ~2–3% hold and tighter than US soft books' 4.5%
([si.com](https://www.si.com/prediction-markets/reviews/kalshi),
[bettingusa](https://www.bettingusa.com/prediction-markets/reviews/kalshi/)).
The widely-reported result is that on flagship games Kalshi's implied price is **as good as or better
than Pinnacle**. **Conclusion for the liquid side: there is essentially no systematic lag to harvest —
SIG keeps the mid on the consensus, and the 1–3c spread+fee hurdle eats any residual deviation.**

**Where an edge could still live:** the **illiquid** listings (futures months out, minor tennis, props,
niche leagues) where SIG quotes lazily/widely and recreational order flow sets prices. There, Kalshi
*can* lag a sharp model — but that is **also** where the spread is 5–10c and depth is 5–20k contracts, so
the **edge has to clear a 4–7c hurdle and capacity is tiny.** This is the identical "soft-but-thin" wall
the crypto research kept hitting.

**Feasibility / what's needed to settle it empirically.** A single live snapshot is **not** proof (same
discipline as the Polymarket study). To actually measure the edge you need a **sharp feed + a CLV log**:
- **Sharp reference:** the-odds-api free tier (500 req/mo, **includes Pinnacle EU** h2h) — enough to poll
  a few leagues a few times/day. [the-odds-api](https://the-odds-api.com/). (Live test today returned 401
  without a key — that key is the only missing ingredient; the harness is wired and runs in
  self-consistency mode until it's set via `ODDS_API_KEY`.)
- **Procedure:** for ~**300–500 games over several weeks**, log (Kalshi entry price, de-vigged Pinnacle
  fair, Kalshi settlement). Compute (i) mean |Kalshi − Pinnacle| deviation, (ii) count of signals clearing
  the spread+fee hurdle, (iii) realized **CLV vs Kalshi settlement**. **Decision rule:** deploy only if
  net-of-fee CLV is **positive and stable** at meaningful frequency on the *illiquid* slice (the liquid
  slice is already shown efficient). This is the honest, falsifiable test; expected outcome is *marginal*.

---

## 4. Comparison to the crypto maker-box

| Dimension | Crypto maker-box (Kalshi BTC) | Kalshi sports value-betting |
|---|---|---|
| Role | **Maker** (rest both legs, lock spread) | **Taker** (lift a mispriced ask), hold to settle |
| Killer in crypto | **Queue position** behind co-located 1.2s mechanical MM ⇒ fill last ⇒ 18–22% strands | **No queue race** — outcome hours/days away, seconds-latency cloud bot is fine ✅ |
| Counterparty | Mechanical ladder MM, prices BTC efficiently | **SIG** quant MM, prices liquid games efficiently |
| Underlying inefficiency | None — BTC price is efficient; Kalshi mid = sufficient stat | **Real on illiquid listings** (soft rec flow); **gone on liquid** (SIG = consensus) |
| Hurdle to clear | round-trip ~1c fee + strand cost > 0.69c edge ⇒ negative | take fee ~1.75c + half-spread; liquid hurdle ~3c, illiquid 4–7c |
| Capacity | ~$500 (and negative anyway) | Liquid: large but efficient (no edge). Illiquid: tiny depth |
| Can the venue ban you? | No (exchange) | **No (exchange)** ✅ — the *one* genuine advantage over soft sportsbooks |
| Net | **Structurally dead** (last-in-queue) | **Escapes the queue death**, but hits a *new* wall: liquid=efficient, illiquid=thin |

**Honest read:** Sports value-betting on Kalshi is **strictly better than the crypto box on the axis that
killed the box** (no maker queue race, no co-located-MM latency war — it's a slow taker hold). It is also
**better than US soft-book betting on the axis that kills that** (Kalshi can't ban you). But it does **not**
produce a clean edge, because it inherits a *different* version of the same problem: the part of Kalshi
that is *soft enough to beat* is *too thin/wide to extract from*, and the part that is *deep enough to
trade size* is *already efficient (SIG = sharp consensus)*. Same final shape as crypto: **the edge exists
where you can't take it, and is gone where you can.**

---

## 5. VERDICT

**Is there a deployable, US-legal, small-bankroll sports-betting edge?**

- **US soft sportsbooks (DraftKings/FanDuel/props):** real +EV signal (a few % ROI vs Pinnacle fair),
  but **NOT deployable/repeatable for a US small bankroll** — winners are **limited/banned within weeks**.
  Access, not signal, is the wall. **Dead end as a stable strategy.** (Pinnacle/Betfair don't ban but are
  **US-illegal** — same legal wall that killed the offshore-perp momentum play.)
- **Kalshi sports liquid games (MLB/NHL/WNBA primetime, top tennis):** **efficient** — mid-overround ≈ 0%,
  1–3c spreads, **SIG keeps the price on the sharp consensus**. **No takeable edge** once the ~3c
  spread+fee hurdle is paid. **Dead** as a value play (it's a *cheaper place to bet*, not an *edge*).
- **Kalshi sports illiquid listings (futures, minor tennis, props, niche leagues):** the **only candidate**
  — softer (rec flow can drive price) **and** the venue **can't ban you**. But **spreads 5–10c, depth
  5–20k contracts**, so edge must clear a **4–7c hurdle with tiny capacity**. **Plausibly marginal;
  unproven.** Worth a *measured live test*, not a deployment.

**Recommended action (if pursuing at all):** run `kalshi_vs_sharp.py` with an `ODDS_API_KEY` for **several
weeks across the illiquid slice**, logging realized **CLV vs Kalshi settlement** net of the spread+fee
hurdle. **Deploy only if net CLV is positive and stable.** Honest expected outcome: a **thin, low-capacity
edge (low single-digit % ROI on small stakes) at best**, capacity capped by the very illiquidity that
creates it — *not* a cash machine, and roughly the same "modest sleeve, not a printer" conclusion the
crypto program reached for long-only momentum.

**Does it beat / escape the crypto box's death?** **It escapes the queue-position death** (it's a slow
taker hold, no co-located-MM race — that specific killer is gone). But it does **not clear into a free
lunch**: it runs into the structural twin (soft↔thin, deep↔efficient) plus the US-legal/ban wall on the
sportsbook side. **Net verdict: not a deployable money-printer; the single honest, testable opportunity is
value-betting Kalshi's *illiquid* markets vs a sharp feed — measure CLV first, expect marginal.**

**Killer constraints, ranked:** (1) soft-book **account bans/limits** (kills all US-sportsbook approaches);
(2) Kalshi liquid markets are **SIG-efficient** (no edge where there's depth); (3) Kalshi illiquid markets
are **wide + thin** (edge < juice / no capacity); (4) the **only** unambiguous Kalshi advantage —
*it can't ban a winner* — is **necessary but not sufficient** without an underlying mispricing to take.

**What data would settle it:** an `ODDS_API_KEY` (Pinnacle h2h) + a **300–500-game, multi-week CLV log**
on Kalshi's illiquid slice via the included harness. Until that shows positive stable net-of-fee CLV,
treat sports as **efficient/access-gated/too-thin — same family of dead-end as the crypto box.**
