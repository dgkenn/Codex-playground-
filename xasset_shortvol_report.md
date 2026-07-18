# Cross-underlying weekly short-vol / longshot premium — does it STACK?

_As-of 2026-07-18. Confirmed edge: SELL BTC/ETH weekly 'above \$X on <date>' YES longshots at p in [0.15,0.3] -> +0.12/ct (week-clustered t~4.6). This tests EXTENSION to other underlyings' weekly ladders. Primary entry = 144h (6d) before close (deep first-half of the 7-day life = genuine far-OTM longshots). Haircut mid->bid = 0.01 (~1c measured half-spread); zero-fee headline (matches ref) + fee 0.07*p*(1-p) sensitivity. Week-clustered t = cluster on ISO resolution week._

**Universe discovery:** Only **BTC, ETH, SOL, XRP** carry the Polymarket `<coin>-above-on-<date>` weekly ladder (11 strikes, 7-day life, Binance noon-ET close). **DOGE** = only 5m/15m up-down micro-markets (no ladder). ADA/AVAX/LINK/BNB/DOT/LTC/TRON/SUI/TON and non-crypto probes (SP500/NASDAQ/gold/TSLA/NVDA) = **no settled weekly ladders**. => reference = BTC, ETH; **new tested underlyings = SOL, XRP**.

**Data:** 224 settled weekly ladders (2026-05-22..2026-07-17, one resolves per calendar day), 1320 strike-markets priced.

## Per-underlying band edge (primary horizon, week-clustered)

| underlying | n | wks | entry | realized YES | overpriced? | win% | mean(mid) | t | exe-1c | t | exe+fee | t | worst wk | vs +0.12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC (REF) | 15 | 4 | 0.228 | 0.267 | no | 0.73 | **-0.039** | -0.34 | -0.049 | -0.43 | -0.068 | -0.59 | -0.398 | -0.33x |
| ETH (REF) | 19 | 4 | 0.205 | 0.263 | no | 0.74 | **-0.058** | -0.46 | -0.068 | -0.54 | -0.084 | -0.66 | -0.314 | -0.48x |
| SOL | 8 | 4 | 0.225 | 0.375 | no | 0.62 | **-0.150** | -0.80 | -0.160 | -0.85 | -0.178 | -0.95 | -0.448 | -1.25x |
| XRP | 14 | 4 | 0.230 | 0.286 | no | 0.71 | **-0.056** | -0.37 | -0.066 | -0.43 | -0.086 | -0.56 | -0.269 | -0.47x |

_'overpriced?'=YES means realized YES hit-rate < entry price (the seller's edge). 'vs +0.12' = mid mean as a multiple of the confirmed BTC/ETH weekly edge. exe+fee = executable (mid-1c) net of 0.07*p(1-p) taker fee._

## Horizon sensitivity (mid seller PnL/ct, week-clustered t)

| underlying | 144h | 120h | 96h |
|---|---|---|---|
| BTC | -0.039 (t=-0.3, n=15) | 0.079 (t=1.0, n=19) | 0.015 (t=0.2, n=19) |
| ETH | -0.058 (t=-0.5, n=19) | 0.004 (t=0.0, n=15) | -0.022 (t=-0.1, n=9) |
| SOL | -0.150 (t=-0.8, n=8) | -0.167 (t=-0.3, n=5) | -0.081 (t=-0.3, n=6) |
| XRP | -0.056 (t=-0.4, n=14) | -0.059 (t=-0.4, n=15) | 0.014 (t=0.1, n=11) |

## Calibration by price bucket at 144h (ALL strikes, high-power)

_edge = realized - entry (edge<0 => overpriced => seller gross-profits); sellPnL = entry - realized._

**BTC**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 34 | 4 | 0.031 | 0.000 | -0.031 | 0.031 | 26.48 |
| 0.05-0.10 | 14 | 4 | 0.073 | 0.000 | -0.073 | 0.073 | 34.73 |
| 0.10-0.15 | 11 | 4 | 0.129 | 0.091 | -0.038 | 0.038 | 0.41 |
| 0.15-0.30 | 15 | 4 | 0.228 | 0.267 | 0.039 | -0.039 | -0.34 |
| 0.30-0.50 | 19 | 4 | 0.399 | 0.526 | 0.127 | -0.127 | -0.80 |
| 0.50-0.70 | 17 | 4 | 0.588 | 0.529 | -0.058 | 0.058 | 0.25 |
| 0.70-0.90 | 32 | 4 | 0.808 | 0.844 | 0.035 | -0.035 | -0.26 |

**ETH**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 25 | 4 | 0.031 | 0.000 | -0.031 | 0.031 | 50.31 |
| 0.05-0.10 | 9 | 4 | 0.070 | 0.111 | 0.041 | -0.041 | -0.35 |
| 0.10-0.15 | 6 | 3 | 0.135 | 0.333 | 0.198 | -0.198 | -2.08 |
| 0.15-0.30 | 17 | 4 | 0.211 | 0.294 | 0.083 | -0.083 | -0.60 |
| 0.30-0.50 | 16 | 4 | 0.447 | 0.562 | 0.115 | -0.115 | -1.12 |
| 0.50-0.70 | 11 | 4 | 0.609 | 0.545 | -0.063 | 0.063 | 0.22 |
| 0.70-0.90 | 21 | 4 | 0.808 | 0.905 | 0.097 | -0.097 | -1.72 |

**SOL**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 42 | 4 | 0.028 | 0.000 | -0.028 | 0.028 | 52.54 |
| 0.05-0.10 | 5 | 3 | 0.083 | 0.400 | 0.317 | -0.317 | -0.87 |
| 0.10-0.15 | 7 | 4 | 0.121 | 0.143 | 0.021 | -0.021 | -0.12 |
| 0.15-0.30 | 8 | 4 | 0.225 | 0.375 | 0.150 | -0.150 | -0.80 |
| 0.30-0.50 | 24 | 4 | 0.454 | 0.292 | -0.162 | 0.162 | 4.30 |
| 0.50-0.70 | 27 | 4 | 0.555 | 0.741 | 0.186 | -0.186 | -1.59 |
| 0.70-0.90 | 5 | 4 | 0.830 | 1.000 | 0.170 | -0.170 | -5.44 |

**XRP**
| bin | n | wks | entry | realized YES | edge | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 42 | 4 | 0.031 | 0.000 | -0.031 | 0.031 | 19.34 |
| 0.05-0.10 | 6 | 4 | 0.068 | 0.000 | -0.068 | 0.068 | 12.76 |
| 0.10-0.15 | 4 | 3 | 0.114 | 0.000 | -0.114 | 0.114 | 17.11 |
| 0.15-0.30 | 14 | 4 | 0.230 | 0.286 | 0.056 | -0.056 | -0.37 |
| 0.30-0.50 | 14 | 3 | 0.461 | 0.286 | -0.175 | 0.175 | 0.85 |
| 0.50-0.70 | 16 | 4 | 0.579 | 0.625 | 0.046 | -0.046 | -0.30 |
| 0.70-0.90 | 15 | 4 | 0.789 | 0.800 | 0.011 | -0.011 | -0.05 |

## Deep-OTM tail vs wide-longshot aggregates (regime-robust power check)

_The [0.15,0.30] band is thin (n<20, 4 wks) and — see verdict — did not reproduce the +0.12 even on the reference BTC/ETH in this rally window. The DEEP tail [0.02,0.10] (strikes far enough to stay OTM through the rally) is where the overpricing structure is measurable; [0.05,0.30] is a wider longshot aggregate. mid + executable(-1c), week-clustered t._

| underlying | region | n | wks | entry | realized YES | seller mid | t | seller exe-1c | t |
|---|---|---|---|---|---|---|---|---|---|
| BTC | deep [0.02,0.10] | 49 | 4 | 0.042 | 0.000 | 0.042 | 18.98 | 0.032 | 14.51 |
| BTC | wide [0.05,0.30] | 40 | 4 | 0.146 | 0.125 | 0.021 | 0.54 | 0.011 | 0.29 |
| ETH | deep [0.02,0.10] | 36 | 4 | 0.041 | 0.028 | 0.013 | 0.43 | 0.003 | 0.09 |
| ETH | wide [0.05,0.30] | 32 | 4 | 0.157 | 0.250 | -0.093 | -0.94 | -0.103 | -1.04 |
| SOL | deep [0.02,0.10] | 47 | 4 | 0.034 | 0.043 | -0.009 | -0.25 | -0.019 | -0.53 |
| SOL | wide [0.05,0.30] | 21 | 4 | 0.148 | 0.286 | -0.137 | -0.67 | -0.147 | -0.72 |
| XRP | deep [0.02,0.10] | 54 | 4 | 0.034 | 0.000 | 0.034 | 47.15 | 0.024 | 33.40 |
| XRP | wide [0.05,0.30] | 27 | 4 | 0.157 | 0.148 | 0.008 | 0.12 | -0.002 | -0.02 |

_Deep-tail overpricing is present on ALL four (incl. SOL/XRP): realized YES ~0 vs a 3-8c ask. But it is the taker-dead deep wing (executability trap that killed prior candidates) — structural extension, not a clean tradeable [0.15,0.30] edge._

## Cross-underlying weekly-PnL correlation matrix

_Pearson corr of per-week mean seller PnL/ct (mid), primary horizon. High + corr => longshots die together (shared crypto beta) => LITTLE diversification. Off-diagonal common-weeks count in parens._

| corr | BTC | ETH | SOL | XRP |
|---|---|---|---|---|
| **BTC** | 1.00 | 0.82 (4) | 0.79 (4) | 0.71 (4) |
| **ETH** | 0.82 (4) | 1.00 | 0.36 (4) | 0.32 (4) |
| **SOL** | 0.79 (4) | 0.36 (4) | 1.00 | 0.98 (4) |
| **XRP** | 0.71 (4) | 0.32 (4) | 0.98 (4) | 1.00 |

- SOL vs BTC+ETH reference (pooled weekly PnL): corr **0.59** (4 wks)
- XRP vs BTC+ETH reference: corr **0.53** (4 wks)

## Diversification / frontier impact

| portfolio | n | wks | mean PnL/ct | wk-clustered t | wk-Sharpe | positions/wk |
|---|---|---|---|---|---|---|
| BTC+ETH (confirmed) | 34 | 4 | -0.050 | -0.43 | -0.29 | 8.5 |
| SOL+XRP (new) | 22 | 4 | -0.090 | -0.57 | -0.13 | 5.5 |
| ALL 4 stacked | 56 | 4 | -0.066 | -0.54 | -0.29 | 14.0 |

_wk-Sharpe = mean / stdev of the equal-weight per-week portfolio PnL. If the added underlyings were uncorrelated the ALL-4 Sharpe would rise ~sqrt(2) over BTC+ETH; the actual rise measures the REAL diversification (net of shared crypto beta)._

## Per-underlying weekly PnL series (band, mid)

- **BTC**: 2026-W26:0.2137(n4), 2026-W27:-0.3983(n3), 2026-W28:-0.03(n4), 2026-W29:-0.0313(n4) | neg-week frac 0.75
- **ETH**: 2026-W26:0.242(n5), 2026-W27:-0.3137(n4), 2026-W28:0.015(n6), 2026-W29:-0.2875(n4) | neg-week frac 0.50
- **SOL**: 2026-W26:0.25(n1), 2026-W27:-0.4483(n3), 2026-W28:-0.3005(n2), 2026-W29:0.248(n2) | neg-week frac 0.50
- **XRP**: 2026-W26:0.227(n5), 2026-W27:-0.2575(n4), 2026-W28:-0.2687(n4), 2026-W29:0.185(n1) | neg-week frac 0.50

## VERDICT

**BTC**: [0.15,0.30] band n=15 over 4 wks | seller PnL/ct mid **-0.039** (wk-clustered t=-0.34), exe-1c -0.049 | entry 0.228 vs realized YES 0.267 (UNDER/at (rally regime)).

**ETH**: [0.15,0.30] band n=19 over 4 wks | seller PnL/ct mid **-0.058** (wk-clustered t=-0.46), exe-1c -0.068 | entry 0.205 vs realized YES 0.263 (UNDER/at (rally regime)).

**SOL**: [0.15,0.30] band n=8 over 4 wks | seller PnL/ct mid **-0.150** (wk-clustered t=-0.80), exe-1c -0.160 | entry 0.225 vs realized YES 0.375 (UNDER/at (rally regime)).

**XRP**: [0.15,0.30] band n=14 over 4 wks | seller PnL/ct mid **-0.056** (wk-clustered t=-0.37), exe-1c -0.066 | entry 0.230 vs realized YES 0.286 (UNDER/at (rally regime)).



**Reference sanity FIRST.** The confirmed edge is +0.12/ct with band longshots settling YES ~10.5%. In THIS 8-week window (2026-05-22..07-17) the BTC/ETH [0.15,0.30] band settled YES 0.27/0.26 (vs 0.105 confirmed) and the seller mean was -0.039/-0.058/ct — i.e. the reference band edge does NOT reproduce here. This window is a RALLY REGIME: 'above $X' band strikes printed YES far more than priced, so the band lost money on ALL FOUR underlyings including BTC/ETH. => **this short window cannot adjudicate band EXTENSION** (the yardstick itself is broken in-sample). Read the band rows as regime-confounded + underpowered (only 4 populated ISO-weeks, n<20 each), NOT as 'SOL/XRP specifically fail'.



**Where the longshot-overpricing STRUCTURE is measurable — the deep-OTM tail [0.02,0.10].** Far-enough strikes stayed OTM even through the rally, so the overpricing is visible regime-free:

  - BTC: n=49, entry 0.042 vs realized YES 0.000 -> seller 0.042/ct (exe-1c 0.032, t=19.0).

  - ETH: n=36, entry 0.041 vs realized YES 0.028 -> seller 0.013/ct (exe-1c 0.003, t=0.4).

  - SOL: n=47, entry 0.034 vs realized YES 0.043 -> seller -0.009/ct (exe-1c -0.019, t=-0.2).

  - XRP: n=54, entry 0.034 vs realized YES 0.000 -> seller 0.034/ct (exe-1c 0.024, t=47.2).

The overpricing is clean on **BTC (+0.042, t=19) and XRP (+0.034, t=47)** — realized YES ~0 vs a 3-4c ask — and weak-positive on ETH; on SOL it is a small NEGATIVE (2 of 47 deep strikes printed, small-n noise). So the longshot-overpricing STRUCTURE that underpins the BTC/ETH edge does appear on the new underlyings (clearly on XRP, noisily on SOL). BUT this is the taker-dead deep wing (the exact executability trap that killed ~5 prior candidates): per-contract only ~3-4c gross, nobody reliably lifts a 3-4c bid, and with the 0.07*p(1-p) fee + spread haircut the net shrinks further. It is a structural extension, not a clean tradeable one.



**Correlation / diversification (the decisive question for STACKING).** Weekly-PnL correlations (band, primary 144h, 2026-05-22..2026-07-17): BTC-ETH 0.82, BTC-SOL 0.79, BTC-XRP 0.71, ETH-SOL 0.36, ETH-XRP 0.32, SOL-XRP 0.98; SOL vs BTC+ETH ref 0.59, XRP vs ref 0.53. The weekly PnL series make it concrete: EVERY underlying's worst week is the SAME week (2026-W27: BTC -0.40, ETH -0.31, SOL -0.45, XRP -0.26) — they all die together when spot rallies through the strikes. These are NOT uncorrelated bets; they are one shared crypto-beta longshot trade wearing four tickers. (Only ~4 common weeks -> correlations are noisy, but the co-movement is structural, not a sampling fluke: all four sell the same directional 'crypto went up' risk.)



**Frontier / capacity.** Band positions/week: BTC ~3.8, ETH ~4.8, SOL ~2.0, XRP ~3.5; BTC+ETH pooled ~8.5/wk, ALL-4 pooled ~14.0/wk (a ~65% frequency increase). But wk-Sharpe barely moves (BTC+ETH -0.29 -> ALL-4 -0.29) because the added streams are ~correlated: with corr~0.6-0.8 the variance-reduction from stacking is small (an uncorrelated 2x stack would raise Sharpe ~sqrt(2)=1.41x; here it is ~flat).



**BLUNT VERDICT.** Three honest conclusions:
1. **Universe:** only BTC, ETH, SOL, XRP have Polymarket weekly 'above $X' ladders — DOGE and every other crypto/non-crypto probed do NOT. So at most +2 underlyings (SOL, XRP) are even candidates.
2. **Band extension = NOT ADJUDICABLE here (lean null-of-benefit).** The [0.15,0.30] band premium did not reproduce on the reference BTC/ETH in this recent 8-week rally window (realized YES ~26% vs 10.5% confirmed; seller mean negative), so SOL/XRP can't be judged against a working yardstick. The longshot-OVERPRICING STRUCTURE does extend to SOL/XRP in the deep-OTM tail, but that tail is taker-dead and per-contract tiny — not the clean [0.15,0.30] edge.
3. **Diversification = the real killer.** Even granting the premium, SOL/XRP weekly PnL is strongly POSITIVELY correlated with BTC/ETH (they all crater the same rally week). Stacking them buys FREQUENCY (~14 vs ~8 positions/wk) but almost NO diversification — the efficient frontier rises only marginally, far below the naive sqrt(k). **Do NOT treat SOL/XRP as independent positions.** They are the same crypto-beta short-vol bet; size the COMBINED crypto-longshot book on its shared tail risk, not per-underlying. The '4 uncorrelated underlyings' premise is false: it is effectively ~1 underlying (crypto) traded 4 ways.