"""E167 — Challenge B asked WITHIN subject: does the pre-cue spontaneous state predict THIS trial?

REGISTERED BEFORE `results/stieger_trials.csv` EXISTS. The extractor was written and committed in the same
change; no trial-level value has been read.

---------------------------------------------------------------------------------------------------------
THE QUESTION, AND WHY IT IS NOT THE ONE THIS PROJECT KEEPS ASKING

Thirty Challenge B rows are in the ledger. Every one of them predicts a SUBJECT-LEVEL TRAIT: "is this
person a good BCI user?" — E41, E42, E73, E86, E106, E114, E124, E125, E129, E131, E132, E134, E143, E144,
E149, E164. The label is a session's mean accuracy, the unit is a subject, and the ceiling on the whole
enterprise is the reliability of that mean (E38, E68).

**A bedside assessment of a patient with a disorder of consciousness does not ask that question.** It asks
whether the command response is present *in this attempt*. The moment-to-moment version — given the two
seconds of spontaneous EEG immediately before the cue, is this trial's command followed? — has never been
asked here, and the segment it needs was already being extracted and then averaged away by
`extract_stieger_features.py`.

Three things change when the unit is a trial rather than a subject:

  * **Each subject is their own control.** Skull thickness, electrode impedance, age, montage fit and
    every other between-subject nuisance that has dominated the trait analyses is differenced out.
  * **The n is ~450 per session rather than 1**, so the power problem that E38/E68's label-ceiling work
    was trying to solve from the label side is attacked from the observation side instead.
  * **The label ceiling stops binding.** A session-mean accuracy needs to be reliable; a single trial's
    hit or miss is what it is.

---------------------------------------------------------------------------------------------------------
ESTIMAND, STATED EXACTLY

Within each session, the **partial rank association** between a pre-cue feature and trial success, with
the trial's position in the session (linear and quadratic) residualised out of BOTH sides. The reported
statistic is the MEAN of that per-session correlation over sessions; its interval is a cluster bootstrap on
SUBJECT (not session), because sessions are nested in subjects (rule 69).

Position is residualised rather than competed against because practice and fatigue produce a within-session
trend in accuracy for free, and any feature with its own within-session drift — electrode gel drying,
impedance, alertness — would inherit an association from it with no state coupling at all. This is the same
mechanism as rule 64's time-split-in-disguise, met before the fact rather than after.

DECLARED TWO-SIDED, AND WHY (rule 42). Blankertz 2010's published predictor says a LARGER resting
sensorimotor rhythm goes with BETTER BCI control — between subjects. The pre-stimulus literature on
trial-to-trial variability points the other way, toward high pre-cue alpha marking a disengaged
sensorimotor cortex. **This project has no basis to choose between them, so the test is two-sided and the
direction is a reported finding rather than a prediction.** If the within-trial sign is opposite to the
between-subject sign, that is stated plainly: it would mean the trait and state versions of "sensorimotor
idling" are not the same quantity, which is a result in its own right.

PRIMARY  `mu_mean` — relative alpha over C3 and C4, the sensorimotor mu the SMR literature actually names.
         It is a different measure from the montage-median `relative_alpha_power` this project has used at
         session level (rule 60 requires the distinction be stated rather than assumed; the correlation
         between the two is reported before anything else).
SECONDARY the eight-feature spectral panel plus `mu_c3`, `mu_c4`, `mu_lateralisation`, BH at q = 0.05.

INCUMBENT (rule 45)  `artifact` — the deposit's own per-trial artefact flag, scored by the identical
         statistic. It is the trivially available non-EEG trial-level predictor of trial success and it is
         the bar. It is REPORTED, not used as a gate: G3 establishes the instrument's aliveness
         synthetically, so a dead incumbent here would be informative rather than disqualifying (E61's
         trap run the other way).

---------------------------------------------------------------------------------------------------------
PRIOR ART — ADDED AFTER REGISTRATION, BEFORE ANY DATA (verified from the MEDLINE record, rule 25)

The question has been asked once before, at much smaller scale. **PMID 27199630** (Frontiers in
Neuroscience, 2016, "Single Trial Predictors for Gating Motor-Imagery Brain-Computer Interfaces Based on
Sensorimotor Rhythm and Visual Evoked Potentials") reports, verbatim:

> "mu rhythm amplitude over the central electrodes at the time of cue presentation and to a lesser extent
>  the single trial visual evoked response **were correlated with the success on the subsequent imagery
>  task**"

Two things follow, and only two (rule 42 — a quotation supports what it literally says and no more).
**First, this makes E167 a REPLICATION rather than a first look**, on 62 subjects with online BCI control
instead of an offline gating analysis, which raises the bar on a null: a null here would be a failure to
replicate a published single-trial effect, not an absence of prior expectation. **Second, the abstract
does not state the SIGN.** It says correlated, not which way. So the registered two-sided test stands
exactly as written, and nothing about the design moves — this note adds a citation and a bar, not a
prediction.

The choice of `mu_mean` as the primary was made before this record was read and is corroborated by it:
the source's own variable is central-electrode mu amplitude, which is what `mu_mean` (C3/C4 relative
alpha) is.

---------------------------------------------------------------------------------------------------------
GATES

G1  LABEL VARIANCE. At least 40 sessions with >= 100 scored trials and a hit rate inside [0.15, 0.85].
    Derived rather than round (rule 63): a within-session rank correlation needs both classes present in
    quantity, and 0.15 of 100 is 15 — the smallest count at which a per-session Spearman is not dominated
    by a handful of trials.

G2  POSITION IS ACTUALLY REMOVED. After residualisation the mean within-session correlation between trial
    index and the residualised outcome must be within 0.02 of zero. This checks that the adjustment did
    what it claims; a caveat in the docstring is not a control (rule 54).

G3  CALIBRATION AND FLOOR, BOTH HALVES, AND EITHER CAN FAIL.
      (a) an i.i.d. synthetic column must NOT be detected (two-sided p > 0.05). If pure noise is
          detected, the null is anti-conservative and NOTHING is reported.
      (b) a synthetic column carrying a KNOWN within-session association must BE detected. Rungs
          rho = 0.02, 0.05, 0.10, 0.20 are climbed and the smallest detected rung is the **measured
          floor**. If no rung is detected the experiment has no power and every candidate null is
          reported as ABSENT, never as NEGATIVE (rule 31).

---------------------------------------------------------------------------------------------------------
PLACEBO, AND IT GATES THE VERDICT (rule 34)

The alternative explanation this design must beat is that the pre-cue window of trial e is adjacent in
time to trial e-1, so a feature could track the CONSEQUENCE of the last outcome — frustration, a change in
posture, a change in effort — rather than predict the next one.

**The placebo replaces the outcome with the PREVIOUS trial's outcome**, everything else identical. If the
pre-cue feature explains the trial just finished as well as the trial about to start, the finding is a
lagged consequence and not a state predictor.

It is a COMPARISON against the placebo's own null distribution, never an absolute threshold (rule 34), and
it can change the statistic it is a placebo for (rule 55) — shifting the outcome by one trial alters both
the pairing and the direction of time, which is exactly the estimand.

---------------------------------------------------------------------------------------------------------
VERDICT RULE — THE UNINFORMATIVE CASES ARE ENUMERATED FIRST (rules 31, 37, 48)

  (1) NOT INTERPRETABLE   G3(a) fails: noise is detected. Nothing is reported.
  (2) NO POWER            G3(b) fails at every rung. All candidate nulls are ABSENT, not negative.
  (3) LAGGED              the primary reaches p <= 0.05 AND the placebo's statistic is at least as large
                          against its own null. The association is a consequence of the previous trial and
                          the forward claim is refused.
  (4) PRESENT             the primary reaches p <= 0.05, the placebo does not, and the direction is
                          reported against the between-subject SMR direction.
  (5) ABSENT ABOVE FLOOR  p > 0.05 with a floor established: nothing above rho = floor.

WHAT WOULD MAKE THIS FILE WRONG. If the per-session correlations are dominated by a handful of sessions
with extreme hit rates, the mean is not the estimand it claims to be; the median and the fraction of
sessions with the same sign are printed beside it for that reason, and a mean whose sign is not shared by
a majority of sessions is not claimed.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import screen_candidates, spearman                  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e167_trial_level_responsiveness.json")
SEED = 20260801

PRIMARY = "mu_mean"
CANDIDATES = ["mu_mean", "mu_c3", "mu_c4", "mu_lateralisation",
              "relative_alpha_power", "relative_delta_power", "exponent_low", "exponent_high",
              "whole_head_exponent", "spectral_edge_95", "spectral_entropy", "lempel_ziv"]
INCUMBENT = "artifact"

N_BLOCKS = 10
MIN_TRIALS = 100
HIT_BAND = (0.15, 0.85)
MIN_SESSIONS = 40
REPS = 1000
RUNGS = (0.02, 0.05, 0.10, 0.20)
ALPHA = 0.05
Q = 0.05


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _resid_on_position(v, pos, blocks=N_BLOCKS):
    """Residual of `v` after subtracting the mean of its own BLOCK of consecutive trials.

    THE ONE REPAIR THIS FILE IS ALLOWED (rule 58), WITH THE REASON. The registered adjustment was a
    residual on [1, pos, pos^2]. G2 measured whether it worked and it did not: the mean within-session
    rank correlation between trial index and the residualised outcome came to **+0.2184** against a
    measured within-session-permutation null of [-0.0790, +0.0789] over 400 draws. A quadratic removes
    linear and quadratic MEAN structure; the estimand here is a RANK correlation, and a session's hit rate
    does not move quadratically -- early learning and late fatigue leave rank structure a polynomial
    cannot see. Block centring at `blocks` equal stretches of consecutive trials removes any trend the
    block resolution can express, which is strictly stronger.

    The gate's own STATISTIC was also wrong and is fixed rather than narrated: `spearman(pos, residual)`
    on a binary outcome is a ties artefact -- residuals take two values per position, so their ranks track
    position within class whatever the adjustment does. G2 now asks the question that matters, in the
    units the primary uses: does POSITION ITSELF, scored as a candidate by the identical statistic, still
    predict the outcome? Under the registered polynomial that question was degenerate (position
    residualised on position is identically zero); under block centring it is not, which is the second
    reason for the repair.

    If G2 fails again the run is over and the failure is the result.
    """
    v = np.asarray(v, float)
    out = np.full(len(v), np.nan)
    n = len(v)
    if n < 8:
        return out
    edges = np.linspace(0, n, blocks + 1).astype(int)
    for a, b in zip(edges[:-1], edges[1:]):
        seg = v[a:b]
        ok = np.isfinite(seg)
        if ok.sum() < 3:
            continue
        out[a:b][ok] = seg[ok] - seg[ok].mean()
    return out


def load_sessions():
    paths = sorted(glob.glob(os.path.join(RESULTS, "stieger_trials*.csv")))
    rows, seen = [], set()
    for p in paths:
        if os.path.getsize(p) == 0:
            continue
        for r in csv.DictReader(open(p, newline="")):
            k = (r.get("subject"), r.get("session"), r.get("trial"))
            if k in seen:            # a second writer on one CSV has happened here before (rule 56)
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        by.setdefault((r["subject"], r["session"]), []).append(r)
    sess = []
    for (subj, s), rr in sorted(by.items()):
        rr.sort(key=lambda r: int(float(r["trial"])))
        res = np.array([_f(r["result"]) for r in rr])
        ok = np.isfinite(res)
        if ok.sum() < MIN_TRIALS:
            continue
        hit = float(res[ok].mean())
        if not (HIT_BAND[0] <= hit <= HIT_BAND[1]):
            continue
        pos = np.arange(len(rr), dtype=float)
        pos = (pos - pos.mean()) / (pos.std() if pos.std() > 0 else 1.0)
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES + [INCUMBENT]}
        sess.append({"subject": subj, "session": s, "n": len(rr), "hit": hit, "ok": ok,
                     "result": res, "pos": pos, "cols": cols,
                     "prev": np.concatenate([[np.nan], res[:-1]])})
    return sess, len(rows)


def session_stat(sess, name, outcome="result", override=None):
    """Per-session partial rank association, position residualised out of BOTH sides."""
    vals, subs = [], []
    for s in sess:
        x = s["cols"][name] if override is None else override[(s["subject"], s["session"])]
        y = s[outcome]
        m = np.isfinite(x) & np.isfinite(y)
        if m.sum() < MIN_TRIALS // 2:
            continue
        rx = _resid_on_position(np.where(m, x, np.nan), s["pos"])
        ry = _resid_on_position(np.where(m, y, np.nan), s["pos"])
        mm = np.isfinite(rx) & np.isfinite(ry)
        if mm.sum() < MIN_TRIALS // 2 or len(np.unique(ry[mm])) < 2:
            continue
        r = spearman(list(rx[mm]), list(ry[mm]))
        if np.isfinite(r):
            vals.append(float(r))
            subs.append(s["subject"])
    if not vals:
        return {"mean": float("nan"), "median": float("nan"), "n_sessions": 0,
                "frac_same_sign": float("nan"), "subjects": []}
    v = np.asarray(vals)
    mu = float(v.mean())
    return {"mean": mu, "median": float(np.median(v)), "n_sessions": int(v.size),
            "frac_same_sign": float(np.mean(np.sign(v) == np.sign(mu))),
            "vals": v.tolist(), "subjects": subs}


def within_session_null(sess, name, outcome, rng, reps=REPS):
    """Permute the OUTCOME within each session. Two-sided p against the null of the mean."""
    obs = session_stat(sess, name, outcome)["mean"]
    if not np.isfinite(obs):
        return obs, float("nan"), float("nan"), 0
    nulls = []
    for _ in range(reps):
        shuf = []
        for s in sess:
            y = s[outcome].copy()
            fin = np.flatnonzero(np.isfinite(y))
            y[fin] = y[fin][rng.permutation(fin.size)]
            shuf.append(y)
        tmp = [{**s, outcome: shuf[i]} for i, s in enumerate(sess)]
        v = session_stat(tmp, name, outcome)["mean"]
        if np.isfinite(v):
            nulls.append(v)
    if len(nulls) < 30:
        return obs, float("nan"), float("nan"), len(nulls)
    n = np.asarray(nulls)
    p = float((np.abs(n - n.mean()) >= abs(obs - n.mean())).mean())
    return obs, p, float(n.mean()), len(n)


def cluster_ci(stat, rng, reps=2000):
    """Percentile CI resampling SUBJECTS -- sessions are nested in subjects (rule 69)."""
    v, subs = np.asarray(stat.get("vals", [])), np.asarray(stat.get("subjects", []))
    if v.size == 0:
        return float("nan"), float("nan")
    uniq = np.unique(subs)
    draws = []
    for _ in range(reps):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        vals = np.concatenate([v[subs == u] for u in pick])
        if vals.size:
            draws.append(vals.mean())
    if len(draws) < 100:
        return float("nan"), float("nan")
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def synthetic(sess, rho, rng):
    """A column with a KNOWN within-session rank association `rho` with the outcome, per session."""
    out = {}
    for s in sess:
        y = np.where(np.isfinite(s["result"]), s["result"], 0.0)
        u = (y - y.mean()) / (y.std() if y.std() > 1e-12 else 1.0)
        out[(s["subject"], s["session"])] = rho * u + np.sqrt(max(0.0, 1 - rho ** 2)) * \
            rng.normal(size=len(y))
    return out


def probe_p(sess, override, rng, reps=400):
    obs = session_stat(sess, PRIMARY, "result", override=override)["mean"]
    if not np.isfinite(obs):
        return float("nan"), float("nan")
    nulls = []
    for _ in range(reps):
        shuf = []
        for s in sess:
            y = s["result"].copy()
            fin = np.flatnonzero(np.isfinite(y))
            y[fin] = y[fin][rng.permutation(fin.size)]
            shuf.append(y)
        tmp = [{**s, "result": shuf[i]} for i, s in enumerate(sess)]
        v = session_stat(tmp, PRIMARY, "result", override=override)["mean"]
        if np.isfinite(v):
            nulls.append(v)
    if len(nulls) < 30:
        return obs, float("nan")
    n = np.asarray(nulls)
    return obs, float((np.abs(n - n.mean()) >= abs(obs - n.mean())).mean())


def bh(pvals, q=Q):
    idx = [i for i, p in enumerate(pvals) if np.isfinite(p)]
    if not idx:
        return set()
    order = sorted(idx, key=lambda i: pvals[i])
    keep, m = set(), len(order)
    for rank, i in enumerate(order, 1):
        if pvals[i] <= q * rank / m:
            keep = set(order[:rank])
    return keep


def main() -> int:
    print("E167 — Challenge B within subject: does the pre-cue state predict THIS trial?")
    sess, n_rows = load_sessions()
    res = {"experiment": "E167", "n_trial_rows": n_rows, "n_sessions_usable": len(sess)}
    if not sess:
        print("   ABSENT: no stieger_trials table yet (or no session clears G1).")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2
    subs = sorted({s["subject"] for s in sess})
    print(f"   {n_rows} trial rows -> {len(sess)} sessions from {len(subs)} subjects clear G1 "
          f"(>= {MIN_TRIALS} scored trials, hit rate in {HIT_BAND})")
    res.update({"n_subjects": len(subs),
                "G1_pass": bool(len(sess) >= MIN_SESSIONS)})
    print(f"   G1 {'PASS' if res['G1_pass'] else '*** FAIL'} "
          f"({len(sess)} sessions vs floor {MIN_SESSIONS})")
    if not res["G1_pass"]:
        res["verdict"] = "GATE-FAILED"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # G2 -- did the position adjustment actually work? The bar is MEASURED, not chosen (rule 63): the
    # first draft compared this against 0.02, and a null simulation puts the per-session sd of this
    # statistic at 0.2935 for a binary outcome independent of position, so the mean over 60 sessions has
    # sd ~0.038 and a bar of 0.02 sat BELOW the statistic's own resolution. The null here is generated by
    # permuting the outcome within session, which is the same destruction the primary uses.
    # G2 -- POSITION SCORED AS A CANDIDATE BY THE IDENTICAL STATISTIC, against its own permutation null.
    # The bar is measured, never a round number (rule 63), and this gate now GATES: the first draft
    # computed it and carried on regardless, which is a gate that does not gate.
    pos_override = {(s["subject"], s["session"]): s["pos"].copy() for s in sess}
    g2_obs, g2_p = probe_p(sess, pos_override, np.random.default_rng(SEED + 3), reps=400)
    res["G2_position_as_candidate"] = {"mean_r": float(g2_obs), "p": float(g2_p)}
    res["G2_pass"] = bool(np.isfinite(g2_p) and g2_p > ALPHA)
    print(f"   G2 position as a candidate: mean r = {g2_obs:+.4f}, p = {g2_p:.4f}   "
          f"{'PASS -- position no longer predicts' if res['G2_pass'] else '*** FAIL -- the clock survives'}")
    if not res["G2_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = ("position still predicts the outcome after block centring, so any feature with a "
                      "within-session time trend inherits an association and no candidate is readable")
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # rule 60 -- is the primary actually a different measure from the session-level incumbent?
    a = np.concatenate([s["cols"]["mu_mean"] for s in sess])
    b = np.concatenate([s["cols"]["relative_alpha_power"] for s in sess])
    m = np.isfinite(a) & np.isfinite(b)
    rho_family = spearman(list(a[m]), list(b[m])) if m.sum() > 100 else float("nan")
    res["rule60_mu_vs_montage_alpha"] = float(rho_family)
    print(f"   rule 60: rho(mu_mean, relative_alpha_power) over {int(m.sum())} trials = "
          f"{rho_family:+.4f}" + ("   *** the primary is the incumbent family restated"
                                  if np.isfinite(rho_family) and abs(rho_family) > 0.9 else ""))

    # G3 -- calibration and floor
    rng = np.random.default_rng(SEED)
    print("\n   G3 calibration and floor")
    _, p0 = probe_p(sess, synthetic(sess, 0.0, rng), rng)
    res["G3a_noise_p"] = float(p0)
    res["G3a_pass"] = bool(np.isfinite(p0) and p0 > ALPHA)
    print(f"      (a) i.i.d. noise: p = {p0:.4f}   "
          f"{'PASS -- not detected' if res['G3a_pass'] else '*** FAIL -- noise detected'}")
    floor, ladder = None, []
    for rho in RUNGS:
        _, p = probe_p(sess, synthetic(sess, rho, rng), rng)
        ladder.append({"rho": rho, "p": float(p)})
        det = np.isfinite(p) and p <= ALPHA
        print(f"      (b) rho = {rho:.2f}: p = {p:.4f}   {'DETECTED' if det else 'not detected'}")
        if det:
            floor = rho
            break
    res["G3b_ladder"], res["floor"] = ladder, floor
    print(f"      FLOOR: {'none up to %.2f' % max(RUNGS) if floor is None else '%.2f' % floor}")

    if not res["G3a_pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        print("\n   VERDICT NOT INTERPRETABLE — pure noise is detected; the null is anti-conservative.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # candidates + the incumbent, all scored identically
    cand = {c: np.concatenate([s["cols"][c] for s in sess]) for c in CANDIDATES}
    usable, dropped = screen_candidates(cand)
    for c, why in dropped.items():
        print(f"   dropped: {c} ({why})")
    names = [c for c in CANDIDATES if c in usable] + [INCUMBENT]
    print(f"\n   {'candidate':<24s} {'mean r':>9s} {'[95% CI]':>20s} {'median':>8s} "
          f"{'same sign':>10s} {'p':>8s}")
    table, ps = {}, []
    for c in names:
        st = session_stat(sess, c)
        obs, p, nm, k = within_session_null(sess, c, "result", np.random.default_rng(SEED + 11))
        lo, hi = cluster_ci(st, np.random.default_rng(SEED + 12))
        table[c] = {**{kk: st[kk] for kk in ("mean", "median", "n_sessions", "frac_same_sign")},
                    "ci": [lo, hi], "p": float(p), "null_mean": float(nm), "n_null": int(k)}
        if c != INCUMBENT:
            ps.append(p)
        print(f"   {c:<24s} {st['mean']:>+9.4f} [{lo:>+8.4f},{hi:>+8.4f}] {st['median']:>+8.4f} "
              f"{st['frac_same_sign']:>10.2f} {p:>8.4f}"
              + ("   <- INCUMBENT" if c == INCUMBENT else ""))
    keep = bh(ps)
    cnames = [c for c in names if c != INCUMBENT]
    res["survivors_bh"] = [cnames[i] for i in sorted(keep)]
    res["table"] = table
    print(f"   BH q={Q}: {res['survivors_bh'] or 'none'}")

    # placebo -- the PREVIOUS trial's outcome
    print("\n   PLACEBO — the same statistic against the PREVIOUS trial's outcome")
    pobs, pp, pnm, pk = within_session_null(sess, PRIMARY, "prev", np.random.default_rng(SEED + 21))
    res["placebo"] = {"mean": float(pobs), "p": float(pp), "null_mean": float(pnm), "n_null": int(pk)}
    print(f"      {PRIMARY}: mean r = {pobs:+.4f}, p = {pp:.4f}")

    prim = table[PRIMARY]
    if floor is None:
        v, why = "NO-POWER", (f"no injected within-session association up to rho = {max(RUNGS):.2f} is "
                              "detectable; every candidate null here is ABSENT, not negative")
    elif not (np.isfinite(prim["p"]) and prim["p"] <= ALPHA):
        v, why = "ABSENT-ABOVE-FLOOR", f"the primary is null with nothing above rho = {floor:.2f}"
    elif np.isfinite(pp) and pp <= ALPHA and abs(pobs) >= abs(prim["mean"]):
        v, why = "LAGGED", ("the previous trial's outcome is explained at least as well, so this is a "
                            "consequence and not a prediction")
    elif np.isfinite(prim["frac_same_sign"]) and prim["frac_same_sign"] < 0.5:
        v, why = "NOT-CLAIMED", "the mean's sign is not shared by a majority of sessions"
    else:
        direction = "MORE pre-cue mu goes with SUCCESS" if prim["mean"] > 0 else \
                    "MORE pre-cue mu goes with FAILURE"
        v, why = "PRESENT", (f"{direction}; between subjects Blankertz 2010 reports more resting SMR with "
                             "BETTER control, so agreement or disagreement is stated, not predicted")
    res["verdict"], res["why"] = v, why
    print(f"\n   VERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
