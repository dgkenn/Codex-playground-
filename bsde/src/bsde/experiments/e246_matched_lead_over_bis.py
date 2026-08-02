#!/usr/bin/env python3
"""E246 -- Challenge C: does an EEG measure detect EMERGENCE before BIS *at matched smoothing and
matched false-alarm rate*?

PRE-REGISTRATION. Written and committed before any statistic in it has been computed. The dense
transition extraction it reads was still running when this file was written; the extractor
(`bsde/scripts/stream_vitaldb_transitions.py`) chooses window times from the clinical record alone and
has never seen a candidate, a BIS value or a verdict.

------------------------------------------------------------------------------------------------------
THE BRIEFED CHALLENGE, VERBATIM (bsde/governance/CHALLENGES.json):

    C: "seeing a transition before the conventional monitor"

This is a TEMPORAL claim. E240 replicated a DISCRIMINATIVE one (the aperiodic exponent separates depth
strata) and `DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md` retired that as already-established prior art.
This file is the first experiment in the project to test the briefed claim in its own units -- seconds.

------------------------------------------------------------------------------------------------------
WHY THIS IS NOT THE SAME AS THE PUBLISHED RESULT, AND WHAT THE CONTRIBUTION ACTUALLY IS

"An index leads BIS" is published. Ra, Li & Li 2021 (PMID 33978842) report a spectral-entropy index
reacting 158 s before BIS (range 6-331, n = 14). BIS's own lag is measured at 20-160 s and is asymmetric
by direction (PMIDs 16508396, 19648154, 22584557, 32040794). Kavuncu et al. 2026 (PMID 42351597) predict
BIS-threshold crossings 3/5/10 min ahead on 5,471 VitalDB cases. **Leading BIS is not the contribution.**

THE GAP IS MEASURED, NOT ASSUMED. A PubMed check via E-utilities (records retrieved and parsed, never
WebFetch -- rules 25 and 39) returned, and I verified the three load-bearing records myself:

  * The closest existing work is one group's series that empirically measures each monitor's OWN raw
    latency by replaying identical transition EEG through several devices -- Pilge 2006 (PMID 16508396,
    delays 14-155 s), Zanner 2009 (PMID 19648154), Kreuzer 2012 (PMID 22584557), Zanner 2021
    ("Time delay of the qCON monitor and its performance during state transitions", J Clin Monit Comput
    2021;35:379-386, PMID 32040794 -- title, journal, volume and pages verified via esummary). They
    establish that indices differ in delay by up to an order of magnitude. **None equalises the
    smoothing window before comparing, and none reports latency at a matched false-alarm rate.**
  * The exact phrases "same smoothing window", "matched false alarm rate" and "equal false alarm rate"
    return `quotedphrasesnotfound` from PubMed -- they occur in no indexed record.
  * The discipline EXISTS, in a neighbouring field, which is the strongest form this gap could take.
    Seizure detection reports detection delay paired with false-positives-per-hour as standard
    (Baumgartner & Koren 2018, "Seizure detection using scalp-EEG", Epilepsia 2018;59 Suppl 1:14-22,
    PMID 29873826 -- verified), and Snyder et al. 2008 ("The statistics of a practical seizure warning
    system", J Neural Eng 2008;5:392-401, PMID 18827312 -- verified) proposes exactly this comparison as
    a methodological advance, in words checked against the retrieved abstract: *"the difference between
    algorithm and chance sensitivities given a constraint on proportion of time spent in warning"*.

So the contribution is importable rather than invented: a norm that is standard one field over has never
crossed into anaesthesia depth-index comparison. That is a citable gap.

There are exactly two trivial ways to lead a monitor, and neither is a discovery:

  (T1) BE LESS SMOOTHED. BIS is displayed after internal trend averaging. Any measure computed on a
       shorter effective window reacts sooner to the same underlying change, with no extra information.
  (T2) BE MORE TRIGGER-HAPPY. A detector whose threshold sits closer to its own baseline fires earlier
       on noise alone. Lead and false-alarm rate trade off along one curve; quoting a lead without the
       operating point quotes one coordinate of a two-dimensional object.

**The contribution is the ablation that removes both.** The primary is measured with the candidate
smoothed UP to BIS's own measured effective window, and with both detectors calibrated to the same
baseline z-threshold on the same 10 s grid, so the number of firing opportunities per case is identical
by construction. A lead that survives that is information; a lead that dies is engineering. Catalogue
rule 49: before running a comparison, compute what the statistic is FORCED to be by the machinery.

If this returns ARTEFACT -- lead at L0, gone at L* -- that is a publishable negative and the line ends
cleanly, because it is a direct methodological criticism of a live literature. Both outcomes are worth
the run, which is the property a design should have before it is registered.

------------------------------------------------------------------------------------------------------
COHORT, AND ONE CONSTRAINT DECLARED IN ADVANCE

`bsde/results/vitaldb_transitions.s*.csv`: 10 s windows on a 10 s stride, -600 s to +600 s around each
anaesthesia transition, from `VitalDBTargetedAdapter`.

**THIS IS AN EMERGENCE EXPERIMENT, NOT AN INDUCTION ONE, AND THAT IS A PROPERTY OF THE DEPOSIT.** The
adapter drops planned times before case-relative t = 0, and in VitalDB the BIS sensor is generally
applied AFTER induction, so `anestart` is negative for the great majority of cases. Measured on the
partial extraction at the time of writing (216 cases): 148 cases carry >= 60 windows around `aneend`
against 14 around `anestart`. Induction is therefore NOT tested here and no claim is made about it --
loss and recovery are not each other's reverse (`bsde/src/bsde/ingestion/vitaldb.py` module docstring).

------------------------------------------------------------------------------------------------------
THE CANDIDATE IS PRE-DECLARED (rule 45's other half)

PRIMARY CANDIDATE: `whole_head_exponent`. It is the one measure this project has replicated across
independent deposits (E222 Sleep-EDFx, E240 ds006695), so it is the only one with a prior claim on being
tested here rather than screened. INCUMBENT: **BIS**, the conventional monitor named in the challenge.

Every other panel column is run too, and every one of them is DESCRIPTIVE: reported, never gated, never
promoted to a verdict. A screen over 24 columns is a screen and this file does not pretend otherwise.

------------------------------------------------------------------------------------------------------
DETECTOR, IDENTICAL FOR BOTH SERIES

For each case, on the emergence window:

  baseline  B = [aneend - 600, aneend - 300)   -- deep anaesthesia, 30 windows on the 10 s grid
  test      T = [aneend - 300, aneend + 600]   -- 91 windows

  Both BIS and the candidate are placed on the SAME 10 s grid (BIS by averaging its 1 Hz trace inside
  each window -- which is itself a smoothing operation, applied to both, and therefore not a source of
  asymmetry). Detection time = the first t in T at which the z-score against B, signed by the declared
  direction, reaches k.

  k = 3.0, DERIVED not chosen (rule 63): with 30 baseline windows estimating mu and sigma and 91 test
  windows, a Gaussian series gives an expected 91 * 0.00135 = 0.12 spurious crossings per case, i.e. a
  baseline false-alarm rate around 12 % of cases. That is the resolution the machinery has; a k chosen
  to make the rate "look small" would only measure the choice. The realised rate is MEASURED by G2 and
  reported, for both detectors, rather than assumed.

  BIS direction is +1: BIS rises at emergence. This is not fitted.
  CANDIDATE direction is fitted on a DISJOINT HALF OF THE CASES and applied to the other half, then
  swapped and pooled (rule 73's concern in reverse -- a direction fitted on the same cases it is
  evaluated on is a free parameter, and choosing it from the timing would be the whole result).

  LEAD = t_BIS - t_candidate, in seconds, per case. Positive means the candidate fired first.

------------------------------------------------------------------------------------------------------
THE SMOOTHING LADDER -- the registered primary is the MIDDLE rung, not the first

L0  candidate unsmoothed          -- the naive comparison, i.e. what the literature reports
L*  candidate smoothed to BIS's MEASURED effective window   <-- **PRIMARY**
L2  candidate smoothed to 2x BIS's effective window         -- over-correction

BIS's effective smoothing is MEASURED from its own 1 Hz trace rather than taken from the manufacturer:
the equivalent rectangular window of a first-order autoregressive fit on the baseline segment,
w_eff = (1 + rho) / (1 - rho) samples, pooled as the median across cases. Reported with its spread.
If that estimate is not finite or lands below one grid step, L* is UNDEFINED and the file says so and
declines a verdict rather than substituting a manufacturer number (rule 31: when a precondition fails
the downstream verdict is absent, not negative).

------------------------------------------------------------------------------------------------------
GATES. Each is evaluated AFTER the primary and can only invalidate a pass, never rescue a null (rule 37).

G1  INCUMBENT ALIVE (rules 33, 53). BIS must actually detect emergence: its detection time must fall
    within +/- 300 s of `aneend` in >= 50 % of analysable cases. If BIS does not see the transition,
    "before BIS" is not a meaningful comparison and no candidate can earn credit for beating it.

G2  FALSE-ALARM RATES COMPARABLE. On a HELD-OUT baseline segment [aneend - 900, aneend - 600) -- not the
    one the threshold was calibrated on -- the two detectors' firing rates must be within a factor of
    two of each other. Two is derived from the count, not chosen for looseness: with ~30 held-out
    windows per case the rate is resolvable to roughly +/- 1 case in 30, and a factor below two is
    inside that resolution. If the candidate's rate is MORE than twice BIS's, any lead it shows is the
    T2 artefact and the file must say so.

G3  CAPABILITY, IN BOTH DIRECTIONS (rule 40, and rule 81's mirror). Two synthetic candidates are built
    from each case's own BIS series: one advanced by exactly +60 s and one delayed by exactly -60 s. The
    estimator must return a median lead within +/- 20 s of +60 and of -60 respectively. A gate that can
    only fail in one direction is half a gate; this one is constructed so that a estimator biased either
    way breaks it.

G4  SUPPORT. >= 40 cases contribute a finite lead at L*, and both detectors fire in each of them. Forty
    is the count at which a case-level bootstrap of a median has a percentile interval narrower than the
    10 s grid resolution under the observed spread; below it the statistic cannot resolve its own units.

PLACEBO (rule 34, as a DISTRIBUTION per rule 79, never a single draw per rule 72).

P1, THE REGISTERED PLACEBO -- CASE-MISMATCHED PAIRING. Each case's candidate detection time is paired
with a DIFFERENT case's BIS detection time, drawn at random, 200 times. This is rule 82's move: the
control object already exists in the deposit and nothing has to be synthesised, so nothing has to be
argued about what the synthesis preserved. What it destroys is stated explicitly and is exactly one
thing -- the within-case correspondence between the two detectors -- while preserving both series'
dynamics, both detectors' calibration, and both marginal distributions of firing time.

It is aimed squarely at the T2 artefact and this is why it is the primary placebo. If the candidate
simply fires EARLY IN THE WINDOW as a marginal habit -- irrespective of when that case's transition
actually happened -- then mismatching cases reproduces the lead in full, and the "lead" was never a
within-case timing relation at all. A real lead must collapse under mismatching. The placebo fires if
>= 5 % of draws reach or exceed the observed median lead.

P2, SECONDARY, AND DECLARED IN ADVANCE AS POSSIBLY NOT EVALUABLE. A random landmark drawn 600-1200 s
from the true one. The extraction covers only +/- 600 s around each transition, so a displaced landmark
loses most of its test span and many cases will fall below the support floor. If fewer than the floor
survive, this arm reports NOT EVALUABLE and contributes nothing -- it does not report a pass (rule 31:
when a precondition fails the downstream verdict is absent, not negative; rule 48: a placebo cannot
validate anything when its own support is gone). It is registered rather than dropped because a
sensitivity arm that cannot execute must still be reported (rule 48's second half).

Rule 48 also governs the degenerate case for both arms: if the primary interval includes zero, both
placebos are marked NOT INFORMATIVE rather than PASSED, because there is no real effect for a fake
landmark to fail to reproduce.

------------------------------------------------------------------------------------------------------
VERDICT RULE. The wrong-direction case is enumerated FIRST and explicitly (rule 37, five prior
occurrences in this project's catalogue). A confidence interval answers "does this exclude zero", never
"does this support the hypothesis", and those are different questions.

  (a) LAGS       -- CI for the median lead at L* lies entirely BELOW zero. The candidate is LATER than
                    BIS. This REFUTES the challenge for this candidate and is reported as a refutation,
                    not as "no evidence".
  (b) ABSENT     -- CI includes zero. No timing difference resolvable at this n and this grid.
  (c) LEADS      -- CI entirely ABOVE zero. Provisional only; then the gates and the placebo are read,
                    and any failure downgrades this to NOT INTERPRETABLE, never to (a) or (b).
  (d) ARTEFACT   -- a special case of (b) or (a) that must be named when it occurs: the CI at L0 lies
                    above zero and the CI at L* does not. The lead existed only while the candidate was
                    less smoothed than the monitor. This is the outcome the whole design exists to be
                    able to detect and it is a RESULT, not a failure to find one.

FALSIFICATION. If `whole_head_exponent` returns (a), (b) or (d) at L*, Challenge C's temporal claim is
not supported for this candidate on this deposit, and no descriptive column may be promoted in its
place -- the screen is a screen (rule 70's neighbour: a candidate list is not a set of primaries).

    python -m bsde.experiments.e246_matched_lead_over_bis
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
sys.path.insert(0, os.path.join(ROOT, "src"))

GRID_S = 10.0
BASE_LO, BASE_HI = -600.0, -300.0
TEST_LO, TEST_HI = -300.0, 600.0
HELDOUT_LO, HELDOUT_HI = -900.0, -600.0
K = 3.0
PRIMARY = "whole_head_exponent"
MIN_CASES = 40
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}


def _f(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _panel_columns(header):
    return [c for c in header if not c.startswith("meta_") and c not in SKIP]


# ----------------------------------------------------------------------------------------------------
# loading


def load_cases(paths):
    """case id -> {'t': [...], 'bis': [...], <col>: [...]} on the case's own time axis, sorted by time.

    BIS per window is taken from `meta_bis_trace` (1 Hz, "t:value|..." with 0 meaning invalid) and
    averaged inside the window. That averaging is applied to BIS and to nothing else, and it is the
    ONLY place BIS is treated differently from a candidate -- it exists to put both on one grid.
    """
    cases = collections.defaultdict(lambda: collections.defaultdict(list))
    cols = None
    for p in sorted(paths):
        with open(p) as fh:
            rd = csv.DictReader(fh)
            if cols is None:
                cols = _panel_columns(rd.fieldnames or [])
            for r in rd:
                if r.get("status") != "ok":
                    continue
                cid = r.get("meta_caseid")
                t = _f(r.get("meta_t_s"))
                if not cid or not math.isfinite(t):
                    continue
                d = cases[cid]
                d["t"].append(t)
                d["rel_aneend"].append(_f(r.get("meta_rel_aneend_s")))
                d["rel_anestart"].append(_f(r.get("meta_rel_anestart_s")))
                vals = []
                for tok in (r.get("meta_bis_trace") or "").split("|"):
                    if ":" not in tok:
                        continue
                    v = _f(tok.split(":", 1)[1])
                    if math.isfinite(v) and v > 0:
                        vals.append(v)
                d["bis"].append(sum(vals) / len(vals) if vals else float("nan"))
                d["bis_raw"].append(vals)
                for c in cols:
                    d[c].append(_f(r.get(c)))
    out = {}
    for cid, d in cases.items():
        order = sorted(range(len(d["t"])), key=lambda i: d["t"][i])
        out[cid] = {k: [v[i] for i in order] for k, v in d.items()}
    return out, (cols or [])


# ----------------------------------------------------------------------------------------------------
# detector


def _smooth(y, w):
    """Centred moving average of odd length `w` over a list that may contain NaN."""
    if w <= 1:
        return list(y)
    h = w // 2
    out = []
    for i in range(len(y)):
        seg = [v for v in y[max(0, i - h):i + h + 1] if math.isfinite(v)]
        out.append(sum(seg) / len(seg) if seg else float("nan"))
    return out


def _mean_sd(vals):
    v = [x for x in vals if math.isfinite(x)]
    if len(v) < 5:
        return float("nan"), float("nan")
    m = sum(v) / len(v)
    var = sum((x - m) ** 2 for x in v) / (len(v) - 1)
    return m, math.sqrt(var)


def detect(times, series, rel, sign, lo=TEST_LO, hi=TEST_HI, base=(BASE_LO, BASE_HI), k=K):
    """First time in the test span whose signed z against the baseline reaches k. NaN if never."""
    b = [series[i] for i in range(len(times)) if base[0] <= rel[i] < base[1]]
    m, s = _mean_sd(b)
    if not math.isfinite(m) or not math.isfinite(s) or s <= 0:
        return float("nan")
    for i in range(len(times)):
        if not (lo <= rel[i] <= hi):
            continue
        v = series[i]
        if math.isfinite(v) and sign * (v - m) / s >= k:
            return rel[i]
    return float("nan")


def fire_rate(times, series, rel, sign, k=K):
    """Did the detector fire in the HELD-OUT baseline span? 1/0, or NaN if uncalibratable."""
    t = detect(times, series, rel, sign, lo=HELDOUT_LO, hi=HELDOUT_HI, k=k)
    b = [series[i] for i in range(len(times)) if BASE_LO <= rel[i] < BASE_HI]
    m, s = _mean_sd(b)
    if not math.isfinite(s) or s <= 0:
        return float("nan")
    return 1.0 if math.isfinite(t) else 0.0


def bis_effective_window(case):
    """Equivalent rectangular window of BIS's own smoothing, MEASURED from its 1 Hz trace.

    First-order autoregression on the baseline segment: w_eff = (1 + rho) / (1 - rho) samples at 1 Hz.
    Returns NaN when the baseline has too few valid BIS samples to estimate rho.
    """
    raw = []
    for i, rl in enumerate(case["rel_aneend"]):
        if BASE_LO <= rl < BASE_HI:
            raw.extend(case["bis_raw"][i])
    if len(raw) < 60:
        return float("nan")
    m = sum(raw) / len(raw)
    num = sum((raw[i] - m) * (raw[i + 1] - m) for i in range(len(raw) - 1))
    den = sum((x - m) ** 2 for x in raw)
    if den <= 0:
        return float("nan")
    rho = num / den
    if not (-0.99 < rho < 0.99):
        return float("nan")
    if rho <= 0:
        return 1.0
    return (1.0 + rho) / (1.0 - rho)


# ----------------------------------------------------------------------------------------------------


def usable(case):
    rel = case["rel_aneend"]
    n_base = sum(1 for r in rel if BASE_LO <= r < BASE_HI)
    n_test = sum(1 for r in rel if TEST_LO <= r <= TEST_HI)
    return n_base >= 15 and n_test >= 45


def leads_for(cases, col, sign_by_case, smooth_w):
    """Per-case lead (t_BIS - t_candidate) in seconds at a given candidate smoothing."""
    out = {}
    for cid, c in cases.items():
        if not usable(c):
            continue
        sgn = sign_by_case.get(cid)
        if sgn is None:
            continue
        rel, t = c["rel_aneend"], c["t"]
        t_bis = detect(t, c["bis"], rel, +1.0)
        t_cand = detect(t, _smooth(c[col], smooth_w), rel, sgn)
        if math.isfinite(t_bis) and math.isfinite(t_cand):
            out[cid] = t_bis - t_cand
    return out


def fit_direction(cases, col, ids):
    """Sign of the candidate's emergence change, fitted on a DISJOINT set of cases.

    Uses the difference between the late-test mean and the baseline mean -- an amplitude contrast that
    uses no timing information at all, so the thing being measured (when it crosses) cannot leak into
    the thing being declared (which way it goes).
    """
    diffs = []
    for cid in ids:
        c = cases.get(cid)
        if c is None or not usable(c):
            continue
        rel = c["rel_aneend"]
        b = [c[col][i] for i in range(len(rel)) if BASE_LO <= rel[i] < BASE_HI]
        l = [c[col][i] for i in range(len(rel)) if 300.0 <= rel[i] <= TEST_HI]
        mb, _ = _mean_sd(b)
        ml, _ = _mean_sd(l)
        sb = _mean_sd(b)[1]
        if math.isfinite(mb) and math.isfinite(ml) and math.isfinite(sb) and sb > 0:
            diffs.append((ml - mb) / sb)
    if not diffs:
        return float("nan")
    m = sum(diffs) / len(diffs)
    return 1.0 if m >= 0 else -1.0


def split_fitted_signs(cases, col, ids):
    """Two-fold, swapped: each case's direction comes from the OTHER half's cases."""
    ids = sorted(ids)
    a, b = ids[0::2], ids[1::2]
    sa, sb = fit_direction(cases, col, b), fit_direction(cases, col, a)
    out = {}
    for cid in a:
        if math.isfinite(sa):
            out[cid] = sa
    for cid in b:
        if math.isfinite(sb):
            out[cid] = sb
    return out


def median(v):
    v = sorted(x for x in v if math.isfinite(x))
    if not v:
        return float("nan")
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def boot_ci(vals_by_case, rng, reps=4000):
    ids = sorted(vals_by_case)
    if len(ids) < 3:
        return float("nan"), float("nan")
    draws = []
    for _ in range(reps):
        s = [vals_by_case[ids[rng.randrange(len(ids))]] for _ in ids]
        draws.append(median(s))
    draws.sort()
    return draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--glob", default=os.path.join(RESULTS, "vitaldb_transitions.s*.csv"))
    ap.add_argument("--placebo-draws", type=int, default=200)
    ap.add_argument("--seed", type=int, default=246)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e246_matched_lead_over_bis.json"))
    ap.add_argument("--smoke", action="store_true",
                    help="Rule 26: exercise every code path on a RANDOMLY DISPLACED landmark, so the "
                         "real feature distributions are used and the real association is not seen. "
                         "Refuses to write the report.")
    a = ap.parse_args(argv)

    import random
    rng = random.Random(a.seed)

    paths = sorted(glob.glob(a.glob))
    if not paths:
        print("no input shards matched", a.glob)
        return 2
    cases, cols = load_cases(paths)
    if a.smoke:
        # The landmark, not the feature, is this design's label. Displacing it by a few hundred seconds
        # keeps every case analysable (so every branch runs) while destroying the timing relation.
        for c in cases.values():
            off = rng.uniform(-250.0, 250.0)
            c["rel_aneend"] = [r - off for r in c["rel_aneend"]]
        print("[SMOKE] landmarks randomly displaced; NO report will be written (rule 26)")
    use = {cid: c for cid, c in cases.items() if usable(c)}
    print(f"[cohort] {len(cases)} cases loaded, {len(use)} usable around aneend, {len(cols)} panel columns")
    if PRIMARY not in cols:
        print(f"REFUSED: the pre-declared primary candidate {PRIMARY!r} is not in the panel")
        return 2

    rep = {"n_cases_loaded": len(cases), "n_usable": len(use), "k": K, "primary": PRIMARY}

    # ---- BIS's own effective smoothing, measured -----------------------------------------------------
    weff = [bis_effective_window(c) for c in use.values()]
    weff = sorted(x for x in weff if math.isfinite(x))
    w_bis = median(weff)
    rep["bis_effective_window_s"] = w_bis
    rep["bis_effective_window_n"] = len(weff)
    rep["bis_effective_window_iqr"] = ([weff[len(weff) // 4], weff[3 * len(weff) // 4]] if len(weff) >= 4
                                       else None)
    print(f"[bis] measured effective smoothing window = {w_bis:.1f} s "
          f"(n={len(weff)}, IQR {rep['bis_effective_window_iqr']})")

    if not math.isfinite(w_bis) or w_bis < GRID_S:
        print("L* UNDEFINED: BIS's measured effective window is not resolvable above one grid step.")
        print("VERDICT: NOT INTERPRETABLE -- the primary rung does not exist (rule 31).")
        rep["verdict"] = "NOT INTERPRETABLE (L* undefined)"
        json.dump(rep, open(a.out, "w"), indent=1)
        return 0

    def odd(w):
        n = max(1, int(round(w / GRID_S)))
        return n if n % 2 else n + 1

    ladder = {"L0": 1, "L*": odd(w_bis), "L2": odd(2 * w_bis)}
    rep["ladder_windows"] = ladder
    print(f"[ladder] smoothing lengths in grid steps: {ladder}")

    signs = split_fitted_signs(use, PRIMARY, list(use))
    rep["direction_by_half"] = {"n_assigned": len(signs),
                                "signs": sorted(set(signs.values()))}

    # ---- PRIMARY (evaluated BEFORE any gate, rule 37) ------------------------------------------------
    prim = {}
    for name, w in ladder.items():
        L = leads_for(use, PRIMARY, signs, w)
        lo, hi = boot_ci(L, rng)
        prim[name] = {"n": len(L), "median_lead_s": median(L.values()), "ci": [lo, hi]}
        print(f"[primary] {PRIMARY} @ {name} (w={w}): n={len(L)} "
              f"median lead {median(L.values()):+.1f} s [{lo:+.1f}, {hi:+.1f}]")
    rep["primary"] = prim
    p = prim["L*"]

    if not math.isfinite(p["median_lead_s"]) or p["n"] < MIN_CASES:
        verdict = f"NOT INTERPRETABLE (support: {p['n']} cases < {MIN_CASES})"
    elif p["ci"][1] < 0:
        verdict = "LAGS -- the candidate fires LATER than BIS; the temporal claim is REFUTED here"
    elif p["ci"][0] > 0:
        verdict = "LEADS (provisional, pending gates and placebo)"
    else:
        verdict = "ABSENT -- no resolvable timing difference"

    if (prim["L0"]["ci"][0] > 0) and not (p["ci"][0] > 0):
        verdict += " | ARTEFACT: the lead is present unsmoothed and gone at matched smoothing"

    # ---- GATES ---------------------------------------------------------------------------------------
    gates = {}

    n_alive = 0
    for c in use.values():
        tb = detect(c["t"], c["bis"], c["rel_aneend"], +1.0)
        if math.isfinite(tb) and abs(tb) <= 300.0:
            n_alive += 1
    g1 = n_alive / max(1, len(use))
    gates["G1_incumbent_alive"] = {"frac_bis_detects_within_300s": g1, "pass": g1 >= 0.50}

    fr_b, fr_c = [], []
    for cid, c in use.items():
        if cid not in signs:
            continue
        fr_b.append(fire_rate(c["t"], c["bis"], c["rel_aneend"], +1.0))
        fr_c.append(fire_rate(c["t"], _smooth(c[PRIMARY], ladder["L*"]), c["rel_aneend"], signs[cid]))
    def _rate(v):
        f = [x for x in v if math.isfinite(x)]
        return (sum(f) / len(f)) if f else float("nan")

    rb, rc = _rate(fr_b), _rate(fr_c)
    ratio = (rc / rb) if rb > 0 else float("inf")
    gates["G2_false_alarm_match"] = {"bis_rate": rb, "candidate_rate": rc, "ratio": ratio,
                                     "pass": bool(math.isfinite(ratio) and ratio <= 2.0)}

    g3 = {}
    for want in (+60.0, -60.0):
        # A candidate equal to BIS shifted forward in time by `want` seconds fires `want` seconds
        # earlier, so the estimator must return a median lead of exactly `want`. Both signs are run so
        # that an estimator biased in EITHER direction breaks the gate (rule 81's mirror of rule 40).
        n = int(round(want / GRID_S))
        synth = {}
        for cid, c in use.items():
            b = c["bis"]
            s = (b[n:] + [float("nan")] * n) if n >= 0 else ([float("nan")] * (-n) + b[:n])
            d = dict(c)
            d["__synth"] = s
            synth[cid] = d
        L = leads_for(synth, "__synth", {cid: +1.0 for cid in synth}, 1)
        med = median(L.values())
        g3[f"shift_{want:+.0f}s"] = {"n": len(L), "median_lead_s": med,
                                     "pass": bool(math.isfinite(med) and abs(med - want) <= 20.0)}
    gates["G3_capability_both_directions"] = g3

    gates["G4_support"] = {"n": p["n"], "pass": p["n"] >= MIN_CASES}

    # ---- PLACEBOS, both as DISTRIBUTIONS -------------------------------------------------------------
    obs = p["median_lead_s"]

    def _summarise(draws, label, evaluable=True, note=None):
        d = sorted(x for x in draws if math.isfinite(x))
        if not evaluable or len(d) < 20:
            return {"label": label, "n_draws": len(d), "evaluable": False,
                    "note": note or "fewer than 20 evaluable draws -- reports NOTHING (rule 31)"}
        frac = sum(1 for x in d if x >= obs) / len(d)
        return {"label": label, "n_draws": len(d), "evaluable": True, "median": median(d),
                "p95": d[int(0.95 * len(d))], "frac_reaching_observed": frac,
                "fires": bool(math.isfinite(frac) and frac >= 0.05)}

    # P1 -- case-mismatched pairing. Destroys within-case correspondence and nothing else.
    tb, tc = {}, {}
    for cid, c in use.items():
        if cid not in signs:
            continue
        x = detect(c["t"], c["bis"], c["rel_aneend"], +1.0)
        y = detect(c["t"], _smooth(c[PRIMARY], ladder["L*"]), c["rel_aneend"], signs[cid])
        if math.isfinite(x) and math.isfinite(y):
            tb[cid], tc[cid] = x, y
    ids = sorted(tb)
    p1 = []
    for _ in range(a.placebo_draws):
        perm = ids[:]
        rng.shuffle(perm)
        p1.append(median([tb[j] - tc[i] for i, j in zip(ids, perm) if i != j]))
    placebo1 = _summarise(p1, "P1 case-mismatched pairing", evaluable=len(ids) >= MIN_CASES,
                          note=f"only {len(ids)} cases with both detections (floor {MIN_CASES})")

    # P2 -- random landmark. Declared knowing the extraction may not cover it (rule 48's second half).
    p2, p2_support = [], []
    for _ in range(a.placebo_draws // 4):
        shifted = {}
        for cid, c in use.items():
            off = math.copysign(rng.uniform(600.0, 1200.0), rng.choice([-1.0, 1.0]))
            d = dict(c)
            d["rel_aneend"] = [r - off for r in c["rel_aneend"]]
            if usable(d):
                shifted[cid] = d
        p2_support.append(len(shifted))
        L = leads_for(shifted, PRIMARY, signs, ladder["L*"])
        if len(L) >= MIN_CASES:
            p2.append(median(L.values()))
    placebo2 = _summarise(p2, "P2 random landmark", evaluable=len(p2) >= 20,
                          note=f"median support {median(p2_support):.0f} cases against a floor of "
                               f"{MIN_CASES}; the extraction covers only +/-600 s, so a displaced "
                               f"landmark loses most of its test span. NOT EVALUABLE is reported as "
                               f"such and contributes nothing to the verdict.")

    placebo = placebo1
    rep["placebo_primary"] = placebo1
    rep["placebo_secondary"] = placebo2

    # a placebo cannot validate a null (rule 48)
    if not (p["ci"][0] > 0):
        for q in (placebo1, placebo2):
            q["interpretation"] = "NOT INFORMATIVE -- the primary did not exclude zero"
            q["fires"] = False

    rep["gates"] = gates
    failed = [k for k, v in gates.items()
              if (v.get("pass") is False) or (k == "G3_capability_both_directions"
                                              and not all(x["pass"] for x in v.values()))]
    if verdict.startswith("LEADS"):
        fired = [q["label"] for q in (placebo1, placebo2)
                 if q.get("evaluable") and q.get("fires")]
        if failed or fired:
            verdict = ("NOT INTERPRETABLE -- primary led but "
                       + (f"gates failed: {failed}; " if failed else "")
                       + (f"placebo reproduces it: {fired}" if fired else ""))
        else:
            verdict = "LEADS at matched smoothing and matched false-alarm rate"
    rep["verdict"] = verdict

    # ---- descriptive screen, never gated, never promoted ----------------------------------------------
    desc = {}
    for col in cols:
        if col == PRIMARY:
            continue
        s = split_fitted_signs(use, col, list(use))
        L = leads_for(use, col, s, ladder["L*"])
        if len(L) >= MIN_CASES:
            lo, hi = boot_ci(L, rng, reps=1500)
            desc[col] = {"n": len(L), "median_lead_s": median(L.values()), "ci": [lo, hi]}
    rep["descriptive_screen"] = desc

    print("\n[gates]", json.dumps(gates, indent=1, default=float))
    print("[placebo P1]", json.dumps(placebo1, indent=1, default=float))
    print("[placebo P2]", json.dumps(placebo2, indent=1, default=float))
    print("\nVERDICT:", verdict)
    print("\nDESCRIPTIVE SCREEN (not gated, not promotable):")
    for col, d in sorted(desc.items(), key=lambda kv: -abs(kv[1]["median_lead_s"])):
        print(f"  {col:32s} n={d['n']:4d} {d['median_lead_s']:+8.1f} s "
              f"[{d['ci'][0]:+.1f}, {d['ci'][1]:+.1f}]")

    if a.smoke:
        print("\n[SMOKE] complete; report NOT written and nothing above is a result.")
        return 0
    json.dump(rep, open(a.out, "w"), indent=1, default=float)
    print("\nwrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
