# Live / in-game betting, steam-chasing & CLV capture — feasibility for a seconds-latency CLOUD bot (2026-06-15)

Brutally honest answer to: *can a cloud bot (GitHub Actions, seconds latency, NOT co-located) capture a
live/in-game latency edge, chase steam into soft books for closing-line value (CLV), or systematically
beat the close — and is Kalshi in-play a slow/soft maker opportunity?*

Builds on `SPORTS_BETTING.md` (commit 56fb362) and `SHARP_VS_KALSHI.md` (commit 077b61c), which already
established the prior: **Kalshi LIQUID game markets are SIG/Susquehanna-priced and de-vig-efficient (mid
overround ≈ 0%, 1–3c spreads); the only soft slice is illiquid (wide + no capacity); and every US
soft-sportsbook approach dies to account limits/bans.** This doc adds the missing piece: the **latency
physics of LIVE and STEAM**, and whether a *cloud, seconds-latency* executor can ever realize them.

**TL;DR verdict (details §6):** **No deployable live/steam/CLV edge survives seconds-latency cloud
execution. It is latency-walled AND limiting-walled — structurally the same dead-end as the crypto box,
for the same reason: you are last in the queue behind faster, co-located capital.** Live in-play is a pure
latency game where US books already run on a sub-second official data feed and *you* are the slowest node
(broadcast is 8–12s behind the venue; the book's reprice→screen chain is 150–450ms). Steam-chasing needs
sub-minute (often sub-20s) action at a soft book and gets you *limited within weeks*, the limit arriving
fastest precisely for early bets that beat the close. CLV is real and is the correct edge proxy, but it
is not systematically harvestable by retail net of vig + bans. Kalshi in-play is **not** a slow/soft
maker pond: SIG market-makes it 24/7 on a Sportradar real-time feed, so the liquid in-play book is tight
and fast; the only soft corners are illiquid and static (no fills). **Live/steam = latency-walled, same as
the crypto box.**

---

## 1. LIVE / IN-GAME: the latency physics, and why a cloud bot can't compete

The live edge thesis is real in principle: *if you observe game state faster than the book reprices, or
model in-play probability better, you can hit a stale line.* Both halves fail for a cloud retail bot.

**How fast US books update in-play (measured/cited).** The book's pricing engine consumes a continuous
**official** data feed (Genius Sports, Sportradar, IMG Arena, Stats Perform), reruns a simulation on each
state change, and pushes a new odds row through its CDN. The **engine-reprice → your-screen chain is
typically 150–450ms** depending on edge network and your connection. Bet-acceptance latency (the book's
own validation) is **~1.4s FanDuel / 1.7s DraftKings / 2.0s BetMGM** median.
[tonyspicks live latency](https://www.tonyspicks.com/2026/05/12/live-betting-latency-which-sportsbooks-update-fastest-during-play/),
[OpticOdds real-time feeds](https://opticodds.com/blog/leveraging-real-time-odds-api),
[Genius/Sportradar feed chain — search summary, tonyspicks].

**Where your information actually comes from, and why it's the slowest node.** Cable/stream broadcast runs
**8–12 seconds behind the live venue**. The book's engine is already on a near-live official feed, so your
screen is *one of the slowest information sources in the chain* — you find out the 3-pointer dropped
**seconds after** the engine has already repriced. To have a latency edge you would need a **faster-than-
the-book official data feed** (court-side scouts / a low-latency commercial feed), which is the documented
pro edge — and it is **not accessible to retail**, and certainly not to a GitHub-Actions cron.
[tonyspicks live latency](https://www.tonyspicks.com/2026/05/12/live-betting-latency-which-sportsbooks-update-fastest-during-play/).

**The bet-delay makes it worse, not better.** Books add a **multi-second bet-acceptance delay** during
which they re-check the line; "during this validation time, the sportsbook updates its odds, which
eliminates the [in-play] opportunity." So even if you *somehow* saw a stale line, the book's own delay
window lets it move the line out from under your in-flight bet (and reject/re-price it). The delay is a
one-way option the book holds against you.
[agentbets arb guide](https://agentbets.ai/guides/sports-betting-arbitrage-bot/),
[symphony-solutions API](https://symphony-solutions.com/insights/sports-betting-api-integration).

**The latency budget vs a cloud bot.** Pro in-play arb setups run **~20–100ms** (WebSocket feeds ~100ms;
DOM-observation ~20ms), co-located VPS reaches **<0.52ms** to trading hubs.
[quantvps](https://www.quantvps.com/blog/automated-sports-betting-bots-on-polymarket).
A **GitHub-Actions cloud bot is a different universe**: cron granularity is minutes (not ms), runner
cold-start + checkout is tens of seconds, and a single REST poll → decide → POST round-trip from a shared
cloud runner to a US book is **multiple seconds before counting the book's 1.4–2.0s acceptance delay**.
The in-play suspension/reset windows are **1–2s (tennis), per-possession 12–24s (NBA)** — a cloud bot's
**round-trip alone overruns the window.** This is exactly the crypto-box failure: by the time you act, a
faster, co-located actor has already taken the price.

**Quantified conclusion (live).** Required end-to-end latency to beat the live line: **sub-second, on a
faster-than-broadcast official feed.** Cloud-bot achievable latency: **seconds, on the slowest feed in the
chain (delayed broadcast/screen).** Gap ≈ **1–3 orders of magnitude.** The documented live edge
(court-side / fast-feed bettors) is **real but inaccessible to retail and impossible for a cron cloud
bot.** **Live in-game = hard latency wall. Not deployable.**

## 2. STEAM-CHASING: speed required, services, and the limiting wall

**The play.** A sharp move ("steam") hits the market leader (Pinnacle/Circa); reference-following books
move "within minutes, sometimes seconds." You bet a **soft book that hasn't moved yet**, capturing the
old (now +EV) price before it catches up.
[playohio steam](https://www.playohio.com/sports-betting/chasing-steam/),
[SI steam](https://www.si.com/betting/sports-gambling-what-is-chasing-steam-betting).

**How fast you must act.** The slow-book window has **collapsed**: a surebet/steam window that lasted
**2–3 minutes in 2015 now disappears in <20s** in-play (per `SPORTS_BETTING.md` §1b cites). Pre-game steam
gives **seconds-to-a-few-minutes** before the soft book moves. **Alert services** ($50–300/mo,
e.g. steam/line-move monitors) detect a synchronized multi-book move and push an alert — but the alert is
**downstream of the move**, and the soft book is also watching the same signal. A **cloud cron bot adds
its own seconds-to-minutes** of polling + runner latency *on top of* the alert lag → it routinely arrives
**after** the soft book has already moved. Steam-chasing is winnable by a **fast human with funded soft-book
accounts and instant manual entry**, marginal-to-impossible for a seconds-latency cron.
[playohio steam](https://www.playohio.com/sports-betting/chasing-steam/),
[xclsv steam 2026](https://xclsvmedia.com/how-to-use-steam-moves-sports-betting-sharp-action-2026/),
[sportbotai steam](https://www.sportbotai.com/blog/steam-moves-betting-ai).

**Does limiting kill it? Yes — fastest.** Betting *into* a sharp move at a soft book is the single most
flagged behavior: "early-market bets that subsequently move the line are flagged fastest," and books
"limit or ban accounts that consistently bet into sharp moves and beat closing lines," typically **within
weeks, sometimes after only a few hundred dollars of profit.** Steam-chasers survive only by **spreading
across many funded accounts and camouflaging with rec-looking bets** — operational overhead a small-bankroll
cloud bot cannot sustain, and which itself is a treadmill, not an edge.
[oddsshopper limits](https://www.oddsshopper.com/articles/betting-101/why-sportsbooks-limits-ev-bettors-and-what-to-do-about-it-y10),
[outlier why limited](https://outlier.bet/sports-betting-strategy/positive-ev-betting/why-sportsbooks-limit-your-bets/),
[xclsv avoid limits](https://xclsvmedia.com/how-to-avoid-getting-limited-by-sportsbooks-in-2026-complete-guide-for-profitable-bettors/).

**Conclusion (steam).** **Double-walled:** latency (sub-20s window vs cloud seconds-to-minutes) **and**
limiting (fastest ban trigger). **Not deployable for a cloud small-bankroll bot.**

## 3. CLV as the edge proxy — is beating the close systematically harvestable?

**CLV is the correct proof of +EV.** Beating the de-vigged closing line repeatedly over hundreds of bets
is the accepted long-run +EV signal; "if your model can't beat Pinnacle's closing price by log-loss across
thousands of bets, you don't have an edge — you have noise."
[boydsbets CLV](https://www.boydsbets.com/closing-line-value/),
[oddsjam CLV](https://oddsjam.com/betting-education/closing-line-value).

**The vig hurdle.** At −110 the break-even is **52.38%**, not 50%. A **55% win rate ≈ 4–5% ROI** after
vig; **+1% CLV ≈ ~5% profit over thousands of bets.** Realistic *sustained* pro ROI is **2–5% over 1000+
bets**; ~3–5% of bettors beat the market long-term.
[webopedia ROI](https://www.webopedia.com/crypto-gambling/casinos/guides/professional-betting-roi-strategy/),
[bet105 +EV](https://bet105.ag/what-is-ev-betting/).

**Is it systematic for retail net of vig + limiting? No.** The only repeatable way to beat the close is to
**bet early at a soft book on a sharp signal** — which is precisely (a) the steam/early-bet behavior that
gets you **limited fastest** (§2), and (b) benchmarked correctly only against **Pinnacle**, which is
**US-illegal to bet** (`SPORTS_BETTING.md` §1). Most "+EV" tools benchmark against a rec book's line (the
wrong reference) and surface noise. So the *signal* (positive CLV) is real and measurable, but the
*harvest* is access-gated: the books you can beat ban you for beating them; the book that doesn't ban you
can't be bet. **CLV is a valid yardstick, not a deployable retail edge net of vig + bans.**

## 4. KALSHI IN-PLAY — slow/soft maker pond, or SIG-efficient? (live API check)

Kalshi **does** offer in-play: contracts trade throughout a game ($0.01–$0.99 = live implied prob), and a
**Feb–2026 Sportradar partnership** now pushes real-time scores/progress into the app and speeds
settlement, explicitly to make **in-play trades more viable**.
[tech-insider Kalshi in-play](https://tech-insider.org/sports-prediction-markets/),
[deadspin Sportradar×Kalshi](https://deadspin.com/prediction-markets/legal-news/kalshi-teams-up-with-sportradar-to-enhance-real-time-data/),
[si Kalshi review](https://www.si.com/prediction-markets/reviews/kalshi).

**But it is market-made by SIG, 24/7, on-site, live.** Susquehanna is Kalshi's flagship designated MM,
"expert traders on-site to trade **live**," providing ~30× prior liquidity with deep two-sided quotes — and
they now have the same real-time data feed.
[kalshi kit SIG](https://kalshi.com/blog/article/kalshi-kit-liquidity-sig-market-makers),
[businesswire SIG MM](https://www.businesswire.com/news/home/20240403664852/en/Kalshi-Onboards-Its-First-Dedicated-Institutional-Market-Maker).

**Live API probe (this repo, `kalshi_inplay_probe.py`, run 2026-06-15 02:42Z):**
- Liquid games (NHL Final, top MLB/WNBA/tennis): **touch spread 0.3–3.0c, deep books** (top-of-book
  hundreds–thousands of contracts; d5 depth in the 100k+ on the NHL Final). Decided/near-settled games sit
  pinned at 0.03/0.96 — i.e. the book tracks game state tightly.
- 128 open-not-closed markets with vol>1k; **top-of-book |move| over a 20s window: median 0.00c, max
  1.00c** in the sampled set (a late-night window with no game mid-flight). The structure mirrors the
  crypto MM pond: **a fast institutional maker holds the inside, and the price is on the true state.**
- The only **soft** corners are **illiquid** WTA/minor markets at **3–4c spreads** — and they are **static**
  (0c motion), i.e. wide *because* nobody is there, so a maker quote sits unfilled. Same soft↔thin /
  deep↔efficient wall as `SPORTS_BETTING.md`.

**Maker opportunity assessment.** In-play maker on Kalshi means **resting a quote and getting filled by
the slower side.** Against SIG (faster feed, on-site, last-look-free but co-incentivized, deep) a cloud
bot resting an in-play YES/NO quote is **adversely selected exactly like the crypto box**: when the game
state ticks, SIG repulls/repprices and the *cloud bot's stale resting quote* is what gets lifted → you are
the toxic-flow donor, not the harvester. There is **no measured timing-lag of Kalshi behind the sharp
consensus on the liquid side** (confirmed efficient in `SHARP_VS_KALSHI.md`: closing mid calibrated to
±0.3c on 706 games). **Kalshi in-play = SIG-efficient + fast, NOT a slow/soft maker pond.**

## 5. CLOUD-BOT FEASIBILITY — the brutal lens (vs the crypto box)

The crypto box (`LIVE_POSTMORTEM.md`, `LIVE_RCA_2026-06-13.md`) died to **two** things, both of which
**recur, amplified, in live/steam:**
1. **Last-in-queue behind a ~1.2s co-located MM** → fills came only when the price was about to move
   against us (adverse selection). **Live in-play is *more* latency-sensitive** (1–2s tennis resets,
   12–24s NBA possessions, sub-20s steam windows) and the competing capital is *also* co-located/on-site
   (SIG on Kalshi; pro fast-feed bettors on books). A GitHub-Actions runner's **seconds-to-minutes**
   round-trip is structurally last in line **every time.**
2. **Optimistic fill model vs live adverse selection** → the live strand rate was 4× backtest because a
   resting quote gets picked off the instant state changes. A live-sports maker quote on Kalshi has the
   **same failure mode against a faster, better-informed feed.**

There is **no version of GitHub Actions** that closes a 1–3 order-of-magnitude latency gap. Cron is
minute-granular; runners cold-start; the network path is shared cloud, not co-located. The crypto-box RCA's
honest meta-finding applies verbatim: **the backtest/alert says edge; live latency says you never get the
price.** Live/steam are *harder* latency games than the crypto box, so the conclusion can only be
**stronger**, not weaker.

## 6. VERDICT — 7-trait scores (0–10; higher = better for a seconds-latency cloud small-bankroll bot)

| Trait | Score | Why |
|---|---:|---|
| **Edge exists (in principle)** | 7 | Live latency edge, steam, and CLV are all **real and documented** — for the right actor. |
| **Edge accessible to retail** | 1 | Faster-than-broadcast feed = pro-only; soft-book steam = **banned within weeks**; Pinnacle = US-illegal. |
| **Cloud (seconds-latency) executable** | 0 | Live windows 1–24s, steam <20s; cloud round-trip is seconds-to-minutes + book's 1.4–2.0s delay. **Hard wall.** |
| **Net of vig / spread / fees** | 2 | −110 ⇒ 52.38% break-even; Kalshi liquid 1–3c+fee hurdle; thin slice 3–4c+fee — edge rarely clears. |
| **Survives limiting / bans** | 1 | Steam/early-bet = **fastest** limit trigger on soft books. Kalshi can't ban (only redeeming factor) but is efficient. |
| **Capacity (small bankroll)** | 3 | Soft corners are illiquid (no depth); liquid corners are efficient (no edge). Soft↔thin wall. |
| **Beats/escapes the crypto-box death** | 1 | **Same death**: last-in-queue vs co-located/on-site faster capital; adverse-selected resting quotes. |

**Overall: latency-walled + limiting-walled. Not deployable.** Identical structural verdict to the crypto
box, for the identical reason (last in queue behind faster, co-located capital), now compounded by
soft-book account bans.

**Is there ANY deployable live/steam/CLV edge for a seconds-latency cloud small-bankroll operator?**
**No.**
- **Live in-game:** pure latency game; cloud bot is the slowest node (delayed broadcast vs the book's
  sub-second official feed). **Dead.**
- **Steam-chasing:** sub-20s window the cloud can't hit, and the fastest path to being limited. **Dead.**
- **CLV harvest:** the signal is real and is the right proxy, but harvesting it = early soft-book bets =
  banned; the unbeatable-reference book (Pinnacle) is US-illegal. **Not retail-deployable.**
- **Kalshi in-play:** SIG-market-made on a real-time feed; liquid = efficient/fast, illiquid = wide/static.
  **Not a slow/soft maker pond.** A resting cloud quote is adversely selected — **the crypto box again.**

**Honest finding (as anticipated by the brief): "latency-walled, same as the crypto box."** The only thing
that changed vs the sportsbook side is *who* the faster actor is (SIG / pro fast-feed bettors instead of a
1.2s co-located crypto MM) — the *position* is unchanged: **the cloud bot is last in line.** No live, steam,
or CLV edge survives seconds-latency cloud execution. **Do not deploy.** Consistent with
`SPORTS_BETTING.md` and `SHARP_VS_KALSHI.md`: the single non-latency, non-banned candidate remains a *slow,
non-in-play* value-bet of Kalshi's *illiquid* slice vs a sharp feed — measured first, expected marginal —
which is explicitly **not** a live/steam/CLV-latency play.

---

### Method note
Web research cited inline (live-latency, steam, CLV/limiting, Kalshi in-play, SIG). Live Kalshi public-API
probes in this repo: `kalshi_sports_probe.py` (inventory/spreads/depth) and `kalshi_inplay_probe.py`
(open-not-closed in-play markets + 20s top-of-book motion sampling), run 2026-06-15 ~02:42Z. No paid feed
required for the structural conclusion; a forward CLV log (per `SHARP_VS_KALSHI.md`) would only refine the
*illiquid non-in-play* candidate, not revive the latency plays.
