#!/usr/bin/env python3
"""E227 -- is the propofol arm's weak coupling ABSENCE of coupling, or coupling with a patient-specific SIGN?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E225. Instrument changed; cohort, arms, thresholds and horizon are identical to E225's.
E225 IS THE REASON THIS FILE EXISTS AND ITS FAILURE IS THE DESIGN INPUT. Its consistency statistic was
|median across cases of the signed rho|, and its own capability gate refused the run: the planted
sign-varying control -- the exposure times a per-case random sign, balance measured at 0.455 positive --
scored C = 1.0000 against a donor floor of 0.1124. A median does not cancel for a BIMODAL distribution.
A balanced mixture of -1 and +1 has median -1 or +1, never 0, so the median reports the MAJORITY sign
rather than the degree of agreement, and the statistic was incapable of the discrimination it was
registered to make. The one thing changed here is that summary.

THE REPLACEMENT IS A RESULTANT LENGTH, WHICH CANCELS BY CONSTRUCTION.

    C  (consistency)  = |mean across cases of the signed rho| / mean across cases of |rho|.

The numerator cancels when directions disagree; the denominator is the strength. Their ratio is the
fraction of the available coupling that points the same way -- 1 when every case agrees, 0 when the
signs are balanced, and undefined only if there is no coupling at all, which the strength arm reports
separately. It is the circular-statistics resultant length restricted to a sign, and it is bounded in
[0, 1] regardless of how large the individual correlations are, so a feature cannot buy consistency by
being strongly coupled. E225 measured what the donor null does to this family: a donated exposure gives
consistency near zero (0.0473 and 0.0368 on the median version), which is the premise this rests on and
which is re-measured here rather than carried forward (rule 2).

WHY A SUCCESSOR EXISTS, AND WHAT CHANGED. E224 returned NOT INTERPRETABLE because its donor placebo was
not beaten in the propofol arm: per-case mean |rho| was 0.2466 against a donor-mean null of 0.2253,
p = 0.0650. That is a fact about the STATISTIC as much as about the drug. Mean |rho| never cancels, so any
smooth monotone exposure -- including one donated from an unrelated patient -- scores ~0.22 against this
panel, and a floor that high leaves almost no dynamic range. The instrument changed here, and only the
instrument (rule 58 and the ledger's `instrument_changed` field): the same per-case signed Spearman values
are summarised two ways instead of one.

    C  (consistency)  = |mean signed rho| / mean |rho|, per feature -- a resultant length in [0, 1].
                        Donor null is near zero, because donated exposures produce signs that cancel.
    S  (strength)     = mean across cases of |rho|, per feature.
                        Donor null is high -- E224 measured 0.2253 -- because nothing cancels.

THE TWO SUMMARIES SEPARATE THE TWO READINGS THAT E224 COULD NOT TELL APART, and this is the whole point
of the design. A drug the EEG simply does not track scores low on BOTH. A drug the EEG tracks with a
direction that DIFFERS BETWEEN PATIENTS scores low on C and high on S. Those are completely different
findings about Challenge A and they license opposite next moves: the first says stop looking at propofol,
the second says the propofol effect is real and the population-level analysis has been averaging it away.

There is direct evidence the second is live. Recomputed on identical mutually-exclusive arms and a fixed
15-column panel, the propofol arm scores 0.1402 on C and 0.2466 on S; sevoflurane scores 0.3225 and
0.3663. Propofol's C/S ratio is 0.57 against sevoflurane's 0.88 -- propofol's coupling is markedly less
sign-consistent -- but whether either exceeds its own null is exactly what has never been measured, and is
what this file measures.

PRIMARIES, all per feature, all with a MEASURED donor null rather than an assumed one (rule 63).

  P1  propofol: the number of the evaluable features whose C exceeds the 95th percentile of its own donor
      null. C is now a resultant length, so a feature passes only if its per-case directions AGREE, not
      merely if a majority of them share a sign.
  P2  propofol: the same for S. E224 already suggests this is at the floor; it is recomputed here so that
      P1 and P2 come from one run on one cohort and can be read against each other (rule 20).
  P3  sign agreement: among features passing C in BOTH arms, how often the two arms agree in direction,
      against an exact binomial null. A reversal between agents is a different claim from a weaker effect
      and the panel has shown reversals before.

GATES. Each is constructed so that the input which should fail it does, and the input which should pass
it does (rules 40 and 81).

  G1  ALIVENESS OF THE REFERENCE ARM (rule 53). Sevoflurane must pass C on a majority of evaluable
      features. If it does not, no statement about propofol having less is readable (rule 69).
  G2  THE DONOR NULL IS MEASURED, NOT ASSUMED. Both C and S nulls are built by pairing each case's panel
      with a contiguous exposure block from a DIFFERENT case (rule 82 -- the deposit already contains the
      object we would otherwise synthesise), and the null for a per-feature summary is a distribution of
      that SUMMARY over donor draws, never the spread of individual cases (rule 50, the shape error E224
      was repaired for). The C null is REPORTED, and if it is not near zero the design's premise is wrong
      and that must be visible.
  G3  CAPABILITY, THREE WAYS, and the third is the one that matters. (i) a synthetic feature equal to the
      exposure must pass C and S; (ii) a synthetic feature of pure noise must fail both; (iii) A SYNTHETIC
      FEATURE EQUAL TO THE EXPOSURE TIMES A PER-CASE RANDOM SIGN must FAIL C and PASS S. Construct (iii)
      is the entire hypothesis in synthetic form, and rule 84 says a control built to have a property must
      have that property MEASURED rather than asserted -- so its per-case sign balance is printed.
  G4  COVERAGE. At least 20 cases per arm and at least 20 evaluable cases per feature; features below that
      are EXCLUDED and REPORTED with the count (rules 14 and 74).

PLACEBO. The donor null in G2 is the placebo, applied to the primary statistic itself rather than to a
proxy for it (rule 79). It destroys the whole association, not only its timing; that is a design choice
and is stated rather than discovered (rule 82).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37).

  (a) propofol C excess interval lies entirely BELOW zero -> WRONG DIRECTION. The propofol arm is less
      sign-consistent than a donated exposure, which is incoherent and indicates a defect, not a finding.
  (b) propofol fails C AND fails S -> NO COUPLING. The panel does not track propofol at all in this
      cohort. Challenge A's propofol arm is a dead end and should be reported as one.
  (c) propofol fails C AND passes S -> SIGN-VARYING COUPLING. The effect is real per patient and its
      direction differs between patients; every population-level propofol analysis in this project has
      been averaging it to zero, and the successor is to model the sign.
  (d) propofol passes C on any feature -> CONSISTENT BUT WEAK. The gap is quantitative, and the features
      that pass are named.

  Gating, applied AFTER the primary is evaluated because a gate can only invalidate a pass and never
  rescue a null (rule 37): G1 or G3 failure -> NOT INTERPRETABLE, and G3(iii) failing is the most
  informative failure available, because it would mean the statistic cannot detect sign-varying coupling
  even when that coupling is planted by construction.

SCOPE. Arms are mutually exclusive; combined-technique cases are in neither. BIS is not used. The anchor
is the recorded exposure throughout.

INCUMBENT (rule 45): `Orchestra/PPF20_CE` for propofol and `Primus/EXP_SEVO` for sevoflurane, the same
exposures E224 used, so the two files are directly comparable.

    python bsde/src/bsde/experiments/e227_sign_varying_coupling_v2.py
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

MIN_WINDOWS = 10
MIN_CASES = 20
N_DONOR = 400
N_BOOT = 2000
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e227_sign_varying_coupling_v2.json"
SKIP = ("meta_", "recording_id", "dataset", "subject", "status", "error",
        "n_channels", "sfreq", "n_samples")
VOL = ("Primus/EXP_SEVO", "Primus/EXP_DES", "Primus/INSP_SEVO", "Primus/INSP_DES")
EXPOSURE = {"propofol": "Orchestra/PPF20_CE", "sevoflurane": "Primus/EXP_SEVO"}


def _num(r, f):
    try:
        return float(r[f])
    except (TypeError, ValueError, KeyError):
        return float("nan")


def _hold(track, t_eval):
    """Zero-order hold. A pump target and an end-tidal reading are both held between updates."""
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


def _rho(x, e):
    import numpy as np
    from bsde.verifier.stats import spearman
    m = np.isfinite(x) & np.isfinite(e)
    if m.sum() < MIN_WINDOWS or np.std(x[m]) <= 0 or np.std(e[m]) <= 0:
        return float("nan")
    return float(spearman(x[m], e[m]))


def summarise(per_case):
    """C and S from one feature's per-case signed rho values."""
    import numpy as np
    v = np.asarray([x for x in per_case if np.isfinite(x)], float)
    if len(v) < MIN_CASES:
        return float("nan"), float("nan"), len(v)
    S = float(np.mean(np.abs(v)))
    # RESULTANT LENGTH, not a median. |mean signed| cancels when directions disagree; dividing by the mean
    # magnitude makes it a FRACTION of the available coupling that points one way, bounded in [0, 1], so a
    # strongly coupled feature cannot buy consistency with magnitude. E225 died because a median cannot do
    # this: the median of a balanced mixture of -1 and +1 is +/-1, never 0.
    C = float(abs(np.mean(v)) / S) if S > 0 else float("nan")
    return C, S, len(v)


def main() -> int:
    import numpy as np
    from bsde.verifier.stats import read_rows
    rng = np.random.default_rng(SEED)

    rows, dropped = [], 0
    for p in sorted(glob.glob(GRID)):
        r, d = read_rows(p)
        rows += r
        dropped += d
    cols = [k for k in rows[0] if not k.startswith(SKIP) and k != "uce_v1"]
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    for c in by:
        by[c].sort(key=lambda r: _num(r, "meta_t_s"))
    tracks = {}
    for s in range(4):
        for line in open(PK % s):
            r = json.loads(line)
            tracks[r["caseid"]] = r
    print(f"panel: {len(rows)} windows, {len(by)} cases, {len(cols)} columns, {dropped} header rows dropped")

    arms = {"propofol": [], "sevoflurane": []}
    for c in by:
        tr = set(tracks[c]["tracks"])
        hp = "Orchestra/PPF20_RATE" in tr and "Orchestra/PPF20_CE" in tr
        hv = any(v in tr for v in VOL)
        if hp and hv:
            continue
        if hp:
            arms["propofol"].append(c)
        elif "Primus/EXP_SEVO" in tr:
            arms["sevoflurane"].append(c)
    print("arms:", {k: len(v) for k, v in arms.items()})

    # ---- per-case signed rho, and the exposure series kept for the donor null ---------------------
    real = {a: collections.defaultdict(list) for a in arms}
    expo = {a: {} for a in arms}
    panels = {a: {} for a in arms}
    for a, cases in arms.items():
        for c in cases:
            panel = by[c]
            te = [_num(r, "meta_t_s") for r in panel]
            if len(te) < MIN_WINDOWS:
                continue
            e = _hold(tracks[c]["tracks"][EXPOSURE[a]], te)
            if np.isfinite(e).sum() < MIN_WINDOWS or np.nanstd(e) <= 0:
                continue
            expo[a][c] = e
            panels[a][c] = panel
            for f in cols:
                x = np.asarray([_num(r, f) for r in panel], float)
                v = _rho(x, e)
                if np.isfinite(v):
                    real[a][f].append(v)

    # ---- G4 coverage / exclusions -----------------------------------------------------------------
    evaluable, excluded = [], {}
    for f in cols:
        n = {a: len([v for v in real[a][f] if np.isfinite(v)]) for a in arms}
        if min(n.values()) >= MIN_CASES:
            evaluable.append(f)
        else:
            excluded[f] = n
    g4 = len(evaluable) >= 5 and all(len(expo[a]) >= MIN_CASES for a in arms)
    print(f"G4: {len(evaluable)} evaluable features, cases per arm "
          f"{ {a: len(expo[a]) for a in arms} } -> {'PASS' if g4 else 'FAIL'}")
    print("EXCLUDED (rule 74):", excluded)

    # ---- G2 donor null, per feature, as a distribution of the SUMMARY -----------------------------
    donor = {a: {f: {"C": [], "S": []} for f in evaluable} for a in arms}
    for a in arms:
        cs = list(expo[a])
        for _ in range(N_DONOR):
            draw = {f: [] for f in evaluable}
            for c in cs:
                d = cs[int(rng.integers(0, len(cs)))]
                if d == c:
                    continue
                de = expo[a][d]
                panel = panels[a][c]
                n = min(len(panel), len(de))
                if n < MIN_WINDOWS:
                    continue
                for f in evaluable:
                    x = np.asarray([_num(r, f) for r in panel[:n]], float)
                    v = _rho(x, de[:n])
                    if np.isfinite(v):
                        draw[f].append(v)
            for f in evaluable:
                C, S, n = summarise(draw[f])
                if np.isfinite(C):
                    donor[a][f]["C"].append(C)
                    donor[a][f]["S"].append(S)
    nullC = {a: {f: float(np.percentile(donor[a][f]["C"], 95)) for f in evaluable} for a in arms}
    nullS = {a: {f: float(np.percentile(donor[a][f]["S"], 95)) for f in evaluable} for a in arms}
    meanC = {a: float(np.mean([np.mean(donor[a][f]["C"]) for f in evaluable])) for a in arms}
    meanS = {a: float(np.mean([np.mean(donor[a][f]["S"]) for f in evaluable])) for a in arms}
    print(f"G2 donor null measured: mean C = { {a: round(meanC[a], 4) for a in arms} } "
          f"(the design's premise requires this to be near zero); "
          f"mean S = { {a: round(meanS[a], 4) for a in arms} }")

    # ---- G3 capability, three ways ----------------------------------------------------------------
    a0 = "propofol"
    cs = list(expo[a0])
    signs = rng.choice([-1.0, 1.0], size=len(cs))
    cap = {}
    for name, mk in (("exposure", lambda i, c: expo[a0][c]),
                     ("noise", lambda i, c: rng.normal(size=len(expo[a0][c]))),
                     ("sign_flipped", lambda i, c: signs[i] * expo[a0][c])):
        vals = [_rho(np.asarray(mk(i, c), float), expo[a0][c]) for i, c in enumerate(cs)]
        C, S, n = summarise(vals)
        cap[name] = {"C": C, "S": S, "n": n}
    fC = float(np.mean([nullC[a0][f] for f in evaluable]))
    fS = float(np.mean([nullS[a0][f] for f in evaluable]))
    bal = float(np.mean(signs > 0))
    g3 = (cap["exposure"]["C"] > fC and cap["exposure"]["S"] > fS
          and cap["noise"]["C"] < fC and cap["noise"]["S"] < fS
          and cap["sign_flipped"]["C"] < fC and cap["sign_flipped"]["S"] > fS)
    print(f"G3 capability against mean donor floors C={fC:.4f} S={fS:.4f}:")
    for k, v in cap.items():
        print(f"     {k:14s} C={v['C']:.4f}  S={v['S']:.4f}  (n={v['n']})")
    print(f"     sign-flip control balance measured at {bal:.3f} positive (rule 84) "
          f"-> G3 {'PASS' if g3 else 'FAIL'}")

    # ---- primaries --------------------------------------------------------------------------------
    res = {}
    for a in arms:
        rec = {}
        for f in evaluable:
            C, S, n = summarise(real[a][f])
            rec[f] = {"C": C, "S": S, "n": n, "C_null95": nullC[a][f], "S_null95": nullS[a][f],
                      "C_pass": bool(C > nullC[a][f]), "S_pass": bool(S > nullS[a][f]),
                      "mean_signed": float(np.mean([v for v in real[a][f] if np.isfinite(v)]))}
        res[a] = rec
    print()
    print(f"{'feature':28s} {'PPF C':>8}{'null':>8}{'':2}{'PPF S':>8}{'null':>8}{'':3}"
          f"{'SEV C':>8}{'null':>8}{'':2}{'SEV S':>8}{'null':>8}")
    for f in evaluable:
        p, s = res["propofol"][f], res["sevoflurane"][f]
        print(f"{f:28s} {p['C']:8.4f}{p['C_null95']:8.4f}{'*' if p['C_pass'] else ' ':>2}"
              f"{p['S']:8.4f}{p['S_null95']:8.4f}{'*' if p['S_pass'] else ' ':>3}"
              f"{s['C']:8.4f}{s['C_null95']:8.4f}{'*' if s['C_pass'] else ' ':>2}"
              f"{s['S']:8.4f}{s['S_null95']:8.4f}{'*' if s['S_pass'] else ' ':>2}")

    p1 = sum(res["propofol"][f]["C_pass"] for f in evaluable)
    p2 = sum(res["propofol"][f]["S_pass"] for f in evaluable)
    s1 = sum(res["sevoflurane"][f]["C_pass"] for f in evaluable)
    s2 = sum(res["sevoflurane"][f]["S_pass"] for f in evaluable)
    both = [f for f in evaluable if res["propofol"][f]["C_pass"] and res["sevoflurane"][f]["C_pass"]]
    agree = sum(1 for f in both
                if np.sign(res["propofol"][f]["mean_signed"])
                == np.sign(res["sevoflurane"][f]["mean_signed"]))
    print()
    print(f"P1 propofol    C passes {p1}/{len(evaluable)}   S passes {p2}/{len(evaluable)}")
    print(f"   sevoflurane C passes {s1}/{len(evaluable)}   S passes {s2}/{len(evaluable)}")
    print(f"P3 direction agreement on the {len(both)} features passing C in BOTH arms: {agree}/{len(both)}")

    g1 = s1 > len(evaluable) / 2
    print(f"G1 aliveness: sevoflurane passes C on {s1} of {len(evaluable)} -> {'PASS' if g1 else 'FAIL'}")

    if p1 == 0 and p2 == 0:
        verdict = ("NO COUPLING -- the panel does not track propofol in this cohort on either summary; "
                   "Challenge A's propofol arm is a dead end and should be reported as one")
    elif p1 == 0 and p2 > 0:
        verdict = (f"SIGN-VARYING COUPLING -- {p2} features exceed the donor null on strength while none "
                   "does on consistency; the propofol effect is real per patient with a direction that "
                   "differs between patients, and every population-level propofol analysis here has been "
                   "averaging it away")
    else:
        verdict = (f"CONSISTENT BUT WEAK -- {p1} features exceed the donor null on consistency: "
                   + ", ".join(f for f in evaluable if res["propofol"][f]["C_pass"]))
    if not g3:
        verdict = ("NOT INTERPRETABLE -- G3 capability failed; the C/S split cannot be trusted to "
                   "distinguish sign-varying coupling from no coupling")
    elif not g1:
        verdict = "NOT INTERPRETABLE -- G1 failed; the reference arm does not couple in this cohort"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 coverage failed"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"per_feature": res, "evaluable": evaluable, "excluded": excluded,
                   "capability": cap, "sign_balance": bal,
                   "donor_mean_C": meanC, "donor_mean_S": meanS,
                   "counts": {"propofol_C": p1, "propofol_S": p2,
                              "sevoflurane_C": s1, "sevoflurane_S": s2},
                   "direction_agreement": {"n": len(both), "agree": agree, "features": both},
                   "gates": {"G1": bool(g1), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
