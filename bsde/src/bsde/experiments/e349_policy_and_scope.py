#!/usr/bin/env python3
"""E349 -- ten tests: does a reporting MANDATE fix this, and how far do the CTG findings generalise?

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY. E346-E348 established that 7-15 % of registered trials stop before answering their question, that
the rate is 5.5-fold higher in the smallest studies, that small studies stop for MACHINERY while large
ones stop on RESULTS, and that published abstracts report such events at 1 in 891. **The obvious question
a reader will ask next is whether policy fixes it**, and ClinicalTrials.gov contains two natural
experiments that bear on it: the FDA Amendments Act of 2007 (results reporting mandatory for applicable
trials from late 2008) and the 2017 Final Rule (scope widened, penalties specified). T1 and T2 look for
those discontinuities. T3-T10 test how far the descriptive findings generalise -- to observational
studies, outside the United States, and across design features -- and bound the one number E346 could
only give as a range.

------------------------------------------------------------------------------------------------------
T1  THE FDAAA DISCONTINUITY. Primary: results-posting rate among completed interventional studies by
    START year, 2004-2020, and the change across the 2008 boundary measured as
    `mean(2009-2012) - mean(2004-2007)`.
    PREDICTION: a rise. **WRONG IF flat or falling**, which would say a decade of mandatory reporting did
    not move the rate and would be the more newsworthy outcome; it is named first for that reason.
    **CONFOUND, declared before the run and NOT controlled**: start year is not the year the mandate
    applied -- FDAAA attaches to trials ongoing or completing after its effective date, and a study
    starting in 2006 could complete in 2012. So T1 measures a cohort trend across a policy boundary, not
    a treatment effect, and any jump is an upper bound on what the mandate did. Rule 54 -- naming a
    confound is not controlling it, so the claim is bounded rather than adjusted.

T2  THE 2017 FINAL RULE. Same series, boundary at 2017, `mean(2018-2020) - mean(2014-2016)`.
    **RIGHT-CENSORING IS SEVERE HERE and biases DOWNWARD**: posting is due a year after completion, so
    recent cohorts have had less opportunity. Any decline is uninterpretable; only a RISE would be
    readable, and that asymmetry is stated in advance.

T3  DOES THE STOPPING PHENOMENON EXIST OUTSIDE INTERVENTIONAL RESEARCH? Primary: the stopped share among
    OBSERVATIONAL studies with a terminal status, against the interventional 0.1491.

T4  DOES THE SIZE GRADIENT HOLD IN OBSERVATIONAL STUDIES? Primary: stopped share by enrolment stratum
    within observational. PREDICTION: it holds. This is the strongest available test that the gradient
    is about study size rather than about anything specific to trials.

T5  DOES IT HOLD OUTSIDE THE UNITED STATES? Primary: stopped share by size for studies with a US
    location against those without. The register being audited here is a US-hosted registry; if the
    gradient is US-specific it is a reporting artefact rather than a property of small studies.

T6  RANDOMISED VERSUS NOT. Primary: stopped share by size within randomised and non-randomised designs.

T7  BY PRIMARY PURPOSE. Primary: stopped share for TREATMENT, PREVENTION, DIAGNOSTIC, SUPPORTIVE_CARE,
    BASIC_SCIENCE. Descriptive; BASIC_SCIENCE is the category closest to the analyses in this project's
    own register and is named in advance as the one to read.

T8  **BOUNDING THE UNCLASSIFIABLE.** E346/T2 could only give the external machinery-failure rate as a
    RANGE (0.070-0.149) because 46.8 % of `whyStopped` texts matched nothing. Primary: draw a sample of
    those unmatched texts and classify them with a SECOND pattern set derived from the unmatched corpus
    itself rather than from the first pass, and report what fraction of the residue is machinery.
    That tightens the bound in whichever direction the data says.
    G8: the second pattern set must be shown to classify the ALREADY-MATCHED corpus consistently with
    the first (>= 0.70 agreement on those), else it is a different instrument and cannot bound the same
    quantity.

T9  DOES POSTING RESULTS DEPEND ON WHY YOU STOPPED? Primary: results-posting rate among terminated
    studies whose stop reason is MACHINERY versus RESULT.
    PREDICTION: RESULT stops post more -- a trial stopped for efficacy or futility has something to
    report. If so, the machinery failures are doubly invisible: rarer in the literature (E346/T10) and
    less often posted even inside the registry.

T10 WHICH FACTOR SPREADS THE RATE MOST? Primary: the range of the stopped share across the strata of
    each factor measured here and in E347 -- size, phase, sponsor, study type, country, allocation,
    purpose -- reported as a single table.
    **Descriptive ranking only. No model, no significance test**: these factors are correlated with each
    other and with size, and a ranking of marginal ranges is not a decomposition of variance. Registered
    with that wording so it cannot drift into one.

GATES.
  G0  Every response cached (shared cache with E346/E347); unreachable endpoints report BLOCKED.
  G1  Each stratum must carry >= 200 terminal-status studies to be reported as a rate; smaller cells are
      printed with their counts and excluded from any comparison (rule 14 -- exclusions are reported).

LIMITATIONS.
  1. T1 and T2 are cohort trends across policy boundaries, not treatment effects (see T1's confound).
  2. All of this is one registry. A finding that holds in CTG holds in CTG.
  3. `whyStopped` is what sponsors wrote (E346 limitation 2), and T8 tightens the bound without removing
     that.

    python -m bsde.experiments.e349_policy_and_scope --smoke
    python -m bsde.experiments.e349_policy_and_scope
"""
from __future__ import annotations

import argparse, collections, json, math, os, random, re, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")

from bsde.experiments.e346_external_register import (            # noqa: E402
    API, TERMINAL, STOPPED, _get, classify_why, fetch, wilson)

INTERV = "AREA[StudyType]INTERVENTIONAL"
OBS = "AREA[StudyType]OBSERVATIONAL"
SIZES = [("1-20", 1, 20), ("21-100", 21, 100), ("101-500", 101, 500), ("501+", 501, 100000)]
MIN_CELL = 200


def cnt(status, term):
    u = (f"{API}?filter.overallStatus={status}&query.term={urllib.parse.quote(term)}"
         f"&pageSize=1&countTotal=true&fields=NCTId")
    return int(_get(u).get("totalCount", 0))


def cnt_res(status, term):
    u = (f"{API}?filter.overallStatus={status}&query.term={urllib.parse.quote(term)}"
         f"&aggFilters=results:with&pageSize=1&countTotal=true&fields=NCTId")
    return int(_get(u).get("totalCount", 0))


def stopped(term):
    t = {s: cnt(s, term) for s in TERMINAL}
    n = sum(t.values())
    k = sum(t[s] for s in STOPPED)
    return k, n, (k / n if n else float("nan"))


def show(label, k, n, rate):
    flag = "" if n >= MIN_CELL else "   [CELL < 200 -- excluded from comparisons]"
    lo, hi = wilson(k, n) if n else (float("nan"),) * 2
    print(f"    {label:<28} {k:>7,}/{n:>8,} = {rate:.4f}  [{lo:.4f}, {hi:.4f}]{flag}")
    return {"stopped": k, "n": n, "rate": rate, "ci": [lo, hi], "usable": n >= MIN_CELL}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e349_policy_and_scope.json"))
    a = ap.parse_args(argv)
    rng = random.Random(349)
    R = {}

    # -------------------------------------------------------------------------------- T1 / T2
    print("=" * 96)
    print("T1/T2 -- results posting by START year, across the FDAAA (2008) and Final Rule (2017)")
    print("        boundaries. COHORT TRENDS, NOT TREATMENT EFFECTS -- see the registered confound.")
    years = list(range(2004, 2021))
    if a.smoke:
        years = [2004, 2005, 2010, 2011, 2018, 2019]
    ser = {}
    for y in years:
        term = f"{INTERV} AND AREA[StartDate]RANGE[{y}-01-01,{y}-12-31]"
        n = cnt("COMPLETED", term)
        k = cnt_res("COMPLETED", term)
        ser[y] = {"n": n, "with_results": k, "rate": k / n if n else float("nan")}
        print(f"    {y}: {k:>6,}/{n:>7,} = {ser[y]['rate']:.4f}")

    def mean_over(ys):
        v = [ser[y]["rate"] for y in ys if y in ser and math.isfinite(ser[y]["rate"])]
        return sum(v) / len(v) if v else float("nan")
    pre1, post1 = mean_over([2004, 2005, 2006, 2007]), mean_over([2009, 2010, 2011, 2012])
    pre2, post2 = mean_over([2014, 2015, 2016]), mean_over([2018, 2019, 2020])
    print(f"  [T1] FDAAA: mean(2004-07) {pre1:.4f} -> mean(2009-12) {post1:.4f}  "
          f"change {post1-pre1:+.4f}")
    print(f"       {'RISE' if post1 > pre1 else 'FLAT/FALL -- a decade of mandatory reporting did not move it'}")
    print(f"  [T2] Final Rule: mean(2014-16) {pre2:.4f} -> mean(2018-20) {post2:.4f}  "
          f"change {post2-pre2:+.4f}")
    print(f"       right-censoring biases this DOWNWARD, so only a rise is readable; "
          f"{'readable' if post2 > pre2 else 'a decline here is UNINTERPRETABLE'}")
    R["T1"] = {"series": ser, "pre": pre1, "post": post1, "change": post1 - pre1}
    R["T2"] = {"pre": pre2, "post": post2, "change": post2 - pre2,
               "readable": bool(post2 > pre2)}

    # -------------------------------------------------------------------------------- T3 / T4
    print("\n" + "=" * 96)
    print("T3 -- does the stopping phenomenon exist outside interventional research?")
    ki, ni, ri = stopped(INTERV)
    ko, no_, ro = stopped(OBS)
    R["T3"] = {"interventional": show("INTERVENTIONAL", ki, ni, ri),
               "observational": show("OBSERVATIONAL", ko, no_, ro)}

    print("\nT4 -- does the SIZE GRADIENT hold in observational studies?")
    t4 = {}
    for lbl, lo, hi in SIZES:
        k, n, r = stopped(f"{OBS} AND AREA[EnrollmentCount]RANGE[{lo},{hi}]")
        t4[lbl] = show(f"observational {lbl}", k, n, r)
    us = [t4[l]["rate"] for l, _, _ in SIZES if t4[l]["usable"]]
    holds4 = len(us) >= 3 and us[0] > us[-1]
    print(f"  [T4] gradient holds in observational studies -> "
          f"{'PREDICTION MET' if holds4 else 'PREDICTION NOT MET'}")
    R["T4"] = {"strata": t4, "holds": holds4}

    # -------------------------------------------------------------------------------- T5
    print("\n" + "=" * 96)
    print("T5 -- does it hold outside the United States?")
    t5 = {}
    for tag, q in (("US site", f'{INTERV} AND AREA[LocationCountry]"United States"'),
                   ("no US site", f'{INTERV} AND NOT AREA[LocationCountry]"United States"')):
        for lbl, lo, hi in (SIZES[0], SIZES[-1]):
            k, n, r = stopped(f"{q} AND AREA[EnrollmentCount]RANGE[{lo},{hi}]")
            t5[f"{tag}|{lbl}"] = show(f"{tag} {lbl}", k, n, r)
    ok5 = all(t5[f"{t}|1-20"]["rate"] > t5[f"{t}|501+"]["rate"]
              for t in ("US site", "no US site")
              if t5[f"{t}|1-20"]["usable"] and t5[f"{t}|501+"]["usable"])
    print(f"  [T5] gradient present on both sides of the US boundary -> {ok5}")
    R["T5"] = {"cells": t5, "holds_both": ok5}

    # -------------------------------------------------------------------------------- T6 / T7
    print("\n" + "=" * 96)
    print("T6 -- randomised versus not")
    t6 = {}
    for tag in ("RANDOMIZED", "NON_RANDOMIZED"):
        for lbl, lo, hi in (SIZES[0], SIZES[-1]):
            k, n, r = stopped(f"{INTERV} AND AREA[DesignAllocation]{tag} AND "
                              f"AREA[EnrollmentCount]RANGE[{lo},{hi}]")
            t6[f"{tag}|{lbl}"] = show(f"{tag} {lbl}", k, n, r)
    R["T6"] = t6

    print("\nT7 -- by primary purpose (BASIC_SCIENCE is the category closest to this register)")
    t7 = {}
    for p in ("TREATMENT", "PREVENTION", "DIAGNOSTIC", "SUPPORTIVE_CARE", "BASIC_SCIENCE"):
        k, n, r = stopped(f"{INTERV} AND AREA[DesignPrimaryPurpose]{p}")
        t7[p] = show(p, k, n, r)
    R["T7"] = t7

    # -------------------------------------------------------------------------------- T8
    print("\n" + "=" * 96)
    print("T8 -- bounding the 46.8 % of whyStopped texts that matched nothing")
    corp = fetch("TERMINATED", want=200 if a.smoke else 2500)
    matched = [s for s in corp if classify_why(s["why"])[0] != "OTHER"]
    unmatched = [s for s in corp if classify_why(s["why"])[0] == "OTHER" and s["why"].strip()]
    print(f"    corpus {len(corp)}: matched {len(matched)}, unmatched-with-text {len(unmatched)}, "
          f"blank {sum(1 for s in corp if not s['why'].strip())}")
    # second pattern set, derived from the UNMATCHED corpus's own frequent terms
    words = collections.Counter()
    for s in unmatched:
        for w in re.findall(r"[a-z]{4,}", s["why"].lower()):
            words[w] += 1
    print("    most frequent terms in the unmatched residue: " +
          ", ".join(f"{w}:{c}" for w, c in words.most_common(14)))
    SECOND_MACH = re.compile(r"\b(pi|investigator|sponsor|company|site|centre|center|staff|"
                             r"protocol|amend|feasib|slow|low|lack|unable|difficult|resource|"
                             r"time|closed|withdraw|decision|priorit|strateg|covid|supply|"
                             r"equipment|contract|irb|ethic|approv|budget|monet)\w*\b", re.I)
    SECOND_RES = re.compile(r"\b(efficac|futil|safety|toxic|adverse|benefit|endpoint|"
                            r"interim|superior|inferior)\w*\b", re.I)

    def second(t):
        if SECOND_RES.search(t or ""):
            return "RESULT"
        if SECOND_MACH.search(t or ""):
            return "MACHINERY"
        return "OTHER"
    agree = sum(1 for s in matched if second(s["why"]) == classify_why(s["why"])[0])
    ag = agree / len(matched) if matched else float("nan")
    G8 = math.isfinite(ag) and ag >= 0.70
    print(f"    [G8] second pattern set agrees with the first on the ALREADY-MATCHED corpus: "
          f"{ag:.3f} -> {'PASS' if G8 else 'FAIL -- different instrument, cannot bound the same thing'}")
    if G8 and unmatched:
        c2 = collections.Counter(second(s["why"]) for s in unmatched)
        m2 = c2["MACHINERY"] / len(unmatched)
        still = c2["OTHER"] / len(unmatched)
        base = len(matched) / len(corp)
        mach_first = sum(1 for s in matched if classify_why(s["why"])[0] == "MACHINERY") / len(corp)
        tightened = mach_first + (len(unmatched) / len(corp)) * m2
        print(f"    residue: MACHINERY {m2:.3f}, RESULT {c2['RESULT']/len(unmatched):.3f}, "
              f"still unclassified {still:.3f}")
        print(f"  [T8] machinery share tightens from >= {mach_first:.3f} to ~{tightened:.3f} of all "
              f"stops; E346's range 0.070-0.149 narrows to about "
              f"{0.1491*tightened:.4f} on the same denominator")
        R["T8"] = {"n_corpus": len(corp), "n_unmatched": len(unmatched), "agreement": ag,
                   "residue_machinery": m2, "tightened_share": tightened, "gate": True}
    else:
        print("  [T8] NOT INTERPRETABLE")
        R["T8"] = {"agreement": ag, "gate": False}

    # -------------------------------------------------------------------------------- T9
    print("\n" + "=" * 96)
    print("T9 -- does posting results depend on WHY you stopped?")
    # counts are not available split by whyStopped, so this is measured on the fetched corpus by
    # asking the API whether each arm's NCT ids carry results -- done as two count queries using
    # the reason-specific search terms the API does expose.
    t9 = {}
    for tag, term in (("accrual/funding (machinery)",
                       f'{INTERV} AND (AREA[WhyStopped]accrual OR AREA[WhyStopped]enrollment OR '
                       f'AREA[WhyStopped]funding OR AREA[WhyStopped]recruitment)'),
                      ("efficacy/futility/safety (result)",
                       f'{INTERV} AND (AREA[WhyStopped]efficacy OR AREA[WhyStopped]futility OR '
                       f'AREA[WhyStopped]safety)')):
        n = cnt("TERMINATED", term)
        k = cnt_res("TERMINATED", term)
        lo, hi = wilson(k, n) if n else (float("nan"),) * 2
        t9[tag] = {"n": n, "with_results": k, "rate": k / n if n else float("nan"),
                   "ci": [lo, hi]}
        print(f"    {tag:<34} {k:>6,}/{n:>7,} = {t9[tag]['rate']:.4f}  [{lo:.4f}, {hi:.4f}]")
    ks = list(t9)
    if all(t9[k_]["n"] >= MIN_CELL for k_ in ks):
        d = t9[ks[1]]["rate"] - t9[ks[0]]["rate"]
        print(f"  [T9] RESULT stops post {d:+.4f} more often than MACHINERY stops -> "
              f"{'PREDICTION MET -- machinery failures are doubly invisible' if d > 0 else 'PREDICTION NOT MET'}")
        R["T9"] = {"arms": t9, "diff": d}
    else:
        print("  [T9] NOT INTERPRETABLE -- a cell is under 200")
        R["T9"] = {"arms": t9}

    # -------------------------------------------------------------------------------- T10
    print("\n" + "=" * 96)
    print("T10 -- which factor spreads the stopped share most? DESCRIPTIVE RANKING ONLY.")
    print("       These factors are correlated with each other and with size; a ranking of marginal")
    print("       ranges is NOT a decomposition of variance, and no model is fitted.")
    spreads = {}
    spreads["size (interventional)"] = 0.2732 - 0.0501          # E346/T4, cached values
    spreads["phase"] = 0.2354 - 0.1607                          # E346/T6
    spreads["sponsor (at n<=20)"] = 0.296 - 0.274               # E347/T5
    if all(t4[l]["usable"] for l, _, _ in SIZES):
        spreads["size (observational)"] = (max(t4[l]["rate"] for l, _, _ in SIZES)
                                           - min(t4[l]["rate"] for l, _, _ in SIZES))
    us7 = [v["rate"] for v in t7.values() if v["usable"]]
    if len(us7) >= 3:
        spreads["primary purpose"] = max(us7) - min(us7)
    spreads["study type"] = abs(ri - ro)
    for k_, v in sorted(spreads.items(), key=lambda t: -t[1]):
        print(f"    {k_:<26} range {v:.4f}")
    R["T10"] = spreads

    print("\n" + "=" * 96)
    if a.smoke:
        print("[SMOKE] short year list and small corpus; counts are exact regardless.")
        return 0
    json.dump(R, open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
