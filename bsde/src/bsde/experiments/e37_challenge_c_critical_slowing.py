#!/usr/bin/env python3
"""E37 — Challenge C with a dynamical instrument: does critical slowing down precede loss of consciousness?

THE INSTRUMENT CHANGE, STATED FIRST, BECAUSE IT IS WHAT LICENSES THIS FILE AT ALL.

Four designs have asked Challenge C's question — can EEG see a transition coming before the depth index
does — and all four asked it the same way: **take the LEVEL of a spectral feature in a window and see
whether it discriminates.** E26 (300 s grid, negative, every gate passed), E27 (60 s grid, absent on base
rate), E33 (gate-failed: position-AUC 1.000), E34 (negative: PE31 adds +0.0178 [-0.0226, +0.0474] over
SEF95, an interval spanning zero, and its placebo landmark scored +0.0244 [-0.0440, +0.0935], also spanning
zero). `DISCOVERY_LOOP.md` §2 permits a successor to a failed experiment **only by changing the
instrument**, and the instrument here changes from *the level of a signal* to *the second-order statistics
of that signal's own trajectory*: rolling variance and lag-1 autocorrelation. Everything else — cohort,
label, horizon, landmark, placebo, incumbent — is E34's, unchanged, so that the comparison is attributable.

WHY SECOND-ORDER STATISTICS AND NOT ANOTHER FEATURE, AND WHY THE PREDICTION IS SIGNED IN ADVANCE.

The prediction is not fitted here and it is not this project's. Steyn-Ross, Steyn-Ross, Sleigh and Whiting,
*Phys Rev E* 2003; 68:021902 (**PMID 14525001**, record verified through NCBI E-utilities, not WebFetch —
rules 25 and 39) model propofol-like GABAergic action as a prolongation of the inhibitory postsynaptic
impulse response and derive "a hysteretically separated pair of first-order phase transitions ... the first
occurring at the point of induction of unconsciousness". What they then state, and this is quoted rather
than paraphrased so that rule 42 is satisfiable by a reader:

    "We establish that the correlation length of the EEG fluctuations is expected to increase at the
     approach to the transition points, and this finding is consistent with both the homogeneous-cortex
     prediction of increased correlation time ('critical slowing down') near transition, and the recent,
     comprehensive anesthetic study by John et al. [Conscious. Cogn. 10, 165 (2001)] reporting an increase
     in EEG coherence near the points of loss and recovery of consciousness."

Bukoski, Steyn-Ross, Pickett and Steyn-Ross, *Phys Rev E* 2018; 97:062403 (**PMID 30011536**, likewise
verified) reach the same signature from a stochastic Hodgkin-Huxley point neuron: "increasing the magnitude
of anesthetic-induced inhibition is associated with augmented signatures of critical slowing: fluctuation
amplitudes and correlation times grow as spectral power is increasingly focused at 0 Hz."

So the theory says three things rise on approach to induction: **correlation time, fluctuation amplitude,
and coherence.** Those map onto lag-1 autocorrelation, variance, and `sync_alpha`. The directions are
therefore fixed by a published model before any DOSE-I row is read, and P4 tests the SIGN, which is the part
that cannot be rescued by discrimination. **E34 found every spectral feature it tracked FALLING toward the
loss** (SEF95 -1.02, PE31 -0.048, MF -0.300, rel_gamma -0.335), so a rise here is not the default outcome.

**WHAT IS NOT TESTED, AND IT IS HALF THE THEORY.** Steyn-Ross's own primary result is *spatial* — the
correlation LENGTH across cortex. DOSE-I ships single-site derived features at 1 Hz, so the spatial half is
untestable here and no result of this file speaks to it. Only the temporal half (correlation time,
fluctuation amplitude) and the coherence proxy are in scope. A negative here is a negative about temporal
critical slowing in a frontal montage, not about the phase-transition model.

THE BASE SIGNAL IS THE INCUMBENT ITSELF, AND THAT IS A DESIGN CHOICE WITH A PURPOSE.

Variance and autocorrelation have to be computed on something, and choosing that something is a researcher
degree of freedom the previous four files did not have. It is removed by fiat: **the EWS statistics are
computed on SEF95, the incumbent.** The question then becomes exactly "is there information in the
incumbent's own trajectory that the incumbent's level discards?" — which is the sharpest form Challenge C
can take on this deposit, and which no alternative choice of base signal could make more favourable, because
the comparator is the same series.

PREPROCESSING, FIXED HERE. Both constants are declared before the run and neither is swept for the primary.

    DETREND_S = 300   trailing rolling mean subtracted from SEF95 before anything is measured. Variance and
                      autocorrelation of a TRENDING series measure the trend, not the fluctuations; every
                      early-warning-signal protocol detrends first and this one says at what scale.
    EWS_W     = 60    trailing window over which the residual's variance and lag-1 autocorrelation are
                      computed. Sixty seconds is the horizon, so the estimator and the question share a
                      timescale rather than being tuned against each other.

A window is scored only if enough of the trailing DETREND_S + EWS_W samples are present and the samples are
**contiguous in time**. That last clause is error-catalogue rule 27 and it is the reason the EWS series is
built on the WHOLE recording and only afterwards restricted to conscious windows: masking to `SOC == 1`
first would glue unconscious stretches together and manufacture autocorrelation across a discontinuity.
G1(d) checks 1 Hz contiguity in every contributing file rather than assuming it.

--------------------------------------------------------------------------------------------------------
FIRST RUN: G1 FAILED ON COVERAGE AT 28 RECORDINGS AGAINST A FLOOR OF 50, AND THE CAUSE WAS THIS FILE'S
ESTIMATOR RATHER THAN THE DEPOSIT. Recorded here rather than overwritten (rule 3), and note what was and
was not known when the fix was made: **the gate failed before any candidate was scored**, so no
candidate-outcome relationship had been observed when the estimator was changed. That is the only
circumstance in which changing it is not a goalpost move, and it is why gates are evaluated first.

    (a) 28 recordings, floor 50.     (b) base rate 20.2 %, inside the band.
    (c) position-AUC 0.324, distance 0.176 against a ceiling of 0.20 — passed, but not by much.
    (d) 0 files rejected as non-1 Hz — the deposit is strictly 1 Hz throughout, as sampled.
    (e) all three statistics varied; 28 recordings with >= 10 distinct values, against a floor of 40.

Diagnosis, run on the label and missingness channels only: **SEF95 is NaN in 13.2 % of samples, scattered
rather than blocked.** The first version required all 360 trailing samples (300 s detrend + 60 s window) to
be finite, and that requirement removed **84 % of conscious windows — 45,304 down to 7,427**. `sync_alpha`
contributed nothing to the loss (0 additional windows).

**The requirement was wrong, and wrong in the direction of rule 27 rather than against it.** What rule 27
forbids is computing autocorrelation ACROSS a discontinuity. Requiring every sample to be present is a
blunt way of avoiding that, and it discards a window because of a hole that a correct estimator can simply
skip. The corrected estimator computes the lag-1 term from **adjacent pairs that are both present**, so a
pair straddling a hole is never formed, and requires a declared minimum coverage instead of totality:

    MIN_COVER  = 0.80   of both the detrend window and the EWS window must be present
    MIN_PAIRS  = 30     adjacent both-present pairs before a lag-1 estimate is issued

Nothing else moves. The label, horizon, directions, primary, incumbent, landmark, placebo and every numeric
floor in G1 are unchanged, and the two new constants are declared here before the re-run.

**AND A GATE IS ADDED RATHER THAN RELAXED.** Dropping 13 % of samples raises a question the first version
never asked: is SEF95 missing MORE OFTEN near a loss of consciousness? If so the exclusion is
outcome-related and the surviving windows are a biased sample of the question (rule 14). G1(f) now tests it
directly — the AUC of the "this window has insufficient EWS coverage" indicator against the label, over all
conscious windows, must sit within MAX_EXCLUSION_AUC_DIST of chance. This check makes the design harder to
pass than it was on the run that failed.

SEARCH SPACE. **Three candidates** — `ar1_sef95`, `var_sef95`, `sync_alpha` — one primary (`ar1_sef95`,
because correlation time is the quantity the phrase "critical slowing down" names), two co-reported. Three
sensitivity windows (30, 60, 120 s) are reported for the primary as context and the primary stays at 60.
Multiplicity across the three candidates is reported through `verifier/multiplicity.py`.

REGISTERED BEFORE ANY DOSE-I ROW IS READ BY THIS FILE. Evaluated in this order, failing branch written first.

  G1  MACHINERY GATE, no candidate consulted.
      (a) at least MIN_RECORDINGS recordings contribute;
      (b) base rate of "LOC within 60 s" inside (0.05, 0.95);
      (c) position-AUC of the label within MAX_POSITION_AUC_DIST of chance — the check E33 failed at 1.000
          and the reason E34 exists;
      (d) every contributing file is strictly 1 Hz contiguous (rule 27);
      (f) **the EWS coverage exclusion is not outcome-related** — AUC of "insufficient coverage" against
          the label, over all conscious windows, within MAX_EXCLUSION_AUC_DIST of chance (rule 14). Added
          after the first run's estimator correction and before the re-run; see the note above.
      (e) **the EWS statistics VARY** — interquartile range above zero for both, and at least
          MIN_EWS_SUBJECTS recordings in which the primary takes at least 10 distinct values. Rule 32: two
          whole ledger entries were spent comparing a measure against a flag that was present in 100.0 % of
          the analysis cohort, and this clause is the cheap check that would have caught it.
      If any part fails, nothing downstream is reported: ABSENT, not negative (rule 31).

  P2  THE INCUMBENT, printed before any candidate. SEF95's own out-of-fold AUC for the same label. E34
      measured 0.610 [0.571, 0.650] on this cohort and label; a materially different number here means the
      cohort changed and the comparison to E34 is void.

  P3a PRIMARY AGAINST CHANCE. `ar1_sef95`, out-of-fold with subject-level folds, DIRECTIONAL — scored as
      "higher AR1 in the windows preceding a loss", per Steyn-Ross. A candidate firing in the opposite
      direction scores BELOW 0.5 and is refuted, not rewarded (`directional_auc`, not `auc_abs`).

  P3b PRIMARY AGAINST THE INCUMBENT. Out-of-bag AUC increment of {SEF95, ar1_sef95} over {SEF95}, clustered
      on recording, refit on the drawn resample and evaluated on the recordings NOT drawn (rule 9). FAILS if
      the interval includes 0.

  P4  THE SIGN TEST, which is the theory's actual content. Within each recording, the median change in each
      EWS statistic over the 120 s approaching each loss. Steyn-Ross predicts POSITIVE for all three. This
      is reported for every candidate and is the sentence that survives if the AUCs are null.

  P5  PLACEBO GATE, evaluated after the primary and gating the verdict (rule 34). E34's fake landmark at a
      matched relative position in each recording. FAILS — and the primary is WITHDRAWN — if the placebo
      increment reaches the real one. E34's did, which is precisely why this gate is not optional.

  P6  LEAD TIME, reported only if P3a and P5 both pass.

VERDICT RULE, written before the run and stating the failing case first.

    NOT INTERPRETABLE  G1 failed.
    NOT MET            P3a's interval includes 0.5, or P3b's includes 0, or the placebo reaches the real
                       increment. **P4's sign is reported regardless**, because a refuted direction is
                       itself a result about the Steyn-Ross prediction and does not depend on any AUC.
    MET                P3a above chance in the DECLARED direction, P3b's interval excluding 0, and the
                       placebo below the real increment. Permitted sentence: *"the trajectory of SEF95
                       carries information about imminent loss of consciousness that its level does not,
                       in the direction a phase-transition model predicts."* Forbidden: any claim about
                       BIS, which is not in this deposit, and any claim about spatial correlation length.

SCOPE LIMIT. DOSE-I, procedural sedation with propofol, single-site derived pEEG at 1 Hz; `SOC` is the
deposit's own consciousness flag and this file inherits whatever defines it; the incumbent is SEF95, not a
commercial depth index. Claim scope is "ahead of SEF95", never "ahead of BIS" — E34's wording, kept.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import os
import sys
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance")))

from bsde.verifier.stats import (auc, cluster_bootstrap_ci, cv_predict_proba,           # noqa: E402
                                 directional_auc, oob_auc_increment)
from bsde.verifier.multiplicity import westfall_young_maxt                              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
OUT = os.path.join(RESULTS, "e37_challenge_c_critical_slowing.json")

INCUMBENT = "SEF95"
BASE = "SEF95"
PRIMARY = "ar1_sef95"
CANDIDATES = ("ar1_sef95", "var_sef95", "sync_alpha")
DIRECTION = {"ar1_sef95": "higher", "var_sef95": "higher", "sync_alpha": "higher"}
"""All three declared HIGHER before the run, from PMID 14525001 and PMID 30011536. See the header."""

HORIZON_S = 60
DETREND_S = 300
EWS_W = 60
SENSITIVITY_W = (30, 60, 120)
MIN_RECORDINGS = 50
MIN_CONSCIOUS_S = 200
MIN_EWS_SUBJECTS = 40
BASE_RATE_BAND = (0.05, 0.95)
MAX_POSITION_AUC_DIST = 0.20
MIN_COVER = 0.80
MIN_PAIRS = 30
MAX_EXCLUSION_AUC_DIST = 0.10
APPROACH_S = 120
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _trailing_mean(x, w, min_cover=None):
    """Mean of the trailing `w` samples ending at each index, over the samples that are PRESENT.

    NaN until at least `min_cover * w` of them exist. The time axis is verified 1 Hz contiguous by G1(d),
    so a missing sample is a hole in the measurement rather than a jump in time, and averaging over the
    present samples is the right thing; what would be wrong is forming a lag-1 pair across the hole, and
    that is `_ews`'s job rather than this one's.
    """
    need = w if min_cover is None else int(np.ceil(min_cover * w))
    n = x.size
    fin = np.isfinite(x)
    c = np.concatenate(([0.0], np.cumsum(np.where(fin, x, 0.0))))
    k = np.concatenate(([0], np.cumsum(fin.astype(int))))
    out = np.full(n, np.nan)
    idx = np.arange(w - 1, n)
    cnt = k[idx + 1] - k[idx + 1 - w]
    ok = cnt >= need
    out[idx[ok]] = (c[idx + 1] - c[idx + 1 - w])[ok] / cnt[ok]
    return out


def _ews(resid, w, min_cover, min_pairs):
    """Trailing-window variance and lag-1 autocorrelation of `resid`, tolerant of scattered holes.

    Variance is taken over the present samples. The lag-1 term is accumulated ONLY over adjacent pairs in
    which both members are present, so a pair straddling a hole is never formed — which is what rule 27
    actually forbids. Requiring every sample instead cost 84 % of the conscious windows on the first run
    and bought no additional correctness; see the header.
    """
    n = resid.size
    fin = np.isfinite(resid)
    x = np.where(fin, resid, 0.0)
    k = np.concatenate(([0], np.cumsum(fin.astype(int))))
    s1 = np.concatenate(([0.0], np.cumsum(x)))
    s2 = np.concatenate(([0.0], np.cumsum(x * x)))
    pair = fin[:-1] & fin[1:]
    pk = np.concatenate(([0], np.cumsum(pair.astype(int))))
    pxy = np.concatenate(([0.0], np.cumsum(np.where(pair, x[:-1] * x[1:], 0.0))))
    px = np.concatenate(([0.0], np.cumsum(np.where(pair, x[:-1], 0.0))))
    py = np.concatenate(([0.0], np.cumsum(np.where(pair, x[1:], 0.0))))
    pxx = np.concatenate(([0.0], np.cumsum(np.where(pair, x[:-1] * x[:-1], 0.0))))
    pyy = np.concatenate(([0.0], np.cumsum(np.where(pair, x[1:] * x[1:], 0.0))))

    var = np.full(n, np.nan)
    ar1 = np.full(n, np.nan)
    need = int(np.ceil(min_cover * w))
    for i in range(w - 1, n):
        a, b = i + 1 - w, i + 1
        cnt = k[b] - k[a]
        if cnt < need:
            continue
        m = (s1[b] - s1[a]) / cnt
        v = (s2[b] - s2[a]) / cnt - m * m
        if v <= 0:
            continue
        var[i] = v
        # pair indices a..b-2 correspond to pairs (a,a+1) .. (b-2,b-1)
        np_ = pk[b - 1] - pk[a]
        if np_ < min_pairs:
            continue
        sxy = pxy[b - 1] - pxy[a]
        sx = px[b - 1] - px[a]
        sy = py[b - 1] - py[a]
        sxx = pxx[b - 1] - pxx[a]
        syy = pyy[b - 1] - pyy[a]
        cx = sxx - sx * sx / np_
        cy = syy - sy * sy / np_
        if cx <= 0 or cy <= 0:
            continue
        ar1[i] = float((sxy - sx * sy / np_) / np.sqrt(cx * cy))
    return var, ar1


def _load(zip_path, ews_w=EWS_W):
    """Every conscious window with a valid EWS estimate, and its time to the NEXT loss.

    The EWS series is built on the WHOLE recording and only then restricted to conscious windows. Doing it
    the other way round would glue unconscious stretches together and manufacture autocorrelation across a
    discontinuity — error-catalogue rule 27.
    """
    z = zipfile.ZipFile(zip_path)
    recs, noncontig = [], []
    for nm in sorted(n for n in z.namelist() if n.endswith("_pEEG.csv")):
        rows = list(csv.DictReader(io.StringIO(z.read(nm).decode("utf-8-sig"))))
        if len(rows) < DETREND_S + ews_w + MIN_CONSCIOUS_S:
            continue
        rid = os.path.basename(nm).replace("_pEEG.csv", "")
        t = [datetime.datetime.fromisoformat(r["Time"]) for r in rows]
        step = np.array([(t[i + 1] - t[i]).total_seconds() for i in range(len(t) - 1)])
        if step.size and (step.min() != 1.0 or step.max() != 1.0):
            noncontig.append(rid)
            continue
        soc = np.array([_f(r.get("SOC", "")) for r in rows])
        base = np.array([_f(r.get(BASE, "")) for r in rows])
        sync = np.array([_f(r.get("sync_alpha", "")) for r in rows])
        trend = _trailing_mean(base, DETREND_S, MIN_COVER)
        resid = base - trend
        var, ar1 = _ews(resid, ews_w, MIN_COVER, MIN_PAIRS)
        losses = np.flatnonzero((soc[:-1] == 1) & (soc[1:] == 0))
        if losses.size == 0:
            continue
        has_ews = np.isfinite(ar1) & np.isfinite(var) & np.isfinite(sync) & np.isfinite(base)
        usable = (soc == 1) & has_ews
        conscious = np.flatnonzero(usable)
        if conscious.size < MIN_CONSCIOUS_S:
            continue
        # G1(f) channel: every conscious window, whether or not it has an EWS estimate, with the label it
        # would have carried. Built here so the exclusion can be tested for outcome-relatedness (rule 14).
        all_c = np.flatnonzero(soc == 1)
        ttl_all = np.full(all_c.size, np.inf)
        for k, c in enumerate(all_c):
            nxt = losses[losses >= c]
            if nxt.size:
                ttl_all[k] = float(nxt[0] - c)
        ttl = np.full(conscious.size, np.inf)
        for k, c in enumerate(conscious):
            nxt = losses[losses >= c]
            if nxt.size:
                ttl[k] = float(nxt[0] - c)
        recs.append({"id": rid, "pos": conscious, "n_samples": len(rows), "losses": losses,
                     "cols": {"ar1_sef95": ar1[conscious], "var_sef95": var[conscious],
                              "sync_alpha": sync[conscious], INCUMBENT: base[conscious]},
                     "full": {"ar1_sef95": ar1, "var_sef95": var, "sync_alpha": sync},
                     "ttl": ttl, "y": (ttl <= HORIZON_S).astype(float),
                     "excl_y": (ttl_all <= HORIZON_S).astype(float),
                     "excl_flag": (~has_ews[all_c]).astype(float)})
    return recs, noncontig


def _stack(recs, name):
    return (np.concatenate([r["cols"][name] for r in recs]),
            np.concatenate([r["y"] for r in recs]),
            np.concatenate([np.full(len(r["y"]), r["id"]) for r in recs]))


def main(argv=None) -> int:
    print("E37 — Challenge C with a dynamical instrument: critical slowing down before LOC")
    print("   Instrument change from E34: the SECOND-ORDER statistics of SEF95's trajectory, not its level.")
    print("   Directions declared in advance from PMID 14525001 / PMID 30011536: all three rise.")
    print("   CLAIM SCOPE: 'ahead of SEF95', never 'ahead of BIS'.")
    if not os.path.exists(PEEG_ZIP):
        print(f"\n   *** {os.path.basename(PEEG_ZIP)} absent.")
        return 2
    from feasibility import label_collinear_with_position

    recs, noncontig = _load(PEEG_ZIP)
    if not recs:
        print("\n   *** no recording survived loading.")
        return 1
    x_inc, y, grp = _stack(recs, INCUMBENT)
    rng = np.random.default_rng(SEED)
    st = {"experiment": "E37", "n_recordings": len(recs), "n_windows": int(len(y)),
          "detrend_s": DETREND_S, "ews_w": EWS_W, "horizon_s": HORIZON_S,
          "non_contiguous_files": noncontig}

    print("\n" + "=" * 100)
    print("G1 — MACHINERY GATE (no candidate-outcome relationship consulted)")
    print("=" * 100)
    base_rate = float(np.mean(y))
    col = label_collinear_with_position(y, grp)
    print(f"   (a) recordings contributing     : {len(recs)}   (floor {MIN_RECORDINGS})")
    print(f"       conscious windows with EWS  : {len(y)}")
    print(f"   (b) base rate (LOC within {HORIZON_S} s) : {base_rate:.1%}   (band {BASE_RATE_BAND})")
    print(f"   (c) position-AUC for the label  : {col['auc_of_position']:.3f}  "
          f"(distance {col['distance_from_chance']:.3f}, ceiling {MAX_POSITION_AUC_DIST})")
    print(f"   (d) files rejected as non-1 Hz  : {len(noncontig)}   {noncontig[:5]}")
    ex_y = np.concatenate([r["excl_y"] for r in recs])
    ex_f = np.concatenate([r["excl_flag"] for r in recs])
    ex_auc = float(auc(ex_y, ex_f)) if np.unique(ex_y).size > 1 else float("nan")
    ex_dist = abs(ex_auc - 0.5) if np.isfinite(ex_auc) else float("inf")
    print(f"   (f) exclusion-vs-label AUC      : {ex_auc:.3f}  (distance {ex_dist:.3f}, "
          f"ceiling {MAX_EXCLUSION_AUC_DIST})")
    print(f"       {int(ex_f.sum())} of {len(ex_f)} conscious windows lack an EWS estimate "
          f"({ex_f.mean():.1%})")
    f_ok = ex_dist <= MAX_EXCLUSION_AUC_DIST
    varies = {}
    for c in CANDIDATES:
        v, _, g = _stack(recs, c)
        q1, q3 = np.percentile(v, [25, 75])
        nsub = sum(1 for r in recs if np.unique(r["cols"][c]).size >= 10)
        varies[c] = {"iqr": float(q3 - q1), "n_subjects_10plus_values": nsub}
        print(f"   (e) {c:12s} IQR {q3 - q1:.5f}   recordings with >=10 distinct values {nsub} "
              f"(floor {MIN_EWS_SUBJECTS})")
    e_ok = all(v["iqr"] > 0 and v["n_subjects_10plus_values"] >= MIN_EWS_SUBJECTS
               for v in varies.values())
    g1 = bool(len(recs) >= MIN_RECORDINGS
              and BASE_RATE_BAND[0] <= base_rate <= BASE_RATE_BAND[1]
              and col["distance_from_chance"] <= MAX_POSITION_AUC_DIST
              and f_ok and e_ok)
    print(f"\n   G1 {'PASSED' if g1 else '*** FAILED'}")
    st["g1"] = {"base_rate": base_rate, "position_auc": col["auc_of_position"],
                "position_distance": col["distance_from_chance"],
                "exclusion_auc": ex_auc, "exclusion_distance": ex_dist,
                "n_excluded": int(ex_f.sum()), "n_conscious": int(len(ex_f)),
                "varies": varies, "passed": g1}
    if not g1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P2 — THE INCUMBENT (SEF95 level), printed before any candidate and NOT gating")
    print("=" * 100)
    p_inc = cv_predict_proba(x_inc, y, grp, rng)
    a_inc = float(auc(y, p_inc))
    lo, hi, _ = cluster_bootstrap_ci(lambda i: auc(y[i], p_inc[i]), grp, rng, reps=600)
    print(f"   SEF95 out-of-fold AUC {a_inc:.3f} [{lo:.3f}, {hi:.3f}]")
    print(f"   E34 measured 0.610 [0.571, 0.650] on the same cohort and label.")
    st["p2"] = {"auc": a_inc, "ci": [float(lo), float(hi)]}

    print("\n" + "=" * 100)
    print("P3a — CANDIDATES AGAINST CHANCE, out-of-fold and DIRECTIONAL")
    print("=" * 100)
    print(f"   {'candidate':14s} {'declared':9s} {'AUC':>7s}   95% CI")
    p3 = {}
    for c in CANDIDATES:
        v, yy, gg = _stack(recs, c)
        p = cv_predict_proba(v, yy, gg, rng)
        a = float(directional_auc(yy, p, DIRECTION[c]))
        l_, h_, _ = cluster_bootstrap_ci(lambda i: directional_auc(yy[i], p[i], DIRECTION[c]),
                                         gg, rng, reps=600)
        p3[c] = {"auc": a, "ci": [float(l_), float(h_)]}
        print(f"   {c:14s} {DIRECTION[c]:9s} {a:7.3f}   [{l_:.3f}, {h_:.3f}]")
    a_pri, ci_pri = p3[PRIMARY]["auc"], p3[PRIMARY]["ci"]
    p3a = bool(ci_pri[0] > 0.5)
    print(f"\n   P3a {'PASSED' if p3a else '*** FAILED'} for the primary {PRIMARY}")
    if not p3a and ci_pri[1] < 0.5:
        print(f"   NOTE: the primary fires BELOW 0.5 in its declared direction — that is a refutation of")
        print(f"   the Steyn-Ross sign, not a null.")
    st["p3a"] = {"per_candidate": p3, "passed": p3a}

    print("\n" + "=" * 100)
    print(f"P3b — PRIMARY AGAINST THE INCUMBENT: does {PRIMARY} add to {INCUMBENT}? (out-of-bag)")
    print("=" * 100)
    x_pri, _, _ = _stack(recs, PRIMARY)
    one = np.ones_like(x_inc)
    Xa = np.column_stack([one, x_inc])
    Xb = np.column_stack([one, x_inc, x_pri])
    d, dlo, dhi, nrep = oob_auc_increment(Xa, Xb, y, grp, rng, reps=300)
    print(f"   increment {d:+.4f} [{dlo:+.4f}, {dhi:+.4f}] over {nrep} usable resamples")
    p3b = bool(np.isfinite(dlo) and dlo > 0)
    print(f"   P3b {'PASSED' if p3b else '*** FAILED'}")
    st["p3b"] = {"increment": d, "ci": [dlo, dhi], "passed": p3b}

    print("\n" + "=" * 100)
    print(f"P4 — THE SIGN TEST: median change over the {APPROACH_S} s approaching each loss")
    print("=" * 100)
    print("   Steyn-Ross predicts POSITIVE for all three. E34 found every spectral feature falling.")
    p4 = {}
    for c in CANDIDATES:
        ch = []
        for r in recs:
            for L in r["losses"]:
                a0, a1 = L - APPROACH_S, L
                if a0 < 0:
                    continue
                seg = r["full"][c][a0:a1]
                if np.isfinite(seg).sum() < APPROACH_S // 2:
                    continue
                half = seg.size // 2
                e, l = np.nanmean(seg[:half]), np.nanmean(seg[half:])
                if np.isfinite(e) and np.isfinite(l):
                    ch.append(l - e)
        med = float(np.median(ch)) if ch else float("nan")
        l_, h_ = ((float(np.percentile(ch, 2.5)), float(np.percentile(ch, 97.5)))
                  if len(ch) > 20 else (float("nan"),) * 2)
        p4[c] = {"median_change": med, "spread": [l_, h_], "n_losses": len(ch),
                 "matches_prediction": bool(np.isfinite(med) and med > 0)}
        print(f"   {c:14s} median change {med:+.5f}   [{l_:+.5f}, {h_:+.5f}] over {len(ch)} losses"
              f"   rises? {p4[c]['matches_prediction']}")
    st["p4"] = p4
    agree = sum(v["matches_prediction"] for v in p4.values())
    print(f"\n   {agree} of {len(CANDIDATES)} move in the direction the model predicts.")

    print("\n" + "=" * 100)
    print("P5 — PLACEBO GATE: E34's fake landmark at a matched relative position")
    print("=" * 100)
    # E34's construction, copied rather than reinvented so the gate is the same gate: a cut drawn uniformly
    # in the middle 70 % of each recording, with the HORIZON_S seconds before it labelled positive.
    fake_y = []
    for r in recs:
        n = len(r["y"])
        cut = int(n * float(rng.uniform(0.2, 0.9)))
        yy = np.zeros(n)
        yy[max(0, cut - HORIZON_S):cut] = 1.0
        fake_y.append(yy)
    yf = np.concatenate(fake_y)
    if np.unique(yf).size < 2:
        print("   placebo label is constant — the gate cannot be evaluated.")
        p5 = False
        pinc = float("nan")
    else:
        pinc, plo, phi, pn = oob_auc_increment(Xa, Xb, yf, grp, rng, reps=300)
        print(f"   placebo increment {pinc:+.4f} [{plo:+.4f}, {phi:+.4f}] over {pn} resamples"
              f"   real {d:+.4f}")
        p5 = bool(np.isfinite(pinc) and np.isfinite(d) and d > pinc)
        print(f"   P5 {'PASSED' if p5 else '*** FAILED — the primary is WITHDRAWN'}")
    st["p5"] = {"placebo_increment": pinc, "real_increment": d, "passed": bool(p5)}

    print("\n" + "=" * 100)
    print("P6 — LEAD TIME")
    print("=" * 100)
    if p3a and p5:
        st["p6"] = {}
        for h in (30, 60, 120, 180, 300):
            yh = np.concatenate([(r["ttl"] <= h).astype(float) for r in recs])
            if np.unique(yh).size < 2:
                continue
            ph = cv_predict_proba(x_pri, yh, grp, rng)
            ah = float(directional_auc(yh, ph, DIRECTION[PRIMARY]))
            st["p6"][h] = ah
            print(f"   horizon {h:4d} s   directional AUC {ah:.3f}")
    else:
        print("   Not reported: requires P3a and the placebo.")

    print("\n" + "=" * 100)
    print("MULTIPLICITY over the three candidates (reported)")
    print("=" * 100)
    # The null is a CIRCULAR SHIFT of the label within each recording, not a free permutation of rows.
    # A free permutation would destroy the label's own autocorrelation as well as its alignment with the
    # feature, and would therefore be a null about a label this deposit never produces. A circular shift
    # keeps each recording's run structure and its base rate exactly, and moves only the alignment — which
    # is the thing under test. One shift is drawn per permutation and applied to ALL THREE candidates, as
    # `westfall_young_maxt` requires (one relabelling per row of the null matrix).
    feats = {c: _stack(recs, c)[0] for c in CANDIDATES}
    obsv = [abs(float(auc(y, feats[c])) - 0.5) for c in CANDIDATES]
    lens = [len(r["y"]) for r in recs]
    ys = [r["y"] for r in recs]
    nullm = []
    for _ in range(1000):
        ypp = np.concatenate([np.roll(yv, int(rng.integers(0, n))) for yv, n in zip(ys, lens)])
        if np.unique(ypp).size < 2:
            continue
        nullm.append([abs(float(auc(ypp, feats[c])) - 0.5) for c in CANDIDATES])
    wy = westfall_young_maxt(obsv, np.asarray(nullm, float), names=list(CANDIDATES))
    print(f"   effective_tests {wy['effective_tests']:.2f} of {wy['n_candidates']}")
    for c in CANDIDATES:
        print(f"   {c:14s} raw p {wy['raw'][c]:.4f}   adjusted p {wy['adjusted'][c]:.4f}")
    st["multiplicity"] = {"effective_tests": wy["effective_tests"], "adjusted": wy["adjusted"],
                          "raw": wy["raw"]}

    print("\n" + "=" * 100)
    print("SENSITIVITY: the primary at other EWS windows (reported context, the primary stays at 60 s)")
    print("=" * 100)
    st["sensitivity"] = {}
    for w in SENSITIVITY_W:
        if w == EWS_W:
            st["sensitivity"][w] = a_pri
            print(f"   EWS window {w:4d} s   directional AUC {a_pri:.3f}   <- the registered primary")
            continue
        rs, _ = _load(PEEG_ZIP, ews_w=w)
        if not rs:
            continue
        v, yy, gg = _stack(rs, PRIMARY)
        pw = cv_predict_proba(v, yy, gg, rng)
        aw = float(directional_auc(yy, pw, DIRECTION[PRIMARY]))
        st["sensitivity"][w] = aw
        print(f"   EWS window {w:4d} s   directional AUC {aw:.3f}   ({len(rs)} recordings)")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not p3a:
        verdict = "not_met_chance"
        print(f"   NOT MET: {PRIMARY} does not discriminate above chance in its declared direction.")
    elif not p3b:
        verdict = "not_met_incumbent"
        print(f"   NOT MET: {PRIMARY} adds nothing to {INCUMBENT}'s own level.")
    elif not p5:
        verdict = "withdrawn_placebo"
        print("   NOT MET: the increment survives a fake landmark, so it is not about the transition.")
    else:
        verdict = "met"
        print("   MET: the trajectory of SEF95 carries information about imminent loss of consciousness")
        print("   that its level does not, in the direction a phase-transition model predicts.")
        print("   Scope: ahead of SEF95, not ahead of BIS; temporal critical slowing only, not spatial.")
    print(f"\n   P4's sign is reported regardless of this verdict: {agree} of {len(CANDIDATES)} rise.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
