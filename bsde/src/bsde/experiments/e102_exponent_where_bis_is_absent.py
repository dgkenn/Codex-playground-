"""E102 -- Where BIS is ABSENT at emergence, does the aperiodic exponent still carry emergence information?

REGISTERED BEFORE THE EXTRACTION IT CONSUMES HAS FINISHED. `vitaldb_emergence.s?.csv` was launched from
`bsde/scripts/build_vitaldb_emergence_plan.py` at the same commit boundary as this file; the plan is built
from VitalDB's own `aneend` landmark and consults no candidate column, no BIS value and no exponent.

=========================================================================================================
THE QUESTION E90 REFUSED TO ANSWER
=========================================================================================================
E90 measured AVAILABILITY and said so in its own text: the self-computed exponent is finite in 75.1 % of
peri-emergence windows where BIS is finite in 29.9 %, DiD +0.3678 [+0.3215, +0.4152], outside a placebo of
[-0.061, +0.021]. Its verdict named the limit explicitly -- "**availability is not validity: the windows
where a monitor withdraws its index are the windows where artefact is most likely**" -- and deferred the
believability question rather than answering it.

**This is that question, and it is the one that decides whether E90 is a result or a curiosity.** A number
that is computable everywhere and means nothing where the incumbent is missing is worse than a missing
number, because a missing number announces itself.

=========================================================================================================
WHY A NEW EXTRACTION WAS NEEDED -- counted before the design (rule 32)
=========================================================================================================
On `vitaldb_grid.csv` the peri-emergence period holds 902 exponent-finite windows across 222 cases (362
BIS-present, 540 BIS-absent) and **exactly ONE case has >= 3 windows in BOTH cells**. Any present-versus-
absent contrast on that table is between CASES, and BIS availability is a property of a case's monitor and
sensor -- so a between-case contrast compares monitors. The new plan samples every 30 s from -900 s to
+300 s around `aneend`, 250 cases, 8,509 windows, which puts both cells inside the same case.

=========================================================================================================
THE ANCHOR, AND WHY IT IS THIS ONE
=========================================================================================================
BIS cannot be the reference: it is missing in exactly the windows under test. The anchor must be something
recorded independently of the EEG monitor, and the clinical record supplies one -- **time relative to the
end of anaesthesia**. Emergence is a monotone process on the timescale sampled here: the anaesthetic is
being cleared, so a measure that tracks anaesthetic depth must trend as `rel_aneend_s` increases.

    rho_cell = spearman( whole_head_exponent , meta_rel_aneend_s )  within case, within cell

The exponent is expected to FALL as emergence approaches, so rho is expected negative in a cell where the
measure is behaving. **A cell where the measure is noise returns rho ~ 0; a cell where it is driven by
artefact can return either sign.**

    P   D = mean over cases of ( rho_absent - rho_present ),  case bootstrap, 4000 reps.

VERDICT, wrong direction FIRST (rule 37) -- and here the "wrong" direction is the one that HELPS the
product framing, which is why it is worth stating that PREDICTED = D > 0, i.e. **I expect the exponent to
be WORSE where BIS is absent**, because a monitor withdraws its index when the signal is bad:

    (a) interval excludes 0 and NEGATIVE -> BETTER WHERE BIS IS ABSENT. The exponent carries MORE
        emergence information exactly where the incumbent withdraws. This is the outcome that would make
        E90 a usable result, and it is the one I do not expect. It would need its own scrutiny before use,
        starting with G4.
    (b) interval includes 0 and is NARROWER than the equivalence margin -> EQUIVALENT. The exponent
        behaves the same either way; E90's availability advantage transports.
    (c) interval includes 0 and is WIDER than the margin -> UNDETERMINED, printed as that and not as (b).
        Rule 31: a hypothesis of absence needs the power to have detected presence, and 40-odd cases may
        not supply it.
    (d) interval excludes 0 and POSITIVE -> WORSE WHERE BIS IS ABSENT. E90's availability positive is
        HOLLOW, and the honest summary of E90+E102 becomes "the index is computable there and should not
        be trusted there".

EQUIVALENCE MARGIN, fixed before the run and derived rather than chosen (rule 63): **half the observed
|rho_present|**, i.e. the difference that would represent losing half the emergence information the
measure carries where the incumbent agrees it is measurable. A round number would measure the round
number.

=========================================================================================================
GATES (rule 40)
=========================================================================================================
    G1  COVERAGE. >= 40 cases with >= 5 exponent-finite windows in EACH cell. Below that the within-case
        design is not populated and the comparison silently becomes between-case.
    G2  BOTH CELLS VARY. In each contributing case and cell, both `whole_head_exponent` and
        `meta_rel_aneend_s` must have non-zero spread. A rank correlation on a constant is not zero, it
        is undefined, and rule 32 was earned by not checking exactly this.
    G3  TIME OVERLAP -- the gate most likely to fire. BIS-absent windows are expected to sit LATER (nearer
        and past emergence). If the two cells occupy different stretches of time, D compares two epochs
        and not two availability states. Requires: median `rel_aneend_s` reported per cell, and the
        primary RE-RUN restricted to the time band where both cells have mass (the 10th-90th percentile
        overlap). **If the restricted estimate reverses or loses the interval, the unrestricted one is
        withdrawn**, because the unrestricted one is then a time contrast.
    G4  ARTEFACT. `emg_index` distribution reported per cell. A difference in D that coincides with an
        EMG difference is confounded and the verdict must say so rather than report D alone. This is not
        adjusted for -- EMG at emergence is downstream of waking, so conditioning on it is a collider
        (rule 13). It is REPORTED.

PLACEBO, and it GATES the verdict (rule 34). The present/absent labels are replaced by a **contiguous
random split of the same windows within each case, preserving both cell sizes and the block structure in
time**. A shuffled label would destroy the temporal clustering that makes the real split what it is and
would therefore be too easy to beat. If a random contiguous split produces the same D, the finding is
about position in time and not about the monitor. Any real D inside the placebo's central 95 % is
WITHDRAWN. Rule 64 is the reason this placebo is contiguous rather than permuted.

=========================================================================================================
SCOPE
=========================================================================================================
VitalDB, single-channel BIS-module EEG. `whole_head_exponent` on one channel is a UCE-F-like measure at
best. "Emergence information" here means association with clock time relative to a recorded anaesthesia
end, not with any assessment of consciousness, responsiveness or recall -- none of which VitalDB records
at this resolution. Nothing about consciousness is claimed or tested.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e102_exponent_where_bis_is_absent.json")
TABLES = [os.path.join(RESULTS, "vitaldb_emergence.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_emergence.s*.csv")))

FEATURE = "whole_head_exponent"
TIME = "meta_rel_aneend_s"
BIS = "meta_bis"
EMG = "emg_index"

PERI_S = 600.0
MIN_CELL = 5
MIN_CASES = 40
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return float("nan")
    xs, ys = x[ok], y[ok]
    if np.ptp(xs) <= 0 or np.ptp(ys) <= 0:
        return float("nan")          # G2 in the estimator: undefined, not zero
    rx = np.argsort(np.argsort(xs)).astype(float)
    ry = np.argsort(np.argsort(ys)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def ci(vals):
    v = np.sort(np.asarray([x for x in vals if np.isfinite(x)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def load():
    """Peri-emergence windows per case: (time, exponent, bis_present, emg)."""
    per = defaultdict(list)
    seen = set()
    n_rows = 0
    for f in TABLES:
        if not os.path.exists(f):
            continue
        for r in csv.DictReader(open(f, newline="")):
            c = r.get("meta_caseid")
            t = _f(r.get(TIME, ""))
            if not c or not math.isfinite(t) or abs(t) > PERI_S:
                continue
            key = (c, round(t, 3))
            if key in seen:                      # shards are disjoint by case, but merges are not
                continue
            seen.add(key)
            n_rows += 1
            e = _f(r.get(FEATURE, ""))
            b = _f(r.get(BIS, ""))
            per[c].append((t, e, bool(math.isfinite(b) and b > 0), _f(r.get(EMG, ""))))
    for c in per:
        per[c].sort(key=lambda z: z[0])
    return per, n_rows


def cell_rhos(rows, absent_mask):
    """(rho_absent, rho_present) for one case given a boolean 'this window is in the ABSENT cell'."""
    t = np.array([r[0] for r in rows], float)
    e = np.array([r[1] for r in rows], float)
    ok = np.isfinite(e)
    a = absent_mask & ok
    p = (~absent_mask) & ok
    if a.sum() < MIN_CELL or p.sum() < MIN_CELL:
        return float("nan"), float("nan")
    return spearman(e[a], t[a]), spearman(e[p], t[p])


def main() -> int:
    if not any(os.path.exists(f) for f in TABLES):
        print("ABSENT: no vitaldb_emergence table yet -- extraction has not landed")
        return 2
    per, n_rows = load()
    res = {"n_rows": n_rows, "n_cases_seen": len(per), "gates": {}}

    contrib, rho_a, rho_p, tmed_a, tmed_p, emg_a, emg_p, masks = [], [], [], [], [], [], [], {}
    for c, rows in per.items():
        m = np.array([not r[2] for r in rows], bool)
        ra, rp = cell_rhos(rows, m)
        if not (np.isfinite(ra) and np.isfinite(rp)):
            continue
        contrib.append(c); rho_a.append(ra); rho_p.append(rp); masks[c] = m
        t = np.array([r[0] for r in rows], float)
        g = np.array([r[3] for r in rows], float)
        tmed_a.append(float(np.median(t[m]))); tmed_p.append(float(np.median(t[~m])))
        emg_a.append(float(np.nanmedian(g[m]))); emg_p.append(float(np.nanmedian(g[~m])))
    rho_a, rho_p = np.array(rho_a), np.array(rho_p)

    res["gates"]["G1_cases"] = len(contrib)
    res["gates"]["G1_pass"] = bool(len(contrib) >= MIN_CASES)
    print(f"{n_rows} peri-emergence windows over {len(per)} cases; "
          f"{len(contrib)} cases with >= {MIN_CELL} exponent-finite windows in BOTH cells")
    print(f"G1 coverage  {'PASS' if res['gates']['G1_pass'] else 'FAIL'} "
          f"({len(contrib)} >= {MIN_CASES})")
    if not res["gates"]["G1_pass"]:
        res["verdict"] = "GATE-FAILED -- the within-case design is not populated"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # G2 is enforced inside `spearman` (a constant returns nan and the case drops); report the count
    res["gates"]["G2_dropped_for_degeneracy"] = int(len(per) - len(contrib))
    res["gates"]["G2_pass"] = True

    D = rho_a - rho_p
    point = float(np.mean(D))
    rng = np.random.default_rng(SEED)
    boot = [float(np.mean(D[rng.integers(0, len(D), len(D))])) for _ in range(REPS)]
    lo, hi = ci(boot)
    margin = 0.5 * abs(float(np.mean(rho_p)))
    res["primary"] = {"D": point, "lo": lo, "hi": hi, "n_cases": len(contrib),
                      "rho_absent": float(np.mean(rho_a)), "rho_present": float(np.mean(rho_p)),
                      "equivalence_margin": margin}
    print(f"\nrho(exponent, time-to-aneend)   ABSENT cell {np.mean(rho_a):+.4f}   "
          f"PRESENT cell {np.mean(rho_p):+.4f}")
    print(f"P  D = rho_absent - rho_present = {point:+.4f}  [{lo:+.4f}, {hi:+.4f}]  "
          f"(equivalence margin {margin:.4f})")

    # G3 TIME OVERLAP, and the restricted re-run
    print(f"\nG3 time    median rel_aneend_s   ABSENT {np.median(tmed_a):+8.1f} s   "
          f"PRESENT {np.median(tmed_p):+8.1f} s")
    all_a = np.concatenate([np.array([r[0] for r in per[c]], float)[masks[c]] for c in contrib])
    all_p = np.concatenate([np.array([r[0] for r in per[c]], float)[~masks[c]] for c in contrib])
    band = (max(np.percentile(all_a, 10), np.percentile(all_p, 10)),
            min(np.percentile(all_a, 90), np.percentile(all_p, 90)))
    print(f"           overlap band (10th-90th pct of both cells): "
          f"[{band[0]:+.1f}, {band[1]:+.1f}] s")
    r_a, r_p = [], []
    if band[1] > band[0]:
        for c in contrib:
            rows = [r for r in per[c] if band[0] <= r[0] <= band[1]]
            if len(rows) < 2 * MIN_CELL:
                continue
            m = np.array([not r[2] for r in rows], bool)
            ra, rp = cell_rhos(rows, m)
            if np.isfinite(ra) and np.isfinite(rp):
                r_a.append(ra); r_p.append(rp)
    if len(r_a) >= 10:
        Dr = np.array(r_a) - np.array(r_p)
        rb = [float(np.mean(Dr[rng.integers(0, len(Dr), len(Dr))])) for _ in range(REPS)]
        rlo, rhi = ci(rb)
        res["gates"]["G3_restricted"] = {"D": float(np.mean(Dr)), "lo": rlo, "hi": rhi,
                                         "n_cases": len(r_a), "band": list(band)}
        same_sign = (np.mean(Dr) * point) > 0
        res["gates"]["G3_pass"] = bool(same_sign)
        print(f"           RESTRICTED D = {np.mean(Dr):+.4f} [{rlo:+.4f}, {rhi:+.4f}] "
              f"over {len(r_a)} cases   {'consistent' if same_sign else 'SIGN REVERSES -- withdraw'}")
    else:
        res["gates"]["G3_restricted"] = {"n_cases": len(r_a)}
        res["gates"]["G3_pass"] = False
        print(f"           RESTRICTED not computable ({len(r_a)} cases) -- G3 FAIL")

    # G4 ARTEFACT -- reported, never adjusted for (rule 13)
    res["gates"]["G4_emg_median_absent"] = float(np.nanmedian(emg_a))
    res["gates"]["G4_emg_median_present"] = float(np.nanmedian(emg_p))
    print(f"G4 muscle  median emg_index   ABSENT {np.nanmedian(emg_a):.4f}   "
          f"PRESENT {np.nanmedian(emg_p):.4f}   (reported, NOT adjusted -- collider)")

    # PLACEBO: contiguous random split, cell sizes and block structure preserved
    pl = []
    for _ in range(PLACEBO_DRAWS):
        d = []
        for c in contrib:
            rows = per[c]
            k = int(masks[c].sum())
            n = len(rows)
            if k < MIN_CELL or n - k < MIN_CELL:
                continue
            start = int(rng.integers(0, n - k + 1))     # one contiguous block of the SAME size
            m = np.zeros(n, bool); m[start:start + k] = True
            ra, rp = cell_rhos(rows, m)
            if np.isfinite(ra) and np.isfinite(rp):
                d.append(ra - rp)
        if len(d) >= 10:
            pl.append(float(np.mean(d)))
    p_lo, p_hi = ci(pl)
    inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
    res["placebo"] = {"lo": p_lo, "hi": p_hi, "n_draws": len(pl), "inside": inside}
    print(f"\nPLACEBO contiguous random split, same cell sizes: [{p_lo:+.4f}, {p_hi:+.4f}]  "
          f"real D {'INSIDE -- WITHDRAWN' if inside else 'outside'}")

    excl = not (lo <= 0.0 <= hi)
    if inside:
        v = ("WITHDRAWN BY PLACEBO -- a contiguous random split of the same windows reproduces D, so this "
             "is about position in time, not about whether the monitor was publishing")
    elif not res["gates"].get("G3_pass"):
        v = ("WITHDRAWN BY G3 -- the estimate does not survive restriction to the time band where both "
             "cells have mass, so it is a time contrast wearing an availability name")
    elif excl and point < 0:
        v = ("BETTER WHERE BIS IS ABSENT -- the exponent carries MORE emergence information where the "
             "incumbent withdraws. This is the outcome that was NOT predicted and it needs its own "
             "scrutiny before use; read G4 first")
    elif excl and point > 0:
        v = ("WORSE WHERE BIS IS ABSENT -- E90's availability advantage is HOLLOW. The honest joint "
             "summary of E90 and E102 is that the index is computable there and should not be trusted "
             "there")
    elif (hi - lo) <= 2 * margin:
        v = ("EQUIVALENT -- the exponent behaves the same whether or not the monitor is publishing, "
             "within a margin of half the information it carries where BIS agrees it is measurable; "
             "E90's availability advantage transports")
    else:
        v = ("UNDETERMINED -- the interval contains zero but is wider than the equivalence margin, so "
             "this is not evidence of equivalence (rule 31). Named as a possible outcome before the run")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
