#!/usr/bin/env python3
"""E228 -- does the alpha reversal survive WITHIN a patient who receives both agents?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.
SUCCESSOR OF E227 by a cohort change that is forced, not chosen; see below.

WHAT E227 FOUND AND WHY IT IS NOT ENOUGH. Across mutually exclusive VitalDB arms, 10 panel features
cleared a donor null for directional consistency in both the propofol and the sevoflurane arm, and 9 of
those 10 agreed in sign (exact binomial p = 0.0107). The single disagreement was `relative_alpha_power`:
mean signed rho **+0.1079** against propofol effect-site concentration and **-0.2482** against
sevoflurane end-tidal. That is the observation the whole Challenge A thread began from, recovered as the
one directional reversal in a panel that otherwise agrees.

**It is a BETWEEN-PATIENT comparison, and every between-patient confound is available to explain it.**
Propofol-only and sevoflurane-only cases differ in surgery, duration, age, relaxant use and whatever
drove the anaesthetist's choice of technique. E227 cannot separate "alpha responds oppositely to the two
drugs" from "the kind of patient who gets propofol has alpha that behaves differently".

THE OBVIOUS REPLICATION IS NOT AVAILABLE AND THAT IS WHY THIS DESIGN EXISTS. VitalDB carries a second
volatile, and a desflurane arm would have been an independent between-arm test. **There are 15
desflurane-only cases**, below the 20-case floor E224/E225/E227 all used, so that arm cannot be run
without lowering a threshold that three prior experiments were held to -- which is the move
`DISCOVERY_LOOP.md` §2 forbids. The cohort change here is therefore forced by coverage and is declared as
such rather than presented as a refinement.

WHAT REPLACES IT IS STRONGER, NOT WEAKER. **101 VitalDB cases receive propofol AND a volatile.** Those
cases were EXCLUDED from E224, E225 and E227 by construction, so no statistic in this file has been
looked at before. Within one such case the patient is their own control: age, surgery, montage,
electrode impedance, depth of relaxation and the anaesthetist are all held exactly constant, and the
question becomes whether ONE PATIENT'S alpha moves one way with the intravenous exposure and the other
way with the inhaled one.

THE STATISTIC, AND THE REASON IT MUST BE A PARTIAL CORRELATION. Within a combined case the two exposures
are not independent -- both typically rise after induction and fall before emergence -- so a raw
correlation of a feature against each of them is biased TOWARD THE SAME SIGN. Reporting two same-signed
raw correlations would prove nothing, and reporting opposite ones would be conservative. The estimand is
therefore the pair of Spearman PARTIAL correlations computed on ranks within the case:

    a_f = partial( feature_f , propofol Ce | volatile conc )
    b_f = partial( feature_f , volatile conc | propofol Ce )

and the per-case quantity of interest is whether `a_f` and `b_f` have OPPOSITE signs. The exposure-exposure
correlation is itself measured and reported per case, because it sets the direction of the bias and rule 50
says the baseline is measured before the mechanism is named.

PRIMARIES.

  P1  For `relative_alpha_power`: the fraction of cases with sign(a) != sign(b), with a cluster-bootstrap
      interval over cases, tested against the fraction expected under the measured null (P2).
  P2  THE PANEL IS ITS OWN NEGATIVE CONTROL, and this is the design's main idea. The 9 features that
      AGREED in direction in E227 are pre-specified as controls: critical_slowing_ar1,
      emg_beta_gamma_fraction, emg_index, exponent_low, lempel_ziv, multiscale_entropy_slope,
      relative_delta_power, spectral_entropy, whole_head_exponent. If alpha's opposite-sign rate exceeds
      theirs, the reversal is a within-patient property of the drug. If it does not, E227's between-arm
      result is cohort confounding and must be withdrawn.
      P2 = opposite-sign rate for alpha MINUS the mean opposite-sign rate over the 9 controls, cluster
      bootstrapped over cases. This is the primary that decides the question; P1 alone cannot, because an
      opposite-sign rate has no meaning without knowing what rate the machinery produces on features
      that are NOT supposed to reverse.
  P3  Direction: among cases where the signs differ, how often is `a` positive and `b` negative -- the
      direction E227 predicts -- rather than the reverse. A reversal in the wrong direction is not a
      replication, and rule 37's fourth occurrence exists because that case was once not enumerated.

GATES, each constructed so the input that should fail it does and the input that should pass it does
(rules 40 and 81).

  G1  IDENTIFIABILITY. Both exposures must vary within the case and must not be collinear to the point
      where the partials are undefined. Cases with |rho(propofol, volatile)| > 0.95, or with either
      exposure constant, are excluded and COUNTED (rule 14). The distribution of that correlation is
      printed, because if it is strongly positive in most cases the test is conservative and the reader
      must be able to see by how much.
  G2  ALIVENESS (rule 53). At least one feature's partial correlations must clear a within-case
      permutation floor. If nothing in the panel couples to either exposure once the other is partialled
      out, an opposite-sign rate is noise and nothing here is readable.
  G3  CAPABILITY, THREE WAYS. (i) a synthetic feature built as `+propofol - volatile` in ranks must show
      opposite signs in nearly every case; (ii) a synthetic feature built as `+propofol + volatile` must
      NOT; (iii) pure noise must land at the chance rate. Construct (i) is the hypothesis in synthetic
      form and construct (ii) is the null it must be distinguished from; rule 84 requires the property
      each was built to have to be MEASURED and printed, not asserted.
  G4  COVERAGE. At least 20 cases surviving G1, and at least 10 windows per case.

PLACEBO. A donor volatile track from a DIFFERENT combined case, substituted for the real one and matched
in length (rule 82 -- the deposit contains the object we would otherwise synthesise). A donated volatile
carries no information about this patient, so the opposite-sign rate under it is the rate this design
manufactures from nuisance alone. It is compared against the real rate as a DISTRIBUTION over donors,
never as a single draw or a mean (rule 79, and the fifth occurrence of rule 37).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37).

  (a) P2's interval lies entirely BELOW zero -> WRONG DIRECTION. Alpha reverses LESS often than features
      that are not supposed to reverse at all. E227's reversal is then not a within-patient drug effect
      and the between-arm result must be withdrawn, which is a stronger refutation than a null.
  (b) P2's interval contains zero -> NOT REPLICATED. Alpha behaves like the concordant controls within a
      patient; E227's reversal is consistent with cohort confounding and must be reported as such.
  (c) P2 excludes zero above AND P3 shows the predicted direction in a majority -> REPLICATED WITHIN
      PATIENT. The reversal is a property of the drugs and not of the cohorts, and it is the first
      Challenge A finding in this project that survives holding the patient constant.
  (d) P2 excludes zero above but P3's direction is the reverse of E227's -> REVERSAL OF THE REVERSAL,
      reported as a failure to replicate with the sign stated, never as a pass.

  Gating, applied AFTER the primary is evaluated because a gate can only invalidate a pass and never
  rescue a null (rule 37): G2 or G3 failing -> NOT INTERPRETABLE. Placebo not beaten -> NOT INTERPRETABLE.

SCOPE. Combined-technique cases only, which is a different population from E227's mono-technique arms;
this tests whether the reversal exists within a patient, not whether it generalises to mono-technique
anaesthesia. BIS is not used anywhere. The anchors are the recorded exposures.

INCUMBENT (rule 45): the nine pre-specified concordant features are the incumbent -- the bar alpha must
clear is the rate produced by measures that are not supposed to reverse, on the identical cases, windows
and code path.

    python bsde/src/bsde/experiments/e228_within_patient_alpha_reversal.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

MIN_WINDOWS = 10
MIN_CASES = 20
MAX_COLLINEAR = 0.95
N_DONOR = 300
N_BOOT = 2000
N_PERM = 200
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e228_within_patient_alpha_reversal.json"
SKIP = ("meta_", "recording_id", "dataset", "subject", "status", "error",
        "n_channels", "sfreq", "n_samples")

TARGET = "relative_alpha_power"
# Pre-specified from E227's own output, before this file's cohort was touched. These are the features
# that AGREED in direction between the propofol and sevoflurane arms; they are the incumbent (rule 45).
CONTROLS = ("critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "exponent_low",
            "lempel_ziv", "multiscale_entropy_slope", "relative_delta_power", "spectral_entropy",
            "whole_head_exponent")


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


def _rank(x):
    import numpy as np
    from bsde.verifier.stats import _midranks
    return _midranks(np.asarray(x, float))


def partials(f, p, v):
    """Spearman partial correlations of f with p given v, and with v given p, on a common mask.

    Computed as Pearson correlations of the residuals of the RANKS, which is the standard definition and
    is what makes the two numbers comparable to the raw Spearman values E227 reported.
    """
    import numpy as np
    m = np.isfinite(f) & np.isfinite(p) & np.isfinite(v)
    if m.sum() < MIN_WINDOWS:
        return float("nan"), float("nan"), float("nan")
    F, P, V = _rank(f[m]), _rank(p[m]), _rank(v[m])
    for a in (F, P, V):
        if np.std(a) <= 0:
            return float("nan"), float("nan"), float("nan")
    r_pv = float(np.corrcoef(P, V)[0, 1])
    if not np.isfinite(r_pv) or abs(r_pv) >= 1.0:
        return float("nan"), float("nan"), r_pv

    def part(A, B, C):
        rab = np.corrcoef(A, B)[0, 1]
        rac = np.corrcoef(A, C)[0, 1]
        rbc = np.corrcoef(B, C)[0, 1]
        d = np.sqrt((1 - rac ** 2) * (1 - rbc ** 2))
        return float((rab - rac * rbc) / d) if d > 0 else float("nan")

    return part(F, P, V), part(F, V, P), r_pv


def opp_rate(pairs):
    """Fraction of cases whose two partials have opposite signs."""
    import numpy as np
    ok = [(a, b) for a, b in pairs if np.isfinite(a) and np.isfinite(b)]
    if not ok:
        return float("nan"), 0
    return float(np.mean([np.sign(a) != np.sign(b) for a, b in ok])), len(ok)


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
    assert TARGET in cols, f"{TARGET} absent from the panel"
    missing = [c for c in CONTROLS if c not in cols]
    assert not missing, f"pre-specified controls absent: {missing}"

    # ---- combined-technique cohort ----------------------------------------------------------------
    excl = {"few_windows": 0, "exposure_constant": 0, "collinear": 0, "no_partial": 0}
    cases, agents, rpv = [], {"sevoflurane": 0, "desflurane": 0}, []
    P, V, PAN = {}, {}, {}
    for c, panel in by.items():
        tr = tracks[c]["tracks"]
        if not ("Orchestra/PPF20_CE" in tr):
            continue
        vk = "Primus/EXP_SEVO" if "Primus/EXP_SEVO" in tr else (
            "Primus/EXP_DES" if "Primus/EXP_DES" in tr else None)
        if vk is None:
            continue
        te = [_num(r, "meta_t_s") for r in panel]
        if len(te) < MIN_WINDOWS:
            excl["few_windows"] += 1
            continue
        p = _hold(tr["Orchestra/PPF20_CE"], te)
        v = _hold(tr[vk], te)
        m = np.isfinite(p) & np.isfinite(v)
        if m.sum() < MIN_WINDOWS or np.std(p[m]) <= 0 or np.std(v[m]) <= 0:
            excl["exposure_constant"] += 1
            continue
        r = float(np.corrcoef(_rank(p[m]), _rank(v[m]))[0, 1])
        if not np.isfinite(r) or abs(r) > MAX_COLLINEAR:
            excl["collinear"] += 1
            continue
        cases.append(c)
        P[c], V[c], PAN[c] = p, v, panel
        rpv.append(r)
        agents["sevoflurane" if vk == "Primus/EXP_SEVO" else "desflurane"] += 1
    rpv = np.asarray(rpv)
    print(f"combined-technique cohort: {len(cases)} cases  {agents}")
    print(f"exclusions (rule 14): {excl}")
    print(f"G1 identifiability: rho(propofol, volatile) within case -- median {np.median(rpv):+.4f}, "
          f"IQR [{np.percentile(rpv, 25):+.4f}, {np.percentile(rpv, 75):+.4f}], "
          f"{float(np.mean(rpv > 0)) * 100:.1f}% positive. A positive correlation biases the two partials "
          f"toward the SAME sign, so an opposite-sign result is conservative.")
    g1 = len(cases) >= MIN_CASES
    g4 = g1
    print(f"G4 coverage (>= {MIN_CASES} cases): {'PASS' if g4 else 'FAIL'}")

    # ---- per-case partials for every feature -------------------------------------------------------
    pair = {f: [] for f in cols}
    for c in cases:
        for f in cols:
            x = np.asarray([_num(r, f) for r in PAN[c]], float)
            a, b, _ = partials(x, P[c], V[c])
            pair[f].append((a, b))

    # ---- G2 aliveness: partials must clear a within-case permutation floor -------------------------
    alive_obs, alive_null = {}, {}
    for f in [TARGET] + list(CONTROLS):
        obs = float(np.nanmean([abs(a) for a, b in pair[f] if np.isfinite(a)]
                               + [abs(b) for a, b in pair[f] if np.isfinite(b)]))
        nul = []
        for _ in range(N_PERM):
            vals = []
            for c in cases[:min(len(cases), 40)]:
                x = np.asarray([_num(r, f) for r in PAN[c]], float)
                a, b, _ = partials(rng.permutation(x), P[c], V[c])
                if np.isfinite(a):
                    vals += [abs(a), abs(b)]
            if vals:
                nul.append(float(np.mean(vals)))
        alive_obs[f] = obs
        alive_null[f] = float(np.percentile(nul, 95)) if nul else float("nan")
    g2 = any(alive_obs[f] > alive_null[f] for f in alive_obs)
    n_alive = sum(alive_obs[f] > alive_null[f] for f in alive_obs)
    print(f"G2 aliveness: {n_alive} of {len(alive_obs)} tested features exceed their within-case "
          f"permutation floor (target {TARGET}: {alive_obs[TARGET]:.4f} vs "
          f"{alive_null[TARGET]:.4f}) -> {'PASS' if g2 else 'FAIL'}")

    # ---- G3 capability, three ways -----------------------------------------------------------------
    cap = {}
    for name in ("plus_minus", "plus_plus", "noise"):
        pr = []
        for c in cases:
            rp, rv = _rank(P[c]), _rank(V[c])
            n = len(rp)
            if name == "plus_minus":
                x = rp - rv + rng.normal(0, 0.05 * max(np.std(rp), 1e-9), n)
            elif name == "plus_plus":
                x = rp + rv + rng.normal(0, 0.05 * max(np.std(rp), 1e-9), n)
            else:
                x = rng.normal(size=n)
            a, b, _ = partials(np.asarray(x, float), P[c], V[c])
            pr.append((a, b))
        r, n = opp_rate(pr)
        cap[name] = {"opposite_sign_rate": r, "n": n}
    g3 = (cap["plus_minus"]["opposite_sign_rate"] > 0.9
          and cap["plus_plus"]["opposite_sign_rate"] < 0.1
          and 0.3 < cap["noise"]["opposite_sign_rate"] < 0.7)
    print("G3 capability (opposite-sign rate, measured not asserted -- rule 84):")
    for k, v in cap.items():
        print(f"     {k:12s} {v['opposite_sign_rate']:.4f}  (n={v['n']})")
    print(f"     -> G3 {'PASS' if g3 else 'FAIL'}")

    # ---- placebo: donor volatile track --------------------------------------------------------------
    donor_rates = []
    for _ in range(N_DONOR):
        pr = []
        for c in cases:
            d = cases[int(rng.integers(0, len(cases)))]
            if d == c:
                continue
            dv = V[d]
            n = min(len(PAN[c]), len(dv))
            if n < MIN_WINDOWS:
                continue
            x = np.asarray([_num(r, TARGET) for r in PAN[c][:n]], float)
            a, b, _ = partials(x, P[c][:n], dv[:n])
            pr.append((a, b))
        r, _n = opp_rate(pr)
        if np.isfinite(r):
            donor_rates.append(r)
    donor_rates = np.asarray(donor_rates)

    # ---- primaries -----------------------------------------------------------------------------------
    r_t, n_t = opp_rate(pair[TARGET])
    ctl = {f: opp_rate(pair[f])[0] for f in CONTROLS}
    ctl_mean = float(np.nanmean(list(ctl.values())))
    p_donor = float(np.mean(donor_rates >= r_t))

    # cluster bootstrap over cases of (alpha rate - mean control rate)
    idx = np.arange(len(cases))
    boot = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(idx), len(idx))
        rt, _ = opp_rate([pair[TARGET][k] for k in i])
        cm = np.nanmean([opp_rate([pair[f][k] for k in i])[0] for f in CONTROLS])
        if np.isfinite(rt) and np.isfinite(cm):
            boot.append(rt - cm)
    boot = np.asarray(boot)
    p2, lo, hi = float(r_t - ctl_mean), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))

    signed = [(a, b) for a, b in pair[TARGET]
              if np.isfinite(a) and np.isfinite(b) and np.sign(a) != np.sign(b)]
    pred = float(np.mean([a > 0 > b for a, b in signed])) if signed else float("nan")

    print()
    print(f"P1 {TARGET}: opposite-sign rate {r_t:.4f} over {n_t} cases")
    print(f"   nine pre-specified concordant controls: mean {ctl_mean:.4f}")
    for f in CONTROLS:
        print(f"       {f:28s} {ctl[f]:.4f}")
    print(f"P2 alpha minus control mean: {p2:+.4f} [{lo:+.4f}, {hi:+.4f}]")
    print(f"P3 among the {len(signed)} discordant cases, {pred:.4f} have propofol POSITIVE and "
          f"volatile NEGATIVE (E227's predicted direction)")
    print(f"placebo: donor-volatile opposite-sign rate mean {donor_rates.mean():.4f}, "
          f"95th pct {np.percentile(donor_rates, 95):.4f}; p = {p_donor:.4f} "
          f"-> {'BEATEN' if p_donor < 0.05 else 'NOT BEATEN'}")

    if hi < 0:
        verdict = ("WRONG DIRECTION -- alpha reverses LESS often within a patient than features that are "
                   "not supposed to reverse at all; E227's between-arm reversal is refuted against its "
                   "own prediction and must be withdrawn")
    elif lo <= 0 <= hi:
        verdict = ("NOT REPLICATED -- within a patient alpha behaves like the concordant controls; "
                   "E227's reversal is consistent with cohort confounding and must be reported as such")
    elif lo > 0 and np.isfinite(pred) and pred > 0.5:
        verdict = ("REPLICATED WITHIN PATIENT -- the reversal survives holding the patient constant and "
                   "points in E227's predicted direction; it is a property of the drugs, not the cohorts")
    else:
        verdict = ("REVERSAL OF THE REVERSAL -- alpha's signs differ more often than the controls but in "
                   "the OPPOSITE direction to E227; reported as a failure to replicate, with the sign")
    if not g3:
        verdict = "NOT INTERPRETABLE -- G3 capability failed; the opposite-sign statistic is not trustworthy"
    elif not g2:
        verdict = "NOT INTERPRETABLE -- G2 failed; nothing in the panel couples once the other drug is partialled out"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 coverage failed"
    elif p_donor >= 0.05:
        verdict = "NOT INTERPRETABLE -- the donor-volatile placebo reproduces alpha's opposite-sign rate"
    print()
    print("VERDICT:", verdict)

    with open(OUT, "w") as fh:
        json.dump({"n_cases": len(cases), "agents": agents, "exclusions": excl,
                   "rho_exposure_exposure": {"median": float(np.median(rpv)),
                                             "frac_positive": float(np.mean(rpv > 0))},
                   "p1": {"alpha_rate": r_t, "n": n_t},
                   "p2": {"est": p2, "lo": lo, "hi": hi, "control_mean": ctl_mean, "controls": ctl},
                   "p3": {"n_discordant": len(signed), "frac_predicted_direction": pred},
                   "placebo": {"mean": float(donor_rates.mean()),
                               "p95": float(np.percentile(donor_rates, 95)), "p": p_donor,
                               "beaten": bool(p_donor < 0.05)},
                   "capability": cap, "aliveness": {"obs": alive_obs, "null95": alive_null},
                   "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4)},
                   "verdict": verdict, "seed": SEED}, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
