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

Output: gha_data/<day>/box_shadow_<asset>15m.jsonl (append, idempotent per (ws,asset,arm)).
Rows: {"ws":.., "asset":.., "arm":.., "locked":.., "filled":.., "stranded":.., "disposed_at_s":..,
       "qdepth_c":..}  (qdepth_c is an ADDITIVE extra field, kept so a later day's thickbook_veto
       run can compute a genuine rolling percentile from this file's own prior output.)

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

ARMS = ["live", "hazard_stop", "thickbook_veto", "cell_veto", "givecap15", "combined"]

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
        row = {"ws": ws, "asset": asset, "arm": arm,
               "locked": round(float(locked), 4), "filled": bool(filled),
               "stranded": bool(stranded),
               "disposed_at_s": (round(float(disposed_at_s), 2) if disposed_at_s is not None else None)}
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
        for arm in ARMS:
            veto = cell_flag and arm in ("cell_veto", "combined")
            if veto:
                emit(arm, 0.0, False, False, None)
            else:
                emit(arm, spread1, True, False, 0.0)
        return written

    side, p1, pc0 = ff["side"], ff["p1"], ff["pc0"]
    idx_i, idx_fill, ri = ff["idx_i"], ff["idx_fill"], ff["row_i"]
    bsz1, asz1 = ri[5], ri[7]
    qdepth_c = (asz1 if side == "yes" else bsz1) or 0
    thick_flag = qdepth_c > thick_threshold

    c_series, cwin = build_c_series_cwin(rows, idx_fill, side)
    payout = 1.0 if (side == "yes" and resolved_up == 1) or (side == "no" and resolved_up == 0) else 0.0

    if not c_series:
        for arm in ARMS:
            veto = (cell_flag and arm in ("cell_veto", "combined")) or \
                   (thick_flag and arm in ("thickbook_veto", "combined"))
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
        qdepth_c=qdepth_c, qdepth_f=(bsz1 if side == "yes" else asz1) or 0,
        tickrate30_1=tickrate(rows, idx_i, 30),
    )

    for arm in ARMS:
        veto = (cell_flag and arm in ("cell_veto", "combined")) or \
               (thick_flag and arm in ("thickbook_veto", "combined"))
        if veto:
            emit(arm, 0.0, False, False, None, qdepth_c=qdepth_c)
            continue
        if arm in ("live", "thickbook_veto", "cell_veto"):
            b = policy_live(p1, c_series, side, resolved_up, dispose_max_give=DISPOSE_MAX_GIVE)
        elif arm == "givecap15":
            b = policy_live(p1, c_series, side, resolved_up, dispose_max_give=0.15)
        elif arm in ("hazard_stop", "combined"):
            b = hazard_stop_policy(p1, pc0, side, c_series, cwin, resolved_up, base_const)
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
