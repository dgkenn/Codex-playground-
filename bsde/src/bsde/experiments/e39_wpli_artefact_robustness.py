#!/usr/bin/env python3
"""E39 — is wPLI actually artefact-robust? The mundane explanation for E35/E36, tested on independent data.

THE PREDICTION REGISTERED HERE IS AGAINST THIS PROJECT'S OWN PREFERRED READING, AND THAT IS THE POINT.

E35 and E36 found that phase-coupling measures carry almost no information about which anaesthetic produced
a matched state, while power and complexity measures carry a lot. The leading deflationary explanation was
named in E36 and has never been tested on data other than the deposit that produced the finding:

    **wPLI is constructed to be insensitive to amplitude and volume conduction. So of course it leaks less
    about anything — electrode coverage, data quality, drug identity. The "measure-family split" is a
    property of the estimator, not of the brain.**

E36 attacked that within a single drug arm of its own deposit and found the opposite of what the explanation
predicts: phase measures were *more* legible of electrode type than amplitude measures, not less (0.243 vs
0.202 in propofol, 0.344 vs 0.288 in dexmedetomidine). **That test was post hoc, unregistered, and ran on
the same intracranial rows as the finding it was defending.** Its own write-up says so and asks a successor
to pre-register it. This is that successor.

**So the directional prediction below is the DEFLATIONARY one.** If it wins, E36's post-hoc defence fails to
replicate and the family split is materially weakened. Registering the hypothesis that would damage the
project's own result is the only way this test is worth running — and error-catalogue rule 47 says exactly
this: a partition or a defence is credible when the discriminating case was assigned against the favoured
story before the numbers were seen.

WHAT CHANGES FROM E36, AND IT IS EVERYTHING EXCEPT THE QUESTION.

    deposit      two SCALP cohorts, not one intracranial deposit — `ds004541` (8 subjects, 124 rows) and
                 `chennu_propofol` (20 subjects, 80 rows), independent of each other and of Krause/Banks
    implement.   OUR wPLI (`wpli_alpha`, definition fingerprint `8ddebb740c943a76`), not the depositors' —
                 which is the rule-23 check QUEUE.md Q9 item 2 wanted and could not get on Krause, because
                 that deposit ships no raw traces (215 entries enumerated, no EDF, no iEEG)
    artefact     EMG, the classic amplitude artefact and the one wPLI's construction most directly claims
                 robustness to — a sharper test than electrode type, which was what Krause happened to offer
    contrast     within SUBJECT throughout, so neither legibility can be a restatement of "these are
                 different people" (`within_subject_auc`; E14 measured an ICC above 0.9 across windows of
                 one person, which is why pooling would silently swap the question)

THIS IS NOT A FAMILY COMPARISON AND MUST NOT BE WRITTEN AS ONE. **There is exactly ONE phase feature in
these cohorts.** `wpli_alpha` is compared against six amplitude and complexity measures, so the statistic
is "wPLI against the rest", not "phase against amplitude". A single feature cannot represent a family, and
E36's Delta — which averaged four phase features — has no counterpart here. Stated now so it cannot be
blurred afterwards.

THE STATISTIC, AND WHY IT SUBTRACTS CAPABILITY. Per feature, two within-subject direction-free legibilities:

    emg_leg    |AUC - 0.5| for HIGH vs LOW `emg_index`, median-split WITHIN each subject
    state_leg  |AUC - 0.5| for a real state contrast in the same subjects

    Contrast = mean_AMPLITUDE(emg_leg - state_leg) - (emg_leg - state_leg)_wpli        <- THE PRIMARY

Subtracting `state_leg` is the same control E36's Delta used and for the same reason (rule 32): a measure
that separates nothing leaks nothing, so raw artefact-legibility would reward uselessness. What is compared
is each measure's artefact-legibility *relative to its own capability*.

    Contrast > 0   wPLI is artefact-robust relative to its capability -> **the deflationary explanation is
                   supported, E36's post-hoc defence does not replicate, and E35/E36 are weakened.**
    Contrast < 0   wPLI is no more artefact-robust, or less so -> E36's post-hoc finding replicates on
                   independent data with an independent implementation.
    interval spans 0   **no evidence either way.** See the power note; this is the expected outcome.

THE POWER NOTE, WRITTEN BEFORE THE RUN SO IT CANNOT BE PRODUCED AFTERWARDS AS AN EXCUSE. Eight subjects in
`ds004541` and twenty in `chennu`, against a between-feature difference of legibilities. **This test is
under-powered and a null result is the most likely single outcome.** A null therefore does NOT support
E36's post-hoc defence and must not be reported as if it did — absent is not negative (rule 31). What the
design can deliver is a clearly one-sided answer if the effect is large, and agreement or disagreement
between two independent cohorts, which is worth more than either alone.

THE SECOND COHORT IS WEAKER THAN THE FIRST AND THE REASON IS STRUCTURAL. `chennu` ships exactly four rows
per subject, one per sedation level, so a within-subject median split of EMG is 2-versus-2 and its state
contrast is 1-versus-1. The feasibility probe confirmed it: median 4 distinct `emg_index` values per
subject, against 17 in `ds004541`. Chennu is reported as a direction check, never as an independent
estimate, and its interval is not combined with ds004541's.

REGISTERED BEFORE ANY FEATURE-ARTEFACT RELATIONSHIP IS COMPUTED. Failing branch written first throughout.

  G1  MACHINERY GATE. In each cohort: at least `MIN_SUBJECTS` subjects evaluable for BOTH contrasts, and
      every feature varies within subject. If a cohort fails, it is reported as ABSENT for that cohort and
      the other still runs; if both fail, nothing is reported (rule 31).

  G2  BOTH CONTRASTS MUST BE DETECTABLE (rule 32). At least one feature must reach `MIN_DETECTABLE`
      legibility on the EMG contrast, and at least one on the state contrast. If the EMG split separates
      nothing for anybody, there is no artefact to be robust to and the primary is meaningless — a
      comparison of two measures against a non-contrast.

  P1  THE PRIMARY. `Contrast` in `ds004541`, with a subject-clustered bootstrap CI. Direction as above.

  P2  THE INDEPENDENT DIRECTION CHECK. The same in `chennu`, reported with its 2-versus-2 limitation
      attached. **Any claim requires both cohorts to agree in sign**; disagreement is reported as
      disagreement and settles nothing, which is the honest outcome for two thin cohorts.

  P3  REPORTED CONTEXT, no verdict: the per-feature table of `emg_leg` and `state_leg` in both cohorts, so
      a reader can see whether `Contrast` is carried by one feature or by the set.

  P4  THE PLACEBO, gating interpretation (rules 34 and 48). The identical statistic with the EMG channel
      replaced by `emg_kurtosis` — a *different* EMG proxy. The feasibility probe found the two order
      almost identically (fraction-by-decile 0.00 0.00 0.00 0.00 0.05 0.95 1.00 1.00 1.00 1.00), so a
      result that holds for one and reverses for the other is estimator noise rather than artefact
      robustness. **Reported as NOT INFORMATIVE if P1's own interval includes zero**, because a placebo
      cannot validate a null.

VERDICT RULE, written before the run.

    NOT INTERPRETABLE   G1 or G2 failed in both cohorts, or P4 reverses P1.
    NO EVIDENCE         P1's interval includes 0, or the two cohorts disagree in sign. **This is the
                        expected outcome and it supports NEITHER explanation.**
    DEFLATION SUPPORTED Contrast > 0 excluding zero, both cohorts agreeing. E36's post-hoc defence does not
                        replicate; E35/E36's family split is materially weakened and every document
                        carrying it must say so.
    DEFENCE REPLICATES  Contrast < 0 excluding zero, both cohorts agreeing. wPLI is not generically
                        artefact-robust, on independent data with an independent implementation.

SCOPE. Two small scalp cohorts, one phase feature, EMG as the artefact channel, propofol in both. Nothing
here speaks to electrode type (the channel E36 actually tested), to intracranial recordings, or to any
artefact other than muscle. A negative about EMG robustness is not a general negative about wPLI.

--------------------------------------------------------------------------------------------------------
OUTCOME. **NO EVIDENCE either way, which is the outcome this file registered in advance as the most likely
one. It supports NEITHER explanation, and in particular it does NOT vindicate E36's post-hoc defence.**

    G1/G2  Both cohorts passed. `ds004541`: 7 of 8 subjects evaluable for both contrasts, best EMG
           legibility 0.148 and best state legibility 0.325 against a 0.10 floor. `chennu`: 20 of 20
           evaluable, 0.175 and 0.400. So there was a real artefact contrast and a real state contrast to
           compare against — G2 is the check that would have made the primary meaningless, and it held.

    P1     `ds004541`   Contrast **+0.0113 [-0.1750, +0.1966]**
    P2     `chennu`     Contrast **+0.0417 [-0.1935, +0.2674]**

    P4     NOT INFORMATIVE, correctly. Rule 48 fired as designed: with the primary's interval spanning
           zero there is no effect for a second EMG proxy to fail to reproduce, and the branch said so
           instead of printing a pass.

**THE ONE THING NOT TO SAY.** Both point estimates lean positive — the direction of the deflationary
explanation — and both cohorts "agree in sign". **That is not evidence and must not be reported as a
lean.** Two estimates of +0.011 and +0.042 carrying intervals of roughly +/-0.2 are two coin flips landing
the same way; the agreement check exists to *withhold* a claim when the cohorts disagree, not to manufacture
one when they happen to match. The honest summary is that this design cannot see an effect of the size at
issue, which is what the pre-registered power note said before the numbers existed.

**WHAT THE PER-FEATURE TABLE SHOWS, AND IT IS WORTH MORE THAN THE PRIMARY.** `wpli_alpha` sits in the middle
of the pack on artefact legibility in both cohorts — EMG legibility 0.045 in `ds004541` and 0.100 in
`chennu`, against a spread of 0.006-0.148 and 0.050-0.175 across the six amplitude and complexity measures.
It is neither conspicuously robust nor conspicuously fragile. **The strong version of the deflationary
story — "wPLI barely responds to artefact, which is why it barely responds to anything" — is not what these
tables look like**, in either cohort, with our own implementation. That is a weaker statement than a
significant Contrast would have been and it is the one the data supports.

**WHAT THIS MEANS FOR E35/E36, STATED WITHOUT SPIN.** Their status is unchanged: still unclaimed, still
carrying E36's post-hoc within-arm defence as a *hypothesis a successor should pre-register*, and now
carrying a pre-registered successor that **could not resolve it either way**. The right conclusion is that
the deflationary explanation remains live and untested at adequate power, not that it has been dismissed.
The external corroboration from Kallionpaa 2020 and Akeju 2014 remains the strongest thing supporting the
underlying observation, and it is independent of this question entirely.

**WHY THE DESIGN COULD NOT DELIVER, RECORDED FOR THE NEXT ATTEMPT.** Three reasons, all structural and all
knowable in advance — the first two were stated in the header before the run, the third was not:
  1. **One phase feature.** A single measure cannot carry a family mean, so the comparison had no way to
     average down its own noise on the side that mattered.
  2. **8 and 20 subjects**, against a difference of two within-subject legibilities each estimated from a
     handful of rows per person.
  3. **`chennu` supplies four rows per subject**, so its EMG split is 2-versus-2 and its state contrast is
     1-versus-1. Its interval is the widest in the file and it was never going to be otherwise. Reported
     rather than dropped, because a cohort that cannot contribute is a fact about the deposit.
     **A future attempt needs a cohort with many windows per subject and more than one phase measure, and
     should compute the required n from these intervals rather than hoping.**
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import within_subject_auc, cluster_bootstrap_ci               # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e39_wpli_artefact_robustness.json")

PHASE = "wpli_alpha"
AMPLITUDE = ("relative_alpha_power", "relative_delta_power", "lempel_ziv",
             "spectral_entropy", "spectral_edge_95", "whole_head_exponent")
FEATURES = (PHASE,) + AMPLITUDE
ARTEFACT = "emg_index"
PLACEBO_ARTEFACT = "emg_kurtosis"

COHORTS = {
    "ds004541": {"file": "ds004541_v2.csv", "state_col": "meta_phase",
                 "state_a": "awake_pre_drug", "state_b": "post_loc"},
    "chennu": {"file": "chennu_features_v3.csv", "state_col": "meta_sedation_level",
               "state_a": "1.0", "state_b": "3.0"},
}
MIN_SUBJECTS = 5
MIN_DETECTABLE = 0.10
REPS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _load(cfg):
    rows = [r for r in csv.DictReader(open(os.path.join(RESULTS, cfg["file"]), newline=""))
            if r.get("status") == "ok"]
    sub = np.array([r["subject"] for r in rows])
    cols = {c: np.array([_f(r.get(c, "")) for r in rows], float) for c in FEATURES}
    for a in (ARTEFACT, PLACEBO_ARTEFACT):
        cols[a] = np.array([_f(r.get(a, "")) for r in rows], float)
    state = np.array([r.get(cfg["state_col"], "") for r in rows])
    return sub, cols, state


def _within_median_split(values, sub):
    """1 above that subject's own median, 0 below, NaN at the median or where the subject has no spread."""
    y = np.full(values.size, np.nan)
    for s in np.unique(sub):
        m = (sub == s) & np.isfinite(values)
        if m.sum() < 4:
            continue
        med = np.median(values[m])
        idx = np.flatnonzero(m)
        y[idx[values[m] > med]] = 1.0
        y[idx[values[m] < med]] = 0.0
    return y


def _leg(y, x, sub):
    """Direction-free within-subject legibility: |mean-of-per-subject-AUC - 0.5|."""
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < 8 or np.unique(y[ok]).size < 2:
        return float("nan")
    a = within_subject_auc(y[ok], x[ok], sub[ok], "higher")
    return abs(a - 0.5) if np.isfinite(a) else float("nan")


def _contrast(cols, y_art, y_state, sub, idx=None):
    """mean_AMPLITUDE(emg_leg - state_leg) - (emg_leg - state_leg)_wpli."""
    sl = slice(None) if idx is None else idx
    def gap(name):
        return (_leg(y_art[sl], cols[name][sl], sub[sl])
                - _leg(y_state[sl], cols[name][sl], sub[sl]))
    g_w = gap(PHASE)
    g_a = [gap(n) for n in AMPLITUDE]
    g_a = [v for v in g_a if np.isfinite(v)]
    if not np.isfinite(g_w) or not g_a:
        return float("nan")
    return float(np.mean(g_a) - g_w)


def _run_cohort(name, cfg, rng, artefact=ARTEFACT):
    sub, cols, state = _load(cfg)
    y_art = _within_median_split(cols[artefact], sub)
    y_state = np.full(state.size, np.nan)
    y_state[state == cfg["state_a"]] = 0.0
    y_state[state == cfg["state_b"]] = 1.0

    ev_art = sum(1 for s in np.unique(sub)
                 if np.unique(y_art[(sub == s) & np.isfinite(y_art)]).size == 2)
    ev_state = sum(1 for s in np.unique(sub)
                   if np.unique(y_state[(sub == s) & np.isfinite(y_state)]).size == 2)
    per = {n: {"emg_leg": _leg(y_art, cols[n], sub), "state_leg": _leg(y_state, cols[n], sub)}
           for n in FEATURES}
    det_art = max([v["emg_leg"] for v in per.values() if np.isfinite(v["emg_leg"])] or [0.0])
    det_state = max([v["state_leg"] for v in per.values() if np.isfinite(v["state_leg"])] or [0.0])
    g1 = ev_art >= MIN_SUBJECTS and ev_state >= MIN_SUBJECTS
    g2 = det_art >= MIN_DETECTABLE and det_state >= MIN_DETECTABLE

    c = _contrast(cols, y_art, y_state, sub)
    lo = hi = float("nan")
    if g1 and g2 and np.isfinite(c):
        lo, hi, _ = cluster_bootstrap_ci(
            lambda i: _contrast(cols, y_art, y_state, sub, idx=i), sub, rng, reps=REPS)
    return {"n_subjects": int(np.unique(sub).size), "n_rows": int(sub.size),
            "evaluable_emg": ev_art, "evaluable_state": ev_state,
            "best_emg_leg": float(det_art), "best_state_leg": float(det_state),
            "g1": bool(g1), "g2": bool(g2), "per_feature": per,
            "contrast": float(c), "ci": [float(lo), float(hi)]}


def main(argv=None) -> int:
    print("E39 — is wPLI actually artefact-robust? The deflationary explanation, on independent data")
    print("   The registered direction is the one that WEAKENS E35/E36. See the header.")
    print("   NOT a family comparison: there is exactly one phase feature in these cohorts.")
    rng = np.random.default_rng(SEED)
    st = {"experiment": "E39", "phase_feature": PHASE, "amplitude": list(AMPLITUDE)}

    res = {}
    for name, cfg in COHORTS.items():
        if not os.path.exists(os.path.join(RESULTS, cfg["file"])):
            print(f"\n   *** {cfg['file']} absent — cohort skipped.")
            continue
        res[name] = _run_cohort(name, cfg, rng)
    st["cohorts"] = res
    if not res:
        print("\n   *** no cohort available.")
        return 2

    print("\n" + "=" * 100)
    print("G1 / G2 — MACHINERY GATES, per cohort")
    print("=" * 100)
    for name, r in res.items():
        print(f"   {name:10s} {r['n_subjects']:3d} subjects, {r['n_rows']:4d} rows   "
              f"evaluable: EMG {r['evaluable_emg']}, state {r['evaluable_state']}  (floor {MIN_SUBJECTS})")
        print(f"              best legibility  EMG {r['best_emg_leg']:.3f}, state "
              f"{r['best_state_leg']:.3f}  (floor {MIN_DETECTABLE})   "
              f"G1 {'PASS' if r['g1'] else 'FAIL'}  G2 {'PASS' if r['g2'] else 'FAIL'}")
    usable = [n for n, r in res.items() if r["g1"] and r["g2"]]
    if not usable:
        print("\n   Both cohorts refused by their own gates. ABSENT, not negative (rule 31).")
        st["verdict"] = "not_interpretable"
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P3 — PER-FEATURE TABLE (reported, no verdict)")
    print("=" * 100)
    for name in usable:
        print(f"   --- {name}")
        print(f"      {'feature':24s} {'emg_leg':>8s} {'state_leg':>10s} {'gap':>8s}")
        for n in FEATURES:
            v = res[name]["per_feature"][n]
            gap = v["emg_leg"] - v["state_leg"]
            tag = "  <- PHASE" if n == PHASE else ""
            print(f"      {n:24s} {v['emg_leg']:8.3f} {v['state_leg']:10.3f} {gap:8.3f}{tag}")

    print("\n" + "=" * 100)
    print("P1 / P2 — THE PRIMARY and the independent direction check")
    print("=" * 100)
    print("   Contrast > 0 means wPLI IS artefact-robust relative to its capability, i.e. the")
    print("   deflationary explanation wins and E35/E36 are weakened.")
    for name in usable:
        r = res[name]
        print(f"   {name:10s} Contrast {r['contrast']:+.4f}  [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}]")
    signs = {n: np.sign(res[n]["contrast"]) for n in usable}
    agree = len(set(signs.values())) == 1 and len(usable) > 1
    print(f"\n   cohorts agreeing in sign: {agree}"
          + ("" if len(usable) > 1 else "   (only one cohort usable — no agreement check possible)"))
    st["agree"] = bool(agree)

    primary = "ds004541" if "ds004541" in usable else usable[0]
    lo, hi = res[primary]["ci"]
    excludes = bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))

    print("\n" + "=" * 100)
    print("P4 — PLACEBO: the same statistic on a different EMG proxy")
    print("=" * 100)
    if not excludes:
        print("   NOT INFORMATIVE: the primary's interval includes zero, so there is no effect for a")
        print("   second proxy to fail to reproduce (rule 48).")
        st["p4"] = {"status": "not_informative"}
        p4 = None
    else:
        p4res = {n: _run_cohort(n, COHORTS[n], rng, artefact=PLACEBO_ARTEFACT) for n in usable}
        for n in usable:
            print(f"   {n:10s} placebo Contrast {p4res[n]['contrast']:+.4f}   "
                  f"real {res[n]['contrast']:+.4f}")
        p4 = bool(np.sign(p4res[primary]["contrast"]) == np.sign(res[primary]["contrast"]))
        print(f"   P4 {'PASSED' if p4 else '*** FAILED — the second proxy reverses the sign'}")
        st["p4"] = {n: p4res[n]["contrast"] for n in usable} | {"passed": p4}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p4 is False:
        verdict = "not_interpretable"
        print("   NOT INTERPRETABLE: two near-identical EMG proxies give opposite signs, so this is")
        print("   estimator noise rather than artefact robustness.")
    elif not excludes or (len(usable) > 1 and not agree):
        verdict = "no_evidence"
        print("   NO EVIDENCE either way — the expected outcome at 8 and 20 subjects, and it supports")
        print("   NEITHER explanation. It does not vindicate E36's post-hoc defence (rule 31).")
    elif res[primary]["contrast"] > 0:
        verdict = "deflation_supported"
        print("   DEFLATION SUPPORTED: wPLI is artefact-robust relative to its capability. E36's post-hoc")
        print("   defence does not replicate, and E35/E36's family split is materially weakened —")
        print("   every document carrying it must be updated to say so.")
    else:
        verdict = "defence_replicates"
        print("   DEFENCE REPLICATES: wPLI is no more artefact-robust than the rest, on independent")
        print("   cohorts with an independent implementation. Scope: EMG only, propofol only, scalp.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
