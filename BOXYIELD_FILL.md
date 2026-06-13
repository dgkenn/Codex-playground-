# BOX-YIELD Phase 1 -- FILL CONVERSION (GAIN side)

Objective term: **#boxes filled x P(both fill)**, maker-only (no spread paid). All numbers from re-replaying the Kalshi 15m tape (BTC primary, ETH cross-check); IS=first 60% of windows, OOS=last 40%. Backtests SCREEN; forward-validate before arming.

## 1. Baseline conversion (at-touch, q0=0)

| split | n | boxes/window | P(both fill) | maker-fill rate | strand% | net/w | total |
|---|---|---|---|---|---|---|---|
| IS | 552 | 8.301 | 0.991 | 100% (maker by constr.) | 16.67% | +0.734c | +405.4c |
| OOS | 368 | 9.136 | 0.995 | 100% (maker by constr.) | 11.96% | +2.753c | +1013.2c |

- OOS: net=+2.753c boxes/w=9.136 P(both)=0.995 strand=11.96% total=+1013.2c t=+3.41
- P(both fill) here = P(at least one completed box in the window). The stated live ~0.93 corresponds to 1-strand; OOS strand below is consistent with that.

## 3. K-slot fill conversion (minute k=2..12)

`opens` = legs opened at slot k; `pair_rate` = fraction that later completed a box; `fills` = total fills (either side) landing at slot k.

| k | IS opens | IS pair_rate | OOS opens | OOS pair_rate | OOS fills |
|---|---|---|---|---|---|
| 2 | 532 | 1.000 | 362 | 1.000 | 703 |
| 3 | 519 | 0.998 | 348 | 1.000 | 703 |
| 4 | 502 | 0.998 | 346 | 1.000 | 701 |
| 5 | 506 | 0.996 | 343 | 1.000 | 705 |
| 6 | 498 | 0.986 | 339 | 1.000 | 703 |
| 7 | 472 | 0.992 | 340 | 0.997 | 681 |
| 8 | 443 | 0.984 | 326 | 0.997 | 678 |
| 9 | 394 | 0.962 | 314 | 0.990 | 643 |
| 10 | 343 | 0.959 | 289 | 0.965 | 591 |
| 11 | 273 | 0.945 | 234 | 0.949 | 464 |
| 12 | 192 | 0.865 | 165 | 0.897 | 341 |

Boxes/window if we restrict opening to early slots (k<=K), OOS:

| max k | boxes/w | P(both) | net/w | strand% |
|---|---|---|---|---|
| 4 | 2.870 | 0.986 | +1.022c | 0.00% |
| 6 | 4.723 | 0.986 | +2.049c | 0.00% |
| 8 | 6.527 | 0.995 | +2.704c | 0.54% |
| 10 | 8.130 | 0.995 | +3.436c | 4.08% |
| 12 | 9.136 | 0.995 | +2.753c | 11.96% |

- Early slots (k<=5) mean pair_rate=1.000 vs late (k>=9) 0.950. Window-open quoting fills both legs far more reliably (book is balanced, taker flow two-sided); late slots strand more (directional resolution + thinning book).

## 2. Improve-tick / queue-ahead frontier

Post 1c INSIDE the touch on the completing side(s) -> wider fill trigger + front of queue (q0_eff~0), at the cost of 1c locked edge on each improved leg. Modeled by re-pricing the resting quote and re-replaying taker crossings.

| policy | boxes/w | P(both) | strand% | net/w | total | dnet vs base | t(paired) |
|---|---|---|---|---|---|---|---|
| at-touch (base) | 9.136 | 0.995 | 11.96% | +2.753c | +1013.2c | +0.000c | +nan |
| improve YES 1c | 9.174 | 0.995 | 11.14% | +2.365c | +870.4c | -0.388c | -1.17 |
| improve NO 1c | 9.174 | 0.995 | 10.87% | +2.326c | +856.1c | -0.427c | -1.42 |
| improve BOTH 1c | 9.136 | 0.995 | 11.96% | +2.645c | +973.2c | -0.109c | -4.65 |

- Improve-BOTH adds +0.000 boxes/window. Each improved box gives up ~2c of locked edge (1c/leg). Break-even box gain = (edge surrendered)/(edge per incremental box). Net effect on locked edge is the `dnet` column above.
- **MECHANISM NOTE (load-bearing):** the tape's mean spread is 1c. Posting 1c inside the touch on BOTH sides locks/crosses the book (my_bid>=my_ask), so the reconstructor falls back to at-touch -- which is why improve-BOTH boxes==base. The only realizable improve on a 1c book is SINGLE-sided. Single-sided improve does add a sliver of boxes (9.174 vs 9.136) and trims strand (11.1-10.9% vs 12.0%), but the 1c edge surrendered on the improved leg swamps the gain: break-even needs ~1 extra box per 1c-improved leg, we get ~0.04. **Improve-tick is a LOSER on the current 1c-spread book at q0=0.** It would only turn positive on a wider-spread book OR under real queue-ahead (q0>=500 row).

Queue-ahead sensitivity (at-touch, q0 = contracts ahead before our size fills). True position is UNOBSERVABLE; this brackets it.

| q0 | boxes/w | P(both) | strand% | net/w |
|---|---|---|---|---|
| 0 | 9.136 | 0.995 | 11.96% | +2.753c |
| 250 | 7.940 | 0.995 | 36.14% | -14.847c |
| 500 | 7.467 | 0.995 | 43.48% | -20.978c |
| 1000 | 6.826 | 0.995 | 48.91% | -28.579c |
| 2000 | 5.870 | 0.995 | 62.77% | -38.147c |

Improve-tick value GROWS when queue-ahead is real (improved quote jumps to front). Below: base pays q0=500, improved legs pay 0.

| policy | boxes/w | P(both) | net/w | dnet |
|---|---|---|---|---|
| at-touch q0=500 | 7.467 | 0.995 | -20.978c | 0 |
| improve BOTH (q0_imp=0) | 7.476 | 0.995 | -20.586c | +0.392c |

## 4. Completion-regime open bar

`completion_score` (0..4): thin depth<5500, balanced |flow|<250, flat OI, 1c spread. We OPEN normally everywhere, but test (a) opening ONLY in high-completion regimes and (b) improving-tick ONLY in high-completion regimes (open more where boxes complete).

| policy | boxes/w | P(both) | strand% | net/w | dnet | t(paired) |
|---|---|---|---|---|---|---|
| base (open all) | 9.136 | 0.995 | 11.96% | +2.753c | +0.000c | +nan |
| open only score>=2 | 0.163 | 0.141 | 0.27% | +0.065c | -2.689c | -3.34 |
| open only score>=3 | 0.000 | 0.000 | 0.00% | +0.000c | -2.753c | -3.41 |
| improve-both, open score>=3-or-attouch | 9.084 | 0.995 | 11.96% | +2.630c | -0.123c | -1.22 |

**Read:** the base book ALREADY completes P(both)=0.995 -- there is no slack to "open more in high-completion regimes" because we already open everywhere and almost everything pairs. Gating opens on completion_score>=2/3 is destructive (it discards 98%+ of fills, since score>=3 needs thin depth AND 1c spread simultaneously, which is rare). The completion-regime lever is the WRONG knob for THIS book: the bottleneck is not a high open bar, it is late-slot (k>=11) strands. Lowering the open bar can only help when the live policy is currently REFUSING opens (e.g. t36 guarded-opener) -- those refused fills are where regime-conditional opening would recover boxes; on the ungated replay there is nothing to recover.

## 5. Multi-slot re-quote & asymmetric size skew

- A 2nd box completes in **99.2%** of OOS windows under the natural |net|<=1 re-quote (mean boxes/w=9.136). Distribution of boxes/window (OOS): 0:1%, 1:0%, 2:0%, 3:0%.

Size-skew toward the SLOWER-filling side to raise P(both): the late/directional slots strand the side the market is moving away from. We test skewing OPEN size by which side is lagging (proxy: open the favorite-flow side at full, the contra side smaller).

| policy | boxes/w | P(both) | strand% | net/w | dnet |
|---|---|---|---|---|---|
| base unit size | 9.136 | 0.995 | 11.96% | +2.753c | 0 |
| skew-down adverse-flow opens | 9.136 | 0.995 | 11.96% | +1.968c | -0.785c |

## IS/OOS stability (headline candidates)

| candidate | IS dnet | IS boxes/w | OOS dnet | OOS boxes/w |
|---|---|---|---|---|
| improve YES 1c | -0.103c | 8.341 | -0.388c | 9.174 |
| improve NO 1c | -0.295c | 8.333 | -0.427c | 9.174 |
| improve BOTH 1c | -0.096c | 8.301 | -0.109c | 9.136 |
| open k<=8 | +0.128c | 6.250 | -0.050c | 6.527 |

## ETH cross-check (OOS)

- base: boxes/w=6.984 P(both)=1.000 net=-13.151c

- improve-both: boxes/w=7.166 P(both)=1.000 net=-15.693c dnet=-2.542c t=-7.70

## Recommended fill-conversion rules + trader-flag sketch

```
# fill-conversion flags (screen-validated; arm behind a forward A/B)
--improve-tick-side {none|yes|no|both}   # post 1c inside touch on completing side
--improve-completion-min 3               # only improve when completion_score>=N
--quote-kmax 12                          # cap opening slot (early slots convert best)
--skew-adverse-flow 1.0                  # size mult on adverse-flow opens (1.0=off)
```

Decision rule (from the frontier):
- Improve-tick is **NET NEGATIVE** on locked edge OOS at q0=0 (dnet=-0.109c for both sides). The 1c/leg edge given up is the dominant cost on a 1c-spread book -- at q0=0 we are ALREADY assumed front-of-queue, so improving buys few extra boxes. Improve-tick only pays when REAL queue-ahead is large (see q0=500 row): then jumping the queue converts stranded windows into boxes faster than the 1c costs.

- Best single-side improve: YES (dnet=-0.388c) -- improve the SLOWER-filling leg only.

- K-slot: window-open slots convert best; do NOT chase late-window opens hoping to pair.

## Tape caveats (what the replay can vs cannot prove)

- **Queue position is not observable.** q0=0 = optimistic front-of-queue; the q0 sweep brackets the pessimistic case. The improve-tick verdict FLIPS sign between q0=0 and q0=500, so the real-world answer depends on our actual queue depth -- measure it live before arming.

- **Improve-tick reflexivity:** posting inside narrows the spread other makers see; they may re-improve, eroding the queue jump. A replay holds the book fixed and cannot model this -- treat improve-tick dnet as an UPPER bound.

- **Same-flow assumption:** we assume the takers who crossed the old touch still cross the 1c-improved price. For trades strictly between b0 and a0 this is true by price; for the marginal taker it is a screen.

- All deltas are SCREENS on a fixed tape; t-stats are paired per-window. Forward-validate behind the 2-sigma alert + deploy bar before arming any flag.

