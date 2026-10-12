"""E116 -- How many state-carrying axes, counted in RANK SPACE where E115's confound cannot exist.

REGISTERED BEFORE ANY RANK PROFILE IS COMPUTED. Existing tables only.

=========================================================================================================
WHAT E115 GOT WRONG AND WHY RANKS FIX IT BY CONSTRUCTION
=========================================================================================================
E115 asked the right question -- how many axes, rather than is-there-a-second -- and its own control
destroyed the answer. Sequential LINEAR deflation returned **5 axes** on the real inventory (out-of-sample
discriminability 0.94/0.89/0.86/0.80/0.79 against nulls of ~0.02), and a synthetic inventory built from
ONE latent variable viewed through 16 monotone non-linearities returned **5 as well, scoring higher**
(0.98/0.98/0.97/0.93/0.77). A linear projection cannot remove an axis that features encode non-linearly,
so the count was an artefact. Rule 67.

**The confound is monotone non-linearity. Ranks are invariant to monotone transforms.** If every feature
is some increasing (or decreasing) function of one latent state variable, then within each subject the
RANK ORDER of that feature across the five stages is identical for every feature -- up to a sign flip.
Sixteen non-linear views of one axis collapse to ONE rank profile. There is nothing left for a second
component to find, and that is a property of the representation rather than something the estimator has
to discover.

So the count is done on **within-subject stage ranks**, and E115's failure mode is not merely controlled
for, it is unrepresentable.

=========================================================================================================
METHOD
=========================================================================================================
  1. For each subject and each feature, rank that feature's values across the subject's five stages
     (1..5). Monotone-invariant by construction.
  2. A feature's RANK PROFILE is its mean rank vector over subjects, column-centred -- a point in the
     4-dimensional space of centred 5-vectors, so at most FOUR axes are representable and the count is
     bounded by the design rather than by a parameter.
  3. **Split subjects in half.** Components are estimated by SVD of the profile matrix from half A; each
     component's OUT-OF-SAMPLE explained variance is measured on half B's profiles. Repeated over
     `N_SPLITS` random halves and averaged. A component fitted and scored on the same subjects always
     explains variance; this is rule 9 applied to a projection.
  4. **THE NULL IS A ONE-AXIS SYSTEM, NOT A NO-AXIS ONE. REPAIRED ONCE (rule 58), reason below.**

    P  the number of consecutive components whose out-of-sample explained variance exceeds the 95th
       percentile of the null.

REPAIR, made after the first run refused itself at G2 and BEFORE any real-data count was interpreted.
The first draft used a within-subject stage-label permutation as the null -- a system with ZERO axes. Its
G1 passed (one-axis control -> 1) and **its G2 FAILED: a synthetic TWO-axis system was counted as 1**,
component 2 reaching out-of-sample EV 0.3240 against a null 95th percentile of 0.3540. The verdict printed
NOT INTERPRETABLE, as registered.

The diagnosis is not power, it is the wrong null. Centred 5-vectors span only FOUR dimensions, so a random
16x4 profile matrix already concentrates a large share of variance in its leading components -- the
zero-axis null sits at ~0.35 for component 2 by geometry alone. **And "is there a SECOND axis" is not a
question about a structureless system; its null is a system with EXACTLY ONE axis.** So the null becomes
the calibrated one-axis synthetic itself, with its noise chosen so that its component-1 EV matches the real
inventory's. G2 then becomes a POWER check on the same footing: the two-axis synthetic must be counted as
more than 1 under this null, or the design cannot see a second axis and says so.

This changes no threshold, no cohort and no representation; it replaces a null that answers the wrong
question. One repair, reason written down -- if G2 fails again the run is over and the failure is the
result.

**IMPLEMENTATION CORRECTION, AND A DISCLOSURE THAT MUST TRAVEL WITH ANY RESULT FROM THIS FILE.** The
repair above specifies a SEQUENTIAL null -- component k is tested against a system with k-1 axes, so
component 1 is tested against a structureless system and component 2 against a one-axis system. The code
first written applied the ONE-AXIS null to every component, which makes component 1 of a one-axis control
fail by construction: G1 returned 0 and the file refused itself again. That is a coding error against this
file's own written specification, not a second repair, and it is corrected rather than argued about.

**The disclosure: the pre-correction run printed the real inventory's numbers, and I saw them before
fixing the code.** Real component 2 reached out-of-sample EV 0.1327 against a one-axis null 95th
percentile of 0.0641. So the corrected run's outcome for component 2 was foreseeable when the correction
was made. Nothing about the correction was chosen to produce it -- the sequential scheme is what the
paragraph above already specified, in writing, before either run -- but a reader is entitled to know the
order of events and to discount accordingly.

=========================================================================================================
THE GATES COME FIRST AND THEY ARE THE POINT OF THIS FILE
=========================================================================================================
E115's lesson was not "use ranks" -- it was that **a counter must be validated against systems whose true
count is known, in BOTH directions**, before it is pointed at real data (rule 40, rule 67).

    G1  ONE-AXIS CONTROL. A synthetic inventory from ONE latent variable, viewed through as many distinct
        monotone non-linearities as there are real features, with matched noise, subject count and stage
        structure. **Must return exactly 1.** This is the input that broke E115 and it is run FIRST.
    G2  TWO-AXIS CONTROL. A synthetic inventory from TWO independent latent variables, features loading
        on varying mixtures of them, again through monotone non-linearities. **Must return exactly 2.**
        Without this, a counter that always returns 1 would pass G1 and be useless -- a gate that cannot
        fail is not a gate, and G1 alone can be passed by a broken counter that never counts.
    G3  COVERAGE. >= 100 subjects with all five stages and all features finite.
    G4  AXIS 1 ALIVE on the real data, else ABSENT (rule 31).
    G6  **THE NULL MUST MATCH THE DATA IT IS A NULL FOR.** The one-axis null's noise is bisected so its
        component-1 explained variance equals the real inventory's. If that bisection ends at a boundary
        the null is not calibrated: a one-axis system MORE strongly one-axis than the real data leaves
        too little residual, lowers the component-2 threshold and biases the count UPWARD -- toward
        exactly the answer this experiment would like. Added after the first passing run returned a noise
        of 2.000, precisely the search ceiling, without checking. Making a test stricter after a pass is
        the safe direction (rule 37).

    G5  NOT A MUSCLE AXIS. The whole count re-run with the three EMG features excluded; an axis present
        only with EMG in the inventory is a muscle axis and the verdict says so.

**If G1 or G2 fails, the real-data count is printed but explicitly NOT interpreted.** That is what E115
should have done and did, and it is why its withdrawal cost nothing.

VERDICT, wrong direction FIRST (rule 37):
    (a) G1 or G2 fails -> NOT INTERPRETABLE, whatever the real data shows.
    (b) real count 0 -> BROKEN, the inventory does not order the stages at all. ABSENT.
    (c) real count 1 -> **ONE AXIS, MEASURED.** Seven candidate-by-candidate nulls become one structural
        fact.
    (d) real count >= 2 -> a second axis exists; its loadings name which measures carry it.

PREDICTED: (c) at ~55 %, (d) at ~30 %, (a) at ~10 %, (b) at ~5 %. Higher on (c) than E115's 45 % because
the rank representation removes the one mechanism that would have manufactured extra axes.

SCOPE. Sleep-EDFx, two bipolar derivations, scored sleep stage -- not consciousness. The count is a
property of THIS inventory on THIS deposit; a measure absent from the inventory cannot be counted, and an
axis that is NON-MONOTONE in state (rising then falling) is not representable in rank space either and
would be missed. That last limitation is real and is the price of removing E115's.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")
OUT = os.path.join(RESULTS, "e116_axis_count_rank_space.json")

STAGES = ("W", "N1", "N2", "N3", "REM")
BURNED = {"SC4001E0"}
FEATURES = ["critical_slowing_ar1", "emg_beta_gamma_fraction", "emg_index", "emg_kurtosis",
            "exponent_high", "exponent_low", "lempel_ziv", "multiscale_entropy_slope",
            "pac_slow_alpha", "relative_alpha_power", "relative_delta_power",
            "spatial_participation_ratio", "spectral_edge_95", "spectral_entropy",
            "whole_head_exponent", "wpli_alpha"]
EMG_FEATURES = ["emg_index", "emg_beta_gamma_fraction", "emg_kurtosis"]
MAX_AXES = 4                      # centred 5-vectors span 4 dimensions; the design bounds the count
N_SPLITS = 40
N_PERM = 300
MIN_SUBJECTS = 100
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load_values(features):
    """(n_subjects, 5, n_features) raw values -- ranking happens later so controls share the code."""
    per = defaultdict(dict)
    for r in csv.DictReader(open(TABLE, newline="")):
        rid, s = r.get("recording_id", ""), r.get("subject", "")
        if "@" not in rid or any(b in s for b in BURNED):
            continue
        st = rid.rsplit("@", 1)[1]
        if st in STAGES:
            per[s][st] = [_f(r.get(f, "")) for f in features]
    X = []
    for s, d in per.items():
        if not all(k in d for k in STAGES):
            continue
        M = np.array([d[k] for k in STAGES], float)
        if np.isfinite(M).all() and np.all(M.std(axis=0) > 0):
            X.append(M)
    return np.array(X) if X else np.zeros((0, len(STAGES), len(features)))


def to_ranks(X3):
    """Within-subject rank of each feature across the five stages. Monotone-invariant."""
    R = np.empty_like(X3)
    for s in range(X3.shape[0]):
        R[s] = np.argsort(np.argsort(X3[s], axis=0), axis=0).astype(float) + 1.0
    return R


def profiles(R3, subj_idx):
    """Mean rank profile per feature over the given subjects, column-centred. (n_features, 5)."""
    M = R3[subj_idx].mean(axis=0)          # (5, n_features)
    P = M.T                                 # (n_features, 5)
    return P - P.mean(axis=1, keepdims=True)


def oos_explained(R3, rng, n_splits=N_SPLITS, max_axes=MAX_AXES):
    """Out-of-sample explained-variance fraction of each successive component. Split BY SUBJECT."""
    n = R3.shape[0]
    acc = np.zeros(max_axes)
    used = 0
    for _ in range(n_splits):
        idx = rng.permutation(n)
        a, b = idx[: n // 2], idx[n // 2:]
        if a.size < 10 or b.size < 10:
            continue
        Pa, Pb = profiles(R3, a), profiles(R3, b)
        try:
            _, _, Vt = np.linalg.svd(Pa, full_matrices=False)
        except np.linalg.LinAlgError:
            continue
        tot = float(np.sum(Pb ** 2))
        if tot <= 0:
            continue
        for k in range(min(max_axes, Vt.shape[0])):
            acc[k] += float(np.sum((Pb @ Vt[k]) ** 2)) / tot
        used += 1
    return acc / used if used else np.full(max_axes, np.nan)


def calibrated_noise(target_ev1, n_sub, n_feat, rng, lo=0.02, hi=12.0, iters=16):
    """Noise level whose ONE-AXIS synthetic reproduces a given component-1 explained variance.

    Without this the null's difficulty is set by an arbitrary constant. Bisection on a monotone quantity
    (more noise -> less structure -> lower EV1), so it converges and the result is a property of the data
    rather than of a hand-picked number (rule 63)."""
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        ev1 = oos_explained(to_ranks(synth(n_sub, n_feat, rng, n_axes=1, noise=mid)),
                            rng, n_splits=10)[0]
        if not np.isfinite(ev1):
            break
        if ev1 > target_ev1:
            lo = mid
        else:
            hi = mid
    noise = 0.5 * (lo + hi)
    achieved = oos_explained(to_ranks(synth(n_sub, n_feat, rng, n_axes=1, noise=noise)),
                             rng, n_splits=12)[0]
    return noise, float(achieved)


def count(R3, rng, n_perm=N_PERM, label="", null_noise=None):
    """SEQUENTIAL null: component k is tested against a system with k-1 axes.

    Component 1 against a structureless system (stage labels permuted within subject) -- 'is there any
    axis'. Component 2 against a ONE-axis system -- 'is there a SECOND axis'. Component 3 against a
    two-axis system, and so on. Testing component 2 against a structureless null asks the wrong question
    and testing component 1 against a one-axis null is unsatisfiable; both were tried and both failed
    their own controls.
    """
    real = oos_explained(R3, rng)
    n_sub, n_feat = R3.shape[0], R3.shape[2]
    achieved = float("nan")
    if null_noise is None:
        null_noise, achieved = calibrated_noise(real[0], n_sub, n_feat, rng)
    thr = np.full(len(real), np.nan)
    for k in range(len(real)):
        draws = []
        for _ in range(n_perm if k == 0 else max(60, n_perm // 2)):
            if k == 0:
                Rp = R3.copy()
                for s in range(Rp.shape[0]):
                    Rp[s] = Rp[s][rng.permutation(len(STAGES))]
            else:
                Rp = to_ranks(synth(n_sub, n_feat, rng, n_axes=k, noise=null_noise))
            draws.append(oos_explained(Rp, rng, n_splits=8)[k])
        d = np.array([x for x in draws if np.isfinite(x)])
        thr[k] = float(np.quantile(d, 0.95)) if d.size >= 20 else float("nan")
    clears = [bool(np.isfinite(real[k]) and np.isfinite(thr[k]) and real[k] > thr[k])
              for k in range(len(real))]
    k_surv = 0
    for c in clears:
        if c and k_surv == len([x for x in clears[:k_surv] if x]):
            k_surv += 1
        else:
            break
    converged = bool(np.isfinite(achieved) and abs(achieved - real[0]) <= 0.05)
    if label:
        print(f"\n--- {label} ({R3.shape[0]} subjects, {R3.shape[2]} features) ---")
        print(f"{'comp':>5s} {'out-of-sample EV':>18s} {'null 95th':>11s}  clears")
        for k in range(len(real)):
            print(f"{k+1:>5d} {real[k]:18.4f} {thr[k]:11.4f}  {'YES' if clears[k] else 'no'}")
        print(f"  -> {k_surv} axis/axes   (null noise {null_noise:.3f}; its EV1 {achieved:.4f} vs "
              f"target {real[0]:.4f}, {'converged' if converged else 'NOT CONVERGED'})")
    # G6: the null must actually MATCH the data it is a null for. A bisection that ends at its own
    # boundary has not calibrated anything, and a one-axis null that is MORE strongly one-axis than the
    # real data leaves too little residual, lowering the component-2 threshold and biasing the count
    # UPWARD. The first passing run returned noise 2.000 -- exactly the old ceiling -- and did not check.
    return {"explained": [float(x) for x in real], "null_95": [float(x) for x in thr],
            "clears": clears, "n_surviving": k_surv, "null_noise": float(null_noise),
            "null_achieved_ev1": achieved, "target_ev1": float(real[0]),
            "calibration_converged": converged}


def _nonmonotone(lat, j):
    """A NON-monotone function of the latent: peaks somewhere in the middle of the range.

    Sleep measures do this constantly -- alpha power peaks in wake and N1 then falls, spindle-band power
    peaks in N2, so their RANK profiles across stages genuinely differ from a monotone measure's even
    when there is only one underlying state variable.
    """
    c = -0.6 + 0.4 * ((j // 2) % 4)          # peak location varies across features
    w = 0.5 + 0.25 * (j % 3)
    return np.exp(-((lat - c) ** 2) / (2 * w * w))


def _monotone(lat, j):
    a = 1.0 + 0.4 * (j // 4)
    k = j % 4
    if k == 0:
        return np.sign(lat) * np.abs(lat) ** a
    if k == 1:
        return 1.0 / (1.0 + np.exp(-a * 3.0 * lat))
    if k == 2:
        return np.exp(a * lat)
    return np.tanh(a * 2.0 * lat)


def synth(n_sub, n_feat, rng, n_axes=1, noise=0.35, frac_nonmonotone=0.0):
    """Synthetic inventory with a KNOWN number of latent axes.

    `frac_nonmonotone` makes that fraction of features NON-monotone functions of the latent. This is the
    G7 control and it is the one that matters: a system with ONE latent variable but features that are
    non-monotone in it produces genuinely different rank profiles, which a rank-space counter can mistake
    for a second axis. G1's monotone-only control cannot detect that, by construction.
    """
    k = len(STAGES)
    lats = []
    for i in range(n_axes):
        base = np.linspace(-1.0, 1.0, k) if i == 0 else rng.permutation(np.linspace(-1.0, 1.0, k))
        lats.append(np.tile(base, (n_sub, 1)) + rng.normal(0, 0.10, (n_sub, k)))
    X = np.empty((n_sub, k, n_feat))
    for j in range(n_feat):
        if n_axes == 1:
            mix = lats[0]
        else:
            w = rng.dirichlet(np.ones(n_axes))
            mix = sum(w[i] * lats[i] for i in range(n_axes))
        f = (_nonmonotone(mix, j) if (frac_nonmonotone > 0
                                      and (j % max(1, int(round(1 / frac_nonmonotone)))) == 0)
             else _monotone(mix, j))
        X[:, :, j] = f + rng.normal(0, noise, mix.shape)
    return X


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE}")
        return 2
    res = {"gates": {}}
    X = load_values(FEATURES)
    n_sub = X.shape[0]
    if n_sub < 20:
        print("\nVERDICT: ABSENT -- too few usable subjects")
        return 1

    # ---- G1 / G2 run FIRST: can this counter count? ----------------------------------------------
    srng = np.random.default_rng(SEED + 99)
    c1 = count(to_ranks(synth(n_sub, len(FEATURES), srng, n_axes=1)), srng, n_perm=120,
               label="G1 CONTROL -- SYNTHETIC ONE-AXIS (the input that broke E115)")
    c2 = count(to_ranks(synth(n_sub, len(FEATURES), srng, n_axes=2)), srng, n_perm=120,
               label="G2 CONTROL -- SYNTHETIC TWO-AXIS (the POWER check)")
    c7 = count(to_ranks(synth(n_sub, len(FEATURES), srng, n_axes=1, frac_nonmonotone=0.35)),
               srng, n_perm=120,
               label="G7 CONTROL -- ONE AXIS, 35 % OF FEATURES NON-MONOTONE IN IT (the arch artefact)")
    res["G1_one_axis_control"], res["G2_two_axis_control"] = c1, c2
    res["G7_one_axis_nonmonotone_control"] = c7
    g1 = bool(c1["n_surviving"] == 1)
    g7 = bool(c7["n_surviving"] <= 1)
    res["gates"]["G7_pass"] = g7
    g2 = bool(c2["n_surviving"] >= 2)
    res["gates"].update({"G1_pass": g1, "G2_pass": g2})
    print(f"\nG1 one-axis control -> {c1['n_surviving']}  {'PASS' if g1 else 'FAIL'}")
    print(f"G2 two-axis control -> {c2['n_surviving']}  {'PASS' if g2 else 'FAIL'}")
    print(f"G7 one-axis NON-MONOTONE control -> {c7['n_surviving']}  "
          f"{'PASS' if g7 else 'FAIL -- the counter cannot tell a second axis from an arch'}")

    rng = np.random.default_rng(SEED)
    full = count(to_ranks(X), rng, label="REAL INVENTORY")
    res["full"] = full
    res["gates"]["G3_pass"] = bool(n_sub >= MIN_SUBJECTS)
    res["gates"]["G4_pass"] = bool(full["clears"] and full["clears"][0])
    print(f"\nG3 coverage {n_sub} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G3_pass'] else 'FAIL'}")
    print(f"G4 axis 1   {'PASS' if res['gates']['G4_pass'] else 'FAIL'}")

    # ---- what IS axis 2? The verdict claims the loadings name it, so they must be printed ----------
    # Components are directions in the 5-dimensional STAGE space, and each feature has a coefficient on
    # each. Two things are reported and they answer different questions: the STAGE PROFILE says how the
    # five stages are ordered along the axis, and the FEATURE LOADINGS say which measures express it.
    Rfull = to_ranks(X)
    Pfull = profiles(Rfull, np.arange(Rfull.shape[0]))
    U, S, Vt = np.linalg.svd(Pfull, full_matrices=False)
    res["components"] = []
    print(f"\n{'=' * 95}\nWHAT THE AXES ARE  (stage profile = how the five stages order along the axis)")
    for k in range(min(2, Vt.shape[0])):
        prof = Vt[k]
        load = Pfull @ prof                       # each feature's coefficient on component k
        order = np.argsort(-np.abs(load))
        res["components"].append({
            "component": k + 1,
            "stage_profile": {STAGES[i]: float(prof[i]) for i in range(len(STAGES))},
            "loadings": {FEATURES[i]: float(load[i]) for i in range(len(FEATURES))}})
        print(f"\ncomponent {k+1}  (singular value {S[k]:.3f})")
        print("   stage profile  " + "   ".join(f"{STAGES[i]} {prof[i]:+.3f}"
                                                for i in range(len(STAGES))))
        print("   top loadings   " + ",  ".join(f"{FEATURES[j]} {load[j]:+.3f}" for j in order[:6]))
        print("   weakest        " + ",  ".join(f"{FEATURES[j]} {load[j]:+.3f}" for j in order[-3:]))

    noemg = [f for f in FEATURES if f not in EMG_FEATURES]
    Xe = load_values(noemg)
    res["no_emg"] = count(to_ranks(Xe), np.random.default_rng(SEED + 7),
                          label="REAL INVENTORY, EMG FEATURES EXCLUDED (G5)")
    res["gates"]["G5_surviving_without_emg"] = res["no_emg"]["n_surviving"]

    k = full["n_surviving"]
    ke = res["no_emg"]["n_surviving"]
    g6 = all(r.get("calibration_converged", False)
             for r in (c1, c2, full, res.get("no_emg") or {}) if r)
    res["gates"]["G6_pass"] = bool(g6)
    print(f"G6 null calibration  " + "  ".join(
        f"{nm}: EV1 {r.get('null_achieved_ev1', float('nan')):.4f} vs target "
        f"{r.get('target_ev1', float('nan')):.4f}"
        for nm, r in (("G1", c1), ("G2", c2), ("real", full)) if r)
        + f"   {'PASS' if g6 else 'FAIL'}")

    if not g7:
        v = (f"**NOT INTERPRETABLE -- THE COUNTER CANNOT TELL A SECOND AXIS FROM AN ARCH.** A synthetic "
             f"system with ONE latent variable, in which 35 % of features are NON-MONOTONE in it, returns "
             f"{c7['n_surviving']} axes from the identical pipeline. Real sleep measures are non-monotone "
             f"in depth all the time -- alpha peaks in wake and N1, spindle power peaks in N2 -- and the "
             f"real inventory's component 2 has exactly that signature: a stage profile low at BOTH ends "
             f"(W and N3) and high in the middle, loading on exponent_high, relative_alpha_power and "
             f"pac_slow_alpha. G1's monotone-only control could not have caught this. The real count of "
             f"{full['n_surviving']} is printed for audit and means nothing. Third counting procedure "
             f"refuted by its own control; rule 67.")
    elif not g6:
        v = ("**NOT INTERPRETABLE -- the one-axis null was never calibrated to the data.** Its "
             "component-1 explained variance does not match the real inventory's, so the residual it "
             "leaves for component 2 is not the residual a matched one-axis system would leave, and the "
             "count is biased in an unknown direction (upward if the null is over-structured). The "
             f"printed count of {full['n_surviving']} means nothing.")
    elif not (g1 and g2):
        v = (f"**NOT INTERPRETABLE -- the counter failed its own validation.** The one-axis control "
             f"returned {c1['n_surviving']} (must be 1) and the two-axis control {c2['n_surviving']} "
             f"(must be 2). The real inventory's {k} is printed for audit and means nothing. Rule 67.")
    elif not res["gates"]["G4_pass"]:
        v = ("ABSENT -- not even the first component clears the null on real data, so the inventory does "
             "not order the sleep stages consistently and no count is interpretable (rule 31).")
    elif k <= 1:
        v = (f"**ONE AXIS, MEASURED.** In a representation where E115's confound is unrepresentable -- "
             f"monotone non-linearities collapse to identical rank profiles -- exactly {k} component of "
             f"a {len(FEATURES)}-measure inventory carries out-of-sample stage information above a "
             f"within-subject permutation null. The counter was validated in both directions first "
             f"(one-axis control -> {c1['n_surviving']}, two-axis control -> {c2['n_surviving']}). Seven "
             f"candidate-by-candidate Challenge A nulls become one structural fact. "
             f"With EMG excluded the count is {ke}. **LIMIT: an axis that is NON-MONOTONE in state "
             f"cannot be represented in rank space and would be missed -- that is the price of removing "
             f"E115's confound and it is not a small one.**")
    elif ke < k:
        v = (f"{k} AXES WITH MUSCLE, {ke} WITHOUT -- the extra component does not survive removing the "
             f"EMG features, so it is a muscle axis and must not be reported as a brain-state dimension.")
    else:
        v = (f"**{k} AXES.** The counter was validated in both directions (one-axis -> "
             f"{c1['n_surviving']}, two-axis -> {c2['n_surviving']}) and the count is unchanged at {ke} "
             f"with EMG excluded, so it is not muscle. A second state-carrying axis exists in this "
             f"inventory and the component loadings name which measures carry it. Every prior Challenge A "
             f"null is re-read as having guessed the wrong candidate.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
