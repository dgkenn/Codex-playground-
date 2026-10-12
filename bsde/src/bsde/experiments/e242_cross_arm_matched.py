#!/usr/bin/env python3
"""E242 -- the E241 question, with the arms matched ACROSS cases instead of restricted within them.

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E241. One instrument change: how the cohort is equalised. The statistic, the donor null,
the capability controls and the G1 bar are E241's verbatim -- in particular G1 still requires the
prominence gap to HALVE, unchanged, so this is not a threshold being relaxed after a failure.

WHY E241 FAILED, AND IT IS ARITHMETIC RATHER THAN DATA. E241 restricted each case to its own top 19
windows by prominence. That lifts BOTH arms by about the same amount -- propofol 1.7176 -> 1.8981,
sevoflurane 1.9408 -> 2.1358 -- so the between-arm gap went from +0.2231 to +0.2377 rather than
closing. **A within-case relative selection cannot equalise a between-arm difference.** The gate caught
it; the design should not have needed the gate to.

WHAT THIS DOES INSTEAD. Each propofol case is matched to a sevoflurane case of similar MEDIAN
PROMINENCE under a caliper, without replacement, and unmatched cases are DISCARDED. This is E230/E231's
design pointed at prominence rather than demographics, and E231 established both the machinery and its
failure mode: a match that discards nobody cannot equalise anything, and a placebo that only re-pairs
the same cases cannot test a between-arm statistic (rule 88). The caliper is DERIVED, not chosen
(rule 63): the median nearest-neighbour distance in median prominence WITHIN the propofol arm, i.e. a
cross-arm pair is admitted only if the two cases are as similar as two propofol cases typically are.
Feasible because the arms overlap substantially -- IQRs [1.5649, 1.9272] against [1.7583, 2.1259].

ORIGINAL E241 QUESTION, unchanged: does propofol's peak-shift null survive at matched peak prominence?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E233 by a cohort restriction; the statistic, gates and donor null are E233's A1 arm.

WHAT IS BROKEN. E233's one novel Challenge A finding was an ASYMMETRY: sevoflurane's alpha peak slides
downward as dose rises (mean signed within-case rho -0.3296, consistency 0.8204 against a donor null of
0.2770) while propofol's does not move at all (-0.0226, consistency 0.0970 against 0.3163 -- failing).
The sevoflurane half is already published (Hayashi 2008, PMID 18431119: 11.0 -> 9.8 -> 8.7 Hz across
1-3 % sevoflurane). The asymmetry was the novel part.

**It is currently uninterpretable, and three separate defences of it have failed.** E237 measured that
the shipped estimator returns a finite "peak" on signal-free 1/f background in 91.5 % of draws, so peak
AVAILABILITY carries no information. The VitalDB prominence recompute then measured the thing that does:
per-case median prominence is **1.7176 in the propofol arm against 1.9457 in sevoflurane, difference
+0.2281, arm-permutation |p| < 0.0001**. Propofol windows have systematically WEAKER peaks. So "the peak
does not move under propofol" and "there is less peak to follow under propofol" are confounded, and the
measured difference points at the second.

THE ONE TEST THAT CAN SEPARATE THEM. Restrict each case to its OWN most prominent windows. This is a
WITHIN-CASE relative criterion, so it inherits nothing from E239's k = 3.5 -- that threshold was
calibrated on 30 s / 128 Hz synthetic windows and E239 explicitly scoped that it need not transfer, and
indeed only 4.04 % of VitalDB windows clear it against 14-41 % on Sleep-EDFx. Taking the top N windows
per case instead makes every case contribute its best evidence, on its own scale, with no threshold
crossing a signal class.

If propofol's peak still fails to track its exposure among the windows where propofol's own alpha is
strongest, the null means what E233 read it as meaning and the asymmetry is restored. If the null
dissolves -- if propofol's peak DOES track dose once weak windows are removed -- then E233's asymmetry
was an artefact of measuring a weaker signal, and it must be withdrawn rather than merely doubted.

PRIMARIES, all on the restricted cohort.

  P1  Propofol: consistency of within-case Spearman(alpha_peak_hz_wide, propofol Ce), against a
      donor-exposure null computed on the SAME restricted windows. Registered prediction under the
      "artefact" reading: it now clears its null. Under the "real asymmetry" reading: it still fails.
  P2  Sevoflurane: the same, as the positive control. It must still clear -- a restriction that kills
      the known effect has removed signal rather than noise, and nothing is readable (rule 53).
  P3  The direction contrast, mean signed rho propofol minus sevoflurane, cluster-bootstrapped over
      cases, with an ARM-LABEL permutation placebo (rule 88 -- a covariate placebo cannot touch a
      between-arm estimand, which is how E230 and E231 both died).

GATES, each able to go either way (rules 40 and 81).

  G1  PROMINENCE MUST ACTUALLY BE MATCHED AFTER RESTRICTION. This is the whole point of the design and
      it is the gate that can most easily sink it. The arms' per-case median prominence is recomputed on
      the restricted windows and the difference re-tested by arm permutation. The gate is that the
      difference SHRINKS by at least half relative to the unrestricted +0.2281; if it does not, the
      restriction has not removed the confound and P1 is no more interpretable than E233's was. The
      residual difference is printed either way, because a partial match is a partial answer and must be
      readable as one.
  G2  COVERAGE. At least 10 windows per case after restriction and at least 20 cases per arm, the same
      floors E224 through E233 used. N is chosen as the largest value that keeps both arms above those
      floors, derived from the window counts rather than picked (rule 63).
  G3  THE RESTRICTION MUST NOT MANUFACTURE OR DESTROY AN EFFECT. A synthetic control: a feature built to
      track the exposure exactly must still do so after restriction, and one built as pure noise must
      still not. Restriction changes n and therefore the variance of every estimate, and a design that
      cannot show its own selection is neutral cannot interpret what selection reveals.
  G4  THE RESTRICTION MUST BITE. Median prominence among the retained windows must exceed that among the
      discarded ones by a margin larger than the arms differ by; otherwise "most prominent" is a label
      rather than a selection.

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37, five recorded occurrences of getting this
wrong in this project).

  (a) Propofol's peak now tracks its exposure with the OPPOSITE sign to sevoflurane's -> WRONG DIRECTION,
      reported with the sign. That is a different finding from either reading and must not be folded
      into "the asymmetry is real".
  (b) Propofol CLEARS its donor null at matched prominence -> ARTEFACT. E233's asymmetry was a
      consequence of the propofol arm having weaker peaks, and the last novel Challenge A finding is
      withdrawn. Challenge A retains only the already-published sevoflurane half.
  (c) Propofol still FAILS its donor null while sevoflurane clears, AND G1 shows prominence matched ->
      ASYMMETRY RESTORED. The null survives the specific confound that was raised against it, and the
      finding returns with that confound addressed by measurement rather than by argument.
  (d) Both arms fail after restriction -> NOT INTERPRETABLE; the restriction removed the signal (G2/G3
      should catch this first, and if they do not, that is itself worth knowing).

  Gating, applied AFTER the primaries because a gate can only invalidate a pass and never rescue a null
  (rule 37): G1 failing -> NOT INTERPRETABLE, the confound is still present. G3 or G4 failing -> NOT
  INTERPRETABLE.

SCOPE. Single frontal channel under a BIS sensor; the arms are mutually exclusive by the rule-87
predicate (a track counts only if it is ever nonzero). This tests whether the asymmetry survives a
prominence confound, not whether it survives the patient-level confounds E228-E231 could not remove --
no public deposit gives one subject both agents with EEG throughout, which was established by a full
sweep of OpenNeuro, PhysioNet, Zenodo, Dryad, Figshare and OSF.

INCUMBENT (rule 45): E233's own unrestricted result on the identical cases -- propofol consistency
0.0970 against a null of 0.3163, sevoflurane 0.8204 against 0.2770 -- re-derived here, not imported
(rule 59).

    python bsde/src/bsde/experiments/e242_cross_arm_matched.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

PROM = "bsde/results/vitaldb_prominence.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e242_cross_arm_matched.json"
PEAK = "alpha_peak_hz_wide"
MIN_WINDOWS = 10
MIN_CASES = 20
N_DONOR = 300
N_PERM = 2000
N_BOOT = 2000
UNRESTRICTED_GAP = 0.2281
SEED = 20260802


def _num(r, f):
    try:
        return float(r[f])
    except (TypeError, ValueError, KeyError):
        return float("nan")


def _hold(track, t_eval):
    import numpy as np
    t = np.asarray(track["t"], float)
    v = np.asarray(track["v"], float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v = t[ok], v[ok]
    if t.size == 0:
        return np.full(len(t_eval), np.nan)
    o = np.argsort(t)
    t, v = t[o], v[o]
    i = np.searchsorted(t, np.asarray(t_eval, float), side="right") - 1
    return np.where(i >= 0, v[np.clip(i, 0, len(v) - 1)], np.nan)


def _live(tr, key):
    import numpy as np
    if key not in tr:
        return False
    v = np.asarray(tr[key]["v"], float)
    return bool(np.isfinite(v).any() and np.nanmax(v) > 0)


def _rho(x, e):
    import numpy as np
    from bsde.verifier.stats import spearman
    m = np.isfinite(x) & np.isfinite(e)
    if m.sum() < MIN_WINDOWS or np.std(x[m]) <= 0 or np.std(e[m]) <= 0:
        return float("nan")
    return float(spearman(x[m], e[m]))


def consistency(vals):
    """Resultant length |mean signed| / mean|.| -- E227's statistic, unchanged."""
    import numpy as np
    v = np.asarray([x for x in vals if np.isfinite(x)], float)
    if len(v) < MIN_CASES:
        return float("nan"), float("nan")
    S = float(np.mean(np.abs(v)))
    return (float(abs(np.mean(v)) / S) if S > 0 else float("nan")), float(np.mean(v))


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows
    rng = np.random.default_rng(SEED)

    by = {}
    for p in sorted(glob.glob(PROM)):
        r, _ = read_rows(p)
        for row in r:
            by.setdefault(row["meta_caseid"], []).append(row)
    for c in by:
        by[c].sort(key=lambda r: _num(r, "meta_t_s"))
    tracks = {}
    for s in range(4):
        for line in open(PK % s):
            rr = json.loads(line)
            tracks[rr["caseid"]] = rr
    print(f"prominence table: {sum(len(v) for v in by.values())} windows over {len(by)} cases")

    arms = {"propofol": [], "sevoflurane": []}
    for c in by:
        tr = tracks[c]["tracks"]
        hp, hs, hd = (_live(tr, "Orchestra/PPF20_CE"), _live(tr, "Primus/EXP_SEVO"),
                      _live(tr, "Primus/EXP_DES"))
        if hp and (hs or hd):
            continue
        if hp:
            arms["propofol"].append(c)
        elif hs:
            arms["sevoflurane"].append(c)
    key = {"propofol": "Orchestra/PPF20_CE", "sevoflurane": "Primus/EXP_SEVO"}

    # ---- G2: N derived from the window counts, not chosen (rule 63) ---------------------------------
    counts = []
    for a in arms:
        for c in arms[a]:
            v = [r for r in by[c] if np.isfinite(_num(r, PEAK)) and np.isfinite(_num(r, "prominence"))]
            if len(v) >= MIN_WINDOWS:
                counts.append(len(v))
    counts = np.asarray(counts, float)
    N = 0   # no within-case restriction in this design; equalisation is across arms
    print(f"usable windows per case: median {np.median(counts):.0f}, "
          f"25th pct {np.percentile(counts, 25):.0f} (all retained; matching is across arms)")

    def build(keep_cases=None):
        """Per-case peak/exposure series. `keep_cases` restricts to a matched subset; None keeps all."""
        out = {}
        for a in arms:
            per, promed = {}, {}
            for c in arms[a]:
                if keep_cases is not None and c not in keep_cases:
                    continue
                rows = [r for r in by[c]
                        if np.isfinite(_num(r, PEAK)) and np.isfinite(_num(r, "prominence"))]
                if len(rows) < MIN_WINDOWS:
                    continue
                te = [_num(r, "meta_t_s") for r in rows]
                e = _hold(tracks[c]["tracks"][key[a]], te)
                if np.isfinite(e).sum() < MIN_WINDOWS or np.nanstd(e) <= 0:
                    continue
                per[c] = (np.asarray([_num(r, PEAK) for r in rows], float), e, rows)
                promed[c] = float(np.median([_num(r, "prominence") for r in rows]))
            out[a] = (per, promed)
        return out

    unres = build(None)
    # ---- cross-arm caliper match on median prominence -------------------------------------------------
    from scipy.optimize import linear_sum_assignment
    pm, sm = unres["propofol"][1], unres["sevoflurane"][1]
    pcs, scs = sorted(pm), sorted(sm)
    pv = np.asarray([pm[c] for c in pcs], float)
    sv = np.asarray([sm[c] for c in scs], float)
    nn = [float(np.min(np.abs(np.delete(pv, i) - pv[i]))) for i in range(len(pv))]
    caliper = float(np.median(nn))
    BIG = 1e6
    C = np.full((len(pcs), len(scs)), BIG)
    for i in range(len(pcs)):
        for j in range(len(scs)):
            d = abs(pv[i] - sv[j])
            if d <= caliper:
                C[i, j] = d
    ri, ci = linear_sum_assignment(C)
    pairs = [(pcs[i], scs[j]) for i, j in zip(ri, ci) if C[i, j] < BIG]
    keep = {p for p, _ in pairs} | {q for _, q in pairs}
    print(f"derived caliper (median within-propofol nearest-neighbour distance in median prominence) "
          f"= {caliper:.4f}")
    print(f"matched pairs: {len(pairs)}; propofol cases discarded {len(pcs) - len(pairs)}, "
          f"sevoflurane discarded {len(scs) - len(pairs)}")
    res = build(keep)
    print(f"cases: unrestricted {{'propofol': {len(unres['propofol'][0])}, "
          f"'sevoflurane': {len(unres['sevoflurane'][0])}}}; "
          f"restricted {{'propofol': {len(res['propofol'][0])}, "
          f"'sevoflurane': {len(res['sevoflurane'][0])}}}")
    g2 = all(len(res[a][0]) >= MIN_CASES for a in arms)
    print(f"G2 coverage: {'PASS' if g2 else 'FAIL'}")

    # ---- G1: is prominence matched after restriction? ------------------------------------------------
    def gap(state):
        a = np.asarray(list(state["propofol"][1].values()), float)
        b = np.asarray(list(state["sevoflurane"][1].values()), float)
        obs = float(np.median(b) - np.median(a))
        allv = np.concatenate([a, b])
        null = np.asarray([float(np.median(allv[i[:len(b)]]) - np.median(allv[i[len(b):]]))
                           for i in (rng.permutation(len(allv)) for _ in range(N_PERM))])
        return obs, float(np.mean(np.abs(null) >= abs(obs))), float(np.median(a)), float(np.median(b))

    g_un, p_un, ma_un, mb_un = gap(unres)
    g_re, p_re, ma_re, mb_re = gap(res)
    g1 = abs(g_re) <= abs(g_un) / 2.0
    print()
    print(f"G1 prominence gap (sevoflurane minus propofol, per-case medians):")
    print(f"     unrestricted  propofol {ma_un:.4f}  sevoflurane {mb_un:.4f}  gap {g_un:+.4f}  |p| {p_un:.4f}")
    print(f"     restricted    propofol {ma_re:.4f}  sevoflurane {mb_re:.4f}  gap {g_re:+.4f}  |p| {p_re:.4f}")
    print(f"     -> gap must halve from {UNRESTRICTED_GAP:+.4f}: {'PASS' if g1 else 'FAIL'}")

    # ---- G4: the match must DISCARD someone, or it equalises nothing (E231's lesson, rule 88) --------
    discarded = (len(pcs) - len(pairs)) + (len(scs) - len(pairs))
    g4 = discarded > 0
    print(f"G4 the match discards cases: {discarded} of {len(pcs) + len(scs)} "
          f"-> {'PASS' if g4 else 'FAIL'}  (E230's match discarded none and its placebo could not bite)")

    # ---- G3: synthetic controls under the same restriction --------------------------------------------
    cap = {}
    for name in ("tracks_exposure", "pure_noise"):
        vals = []
        for c, (pk, e, rows) in res["propofol"][0].items():
            x = e.copy() if name == "tracks_exposure" else rng.normal(size=len(e))
            vals.append(_rho(np.asarray(x, float), e))
        C, ms = consistency(vals)
        cap[name] = {"C": C, "mean_signed": ms}
    g3 = cap["tracks_exposure"]["C"] > 0.9 and cap["pure_noise"]["C"] < 0.5
    print(f"G3 capability under restriction: a feature that tracks the exposure gives C = "
          f"{cap['tracks_exposure']['C']:.4f}, pure noise gives {cap['pure_noise']['C']:.4f} "
          f"-> {'PASS' if g3 else 'FAIL'}")

    # ---- donor nulls and primaries ---------------------------------------------------------------------
    def evaluate(state, label):
        out = {}
        for a in arms:
            per = state[a][0]
            cs = list(per)
            real = [_rho(per[c][0], per[c][1]) for c in cs]
            C, ms = consistency(real)
            draws = []
            for _ in range(N_DONOR):
                v = []
                for c in cs:
                    d = cs[int(rng.integers(0, len(cs)))]
                    if d == c:
                        continue
                    de = per[d][1]
                    n = min(len(per[c][0]), len(de))
                    if n < MIN_WINDOWS:
                        continue
                    r = _rho(per[c][0][:n], de[:n])
                    if np.isfinite(r):
                        v.append(r)
                Cd, _ = consistency(v)
                if np.isfinite(Cd):
                    draws.append(Cd)
            null95 = float(np.percentile(draws, 95)) if draws else float("nan")
            out[a] = {"C": C, "mean_signed": ms, "null95": null95, "n": len(cs),
                      "clears": bool(np.isfinite(C) and C > null95)}
            print(f"{label:12s} {a:12s} n={len(cs):3d}  mean signed rho {ms:+.4f}  "
                  f"consistency {C:.4f} against donor null {null95:.4f}  "
                  f"-> {'CLEARS' if out[a]['clears'] else 'fails'}")
        return out

    print()
    ev_un = evaluate(unres, "unrestricted")
    ev_re = evaluate(res, "restricted")

    # ---- P3 direction contrast with an arm-label permutation placebo -------------------------------------
    pa = np.asarray([_rho(*res["propofol"][0][c][:2]) for c in res["propofol"][0]], float)
    sb = np.asarray([_rho(*res["sevoflurane"][0][c][:2]) for c in res["sevoflurane"][0]], float)
    pa, sb = pa[np.isfinite(pa)], sb[np.isfinite(sb)]
    p3 = float(pa.mean() - sb.mean())
    allv = np.concatenate([pa, sb])
    plac = np.asarray([float(allv[i[:len(pa)]].mean() - allv[i[len(pa):]].mean())
                       for i in (rng.permutation(len(allv)) for _ in range(N_PERM))])
    p3_p = float(np.mean(np.abs(plac) >= abs(p3)))
    boot = np.asarray([float(pa[rng.integers(0, len(pa), len(pa))].mean()
                             - sb[rng.integers(0, len(sb), len(sb))].mean()) for _ in range(N_BOOT)])
    print()
    print(f"P3 direction contrast (propofol minus sevoflurane), restricted: {p3:+.4f} "
          f"[{np.percentile(boot, 2.5):+.4f}, {np.percentile(boot, 97.5):+.4f}]  "
          f"arm-label placebo |p| = {p3_p:.4f}")

    pc, sc = ev_re["propofol"], ev_re["sevoflurane"]
    if pc["clears"] and np.sign(pc["mean_signed"]) == np.sign(sc["mean_signed"]) and sc["clears"]:
        verdict = ("ARTEFACT -- at matched prominence propofol's peak DOES track its exposure, in the same "
                   "direction as sevoflurane's; E233's asymmetry was a consequence of the propofol arm "
                   "having weaker peaks and is withdrawn")
    elif pc["clears"] and sc["clears"] and np.sign(pc["mean_signed"]) != np.sign(sc["mean_signed"]):
        verdict = (f"WRONG DIRECTION -- both arms now track their exposure but with OPPOSITE signs "
                   f"(propofol {pc['mean_signed']:+.4f}, sevoflurane {sc['mean_signed']:+.4f}); that is a "
                   "third finding, not a restoration of the asymmetry, and is reported with the sign")
    elif not pc["clears"] and sc["clears"]:
        verdict = ("ASYMMETRY RESTORED -- propofol's peak still fails to track its exposure among the "
                   "windows where propofol's own alpha is strongest, while sevoflurane's still clears; "
                   "the null survives the prominence confound raised against it")
    else:
        verdict = ("NOT INTERPRETABLE -- the positive control arm no longer clears after restriction, so "
                   "the restriction removed signal rather than noise")
    if not g1:
        verdict = (f"NOT INTERPRETABLE -- G1 failed; the prominence gap only fell from {g_un:+.4f} to "
                   f"{g_re:+.4f} and the confound is still present")
    elif not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the restriction manufactures or destroys effects"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 failed; 'most prominent' is a label, not a selection"
    elif not g2:
        verdict = "NOT INTERPRETABLE -- G2 coverage failed"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"N_retained": N, "unrestricted": ev_un, "restricted": ev_re,
                   "prominence_gap": {"unrestricted": g_un, "unrestricted_p": p_un,
                                      "restricted": g_re, "restricted_p": p_re},
                   "caliper": caliper, "n_pairs": len(pairs), "n_discarded": discarded, "capability": cap,
                   "p3": {"est": p3, "lo": float(np.percentile(boot, 2.5)),
                          "hi": float(np.percentile(boot, 97.5)), "placebo_p": p3_p},
                   "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
