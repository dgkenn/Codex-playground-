---
name: kwx-study-audit
description: Adversarially audit a claimed trading edge or backtest result before believing it — the checklist that has refuted every false positive in this repo. Use for "verify this edge", "audit this backtest", "is this result real", "review this study".
---

# Adversarial study audit (the checklist that kills false edges)

Run this against ANY claimed positive result before it is treated as real. Every item below has
personally executed at least one kill in this repo. Audits run on Fable (judge tier) per
`CLAUDE.md`; a REFUTED verdict is a successful audit.

## The checklist, in kill-count order

1. **Marketability / execution reality.** Would the order actually rest (limit) or fill (taker)
   at the claimed price? Pull real 1-min candlesticks at the claimed entry times and check the
   best ask/bid. *(Killed the maker study: 26/32 "resting bids" would have crossed the spread —
   n=22.5 fills → n=2.)*
2. **Outcome-conditioned detectors.** Does any entry/lock condition secretly use the answer
   (e.g. "ask>=98c" as a lock signal — the market's knowledge is the outcome)? *(Flipped 9/36
   early-lock cells; cut mentions EV 6x.)*
3. **Look-ahead vs real feed latency.** When was each datum actually AVAILABLE? IEM asos1min:
   22-34h publication lag (fine for backtests, fiction for live timing). Zero-latency
   assumptions are always wrong. *(Killed maker M4; the near-miss diagnosis quantified it.)*
4. **Multiple comparisons.** Bonferroni (or better) across EVERY spec/cell the whole funnel
   tested — not just this study's. 27 effective cells → the t bar is ~3.11, not 1.96. *(Killed
   the early-lock "headline positive" cells.)*
5. **Day-clustered statistics.** Same-day fires are one draw, not n draws. Re-derive the t
   yourself from the committed rows. *(Maker's t=6.22 was on a variable that couldn't go
   negative — significance proved nothing.)*
6. **Fee math.** `ceil(7*p*(1-p))/100` per contract, charged at the crossing price. Check the
   maker-fee exemption claim per series (`fee_type` field) rather than assuming.
7. **Fit/validation contamination.** Was any parameter chosen after seeing validation data?
   Sign-flip between sample halves = seasonal drift eaten by a static fit. *(Killed directional
   SPEC 4 at n=2,109.)*
8. **Sample-size floors and dust.** Wilson CI at the REAL n of independent events (triple-counted
   fills at P=93/95/97 are one event). Cap fill credit at the print's actual `count_fp` — 0.01ct
   dust prints are not fills. *(Maker M2/M3.)*
9. **Survivorship in the data pull.** Did the harvest silently drop failed fetches/stations that
   would have carried losses?
10. **Capacity vs claim.** Does the claimed $/period survive the observed book depth
    (`DEPTH_CAP`, `depth_within_2c`) and a market-impact haircut at the implied order size?

## Verified reproduction of past audits

```bash
python wx_maker_deep_study.py             # naive table vs strict recount, verdict REFUTED
python wx_earlylock_deep_study.py         # 5,415 rows, no Bonferroni-significant cell
./.claude/skills/run-kwx/driver.sh studies
```

Docs with full worked examples: `wx_maker_deep_study.md`, `wx_earlylock_deep_study.md`,
`WX_DIRECTIONAL.md` (kill-report format), `WX_NEARMISS_DIAGNOSIS.md`.
