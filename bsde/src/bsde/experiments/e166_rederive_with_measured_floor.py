"""E166 — re-derivation of the increment-decided ledger rows against a MEASURED DETECTION FLOOR.

REGISTERED BEFORE ANY RE-DERIVED NUMBER EXISTS. What has been read of the cohorts is only their loaders,
their column names and the sizes already printed in the ledger rows being re-derived.

---------------------------------------------------------------------------------------------------------
WHY THIS EXISTS

E146 measured what this project's increment estimator costs as a TEST: at n = 60 subjects and a partial
correlation of 0.35, the bootstrap tail fraction of `oob_regression_increment` detected in **0 %** of draws
where an ordinary partial-correlation test detected in 88 %. The bootstrap spread reflects
resample-to-resample variability, not the sampling distribution of the increment, so its interval is
conservative to the point of blindness. `permutation_increment` (E147) replaces the test and keeps the
point estimate.

Nine ledger rows were decided by the blind instrument. E150 re-derived one and the verdict MOVED (11 of 27
candidates added where none had). E133 and E134 were re-derived and did not move. E163 read those three
together and concluded:

    "movement is predicted by HEADROOM and POWER together, not by rows-per-cluster or by the instrument
     alone. The remaining seven rows should be triaged on their incumbent headroom and their measured
     floor before any are re-run."

**This file is that triage, and it makes the floor a measured quantity rather than a judgement.** The
argument for doing it is not that the verdicts are wrong; it is that a null returned by an instrument with
unquantified power is not a null at all (rule 31), and six of these rows are recorded as `negative`.

---------------------------------------------------------------------------------------------------------
THE MEASURED DETECTION FLOOR — what it is and why it is not a chosen threshold (rule 63)

For each row, after the real increment is computed, a SYNTHETIC column is injected whose partial
association with the outcome, given the baseline, is set to a known value `rho`, and the identical
`permutation_increment` machinery is run on it. Rungs are climbed until the machinery detects:

    rho = 0.00   CALIBRATION — must NOT be detected (this gate can fail; see GATE C)
    rho = 0.05, 0.10, 0.20, 0.40

Three independent draws per rung; a rung is DETECTED when >= 2 of 3 give p <= 0.05. The **floor** is the
smallest detected rung. It is not a threshold anyone picked: it is what this cohort, this clustering and
this baseline can actually resolve. It converts every null from "nothing found" into either "nothing above
rho = X" or "this row cannot see anything at all".

SCOPE LIMIT, STATED IN ADVANCE. The probe injects a ROW-LEVEL partial association. A candidate whose real
effect lives between clusters is harder to detect than the floor implies, so the floor is a LOWER bound on
the difficulty and an upper bound on the row's resolution. It is reported as such and never as a power
calculation for the original candidate.

---------------------------------------------------------------------------------------------------------
ROWS RE-DERIVED, AND THE ONE THAT IS NOT

Six of the seven are re-derived: **e26, e34, e37, e58, e99, E130**.

**e27 is NOT re-derived, deliberately.** Its recorded outcome is `absent`: two machinery gates failed
(coverage 17/25, then base rate 4.0 % against a 5 % floor) and no candidate was ever scored. There is no
increment verdict there to re-derive, and re-running it now would mean choosing a cohort or a horizon after
having seen which choice fails — the move `DISCOVERY_LOOP.md` §2 and error-catalogue rule 58 forbid. The
row stays `absent`.

---------------------------------------------------------------------------------------------------------
GATES

GATE R  REBUILD. Each cohort is rebuilt here and must reproduce the size its own ledger row records, to
        within 2 % on clusters and 5 % on rows. The reference numbers are transcribed from the ledger rows
        IN FULL below (rule 59 — a selective import is a silent cohort choice), not the subset that
        happens to be convenient. A row that fails GATE R emits NO VERDICT and is reported NOT REBUILT
        (rule 31), because a re-derivation on a different cohort is a different experiment.

GATE C  CALIBRATION, AND IT CAN FAIL. The rho = 0.00 rung must NOT be detected in >= 2 of 3 draws. If a
        pure-noise column is "detected", the permutation null is anti-conservative for that row and
        NOTHING is reported for it. This is the rule-40 check applied to the floor apparatus itself: the
        probe is constructed so that it CAN fail, and at rho = 0 it should.

GATE A  ALIVENESS OF THE BASELINE (rule 53 / E33). Each row's baseline model must itself predict the
        outcome out of fold — |stat| better than the outcome-permuted baseline. A row whose baseline is
        dead has nothing to add to and its increment is uninterpretable in either direction.

---------------------------------------------------------------------------------------------------------
VERDICT RULE PER ROW — THE WRONG-DIRECTION CASE IS ENUMERATED FIRST (rule 37)

All increments here are in the LOWER-IS-BETTER convention of `permutation_increment`: a NEGATIVE increment
means the addition helps. `p` is the fraction of cluster-permutation nulls at or below the observed value.

  (1) HURTS      observed > 0 and p >= 0.95. The addition significantly makes the model WORSE. This is a
                 finding with a direction, not a null, and must never be written up as one.
  (2) ADDS       observed < 0 and p <= 0.05. The recorded verdict is OVERTURNED.
  (3) ABSENT-    p is in (0.05, 0.95) AND GATE C passed AND the floor exists (some rung was detected).
      ABOVE-FLOOR   The recorded negative STANDS, and now carries a resolution: nothing above rho = floor.
  (4) NO POWER   p is in (0.05, 0.95) AND no rung up to rho = 0.40 was detected. The row is undecidable
                 with this cohort and this instrument. Its ledger outcome must be downgraded from
                 `negative` to `absent` — an unpowered null is not a negative (rule 31).

Note which way (4) cuts: it can only ever REMOVE a claim this project has made, never add one. The
asymmetry is deliberate.

---------------------------------------------------------------------------------------------------------
WHAT WOULD MAKE THIS FILE WRONG

If GATE C fails on several rows the apparatus is broken, not the rows. If every row returns NO POWER the
ladder is mis-specified (its lowest rung too high, or the injection not actually partial), and the correct
reading is that this file measured nothing — not that six results are void.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))

from bsde.verifier.stats import (auc, permutation_increment, screen_candidates,  # noqa: E402
                                 cluster_permute, spearman)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e166_rederive_measured_floor.json")
SEED = 20260801

RUNGS = (0.00, 0.05, 0.10, 0.20, 0.40)
DRAWS_PER_RUNG = 3
DETECT_AT = 2               # of DRAWS_PER_RUNG
ALPHA = 0.05
REPS_REAL = 500
REPS_PROBE = 300

# Reference sizes, transcribed IN FULL from the ledger rows being re-derived (rule 59). Every arm each row
# reported is listed, including arms this file does not re-derive, so that what was dropped is visible.
REFERENCE = {
    "e26@SR>0":  {"clusters": 81,  "rows": 597,    "note": "81 patients with an onset, base rate 26.1 %"},
    "e26@SR>=10": {"clusters": 33, "rows": 213,    "note": "33 patients with an onset, base rate 14.6 %"},
    "e34":       {"clusters": 129, "rows": None,   "note": "129 recordings (size quoted in e37's row)"},
    "e37":       {"clusters": 70,  "rows": 38684,  "note": "70 recordings, base rate 21.7 %"},
    "e58":       {"clusters": 247, "rows": 5845,   "note": "5,845 windows / 247 cases, joined at 100 %"},
    "e99":       {"clusters": 247, "rows": 5798,   "note": "5,798 windows, 977 positive (16.9 %)"},
    "E130":      {"clusters": 20,  "rows": 78,     "note": "20 subjects, 78 rows"},
}

RECORDED = {   # what each row's blind instrument returned, for side-by-side reading
    "e26@SR>0":   "-0.0021 [-0.1069, +0.0431]  (AUC increment, POSITIVE = adds)",
    "e26@SR>=10": "-0.0387 [-0.3057, +0.1656]  (AUC increment, POSITIVE = adds)",
    "e34":        "+0.0178 [-0.0226, +0.0474]  (AUC increment, POSITIVE = adds)",
    "e37":        "P3b not met (AUC increment, POSITIVE = adds)",
    "e58":        "-0.195 [-0.424, +0.035] BIS units (median|err|, NEGATIVE = better)",
    "e99":        "-0.0306 [-0.0524, -0.0101] (AUC increment, POSITIVE = adds) -> HURTS",
    "E130":       "all 17 span zero; largest exponent_high -0.2054 [-0.4693, +0.1315] (1-rho, NEG = helps)",
}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def neg_auc(t, p):
    """LOWER IS BETTER, so a negative increment means the addition helps -- the same sign convention as
    `permutation_increment`'s default, kept so the two are never read with opposite signs (rule 37)."""
    a = auc(np.asarray(t, int), np.asarray(p, float))
    return -a if np.isfinite(a) else float("nan")


def med_abs_err(t, p):
    return float(np.median(np.abs(np.asarray(t, float) - np.asarray(p, float))))


# --------------------------------------------------------------------------------------------------- floor
def _partial_synthetic(Xa, y, rho, rng):
    """A column with a KNOWN partial association `rho` with `y` given `Xa`.

    Built from the OLS residual of y on Xa so the injected signal is genuinely the part of y the baseline
    does not already carry -- injecting against raw y would credit the probe for information the baseline
    already has and would understate the floor.
    """
    A = np.column_stack([np.ones(len(y)), np.nan_to_num(Xa, nan=0.0)])
    yy = np.asarray(y, float)
    coef, *_ = np.linalg.lstsq(A, yy, rcond=None)
    r = yy - A @ coef
    sd = r.std()
    u = r / sd if sd > 1e-12 else rng.normal(size=len(yy))
    u = (u - u.mean()) / (u.std() if u.std() > 1e-12 else 1.0)
    e = rng.normal(size=len(yy))
    return rho * u + np.sqrt(max(0.0, 1.0 - rho ** 2)) * e


def measure_floor(Xa, y, subject, stat, seed):
    """Climb the rungs. Returns (floor_or_None, per_rung_detail, calibration_passed)."""
    detail, floor = [], None
    for rho in RUNGS:
        ps = []
        for d in range(DRAWS_PER_RUNG):
            rng = np.random.default_rng(seed + 1000 * int(rho * 100) + d)
            z = _partial_synthetic(Xa, y, rho, rng)
            Xb = np.column_stack([Xa, z])
            _, p, _, n = permutation_increment(Xa, Xb, y, subject,
                                               np.random.default_rng(seed + 7717 + d),
                                               stat=stat, reps=REPS_PROBE)
            ps.append(float(p) if np.isfinite(p) else float("nan"))
        hits = sum(1 for p in ps if np.isfinite(p) and p <= ALPHA)
        det = hits >= DETECT_AT
        detail.append({"rho": rho, "p": ps, "hits": hits, "detected": bool(det)})
        print(f"      rho={rho:.2f}  p = " + ", ".join("nan" if not np.isfinite(p) else f"{p:.4f}"
                                                       for p in ps)
              + f"   {hits}/{DRAWS_PER_RUNG} " + ("DETECTED" if det else "not detected"))
        if rho == 0.0:
            calib = not det
            if det:
                return None, detail, False
            continue
        if det and floor is None:
            floor = rho
            break
    return floor, detail, True


def baseline_alive(Xa, y, subject, stat, seed, reps=200):
    """GATE A: does the baseline itself beat an outcome-permuted version of itself, out of fold?

    Implemented as a permutation_increment of {Xa} over {intercept-only}, which reuses the same cross-fit
    and the same null machinery rather than a second, differently-calibrated test.
    """
    n = len(y)
    X0 = np.zeros((n, 1))
    Xb = np.column_stack([X0, Xa])
    obs, p, nm, k = permutation_increment(X0, Xb, y, subject, np.random.default_rng(seed + 31),
                                          stat=stat, reps=reps, n_extra=Xa.shape[1])
    return {"increment": float(obs), "p": float(p), "null_mean": float(nm), "n_null": int(k),
            "pass": bool(np.isfinite(p) and p <= ALPHA)}


def verdict_for(obs, p, floor, calib_ok):
    """Wrong-direction case FIRST (rule 37). Never returns a null when the test had no power (rule 31)."""
    if not calib_ok:
        return "APPARATUS-FAILED", "the rho = 0 rung was detected; the null is anti-conservative here"
    if not (np.isfinite(obs) and np.isfinite(p)):
        return "NOT-COMPUTABLE", "the increment or its null could not be formed"
    if obs > 0 and p >= 1.0 - ALPHA:
        return "HURTS", "the addition significantly worsens the model; this is a direction, not a null"
    if obs < 0 and p <= ALPHA:
        return "ADDS", "the recorded verdict is OVERTURNED"
    if floor is None:
        return "NO-POWER", (f"no injected partial effect up to rho = {max(RUNGS):.2f} is detectable in "
                            "this cohort; the recorded negative must be downgraded to absent")
    return "ABSENT-ABOVE-FLOOR", f"the recorded negative stands, with nothing above rho = {floor:.2f}"


def run_row(name, Xa, Xb, y, subject, stat, n_extra=1, seed=SEED):
    ref = REFERENCE[name]
    clusters = len(set(np.asarray(subject).tolist()))
    rows = len(y)
    ok_c = abs(clusters - ref["clusters"]) <= max(1, 0.02 * ref["clusters"])
    ok_r = ref["rows"] is None or abs(rows - ref["rows"]) <= 0.05 * ref["rows"]
    print(f"\n{'=' * 100}\n{name}")
    print(f"   recorded: {RECORDED[name]}")
    print(f"   GATE R rebuild: {rows} rows / {clusters} clusters  vs recorded "
          f"{ref['rows']} / {ref['clusters']}   ({ref['note']})   "
          f"{'PASS' if (ok_c and ok_r) else '*** FAIL'}")
    out = {"name": name, "n_rows": rows, "n_clusters": clusters, "reference": ref,
           "recorded": RECORDED[name], "gate_R": bool(ok_c and ok_r)}
    if not (ok_c and ok_r):
        out["verdict"] = "NOT-REBUILT"
        print("   NOT REBUILT — no verdict is emitted for this row (rule 31).")
        return out

    alive = baseline_alive(Xa, y, subject, stat, seed)
    out["gate_A"] = alive
    print(f"   GATE A baseline alive: increment {alive['increment']:+.4f}, p = {alive['p']:.4f}   "
          f"{'PASS' if alive['pass'] else '*** FAIL'}")

    obs, p, null_mean, n_null = permutation_increment(Xa, Xb, y, subject,
                                                      np.random.default_rng(seed + 5),
                                                      stat=stat, reps=REPS_REAL, n_extra=n_extra)
    print(f"   increment {obs:+.5f}   p = {p:.4f}   (null mean {null_mean:+.5f}, {n_null} draws)")
    print("   detection floor ladder:")
    floor, ladder, calib = measure_floor(Xa, y, subject, stat, seed)
    v, why = verdict_for(obs, p, floor, calib)
    if not alive["pass"]:
        v, why = "BASELINE-DEAD", "GATE A failed: there was nothing to add to (rule 53)"
    out.update({"increment": float(obs), "p": float(p), "null_mean": float(null_mean),
                "n_null": int(n_null), "floor": floor, "ladder": ladder,
                "calibration_pass": bool(calib), "verdict": v, "why": why})
    print(f"   FLOOR: {'none up to %.2f' % max(RUNGS) if floor is None else '%.2f' % floor}")
    print(f"   VERDICT {v} — {why}")
    return out


# ------------------------------------------------------------------------------------------ cohort builds
def build_e26(thr):
    from bsde.experiments.e26_challenge_c_suppression_onset import _onsets, EMG_MAX, HORIZON_S
    path = os.path.join(RESULTS, "vitaldb_grid.csv")
    rows = [r for r in csv.DictReader(open(path, newline="")) if r.get("status") == "ok"]
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    subj = np.array([r.get("subject", "") for r in rows])
    t_s, bis, sr, emg = col("meta_t_s"), col("meta_bis"), col("meta_sr"), col("meta_emg")
    off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    live = ~off & np.isfinite(sr) & np.isfinite(bis) & np.isfinite(emg) & np.isfinite(t_s)
    base_mask = live & (emg <= EMG_MAX)
    onset, elig = _onsets(subj, t_s, sr, base_mask, thr)
    ttl = np.full(len(rows), np.nan)
    for i in np.flatnonzero(elig):
        ttl[i] = onset[subj[i]] - t_s[i]
    y = (ttl <= HORIZON_S).astype(float)
    x = col("exponent_high")
    m = elig & np.isfinite(x) & np.isfinite(bis)
    return (bis[m].reshape(-1, 1), np.column_stack([bis[m], x[m]]), y[m], subj[m])


def build_e99():
    path = os.path.join(RESULTS, "vitaldb_grid.csv")
    rows = list(csv.DictReader(open(path, newline="")))
    bis = np.array([_f(r["meta_bis"]) for r in rows])
    sr = np.array([_f(r["meta_sr"]) for r in rows])
    x = np.array([_f(r.get("whole_head_exponent", "")) for r in rows])
    subj = np.array([r["subject"] for r in rows])
    m = np.isfinite(bis) & np.isfinite(sr) & np.isfinite(x)
    y = (sr[m] > 0).astype(float)
    return bis[m].reshape(-1, 1), np.column_stack([bis[m], x[m]]), y, subj[m]


def build_e58():
    """Arm A (ours) versus arm C (ours + the four BIS subparameters), the registered primary comparison."""
    from bsde.experiments.e58_bis_like_index import SUBPARAMS
    g = {r["recording_id"]: r for r in csv.DictReader(open(os.path.join(RESULTS, "vitaldb_grid.csv"),
                                                          newline=""))}
    b = {r["recording_id"]: r for r in csv.DictReader(open(os.path.join(RESULTS, "vitaldb_bis.csv"),
                                                          newline=""))}
    keys = ("recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples")
    gf = list(next(iter(g.values())).keys())
    ours = [c for c in gf if c not in keys and not c.startswith("meta_") and c not in SUBPARAMS]
    ids = [k for k in g if k in b]
    cand = {c: [_f(g[k].get(c, "")) for k in ids] for c in ours}
    usable, dropped = screen_candidates(cand)
    for c, why in dropped.items():
        print(f"      dropped from arm A: {c} ({why})")
    ours = [c for c in ours if c in usable]
    y = np.array([_f(g[k]["meta_bis"]) for k in ids], float)
    subj = np.array([g[k]["subject"] for k in ids])
    XA = np.array([[_f(g[k].get(c, "")) for c in ours] for k in ids], float)
    XS = np.array([[_f(b[k].get(c, "")) for c in SUBPARAMS] for k in ids], float)
    m = np.isfinite(y) & np.all(np.isfinite(XA), axis=1) & np.all(np.isfinite(XS), axis=1)
    return XA[m], np.column_stack([XA[m], XS[m]]), y[m], subj[m], len(SUBPARAMS)


def build_e130():
    path = os.path.join(RESULTS, "chennu_features_v3.csv")
    rows = list(csv.DictReader(open(path, newline="")))
    plasma = np.array([_f(r.get("meta_plasma_propofol_ug_per_L", "")) for r in rows])
    rt = np.array([_f(r.get("meta_mean_reaction_time_ms", "")) for r in rows])
    subj = np.array([r.get("subject", "") for r in rows])
    x = np.array([_f(r.get("exponent_high", "")) for r in rows])
    m = np.isfinite(plasma) & np.isfinite(rt) & np.isfinite(x)
    return plasma[m].reshape(-1, 1), np.column_stack([plasma[m], x[m]]), rt[m], subj[m]


def build_dosei(which):
    zp = os.path.join(RESULTS, "dosei_pEEG.zip")
    if which == "e34":
        from bsde.experiments.e34_challenge_c_dosei_allwindows import _load, _stack, PRIMARY, INCUMBENT
        recs = _load(zp)
        xi, y, grp, _ = _stack(recs, INCUMBENT)
        xp, _, _, _ = _stack(recs, PRIMARY)
    else:
        from bsde.experiments.e37_challenge_c_critical_slowing import _load, _stack, PRIMARY, INCUMBENT
        recs, _ = _load(zp)
        xi, y, grp = _stack(recs, INCUMBENT)
        xp, _, _ = _stack(recs, PRIMARY)
    m = np.isfinite(xi) & np.isfinite(xp) & np.isfinite(y)
    return xi[m].reshape(-1, 1), np.column_stack([xi[m], xp[m]]), y[m], grp[m]


def main() -> int:
    print("E166 — re-derivation of the increment-decided rows against a MEASURED detection floor")
    print(f"   rungs {RUNGS}, {DRAWS_PER_RUNG} draws each, detected at {DETECT_AT}/{DRAWS_PER_RUNG}, "
          f"alpha {ALPHA}")
    print("   e27 is NOT re-derived: its outcome is `absent` (two gates failed, no candidate scored).")
    res = {"experiment": "E166", "rungs": list(RUNGS), "alpha": ALPHA,
           "not_rederived": {"e27": "outcome `absent`; gates failed before any candidate was scored, so "
                                    "there is no increment verdict to re-derive, and re-choosing the "
                                    "cohort now would be goalpost-moving (rule 58)"},
           "rows": {}}

    jobs = []
    for thr, nm in ((0.0, "e26@SR>0"), (10.0, "e26@SR>=10")):
        try:
            Xa, Xb, y, s = build_e26(thr)
            jobs.append((nm, Xa, Xb, y, s, neg_auc, 1))
        except Exception as exc:                                              # noqa: BLE001
            res["rows"][nm] = {"verdict": "NOT-BUILT", "error": str(exc)}
    for nm in ("e34", "e37"):
        try:
            Xa, Xb, y, s = build_dosei(nm)
            jobs.append((nm, Xa, Xb, y, s, neg_auc, 1))
        except Exception as exc:                                              # noqa: BLE001
            res["rows"][nm] = {"verdict": "NOT-BUILT", "error": str(exc)}
    try:
        Xa, Xb, y, s, ne = build_e58()
        jobs.append(("e58", Xa, Xb, y, s, med_abs_err, ne))
    except Exception as exc:                                                  # noqa: BLE001
        res["rows"]["e58"] = {"verdict": "NOT-BUILT", "error": str(exc)}
    try:
        Xa, Xb, y, s = build_e99()
        jobs.append(("e99", Xa, Xb, y, s, neg_auc, 1))
    except Exception as exc:                                                  # noqa: BLE001
        res["rows"]["e99"] = {"verdict": "NOT-BUILT", "error": str(exc)}
    try:
        Xa, Xb, y, s = build_e130()
        jobs.append(("E130", Xa, Xb, y, s, None, 1))
    except Exception as exc:                                                  # noqa: BLE001
        res["rows"]["E130"] = {"verdict": "NOT-BUILT", "error": str(exc)}

    for nm, Xa, Xb, y, s, stat, ne in jobs:
        res["rows"][nm] = run_row(nm, Xa, Xb, y, s, stat, n_extra=ne)
        json.dump(res, open(OUT, "w"), indent=2)

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"{'row':<14s} {'rows':>7s} {'clus':>5s} {'increment':>11s} {'p':>8s} {'floor':>7s}  verdict")
    for nm, r in res["rows"].items():
        if "increment" not in r:
            print(f"{nm:<14s} {'-':>7s} {'-':>5s} {'-':>11s} {'-':>8s} {'-':>7s}  {r.get('verdict')}")
            continue
        fl = "none" if r["floor"] is None else f"{r['floor']:.2f}"
        print(f"{nm:<14s} {r['n_rows']:>7d} {r['n_clusters']:>5d} {r['increment']:>+11.5f} "
              f"{r['p']:>8.4f} {fl:>7s}  {r['verdict']}")
    downgrade = [n for n, r in res["rows"].items() if r.get("verdict") == "NO-POWER"]
    overturn = [n for n, r in res["rows"].items() if r.get("verdict") == "ADDS"]
    hurts = [n for n, r in res["rows"].items() if r.get("verdict") == "HURTS"]
    res["downgrade_to_absent"], res["overturned"], res["wrong_direction"] = downgrade, overturn, hurts
    print(f"\n   OVERTURNED (now ADDS)          : {overturn or 'none'}")
    print(f"   WRONG DIRECTION (HURTS)        : {hurts or 'none'}")
    print(f"   DOWNGRADE negative -> absent   : {downgrade or 'none'}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
