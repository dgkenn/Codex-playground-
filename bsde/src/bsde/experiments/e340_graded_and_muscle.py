#!/usr/bin/env python3
"""E340 -- E321's two live weaknesses: is the dissociation GRADED, and is it MUSCLE?

PRE-REGISTRATION. Committed before any statistic in it exists.

E321 found that complexity places REM with wake and drug-unresponsiveness with N3, while every delta
measure fails the drug check. Two things could deflate it and neither has been tested.

**WEAKNESS 1 -- IS IT GRADED, OR JUST A TWO-STATE CONTRAST?** A measure of cognitive-processing capacity
should order a graded behavioural ladder, not merely separate its endpoints. Krause carries an
intermediate: `S` (sedated) sits between `WA` (wake) and `U` (unresponsive) on the OAA/S scale. E320
reported a sedated number (+0.0138) but on a ratio statistic whose null was built from rearrangements of
its own terms, so it says nothing.

**WEAKNESS 2 -- IS IT MUSCLE?** Krause ships no EMG channel, and E322 showed on 141 scalp subjects that
the EEG-derived muscle proxies point OPPOSITE to real submental EMG in REM (`emg_index` +1.27 against
real EMG -0.33). So E321's `AvgGamma` -- the survivor of its delta adjustment -- is the most exposed
measure in the panel and cannot be checked where it was measured.

**Sleep-EDFx can check it, and by a route that does not condition on a mediator.** Adjusting a REM
measure for concurrent EMG is catalogue rule 13 -- atonia is part of what REM *is*, so EMG is
post-exposure and conditioning on it removes the effect along with any artefact (the error E253 made).
The clean test is **between subjects**: if a candidate's REM-versus-N3 change were muscle-driven, then
subjects with a larger drop in *real* submental EMG should show a larger change in the candidate.
Correlating the two per-subject differences conditions on nothing.

======================================================================================================
P1 -- THE GRADED LADDER (Krause, propofol arm, within patient)

Per patient, standardise each measure across that patient's own {WA, S, U} blocks, then test the ordered
contrast with a paired sign-flip null over patients:
    step A = z(WA) - z(S)      step B = z(S) - z(U)
A graded measure has **both steps non-zero and of the same sign**. A measure that only separates the
endpoints has one step at zero.

PREDICTION: **`NmlzCmplx` and `EffDim` show both steps same-signed and non-zero; the delta measures do
not.**
WRONG IF complexity is endpoint-only -- which would make it a detector of unresponsiveness rather than a
graded index of processing capacity, a materially weaker claim and one that must then be made.

P2 -- THE BETWEEN-SUBJECT MUSCLE TEST (Sleep-EDFx, 141 subjects, real submental EMG)

For each subject compute `d_cand = z(REM) - z(N3)` and `d_emg = EMG(REM) - EMG(N3)` (log-transformed;
catalogue rule 57 records that raw EMG amplitude carries a subject-specific gain and must not be used
raw). Correlate `d_cand` against `d_emg` across subjects, per candidate.

PREDICTION: **complexity analogues (`lempel_ziv`, `spectral_entropy`) show |rho| < 0.2 -- no muscle
link -- while the EEG-derived muscle proxies (`emg_index`, `emg_beta_gamma_fraction`) show |rho| >= 0.3.**
The proxies are the positive control: they SHOULD track real muscle if they measure anything muscular.
WRONG IF the proxies show no correlation with real EMG either -- in which case they measure neither
muscle nor cortex, this test has no working positive control, and it is NOT INTERPRETABLE (rule 57: a
positive control is an instrument and needs its own validation).

GATES.
  G1  Krause: >= 12 patients with all three of WA, S, U.
  G2  Sleep-EDFx: >= 100 subjects with REM, N3 and finite EMG in both.
  G3  P2's positive control must work (see WRONG IF above), else P2 is NOT INTERPRETABLE.
  G4  SMOKE: `--smoke` permutes the state labels within patient/subject for both parts and prints the
      counts, which must fall.

SCOPE. P1 is intracranial epilepsy-surgery patients with depositor features. P2 is scalp sleep with no
anaesthetic, so it speaks only to whether the REM half is muscle-driven -- it cannot address the drug
check, which is where E321's discriminating power lives.

    python -m bsde.experiments.e340_graded_and_muscle
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
KSKIP = {"label", "refTime", "patientID", "Subdural", "timeOfDay",
         "timeOfDay_envCorrTimeData", "timeOfDay_bandPowerTimeData",
         "pctGoodSamples", "pctGoodSamples_envCorrTimeData", "pctGoodSamples_bandPowerTimeData"}
SSKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def iqr(v):
    v = sorted(x for x in v if math.isfinite(x))
    return (v[int(0.75 * len(v))] - v[int(0.25 * len(v))]) if len(v) >= 4 else float("nan")


def midranks(vals):
    o = sorted(range(len(vals)), key=lambda i: vals[i]); r = [0.0] * len(vals); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and vals[o[j + 1]] == vals[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def pear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 5:
        return float("nan")
    n = len(q); mx = sum(t[0] for t in q) / n; my = sum(t[1] for t in q) / n
    sxy = sum((t[0] - mx) * (t[1] - my) for t in q)
    sxx = sum((t[0] - mx) ** 2 for t in q); syy = sum((t[1] - my) ** 2 for t in q)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spear(x, y):
    q = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(q) < 5:
        return float("nan")
    return pear(midranks([t[0] for t in q]), midranks([t[1] for t in q]))


def signflip(d, rng, reps):
    d = [x for x in d if math.isfinite(x)]
    if len(d) < 8:
        return float("nan"), float("nan"), len(d)
    obs = med(d)
    null = [med([x if rng.random() < 0.5 else -x for x in d]) for _ in range(reps)]
    return obs, sum(1 for v in null if abs(v) >= abs(obs)) / len(null), len(d)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=340)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e340_graded_and_muscle.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    # ---------------------------------------------------------------- P1
    print("=" * 96 + "\nP1 -- the graded ladder: wake > sedated > unresponsive (Krause, propofol)")
    rows = list(csv.DictReader(open(os.path.join(RESULTS, "krause_dexprosleep_allData.csv"))))
    kcols = [c for c in rows[0] if c not in KSKIP]
    by = {}
    for r in rows:
        by.setdefault((r["patientID"], r["label"]), []).append(r)
    LAD = ("WA", "S", "U")
    pats = sorted({p for p, l in by if l == "WA"} & {p for p, l in by if l == "S"}
                  & {p for p, l in by if l == "U"})
    print(f"  {len(pats)} patients with all of WA, S, U")
    G1 = len(pats) >= 12
    print(f"  [G1] >= 12 -> {'PASS' if G1 else 'FAIL'}")
    p1 = {}
    if G1:
        for c in kcols:
            dA, dB = [], []
            for p in pats:
                pool = [f(x.get(c)) for st in LAD for x in by[(p, st)]]
                m0, s0 = med(pool), iqr(pool)
                if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                    continue
                z = {st: (med([f(x.get(c)) for x in by[(p, st)]]) - m0) / s0 for st in LAD}
                if a.smoke:
                    ks = list(LAD); vs = [z[k] for k in ks]; rng.shuffle(vs); z = dict(zip(ks, vs))
                if all(math.isfinite(v) for v in z.values()):
                    dA.append(z["WA"] - z["S"]); dB.append(z["S"] - z["U"])
            oA, pA, nA = signflip(dA, rng, a.reps)
            oB, pB, nB = signflip(dB, rng, a.reps)
            graded = (math.isfinite(pA) and pA < 0.05 and math.isfinite(pB) and pB < 0.05
                      and oA * oB > 0)
            p1[c] = {"stepA": oA, "pA": pA, "stepB": oB, "pB": pB, "n": nA, "graded": graded}
        for c in sorted(p1, key=lambda k: -(abs(p1[k]["stepA"]) + abs(p1[k]["stepB"])
                                            if math.isfinite(p1[k]["stepA"]) else -9))[:10]:
            r_ = p1[c]
            print(f"  {c:24s} A(WA-S) {r_['stepA']:+7.4f} p={r_['pA']:.4f}   "
                  f"B(S-U) {r_['stepB']:+7.4f} p={r_['pB']:.4f}   "
                  f"{'GRADED' if r_['graded'] else ''}")
        gr = [c for c in p1 if p1[c]["graded"]]
        cx = [c for c in ("NmlzCmplx", "EffDim") if c in p1 and p1[c]["graded"]]
        dl = [c for c in p1 if c.lower().endswith("delta") or c == "AvgDelta"]
        dlg = [c for c in dl if p1[c]["graded"]]
        print(f"\n  GRADED: {gr}")
        print(f"  complexity graded: {cx}   |   delta measures graded: {dlg} of {len(dl)}")
        met1 = len(cx) == 2 and not dlg
        print(f"  PREDICTED both complexity graded AND no delta graded -> "
              f"{'MET' if met1 else 'NOT MET'}")
        R["P1"] = {"detail": p1, "graded": gr, "complexity_graded": cx,
                   "delta_graded": dlg, "prediction_met": met1, "n_patients": len(pats)}

    # ---------------------------------------------------------------- P2
    print("\n" + "=" * 96 + "\nP2 -- between-subject muscle test (Sleep-EDFx, real submental EMG)")
    srows = [r for r in csv.DictReader(open(os.path.join(RESULTS, "sleep_edfx_five_stage.csv")))
             if r.get("status") == "ok"]
    scols = [c for c in srows[0] if c not in SSKIP]
    val = {}
    for r in srows:
        rid = r["recording_id"]
        if "@" not in rid:
            continue
        s, st = rid.rsplit("@", 1)
        val[(s, st)] = {c: f(r.get(c)) for c in scols}
    emg = {}
    for r in csv.DictReader(open(os.path.join(RESULTS, "sleep_edfx_emg.csv"))):
        emg[(r["subject"], r.get("label"))] = f(r.get("emg_median"))
    STAGES = ("W", "N1", "N2", "N3", "REM")
    subs = [s for s in {x for x, _ in val}
            if all((s, st) in val for st in STAGES)
            and (s, "REM") in emg and (s, "N3") in emg
            and emg[(s, "REM")] > 0 and emg[(s, "N3")] > 0]
    print(f"  {len(subs)} subjects with all stages and finite positive EMG in REM and N3")
    G2 = len(subs) >= 100
    print(f"  [G2] >= 100 -> {'PASS' if G2 else 'FAIL'}")
    # rule 57: log-transform EMG; raw amplitude carries a subject-specific gain
    d_emg = {s: math.log(emg[(s, "REM")]) - math.log(emg[(s, "N3")]) for s in subs}
    if a.smoke:
        ks = list(d_emg); vs = [d_emg[k] for k in ks]; rng.shuffle(vs); d_emg = dict(zip(ks, vs))
    p2 = {}
    for c in scols:
        dc = {}
        for s in subs:
            pool = [val[(s, st)][c] for st in STAGES]
            m0, s0 = med(pool), iqr(pool)
            if math.isfinite(m0) and math.isfinite(s0) and s0 > 0:
                dc[s] = (val[(s, "REM")][c] - val[(s, "N3")][c]) / s0
        ks = [s for s in subs if s in dc]
        p2[c] = {"rho": spear([dc[s] for s in ks], [d_emg[s] for s in ks]), "n": len(ks)}
    PROXY = [c for c in ("emg_index", "emg_beta_gamma_fraction", "emg_kurtosis") if c in p2]
    CPLX = [c for c in ("lempel_ziv", "spectral_entropy", "multiscale_entropy_slope") if c in p2]
    for c in PROXY + CPLX:
        print(f"  {c:28s} rho(d_candidate, d_realEMG) = {p2[c]['rho']:+.4f}  n={p2[c]['n']}")
    ctrl_ok = any(math.isfinite(p2[c]["rho"]) and abs(p2[c]["rho"]) >= 0.30 for c in PROXY)
    print(f"  [G3] positive control -- a muscle proxy tracks real EMG at |rho| >= 0.30 -> "
          f"{'PASS' if ctrl_ok else 'FAIL'}")
    if not ctrl_ok:
        print("       NOT INTERPRETABLE: with no working positive control this test cannot "
              "distinguish 'not muscle' from 'no sensitivity' (rule 57).")
        met2 = None
    else:
        met2 = all(math.isfinite(p2[c]["rho"]) and abs(p2[c]["rho"]) < 0.20 for c in CPLX)
        print(f"  PREDICTED complexity |rho| < 0.20 with a working control -> "
              f"{'MET' if met2 else 'NOT MET'}")
    R["P2"] = {"detail": p2, "n_subjects": len(subs), "control_ok": ctrl_ok,
               "prediction_met": met2, "G2": G2}

    print("\n" + "=" * 96)
    print("SCOPE: P1 is intracranial epilepsy-surgery patients with depositor features. P2 is scalp "
          "sleep with NO anaesthetic, so it speaks only to whether the REM half is muscle-driven and "
          "cannot address the drug check, which is where E321's discriminating power lives.")
    if not a.smoke:
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
