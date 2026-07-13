#!/usr/bin/env python3
"""box_shadow.py -- forward-validation harness for the Kalshi 15m box strategy's DECISION-LAYER
policies (disposal timing + entry/veto gates). READ-ONLY replay over already-collected tick tapes;
no orders, no keys. stdlib + numpy ONLY (the collector env installs numpy/scipy/requests/websockets,
no pandas/sklearn -- this file must run there unmodified).

Ports the live-policy replay (window scan, two-sided quoting, first-fill cross-rule detection,
live disposal-policy constants) EXACTLY from completion/pairprob/build.py, and the hazard-model
feature construction (h{s}_ per-5s panel features) EXACTLY from pairalarm/build_alarm.py. The
logistic hazard + linear dca-regressor coefficients are the FROZEN, pre-registered artifact from
minhaz/run_minhaz.py's "LOGIT-all" model (embedded below as a JSON literal -- no runtime file dep).

Six PRE-REGISTERED arms, one output row per (asset, ws, arm):
  1. live            -- exact build.py live policy (chase/close-flatten/force, DISPOSE_MAX_GIVE=0.25).
  2. hazard_stop      -- live policy for the pairing/maker leg, but the DISPOSAL decision is replaced
                         every 5s by the state-dependent stopping rule from minhaz/run_minhaz.py:
                         wait_edge = hz*(dist+fee) - (1-hz)*edca; dispose (cross the then-current ask
                         + fee) iff wait_edge < kappa. Ported verbatim from minhaz/core.py's
                         replay_state_rule (SMAX=300s cap, unconditional force-cross fallback at the
                         last observed ask if neither pairing nor a hazard-trigger occurs by then --
                         this is a property of the REFERENCE implementation, not an omission here).
  3. thickbook_veto   -- live policy, but skip (0 P&L, no participation) windows whose completing-side
                         queue depth AT FILL (qdepth_c) exceeds a rolling 80th-percentile threshold.
  4. cell_veto        -- live policy, but skip windows whose OPEN state falls in pairprob/analyze.py's
                         "worst train cell": vol60_0 tercile in {0,1,2} (ALL 3 tercile bins -- i.e. the
                         vol term is VACUOUS by construction, see CELL_VETO_SPREAD0 comment below) x
                         spread0 bucket 2 (sprb cut edges [0,.011,.021,1] -> spread0 > 2.1c).
  5. givecap15        -- live policy with DISPOSE_MAX_GIVE=0.15 instead of 0.25 (the force-cross give
                         cap used only in the near-close/force branch of policy_live).
  6. combined         -- (3) AND (4) entry vetoes, THEN (2)'s hazard_stop disposal mechanic. Note:
                         (5)'s DISPOSE_MAX_GIVE has NO effect inside hazard_stop's own fallback (the
                         reference replay_state_rule has no give-cap-gated branch at all -- its
                         fallback force-crosses unconditionally), so combined does not additionally
                         thread givecap15's parameter through hazard_stop; documented, not a bug.
  7. stack_full        -- STRAND_DEFENSE STACK-FULL forward arm (primary). L0 entry veto (skip window
                         iff qdepth_c > L0_QDEPTH_C_MAX OR minute1-at-fill > L0_MINUTE1_MAX) THEN
                         stack_stop_policy with the L1 UNCERTAINTY-LCB 7-model bootstrap-logistic
                         ensemble hazard sensor, the L2 HONEST 2-step lookahead stopping rule
                         (kappa2=L2_KAPPA2=-0.50c), and an L3 give-cap of 0.15 gating the dispose
                         trigger (see "STACK ARMS" section below for the full mechanics + the C7
                         lookahead LEAKAGE finding).
  8. stack_lean        -- STRAND_DEFENSE STACK-LEAN forward challenger. Same L0 veto as (7), same L2
                         honest 2-step stopping rule, but the L1 sensor is the BASE single
                         logistic-33 hazard (hazard_predict -- reused verbatim from arm (2)/(6), no
                         ensemble) and the L3 give-cap is 0.25 instead of 0.15.
  9. c3_share         -- live policy, but skip (0 P&L, no participation, same semantics as (3)) windows
                         whose completing-side depth SHARE at fill, qdepth_c/(qdepth_c+qdepth_f),
                         exceeds 0.90 (C3 completing-side depth-share veto, MILD variant -- the book
                         is leaning overwhelmingly against completion). Division-by-zero guarded: if
                         qdepth_c+qdepth_f <= 0, do NOT veto. Replay prior: +1.42c/window t=5.15
                         marginal beyond thickbook_veto (in-sample; known large-skip accounting
                         artifact -> forward arm is the only valid sizing (DECISION_MAP K artifact) --
                         which is exactly why this ships only as a forward arm here, not a standalone
                         live change).

Output: gha_data/<day>/box_shadow_<asset>15m.jsonl (append, idempotent per (ws,asset,arm)).
Rows: {"ws":.., "asset":.., "arm":.., "locked":.., "filled":.., "stranded":.., "disposed_at_s":..,
       "qdepth_c":.., "dispose_give":..}  (qdepth_c and dispose_give are ADDITIVE extra fields --
       qdepth_c kept so a later day's thickbook_veto run can compute a genuine rolling percentile
       from this file's own prior output; dispose_give = max(0, -locked) when the window completed
       [None when stranded], i.e. the cents actually given away below flat, needed for the risk
       benchmarks in box_shadow_report.py. Both fields are purely additive -- rows written by older
       versions of this script that lack them remain valid JSON and parse fine with dict.get().)

================================================================================================
STACK ARMS (7)/(8): L0/L1/L2/L3 forward-validation mechanics, provenance, and the C7 LEAKAGE finding
================================================================================================
L0 ENTRY VETO (both stack arms): STRAND_DEFENSE Layer 0 champion, "joint_sweep@95%" rule from
  layer0/layer0_study.py (results_layer0.txt): keep entry iff (qdepth_c <= 6,717 [TRAIN q95 of BTC
  completing-side depth-at-fill, day<=2026-06-29]) AND (minute1-at-fill <= 7). TEST (BTC,
  day-clustered, out-of-sample): volume retained 90.5%, strand 6.77%->6.45% (t=-1.12), EV
  -4.356c->-4.181c (t=+1.17) -- directionally right but below the standalone t=2 promotion bar,
  which is exactly why this ships only as a forward-arm component, not a standalone live change.
  L0_QDEPTH_C_MAX/L0_MINUTE1_MAX below are those two TRAIN-fixed constants, embedded verbatim.

L1 SENSOR: stack_lean reuses the BASE single logistic-33 hazard already embedded above
  (HAZARD_MODEL / hazard_predict -- the minhaz "LOGIT-all" deployable form). stack_full uses the
  STRAND_DEFENSE Layer 1 CHAMPION instead: UNCERTAINTY-LCB, a 7-model 80%-bootstrap logistic-33
  ensemble, hz_lcb = clip(mean(sigmoid) - 1.0*std(sigmoid), 0, 1) -- "conservative when unsure".
  Refit here (not copied from the study) on the same train panel (events_alarm.csv, day<=2026-06-29)
  via layer1/layer1_sensor.py's exact deployable-form method (7x 80% bootstrap without replacement,
  SEED=7, each LogisticRegression(C=1.0, max_iter=1000) standardized on its OWN bootstrap sample's
  mu/sd) -- see L1_ENSEMBLE below for the 7 embedded coefficient sets. Sanity check against the
  study's own reported deployable number (STRAND_DEFENSE: "deployable numpy form verified:
  logit-LCB gate +1.081c t=2.56"): this refit's one-step-lookahead sanity replay reproduces
  gate-passed delta=+1.083c t=2.57 -- matches to within refit noise. edca (expected cost of
  waiting) is held FIXED at the existing embedded linear dca model (HAZ_DCA) for BOTH stack arms,
  matching the layer1/layer2 studies' own convention of only swapping the hazard side.

L2 STOPPING RULE + CRITICAL LEAKAGE CHECK (both stack arms): STRAND_DEFENSE's Layer 2 champion is
  "2-step lookahead", layer2.py's rule_lookahead2: w2 = hz*(dist+fee) - (1-hz)*edca +
  (1-hz)*wait_edge(s+5), dispose iff w2 < kappa2 (reported: kappa2=-0.005 i.e. -0.50c, gate-passed
  TEST delta=+1.176c t=2.82, beating the one-step incumbent's +1.110c t=2.64).
  ** LEAKAGE FINDING **: inspecting layer2.py's replay engine, wait_edge(s+5) there (`A.wnext`) is
  built from `A.we[:, 1:]` -- i.e. it is the REALIZED wait_edge computed from the ACTUAL panel row
  at s+5 (the true future book state), not a state(s)-conditioned expectation. A live policy
  deciding at time s cannot see the s+5 book; that is lookahead leakage and cannot ship as-is.
  Honest fix implemented here: E[wait_edge(s+5) | features(s)] is a plain LINEAR regression
  (33 standardized HAZ_FEATS inputs, i.e. features available AT s only -- s+5's realized wait_edge
  is used ONLY as a train label, never as a runtime input) fit on TRAIN (day<=2026-06-29) via
  /tmp/.../scratchpad/stacktest/fit_stack_arms.py, which reruns layer2.py's own replay engine
  verbatim to keep the comparison apples-to-apples (reproduced the leaky C7 exactly: gate-passed
  +1.176c t=2.82, bit-for-bit match to results_layer2.txt). RESULT, rerunning the SAME harness with
  the honest w_next substituted for the leaky one (TEST, gate-passed, day-clustered):
      LEAKY  (layer2.py as published): +1.176c t=2.82
      HONEST (this linear delooked form): +1.128c t=3.04
      GAP (leaky-honest) = +0.048c -- SMALL. The honest version's point estimate is very slightly
      lower but its t-stat is actually HIGHER (tighter day-to-day SE) -- the champion's edge is
      NOT mostly a lookahead artifact; it survives delooking on this test slice. Recorded per the
      charter regardless of outcome: the arms still ship on this evidence (forward data decides),
      but the expectation is that STACK-FULL/LEAN's L2 component should perform close to, not
      dramatically below, the originally-reported +1.176c/t=2.82 headline.
  L2_KAPPA2 / L2_HONEST below are the honest linear model's threshold and embedded coefficients.

L3 GIVE-CAP (differs between the two arms: stack_full=0.15, stack_lean=0.25): gates the L2 dispose
  TRIGGER itself (not the terminal SMAX fallback, which -- like hazard_stop_policy's own fallback --
  force-crosses unconditionally; documented precedent, not an omission): when w2 < kappa2 fires,
  the cross is only EXECUTED if its give (max(0, p1+ask+fee-1)) is <= give_cap; otherwise the
  position HOLDS and the loop continues to the next 5s step. This is a documented design choice
  (the studies do not specify how a give-cap should interact with 2-step lookahead stopping) chosen
  to match the mechanism STRAND_DEFENSE's own stack-test LOO ablation describes: "cap15 converts
  ~17/983 borderline crosses into forced holds = near-total losers" -- i.e. a tight cap can make
  the stack WORSE by deferring cheap early exits into expensive late ones. That negative marginal
  finding is exactly why stack_full (cap15, matching the tested STACK-FULL configuration) and
  stack_lean (cap25, the challenger) are shipped side-by-side as competing forward arms rather than
  one being promoted outright -- forward data adjudicates.

DAY PARTITIONING (matches the two real layouts this repo uses):
  --day given      -> reads AND writes <data-dir>/<day>/... (the historical, gha-data-branch
                      day-partitioned archive layout used by pairprob/build.py & friends).
  --day omitted    -> reads AND writes <data-dir>/... FLAT, matching kalshi_collect.py /
                      box_policy_ab.py's convention for the live collector's per-run gha_data/
                      (which is wiped clean each cycle and is NOT day-partitioned until the
                      workflow's separate commit step copies it onto the gha-data branch under
                      gha_data/$day/ -- writing a nested day dir ourselves during that step would
                      double-nest under that copy).

    python box_shadow.py --asset btc [--data-dir gha_data] [--day 2026-07-05 2026-06-25]
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
import statistics
import time
from datetime import datetime

import numpy as np

ASSETS = ["btc", "eth", "sol", "xrp"]
ASSET_C = {"btc": 0.0, "eth": 1.0, "sol": 2.0, "xrp": 3.0}
WINDOW_S = 900.0
OPEN_T = 120.0

# ---- live policy params: EXACT copy of pairprob/build.py / pairalarm/build_alarm.py ----
MIN_LOCK = 0.0
CLOSE_FLATTEN_TAU = 120.0
CLOSE_MAX_GIVE = 0.04
CHASE_UNPAIRED_S = 15.0
CHASE_MAX_GIVE = 0.02
DISPOSE_CROSS_S = 15.0
CLOSE_FORCE_S = 45.0
DISPOSE_MAX_GIVE = 0.25          # arm "givecap15" overrides this to 0.15

# ---- cell_veto: pairprob/analyze.py "worst train cells" gate ----
# analyze.py: qs = train vol60_0 quantiles at [.2,.4,.6,.8] (5 vol quintile bins, volb 0..4);
#             sprb = pd.cut(spread0, [0, .011, .021, 1], labels=False)  (3 bins, sprb 0..2)
#             worst 3 train cells (n>=100) were (volb,sprb) = (2,2),(0,2),(1,2) -- i.e. EVERY volb
#             value that appeared was paired with sprb=2. Per the task spec ("vol60_0 tercile 0-2"),
#             using a plain TERCILE split there are only 3 bins (0,1,2) total, so "tercile 0-2" spans
#             the FULL range -- the vol condition is vacuous and the cell collapses to sprb==2 alone,
#             i.e. spread0 in the pd.cut bucket (.021, 1] (right-closed). We embed that exact edge:
CELL_VETO_SPREAD0 = 0.021        # veto iff spread0 > 0.021 (2.1c), matching sprb==2's left edge

# ---- thickbook_veto bootstrap (documented per the task spec) ----
THICKBOOK_BOOTSTRAP = 2000.0     # used until >=THICKBOOK_MIN_N qdepth_c samples exist in the rolling
THICKBOOK_MIN_N = 50             # 5-prior-day window of this script's own "live"-arm output
THICKBOOK_PCTL = 80.0
THICKBOOK_LOOKBACK_DAYS = 5

# ---- L0 champion entry veto (STRAND_DEFENSE Layer 0 champion; stack_full/stack_lean only) ----
# layer0/layer0_study.py "joint_sweep@95%" champion, TRAIN-fixed thresholds (BTC, train<=2026-06-29
# per results_layer0.txt): "keep entry iff (qdepth_c <= 6,717 [TRAIN q95 of completing-side depth])
# AND (minute1 <= 7)". See the module docstring's "STACK ARMS" section for the full writeup.
L0_QDEPTH_C_MAX = 6717.0
L0_MINUTE1_MAX = 7.0

ARMS = ["live", "hazard_stop", "thickbook_veto", "cell_veto", "givecap15", "combined",
        "stack_full", "stack_lean", "c3_share"]
STACK_ARMS = ("stack_full", "stack_lean")

# ---- c3_share: C3 completing-side depth-share veto, MILD variant (forward arm only) ----
# Replay prior +1.42c/window t=5.15 marginal beyond thickbook_veto (in-sample; known large-skip
# accounting artifact -> forward arm is the only valid sizing (DECISION_MAP K artifact)).
C3_SHARE_MAX = 0.9

# ============================================================================================
# Hazard model: frozen "LOGIT-all" artifact from minhaz/run_minhaz.py, embedded verbatim as a
# JSON literal (json.loads at import time -- no runtime file dependency). kappa=-0.005 is the
# pre-registered stopping threshold from the study.
# ============================================================================================
_HAZARD_JSON = r"""
{"label": "LOGIT-all", "feats": ["asset_c", "side_c", "t1", "minute1", "tau1", "p1", "pc0", "spread1", "mid1", "vol30_1", "drift_need10", "drift_need30", "imb1", "micdev_need", "qdepth_c", "qdepth_f", "tickrate30_1", "dist", "dist_chg", "mindist", "cspread", "cspread_chg", "dmid_need", "dtheo_need", "dspot_need", "theo_dist", "vol", "opp_depth", "opp_depth_chg", "own_depth", "nticks", "stale", "s"], "auc": 0.9025914997710459, "kappa": -0.005, "delta": 0.2593611916613362, "t": 1.11726744240081, "cap": 11.493427196322124, "gate_delta": 0.83748528389838, "gate_t": 1.8766720045330882, "logit": {"coef": {"asset_c": -0.20104, "side_c": 0.00871, "t1": -0.265067, "minute1": 0.437528, "tau1": 0.265067, "p1": 0.008235, "pc0": -0.00663, "spread1": -0.018953, "mid1": -0.030742, "vol30_1": 0.104708, "drift_need10": 0.005858, "drift_need30": -0.002667, "imb1": 0.02302, "micdev_need": -0.007257, "qdepth_c": -0.054071, "qdepth_f": 0.007678, "tickrate30_1": -0.026873, "dist": -2.331114, "dist_chg": -0.171917, "mindist": 0.122541, "cspread": 0.010049, "cspread_chg": 0.043993, "dmid_need": 0.173958, "dtheo_need": 0.007367, "dspot_need": 0.037026, "theo_dist": -2.387965, "vol": 0.508776, "opp_depth": 0.084113, "opp_depth_chg": 0.007774, "own_depth": -0.190997, "nticks": -0.074834, "stale": -0.090321, "s": -0.14822}, "intercept": -7.140693067677155, "mu": {"asset_c": 1.6757887062566277, "side_c": 0.5059981442205727, "t1": 139.0316648992577, "minute1": 2.1484822375397665, "tau1": 760.9683351007424, "p1": 0.4731681004772004, "pc0": 0.5075205593849416, "spread1": 0.019311340137857902, "mid1": 0.500082592126193, "vol30_1": 0.022543138189289505, "drift_need10": -0.002470569326617179, "drift_need30": -0.002174261002120891, "imb1": 0.48675854520148465, "micdev_need": -0.0020404675901378577, "qdepth_c": 817.0780620360551, "qdepth_f": 334.36034663308584, "tickrate30_1": 0.7418091595970308, "dist": 0.15874270943796395, "dist_chg": 0.10236806071049842, "mindist": 0.04089315349946978, "cspread": 0.02054783934252386, "cspread_chg": 0.00020913308589607635, "dmid_need": -0.10226349416755039, "dtheo_need": -0.10099880302226935, "dspot_need": -7.794491344114529, "theo_dist": 0.1483739680540827, "vol": 0.04339370539501591, "opp_depth": 513.6895870890775, "opp_depth_chg": 121.02042285259809, "own_depth": 535.9710630965005, "nticks": 82.83018955461294, "stale": 1.5868624072110287, "s": 113.79513520678685}, "sd": {"asset_c": 1.1069791537979756, "side_c": 0.49996567780634127, "t1": 51.18671097219308, "minute1": 0.790046009762543, "tau1": 51.18671097219308, "p1": 0.17519617717917782, "pc0": 0.17528694849954904, "spread1": 0.014804618525230007, "mid1": 0.17592564115537407, "vol30_1": 0.01712828487740692, "drift_need10": 0.04339607419551815, "drift_need30": 0.07306563521819695, "imb1": 0.3816885648885711, "micdev_need": 0.007972191217922055, "qdepth_c": 1922.1819505780124, "qdepth_f": 677.8760788776925, "tickrate30_1": 0.16936332439472754, "dist": 0.1155124890277722, "dist_chg": 0.11226253683357855, "mindist": 0.03128207209941468, "cspread": 0.016351345214919176, "cspread_chg": 0.016428378754088282, "dmid_need": 0.11302284642300592, "dtheo_need": 0.11339000626273653, "dspot_need": 10.073668339233954, "theo_dist": 0.11572895589410914, "vol": 0.03286588067210598, "opp_depth": 1221.6959380648996, "opp_depth_chg": 1207.8085213247193, "own_depth": 1211.4459995950535, "nticks": 65.52313373861664, "stale": 7.181884649157462, "s": 87.6851115819205}}, "dca": {"asset_c": 0.000166, "side_c": -4.5e-05, "t1": 3.3e-05, "minute1": 0.000118, "tau1": -3.3e-05, "p1": 0.00017, "pc0": -0.000204, "spread1": 0.000394, "mid1": -2.8e-05, "vol30_1": 1.2e-05, "drift_need10": -0.000186, "drift_need30": 0.000173, "imb1": -6.8e-05, "micdev_need": 0.000239, "qdepth_c": -0.000185, "qdepth_f": -0.000248, "tickrate30_1": 8e-05, "dist": -0.016275, "dist_chg": -6.7e-05, "mindist": 0.000346, "cspread": -0.000308, "cspread_chg": -0.000395, "dmid_need": 3.8e-05, "dtheo_need": -0.000369, "dspot_need": 0.000422, "theo_dist": 0.013711, "vol": 0.000805, "opp_depth": -0.000724, "opp_depth_chg": 9.6e-05, "own_depth": 0.000972, "nticks": -0.00059, "stale": -0.00038, "s": 0.00059, "_intercept": 0.0014432204642386333}}
"""
HAZARD_MODEL = json.loads(_HAZARD_JSON)
HAZ_KAPPA = HAZARD_MODEL["kappa"]          # -0.005
HAZ_FEATS = HAZARD_MODEL["feats"]
HAZ_COEF = HAZARD_MODEL["logit"]["coef"]
HAZ_MU = HAZARD_MODEL["logit"]["mu"]
HAZ_SD = HAZARD_MODEL["logit"]["sd"]
HAZ_INTERCEPT = HAZARD_MODEL["logit"]["intercept"]
HAZ_DCA = HAZARD_MODEL["dca"]

HORIZON_STEP = 5
HORIZON_MAX = 300     # SMAX from minhaz/run_minhaz.py -- range(0, SMAX, STEP) = s in 0,5,...,295


# ================================================================================================
# Ported verbatim from pairprob/build.py / pairalarm/build_alarm.py
# ================================================================================================
def taker_fee(p):
    p = min(max(p, 0.0), 1.0)
    return math.ceil(7.0 * p * (1.0 - p) - 1e-9) / 100.0


def micro(bb, bsz, ba, asz):
    tot = (bsz or 0) + (asz or 0)
    if bb is None or ba is None:
        return None
    return (bb + ba) / 2 if tot <= 0 else bb + (ba - bb) * (bsz or 0) / tot


def trailing_vol(rows, idx, sec):
    t1 = rows[idx][0]
    mids = []
    for r in reversed(rows[:idx + 1]):
        if t1 - r[0] > sec:
            break
        if r[1] is not None:
            mids.append(r[1])
    if len(mids) < 3:
        return 0.0
    try:
        return statistics.pstdev(mids)
    except Exception:
        return 0.0


def momentum(rows, idx, sec):
    t1 = rows[idx][0]
    mid1 = rows[idx][1]
    prior = None
    for r in reversed(rows[:idx + 1]):
        if t1 - r[0] >= sec:
            prior = r[1]
            break
    if prior is None or mid1 is None:
        return 0.0
    return mid1 - prior


def tickrate(rows, idx, sec):
    t1 = rows[idx][0]
    n = 0
    for r in reversed(rows[:idx + 1]):
        if t1 - r[0] > sec:
            break
        n += 1
    return n / sec


def find_first_fill(rows):
    """Cross rule (conservative), identical to pairprob/build.py."""
    idx0 = None
    for i, r in enumerate(rows):
        if r[0] >= OPEN_T:
            idx0 = i
            break
    if idx0 is None or idx0 >= len(rows) - 1:
        return None
    for j in range(idx0, len(rows) - 1):
        row_i, row_n = rows[j], rows[j + 1]
        yb_i, ya_i = row_i[4], row_i[6]
        yb_n, ya_n = row_n[4], row_n[6]
        if None in (yb_i, ya_i, yb_n, ya_n):
            continue
        yes_fill = ya_n <= yb_i + 1e-9
        no_fill = yb_n >= ya_i - 1e-9
        if yes_fill and no_fill:
            return {"both": True, "row_i": row_i, "idx_fill": j + 1, "spread1": round(ya_i - yb_i, 4)}
        if yes_fill:
            return {"side": "yes", "p1": yb_i, "pc0": round(1 - ya_i, 4),
                    "row_i": row_i, "idx_i": j, "idx_fill": j + 1, "spread1": round(ya_i - yb_i, 4)}
        if no_fill:
            return {"side": "no", "p1": round(1 - ya_i, 4), "pc0": yb_i,
                    "row_i": row_i, "idx_i": j, "idx_fill": j + 1, "spread1": round(ya_i - yb_i, 4)}
    return None


def c_quotes(r, side):
    """completing-contract (cb, ca) from a raw tick row; None if book missing."""
    yb, ya = r[4], r[6]
    if yb is None or ya is None:
        return None
    if side == "yes":
        return (round(1 - ya, 4), round(1 - yb, 4))
    return (yb, ya)


def build_c_series_cwin(rows, idx_fill, side):
    """c_series: list of (t,cb,ca) with valid book, from idx_fill on (identical semantics to
    build.py's c_series_from). cwin: the parallel raw tick rows (build_alarm.py's cwin) -- needed
    for the h{s}_ hazard features (mid/spot/theo/depth), which c_series alone doesn't carry."""
    c_series, cwin = [], []
    for r in rows[idx_fill:]:
        cq = c_quotes(r, side)
        if cq is None:
            continue
        c_series.append((r[0], cq[0], cq[1]))
        cwin.append(r)
    return c_series, cwin


def window_open_state(rows):
    idx0 = None
    for i, r in enumerate(rows):
        if r[0] >= OPEN_T:
            idx0 = i
            break
    if idx0 is None or idx0 >= len(rows) - 1:
        return None
    r0 = rows[idx0]
    t0, mid0, yb0, ya0 = r0[0], r0[1], r0[4], r0[6]
    if yb0 is None or ya0 is None:
        return None
    return dict(idx0=idx0, t0=t0, spread0=round(ya0 - yb0, 4),
                vol60_0=trailing_vol(rows, idx0, 60), mid0=mid0)


def policy_live(p1, c_series, side, resolved_up, dispose_max_give=DISPOSE_MAX_GIVE):
    """EXACT port of pairprob/build.py's policy_current (live disposal policy)."""
    t1 = c_series[0][0]
    for (t, cb, ca) in c_series:
        age = t - t1
        tau_left = max(WINDOW_S - t, 0.0)
        near_close = tau_left < CLOSE_FLATTEN_TAU
        force = tau_left < CLOSE_FORCE_S
        aged = age >= DISPOSE_CROSS_S
        eff_close = MIN_LOCK
        if near_close:
            frac = 1.0 - max(tau_left, 0.0) / CLOSE_FLATTEN_TAU
            eff_close = MIN_LOCK - (MIN_LOCK + CLOSE_MAX_GIVE) * frac
        eff_chase = MIN_LOCK
        if age >= CHASE_UNPAIRED_S:
            u = min(1.0, age / CHASE_UNPAIRED_S - 1.0)
            eff_chase = MIN_LOCK - (MIN_LOCK + CHASE_MAX_GIVE) * u
        eff_lock = min(eff_close, eff_chase)
        cap = 1.0 - p1 - eff_lock
        p_maker = min(cb, cap)
        if p_maker > 0 and ca <= p_maker + 1e-9:
            return dict(completed=1, locked=1.0 - p1 - p_maker, mode="maker", wait_s=age)
        if aged or near_close or force:
            give = CLOSE_MAX_GIVE if near_close else CHASE_MAX_GIVE
            cross_lock = 1.0 - p1 - ca
            cross_ok = (cross_lock >= -give - 1e-9) or (force and cross_lock >= -dispose_max_give - 1e-9)
            if cross_ok:
                fee = taker_fee(ca)
                return dict(completed=1, locked=1.0 - p1 - ca - fee, mode="taker", wait_s=age)
    payout = 1.0 if (side == "yes" and resolved_up == 1) or (side == "no" and resolved_up == 0) else 0.0
    return dict(completed=0, locked=payout - p1, mode="strand", wait_s=WINDOW_S - t1)


# ================================================================================================
# Hazard model inference (numpy-only logistic + linear regression, standardized features)
# ================================================================================================
def _sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def hazard_predict(raw_feats):
    """hz (pairing-in-next-5s probability) + edca (predicted change in the completing ask over the
    next 5s), computed on the SAME standardized features z=(x-mu)/sd for both models (matches
    run_minhaz.py's fit_variant: both `m` (LogisticRegression) and `r` (LinearRegression) are fit
    on Xz). Missing raw features are filled with 0.0 BEFORE standardizing (X.fillna(0.0) in the
    reference, i.e. before the (X-mu)/sd step -- replicated exactly, not "neutral" post-standardization)."""
    lin = HAZ_INTERCEPT
    edca = HAZ_DCA.get("_intercept", 0.0)
    for f in HAZ_FEATS:
        x = raw_feats.get(f)
        if x is None:
            x = 0.0
        sd = HAZ_SD[f] if HAZ_SD[f] else 1.0
        z = (x - HAZ_MU[f]) / sd
        lin += HAZ_COEF[f] * z
        edca += HAZ_DCA.get(f, 0.0) * z
    return _sigmoid(lin), edca


# ================================================================================================
# STACK-FULL / STACK-LEAN forward arms: L1 UNCERTAINTY-LCB ensemble sensor + L2 HONEST 2-step
# lookahead stopping. Both embedded as frozen JSON literals (json.loads at import time -- no
# runtime file dependency), refit from /tmp/.../scratchpad/stacktest/fit_stack_arms.py. See the
# module docstring's "STACK ARMS" section for full provenance, the LEAKAGE finding, and the
# give-cap mechanics.
# ================================================================================================
_L1_ENSEMBLE_JSON = r"""
{"label":"DEPLOY-LOGIT-LCB","feats":["asset_c","side_c","t1","minute1","tau1","p1","pc0","spread1","mid1","vol30_1","drift_need10","drift_need30","imb1","micdev_need","qdepth_c","qdepth_f","tickrate30_1","dist","dist_chg","mindist","cspread","cspread_chg","dmid_need","dtheo_need","dspot_need","theo_dist","vol","opp_depth","opp_depth_chg","own_depth","nticks","stale","s"],"n_ens":7,"shrink":1.0,"models":[{"coef":[-0.2170870297520488,0.008240904241591348,-0.25112543878820837,0.41639204205825847,0.2511254387882172,0.007057136492411716,-0.006360407933245474,-0.008257708981014734,-0.035323438762066464,0.10583843678617932,-0.00324317140082858,-0.006293758045619402,0.018966109584094625,-0.013868763411544322,-0.05424912486330108,0.007760879979420635,-0.02646395177366646,-2.3001906223075714,-0.17767260240918956,0.15477169298485205,0.004021626726269023,0.036878750083830965,0.1791604344034,0.05538474491313635,0.038072204557447996,-2.3650091235742114,0.5090925613588874,0.07586101489828677,0.013601688028109973,-0.20144066882603323,-0.07592401583185113,-0.08400754071644724,-0.1528857328596155],"intercept":-7.136466350374253,"mu":{"asset_c":1.6746586691410392,"side_c":0.5058158801696713,"t1":139.13457383351007,"minute1":2.1502932794273595,"tau1":760.86542616649,"p1":0.47293843617444326,"pc0":0.5077722527836691,"spread1":0.019289311041887598,"mid1":0.5002259949960234,"vol30_1":0.022505646126060444,"drift_need10":-0.002483148860021209,"drift_need30":-0.0021976239395546126,"imb1":0.48716278996553547,"micdev_need":-0.002041981707317073,"qdepth_c":818.2964814753446,"qdepth_f":333.8514846235419,"tickrate30_1":0.7415953158138919,"dist":0.15858827379374338,"dist_chg":0.10222344744167551,"mindist":0.040866259610286323,"cspread":0.02051340469247084,"cspread_chg":0.00019800503711558856,"dmid_need":-0.10212444492311772,"dtheo_need":-0.10089846069724284,"dspot_need":-7.7941286949893955,"theo_dist":0.14825485650848355,"vol":0.043378789683854724,"opp_depth":512.5384693133616,"opp_depth_chg":119.55629887990456,"own_depth":537.6288590270414,"nticks":82.80504374337221,"stale":1.5830511002120888,"s":113.72183191940616},"sd":{"asset_c":1.1073310254512125,"side_c":0.49996824544882756,"t1":51.53080351817768,"minute1":0.7961518261483479,"tau1":51.53080351817768,"p1":0.17531161332035847,"pc0":0.1754099054328999,"spread1":0.014715877018969098,"mid1":0.17606975668548586,"vol30_1":0.017144566524269225,"drift_need10":0.04329791215705228,"drift_need30":0.07312124821539677,"imb1":0.3816473684823964,"micdev_need":0.007933053825423865,"qdepth_c":1928.1193267219967,"qdepth_f":676.0598363887759,"tickrate30_1":0.16965732533891734,"dist":0.11545213607266497,"dist_chg":0.11215570826839832,"mindist":0.03117336837020252,"cspread":0.01635078554055557,"cspread_chg":0.016386844829298516,"dmid_need":0.11291086566081908,"dtheo_need":0.1132645419947362,"dspot_need":10.058629936486886,"theo_dist":0.11565004414674114,"vol":0.0328439131061492,"opp_depth":1232.0209856810918,"opp_depth_chg":1220.807136450213,"own_depth":1212.057480021795,"nticks":65.52647277307157,"stale":7.157450876821633,"s":87.66328590533375}},{"coef":[-0.20948577970698828,-0.002970501115943665,-0.2506404123723872,0.4045696490613879,0.2506404123723874,0.006462009366807397,-0.004980356635606932,-0.01746997720806292,-0.04564007596235139,0.10532099581135383,0.010873569188719066,0.009114538060763282,0.02072367178540312,-0.0070973563891811794,-0.06594013672859755,0.0017246158638291678,-0.02257562095399707,-2.32457409507228,-0.10986252423233031,0.12435412895905816,0.013966806213507158,0.04781709049525817,0.11261392215937574,0.04190571049689691,0.05138446030105919,-2.397419541441616,0.5215147409511411,0.07958012076384802,0.004565016728098483,-0.18608131927805321,-0.12171801047672921,-0.10199161980666985,-0.103462693265053],"intercept":-7.0532249583998485,"mu":{"asset_c":1.675197176564157,"side_c":0.5059070121951219,"t1":138.99484275583245,"minute1":2.1480066940615057,"tau1":761.0051572441675,"p1":0.4732830229321315,"pc0":0.5074088099814421,"spread1":0.0193081670864263,"mid1":0.500009854685843,"vol30_1":0.022528929364395545,"drift_need10":-0.0024620186572110285,"drift_need30":-0.00209537380699894,"imb1":0.48679818564422056,"micdev_need":-0.0020202401743107104,"qdepth_c":815.3193249602333,"qdepth_f":336.4454011466066,"tickrate30_1":0.7416484706389184,"dist":0.15856550735683989,"dist_chg":0.1021291589342524,"mindist":0.04094504738865324,"cspread":0.020549294141039242,"cspread_chg":0.00016880965005302225,"dmid_need":-0.10204475410922587,"dtheo_need":-0.10078657956654295,"dspot_need":-7.78010615224019,"theo_dist":0.1482028408337752,"vol":0.04334038084901909,"opp_depth":513.0973753976671,"opp_depth_chg":120.80744880037116,"own_depth":537.3630252518558,"nticks":82.73168246288441,"stale":1.5782476139978792,"s":113.65211591993638},"sd":{"asset_c":1.106894225914569,"side_c":0.49996717704005617,"t1":50.94473679358491,"minute1":0.78628996621886,"tau1":50.94473679358491,"p1":0.17492001539004437,"pc0":0.17500152054434423,"spread1":0.014811970887411423,"mid1":0.1756347574326453,"vol30_1":0.017088483952561084,"drift_need10":0.043437203600229866,"drift_need30":0.07285429619450014,"imb1":0.3818250955908533,"micdev_need":0.007996090704810062,"qdepth_c":1922.0367212505855,"qdepth_f":683.9485234603941,"tickrate30_1":0.16956196520853806,"dist":0.11539748260549185,"dist_chg":0.11211198350052307,"mindist":0.03140264345429892,"cspread":0.01633155705769328,"cspread_chg":0.016468006880360115,"dmid_need":0.11286909600494142,"dtheo_need":0.11323428000192233,"dspot_need":10.063755882479953,"theo_dist":0.11560851342667344,"vol":0.032828934356917,"opp_depth":1205.8830965389984,"opp_depth_chg":1198.046264492293,"own_depth":1226.3692606029033,"nticks":65.52679598344044,"stale":7.132734136746268,"s":87.6937674814307}},{"coef":[-0.2071765391181712,0.022322053183974646,-0.27286310470698927,0.45529505029359146,0.2728631047070091,0.011051993565314817,-0.010756803748584108,-0.003419805296680044,-0.02248072968624293,0.09914764123468305,0.02544513150743689,-0.011164903505925687,0.03158112943574874,0.006491702486491115,-0.06820197453866945,-0.0035521994240140437,-0.038519514209841836,-2.2956824390430803,-0.1739423092564776,0.10735624418835162,0.02560330315785779,0.03826988103920506,0.17556817510915323,-0.01446203297886948,0.06904356482871196,-2.3451251630165766,0.510240307698821,0.08288771459660887,0.0044923639769716035,-0.17241229822433884,-0.07996800042895602,-0.0779477126044499,-0.16737818387044603],"intercept":-7.064284341888379,"mu":{"asset_c":1.6747249469777306,"side_c":0.5057827412513256,"t1":138.99981939289503,"minute1":2.1481723886532342,"tau1":761.0001806071051,"p1":0.4731327545068929,"pc0":0.507548217126193,"spread1":0.01931902836691411,"mid1":0.49995585896076356,"vol30_1":0.022555484076749736,"drift_need10":-0.00245198999204666,"drift_need30":-0.0021376010737009545,"imb1":0.4860329011466066,"micdev_need":-0.0020429467126193,"qdepth_c":821.7917202412513,"qdepth_f":335.57576053817604,"tickrate30_1":0.742080892099682,"dist":0.15845947110286324,"dist_chg":0.1021165164369035,"mindist":0.0408356309650053,"cspread":0.020540843716861084,"cspread_chg":0.00020676199628844117,"dmid_need":-0.10201313543875928,"dtheo_need":-0.10072449960233298,"dspot_need":-7.782715303552492,"theo_dist":0.148073777173913,"vol":0.0433111638388123,"opp_depth":513.030008119035,"opp_depth_chg":121.14560909331918,"own_depth":535.8281713944856,"nticks":82.77846633085896,"stale":1.5954326285790033,"s":113.68703605514315},"sd":{"asset_c":1.1074477533880969,"side_c":0.499968629842045,"t1":51.26551117894681,"minute1":0.7916457782842304,"tau1":51.2655111789468,"p1":0.17533934600045106,"pc0":0.17543890797187728,"spread1":0.014821727094880024,"mid1":0.17607536444986507,"vol30_1":0.0171189066251312,"drift_need10":0.043439328014628166,"drift_need30":0.0731050128254395,"imb1":0.381425492163291,"micdev_need":0.00797533103825941,"qdepth_c":1935.6769385350922,"qdepth_f":680.7607006058441,"tickrate30_1":0.1689091423521173,"dist":0.115352626797527,"dist_chg":0.1120273574014389,"mindist":0.03125829555845512,"cspread":0.016308929524792515,"cspread_chg":0.016396304250583676,"dmid_need":0.11277692862372207,"dtheo_need":0.11313778427700835,"dspot_need":10.063238826674937,"theo_dist":0.11554618091886758,"vol":0.03279664559696206,"opp_depth":1204.6632646358757,"opp_depth_chg":1190.3513413503422,"own_depth":1199.5898585627197,"nticks":65.52917486638695,"stale":7.22980384546409,"s":87.67467880435869}},{"coef":[-0.2043983674345782,-0.005347085319063093,-0.22686614429394686,0.3714484182532879,0.22686614429393848,0.005596386432120536,-0.005263215966264027,-0.003916784033699345,-0.030045226953434732,0.11338212656092342,0.005876416353690669,0.005720304219645309,0.00842558407912261,0.0043853898507378065,-0.068225020361079,0.000976620454644664,-0.013697784105437621,-2.3169474428136683,-0.15496599757821455,0.12422311666104525,0.013572441397482543,0.03984085638703701,0.15686948715124013,0.002382811142921798,0.0471389458337362,-2.3811622021018355,0.4686374677288344,0.08700157201809666,0.009895019632882555,-0.1715181590926113,-0.1155583154697995,-0.08709345429428371,-0.07719682438016771],"intercept":-7.075807728785369,"mu":{"asset_c":1.6741698700954402,"side_c":0.5063295334040296,"t1":139.01657940084834,"minute1":2.148346367974549,"tau1":760.9834205991516,"p1":0.4731266072375398,"pc0":0.5075937334305408,"spread1":0.01927965933191941,"mid1":0.5004411038573701,"vol30_1":0.022544398362937434,"drift_need10":-0.0024457308788441144,"drift_need30":-0.0021341753380169667,"imb1":0.4871660475212089,"micdev_need":-0.0020567779858165426,"qdepth_c":819.5493322507953,"qdepth_f":335.039884345175,"tickrate30_1":0.7418369813759279,"dist":0.15867842822110287,"dist_chg":0.10231887095705197,"mindist":0.040878479586426306,"cspread":0.020532351869034998,"cspread_chg":0.00020981906150583244,"dmid_need":-0.10221396142629906,"dtheo_need":-0.10093947839342524,"dspot_need":-7.792105448038177,"theo_dist":0.14830867494035,"vol":0.04336057769419407,"opp_depth":515.903588116384,"opp_depth_chg":121.8400218716861,"own_depth":536.3539219909862,"nticks":82.82259080063626,"stale":1.592570254506893,"s":113.79556601272535},"sd":{"asset_c":1.1069291098457337,"side_c":0.49996200643101796,"t1":51.30813419294474,"minute1":0.7925388690792486,"tau1":51.30813419294475,"p1":0.175047122373926,"pc0":0.175136825024081,"spread1":0.01476936343412956,"mid1":0.17578245454173477,"vol30_1":0.017095682181083954,"drift_need10":0.04350883922067061,"drift_need30":0.07305215603196161,"imb1":0.38149557218947533,"micdev_need":0.007958177218446655,"qdepth_c":1920.7553222998445,"qdepth_f":679.5069902771081,"tickrate30_1":0.16925806626045897,"dist":0.11530791088176777,"dist_chg":0.11210029797688467,"mindist":0.031226724185292876,"cspread":0.016353637292841824,"cspread_chg":0.016462094020091855,"dmid_need":0.11283052420246507,"dtheo_need":0.11319561437165375,"dspot_need":10.052618259688087,"theo_dist":0.11552962147645689,"vol":0.03277256272540861,"opp_depth":1258.087757819956,"opp_depth_chg":1243.3859408031033,"own_depth":1204.2198726316199,"nticks":65.50534462841303,"stale":7.184424841806535,"s":87.67712514110151}},{"coef":[-0.22350553065032777,0.011567925764982837,-0.25759612127567333,0.4276436304289929,0.25759612127568027,0.004071521809296398,-0.0010640492963516451,-0.03580534393591113,-0.03555723947165074,0.1032474143060241,0.004358941305631098,-0.006304885833988708,0.024066857151348917,0.0014307768562469134,-0.04999077820972365,0.004816451268716309,-0.040828844946663764,-2.2820593213080844,-0.15363442997329801,0.10878591206440266,0.04618599277398121,0.022372959418684453,0.15421072318989892,0.06093346118215051,0.023660555607678768,-2.3777585527337757,0.5217381321864386,0.06817655530093415,0.02064415630470107,-0.18448786952961546,-0.06240050184389801,-0.08522778144547723,-0.1543051406919077],"intercept":-7.067094761835452,"mu":{"asset_c":1.6751308987274656,"side_c":0.5058241648992576,"t1":138.94503496155886,"minute1":2.1471119432661716,"tau1":761.0549650384412,"p1":0.47323236181071054,"pc0":0.5074770678685048,"spread1":0.01929057032078473,"mid1":0.500408814123807,"vol30_1":0.02252839325954401,"drift_need10":-0.002458348522004242,"drift_need30":-0.00221805408271474,"imb1":0.48695229818398733,"micdev_need":-0.0020474460664103925,"qdepth_c":817.2888752651114,"qdepth_f":333.33994565217387,"tickrate30_1":0.7418793411983033,"dist":0.15858348522004242,"dist_chg":0.10225370327412514,"mindist":0.0408458874602333,"cspread":0.020513512393955463,"cspread_chg":0.00022388653234358433,"dmid_need":-0.10214176000795333,"dtheo_need":-0.10088196662910921,"dspot_need":-7.772376234424708,"theo_dist":0.14823821828605513,"vol":0.043359952279957585,"opp_depth":515.8795524589077,"opp_depth_chg":123.87481690747613,"own_depth":532.2091297720042,"nticks":82.75878181336161,"stale":1.5911320254506893,"s":113.6739461823966},"sd":{"asset_c":1.1065004691974498,"side_c":0.4999681490072687,"t1":50.798605621960576,"minute1":0.7842214077368214,"tau1":50.798605621960576,"p1":0.17534013453652628,"pc0":0.1754136525007119,"spread1":0.0147255227946164,"mid1":0.1760564004739372,"vol30_1":0.01710585269372591,"drift_need10":0.043321650645749075,"drift_need30":0.07299639785770835,"imb1":0.38152808821401374,"micdev_need":0.00793645113928368,"qdepth_c":1913.0854925858562,"qdepth_f":671.5157604882863,"tickrate30_1":0.1692213779043862,"dist":0.11551202850506884,"dist_chg":0.11222366822528089,"mindist":0.031238603044875687,"cspread":0.01631555374065367,"cspread_chg":0.01639916614678475,"dmid_need":0.11299388185343925,"dtheo_need":0.11333909391071355,"dspot_need":10.048714600481805,"theo_dist":0.11574122686382743,"vol":0.032870192017574316,"opp_depth":1260.3040021195256,"opp_depth_chg":1242.972894263593,"own_depth":1186.2189664658163,"nticks":65.51827111986591,"stale":7.2053778563152004,"s":87.65188986396022}},{"coef":[-0.21321527570737292,0.008064634786597625,-0.23509736662910666,0.38578851305555567,0.23509736662911382,0.007367713356245028,-0.005657217909884526,-0.02026195703085086,-0.0288853807208859,0.10987916791581886,0.012821793463221912,-0.000830163853176418,0.02765194572860128,-0.0011215452553826682,-0.04208413643967391,0.008113644892981112,-0.03219569288766775,-2.3668598414507525,-0.21302756943966586,0.11651975166859053,0.018128024656365205,0.024421449469622228,0.21335288058449398,-0.04365894456780784,0.03880541694966034,-2.3502278879167933,0.5148897770120417,0.06207977819739609,0.032475499500657035,-0.192382754478434,0.003801333436280474,-0.08853230841457117,-0.22596775155544943],"intercept":-7.159821020727327,"mu":{"asset_c":1.678751325556734,"side_c":0.5056419008483564,"t1":138.9802185511665,"minute1":2.1476504506892895,"tau1":761.0197814488336,"p1":0.4730883483563097,"pc0":0.5075797570917285,"spread1":0.019331894551961826,"mid1":0.4997354892961293,"vol30_1":0.022547273081256626,"drift_need10":-0.002498599880699894,"drift_need30":-0.0021344280222693533,"imb1":0.4868762667351537,"micdev_need":-0.0020372991781548253,"qdepth_c":812.6798763918346,"qdepth_f":334.82186091595975,"tickrate30_1":0.7416284713016966,"dist":0.15875994996023332,"dist_chg":0.1023733016304348,"mindist":0.04090437765111347,"cspread":0.02055937665694592,"cspread_chg":0.00021730017232237544,"dmid_need":-0.10226465154427358,"dtheo_need":-0.10102737026113467,"dspot_need":-7.814277414170201,"theo_dist":0.14838487622613997,"vol":0.043386826285790034,"opp_depth":510.6039161916755,"opp_depth_chg":120.38909149655356,"own_depth":532.1429820055673,"nticks":82.82927657741251,"stale":1.5779079400848355,"s":113.82021308324497},"sd":{"asset_c":1.1056366619986198,"side_c":0.4999702390049426,"t1":50.96793784365376,"minute1":0.7868045790387495,"tau1":50.96793784365376,"p1":0.1754705738031487,"pc0":0.1755480016561471,"spread1":0.014791443431033618,"mid1":0.17619921025676313,"vol30_1":0.01716659264755153,"drift_need10":0.04345375162234272,"drift_need30":0.07312110340894529,"imb1":0.3817215547454621,"micdev_need":0.007964935308598743,"qdepth_c":1919.54813095332,"qdepth_f":683.1998193037344,"tickrate30_1":0.16936415894715845,"dist":0.11555197952973767,"dist_chg":0.11226967559264342,"mindist":0.031209649502031058,"cspread":0.016404772048524714,"cspread_chg":0.01640604945270519,"dmid_need":0.11303745138601207,"dtheo_need":0.11340686743488204,"dspot_need":10.099408782807094,"theo_dist":0.11576387146343772,"vol":0.03283741121099031,"opp_depth":1189.137073315102,"opp_depth_chg":1173.0664770397711,"own_depth":1198.7923171818998,"nticks":65.5101225552153,"stale":7.164288697789949,"s":87.73346063897122}},{"coef":[-0.18786534308587377,0.008017794545775107,-0.23413903670504815,0.37034174764889716,0.23413903670504344,0.008083269589985296,-0.005756083347619335,-0.027338494382763902,-0.02608150671328328,0.1078066619189003,0.0046474280230926176,-0.00701705902865566,0.02418636067685812,-0.017400560193542178,-0.05394789986805461,0.008656789514880234,-0.034792643148649244,-2.334200052583904,-0.1823150789975844,0.11847778206098888,-0.0067794724933293304,0.04824207065793826,0.1845916330154441,-0.012176730898093655,0.03259071917690488,-2.420012495944081,0.5089026251906552,0.08893006701450476,-0.0009329599992796434,-0.17242381028458703,-0.07551574454872106,-0.10244814073752734,-0.13767286474676874],"intercept":-7.173639338781301,"mu":{"asset_c":1.6758019618239661,"side_c":0.5058904427359491,"t1":139.03232287248144,"minute1":2.1484789236479322,"tau1":760.9676771275185,"p1":0.47289958907741253,"pc0":0.5077816062433722,"spread1":0.01931880467921527,"mid1":0.5002143715204136,"vol30_1":0.022533756130699894,"drift_need10":-0.002512708775185578,"drift_need30":-0.002316236413043478,"imb1":0.4868246619830328,"micdev_need":-0.002033029891304348,"qdepth_c":813.5769121155885,"qdepth_f":334.15786137990455,"tickrate30_1":0.7416648329798515,"dist":0.15889334239130437,"dist_chg":0.10250632124867445,"mindist":0.040889465137857905,"cspread":0.020541746752386007,"cspread_chg":0.00018903267497348886,"dmid_need":-0.1024118049111877,"dtheo_need":-0.10113729702412512,"dspot_need":-7.80471836061771,"theo_dist":0.1485227888056734,"vol":0.04343666307661718,"opp_depth":511.8752485418876,"opp_depth_chg":119.85048879904559,"own_depth":534.9223488865324,"nticks":82.88576186373277,"stale":1.5883814952279958,"s":113.87522368769883},"sd":{"asset_c":1.10619933953308,"side_c":0.49996737253191853,"t1":50.9869874072665,"minute1":0.7861745840109287,"tau1":50.9869874072665,"p1":0.17487748332037995,"pc0":0.17496398277096503,"spread1":0.01486821364575477,"mid1":0.17563070380922852,"vol30_1":0.0171172924034174,"drift_need10":0.043458104098089236,"drift_need30":0.07311317861757886,"imb1":0.38152250497273354,"micdev_need":0.00799415649420267,"qdepth_c":1910.9676578379492,"qdepth_f":677.9382955669417,"tickrate30_1":0.16949231497239625,"dist":0.11553051189933193,"dist_chg":0.11220782445537442,"mindist":0.031321867824631276,"cspread":0.016318623947394327,"cspread_chg":0.01638045212935371,"dmid_need":0.11296444754081614,"dtheo_need":0.11332682100624876,"dspot_need":10.088371422385116,"theo_dist":0.1157273004556793,"vol":0.032874188591462405,"opp_depth":1211.5097778509232,"opp_depth_chg":1195.8333534062506,"own_depth":1210.4141412262427,"nticks":65.55521925382402,"stale":7.166758333575901,"s":87.71633629300639}}]}
"""
L1_ENSEMBLE = json.loads(_L1_ENSEMBLE_JSON)
L1_FEATS = L1_ENSEMBLE["feats"]          # == HAZ_FEATS, verified identical order (33 feats)
L1_MODELS = L1_ENSEMBLE["models"]        # 7 dicts: {coef (list, aligned to L1_FEATS), intercept, mu, sd}
L1_SHRINK = L1_ENSEMBLE["shrink"]        # 1.0 -- hz_lcb = mean(sigmoid) - L1_SHRINK*std(sigmoid)

_L2_HONEST_JSON = r"""
{"label":"HONEST-LOOKAHEAD2-LIN","feats":["asset_c","side_c","t1","minute1","tau1","p1","pc0","spread1","mid1","vol30_1","drift_need10","drift_need30","imb1","micdev_need","qdepth_c","qdepth_f","tickrate30_1","dist","dist_chg","mindist","cspread","cspread_chg","dmid_need","dtheo_need","dspot_need","theo_dist","vol","opp_depth","opp_depth_chg","own_depth","nticks","stale","s"],"coef":[-0.000222537177101178,1.6999362229735103e-05,9.215628870218292e-06,-0.000141271748209638,-9.21562887029604e-06,4.078847049184808e-05,-4.2947750927317893e-05,2.5690281949723425e-05,-3.2007265516296104e-05,0.0001361117465293599,5.535497160368239e-05,-8.215438215874996e-05,5.186051364403619e-05,-2.1761055928286725e-05,-8.329333668678256e-05,1.9106340322004853e-05,-7.825161418210775e-05,0.006967033045464568,-0.00020178963047524538,-0.00010920734897180442,-0.0001369365336371364,0.00019475950578363356,0.0002147889323423354,-4.499061457343176e-05,-0.0001438339708600769,-0.0072466321411892905,0.0003040874737425728,-8.890668366138909e-05,0.00022512957526267782,-0.00015458747198351767,-0.00019189274005608134,5.619410509546716e-05,-3.099223147275227e-05],"intercept":0.000741796631370516,"mu":{"asset_c":1.6840349307419662,"side_c":0.5061281395010092,"t1":139.12713305727226,"minute1":2.149024422387304,"tau1":760.8728669427277,"p1":0.4726365843338813,"pc0":0.5079440248038787,"spread1":0.01941939086223998,"mid1":0.5001681371426986,"vol30_1":0.022489971214738055,"drift_need10":-0.002536952646510047,"drift_need30":-0.0022028528622261064,"imb1":0.4862782126780004,"micdev_need":-0.002053413307808089,"qdepth_c":813.7894930325793,"qdepth_f":332.2542640336822,"tickrate30_1":0.7414271247338231,"dist":0.161939405289552,"dist_chg":0.10518867178558795,"mindist":0.0415248073468312,"cspread":0.020620103904391313,"cspread_chg":0.0001696735127036644,"dmid_need":-0.10510383502923612,"dtheo_need":-0.10386201039043912,"dspot_need":-7.9456197848388355,"theo_dist":0.15158522657122445,"vol":0.04387799411809587,"opp_depth":503.5063050127973,"opp_depth_chg":115.53905362382172,"own_depth":538.5778776591686,"nticks":83.04712459509888,"stale":1.5969792815476065,"s":114.090593808741},"sd":{"asset_c":1.105786463998008,"side_c":0.49996417842653856,"t1":50.99094468126136,"minute1":0.7863333327428542,"tau1":50.99094468126136,"p1":0.17518048618840357,"pc0":0.1752837025030665,"spread1":0.01489655527385045,"mid1":0.17596147431181994,"vol30_1":0.017107307290493222,"drift_need10":0.043299080782947724,"drift_need30":0.07291937270126596,"imb1":0.381847394753674,"micdev_need":0.008009630288475119,"qdepth_c":1918.620091326021,"qdepth_f":671.201263394952,"tickrate30_1":0.1691362702543666,"dist":0.11419739467872644,"dist_chg":0.11116625817192093,"mindist":0.0315106247201485,"cspread":0.016391519057196987,"cspread_chg":0.01648240467633145,"dmid_need":0.11191103000577593,"dtheo_need":0.1122573939264696,"dspot_need":10.092153524314215,"theo_dist":0.11437527266132326,"vol":0.03272172222572259,"opp_depth":1194.4396580406253,"opp_depth_chg":1194.1349241276635,"own_depth":1215.9256544571203,"nticks":64.4387433093127,"stale":7.186556003059369,"s":86.11521580399406},"kappa2":-0.005}
"""
L2_HONEST = json.loads(_L2_HONEST_JSON)
L2_HONEST_FEATS = L2_HONEST["feats"]     # == HAZ_FEATS order (33 feats)
L2_HONEST_COEF = L2_HONEST["coef"]       # list, aligned to L2_HONEST_FEATS
L2_HONEST_INTERCEPT = L2_HONEST["intercept"]
L2_HONEST_MU = L2_HONEST["mu"]
L2_HONEST_SD = L2_HONEST["sd"]
L2_KAPPA2 = L2_HONEST["kappa2"]          # -0.005 (-0.50c); TRAIN-tuned, identical to the leaky C7's


def _std_dot(raw_feats, feats, coef, mu, sd, intercept):
    """Standardized linear/logit-pre-activation dot product: sum coef[i]*((x_i-mu_i)/sd_i) +
    intercept, matching sklearn's StandardScaler+LinearModel convention used to fit L1_MODELS and
    L2_HONEST. Missing raw features filled with 0.0 BEFORE standardizing (matches hazard_predict's
    convention above)."""
    z = intercept
    for i, f in enumerate(feats):
        x = raw_feats.get(f)
        if x is None:
            x = 0.0
        sd_f = sd[f] if sd[f] else 1.0
        z += coef[i] * ((x - mu[f]) / sd_f)
    return z


def l1_lcb_hazard(raw_feats):
    """STRAND_DEFENSE Layer 1 CHAMPION, numpy-deployable form: 7x 80%-bootstrap logistic-33
    ensemble, hz_lcb = clip(mean(sigmoid(z_i)) - L1_SHRINK*std(sigmoid(z_i)), 0, 1). Used by
    stack_full only (stack_lean reuses hazard_predict's base single logistic instead)."""
    preds = np.empty(len(L1_MODELS))
    for i, m in enumerate(L1_MODELS):
        z = _std_dot(raw_feats, L1_FEATS, m["coef"], m["mu"], m["sd"], m["intercept"])
        preds[i] = _sigmoid(z)
    lcb = preds.mean() - L1_SHRINK * preds.std()
    return float(min(max(lcb, 0.0), 1.0))


def l2_honest_wait_edge_next(raw_feats):
    """Honest (non-leaky) E[wait_edge(s+5) | features(s)] -- see module docstring's LEAKAGE FINDING.
    Plain linear regression on the SAME 33 standardized HAZ_FEATS available at the CURRENT step s
    (never consumes the s+5 book). Coefficients embedded in L2_HONEST."""
    return _std_dot(raw_feats, L2_HONEST_FEATS, L2_HONEST_COEF, L2_HONEST_MU, L2_HONEST_SD,
                     L2_HONEST_INTERCEPT)


def stack_stop_policy(p1, pc0, side, c_series, cwin, resolved_up, base_const, give_cap,
                       use_lcb_sensor, kappa2=None):
    """STACK-FULL / STACK-LEAN disposal mechanic: same horizon-scan skeleton as
    hazard_stop_policy (ported verbatim below -- SMAX/STEP/pairing/fallback semantics identical),
    but the per-step decision is L2's HONEST 2-step lookahead (w2 = hz*(dist+fee) - (1-hz)*edca +
    (1-hz)*l2_honest_wait_edge_next(raw), dispose iff w2 < kappa2) with an L3 give-cap gating the
    dispose trigger (see docstring). hz comes from hazard_predict's base logistic when
    use_lcb_sensor=False (stack_lean) or l1_lcb_hazard's ensemble when True (stack_full); edca
    (cost of waiting) is always hazard_predict's embedded linear dca (HAZ_DCA), held fixed for
    both -- matching the layer1/layer2 studies' own convention."""
    if kappa2 is None:
        kappa2 = L2_KAPPA2
    t1 = c_series[0][0]
    need = 1.0 if side == "yes" else -1.0
    cb_1, ca_1 = c_series[0][1], c_series[0][2]
    mid_f, spot_f, theo_f = cwin[0][1], cwin[0][2], cwin[0][3]
    opp_1 = (cwin[0][5] if side == "yes" else cwin[0][7]) or 0
    cspread_1 = ca_1 - cb_1
    mindist = ca_1 - pc0
    mids_win = [mid_f] if mid_f is not None else []

    ttp = None
    for (t, cb, ca) in c_series:
        if ca <= pc0 + 1e-9:
            ttp = t - t1
            break

    k = 0
    j = 0
    last_ca, last_s = None, None
    for s in range(0, HORIZON_MAX, HORIZON_STEP):
        hb = t1 + s
        while j < len(c_series) and c_series[j][0] < hb - 1e-9:
            j += 1
        if j >= len(c_series):
            break   # matches hazard_stop_policy / replay_state_rule: `if pd.isna(ca): break`
        ed_ca = c_series[j][2]
        last_ca, last_s = ed_ca, s

        if ttp is not None and ttp <= s:
            return dict(completed=1, locked=1.0 - p1 - pc0, mode="pair", wait_s=ttp)

        while k + 1 < len(cwin) and cwin[k + 1][0] <= hb + 1e-9:
            k += 1
            r = cwin[k]
            if r[1] is not None:
                mids_win.append(r[1])
            cq = c_quotes(r, side)
            if cq:
                mindist = min(mindist, cq[1] - pc0)
        r_h = cwin[k]
        cb_h, ca_h = c_quotes(r_h, side)
        mid_h, spot_h, theo_h = r_h[1], r_h[2], r_h[3]
        opp_h = (r_h[5] if side == "yes" else r_h[7]) or 0
        own_h = (r_h[7] if side == "yes" else r_h[5]) or 0
        vol_h = statistics.pstdev(mids_win) if len(mids_win) >= 3 else 0.0
        dist = ca_h - pc0
        dist_chg = dist - (ca_1 - pc0)
        cspread = ca_h - cb_h
        cspread_chg = cspread - cspread_1
        dmid_need = need * (mid_h - mid_f) if (mid_h is not None and mid_f is not None) else None
        dtheo_need = need * (theo_h - theo_f) if (theo_h is not None and theo_f is not None) else None
        dspot_need = need * (spot_h / spot_f - 1.0) * 1e4 if (spot_h and spot_f) else None
        theo_dist = (((1 - theo_h) if side == "yes" else theo_h) - pc0) if theo_h is not None else None
        stale = hb - r_h[0]

        raw = dict(base_const)
        raw.update(dist=dist, dist_chg=dist_chg, mindist=mindist, cspread=cspread,
                   cspread_chg=cspread_chg, dmid_need=dmid_need, dtheo_need=dtheo_need,
                   dspot_need=dspot_need, theo_dist=theo_dist, vol=vol_h, opp_depth=opp_h,
                   opp_depth_chg=opp_h - opp_1, own_depth=own_h, nticks=len(mids_win),
                   stale=stale, s=float(s))
        hz_base, edca = hazard_predict(raw)
        hz = l1_lcb_hazard(raw) if use_lcb_sensor else hz_base
        fee_now = taker_fee(ed_ca) if ed_ca is not None else 0.05
        wait_edge = hz * (dist + fee_now) - (1 - hz) * edca
        w_next_hat = l2_honest_wait_edge_next(raw)
        w2 = wait_edge + (1 - hz) * w_next_hat
        if w2 < kappa2:
            give = max(0.0, p1 + ed_ca + fee_now - 1.0)
            if give <= give_cap + 1e-9:
                return dict(completed=1, locked=1.0 - p1 - ed_ca - fee_now, mode="dispose", wait_s=s)
            # else: L3 give-cap gates the trigger -- HOLD, continue to the next 5s step (see docstring)

        if ttp is not None and ttp <= s + HORIZON_STEP:
            return dict(completed=1, locked=1.0 - p1 - pc0, mode="pair", wait_s=ttp)

    # fallback: matches hazard_stop_policy's post-loop "if not done" branch exactly (unconditional,
    # not give-cap-gated -- documented in the module docstring)
    if ttp is not None and ttp <= HORIZON_MAX:
        return dict(completed=1, locked=1.0 - p1 - pc0, mode="pair", wait_s=ttp)
    if last_ca is not None:
        return dict(completed=1, locked=1.0 - p1 - last_ca - taker_fee(last_ca), mode="force", wait_s=last_s)
    payout = 1.0 if (side == "yes" and resolved_up == 1) or (side == "no" and resolved_up == 0) else 0.0
    return dict(completed=0, locked=payout - p1, mode="strand", wait_s=None)


def hazard_stop_policy(p1, pc0, side, c_series, cwin, resolved_up, base_const):
    """Port of minhaz/core.py's replay_state_rule, but computing the h{s}_ hazard features and
    ed{s}_ca execution price INLINE from raw ticks (rather than from a precomputed CSV), for
    s = 0,5,...,295 (HORIZON_MAX=300 exclusive, matching SMAX in run_minhaz.py exactly).
    base_const: dict of the per-event BASE features (constant across all horizons), computed once
    at the pre-fill tick -- see caller."""
    t1 = c_series[0][0]
    need = 1.0 if side == "yes" else -1.0
    cb_1, ca_1 = c_series[0][1], c_series[0][2]
    mid_f, spot_f, theo_f = cwin[0][1], cwin[0][2], cwin[0][3]
    opp_1 = (cwin[0][5] if side == "yes" else cwin[0][7]) or 0
    cspread_1 = ca_1 - cb_1
    mindist = ca_1 - pc0
    mids_win = [mid_f] if mid_f is not None else []

    # time-to-pair (ttp), scanned once up front -- identical semantics to build_alarm.py's ttp
    ttp = None
    for (t, cb, ca) in c_series:
        if ca <= pc0 + 1e-9:
            ttp = t - t1
            break

    k = 0
    j = 0
    last_ca, last_s = None, None
    for s in range(0, HORIZON_MAX, HORIZON_STEP):
        hb = t1 + s
        while j < len(c_series) and c_series[j][0] < hb - 1e-9:
            j += 1
        if j >= len(c_series):
            break   # matches replay_state_rule: `if pd.isna(ca): break`
        ed_ca = c_series[j][2]
        last_ca, last_s = ed_ca, s

        if ttp is not None and ttp <= s:
            return dict(completed=1, locked=1.0 - p1 - pc0, mode="pair", wait_s=ttp)

        while k + 1 < len(cwin) and cwin[k + 1][0] <= hb + 1e-9:
            k += 1
            r = cwin[k]
            if r[1] is not None:
                mids_win.append(r[1])
            cq = c_quotes(r, side)
            if cq:
                mindist = min(mindist, cq[1] - pc0)
        r_h = cwin[k]
        cb_h, ca_h = c_quotes(r_h, side)
        mid_h, spot_h, theo_h = r_h[1], r_h[2], r_h[3]
        opp_h = (r_h[5] if side == "yes" else r_h[7]) or 0
        own_h = (r_h[7] if side == "yes" else r_h[5]) or 0
        vol_h = statistics.pstdev(mids_win) if len(mids_win) >= 3 else 0.0
        dist = ca_h - pc0
        dist_chg = dist - (ca_1 - pc0)
        cspread = ca_h - cb_h
        cspread_chg = cspread - cspread_1
        dmid_need = need * (mid_h - mid_f) if (mid_h is not None and mid_f is not None) else None
        dtheo_need = need * (theo_h - theo_f) if (theo_h is not None and theo_f is not None) else None
        dspot_need = need * (spot_h / spot_f - 1.0) * 1e4 if (spot_h and spot_f) else None
        theo_dist = (((1 - theo_h) if side == "yes" else theo_h) - pc0) if theo_h is not None else None
        stale = hb - r_h[0]

        raw = dict(base_const)
        raw.update(dist=dist, dist_chg=dist_chg, mindist=mindist, cspread=cspread,
                   cspread_chg=cspread_chg, dmid_need=dmid_need, dtheo_need=dtheo_need,
                   dspot_need=dspot_need, theo_dist=theo_dist, vol=vol_h, opp_depth=opp_h,
                   opp_depth_chg=opp_h - opp_1, own_depth=own_h, nticks=len(mids_win),
                   stale=stale, s=float(s))
        hz, edca = hazard_predict(raw)
        fee_now = taker_fee(ed_ca) if ed_ca is not None else 0.05
        wait_edge = hz * (dist + fee_now) - (1 - hz) * edca
        if wait_edge < HAZ_KAPPA:
            return dict(completed=1, locked=1.0 - p1 - ed_ca - taker_fee(ed_ca), mode="dispose", wait_s=s)

        if ttp is not None and ttp <= s + HORIZON_STEP:
            return dict(completed=1, locked=1.0 - p1 - pc0, mode="pair", wait_s=ttp)

    # fallback: matches replay_state_rule's post-loop "if not done" branch exactly
    if ttp is not None and ttp <= HORIZON_MAX:
        return dict(completed=1, locked=1.0 - p1 - pc0, mode="pair", wait_s=ttp)
    if last_ca is not None:
        return dict(completed=1, locked=1.0 - p1 - last_ca - taker_fee(last_ca), mode="force", wait_s=last_s)
    payout = 1.0 if (side == "yes" and resolved_up == 1) or (side == "no" and resolved_up == 0) else 0.0
    return dict(completed=0, locked=payout - p1, mode="strand", wait_s=None)


# ================================================================================================
# I/O: tick / settlement loading (recursive glob, matches box_policy_ab.py's _rglob convention so
# this works unmodified against BOTH the flat live gha_data/ layout and the day-partitioned
# gha-data-branch archive layout)
# ================================================================================================
def _rglob(root, pattern):
    return sorted(set(glob.glob(os.path.join(root, "**", pattern), recursive=True))
                  | set(glob.glob(os.path.join(root, pattern))))


def resolve_roots(data_dir, day):
    if day:
        day_dir = os.path.join(data_dir, day)
        if os.path.isdir(day_dir):
            return [day_dir]
    return [data_dir]


def build_settle_map(roots):
    sm = {}
    for root in roots:
        for f in _rglob(root, "shadow_windows_kalshi_*.jsonl"):
            base = os.path.basename(f)
            try:
                asset = base.split("shadow_windows_kalshi_")[1].split("15m")[0]
            except Exception:
                asset = None
            try:
                with open(f) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                        except Exception:
                            continue
                        ws = d.get("ws")
                        ru = d.get("resolved_up")
                        a = d.get("asset", asset)
                        if ws is None or ru is None or a is None:
                            continue
                        sm[(a, ws)] = int(ru)
            except Exception:
                continue
    return sm


def load_asset_ticks(roots, asset):
    per_ws = {}
    for root in roots:
        for f in _rglob(root, f"ticks_kalshi_{asset}15m*.jsonl.gz"):
            try:
                with gzip.open(f, "rt") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                        except Exception:
                            continue
                        ws = d.get("ws")
                        ticks = d.get("ticks")
                        if ws is None or not ticks:
                            continue
                        per_ws.setdefault(ws, []).extend(ticks)
            except Exception:
                continue
    for ws in list(per_ws.keys()):
        arr = per_ws[ws]
        arr.sort(key=lambda r: r[0])
        deduped, last_t = [], None
        for r in arr:
            if last_t is not None and r[0] == last_t:
                continue
            deduped.append(r)
            last_t = r[0]
        per_ws[ws] = deduped
    return per_ws


def existing_keys_for(fp):
    keys = set()
    if os.path.isfile(fp):
        try:
            with open(fp) as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    keys.add((d.get("ws"), d.get("asset"), d.get("arm")))
        except Exception:
            pass
    return keys


def thickbook_threshold(data_dir, asset, day):
    """80th-percentile of qdepth_c ('live'-arm rows) from this script's own output over the
    THICKBOOK_LOOKBACK_DAYS most recent PRIOR day-partitioned runs, if enough samples exist;
    else the documented bootstrap constant. Only meaningful when --day is used (the historical,
    day-partitioned archive) -- in flat/live mode there is no persistent prior-day output to read
    (the collector's gha_data/ is wiped every cycle), so this always falls back to the bootstrap
    constant there, which is the intended/expected behavior (documented in the module docstring)."""
    if not day:
        return THICKBOOK_BOOTSTRAP, "bootstrap(flat-mode)"
    try:
        base_day = datetime.strptime(day, "%Y-%m-%d")
    except Exception:
        return THICKBOOK_BOOTSTRAP, "bootstrap(bad-day)"
    candidates = []
    if os.path.isdir(data_dir):
        for name in os.listdir(data_dir):
            if len(name) == 10 and name[4] == "-" and name[7] == "-":
                try:
                    d = datetime.strptime(name, "%Y-%m-%d")
                except Exception:
                    continue
                if d < base_day:
                    candidates.append((d, name))
    candidates.sort()
    recent = [name for _, name in candidates[-THICKBOOK_LOOKBACK_DAYS:]]
    vals = []
    for name in recent:
        fp = os.path.join(data_dir, name, f"box_shadow_{asset}15m.jsonl")
        if not os.path.isfile(fp):
            continue
        try:
            with open(fp) as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if d.get("arm") == "live" and d.get("qdepth_c") is not None:
                        vals.append(float(d["qdepth_c"]))
        except Exception:
            continue
    if len(vals) < THICKBOOK_MIN_N:
        return THICKBOOK_BOOTSTRAP, f"bootstrap(n={len(vals)}<{THICKBOOK_MIN_N})"
    pctl = float(np.percentile(vals, THICKBOOK_PCTL))
    return pctl, f"rolling{THICKBOOK_LOOKBACK_DAYS}d(n={len(vals)})"


# ================================================================================================
# Per-window arm replay
# ================================================================================================
def process_window(ws, rows, asset, resolved_up, thick_threshold, existing_keys, out_fh):
    written = 0
    open_state = window_open_state(rows)
    if open_state is None:
        return 0
    cell_flag = open_state["spread0"] > CELL_VETO_SPREAD0 + 1e-12

    def emit(arm, locked, filled, stranded, disposed_at_s, qdepth_c=None):
        nonlocal written
        key = (ws, asset, arm)
        if key in existing_keys:
            return
        locked_f = round(float(locked), 4)
        stranded_b = bool(stranded)
        # dispose_give: cents actually given away below flat lock, ADDITIVE risk-benchmark field.
        # Derived purely from (locked, stranded) -- no policy-function signature changes needed.
        # None when stranded (a strand is a settlement loss, not a "give"; distinct risk category
        # per STRAND_DEFENSE Layer 3/4). 0.0 for maker/pair completions (locked>=0 by construction,
        # no cross was needed). max(0,-locked) for taker/dispose/force completions that crossed.
        dispose_give = None if stranded_b else round(max(0.0, -locked_f), 4)
        row = {"ws": ws, "asset": asset, "arm": arm,
               "locked": locked_f, "filled": bool(filled),
               "stranded": stranded_b,
               "disposed_at_s": (round(float(disposed_at_s), 2) if disposed_at_s is not None else None),
               "dispose_give": dispose_give}
        if qdepth_c is not None:
            row["qdepth_c"] = round(float(qdepth_c), 1)
        out_fh.write(json.dumps(row) + "\n")
        existing_keys.add(key)
        written += 1

    ff = find_first_fill(rows)
    if ff is None:
        for arm in ARMS:
            emit(arm, 0.0, False, False, None)
        return written

    if ff.get("both"):
        spread1 = ff["spread1"]
        # L0 veto in the simultaneous-both-sides-fill case: qdepth_c is not meaningfully defined
        # here (no single completing side was "consumed"), matching thickbook_veto's own precedent
        # of not applying to "both" fills -- only the minute1-at-fill half of the L0 rule applies.
        l0_minute1_both = float(int(ff["row_i"][0] // 60))
        l0_flag_both = l0_minute1_both > L0_MINUTE1_MAX
        for arm in ARMS:
            veto = (cell_flag and arm in ("cell_veto", "combined")) or \
                   (l0_flag_both and arm in STACK_ARMS)
            if veto:
                emit(arm, 0.0, False, False, None)
            else:
                emit(arm, spread1, True, False, 0.0)
        return written

    side, p1, pc0 = ff["side"], ff["p1"], ff["pc0"]
    idx_i, idx_fill, ri = ff["idx_i"], ff["idx_fill"], ff["row_i"]
    bsz1, asz1 = ri[5], ri[7]
    qdepth_c = (asz1 if side == "yes" else bsz1) or 0
    qdepth_f = (bsz1 if side == "yes" else asz1) or 0
    thick_flag = qdepth_c > thick_threshold
    # c3_share: completing-side depth SHARE at fill (MILD variant, veto iff share > 0.9). Guard
    # div-by-zero: if both sides are empty at fill, do NOT veto (see module docstring item 9).
    c3_denom = qdepth_c + qdepth_f
    c3_flag = (c3_denom > 0) and ((qdepth_c / c3_denom) > C3_SHARE_MAX)
    # L0 champion entry veto (stack_full/stack_lean only): minute1 taken from the FILL row itself
    # (ri[0]) rather than base_const's c_series[0][0]-derived minute1, so it is defined identically
    # whether or not c_series ends up empty below (single source of truth, see module docstring).
    l0_minute1 = float(int(ri[0] // 60))
    l0_flag = (qdepth_c > L0_QDEPTH_C_MAX) or (l0_minute1 > L0_MINUTE1_MAX)

    c_series, cwin = build_c_series_cwin(rows, idx_fill, side)
    payout = 1.0 if (side == "yes" and resolved_up == 1) or (side == "no" and resolved_up == 0) else 0.0

    if not c_series:
        for arm in ARMS:
            veto = (cell_flag and arm in ("cell_veto", "combined")) or \
                   (thick_flag and arm in ("thickbook_veto", "combined")) or \
                   (c3_flag and arm == "c3_share") or \
                   (l0_flag and arm in STACK_ARMS)
            if veto:
                emit(arm, 0.0, False, False, None, qdepth_c=qdepth_c)
            else:
                emit(arm, payout - p1, True, True, None, qdepth_c=qdepth_c)
        return written

    need = 1.0 if side == "yes" else -1.0
    mic1 = micro(ri[4], ri[5], ri[6], ri[7])
    tot1 = (bsz1 or 0) + (asz1 or 0)
    base_const = dict(
        asset_c=ASSET_C.get(asset), side_c=(1.0 if side == "yes" else 0.0),
        t1=c_series[0][0], minute1=float(int(c_series[0][0] // 60)),
        tau1=WINDOW_S - c_series[0][0], p1=p1, pc0=pc0, spread1=ff["spread1"], mid1=ri[1],
        vol30_1=trailing_vol(rows, idx_i, 30),
        drift_need10=need * momentum(rows, idx_i, 10),
        drift_need30=need * momentum(rows, idx_i, 30),
        imb1=((bsz1 or 0) / tot1) if tot1 > 0 else None,
        micdev_need=(need * (mic1 - ri[1])) if (mic1 is not None and ri[1] is not None) else None,
        qdepth_c=qdepth_c, qdepth_f=qdepth_f,
        tickrate30_1=tickrate(rows, idx_i, 30),
    )

    for arm in ARMS:
        veto = (cell_flag and arm in ("cell_veto", "combined")) or \
               (thick_flag and arm in ("thickbook_veto", "combined")) or \
               (c3_flag and arm == "c3_share") or \
               (l0_flag and arm in STACK_ARMS)
        if veto:
            emit(arm, 0.0, False, False, None, qdepth_c=qdepth_c)
            continue
        if arm in ("live", "thickbook_veto", "cell_veto", "c3_share"):
            b = policy_live(p1, c_series, side, resolved_up, dispose_max_give=DISPOSE_MAX_GIVE)
        elif arm == "givecap15":
            b = policy_live(p1, c_series, side, resolved_up, dispose_max_give=0.15)
        elif arm in ("hazard_stop", "combined"):
            b = hazard_stop_policy(p1, pc0, side, c_series, cwin, resolved_up, base_const)
        elif arm == "stack_full":
            b = stack_stop_policy(p1, pc0, side, c_series, cwin, resolved_up, base_const,
                                   give_cap=0.15, use_lcb_sensor=True)
        elif arm == "stack_lean":
            b = stack_stop_policy(p1, pc0, side, c_series, cwin, resolved_up, base_const,
                                   give_cap=0.25, use_lcb_sensor=False)
        else:
            continue
        stranded = b["mode"] == "strand"
        disposed = None if stranded else b["wait_s"]
        emit(arm, b["locked"], True, stranded, disposed, qdepth_c=qdepth_c)
    return written


def run_asset(asset, data_dir, day):
    t0 = time.time()
    roots = resolve_roots(data_dir, day)
    settle_map = build_settle_map(roots)
    per_ws = load_asset_ticks(roots, asset)
    out_dir = os.path.join(data_dir, day) if day else data_dir
    os.makedirs(out_dir, exist_ok=True)
    out_fp = os.path.join(out_dir, f"box_shadow_{asset}15m.jsonl")
    existing = existing_keys_for(out_fp)
    thresh, thresh_src = thickbook_threshold(data_dir, asset, day)
    n_windows = 0
    n_rows = 0
    with open(out_fp, "a") as out_fh:
        for ws, rows in per_ws.items():
            key = (asset, ws)
            if key not in settle_map:
                continue
            resolved_up = settle_map[key]
            n = process_window(ws, rows, asset, resolved_up, thresh, existing, out_fh)
            n_windows += 1
            n_rows += n
    return dict(asset=asset, day=day, roots=roots, settle_windows=len(settle_map),
                ticks_windows=len(per_ws), windows_settled=n_windows, rows_written=n_rows,
                thick_threshold=round(thresh, 1), thick_source=thresh_src, out=out_fp,
                elapsed_s=round(time.time() - t0, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", nargs="+", default=ASSETS, choices=ASSETS)
    ap.add_argument("--data-dir", default="gha_data")
    ap.add_argument("--day", nargs="+", default=None,
                     help="YYYY-MM-DD, one or more (processed in ascending order so the "
                          "thickbook_veto rolling percentile sees earlier days first). "
                          "Omit for flat/live mode (matches the collector's per-run gha_data/).")
    args = ap.parse_args()
    days = sorted(args.day) if args.day else [None]
    for day in days:
        for asset in args.asset:
            info = run_asset(asset, args.data_dir, day)
            print(f"[box_shadow] {json.dumps(info)}", flush=True)


if __name__ == "__main__":
    main()
