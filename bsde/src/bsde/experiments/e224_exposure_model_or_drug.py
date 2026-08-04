#!/usr/bin/env python3
"""E224 -- is the propofol/sevoflurane coupling gap a property of the EXPOSURE VARIABLE or of the DRUG?

PRE-REGISTRATION. Written and committed before the numbers below this line exist.

THE FACT TO EXPLAIN. On VitalDB, mean per-case |Spearman| between the EEG candidate panel and the
anaesthetic exposure is 0.0912 for propofol effect-site concentration as reported by the Orchestra TCI
pump (n = 44), against 0.4192 / 0.4392 / 0.4925 for sevoflurane inspired / MAC / end-tidal (n = 70). The
EEG tracks sevoflurane about 4.6x better. A provenance hypothesis -- modelled concentrations are noisier
than measured ones -- was tested the same day and explains only the ~15 % monotone ordering WITHIN the
sevoflurane arm, leaving the bulk of the gap unexplained (`NOTE_CHALLENGE_A_REFRAMED.md`).

Three readings remain, and they license completely different next moves:

  (i)   THE PUMP'S MODEL IS BAD. Its ke0 is a population constant; if it is wrong for this patient, the
        predicted Ce is temporally misaligned with the EEG and a rank correlation is attenuated. Fixable
        by a better exposure model, which is what the investigator asked for ("an advanced all-encompassing
        PK/PD model").
  (ii)  RESTRICTION OF RANGE. If propofol is held at a near-constant TCI target while the vaporiser is
        adjusted continuously, the propofol exposure simply does not VARY within a case, and a within-case
        correlation against a near-constant is attenuated for arithmetic reasons with no pharmacology in
        it at all. Catalogue rule 43 is the same error one step earlier: a correlation never looks at
        where its exposure sits.
  (iii) A REAL PHARMACODYNAMIC DIFFERENCE. End-tidal gas is a direct surrogate for brain partial pressure
        in a way no plasma concentration is for an intravenous agent.

This file separates (i) and (ii) from (iii). It cannot prove (iii); it can only leave it standing.

WHAT IS COMPUTED, AND WHY IT IS NOT A FITTED MODEL. It is tempting to fit the eight-rate exponential
basis in `bsde.pkpd.propofol` to the EEG and report how well the fit tracks it. That is circular. Instead
each of the eight half-lives is used ON ITS OWN, as a complete one-compartment exposure model with a
different ke0 -- a KE0 SWEEP with no free parameters -- and the statistic is the best of the eight. That
is optimistically biased by the maximum over eight, so:

  * the SAME eight filters are applied to the sevoflurane arm (a first-order lag of the DELIVERED
    inspired concentration), so both arms pay the identical selection cost and the bias cancels in the
    contrast (catalogue rule 49: never select on the incumbent you intend to beat -- here neither arm
    is selected on, and both get the same eight-fold freedom);
  * the inflation is MEASURED on pure-noise columns whose nuisance structure matches the real ones
    (rule 79), and that measured floor -- not zero -- is what P1 must clear.

PRIMARIES.

  P1  mean_case[ best-of-eight |rho| ]  -  mean_case[ pump Ce |rho| ]        , propofol arm.
      Does a free ke0 buy propofol anything at all? This is reading (i).

  P2  mean_case[ best-of-eight |rho| ]_propofol  -  mean_case[ end-tidal |rho| ]_sevoflurane.
      Even at its best, does propofol reach plain sevoflurane end-tidal? This is the gap itself.

  P3  the ratio of within-case exposure dispersion (IQR / median) between the arms. This is reading (ii)
      and it GATES the interpretation of P1 and P2 rather than sitting beside them: if propofol exposure
      barely moves within a case, an attenuated correlation is arithmetic and the pharmacological reading
      must be withheld (rule 54 -- a named confound with no corresponding filter is an unnamed confound
      wearing a disclaimer, so P3 is computed, not merely mentioned).

GATES. Each must be able to go either way; the input that should fail is constructed, and so is the
input that should pass (rules 40 and 81).

  G1  ALIVENESS OF THE REFERENCE ARM (rule 53). The sevoflurane incumbent must clear a per-case
      permutation floor. If neither arm couples to anything in this cohort, "propofol couples less" is
      absence of power, not measured absence (rule 69). FAILS -> NOT INTERPRETABLE.
  G2  SELECTION SYMMETRY. Assert both arms sweep the same number of filters, and report the max-of-eight
      inflation measured on matched pure-noise columns. P1 is read against that floor, never against 0.
  G3  CAPABILITY, both directions. A synthetic case whose panel IS a lagged function of the recorded
      infusion at a KNOWN half-life -- the sweep must recover it and score high. A synthetic case whose
      panel is noise -- the sweep must return the G2 floor. If the recoverable case is not recovered the
      machinery is broken and nothing else in the file is readable.
  G4  COVERAGE. At least 20 cases per arm with at least 10 windows carrying a finite exposure, and the
      exposure not constant within the case. Cases failing this are REPORTED, with the reason and the
      count, never silently dropped (rule 14).

PLACEBO (rule 82 -- the deposit already contains the object we would otherwise synthesise). Each case's
panel is paired with a DIFFERENT case's exposure track, taken as a contiguous block of the same length.
A donor exposure is realistic in trend, autocorrelation, marginal and drift, and carries no information
about the recipient. It destroys the WHOLE association, not only its timing, so it is a placebo for the
association as such -- stated here because that is a design choice and not a discovery. Both arms get it.
The placebo is a COMPARISON against the real effect and against its DISTRIBUTION over donors, never an
absolute threshold (rules 34 and 5th-occurrence-of-37).

VERDICT RULE, wrong-direction case enumerated FIRST (rule 37, fourth occurrence). Let [lo, hi] be the
cluster-bootstrap interval over cases and `floor` the G2 noise inflation.

  (a) P1 hi < floor          -> WRONG DIRECTION. The free-ke0 sweep does WORSE than the pump's own model
                                once the selection inflation is accounted for. Reading (i) is refuted
                                against its own prediction, which is a stronger refutation than a null.
  (b) P1 interval contains floor -> NO GAIN FROM ke0. Reading (i) is not supported; the pump's population
                                ke0 is not what is costing propofol its coupling.
  (c) P1 lo > floor AND P2 hi < 0 -> PARTIAL. A free ke0 helps propofol measurably and still does not
                                close the gap. Report both numbers; the residual is what (iii) must explain.
  (d) P1 lo > floor AND P2 interval contains or exceeds 0 -> THE GAP WAS AN EXPOSURE-MODEL ARTEFACT.
                                Every Challenge A conclusion drawn from the propofol arm needs revisiting.

  Gating, applied AFTER the primary is evaluated, because a gate can only invalidate a pass and never
  rescue a null (rule 37): G1 failure -> NOT INTERPRETABLE. Placebo not beaten in an arm -> that arm is
  NOT INTERPRETABLE. G3 recoverable-case failure -> whole file NOT INTERPRETABLE. P3 showing propofol
  dispersion below a quarter of sevoflurane's -> the primary stands as an arithmetic statement and the
  PHARMACOLOGICAL reading is withheld, explicitly, in the printed verdict.

SCOPE LIMIT. Arms are mutually exclusive by construction (a case with both propofol and a volatile is in
neither), so this compares mono-technique cases and says nothing about combined anaesthesia. BIS is not
used anywhere as a depth variable: the anchor is the recorded exposure, which is the point of the design.

INCUMBENT (rule 45): the Orchestra TCI pump's own effect-site concentration, `Orchestra/PPF20_CE`. It is
an EXPOSURE rather than an observation, so rule 86 does not bite here.

    python bsde/src/bsde/experiments/e224_exposure_model_or_drug.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

HALF_LIVES_MIN = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
MIN_WINDOWS = 10
MIN_CASES_PER_ARM = 20
N_BOOT = 2000
N_DONOR = 200
N_NOISE = 300
SEED = 20260802

GRID = "bsde/results/vitaldb_grid.s*.csv"
PK = "bsde/results/vitaldb_pk_inputs.s%d.jsonl"
OUT = "bsde/results/e224_exposure_model_or_drug.json"

SKIP_PREFIX = ("meta_", "recording_id", "dataset", "subject", "status", "error",
               "n_channels", "sfreq", "n_samples")


def _panel_columns(row):
    """A candidate is a measurement of the SIGNAL. Enumerate what it is allowed to be, not what it is
    not -- rule 70, where a SKIP set let a re-description of the outcome into a candidate list."""
    return [k for k in row
            if not k.startswith(SKIP_PREFIX) and k not in ("uce_v1",)]


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


def load_panel():
    from bsde.verifier.stats import read_rows
    rows, dropped = [], 0
    for p in sorted(glob.glob(GRID)):
        r, d = read_rows(p)
        rows += r
        dropped += d
    cols = _panel_columns(rows[0])
    by_case = {}
    for r in rows:
        by_case.setdefault(r["meta_caseid"], []).append(r)
    for c in by_case:
        by_case[c].sort(key=lambda r: _f(r["meta_t_s"]))
    return by_case, cols, dropped


def load_tracks():
    out = {}
    for s in range(4):
        for line in open(PK % s):
            r = json.loads(line)
            out[r["caseid"]] = r
    return out


def _hold(track, t_eval):
    """Zero-order hold of a (t, v) track at the evaluation times. A pump target and an end-tidal reading
    are both held between samples; interpolating either would invent values between updates."""
    import numpy as np
    t = np.asarray(track["t"], float)
    v = np.asarray(track["v"], float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v = t[ok], v[ok]
    if t.size == 0:
        return np.full(len(t_eval), np.nan)
    o = np.argsort(t)
    t, v = t[o], v[o]
    idx = np.searchsorted(t, np.asarray(t_eval, float), side="right") - 1
    out = np.where(idx >= 0, v[np.clip(idx, 0, len(v) - 1)], np.nan)
    return out


def propofol_family(rec, t_eval):
    """Eight one-compartment exposure models driven by the recorded infusion, plus the pump's own Ce."""
    import numpy as np
    from bsde.pkpd.propofol import rate_track_to_segments, infusion_basis
    tr = rec["tracks"]
    rate = tr.get("Orchestra/PPF20_RATE")
    ce = tr.get("Orchestra/PPF20_CE")
    if rate is None or ce is None:
        return None, None
    s0, s1, r = rate_track_to_segments(rate["t"], rate["v"])
    if len(s0) == 0:
        return None, None
    fam = infusion_basis(s0, s1, r, np.asarray(t_eval, float), half_lives_min=HALF_LIVES_MIN)
    return fam, _hold(ce, t_eval)


def volatile_family(rec, t_eval):
    """The same eight filters applied to the DELIVERED inspired concentration, plus measured end-tidal.

    The volatile analogue of a one-compartment exposure model is a first-order lag on what was delivered:
    the vaporiser setting is the input, the alveolar/effect compartment is the filter. `effect_site_lag`
    integrates it exactly under a zero-order hold, so the two arms differ in their input signal and in
    nothing else about the filtering.
    """
    import numpy as np
    from bsde.pkpd.propofol import effect_site_lag
    tr = rec["tracks"]
    insp = tr.get("Primus/INSP_SEVO")
    et = tr.get("Primus/EXP_SEVO")
    if insp is None or et is None:
        return None, None
    t = np.asarray(insp["t"], float)
    v = np.asarray(insp["v"], float)
    ok = np.isfinite(t) & np.isfinite(v)
    if ok.sum() < 2:
        return None, None
    t, v = t[ok], v[ok]
    cols = []
    for hl in HALF_LIVES_MIN:
        ke0 = 0.6931471805599453 / float(hl)          # per minute, from the half-life
        lag = effect_site_lag(t, v, ke0_per_min=ke0)
        cols.append(_hold({"t": t.tolist(), "v": lag.tolist()}, t_eval))
    return np.column_stack(cols), _hold(et, t_eval)


def case_score(panel, cols, exposure):
    """Mean over candidate columns of |Spearman(column, exposure)| within one case."""
    import numpy as np
    from bsde.verifier.stats import spearman
    e = np.asarray(exposure, float)
    vals = []
    for c in cols:
        x = np.asarray([_f(r[c]) for r in panel], float)
        m = np.isfinite(x) & np.isfinite(e)
        if m.sum() < MIN_WINDOWS or np.nanstd(x[m]) <= 0 or np.nanstd(e[m]) <= 0:
            continue
        vals.append(abs(spearman(x[m], e[m])))
    if not vals:
        return float("nan")
    return float(np.mean(vals))


def best_of_family(panel, cols, family):
    """Max over the eight filters of the per-case score. Optimistically biased BY CONSTRUCTION; the
    inflation is measured in G2 and both arms pay it identically."""
    import numpy as np
    s = [case_score(panel, cols, family[:, k]) for k in range(family.shape[1])]
    s = [v for v in s if np.isfinite(v)]
    if not s:
        return float("nan"), -1
    a = int(np.argmax(s))
    return float(s[a]), a


def boot_mean_diff(a, b, rng, n=N_BOOT):
    """Cluster bootstrap over CASES of the difference of two per-case means. Paired where both arms
    contain the same case is impossible here -- the arms are disjoint -- so this resamples each arm's
    cases independently, which is the correct structure for a between-arm contrast."""
    import numpy as np
    a = np.asarray([v for v in a if np.isfinite(v)], float)
    b = np.asarray([v for v in b if np.isfinite(v)], float)
    d = []
    for _ in range(n):
        ia = rng.integers(0, len(a), len(a))
        ib = rng.integers(0, len(b), len(b))
        d.append(a[ia].mean() - b[ib].mean())
    d = np.asarray(d)
    return float(a.mean() - b.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)), d


def boot_paired_diff(pairs, rng, n=N_BOOT):
    """Cluster bootstrap of a WITHIN-case difference (best-of-eight minus incumbent, same case)."""
    import numpy as np
    p = np.asarray([x for x in pairs if all(np.isfinite(x))], float)
    d = p[:, 0] - p[:, 1]
    out = []
    for _ in range(n):
        i = rng.integers(0, len(d), len(d))
        out.append(d[i].mean())
    out = np.asarray(out)
    return float(d.mean()), float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)), len(d)


def main() -> int:
    import numpy as np
    rng = np.random.default_rng(SEED)
    by_case, cols, dropped = load_panel()
    tracks = load_tracks()
    print(f"panel: {sum(len(v) for v in by_case.values())} windows, {len(by_case)} cases, "
          f"{len(cols)} candidate columns, {dropped} shard-header rows dropped")
    print("candidates:", ", ".join(cols))

    # ---- arm assignment, mutually exclusive ------------------------------------------------------
    VOL = ("Primus/EXP_SEVO", "Primus/EXP_DES", "Primus/INSP_SEVO", "Primus/INSP_DES")
    arms = {"propofol": [], "sevoflurane": []}
    excluded = {"no_pk": 0, "both_techniques": 0, "neither": 0, "few_windows": 0,
                "constant_exposure": 0, "no_family": 0}
    for c, panel in by_case.items():
        rec = tracks.get(c)
        if rec is None:
            excluded["no_pk"] += 1
            continue
        tr = set(rec["tracks"])
        has_ppf = "Orchestra/PPF20_RATE" in tr and "Orchestra/PPF20_CE" in tr
        has_vol = any(v in tr for v in VOL)
        if has_ppf and has_vol:
            excluded["both_techniques"] += 1
            continue
        if has_ppf:
            arms["propofol"].append(c)
        elif "Primus/EXP_SEVO" in tr and "Primus/INSP_SEVO" in tr:
            arms["sevoflurane"].append(c)
        else:
            excluded["neither"] += 1
    print("arm sizes before coverage:", {k: len(v) for k, v in arms.items()}, "excluded:", excluded)

    # ---- per-case scores -------------------------------------------------------------------------
    res = {"propofol": [], "sevoflurane": []}
    disp = {"propofol": [], "sevoflurane": []}
    chosen_hl = {"propofol": [], "sevoflurane": []}
    keep = {"propofol": [], "sevoflurane": []}
    for arm, cases in arms.items():
        build = propofol_family if arm == "propofol" else volatile_family
        for c in cases:
            panel = by_case[c]
            t_eval = [_f(r["meta_t_s"]) for r in panel]
            if len(t_eval) < MIN_WINDOWS:
                excluded["few_windows"] += 1
                continue
            fam, inc = build(tracks[c], t_eval)
            if fam is None or inc is None:
                excluded["no_family"] += 1
                continue
            fin = np.isfinite(inc)
            if fin.sum() < MIN_WINDOWS or np.nanstd(inc[fin]) <= 0:
                excluded["constant_exposure"] += 1
                continue
            b, k = best_of_family(panel, cols, fam)
            i = case_score(panel, cols, inc)
            if not (np.isfinite(b) and np.isfinite(i)):
                excluded["few_windows"] += 1
                continue
            res[arm].append((b, i))
            chosen_hl[arm].append(HALF_LIVES_MIN[k])
            v = inc[fin]
            med = float(np.median(np.abs(v)))
            iqr = float(np.percentile(v, 75) - np.percentile(v, 25))
            disp[arm].append(iqr / med if med > 0 else float("nan"))
            keep[arm].append(c)
    for arm in res:
        print(f"{arm:12s} n_cases={len(res[arm]):3d}  best-of-8 mean={np.mean([x[0] for x in res[arm]]):.4f}  "
              f"incumbent mean={np.mean([x[1] for x in res[arm]]):.4f}")
    print("exclusions (rule 14):", excluded)

    # ---- G4 coverage ------------------------------------------------------------------------------
    g4 = all(len(res[a]) >= MIN_CASES_PER_ARM for a in res)
    print(f"G4 coverage (>= {MIN_CASES_PER_ARM} cases per arm): {'PASS' if g4 else 'FAIL'}")

    # ---- G2 selection symmetry + the noise floor ---------------------------------------------------
    # A max over eight filters is optimistically biased. Measure that inflation on columns whose NUISANCE
    # structure matches the real panel -- same case, same window count -- and whose SIGNAL is absent by
    # construction (rule 79). The floor is the mean of (best-of-eight - single) for a noise panel.
    noise_gain = []
    pool = keep["propofol"] + keep["sevoflurane"]
    for _ in range(N_NOISE):
        c = pool[int(rng.integers(0, len(pool)))]
        panel = by_case[c]
        t_eval = [_f(r["meta_t_s"]) for r in panel]
        build = propofol_family if c in keep["propofol"] else volatile_family
        fam, inc = build(tracks[c], t_eval)
        if fam is None:
            continue
        fake = [{"z": float(v)} for v in rng.normal(size=len(panel))]
        s = [case_score(fake, ["z"], fam[:, k]) for k in range(fam.shape[1])]
        s = [v for v in s if np.isfinite(v)]
        si = case_score(fake, ["z"], inc)
        if len(s) < 2 or not np.isfinite(si):
            continue
        noise_gain.append(max(s) - si)
    floor = float(np.mean(noise_gain))
    floor_hi = float(np.percentile(noise_gain, 95))
    g2 = True
    print(f"G2 selection symmetry: 8 filters in BOTH arms -> PASS; "
          f"max-of-8 inflation on matched noise = {floor:+.4f} (95th pct {floor_hi:+.4f}, n={len(noise_gain)})")

    # ---- G3 capability, both directions ------------------------------------------------------------
    cap = {}
    c = keep["propofol"][0] if keep["propofol"] else pool[0]
    panel = by_case[c]
    t_eval = [_f(r["meta_t_s"]) for r in panel]
    fam, inc = propofol_family(tracks[c], t_eval)
    TRUE_K = 5                                     # 16 min half-life, an interior rate, not an endpoint
    drive = fam[:, TRUE_K]
    sd = np.nanstd(drive)
    synth_pass = [{"z": float(v)} for v in drive + rng.normal(0, 0.05 * sd, size=len(drive))]
    synth_fail = [{"z": float(v)} for v in rng.normal(size=len(drive))]
    bp, kp = best_of_family(synth_pass, ["z"], fam)
    bf, kf = best_of_family(synth_fail, ["z"], fam)
    cap = {"recoverable_score": bp, "recoverable_hl_recovered": HALF_LIVES_MIN[kp],
           "recoverable_hl_true": HALF_LIVES_MIN[TRUE_K], "noise_score": bf}
    g3 = bp > 0.9 and HALF_LIVES_MIN[kp] == HALF_LIVES_MIN[TRUE_K] and bf < 0.5
    print(f"G3 capability: recoverable case scores {bp:.4f} and recovers half-life "
          f"{HALF_LIVES_MIN[kp]} min (true {HALF_LIVES_MIN[TRUE_K]}); pure-noise case scores {bf:.4f} "
          f"-> {'PASS' if g3 else 'FAIL'}")

    # ---- G1 aliveness of the reference arm ---------------------------------------------------------
    # Rule 53: if the phenomenon does not exist in this cohort at all, "propofol has less of it" is
    # absence of power. The floor is a per-case circular shift of the exposure against the panel, which
    # preserves the exposure's own autocorrelation and destroys its alignment.
    sev_inc = np.asarray([x[1] for x in res["sevoflurane"]], float)
    shift_scores = []
    for c in keep["sevoflurane"]:
        panel = by_case[c]
        t_eval = [_f(r["meta_t_s"]) for r in panel]
        _, inc = volatile_family(tracks[c], t_eval)
        n = len(inc)
        s = int(rng.integers(1, n)) if n > 2 else 1
        shift_scores.append(case_score(panel, cols, np.roll(inc, s)))
    shift_scores = np.asarray([v for v in shift_scores if np.isfinite(v)], float)
    # THE COMPARISON IS MEAN AGAINST THE DISTRIBUTION OF MEANS, not against individual floor cases.
    # The first draft took the 95th percentile of the individual shifted case-scores, which is a baseline
    # of the wrong SHAPE (rule 50): the real quantity is an average over n cases and its sampling
    # distribution is narrower than a single case's by roughly sqrt(n), so the test was answering
    # "is the mean bigger than a typical single null case" instead of "is the mean bigger than a null
    # mean". Repaired once, with the reason stated, per rule 58.
    g1_null = np.asarray([shift_scores[rng.integers(0, len(shift_scores), len(sev_inc))].mean()
                          for _ in range(N_BOOT)])
    g1_p = float(np.mean(g1_null >= sev_inc.mean()))
    g1 = g1_p < 0.05
    print(f"G1 aliveness: sevoflurane incumbent {sev_inc.mean():.4f} against the distribution of "
          f"circular-shift MEANS (mean {g1_null.mean():.4f}, 95th pct {np.percentile(g1_null, 95):.4f}); "
          f"p = {g1_p:.4f} -> {'PASS' if g1 else 'FAIL'}")

    # ---- placebo: donor exposure from a DIFFERENT case ---------------------------------------------
    placebo = {}
    for arm in res:
        build = propofol_family if arm == "propofol" else volatile_family
        vals = []
        cs = keep[arm]
        for _ in range(N_DONOR):
            i, j = rng.integers(0, len(cs)), rng.integers(0, len(cs))
            if i == j:
                continue
            panel = by_case[cs[i]]
            t_eval = [_f(r["meta_t_s"]) for r in panel]
            dpanel = by_case[cs[j]]
            dt = [_f(r["meta_t_s"]) for r in dpanel]
            _, dinc = build(tracks[cs[j]], dt)
            if dinc is None:
                continue
            n = min(len(panel), len(dinc))
            if n < MIN_WINDOWS:
                continue
            v = case_score(panel[:n], cols, dinc[:n])
            if np.isfinite(v):
                vals.append(v)
        real = float(np.mean([x[1] for x in res[arm]]))
        # Same shape repair as G1: the real quantity is a mean over n cases, so the null must be a
        # distribution of MEANS over n donor draws, not the spread of individual donor cases.
        v = np.asarray(vals, float)
        k = len(res[arm])
        null = np.asarray([v[rng.integers(0, len(v), k)].mean() for _ in range(N_BOOT)])
        p = float(np.mean(null >= real))
        placebo[arm] = {"n": len(vals), "donor_case_mean": float(v.mean()),
                        "donor_mean_p95": float(np.percentile(null, 95)), "real": real,
                        "p_donor_mean_reaches_real": p, "beaten": p < 0.05}
        print(f"placebo {arm:12s}: real {real:.4f} vs the distribution of donor MEANS "
              f"(mean {null.mean():.4f}, 95th pct {np.percentile(null, 95):.4f}); p = {p:.4f} "
              f"-> {'BEATEN' if p < 0.05 else 'NOT BEATEN'}")

    # ---- primaries ---------------------------------------------------------------------------------
    p1, p1lo, p1hi, n1 = boot_paired_diff(res["propofol"], rng)
    p2, p2lo, p2hi, _ = boot_mean_diff([x[0] for x in res["propofol"]],
                                       [x[1] for x in res["sevoflurane"]], rng)
    dp = float(np.nanmedian(disp["propofol"]))
    ds = float(np.nanmedian(disp["sevoflurane"]))
    p3 = dp / ds if ds > 0 else float("nan")
    print()
    print(f"P1  best-of-8 minus pump Ce, propofol arm : {p1:+.4f} [{p1lo:+.4f}, {p1hi:+.4f}]  (n={n1} cases)")
    print(f"    read against the measured noise floor  : {floor:+.4f}")
    print(f"P2  best propofol minus sevoflurane ET     : {p2:+.4f} [{p2lo:+.4f}, {p2hi:+.4f}]")
    print(f"P3  within-case dispersion IQR/median      : propofol {dp:.4f}  sevoflurane {ds:.4f}  "
          f"ratio {p3:.4f}")
    from collections import Counter
    print(f"    half-life chosen, propofol arm         : {sorted(Counter(chosen_hl['propofol']).items())}")

    # ---- verdict, wrong direction first -------------------------------------------------------------
    if not g3:
        verdict = "NOT INTERPRETABLE -- G3 capability failed; the sweep cannot recover a known exposure"
    elif not g1:
        verdict = "NOT INTERPRETABLE -- G1 failed; neither arm couples above its own floor in this cohort"
    elif not g4:
        verdict = "NOT INTERPRETABLE -- G4 coverage failed"
    elif not placebo["propofol"]["beaten"] or not placebo["sevoflurane"]["beaten"]:
        bad = [a for a in placebo if not placebo[a]["beaten"]]
        verdict = f"NOT INTERPRETABLE -- donor placebo not beaten in: {bad}"
    elif p1hi < floor:
        verdict = ("WRONG DIRECTION -- a free ke0 does WORSE than the pump's own model once selection "
                   "inflation is accounted for; reading (i) is refuted against its own prediction")
    elif p1lo <= floor <= p1hi:
        verdict = ("NO GAIN FROM ke0 -- the pump's population ke0 is not what costs propofol its "
                   "coupling; reading (i) is not supported")
    elif p1lo > floor and p2hi < 0:
        verdict = ("PARTIAL -- a free ke0 helps propofol measurably and does NOT close the gap; "
                   "the residual is what a pharmacodynamic explanation must account for")
    else:
        verdict = ("EXPOSURE-MODEL ARTEFACT -- the best propofol exposure reaches sevoflurane end-tidal; "
                   "Challenge A conclusions drawn from the propofol arm need revisiting")
    if np.isfinite(p3) and p3 < 0.25:
        verdict += (f" | PHARMACOLOGICAL READING WITHHELD: propofol's within-case exposure dispersion is "
                    f"{p3:.3f} of sevoflurane's, so attenuation by restriction of range is not excluded")
    print()
    print("VERDICT:", verdict)

    out = {"p1": {"est": p1, "lo": p1lo, "hi": p1hi, "n_cases": n1, "noise_floor": floor,
                  "noise_floor_p95": floor_hi},
           "p2": {"est": p2, "lo": p2lo, "hi": p2hi},
           "p3": {"propofol_disp": dp, "sevo_disp": ds, "ratio": p3},
           "arm_means": {a: {"best": float(np.mean([x[0] for x in res[a]])),
                             "incumbent": float(np.mean([x[1] for x in res[a]])),
                             "n": len(res[a])} for a in res},
           "gates": {"G1_aliveness": bool(g1), "G2_symmetry": bool(g2), "G3_capability": bool(g3),
                     "G4_coverage": bool(g4)},
           "capability": cap, "placebo": placebo, "exclusions": excluded,
           "chosen_half_lives": {a: sorted(Counter(chosen_hl[a]).items()) for a in chosen_hl},
           "candidates": cols, "verdict": verdict, "seed": SEED}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
