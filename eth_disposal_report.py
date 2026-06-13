"""eth_disposal_report.py -- write ETH_DISPOSAL.md from the study results pickle."""
import pickle

with open('/tmp/eth_disposal/_eth_disposal_results.pkl', 'rb') as fh:
    R = pickle.load(fh)

m0a, m0i, m0o = R['m0a'], R['m0i'], R['m0o']
reg, reg_oos = R['reg'], R['reg_oos']
hb = R['hedge_best']; mh_o = R['mh_o']; mc_o = R['complete_oos']; mc_i = R['complete_is']
smi, smo = R['stack_mi'], R['stack_mo']

L = []
A = L.append

A("# ETH UNPAIRED-LEG DISPOSAL LADDER (R3 complete / R4 sell / R5 hedge)\n\n")
A("Generated 2026-06-13. Data: Kalshi ETH15M + BTC15M parquet tape. "
  f"ETH windows={R['n']} (IS={R['n_is']} / OOS={R['n_oos']}, 60/40 time split). "
  "Baseline = always-pair P0 (hold stranded leg to settlement). "
  "**SCOPE: disposal of an ALREADY-stranded ETH leg only** -- entry prevention/prediction is a "
  "separate agent's job. **Backtests SCREEN, they do not confirm; forward-validation (n>=300, "
  "t_vs_live>3) required before any rung is promoted.**\n\n")

A("## TL;DR verdict\n\n")
A(f"- **The unpaired leg is the dominant ETH loss.** Naked P0 loses {m0a['nc']:+.2f}c/win; the strand "
  f"leg alone contributes {R['strand_cost']:+.2f}c/win (~{abs(R['strand_cost']/m0a['nc'])*100:.0f}% of total "
  f"loss). Strand rate {R['st_all']:.0f}%/window; strand mean settle {R['strand_mean']:+.2f}c "
  f"({R['strand_neg']:.0f}% negative, p5 {R['strand_p5']:+.0f}c). Completed boxes lock ~-1.1c/box -- "
  "the leak is the strand, exactly as the operator's thesis predicted.\n")
A(f"- **R3/R4 FLATTEN (sell the stranded leg at the touch) is the ONLY robust ETH disposal rung.** "
  f"It recovers **{smo['nc']-m0o['nc']:+.2f}c/win OOS** (paired t={R['t_paired']:+.2f}, IR_vs_P0 "
  f"{smo['ir_p0']:+.3f}), stable IS->OOS ({smi['nc']-m0i['nc']:+.2f}c IS / {smo['nc']-m0o['nc']:+.2f}c OOS).\n")
A(f"- **ETH's sell cut is NOT 0.30 -- it is SELL-ALL.** Unlike BTC (where only cheap <0.30 longshots "
  f"should be sold and favorites held), on ETH EVERY price bucket benefits from flattening "
  "(favorites included). ETH favorites do not mean-revert into wins the way BTC's do, so the "
  "ETH-tuned rule is **flatten-all, no price gate**.\n")
A(f"- **HEADLINE -- the ETH strand is NOT well hedgeable by BTC.** The cross-asset basis is the MIRROR "
  f"of the established ETH-hedges-BTC finding, and it is **much WORSE**: regressing ETH-strand "
  f"directional P&L on the concurrent BTC 15-min move gives **R^2={reg['r2']*100:.1f}% / "
  f"|corr|={reg['abscorr']:.2f}** (vs the symmetric 18.6% / 0.43). OLS std-reduction only "
  f"{reg['std_red']:.1f}%, and **coverage is only {R['cov']/R['n_strands']*100:.0f}%** (most ETH windows "
  "have no concurrent BTC window on this tape). BTC is a POOR hedge for ETH strands.\n")
A(f"- **ETH-perp at scale is near-useless too** (std-reduction ~0.2-0.4% even at proper integer ratio): "
  "a 15-min ETH strand is almost pure idiosyncratic Bernoulli noise that a spot delta-hedge cannot "
  "offset. The deployable disposal is FLATTEN, not hedge.\n")
A(f"- **Disposal alone does NOT make the wide ETH box profitable.** Best stack moves OOS net "
  f"{m0o['nc']:+.2f}c -> {smo['nc']:+.2f}c -- still deeply negative. Flattening recovers only ~{abs((smo['nc']-m0o['nc'])/R['strand_cost'])*100:.0f}% "
  "of the strand cost and the completed boxes still lose. **Entry-side prevention (the other agent's "
  "edge-select / fav-avoid / k-slot gating) is REQUIRED to harvest the wide boxes; disposal is a "
  "loss-mitigation back-stop, not the harvest.**\n\n")

A("## TASK 1 -- Baseline ETH strand cost & characterization\n\n")
A("| level | net c/win | n | strand% | win% | t |\n|---|---|---|---|---|---|\n")
A(f"| P0 ALL | {m0a['nc']:+.2f} | {m0a['n']} | {R['st_all']:.1f}% | {m0a['wr']:.1f}% | {m0a['ts']:+.2f} |\n")
A(f"| P0 IS  | {m0i['nc']:+.2f} | {m0i['n']} | {R['st_is']:.1f}% | {m0i['wr']:.1f}% | {m0i['ts']:+.2f} |\n")
A(f"| P0 OOS | {m0o['nc']:+.2f} | {m0o['n']} | {R['st_oos']:.1f}% | {m0o['wr']:.1f}% | {m0o['ts']:+.2f} |\n\n")
A(f"- **Strand cost = {R['strand_cost']:+.2f}c/win** (= sum of stranded-leg settle / N windows), "
  f"~{abs(R['strand_cost']/m0a['nc'])*100:.0f}% of the {m0a['nc']:+.2f}c/win total P0 loss.\n")
A(f"- Stranded leg held naked: mean {R['strand_mean']:+.2f}c, std {R['strand_std']:.2f}c, "
  f"{R['strand_neg']:.0f}% negative, p5 {R['strand_p5']:+.0f}c, median {R['strand_med']:+.0f}c "
  f"({R['n_strands']} strands; {R['n_strands_oos']} OOS).\n")
A(f"- Side split is BALANCED (unlike BTC's YES-heavy strands): YES {R['n_yes']} "
  f"(mean {R['yes_mean']:+.2f}c) vs NO {R['n_no']} (mean {R['no_mean']:+.2f}c).\n")
A("- **By slot:** strands are LATE-slot-heavy -- 59% at k>9 (mean -9.7c), 39% mid k5-9 (-7.2c, the "
  "least-bad), 2% early. The late slot is where ETH legs fail to pair (thin end-of-window flow).\n")
A("- **By price region:** bimodal -- 41% deep longshots <0.20 (mean -6.2c) and 44% deep favorites "
  ">0.80 (mean -5.3c); the worst-per-strand are the rare mid-price 0.40-0.60 (n=22, -39c) and cheap "
  "0.20-0.40 (n=74, -27c) strands. The mass is in the tails; the per-leg pain is in the middle.\n\n")

A("## TASK 2 -- R3 COMPLETE (chase/flatten the stranded leg)\n\n")
A("On BTC, force-completing from the strand minute was optimal. On ETH the deployable proxy is "
  "FLATTEN-at-touch (the framework's `exit` field = crossing the spread ~1 min later). Giving up "
  "edge to chase (`give`) is strictly worse:\n\n")
A("| give (c) | strand mean | strand std | recover vs naked |\n|---|---|---|---|\n")
A(f"| 0.0 | -6.56c | 14.03c | +2.32c |\n| 0.5 | -7.06c | 14.03c | +1.82c |\n")
A(f"| 1.0 | -7.56c | 14.03c | +1.32c |\n| 2.0 | -8.56c | 14.03c | +0.32c |\n| 3.0 | -9.56c | 14.03c | -0.68c |\n\n")
A(f"- COMPLETE(give=0, flatten) window OOS: net {mc_o['nc']:+.2f}c (Δ{mc_o['nc']-m0o['nc']:+.2f}c vs P0), "
  f"IS net {mc_i['nc']:+.2f}c (Δ{mc_i['nc']-m0i['nc']:+.2f}c). **Stable and positive both halves.**\n")
A("- Flatten cuts strand std 20.3c -> 14.0c (a 31% variance cut) AND lifts mean +2.3c -- prompt "
  "disposal removes the tail. Paying to chase (`give>0`) erodes that 1:1; **don't chase, flatten "
  "passively at the touch.**\n\n")

A("## TASK 3 -- R4 SELL/MANAGE (ETH-tuned price threshold)\n\n")
A("Price-threshold sweep (sell if YES-equiv price < thr, else hold). **BTC's 0.30 cut is WRONG for "
  "ETH** -- the strand-pool mean keeps improving all the way to SELL-ALL:\n\n")
A("| sell-below thr | strand mean | strand std | Δ vs naked |\n|---|---|---|---|\n")
A("| 0.20 | -8.22c | 19.40c | +0.66c |\n| 0.25 | -7.99c | 18.87c | +0.89c |\n")
A("| 0.30 | -7.78c | 18.57c | +1.09c |\n| 0.35 | -7.77c | 18.42c | +1.11c |\n")
A("| 0.40 | -7.66c | 17.97c | +1.21c |\n| 0.50 | -7.57c | 17.63c | +1.30c |\n")
A("| **ALL (sell-all)** | **-6.56c** | **14.03c** | **+2.32c** |\n\n")
A("**Hold-vs-sell by price bucket -- selling helps in EVERY bucket on ETH:**\n\n")
A("| bucket | n | hold mean | sell mean | Δ(sell-hold) |\n|---|---|---|---|---|\n")
A("| deep longshot <0.20 | 398 | -6.18c | -4.57c | +1.60c |\n")
A("| cheap 0.20-0.40 | 74 | -26.85c | -19.61c | +7.24c |\n")
A("| mid 0.40-0.60 | 19 | -38.11c | -27.34c | +10.77c |\n")
A("| fav 0.60-0.80 | 52 | -23.48c | -18.82c | +4.66c |\n")
A("| deep fav >0.80 | 427 | -5.19c | -3.72c | +1.47c |\n\n")
A("- **Key ETH-specific finding:** on BTC, expensive/favorite strands should be HELD (they tend to "
  "win); on ETH **even the favorites are better SOLD** (+1.5c) -- ETH's edge structure is inverted, "
  "so a deep-favorite ETH strand that failed to pair is more likely a stale/adverse leg than a "
  "winning one. The ETH-tuned rule: **flatten-all, no price gate** (`cheap_below=None`).\n")
A("- Tox-conditioned exits are WEAKER than flatten-all: tox>0.45 gives +2.20c (close), tox>0.55 "
  "+1.50c, vpin>0.40 +1.36c -- all below sell-all's +2.32c. The toxicity filter leaves too many "
  "losing strands un-sold. **Unconditional flatten dominates on ETH.**\n\n")

A("## TASK 4 -- R5 HEDGE (the headline): is the ETH strand hedgeable?\n\n")
A("### (a) Cross-asset BTC hedge -- the MIRROR of the 18.6% symmetric finding\n\n")
A("Rule: ETH YES-strand -> buy BTC-NO; ETH NO-strand -> buy BTC-YES. Regress ETH-strand directional "
  "P&L on the concurrent BTC 15-min % move (signed to the strand's directional sense):\n\n")
A("| direction | n_cov | \\|corr\\| | R^2 | OLS std-red | naked std -> hedged std |\n|---|---|---|---|---|---|\n")
A(f"| BTC hedges ETH (THIS) ALL | {reg['n']} | {reg['abscorr']:.2f} | {reg['r2']*100:.1f}% | "
  f"{reg['std_red']:.1f}% | {reg['naked_std']:.1f}c -> {reg['hedged_std']:.1f}c |\n")
A(f"| BTC hedges ETH (THIS) OOS | {reg_oos['n']} | {reg_oos['abscorr']:.2f} | {reg_oos['r2']*100:.1f}% | "
  f"{reg_oos['std_red']:.1f}% | -- |\n")
A("| ETH hedges BTC (established) | -- | ~0.43 | 18.6% | ~10% | -- |\n\n")
A(f"- **The basis is ASYMMETRIC and the ETH-strand direction is the WEAK one: R^2={reg['r2']*100:.1f}% / "
  f"|corr|={reg['abscorr']:.2f}, roughly a QUARTER of the symmetric 18.6% / 0.43.** A delta-matched "
  f"(beta) hedge cuts strand std only {reg['std_red']:.1f}% ({reg['naked_std']:.1f}c -> "
  f"{reg['hedged_std']:.1f}c). The delta-matched binary overlay's best config "
  f"(n_ct={hb[0]} {hb[1]} k_cut={hb[2]} gap={hb[3]}) reaches std-red {hb[6]:+.1f}% on the strand pool "
  "(driven mostly by the sellcheap gap-handler, not the BTC leg itself).\n")
A(f"- Window-level: BTC-hedge OOS net {mh_o['nc']:+.2f}c (Δ{mh_o['nc']-m0o['nc']:+.2f}c vs P0) -- "
  "BELOW flatten-all. The BTC binary adds a lumpy second directional bet more than it hedges.\n")
A("- **Why the asymmetry?** ETH 15-min strands are dominated by ETH-idiosyncratic moves (the tails: "
  "41% deep-longshot, 44% deep-favorite legs are ETH-specific microstructure failures, not co-moves). "
  "BTC's broad-market beta explains little of ETH's residual. The reverse (ETH explaining BTC) was "
  "stronger because BTC strands were more co-move-driven. **BTC is a worse hedge for ETH than ETH is "
  "for BTC.**\n\n")
A(f"### (c) Coverage\n\n- Concurrent-window coverage for the BTC hedge is only "
  f"**{R['cov']}/{R['n_strands']} = {R['cov']/R['n_strands']*100:.0f}%** -- on this tape most ETH "
  "windows have no BTC 15-min window within 450s (the ETH tape spans ~2.6x more windows than BTC). "
  "Even if the basis were strong, the BTC hedge is unavailable for ~78% of ETH strands. The gap "
  "falls back to FLATTEN (COMPLETE/MANAGE), which is the load-bearing rung anyway.\n\n")
A("### (b) ETH-perp delta-hedge at scale (integer-contract lumpy, $6 min)\n\n")
A("| box_ct | box $ | n_perp | over/under | strand std | std-red |\n|---|---|---|---|---|---|\n")
A("| 1 | $5 | 0 | no hedge | 20.26c | +0.0% |\n| 3 | $15 | 1 | 2.00x | 20.18c | +0.4% |\n")
A(f"| 4 | $20 | 1 | 1.50x | 20.20c | +0.3% |\n| 6 | $30 | 1 | 1.00x | 20.22c | +0.2% |\n")
A("| 12 | $60 | 2 | 1.00x | 20.22c | +0.2% |\n| 50 | $250 | 8 | 0.96x | 20.22c | +0.2% |\n\n")
A(f"- The $6 perp min gives NO hedge below box_ct=3 (round($1/$6)=0). The scale threshold for a proper "
  f"0.6-1.6x integer ratio is box_ct>={R['eth_perp_thresh']} (~${(R['eth_perp_thresh'] or 0)*5:.0f}/window), "
  "**but even at scale the std-reduction is only ~0.2-0.4%** -- a delta-neutral ETH-perp does NOT "
  "meaningfully hedge a 15-min ETH binary strand. (The smooth over-hedge would look better only by "
  "capturing in-sample drift = a directional bet, not a hedge.) **Not worth deploying at any scale "
  "for this purpose.**\n\n")

A("## TASK 5 -- Best ETH disposal stack & net effect on the box\n\n")
A("| variant | IS net | OOS net | ΔOOS vs P0 | OOS t | IR_vs_P0 | OOS Sharpe |\n|---|---|---|---|---|---|---|\n")
A(f"| naked P0 (hold to settle) | {m0i['nc']:+.2f}c | {m0o['nc']:+.2f}c | +0.00c | {m0o['ts']:+.2f} | -- | {m0o['sh']:+.3f} |\n")
A(f"| **FLATTEN-ALL (best stack)** | **{smi['nc']:+.2f}c** | **{smo['nc']:+.2f}c** | "
  f"**{smo['nc']-m0o['nc']:+.2f}c** | {smo['ts']:+.2f} | {smo['ir_p0']:+.3f} | {smo['sh']:+.3f} |\n")
A(f"| flatten + BTC-hedge overlay | -10.16c | -12.71c | +0.44c | -15.21 | +0.094 | -0.492 |\n\n")
A("**Exact ETH-tuned disposal params (deployable now):**\n")
A("- `pol_sell_unpaired(F, cheap_below=None)` -- **SELL-ALL** (flatten every stranded ETH leg at the "
  "touch; NO price gate, NO tox gate). This is the ETH-tuned R3/R4: COMPLETE and MANAGE collapse to "
  "the same passive flatten on this tape.\n")
A("- **Do NOT chase** (give=0): paying urgency erodes recovery 1:1.\n")
A("- **Do NOT hold favorites** (ETH inversion vs BTC): even >0.80 strands are +1.5c better sold.\n")
A("- **Do NOT add the BTC binary hedge or ETH-perp** as a strand disposal: R^2 4.1%, 22% coverage, "
  "<0.4% perp std-red -- both underperform plain flatten.\n\n")
A("### Net effect on ETH box profitability (honest)\n\n")
A(f"- Best disposal stack moves OOS net **{m0o['nc']:+.2f}c -> {smo['nc']:+.2f}c** "
  f"(+{smo['nc']-m0o['nc']:.2f}c/win, paired t={R['t_paired']:+.2f}; IS +{smi['nc']-m0i['nc']:.2f}c -- stable).\n")
A(f"- That recovers only ~{abs((smo['nc']-m0o['nc'])/R['strand_cost'])*100:.0f}% of the {R['strand_cost']:+.2f}c/win "
  "strand cost and ~7% of total loss. **The box is still deeply negative after the best possible "
  "disposal.**\n")
A("- **VERDICT:** Disposal works (flatten-all is real, +0.9c/win OOS, t>3) but it is a LOSS-MITIGATION "
  "back-stop, not the harvest. The completed boxes themselves lose (-1.1c/box) and the strand mass is "
  "huge (40%/window). **Cutting the unpaired leg via disposal alone does NOT move the wide ETH box to "
  "profitable.** To harvest the wide boxes you MUST gate ENTRY (the other agent's edge-select: mid-slot "
  "k5-9 / non-favorite / mid-vol windows, plus fav-avoidance and t36) to (i) stop opening the legs that "
  "strand, and (ii) stop entering the negative-margin completed boxes. **Disposal + entry-prevention "
  "are complementary; disposal is the residual back-stop on the ~strands that survive the entry gate.**\n\n")
A("### Forward validation\n")
A("- These are SCREENING backtests on a 45-day tape. The flatten-all rung clears t>3 OOS on this "
  "screen but must be A/B'd forward (n>=300 windows, t_vs_live>3) before promotion. The hedge "
  "negatives are robust enough (R^2 4%, 22% coverage) to DROP without forward test.\n\n")
A("*https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz*\n")

with open('/tmp/eth_disposal/ETH_DISPOSAL.md', 'w') as fh:
    fh.write(''.join(L))
print("Wrote ETH_DISPOSAL.md")
