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
  4. Null: stage labels permuted WITHIN SUBJECT, the entire pipeline re-run inside each draw.

    P  the number of consecutive components whose out-of-sample explained variance exceeds the 95th
       percentile of that null.

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


def count(R3, rng, n_perm=N_PERM, label=""):
    real = oos_explained(R3, rng)
    null = []
    for _ in range(n_perm):
        Rp = R3.copy()
        for s in range(Rp.shape[0]):
            Rp[s] = Rp[s][rng.permutation(len(STAGES))]
        null.append(oos_explained(Rp, rng, n_splits=8))
    null = np.array(null)
    thr = np.nanquantile(null, 0.95, axis=0)
    clears = [bool(np.isfinite(real[k]) and np.isfinite(thr[k]) and real[k] > thr[k])
              for k in range(len(real))]
    k_surv = 0
    for c in clears:
        if c and k_surv == len([x for x in clears[:k_surv] if x]):
            k_surv += 1
        else:
            break
    if label:
        print(f"\n--- {label} ({R3.shape[0]} subjects, {R3.shape[2]} features) ---")
        print(f"{'comp':>5s} {'out-of-sample EV':>18s} {'null 95th':>11s}  clears")
        for k in range(len(real)):
            print(f"{k+1:>5d} {real[k]:18.4f} {thr[k]:11.4f}  {'YES' if clears[k] else 'no'}")
        print(f"  -> {k_surv} axis/axes")
    return {"explained": [float(x) for x in real], "null_95": [float(x) for x in thr],
            "clears": clears, "n_surviving": k_surv}


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


def synth(n_sub, n_feat, rng, n_axes=1, noise=0.35):
    """Synthetic inventory with a KNOWN number of monotone-encoded latent axes."""
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
        X[:, :, j] = _monotone(mix, j) + rng.normal(0, noise, mix.shape)
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
    c1 = count(to_ranks(synth(n_sub, len(FEATURES), srng, n_axes=1)), srng, n_perm=100,
               label="G1 CONTROL -- SYNTHETIC ONE-AXIS (the input that broke E115)")
    c2 = count(to_ranks(synth(n_sub, len(FEATURES), srng, n_axes=2)), srng, n_perm=100,
               label="G2 CONTROL -- SYNTHETIC TWO-AXIS")
    res["G1_one_axis_control"], res["G2_two_axis_control"] = c1, c2
    g1 = bool(c1["n_surviving"] == 1)
    g2 = bool(c2["n_surviving"] == 2)
    res["gates"].update({"G1_pass": g1, "G2_pass": g2})
    print(f"\nG1 one-axis control -> {c1['n_surviving']}  {'PASS' if g1 else 'FAIL'}")
    print(f"G2 two-axis control -> {c2['n_surviving']}  {'PASS' if g2 else 'FAIL'}")

    rng = np.random.default_rng(SEED)
    full = count(to_ranks(X), rng, label="REAL INVENTORY")
    res["full"] = full
    res["gates"]["G3_pass"] = bool(n_sub >= MIN_SUBJECTS)
    res["gates"]["G4_pass"] = bool(full["clears"] and full["clears"][0])
    print(f"\nG3 coverage {n_sub} >= {MIN_SUBJECTS}  {'PASS' if res['gates']['G3_pass'] else 'FAIL'}")
    print(f"G4 axis 1   {'PASS' if res['gates']['G4_pass'] else 'FAIL'}")

    noemg = [f for f in FEATURES if f not in EMG_FEATURES]
    Xe = load_values(noemg)
    res["no_emg"] = count(to_ranks(Xe), np.random.default_rng(SEED + 7),
                          label="REAL INVENTORY, EMG FEATURES EXCLUDED (G5)")
    res["gates"]["G5_surviving_without_emg"] = res["no_emg"]["n_surviving"]

    k = full["n_surviving"]
    ke = res["no_emg"]["n_surviving"]
    if not (g1 and g2):
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
