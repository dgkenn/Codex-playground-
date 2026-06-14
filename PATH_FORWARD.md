# PATH FORWARD for live trading (2026-06-14) — edge check + plan

## Edge check (current data)
- SHADOW A/B n=217 (still < the 300 deploy bar). The ungated/always-on box `live_current` is now
  net-NEGATIVE: -1.35c/win, OOSnet -6.27c, maxDD 838c. The base box has NO edge in this regime.
- 2 LIVE runs failed: run-1 -$3.07 (strands held to settle), run-2 -$1.12 (escaped-strand tail).
- The ONLY positive-net signal anywhere is SELECTIVITY -- `t_edge_select` (open only mid-window k5-9 +
  mid-vol 3-8bps): +0.26c/win, best risk (maxDD 172c vs 838c), but selective (26% of windows) and NOT
  yet significant (diff vs live +1.51c, t=+1.07, n=217).
- `t11_sell_cheap` (t=3.53) and `t14_perp_hedge` (t=3.64) clear t>3 but only make a NEGATIVE base LESS
  negative -- not standalone edges (and perp is scale-gated + a directional artifact).
- NOTHING clears the deploy bar (t>3 vs live AND n>=300) or the risk-upgrade track.

## The lesson: SELECTIVITY, not always-on
The always-on two-sided box is a losing trade now (shadow + live). The only thing with positive
expectancy is trading ONLY the fat-box windows (mid-window, mid-vol) and skipping the strand-prone
high-vol/late-slot windows. We BUILT this capability: `--open-k-min/max` + `--open-sig-lo/hi` (the
edge-select gate) is now in the trader and set as the live config (k5-9, vol 3-8bps). The bot is no
longer the negative always-on box; when armed it trades only the demonstrated-edge regime.

## The plan (disciplined; bot stays OFF until proven)
1. **Bot OFF** -- do not re-arm the negative always-on box. (Done: switch off; live config is now the
   SELECTIVE one so any future arm trades the edge regime, not the losing box.)
2. **Accumulate forward, free** -- the shadow collector keeps running; `t_edge_select` accumulates.
   GATE TO GO LIVE: t_edge_select (or the selective config) clears t>3 vs live AND n>=300, OR the
   risk-upgrade track. At ~44 windows/day from n=217, that's ~2 days more data minimum.
3. **The trader is now HARDENED** (full audit fixed): no naked leg rides to settlement (force-flatten),
   the loss-limit actually caps (liquidate-on-exit + worst-case mark), the inventory clamp can't leak.
   So IF re-armed, a bad run is bounded by the $6 loss-limit -- the downside is now genuinely capped.
4. **When/if it clears:** a BOUNDED selective live test (small size, watched by live_gate.py), then
   scale per SCALE_GATE only after net-positive on live.

## Honest expectation
Even the best candidate is a TINY selective edge (~+0.26c/win x 26% of windows = pennies/day at $5).
Meaningful money requires (a) it actually clearing the bar forward AND (b) scale. The disciplined,
zero-cost path is: keep the shadow test running, keep the bot off, and only commit real money when a
SELECTIVE config clears the pre-registered bar. The research has been exhaustive; the edge, if it
exists, is thin and selective -- trade it small and only when proven, or accept it's not worth it at
this scale. No re-arm without the operator's call.
