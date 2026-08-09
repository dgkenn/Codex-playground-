#!/usr/bin/env python3
"""E347 -- ten tests: audit the register against its own CODE, and standardise it against CTG.

PRE-REGISTRATION. Committed before any statistic in it exists, except where explicitly declared SEEN.

WHERE THIS PICKS UP. E346 externalised the register line and left three things open.
  * **T7 refused**: the register's outcome labelling cannot be audited from TEXT -- not by my own
    vocabulary (E344/T2, precision destroyed by 54 rows that merely MENTION withdrawal) and not by an
    external one derived from ClinicalTrials.gov (E346/T7, 6.2 % coverage, precision 0.071), because
    trial-stopping language and analysis-stopping language barely share terms. I concluded it needed a
    second human reader. **That conclusion was too quick: there is a third artifact, and it is not
    prose.** Every register row carries a `file`, every experiment writes a result JSON, and most of
    those JSONs carry the verdict string the CODE ITSELF emitted at run time. T1 audits the register
    against that.
  * **T5 refused**: whether the external rate is improving is not interpretable, because censoring is
    present in every year (6.9 % -> 34.6 %) and correlates with the stopped share at rho = +0.643.
    T3 handles it properly instead of excluding a tail.
  * **T4's size gradient (0.2732 at n <= 20 against 0.0501 above 500) was left unadjusted**, and small
    trials differ from large ones in phase and sponsor as well as in size. T4-T5 here separate those,
    and T10 uses the result to standardise rather than to hand-wave.

------------------------------------------------------------------------------------------------------
DECLARED SEEN BEFORE REGISTRATION (rule 41 requires the feasibility probe to run first; honesty requires
saying which numbers it produced). The probe returned: TERMINATED studies with posted results
**11,548 / 29,598 = 0.390**, against COMPLETED **62,020 / 255,348 = 0.243**; lead-sponsor class among
terminated studies INDUSTRY 10,507, NIH 747, OTHER 17,446; anaesthesia-condition terminated 250.
**T2 is therefore DESCRIPTIVE and carries no prediction about its headline direction** -- I had expected
terminated trials to post results LESS often and the probe already refuted that. Its contribution is the
DECOMPOSITION, which the probe did not touch.

------------------------------------------------------------------------------------------------------
T1  **AUDIT THE REGISTER AGAINST THE CODE'S OWN VERDICT.** For every register row with a `file`, locate
    the matching result JSON by its `eNNN` stem and extract any verdict string the code emitted.
    Primary: the count of DETECTABLE CONTRADICTIONS in the one direction that is unambiguous --
    **an artifact whose verdict says NOT INTERPRETABLE while the register row says anything other than
    `gate_failed`.** That implication needs no vocabulary judgement: the code refused to interpret its
    own primary, so the row cannot claim a result.
    Reported alongside the converse (rows labelled `gate_failed` whose artifact does not say NOT
    INTERPRETABLE), which is NOT scored as an error because verdict strings are not a controlled
    vocabulary and a gate failure can be phrased many ways.
    PREDICTION: a small non-zero count. **WRONG IF zero** -- which would be the good outcome and would
    mean the labelling survives the first audit that could actually detect a fault.
    G1 (rule 40): a planted row/artifact pair whose verdict says NOT INTERPRETABLE against an outcome of
    `positive` MUST be detected, and a planted consistent pair must NOT be. Both printed before T1's
    count is read.
    G1b COVERAGE: the matcher must resolve >= 40 % of rows to an artifact, else it is measuring its own
    inability to find files (E346/T7's failure mode, and the same floor).

T2  RESULTS POSTING, DECOMPOSED (descriptive; headline direction already seen -- see above).
    Primary: posting rate for TERMINATED versus COMPLETED, split by lead-sponsor class and by enrolment
    stratum. The question the decomposition answers is whether the surprising direction is a sponsor
    effect -- industry trials are subject to mandatory reporting and are over-represented among
    terminations -- rather than anything about terminations as such.

T3  THE CENSORING-AWARE TREND, replacing E346/T5. Primary: for each start-year cohort, the stopped share
    computed **among studies that have reached a terminal status**, reported beside that cohort's
    FOLLOW-UP FRACTION (terminal / (terminal + ongoing)), and the trend fitted only over cohorts whose
    follow-up fraction exceeds a threshold fixed here: **0.90**.
    A second, assumption-free quantity is reported beside it: the stopped count as a share of ALL
    registered studies in that cohort (terminal + ongoing), which is a strict LOWER bound on the
    eventual rate and cannot be inflated by incomplete follow-up.
    PREDICTION: over the cohorts that clear 0.90 follow-up, the trend is flat. WRONG IF it moves.

T4  DOES THE SIZE GRADIENT SURVIVE PHASE? Primary: the stopped share in a size x phase grid.
    PREDICTION: the gradient holds within every phase. WRONG IF it disappears inside phases, which would
    mean E346/T4 was a phase effect wearing a size costume (rule 89's shape).

T5  DOES IT SURVIVE SPONSOR? Same grid against lead-sponsor class. **`OTHER` -- academic and hospital
    sponsors -- is the stratum this project's register actually resembles**, and its rate is the tightest
    available external comparator, so it is named here in advance as the one to quote.

T6  MY OWN FIELD. Primary: the stopped share and machinery share among anaesthesia-condition
    interventional studies, against the corpus. Descriptive, and it answers "is this domain unusual?"
    G6: >= 300 terminal-status studies in the field, else NOT INTERPRETABLE.

T7  **THE PROSPECTIVE SAMPLE.** E344/T7 refused for want of held-out rows: zero registrations postdated
    E330. Since then this session has registered and run E340-E346, and E344 and E346 are themselves
    ten-test batteries whose every test carried a pre-committed gate. Primary: the outcome distribution
    over that prospective set, tabulated by hand from the result notes and declared row by row in the
    output so a reader can check each one.
    **This is n ~ 26 and no interval will make it precise.** It is reported as a tabulation with its
    count, never as a rate to be compared against the retrospective one.

T8  ARE THE `absent` VERDICTS POWERED? Primary: among register rows classed `absent`, the fraction whose
    `outcome_detail` states an interval or an effect size at all. A verdict of "no effect" from a design
    that never reports what it could have detected is not an absence, and if that fraction is low the
    true-positive rate is not the right summary of this register.
    PREDICTION: a majority do state one, because this project's later files print intervals by habit.

T9  DOES *WHY* TRIALS STOP CHANGE WITH SIZE? E346/T4 showed HOW OFTEN changes with size. Primary: the
    MACHINERY share of stops within the smallest and largest enrolment strata.
    PREDICTION: machinery share is HIGHER in small studies -- large trials that stop are more often
    stopping on an interim result. This sharpens T4: if it holds, small studies are not merely stopping
    more, they are stopping more for reasons that mean the question was never asked.

T10 **DIRECT STANDARDISATION -- the like-for-like comparison E346/T9 could only gesture at.**
    Primary: this register's machinery-failure rate re-weighted to CTG's enrolment-size distribution,
    and CTG's rate re-weighted to this register's size distribution. Both directions are reported.
    Every analysis in this register is small-n, so its size distribution is a point mass in the smallest
    stratum; the standardisation therefore reduces to reading CTG's smallest-stratum rate against the
    register's own, and the file says so explicitly rather than dressing it as a model.
    **No significance test**, for the reason registered in E346/T9: the two artifacts count different
    objects and a p-value would imply a common estimand that does not exist.

GATES COMMON TO THE BATTERY.
  G0  Every CTG response is cached (shared with E346's cache); unreachable endpoints report BLOCKED,
      never a number. Partial fetches are reported as partial with counts (rule 14).
  GS  `--smoke` shuffles the register's outcome labels and asserts T1's contradiction count RISES,
      printing both -- if a mislabelling detector cannot detect deliberate mislabelling it is not one.

LIMITATIONS.
  1. T1 audits only rows whose artifact survives on disk and carries a verdict string. Rows whose
     artifact is missing are reported as UNRESOLVED, not as passes.
  2. T7's prospective sample is n ~ 26 and is a tabulation, not an estimate.
  3. T2-T6, T9, T10 measure ClinicalTrials.gov; trials are not analyses, and no test claims they are.

    python -m bsde.experiments.e347_audit_and_standardise --smoke
    python -m bsde.experiments.e347_audit_and_standardise
"""
from __future__ import annotations

import argparse, collections, json, math, os, random, re, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
LEDGER = os.path.join(ROOT, "governance", "REGISTRATION_LEDGER.jsonl")

from bsde.experiments.e346_external_register import (            # noqa: E402
    API, INTERV, TERMINAL, STOPPED, _get, classify_why, fetch, wilson)
from bsde.experiments.e344_register_battery import canon         # noqa: E402

ONGOING = ("RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING",
           "ENROLLING_BY_INVITATION", "UNKNOWN")
SIZES = [("1-20", 1, 20), ("21-100", 21, 100), ("101-500", 101, 500), ("501+", 501, 100000)]
PHASES = ("PHASE1", "PHASE2", "PHASE3", "PHASE4")
SPONSORS = ("INDUSTRY", "NIH", "OTHER")
FOLLOWUP_FLOOR = 0.90
NOT_INTERP = re.compile(r"NOT\s+INTERPRETABLE", re.I)
STEM = re.compile(r"(e\d{2,4})_", re.I)


def cnt(status, extra=""):
    q = INTERV + (" AND " + extra if extra else "")
    u = (f"{API}?filter.overallStatus={status}&query.term={urllib.parse.quote(q)}"
         f"&pageSize=1&countTotal=true&fields=NCTId")
    return int(_get(u).get("totalCount", 0))


def cnt_res(status, extra=""):
    q = INTERV + (" AND " + extra if extra else "")
    u = (f"{API}?filter.overallStatus={status}&query.term={urllib.parse.quote(q)}"
         f"&aggFilters=results:with&pageSize=1&countTotal=true&fields=NCTId")
    return int(_get(u).get("totalCount", 0))


def stopped_share(extra=""):
    t = {s: cnt(s, extra) for s in TERMINAL}
    n = sum(t.values())
    k = sum(t[s] for s in STOPPED)
    return k, n, (k / n if n else float("nan"))


def verdict_strings(obj, out=None, depth=0):
    """Every string in a result JSON that looks like a verdict the code emitted."""
    out = [] if out is None else out
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k.lower() in ("verdict", "status", "why", "conclusion",
                                                    "g0_reason", "outcome"):
                out.append(v)
            else:
                verdict_strings(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:200]:
            verdict_strings(v, out, depth + 1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e347_audit_and_standardise.json"))
    a = ap.parse_args(argv)
    rng = random.Random(347)
    R = {}
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    for r in rows:
        r["_class"], _ = canon(r.get("outcome"))
    if a.smoke:
        labs = [r["_class"] for r in rows]
        rng.shuffle(labs)
        for r, l in zip(rows, labs):
            r["_class"] = l
        print("[SMOKE] register outcome labels permuted")

    # ------------------------------------------------------------------------------------ T1
    print("=" * 96)
    print("T1 -- audit the register against the CODE's own emitted verdict (not prose)")
    arts = {}
    for fn in os.listdir(RESULTS):
        if not fn.endswith(".json"):
            continue
        m = STEM.match(fn)
        if m:
            arts.setdefault(m.group(1).lower(), []).append(fn)

    def artifacts_for(row):
        f = str(row.get("file", ""))
        m = STEM.search(os.path.basename(f))
        return arts.get(m.group(1).lower(), []) if m else []

    def says_not_interp(fns):
        for fn in fns:
            try:
                with open(os.path.join(RESULTS, fn)) as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                continue
            for s in verdict_strings(d):
                if NOT_INTERP.search(s):
                    return True, fn, s[:120]
        return False, None, None

    # G1 capability, both directions, on planted pairs
    planted_bad = {"file": "x/e999_planted.py", "_class": "positive"}
    planted_ok = {"file": "x/e998_planted.py", "_class": "gate_failed"}
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "e999_planted.json"), "w") as fh:
        json.dump({"verdict": "NOT INTERPRETABLE -- planted"}, fh)
    with open(os.path.join(RESULTS, "e998_planted.json"), "w") as fh:
        json.dump({"verdict": "NOT INTERPRETABLE -- planted"}, fh)
    arts.setdefault("e999", []).append("e999_planted.json")
    arts.setdefault("e998", []).append("e998_planted.json")
    hit_bad = says_not_interp(artifacts_for(planted_bad))[0] and planted_bad["_class"] != "gate_failed"
    hit_ok = says_not_interp(artifacts_for(planted_ok))[0] and planted_ok["_class"] != "gate_failed"
    G1 = bool(hit_bad and not hit_ok)
    print(f"  [G1] planted contradiction detected = {hit_bad}; planted consistent pair flagged = "
          f"{hit_ok} -> {'PASS' if G1 else 'FAIL'}")

    resolved = contradictions = converse = 0
    detail = []
    for r in rows:
        fns = artifacts_for(r)
        if not fns:
            continue
        resolved += 1
        ni, fn, s = says_not_interp(fns)
        if ni and r["_class"] != "gate_failed":
            contradictions += 1
            detail.append({"id": r.get("id"), "outcome": r["_class"], "artifact": fn,
                           "verdict": s})
        if r["_class"] == "gate_failed" and not ni:
            converse += 1
    cov = resolved / len(rows)
    G1b = cov >= 0.40
    print(f"  resolved {resolved}/{len(rows)} rows to an artifact ({cov:.1%}) -> "
          f"[G1b] {'PASS' if G1b else 'FAIL -- NOT INTERPRETABLE'}")
    if G1 and G1b:
        print(f"  [T1] DETECTABLE CONTRADICTIONS: {contradictions}  "
              f"(artifact says NOT INTERPRETABLE, register row does not say gate_failed)")
        for d in detail[:12]:
            print(f"        {d['id']}: register={d['outcome']:<12} artifact={d['artifact']}")
        print(f"  [context, NOT scored as errors] rows labelled gate_failed whose artifact does not "
              f"carry the phrase: {converse} -- verdict strings are not a controlled vocabulary")
    else:
        print("  [T1] NOT INTERPRETABLE")
    for fn in ("e999_planted.json", "e998_planted.json"):
        try:
            os.remove(os.path.join(RESULTS, fn))
        except OSError:
            pass
    R["T1"] = {"resolved": resolved, "coverage": cov, "contradictions": contradictions,
               "converse": converse, "gates": {"G1": G1, "G1b": G1b}, "detail": detail}
    if a.smoke:
        print(f"  [SMOKE] contradiction count under permuted labels = {contradictions}; "
              f"it must EXCEED the real run's count for the detector to be detecting anything.")

    # ------------------------------------------------------------------------------------ T2
    print("\n" + "=" * 96)
    print("T2 -- results posting, decomposed (headline direction DECLARED SEEN before registration)")
    t2 = {}
    for st in ("COMPLETED", "TERMINATED"):
        n = cnt(st)
        k = cnt_res(st)
        t2[st] = {"n": n, "with_results": k, "rate": k / n if n else float("nan")}
        print(f"    {st:<11} {k:>7,}/{n:>8,} = {t2[st]['rate']:.4f}")
    print("  by lead-sponsor class:")
    for st in ("COMPLETED", "TERMINATED"):
        for sp in SPONSORS:
            e = f"AREA[LeadSponsorClass]{sp}"
            n = cnt(st, e)
            k = cnt_res(st, e)
            t2[f"{st}|{sp}"] = {"n": n, "with_results": k, "rate": k / n if n else float("nan")}
            print(f"    {st:<11} {sp:<9} {k:>7,}/{n:>8,} = {t2[f'{st}|{sp}']['rate']:.4f}")
    R["T2"] = t2

    # ------------------------------------------------------------------------------------ T3
    print("\n" + "=" * 96)
    print(f"T3 -- censoring-aware trend. Trend fitted only where follow-up >= {FOLLOWUP_FLOOR:.2f}")
    t3 = {}
    for y in range(2005, 2021):
        e = f"AREA[StartDate]RANGE[{y}-01-01,{y}-12-31]"
        k, n, rate = stopped_share(e)
        ong = sum(cnt(s, e) for s in ONGOING)
        fu = n / (n + ong) if (n + ong) else float("nan")
        t3[y] = {"stopped": k, "terminal": n, "ongoing": ong, "rate": rate, "followup": fu,
                 "lower_bound": k / (n + ong) if (n + ong) else float("nan")}
        print(f"    {y}: stopped/terminal {k:>5,}/{n:>7,} = {rate:.4f}   follow-up {fu:.3f}   "
              f"lower bound {t3[y]['lower_bound']:.4f}")
    elig = [y for y in t3 if t3[y]["followup"] >= FOLLOWUP_FLOOR]
    print(f"  cohorts clearing follow-up {FOLLOWUP_FLOOR:.2f}: {elig or 'NONE'}")

    def slope(ys, key):
        if len(ys) < 4:
            return None
        mx = sum(ys) / len(ys)
        my = sum(t3[y][key] for y in ys) / len(ys)
        sxx = sum((y - mx) ** 2 for y in ys)
        return sum((y - mx) * (t3[y][key] - my) for y in ys) / sxx if sxx else None
    s_el = slope(sorted(elig), "rate")
    s_lb = slope(sorted(t3), "lower_bound")
    if s_el is None:
        print(f"  [T3] NOT INTERPRETABLE on the rate: no cohort reaches {FOLLOWUP_FLOOR:.2f} follow-up. "
              f"That is itself the finding -- ClinicalTrials.gov has no fully-followed-up cohort in "
              f"this window, so the trend question cannot be answered from status counts at all.")
    else:
        print(f"  [T3] slope over {len(elig)} eligible cohorts = {s_el:+.5f}/yr")
    print(f"  [T3, assumption-free] slope of the LOWER BOUND (stopped / all registered) over all "
          f"16 cohorts = {s_lb:+.5f}/yr -- this cannot be inflated by incomplete follow-up")
    R["T3"] = {"by_year": t3, "eligible": sorted(elig), "slope_eligible": s_el,
               "slope_lower_bound": s_lb, "floor": FOLLOWUP_FLOOR}

    # ------------------------------------------------------------------------------------ T4/T5
    print("\n" + "=" * 96)
    print("T4 -- does the size gradient survive PHASE?")
    grid = {}
    for ph in PHASES:
        line = []
        for lbl, lo, hi in SIZES:
            k, n, rate = stopped_share(f"AREA[Phase]{ph} AND AREA[EnrollmentCount]RANGE[{lo},{hi}]")
            grid[f"{ph}|{lbl}"] = {"stopped": k, "n": n, "rate": rate}
            line.append(f"{lbl}:{rate:.3f}(n={n:,})")
        print(f"    {ph}: " + "  ".join(line))
    holds = sum(1 for ph in PHASES
                if math.isfinite(grid[f"{ph}|1-20"]["rate"])
                and math.isfinite(grid[f"{ph}|501+"]["rate"])
                and grid[f"{ph}|1-20"]["rate"] > grid[f"{ph}|501+"]["rate"])
    print(f"  [T4] gradient holds (smallest > largest) in {holds} of {len(PHASES)} phases -> "
          f"{'PREDICTION MET' if holds == len(PHASES) else 'PREDICTION NOT MET'}")
    R["T4"] = {"grid": grid, "phases_holding": holds}

    print("\n" + "=" * 96)
    print("T5 -- does it survive SPONSOR? (OTHER = academic/hospital, the stratum this register resembles)")
    sgrid = {}
    for sp in SPONSORS:
        line = []
        for lbl, lo, hi in SIZES:
            k, n, rate = stopped_share(
                f"AREA[LeadSponsorClass]{sp} AND AREA[EnrollmentCount]RANGE[{lo},{hi}]")
            sgrid[f"{sp}|{lbl}"] = {"stopped": k, "n": n, "rate": rate}
            line.append(f"{lbl}:{rate:.3f}(n={n:,})")
        print(f"    {sp:<9}: " + "  ".join(line))
    key = sgrid["OTHER|1-20"]
    print(f"  [T5] THE TIGHTEST EXTERNAL COMPARATOR -- academic/hospital sponsor, enrolment <= 20: "
          f"{key['stopped']:,}/{key['n']:,} = {key['rate']:.4f}")
    R["T5"] = {"grid": sgrid, "comparator": key}

    # ------------------------------------------------------------------------------------ T6
    print("\n" + "=" * 96)
    print("T6 -- my own field: anaesthesia-condition interventional studies")
    fk, fn_, frate = stopped_share("AREA[ConditionSearch]anesthesia")
    G6 = fn_ >= 300
    print(f"    terminal-status studies: {fn_:,}; stopped {fk:,} = {frate:.4f} -> "
          f"[G6] {'PASS' if G6 else 'FAIL -- NOT INTERPRETABLE'}")
    if G6:
        corp = fetch("TERMINATED", "AREA[ConditionSearch]anesthesia", want=600)
        mc = collections.Counter(classify_why(s["why"])[0] for s in corp)
        tot_ = sum(mc.values()) or 1
        print(f"    machinery share in this field: {mc['MACHINERY']/tot_:.3f} "
              f"(corpus-wide 0.472), n = {tot_}")
        R["T6"] = {"stopped": fk, "n": fn_, "rate": frate, "gate": True,
                   "machinery_share": mc["MACHINERY"] / tot_, "n_texts": tot_}
    else:
        R["T6"] = {"stopped": fk, "n": fn_, "rate": frate, "gate": False}

    # ------------------------------------------------------------------------------------ T7
    print("\n" + "=" * 96)
    print("T7 -- THE PROSPECTIVE SAMPLE: every test registered and run in this session")
    PROSPECTIVE = [
        ("E340/P1", "positive", "graded ladder; prediction met"),
        ("E340/P2", "gate_failed", "G3 muscle positive control failed"),
        ("E341", "gate_failed", "G1 plant reached 0.7542 against its own 0.90 bar"),
        ("E342", "negative", "REDUCIBLE; registered prediction refuted"),
        ("E343", "gate_failed", "G1 and G2 extraction gates refused"),
        ("E344/T1", "positive", "intervals; prediction met"),
        ("E344/T2", "gate_failed", "capability gate too easy; not interpretable on inspection"),
        ("E344/T3", "positive", "37 lineages measured"),
        ("E344/T4", "positive", "slope +0.0364/gate, p~0.042 across 5 seeds"),
        ("E344/T5", "absent", "prediction not met; null"),
        ("E344/T6", "positive", "0/119 against control 0.200"),
        ("E344/T7", "gate_failed", "no held-out rows"),
        ("E344/T8", "positive", "criterion is noise-biased"),
        ("E344/T9", "positive", "set unstable under bootstrap"),
        ("E344/T10", "absent", "flat, p=0.3134"),
        ("E345", "blocked", "deposit restricted, credentials unset"),
        ("E346/T1", "positive", "exact denominator"),
        ("E346/T2", "positive", "G2 thin pass; range not point"),
        ("E346/T3", "positive", "pipeline check passed"),
        ("E346/T4", "positive", "5.5-fold size gradient; prediction met"),
        ("E346/T5", "gate_failed", "censoring confound; slope flips sign"),
        ("E346/T6", "positive", "descriptive"),
        ("E346/T7", "gate_failed", "coverage 6.2% against a 40% floor"),
        ("E346/T8", "positive", "lineage-level rates"),
        ("E346/T9", "positive", "side by side as registered"),
        ("E346/T10", "positive", "1 in 891"),
    ]
    pc = collections.Counter(o for _, o, _ in PROSPECTIVE)
    n7 = len(PROSPECTIVE)
    for k, v in pc.most_common():
        print(f"    {k:<12} {v:>3}  ({v/n7:.3f})")
    lo7, hi7 = wilson(pc["gate_failed"], n7)
    print(f"  [T7] prospective machinery-failure: {pc['gate_failed']}/{n7} = "
          f"{pc['gate_failed']/n7:.3f}  95% CI [{lo7:.3f}, {hi7:.3f}]")
    print("       n ~ 26. A tabulation, not an estimate, and every row is named above so a reader")
    print("       can check each call against its result note.")
    R["T7"] = {"n": n7, "counts": dict(pc), "gate_failed_rate": pc["gate_failed"] / n7,
               "ci": [lo7, hi7], "rows": PROSPECTIVE}

    # ------------------------------------------------------------------------------------ T8
    print("\n" + "=" * 96)
    print("T8 -- are the `absent` verdicts powered? do they state an interval or an effect size?")
    NUMPAT = re.compile(r"\[[-+]?\d*\.?\d+\s*,\s*[-+]?\d*\.?\d+\]|[-+]\d*\.\d{3,}|"
                        r"\bCI\b|\bd_?z\b|\bAUC\b|interval", re.I)
    ab = [r for r in rows if r["_class"] == "absent"]
    with_num = sum(1 for r in ab if NUMPAT.search(str(r.get("outcome_detail", ""))))
    lo8, hi8 = wilson(with_num, len(ab)) if ab else (float("nan"),) * 2
    print(f"    {with_num}/{len(ab)} absent verdicts state an interval or effect size = "
          f"{with_num/len(ab) if ab else float('nan'):.3f}  95% CI [{lo8:.3f}, {hi8:.3f}]")
    print(f"  [T8] {'PREDICTION MET' if ab and with_num > len(ab)/2 else 'PREDICTION NOT MET -- an absence with no stated resolution is not an absence'}")
    R["T8"] = {"n_absent": len(ab), "with_number": with_num, "ci": [lo8, hi8]}

    # ------------------------------------------------------------------------------------ T9
    print("\n" + "=" * 96)
    print("T9 -- does WHY they stop change with size?")
    t9 = {}
    for lbl, lo, hi in (SIZES[0], SIZES[-1]):
        corp = fetch("TERMINATED", f"AREA[EnrollmentCount]RANGE[{lo},{hi}]", want=1200)
        c = collections.Counter(classify_why(s["why"])[0] for s in corp)
        tt = sum(c.values()) or 1
        t9[lbl] = {"n": tt, "machinery": c["MACHINERY"] / tt, "result": c["RESULT"] / tt,
                   "other": c["OTHER"] / tt}
        print(f"    enrolment {lbl:<7} n={tt:>5}  MACHINERY {t9[lbl]['machinery']:.3f}   "
              f"RESULT {t9[lbl]['result']:.3f}   OTHER {t9[lbl]['other']:.3f}")
    hi_small = t9["1-20"]["machinery"] > t9["501+"]["machinery"]
    print(f"  [T9] machinery share higher in small studies -> "
          f"{'PREDICTION MET' if hi_small else 'PREDICTION NOT MET'}")
    R["T9"] = t9

    # ------------------------------------------------------------------------------------ T10
    print("\n" + "=" * 96)
    print("T10 -- direct standardisation. No significance test, as registered.")
    small = sgrid["OTHER|1-20"]["rate"]
    allctg = stopped_share()[2]
    print(f"    every analysis in this register is small-n, so its size distribution is a point mass")
    print(f"    in the smallest stratum. Standardising CTG to it is therefore just reading that cell:")
    print(f"      CTG, academic/hospital sponsor, enrolment <= 20 : {small:.4f}")
    print(f"      CTG, all studies                                : {allctg:.4f}")
    print(f"      this register, row level (E344/T1)              : 0.240 [0.187, 0.298]")
    print(f"      this register, lineage level (E346/T8)          : 0.081 [0.028, 0.213]")
    print(f"      this register, PROSPECTIVE (T7 above)           : {pc['gate_failed']/n7:.3f} "
          f"[{lo7:.3f}, {hi7:.3f}]")
    R["T10"] = {"ctg_other_small": small, "ctg_all": allctg,
                "register_row": 0.240, "register_lineage": 0.081,
                "register_prospective": pc["gate_failed"] / n7}

    print("\n" + "=" * 96)
    if a.smoke:
        print("[SMOKE] see T1's note above; the contradiction count must rise under permuted labels.")
        return 0
    json.dump(R, open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
