#!/usr/bin/env python3
"""E28 — Discovery Challenge B, by substitution: does spontaneous EEG predict who can command-follow?

REGISTERED BEFORE `eegmmidb_rest.csv` AND `eegmmidb_bci.csv` ARE COMPLETE, and before any candidate value
from either has been read. What has been read is one smoke row of the label builder (S001: imagery AUC
0.603, permutation p = 0.124, null mean ~0.47) — the machinery check that the decoder runs at all, and the
finding that the permutation null is NOT 0.5, which is why P1 gates on the null rather than on chance.

    **A NUMBER IN AN EARLIER DRAFT OF THIS PARAGRAPH WAS WRONG AND IS CORRECTED RATHER THAN OVERWRITTEN.**
    It said S001 scored 0.690 with p = 0.015. That came from the label builder's FIRST implementation,
    which fetched one HTTP window per trial — and `read_edf_window_http` floors its start to the EDF
    record boundary (`skip = int(start_seconds / rec_dur)`), so every 0.5-3.5 s epoch was silently shifted
    by up to a full second, a third of its own length. The current implementation reads each run once and
    slices in memory, which is exact. Error-catalogue rule 2: a number inherited from a superseded
    extraction must be re-derived, never carried forward. Rule 20 is how it was caught — two
    implementations of the same quantity disagreed (0.690 against 0.603) and were diffed rather than
    reconciled by preference.

WHY THIS DEPOSIT AND NOT A DoC ONE. Challenge B asks for spontaneous EEG features associated with
command-following. The deposits that label command-following in disorders of consciousness are
access-controlled — Bath is requested and not granted — and **the one open DoC deposit this project holds
(figshare 23552964) ships no label file at all**: 298 files, every one BrainVision, 98 subject stems, no
group assignment and no CRS-R, against a description claiming 32 healthy and 59 patients. It cannot answer
the question or any weaker version of it.

**Motor imagery is command-following that produces no movement.** The subject is instructed, complies
covertly, and the only evidence is the EEG — which is structurally the covert-consciousness problem, in a
population where the answer is checkable. And 15-30 % of healthy people cannot drive a motor-imagery BCI, so
the ability has real spread rather than being uniformly present.

WHAT THE SUBSTITUTION COSTS, AND IT IS THE FIRST THING ANY READER SHOULD BE TOLD. **A healthy subject who
cannot drive a BCI is not unconscious.** They are inattentive, untrained, or have a low sensorimotor rhythm.
The populations differ, the failure modes differ, and a feature that predicts one may be silent for the
other. What transfers is the FORM of the claim and the machinery for testing it. **No sentence from this
experiment may be written as a claim about disorders of consciousness**, and that is not a hedge — it is the
condition under which running this at all is honest.

THE INCUMBENT, BECAUSE A MARKER PRESENTED ALONE IS NOT A RESULT. This question has published prior art:

    Blankertz B, Sannelli C, Halder S, Hammer EM, Kubler A, Muller KR, Curio G, Dickhaus T.
    "Neurophysiological predictor of SMR-based BCI performance." NeuroImage 2010 Jul 15; PMID 20303409.

verified through NCBI E-utilities rather than WebFetch (rules 25 and 39). It reports that a measure computed
from RESTING EEG predicts subsequent BCI performance. So Challenge B's substitute question already has an
answer, and a candidate has to be measured against it exactly as Challenge C's candidates were measured
against BIS.

    **THE INCUMBENT HERE IS A PROXY AND IS DECLARED AS ONE.** Blankertz's predictor is computed at CENTRAL
    electrodes and corrected against the aperiodic noise floor at the mu peak. `relative_alpha_power` in
    this registry is whole-head and uncorrected. It is therefore a **weaker** incumbent than the published
    one, which makes beating it a weaker claim than beating Blankertz — and that direction is stated here
    rather than discovered later. Reimplementing the published predictor faithfully would add a candidate
    to the search space and is deferred deliberately, not overlooked.

REGISTERED PREDICTIONS, evaluated in this order. A failed gate makes the downstream verdict ABSENT, not
negative (rule 31).

    P1  MACHINERY GATE, three parts, using no candidate from the resting table.
        (a) **THE LABEL MUST BE REAL.** At least `MIN_DECODERS_FRACTION` of subjects must have a
            permutation p below 0.05, and the group median imagery AUC must exceed the group median
            permutation-null mean. If nobody decodes above their own null, the label is noise and predicting
            it is meaningless. The null is per subject and measured, because the smoke row already showed it
            sitting at 0.466 rather than 0.5 — a small-sample bias of the CV estimator that a chance
            assumption would have mistaken for signal.
        (b) **THE LABEL MUST VARY — rule 32.** The interquartile range of imagery AUC must be at least
            `MIN_IQR`. A cohort where everyone decodes equally well has nothing to predict, and a
            correlation computed in it would be noise regardless of its interval.
        (c) COVERAGE — at least `MIN_SUBJECTS` subjects with both a resting feature row and a label.

    P2  THE INCUMBENT'S SCORE, printed before any candidate: the proxy SMR predictor's Spearman correlation
        with imagery AUC across subjects, with a bootstrap CI. **This is the bar.**

    P3  THE PRIMARY. `exponent_high` computed from the RESTING runs only, correlated with imagery AUC across
        subjects, bootstrap CI excluding zero — and its |rho| must exceed the incumbent's. A candidate that
        cannot beat a deliberately weakened version of a fifteen-year-old published predictor has not earned
        a place in a verifier stack.

    P4  THE PLACEBO, AND IT GATES THE VERDICT (rule 34). The identical analysis with the label replaced by
        **decoding accuracy for EXECUTED movement** (runs R03/R07/R11) instead of imagined. Executed
        movement produces real motor-cortex activation and is decodable from signal quality and anatomy in
        people who cannot imagine at all. **So a resting feature that predicts executed decoding as well as
        imagined decoding is tracking how legible that subject's motor cortex is, not their ability to
        comply covertly** — which is the whole content of Challenge B. The imagery association must exceed
        the executed one; this is a COMPARISON against the real effect, never an absolute threshold
        (rule 37).
            Its limitation, stated before it runs: executed and imagined decoding are correlated across
        subjects for real reasons, so this placebo is CONSERVATIVE — it can withdraw a true effect and
        cannot manufacture one. Same shape as E25's remifentanil gate, and E25 is the reason it is worded
        this carefully.

    P5  THE EYES-OPEN / EYES-CLOSED SPLIT, reported and not gating. The resting features exist for both
        R01 and R02. A predictor that only works eyes-closed is describing alpha; one that works in both is
        describing something more stable. Reported per condition.

    NOTE ON THE OTHER CANDIDATES. The primary is one pre-declared candidate, so the headline is one test.
    The rest are context with UNADJUSTED intervals and would have to pass `verifier/multiplicity.py` before
    becoming a claim. None is made here.

    FALSIFICATION: P3's interval includes zero, or P3 fails to beat the incumbent, or P4 fails. Each is a
    result.

SCOPE AND LIMITS.
  * **Not a DoC result.** Repeated because it is the limit that matters and the one most easily lost in
    summary.
  * **The label is one decoder's opinion.** Log band power at C3/C4/Cz in mu and beta, logistic regression,
    5-fold within-subject CV. A better decoder would rank subjects differently, and "who can command-follow"
    would move with it. The decoder was chosen for being boring and registered before it ran, not tuned.
  * **Between-subject, n ~ 105.** Every association here is across people, so any subject-level confound —
    age, skull thickness, electrode fit, alertness on the day — is uncontrolled. `eegmmidb` ships no
    demographics at all, so none can be adjusted for. This is the single largest weakness and no gate here
    repairs it.
  * **Four subjects are excluded by name** (S088, S089, S092, S100), documented by PhysioNet as damaged.
    Named rather than discovered (rule 14).
  * 64 channels at 160 Hz: `exponent_gamma` (50-90 Hz) is above Nyquist and NaN by design.

--------------------------------------------------------------------------------------------------------
OUTCOME. **P1(a) FAILED at 16.3 % against a registered floor of 20 %. Nothing downstream was computed and
no resting feature was ever touched. The verdict is ABSENT, not negative (rule 31) — and the floor is NOT
being lowered, because the diagnosis below is a reason to distrust the gate's SPECIFICATION, which is not
the same thing as a reason to pass it.**

    (a) 17 of 104 subjects (16.3 %) beat their own permutation null at p < 0.05, against a floor of 20 %.
        Median imagery AUC 0.531 against a median per-subject null of 0.461.        *** FAILED
    (b) imagery AUC IQR 0.212, floor 0.10.                                              PASSED
    (c) 104 subjects with both a resting row and a label, floor 60.                      PASSED

**THE MACHINERY IS BEHAVING, AND THE ONE CHECK THAT SAYS SO IS THE PLACEBO ARM.** Executed movement — real
fist movement, which must be easier to decode than imagined fist movement — scores a median AUC of 0.545
and **24.0 %** beating their own null, against imagery's 0.531 and 16.3 %. The ordering is right in both
statistics. A decoder that was simply broken would not have produced it, and a label that was pure noise
would not have put 17 of 104 subjects past p < 0.05 where 5 are expected by chance. **So the label carries
real signal at the level of the COHORT and almost none at the level of the SUBJECT**, and the second of
those is what Challenge B's substitution needs.

**WHY, AND IT IS ARITHMETIC RATHER THAN BIOLOGY.** `eegmmidb`'s imagery left/right protocol is runs R04,
R08 and R12, roughly fifteen cued trials each — **45 trials per subject, about 22 per class, and that is
the entire deposit.** A per-subject permutation test at that size can only reach p < 0.05 for a fairly
large true effect, so the fraction reaching significance is a statement about detection power at n = 45,
not about how many of these people can drive a BCI.

**THE GATE ASKED FOR THE WRONG QUANTITY, AND SAYING SO CHANGES NOTHING ABOUT THIS RESULT.** The header
argues from the BCI-illiteracy literature that 15-30 % of healthy people cannot drive a motor-imagery BCI,
so 70-85 % can; `MIN_DECODERS_FRACTION = 0.20` was set as a lenient version of that. But the literature's
figure is a **prevalence**, measured over hundreds of trials, and the gate applied it to a **detection
rate** over 45. Those are different quantities and the floor was never the right instrument for the
question. That is error-catalogue rule 30 exactly: pre-registration stops a bar moving afterwards, it does
not stop it being set badly, and the failure is harder to see because the paperwork looks correct.

**What follows from that is a successor, not a re-run.** Lowering the floor now would be indistinguishable
from moving it, whatever the justification, and the whole point of writing the rule down is that the
justification always feels good at the time. E28 stands as ABSENT.

**WHAT THE SUCCESSOR MUST CHANGE, AND IT IS THE INSTRUMENT.** The question a noisy label has to answer
before it can be a regression target is not "how many subjects reach significance" but **"how much of the
between-subject variance in this label is real"** — that is, its RELIABILITY. It is directly measurable
from the trials already extracted: split each subject's trials in half, decode each half separately, and
correlate the two per-subject AUC estimates across subjects. A label whose split-half reliability is near
zero cannot correlate with any resting feature no matter how good the feature is, and the observed
ceiling on any such correlation is bounded by the square root of that reliability. **That number is worth
more than E28's verdict would have been**, because it settles whether the healthy-BCI substitution is
viable at all rather than whether one candidate beat one incumbent — and it can kill the substitution
honestly, which is what Challenge B most needs.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                          # noqa: E402
from bsde.candidates.seed import seed_registry                                          # noqa: E402
from bsde.verifier.stats import cluster_bootstrap_ci, spearman                          # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
REST = os.path.join(RESULTS, "eegmmidb_rest.csv")
LABEL = os.path.join(RESULTS, "eegmmidb_bci.csv")
PLACEBO = os.path.join(RESULTS, "eegmmidb_bci_executed.csv")
OUT = os.path.join(RESULTS, "e28_challenge_b.json")

PRIMARY = "exponent_high"
INCUMBENT = "relative_alpha_power"
MIN_SUBJECTS = 60
MIN_IQR = 0.10
MIN_DECODERS_FRACTION = 0.20
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "wpli_alpha", "spatial_participation_ratio", "uce_v1")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _registered_order() -> None:
    print("   Registered order of evaluation, fixed here and not re-openable:")
    print(f"     P1 GATE  the label must be REAL (>= {MIN_DECODERS_FRACTION:.0%} of subjects beating their")
    print(f"              own permutation null), must VARY (IQR >= {MIN_IQR}), and cover >= "
          f"{MIN_SUBJECTS} subjects")
    print(f"     P2       the incumbent ({INCUMBENT}, a declared-weak proxy for Blankertz 2010) — the bar")
    print(f"     P3       {PRIMARY} from REST must correlate with imagery AUC and beat the incumbent")
    print("     P4 GATE  EXECUTED-movement decoding must be predicted LESS well than imagined")
    print("     P5       eyes-open vs eyes-closed — reported, not gating")


def _rest_by_subject(path):
    """Per subject, the mean of each candidate over the resting runs, plus per-condition values."""
    rows = [r for r in csv.DictReader(open(path, newline="")) if r.get("status") == "ok"]
    subs, per_cond = {}, {}
    for r in rows:
        s = r.get("subject", "")
        subs.setdefault(s, []).append(r)
        per_cond.setdefault((s, r.get("meta_condition", "")), r)
    return subs, per_cond


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    rest = os.path.abspath(args[args.index("--rest") + 1]) if "--rest" in args else REST
    label = os.path.abspath(args[args.index("--label") + 1]) if "--label" in args else LABEL
    placebo = os.path.abspath(args[args.index("--placebo") + 1]) if "--placebo" in args else PLACEBO
    seed_registry()
    print("E28 — Challenge B by substitution: resting EEG vs motor-imagery command-following")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    print("   CLAIM SCOPE: healthy BCI performance is NOT disorders-of-consciousness command-following.")
    print("   No sentence from this experiment may be written as a DoC claim.")
    if not (os.path.exists(rest) and os.path.exists(label)):
        print(f"\n   *** absent: "
              f"{[os.path.basename(p) for p in (rest, label) if not os.path.exists(p)]}")
        _registered_order()
        return 2

    by_sub, per_cond = _rest_by_subject(rest)
    lab = {r["subject"]: r for r in csv.DictReader(open(label, newline="")) if r.get("status") == "ok"}
    common = sorted(set(by_sub) & set(lab))
    if len(common) < MIN_SUBJECTS:
        print(f"\n   *** {len(common)} subjects with both a resting row and a label, below the floor of "
              f"{MIN_SUBJECTS}. The streams are still running; nothing is reported.")
        _registered_order()
        return 2

    y = np.array([_f(lab[s]["imagery_auc"]) for s in common])
    pperm = np.array([_f(lab[s]["perm_p"]) for s in common])
    nullm = np.array([_f(lab[s]["perm_null_mean"]) for s in common])
    subj = np.array(common)

    def rest_col(name):
        out = []
        for s in common:
            v = [_f(r.get(name, "")) for r in by_sub[s]]
            v = [x for x in v if np.isfinite(x)]
            out.append(float(np.mean(v)) if v else float("nan"))
        return np.asarray(out, float)

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (the label, before any resting feature is touched)")
    print("=" * 100)
    frac = float(np.mean(pperm < 0.05))
    med_y, med_null = float(np.nanmedian(y)), float(np.nanmedian(nullm))
    iqr = float(np.nanquantile(y, 0.75) - np.nanquantile(y, 0.25))
    a_ok = frac >= MIN_DECODERS_FRACTION and med_y > med_null
    b_ok = iqr >= MIN_IQR
    print(f"   subjects with both a resting row and a label: {len(common)}")
    print(f"   (a) beating their own permutation null at p < 0.05: {int((pperm < 0.05).sum())}/"
          f"{len(common)} ({frac:.1%}); median imagery AUC {med_y:.3f} vs median null {med_null:.3f}   "
          f"{'PASSED' if a_ok else '*** FAILED'}")
    print(f"   (b) imagery AUC IQR {iqr:.3f} (floor {MIN_IQR})   {'PASSED' if b_ok else '*** FAILED'}")
    print(f"   (c) coverage {len(common)} >= {MIN_SUBJECTS}   PASSED")
    print("   NOTE: the null is measured per subject, not assumed to be 0.5. The smoke row already showed")
    print("   it at 0.466 — a small-sample bias of the CV estimator that a chance assumption would have")
    print("   read as signal.")
    p1 = bool(a_ok and b_ok)
    state = {"experiment": "E28", "n_subjects": len(common),
             "p1": {"frac_beating_null": frac, "median_auc": med_y, "median_null": med_null,
                    "iqr": iqr, "passed": p1}}
    if not p1:
        print("\n   P1 FAILED. Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    rng = np.random.default_rng(20260730)
    print("\n" + "=" * 100)
    print(f"P2 — THE BAR: the incumbent ({INCUMBENT}, a DECLARED-WEAK proxy for Blankertz 2010)")
    print("=" * 100)
    xi = rest_col(INCUMBENT)
    m = np.isfinite(xi) & np.isfinite(y)
    inc_rho = spearman(xi[m], y[m])
    ilo, ihi, _ = cluster_bootstrap_ci(lambda i: spearman(xi[m][i], y[m][i]), subj[m], rng, reps=2000)
    print(f"   rho {inc_rho:+.3f} [{ilo:+.3f}, {ihi:+.3f}] over {int(m.sum())} subjects")
    print("   Blankertz's predictor is central and noise-floor-corrected; this is whole-head and")
    print("   uncorrected, so it is WEAKER than the published one and beating it is a weaker claim.")
    state["p2"] = {"incumbent": INCUMBENT, "rho": float(inc_rho), "ci": [float(ilo), float(ihi)]}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print(f"P3 — PRIMARY: {PRIMARY} from the RESTING runs vs imagery decoding ability")
    print("=" * 100)
    xp = rest_col(PRIMARY)
    mp = np.isfinite(xp) & np.isfinite(y)
    rho = spearman(xp[mp], y[mp])
    lo, hi, _ = cluster_bootstrap_ci(lambda i: spearman(xp[mp][i], y[mp][i]), subj[mp], rng, reps=2000)
    excludes = lo > 0 or hi < 0
    beats = abs(rho) > abs(inc_rho)
    p3 = bool(excludes and beats)
    print(f"   rho {rho:+.3f} [{lo:+.3f}, {hi:+.3f}] over {int(mp.sum())} subjects")
    print(f"   interval {'excludes' if excludes else 'INCLUDES'} zero; "
          f"|rho| {abs(rho):.3f} {'>' if beats else '<='} incumbent's {abs(inc_rho):.3f}")
    print(f"   P3 {'PASSED' if p3 else '*** FAILED'}")
    state["p3"] = {"rho": float(rho), "ci": [float(lo), float(hi)], "beats_incumbent": bool(beats),
                   "passed": p3}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — PLACEBO GATE: EXECUTED movement must be predicted LESS well than imagined")
    print("=" * 100)
    print("   Executed movement is decodable from signal quality and motor-cortex accessibility in people")
    print("   who cannot imagine at all. A resting feature predicting it as well as imagery is tracking")
    print("   how legible that cortex is, not the ability to comply covertly — which is Challenge B.")
    if not os.path.exists(placebo):
        print(f"\n   {os.path.basename(placebo)} absent — the executed-movement label has not been built.")
        print("   P4 is ABSENT, so P3 is UNGATED and provisional (rule 31).")
        p4 = None
        state["p4"] = {"passed": None, "reason": "placebo label absent"}
    else:
        pl = {r["subject"]: r for r in csv.DictReader(open(placebo, newline=""))
              if r.get("status") == "ok"}
        both = [s for s in common if s in pl]
        ye = np.array([_f(pl[s]["imagery_auc"]) for s in both])
        xe = np.array([rest_col(PRIMARY)[common.index(s)] for s in both])
        me = np.isfinite(xe) & np.isfinite(ye)
        if me.sum() < MIN_SUBJECTS:
            print(f"\n   only {int(me.sum())} subjects with both labels — P4 ABSENT, P3 ungated.")
            p4 = None
            state["p4"] = {"passed": None, "reason": "too few subjects with both labels"}
        else:
            rho_e = spearman(xe[me], ye[me])
            elo, ehi, _ = cluster_bootstrap_ci(lambda i: spearman(xe[me][i], ye[me][i]),
                                               np.array(both)[me], rng, reps=2000)
            p4 = bool(abs(rho) > abs(rho_e))
            print(f"\n   executed-movement rho {rho_e:+.3f} [{elo:+.3f}, {ehi:+.3f}] over "
                  f"{int(me.sum())} subjects")
            print(f"   imagined          rho {rho:+.3f}")
            print(f"\n   P4 {'PASSED' if p4 else '*** FAILED — P3 is WITHDRAWN: this tracks cortical legibility, not covert compliance'}")
            state["p4"] = {"executed_rho": float(rho_e), "ci": [float(elo), float(ehi)], "passed": p4}

    # ------------------------------------------------------------------ P5
    print("\n" + "=" * 100)
    print("P5 — EYES OPEN vs EYES CLOSED (reported, not gating)")
    print("=" * 100)
    out5 = {}
    for cond in ("eyes_open", "eyes_closed"):
        vals = np.array([_f((per_cond.get((s, cond)) or {}).get(PRIMARY, "")) for s in common], float)
        mc = np.isfinite(vals) & np.isfinite(y)
        if mc.sum() < MIN_SUBJECTS:
            print(f"   {cond:12s} only {int(mc.sum())} subjects; not reported")
            continue
        r = spearman(vals[mc], y[mc])
        out5[cond] = {"rho": float(r), "n": int(mc.sum())}
        print(f"   {cond:12s} rho {r:+.3f} over {int(mc.sum())} subjects")
    print("   A predictor that works only eyes-closed is describing alpha; one that works in both is")
    print("   describing something more stable.")
    state["p5"] = out5

    # ------------------------------------------------------------------ context
    print("\n" + "=" * 100)
    print("CONTEXT — other candidates, UNADJUSTED, not claims (see the header note)")
    print("=" * 100)
    print(f"   {'candidate':28s} {'rho vs imagery AUC':>20s} {'n':>6s}")
    ctx = {}
    for cname in REPORT:
        v = rest_col(cname)
        mc = np.isfinite(v) & np.isfinite(y)
        if mc.sum() < MIN_SUBJECTS:
            print(f"   {cname:28s} {'—':>20s} {int(mc.sum()):6d}")
            continue
        r = spearman(v[mc], y[mc])
        ctx[cname] = float(r)
        print(f"   {cname:28s} {r:+20.3f} {int(mc.sum()):6d}")
    state["context"] = ctx

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p4 is False:
        print("   P3 is WITHDRAWN by its own placebo: the association tracks cortical legibility rather")
        print("   than the ability to comply with an instruction. Challenge B is not met.")
        verdict = "withdrawn_by_placebo"
    elif p4 is None:
        print("   UNGATED — the placebo could not be evaluated, so P3 is provisional (rule 31).")
        verdict = "ungated"
    elif p3:
        print("   Challenge B's SUBSTITUTE question is answered YES: a spontaneous resting feature predicts")
        print("   who can command-follow covertly, beats a (deliberately weakened) published incumbent, and")
        print("   survives a placebo that holds cortical legibility. **This is a healthy-BCI result and is")
        print("   NOT a disorders-of-consciousness result.**")
        verdict = "met_on_substitute_question"
    else:
        print("   Challenge B's substitute question is answered NO on this deposit: the candidate either")
        print("   did not clear its interval or did not beat the incumbent. That is a result.")
        verdict = "not_met"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
