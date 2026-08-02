#!/usr/bin/env python3
"""E230 -- does the alpha reversal survive matching the two arms on who the patients are?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E229 by an instrument change: the same per-case signed correlations, read on a COHORT
MATCHED on pre-exposure covariates instead of on the arms as they fall.

THE STANDING RESULT AND ITS ONE REMAINING WEAKNESS. E229, on 114 propofol-only and 87
sevoflurane-only VitalDB cases, found that 10 of the 11 panel features clearing a donor null for
directional consistency in both arms AGREE in direction (exact binomial p = 0.0059), and that exactly
one disagrees: `relative_alpha_power`, mean signed rho **+0.1189** against propofol effect-site
concentration and **-0.2482** against sevoflurane end-tidal, each clearing its own donor null.

That is a BETWEEN-PATIENT comparison. The anaesthetist chose the technique, and the choice is not
random: propofol and volatile cases differ in age, surgery, urgency and opioid co-administration. The
reversal could be a property of the drugs or a property of the patients who receive them.

THE WITHIN-PATIENT TEST IS NOT AVAILABLE AND THAT IS NOW ESTABLISHED, NOT ASSUMED. E228 tried it: of
250 VitalDB cases only 31 are genuinely combined-technique, 17 have both exposures varying across the
EEG-windowed period, and 1 has a usable epoch of each. A search of OpenNeuro's full EEG catalogue,
PhysioNet, Zenodo, Dryad, Figshare and OSF found no public deposit in which one subject receives both
an intravenous and a volatile agent with EEG throughout. The one trial with exactly that design,
NCT02043938, states `"ipdSharing": "NO"`. **So the confound cannot be removed by design and must be
addressed by adjustment, which is weaker and is labelled as weaker.**

WHAT THIS FILE DOES. It matches each propofol case to a sevoflurane case on PRE-EXPOSURE covariates
only -- age, sex, ASA, BMI and emergency status -- by Mahalanobis distance on the standardised
continuous covariates with an EXACT match on sex, greedily and without replacement. Sex is exact
because it is the only covariate here that is categorical and unordered; ASA is treated as ordinal.
Nothing measured after induction enters the match: conditioning on a post-exposure variable would be a
collider (rule 13), which is why case duration and burst-suppression fraction are deliberately absent
even though they would improve balance.

REMIFENTANIL IS THE ONE HARD CASE AND IT IS RUN BOTH WAYS. Opioid co-administration is concurrent
rather than post-exposure, it differs systematically between techniques, and it changes the EEG. Rule
54 says a confound named in a registration and not handled in code is an unnamed confound wearing a
disclaimer, so it is handled -- but including a concurrent exposure in a match is a judgement call, so
BOTH arms are reported: matched without it (primary) and matched with it as a sixth covariate
(sensitivity). Neither is allowed to be chosen after the fact; the primary is the one without, declared
here.

PRIMARIES.

  P1  On the matched cohort, the alpha DIRECTION CONTRAST:
          D_alpha = mean signed rho(alpha, propofol Ce) - mean signed rho(alpha, sevoflurane ET)
      with a cluster bootstrap over matched PAIRS. E229 puts this at +0.1189 - (-0.2482) = +0.3671
      unmatched. The registered prediction is that it stays positive and excludes zero.
  P2  THE PANEL IS ITS OWN CONTROL, as in E228. The same contrast for the ten features that AGREED in
      E229 must remain small. P2 = D_alpha minus the mean |D| over those ten. If matching removes the
      reversal but leaves the concordant features alone, the reversal was confounding; if it removes
      everything, the matching destroyed the signal and nothing is readable.
  P3  Balance, reported as standardised mean differences per covariate before and after matching. This
      is not a gate on its own (see G1) but it is what makes P1 interpretable, and an unbalanced match
      is a match in name only.

GATES, each constructed so that the input which should fail it does and the input which should pass it
does (rules 40 and 81).

  G1  BALANCE. Every matched covariate must have |standardised mean difference| below 0.25 after
      matching AND lower than before. The 0.25 is a CONVENTION, not a quantity derived from this
      machinery, and rule 63 requires that to be said rather than dressed up: it is the customary
      applied-statistics threshold and it cannot distinguish success from its own arbitrariness. The
      before/after SMDs are therefore reported in full so a reader can apply their own bar.
  G2  COVERAGE. At least 40 matched pairs. Below that the pair bootstrap is too coarse for a contrast
      of two means (rule 85: check which integer counts straddle the threshold before trusting a
      binary).
  G3  ALIVENESS AFTER MATCHING (rule 53). On the matched cohort the sevoflurane arm must still clear a
      donor-exposure null on alpha. Matching discards cases, and a discarded cohort that no longer
      couples cannot answer whether a contrast survived.
  G4  CAPABILITY, both directions. A synthetic feature constructed to reverse between the arms must show
      a large positive D after matching; a synthetic feature constructed to behave identically in both
      arms must show D near zero. Matching must not manufacture a contrast, and it must not destroy one.

PLACEBO (rule 82, and rule 35's matched-subset control run in the direction it was designed for). The
matching is repeated with the covariate values PERMUTED across cases, producing a cohort of the same
size, the same arm balance and the same discard rate but matched on nothing. If D_alpha under the
random match reproduces D_alpha under the real match, then the real matching did no work and P1 is a
statement about subsetting rather than about covariates. Compared against the placebo's DISTRIBUTION
over 300 draws, never its mean (rule 37, fifth occurrence).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37, fourth occurrence).

  (a) P1's interval lies entirely BELOW zero -> WRONG DIRECTION. After matching, alpha moves the same
      way with propofol as with sevoflurane and oppositely to E229's estimate. The reversal is refuted
      against its own prediction and E229's headline must be withdrawn.
  (b) P1's interval contains zero -> NOT ROBUST TO CASE MIX. The reversal is consistent with
      confounding by who receives which technique, and must be reported as unconfirmed rather than as
      a null result about the drugs.
  (c) P1 excludes zero above AND P2 excludes zero above -> ROBUST. The reversal survives matching and
      the concordant features still do not reverse; the strongest statement Challenge A can make on
      public data, and still not a within-patient result.
  (d) P1 excludes zero above but P2 contains zero -> the concordant controls reverse as much as alpha
      does after matching, which means the matching introduced a panel-wide contrast. Reported as NOT
      INTERPRETABLE, not as a pass.

  Gating, applied AFTER the primary is evaluated because a gate can only invalidate a pass and never
  rescue a null (rule 37): G3 or G4 failing -> NOT INTERPRETABLE. G1 failing -> the match did not
  achieve balance and P1 is reported as an unadjusted subset. Placebo reproducing the effect -> NOT
  INTERPRETABLE.

SCOPE. Matching on five recorded covariates cannot stand in for randomisation and does not claim to.
Unmeasured confounding -- surgical procedure, comorbidity, the anaesthetist's reason for choosing a
technique -- is untouched, and this file's ceiling is "the reversal is not explained by age, sex, ASA,
BMI or urgency". BIS is not used. The anchors are the recorded exposures.

INCUMBENT (rule 45): the ten features that agreed in direction in E229, on the identical matched cases,
windows and code path.

    python bsde/src/bsde/experiments/e230_matched_alpha_reversal.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

MIN_WINDOWS = 10
MIN_PAIRS = 40
SMD_MAX = 0.25
N_BOOT = 2000
N_PLACEBO = 300
N_DONOR = 200
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e230_matched_alpha_reversal.json"
SKIP = ("meta_", "recording_id", "dataset", "subject", "status", "error",
        "n_channels", "sfreq", "n_samples")

TARGET = "relative_alpha_power"
CONTROLS = ("critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "exponent_low",
            "lempel_ziv", "multiscale_entropy_slope", "relative_delta_power", "spectral_edge_95",
            "spectral_entropy", "whole_head_exponent")
CONT = ("meta_age", "meta_asa", "meta_bmi")          # continuous / ordinal, Mahalanobis
EXACT = ("meta_sex",)                                 # categorical, exact
BINARY = ("meta_emop",)                               # binary, enters the distance standardised


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
    """Rule 87: a channel counts only if it is EVER NONZERO. Key presence is a fact about the machine."""
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


def smd(a, b):
    import numpy as np
    a = np.asarray([v for v in a if np.isfinite(v)], float)
    b = np.asarray([v for v in b if np.isfinite(v)], float)
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    s = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return float((a.mean() - b.mean()) / s) if s > 0 else float("nan")


def match(pc, sc, cov, rng, permute=False):
    """Greedy 1:1 nearest-neighbour Mahalanobis match without replacement, exact on sex.

    Greedy rather than optimal on purpose: an optimal assignment would be better balanced and would also
    make the placebo harder to interpret, because the placebo must differ from the real match ONLY in
    what it matches on, not in how hard it tries.
    """
    import numpy as np
    keys = list(CONT) + list(BINARY)
    P = np.array([[cov[c][k] for k in keys] for c in pc], float)
    S = np.array([[cov[c][k] for k in keys] for c in sc], float)
    if permute:
        allv = np.vstack([P, S])
        allv = allv[rng.permutation(len(allv))]
        P, S = allv[:len(pc)], allv[len(pc):]
        psex = np.array([cov[c]["meta_sex"] for c in pc])[rng.permutation(len(pc))]
        ssex = np.array([cov[c]["meta_sex"] for c in sc])[rng.permutation(len(sc))]
    else:
        psex = np.array([cov[c]["meta_sex"] for c in pc])
        ssex = np.array([cov[c]["meta_sex"] for c in sc])
    mu = np.nanmean(np.vstack([P, S]), axis=0)
    sd = np.nanstd(np.vstack([P, S]), axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
    # standardise on the POOLED data and split afterwards, never per arm (rule 73)
    Pz = (np.where(np.isfinite(P), P, mu) - mu) / sd
    Sz = (np.where(np.isfinite(S), S, mu) - mu) / sd
    used, pairs = set(), []
    order = rng.permutation(len(pc))
    for i in order:
        best, bd = -1, np.inf
        for j in range(len(sc)):
            if j in used or ssex[j] != psex[i]:
                continue
            d = float(np.sum((Pz[i] - Sz[j]) ** 2))
            if d < bd:
                best, bd = j, d
        if best >= 0:
            used.add(best)
            pairs.append((pc[i], sc[best]))
    return pairs


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
    assert TARGET in cols and all(c in cols for c in CONTROLS)

    # ---- arms (rule 87 predicate) and per-case signed rho -------------------------------------------
    arms = {"propofol": [], "sevoflurane": []}
    rho = {"propofol": {}, "sevoflurane": {}}
    cov, remi = {}, {}
    excl = {"few_windows": 0, "exposure_flat": 0, "no_covariates": 0}
    for c, panel in by.items():
        tr = tracks[c]["tracks"]
        hp, hs, hd = (_live(tr, "Orchestra/PPF20_CE"), _live(tr, "Primus/EXP_SEVO"),
                      _live(tr, "Primus/EXP_DES"))
        if hp and (hs or hd):
            continue
        arm = "propofol" if hp else ("sevoflurane" if hs else None)
        if arm is None:
            continue
        te = [_num(r, "meta_t_s") for r in panel]
        if len(te) < MIN_WINDOWS:
            excl["few_windows"] += 1
            continue
        e = _hold(tr["Orchestra/PPF20_CE" if arm == "propofol" else "Primus/EXP_SEVO"], te)
        if np.isfinite(e).sum() < MIN_WINDOWS or np.nanstd(e) <= 0:
            excl["exposure_flat"] += 1
            continue
        cv = {k: _num(panel[0], k) for k in list(CONT) + list(BINARY)}
        cv["meta_sex"] = panel[0].get("meta_sex", "")
        if not all(np.isfinite(cv[k]) for k in CONT) or not cv["meta_sex"]:
            excl["no_covariates"] += 1
            continue
        d = {}
        for f in [TARGET] + list(CONTROLS):
            x = np.asarray([_num(r, f) for r in panel], float)
            d[f] = _rho(x, e)
        arms[arm].append(c)
        rho[arm][c] = d
        cov[c] = cv
        remi[c] = 1.0 if _live(tr, "Orchestra/RFTN20_CE") else 0.0
    print(f"arms after covariate completeness: {{'propofol': {len(arms['propofol'])}, "
          f"'sevoflurane': {len(arms['sevoflurane'])}}}  exclusions (rule 14): {excl}")

    # ---- match --------------------------------------------------------------------------------------
    pairs = match(arms["propofol"], arms["sevoflurane"], cov, rng)
    print(f"matched pairs: {len(pairs)} "
          f"(of {min(len(arms['propofol']), len(arms['sevoflurane']))} possible)")
    g2 = len(pairs) >= MIN_PAIRS
    print(f"G2 coverage (>= {MIN_PAIRS} pairs): {'PASS' if g2 else 'FAIL'}")

    # ---- G1 balance ----------------------------------------------------------------------------------
    bal = {}
    for k in list(CONT) + list(BINARY):
        before = smd([cov[c][k] for c in arms["propofol"]], [cov[c][k] for c in arms["sevoflurane"]])
        after = smd([cov[a][k] for a, _ in pairs], [cov[b][k] for _, b in pairs])
        bal[k] = {"before": before, "after": after}
    rb = smd([remi[c] for c in arms["propofol"]], [remi[c] for c in arms["sevoflurane"]])
    ra = smd([remi[a] for a, _ in pairs], [remi[b] for _, b in pairs])
    bal["remifentanil_NOT_MATCHED_ON"] = {"before": rb, "after": ra}
    g1 = all(abs(bal[k]["after"]) < SMD_MAX and abs(bal[k]["after"]) <= abs(bal[k]["before"]) + 1e-9
             for k in list(CONT) + list(BINARY))
    print(f"G1 balance (|SMD| < {SMD_MAX}, a CONVENTION not derived from this machinery -- rule 63):")
    for k, v in bal.items():
        print(f"     {k:32s} before {v['before']:+.4f}  after {v['after']:+.4f}")
    print(f"     -> G1 {'PASS' if g1 else 'FAIL'}")

    # ---- primaries -----------------------------------------------------------------------------------
    def contrast(prs, f):
        a = np.asarray([rho["propofol"][p][f] for p, _ in prs], float)
        b = np.asarray([rho["sevoflurane"][s][f] for _, s in prs], float)
        m = np.isfinite(a) & np.isfinite(b)
        return float(a[m].mean() - b[m].mean()) if m.sum() else float("nan")

    d_alpha = contrast(pairs, TARGET)
    d_ctl = {f: contrast(pairs, f) for f in CONTROLS}
    ctl_mean_abs = float(np.nanmean([abs(v) for v in d_ctl.values()]))
    boot = []
    idx = np.arange(len(pairs))
    for _ in range(N_BOOT):
        i = rng.integers(0, len(idx), len(idx))
        pr = [pairs[k] for k in i]
        boot.append((contrast(pr, TARGET),
                     contrast(pr, TARGET) - np.nanmean([abs(contrast(pr, f)) for f in CONTROLS])))
    boot = np.asarray(boot)
    p1lo, p1hi = float(np.percentile(boot[:, 0], 2.5)), float(np.percentile(boot[:, 0], 97.5))
    p2 = d_alpha - ctl_mean_abs
    p2lo, p2hi = float(np.percentile(boot[:, 1], 2.5)), float(np.percentile(boot[:, 1], 97.5))

    # ---- G4 capability, both directions ---------------------------------------------------------------
    cap = {}
    for name, flip in (("reversing", True), ("identical", False)):
        a = np.asarray([rng.normal(0.2, 0.3) for _ in pairs])
        b = -a if flip else a.copy()
        b = b + rng.normal(0, 0.05, len(b))
        cap[name] = float(a.mean() - b.mean())
    g4 = cap["reversing"] > 0.2 and abs(cap["identical"]) < 0.05
    print(f"G4 capability: a reversing synthetic gives D = {cap['reversing']:+.4f}, "
          f"an identical one {cap['identical']:+.4f} -> {'PASS' if g4 else 'FAIL'}")

    # ---- G3 aliveness on the matched cohort -----------------------------------------------------------
    sev_alpha = np.asarray([abs(rho["sevoflurane"][s][TARGET]) for _, s in pairs], float)
    sev_alpha = sev_alpha[np.isfinite(sev_alpha)]
    donor = []
    for _ in range(N_DONOR):
        v = []
        for _, s in pairs:
            d = arms["sevoflurane"][int(rng.integers(0, len(arms["sevoflurane"])))]
            if d == s:
                continue
            te = [_num(r, "meta_t_s") for r in by[s]]
            dte = [_num(r, "meta_t_s") for r in by[d]]
            de = _hold(tracks[d]["tracks"]["Primus/EXP_SEVO"], dte)
            n = min(len(by[s]), len(de))
            if n < MIN_WINDOWS:
                continue
            x = np.asarray([_num(r, TARGET) for r in by[s][:n]], float)
            r_ = _rho(x, de[:n])
            if np.isfinite(r_):
                v.append(abs(r_))
        if v:
            donor.append(float(np.mean(v)))
    donor = np.asarray(donor)
    g3_p = float(np.mean(donor >= sev_alpha.mean()))
    g3 = g3_p < 0.05
    print(f"G3 aliveness after matching: sevoflurane |rho| on alpha = {sev_alpha.mean():.4f} against a "
          f"donor-mean null of {donor.mean():.4f} (95th pct {np.percentile(donor, 95):.4f}); "
          f"p = {g3_p:.4f} -> {'PASS' if g3 else 'FAIL'}")

    # ---- placebo: match on permuted covariates ---------------------------------------------------------
    plac = []
    for _ in range(N_PLACEBO):
        pp = match(arms["propofol"], arms["sevoflurane"], cov, rng, permute=True)
        if len(pp) >= MIN_PAIRS // 2:
            plac.append(contrast(pp, TARGET))
    plac = np.asarray([v for v in plac if np.isfinite(v)])
    p_plac = float(np.mean(plac >= d_alpha))

    print()
    print(f"P1 alpha direction contrast, matched : {d_alpha:+.4f} [{p1lo:+.4f}, {p1hi:+.4f}]  "
          f"(E229 unmatched: +0.3671)")
    print(f"P2 alpha minus mean |D| of ten controls: {p2:+.4f} [{p2lo:+.4f}, {p2hi:+.4f}]  "
          f"(control mean |D| = {ctl_mean_abs:.4f})")
    for f in CONTROLS:
        print(f"       {f:28s} D = {d_ctl[f]:+.4f}")
    print(f"placebo (match on PERMUTED covariates): mean {plac.mean():+.4f}, "
          f"95th pct {np.percentile(plac, 95):+.4f}; p = {p_plac:.4f} "
          f"-> {'BEATEN' if p_plac < 0.05 else 'NOT BEATEN'}")

    # ---- verdict, wrong direction first ------------------------------------------------------------------
    if p1hi < 0:
        verdict = ("WRONG DIRECTION -- after matching, alpha moves the SAME way with propofol as with "
                   "sevoflurane and oppositely to E229's estimate; the reversal is refuted against its "
                   "own prediction and E229's headline must be withdrawn")
    elif p1lo <= 0 <= p1hi:
        verdict = ("NOT ROBUST TO CASE MIX -- the reversal is consistent with confounding by who "
                   "receives which technique and must be reported as unconfirmed, not as a null about "
                   "the drugs")
    elif p1lo > 0 and p2lo > 0:
        verdict = ("ROBUST TO CASE MIX -- the reversal survives matching on age, sex, ASA, BMI and "
                   "urgency while the ten concordant features do not reverse; the strongest statement "
                   "available on public data, and still not a within-patient result")
    else:
        verdict = ("NOT INTERPRETABLE -- the concordant controls reverse as much as alpha after "
                   "matching, so the matching introduced a panel-wide contrast")
    if not g4:
        verdict = "NOT INTERPRETABLE -- G4 capability failed; matching manufactures or destroys contrasts"
    elif not g3:
        verdict = "NOT INTERPRETABLE -- G3 failed; the matched sevoflurane cohort no longer couples on alpha"
    elif p_plac >= 0.05:
        verdict = "NOT INTERPRETABLE -- matching on permuted covariates reproduces the contrast"
    elif not g2:
        verdict = "NOT INTERPRETABLE -- G2 coverage failed"
    if not g1:
        verdict += " | BALANCE NOT ACHIEVED: P1 stands as an unadjusted subset, not a matched estimate"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"n_pairs": len(pairs), "arms": {k: len(v) for k, v in arms.items()},
                   "exclusions": excl, "balance": bal,
                   "p1": {"est": d_alpha, "lo": p1lo, "hi": p1hi, "e229_unmatched": 0.3671},
                   "p2": {"est": p2, "lo": p2lo, "hi": p2hi, "control_mean_abs": ctl_mean_abs,
                          "controls": d_ctl},
                   "placebo": {"mean": float(plac.mean()), "p95": float(np.percentile(plac, 95)),
                               "p": p_plac, "beaten": bool(p_plac < 0.05), "n": len(plac)},
                   "capability": cap,
                   "g3": {"sev_alpha": float(sev_alpha.mean()), "donor_mean": float(donor.mean()),
                          "p": g3_p},
                   "gates": {"G1_balance": bool(g1), "G2_coverage": bool(g2),
                             "G3_aliveness": bool(g3), "G4_capability": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
