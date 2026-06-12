# Counterparty avoidance — the optimal policy (deep dive 2026-06-12, 20k fills, markout-targeted)

## The reframe that mattered
Counterparty toxicity = ADVERSE SELECTION (markout<0), NOT per-leg settle (one leg of every YES+NO
box mechanically settles to 0 -- gating on that gates the box itself). Target = markout + stranding.

## The findings
1. **The prize is modest and adverse selection is near-random.** P(markout<0)=0.50, best single-feature
   AUC only 0.546 (sig_adv, the pre-fill spot move). Realistic avoidable prize: ~+0.1-0.3c/fill of kept
   volume, NOT the ~9c oracle. We cannot dramatically improve -- per-fill toxicity is mostly noise.
2. **t31 (face-contrarian) is the OPTIMAL gate, and it's already deployed + now VALIDATED on 20k fills**
   (was the n=19 exciting lead): contrarian-side fills +0.233c/fill OOS vs the momentum side it excludes
   -0.182c = a genuine **+0.41c/fill adverse-selection spread**, the largest of any gate. Beats t29
   (+0.154), t32, t18.
3. **The take-size feature does NOT improve the fitted model** (dAUC~0.000) and is uncorrelated with VPIN
   (corr 0.008) -- but a >100-contract TAIL-TRIM is a clean monotone add-on (+0.05-0.10c/fill, keeps
   ~92% volume). Wired as t33 (trim alone) and t34 (face-contrarian + trim = the dive's best combined
   point, +0.341c/fill on 45% of volume). 
4. **The fitted combined LOGIT gate is OVERFIT** -- its +1.52c/win settle gain went NEGATIVE on the
   honest markout target (non-monotone frontier). NOT deployed (a false positive caught by targeting
   markout instead of settle).
5. **The earlier fingerprint size-toxicity (-2.2c facing 50+ takes) was SETTLE-based** = those takers
   win the DIRECTION (informed about the outcome), but they do NOT pick us off on 1-min MARKOUT (large
   takes had slightly POSITIVE markout here). So size helps the directional/settle story, not the
   markout-avoidance gate -- consistent, just different toxicity definitions.

## Deployed decision
- **t31 is the primary counterparty gate (validated). t34 (t31 + take-tail-trim) is the optimal
  combined policy -- both accumulating in the A/B vs the n>=300 bar.** No new model; the consolidated
  gate is what we already have. The honest incremental gain from the new feature is small (+0.05-0.10c)
  but clean. Do NOT deploy a fitted toxicity LOGIT on the settle metric (overfit).
- Bottom line: counterparty avoidance is a real but SMALL edge (adverse selection is ~random per fill);
  t31 captures most of it; we're already near the frontier.

## Do counterparty features predict PAIRING? (2026-06-12) — yes at the WINDOW level (have it), no per-fill
The question: can the fingerprint/counterparty signals tell us if a leg will pair? Test (57k fills,
4 assets, pairing label = opposite side fills later, IS/OOS):
- **Per-FILL: NO incremental prediction.** AUC(minute-k only)=0.8722 vs AUC(k + counterparty
  features: take-size, flow-vs-leg, spot-vs-leg)=0.8705 -- counterparty features ADD NOTHING (slightly
  hurt). MINUTE-OF-FILL stays the dominant pairing predictor (early pairs, late doesn't = t03/t29).
- **The mechanical reason (illuminating):** at front-of-queue, LARGE informed takes almost never fill
  us (large-take fills: n=1 of 57k!) -- we're filled by SMALL RETAIL. The informed flow doesn't hit
  our leg directly; it MOVES THE MARKET and strands our OPPOSITE leg. So counterparty toxicity is a
  WINDOW-level phenomenon, not a per-fill one.
- **Window-LEVEL: YES, already established + deployed.** The fingerprint Test B (2779 windows): high
  decision-time VPIN -> 9.7x more stranded legs (6.8% vs 0.7%), pair-rate OOS r=-0.346. THAT is
  "counterparty predicts pairing," and it's wired as t32 (VPIN open gate) + t06 (flow).
**Answer:** counterparty signals DO help predict stranding -- but as a WINDOW REGIME gate (toxic flow
-> avoid quoting), which we already deploy (t32). Per-LEG, minute-of-fill is the predictor (t03/t29),
and which specific taker crossed your leg is uninformative (it's retail). No new per-leg lever; the
deployed window-level VPIN/flow gates are the right tools.

## "Get informed flow to fill us profitably?" (2026-06-12) — the adverse-selection theorem holds
Q: large informed takes don't fill us at front-of-queue; can we get them to fill us more, profitably?
The mechanic: we post BUY-bids (YES+NO); we're filled when someone SELLS to us. An informed seller
dumps the losing side -> we bought the loser. There is NO resting price filled FAVORABLY by informed
flow (it moves AWAY from where it pays the counterparty). What actually happens: the informed MOVE
fills our now-stale OPPOSITE-side bid at a bad price = the stranding.
- **Tested the profitable reframe ("informed-lean": refuse to open a leg strong cumulative flow is
  against, so the move can't strand it): LOSES at every threshold.** IS diff -0.6 to -1.0c, OOS -1.9
  to -2.1c (t up to -1.8). Refusing legs kills PAIRING more than it saves strands -- the "lagging"
  side is also sometimes the completing side. Same lesson as the avoidance frontier.
- **The theorem (Glosten-Milgrom):** a passive maker CANNOT profit from informed fills without
  compensation -- either a REBATE (Kalshi maker fee=$0, none; Polymarket HAS one -> relevant there)
  or a WIDER SPREAD (1c tick caps this). Our compensation IS the box spread captured from UNINFORMED
  retail flow. We don't want more informed fills; we want fewer adverse stale-fills.
**Deployed answer:** the levers are EXECUTION, not getting-filled-by-informed: (1) reprice fast so the
informed move does NOT fill our stale wrong-side bid (qtime experiment + stale-refresh, live), (2)
complete the box fast (chase, live), (3) the mild validated flow-tilt t31 (open WITH flow, +0.41c/fill
-- the deployable version of "lean with informed direction", but a tilt not a hard refusal). You can't
be paid to be informed flow's counterparty on a $0-fee 1c-tick book; you minimize being its stale victim.
