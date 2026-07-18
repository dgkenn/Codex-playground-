# Conviction-scaled sizing ("press the good ones harder / unload the clip") — data-backed verdict

MC (`kwx_conviction_sizing.py`) on the REAL fires, conviction defined from data: CUSHION (highest margin
m∈{1,2,3} that still fired = how far obs cleared the strike) × GAP (100¢−price). Stressors: 21% unfillable,
2%/day heat-dome (all lose), conviction model-error tail (0/0.5/1%), 25-ct/fire depth cap, 60%/day deploy cap.

## Empirical premise (confirmed): bigger cushion = safer, but LESS profit
| cushion | n | loss rate | mean gap | mean PnL |
|---|---|---|---|---|
| 1–2°F | 644 | 0.93% | 0.333 | +0.312 |
| 2–3°F | 450 | 0.00% | 0.204 | +0.195 |
| ≥3°F | 604 | 0.00% | 0.110 | +0.105 |
Cushion↑ ⇒ loss↓ (safety confirmed) BUT gap↓ (market already repriced the obvious ones). Cushion & profit
oppose. The real target = high cushion AND still-cheap: cushion≥2°F & gap≥15¢ = n=350, 0% loss, +0.29–0.33/ct.

## Sizing sweep ($100 bankroll = the regime where the per-fire cap binds below depth; with 60%/day cap)
| rule | median | p5 | ruin% | worst-day |
|---|---|---|---|---|
| FLAT 5% | 17.0x | 11.8x | 0.0 | −61% |
| conviction cap 10% | 17.5x | 12.4x | 0.0 | −62% |
| conviction cap 20% | 17.7x | 12.6x | 0.0–0.1 | −62% |
| conviction cap 40% / 100% | **17.7x (identical to 20%)** | 12.6x | 0.1 | −62% |

## Verdict on "unload the clip": NO — three data-backed reasons
1. **It's physically impossible.** Book depth caps every fire at ~25 contracts (~$20). Above ~$400 bankroll the
   per-fire cap NEVER binds — depth does — so 5%=20%=100% cap are identical. The market won't sell you the clip.
2. **Even where possible (small bankroll) the payoff is tiny.** Pressing conviction fires 5%→20% cap buys only
   ~+4% median growth (17.0x→17.7x). Going past 20% adds literally nothing (depth-limited).
3. **Safety comes from the DAILY cap, not the per-fire cap.** With the 60%/day deploy cap, even a heat-dome day
   is −62% and ruin ~0%, at ANY per-fire cap. Without it (earlier run) worst-day was −93%→−101% (near-wipeout).
   So the daily cap is the real control; upsizing individual fires is safe ONLY because the daily cap contains it.

## Recommendation (data-backed)
- DETECT conviction (cushion≥2°F & gap≥15¢ — computable live from obs−strike and price) — worth doing.
- PRESS it MILDLY: raise those fires' per-fire cap to ~10–15% (captures ~all of the ~+4% available), keep base 5%.
- KEEP the 60%/day deploy cap + depth-limited fills — that's what makes any upsizing safe.
- Do NOT "unload the clip": impossible above small bankroll (depth), and pure added tail with ~0 extra growth.
The instinct (press the safest+cheapest fires) is right and mildly +EV; the "max the bankroll" version is
contained by the order book and would only be dangerous without the daily cap.
