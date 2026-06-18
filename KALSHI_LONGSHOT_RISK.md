# Longshot-maker harvest — risk / sizing & deployment go/no-go (2026-06-18)

Closes the 4th stream (the risk agent was cut off by a session limit before committing; this is the
direct Monte-Carlo + the consolidated decision). Edge & constraints established in `KALSHI_MAKER_VERDICT.md`,
`KALSHI_MAKER_ADVSEL.md` (+0.97c/contract, 17σ, survives adverse selection), `KALSHI_MAKER_CAPACITY.md` and
`KALSHI_LONGSHOT_CAPACITY2.md` (~$30–150/mo ceiling; no deep-market version — bias decays then flips negative
with volume).

## Monte-Carlo (20k months, edge +0.97c/contract, entry e=0.12, true-YES = e−0.0097, independent fills)
Per **1-contract** clip:
| fills/mo | mean | sd | P(losing month) | p5 | worst of 20k |
|---|---|---|---|---|---|
| 100 | +$0.98 | $3.10 | 31% | −$4 | −$15 |
| 300 | +$2.87 | $5.45 | 26% | −$6 | −$21 |
| 1000 | +$9.75 | $9.83 | 15% | −$7 | −$29 |

P&L scales linearly with clip size. To reach the **$30–150/mo** capacity ceiling you need ~10–50-contract
clips (capacity-permitting), which scales the tail proportionally: at 50× clips a worst-decile month ≈ −$1,000.

## Risk verdict
- **Ruin is effectively impossible** at sane clips: max loss per position ≈ $0.88 (collateral on a sold
  longshot), so losing even $100 needs ~114 simultaneous longshot hits. A $1–5k bankroll is far more
  collateral than capacity can ever use — **fills, not capital, are the binding constraint.**
- **Negative skew is real but small in absolute terms.** 26–31% of months are negative at low fill counts;
  you need **≥300 independent fills/mo** to make ~85% of months positive. Diversify across many *uncorrelated*
  longshots (different events) — correlated tails (one macro surprise hitting many political longshots at once)
  are the only thing that bites, so cap exposure per event-theme.
- **Min safe bankroll:** $1k is plenty for 1–10-contract clips (~$1–30/mo, trivial tail). To push toward
  $150/mo via ~50× clips and ride the −$1k tail months, want ~$3–5k.

## CONSOLIDATED GO/NO-GO
**The edge is REAL, deployable, low-ruin-risk — and small.** It is the first genuinely +EV, queue-independent,
adverse-selection-surviving, maker-fee-free, retail-accessible Kalshi edge the project has found. But:
- **Risk-adjusted return: ~$1–30/mo at safe small clips; ~$30–150/mo only at larger clips that invite −$1k
  tail months and assume capacity you may not get.** It does NOT reach $500/mo and does NOT scale with capital.
- **Effort:** needs an always-on bot quoting/managing dozens of thin markets + per-event-theme exposure caps.

**Recommendation:** treat it as a **side income stream, validated forward before any real money.** The
`kalshi_longshot_paper.py` paper-track (live on `main`, daily) is now accruing the look-ahead-free record of
realized P&L + actual fill rates. **Decision gate: after ~4–6 weeks of paper data, deploy real money (small
clips) ONLY if the forward fills + realized edge confirm the backtest.** It is additive pocket money, not the
$500/mo answer — that remains the portfolio route (`PROJECT_VERDICT.md`).
