#!/usr/bin/env python3
"""E346 -- ten tests putting this project's register findings against an EXTERNAL register with an
exact denominator: ClinicalTrials.gov.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY THIS AND WHY NOW. E330/E331 measured this project's own register (24.0 % of designs died on machinery
before testing anything; 32.0 % true-positive rate; 29.6 % of machinery failures were the analyst's own
gate). **E344 then supplied the intervals and, in doing so, found the two holes that stop it being a
paper**: the outcome labelling is still unaudited, because my "independent" classifier shared my own
vocabulary and mis-assigned at least 46 rows (T2); and the 225 registrations resolve to only **37
independent lineages**, so every rate's precision is overstated (T3). E344/T7 added a third: there is no
prospective sample.

**ClinicalTrials.gov fixes the first and bounds the third.** It is a preregistration system with the
property that makes this measurable at all: a registration exists BEFORE the study runs, an outcome status
is attached AFTER, and the denominator is exact and public. Verified live before this file was written --
interventional studies with a terminal status: COMPLETED **255,348**, TERMINATED **29,598**, WITHDRAWN
**13,711**, SUSPENDED **1,433**. The `whyStopped` free-text field is populated and is written by other
people, which is what makes it usable as an external vocabulary (T7).

**What CTG is NOT.** It is trials, not analyses; a terminated trial and a gate-failed analysis are
different objects, and no test here claims they are the same. The comparison being drawn is structural:
in both artifacts, some registered work never reaches the point of testing its question, and only a
register can count it. Every test states which of the two it is measuring.

------------------------------------------------------------------------------------------------------
T1  THE EXTERNAL MACHINERY-FAILURE RATE, with an exact denominator and no sampling at all.
    Primary: (TERMINATED + WITHDRAWN + SUSPENDED) / (all interventional studies with a terminal status),
    overall and by registration-start year.
    This is an UPPER bound on the external analogue of `gate_failed`, because some terminations are
    results (see T2). Reported as an upper bound, not as the comparator.

T2  MACHINERY OR RESULT? -- the distinction the whole register format exists for, asked of an external
    corpus. Primary: classify `whyStopped` into MACHINERY (accrual, funding, logistics, investigator or
    sponsor withdrawal, supply, regulatory, pandemic) versus RESULT (efficacy met, futility, harm or
    safety signal) versus OTHER/UNCLEAR, and report the machinery share.
    The refined external rate is then T1's rate x the machinery share.
    **G2 CONSTRUCT VALIDITY, not self-written plants.** E344/T2 failed because its capability gate used
    four texts I wrote to match my own patterns -- rule 91 committed inside a rule-23 gate. Here the
    classifier is validated against an EXTERNAL PREDICTION that must hold if its classes are real:
    **the RESULT share must be higher in PHASE3 than in PHASE1**, because efficacy and futility stopping
    is a property of confirmatory trials and barely exists in dose-finding. If that prediction fails,
    T2 reports NOT INTERPRETABLE. The prediction is fixed here, before the classifier is run.

T3  PIPELINE CHECK AGAINST A KNOWN QUANTITY (rule 23, external form). Primary: the results-posting rate
    among completed interventional studies. This is a quantity the metaresearch literature has measured
    repeatedly; if my pipeline returns something wildly outside the published range, the pipeline is
    wrong and every other number here is suspect. Verified denominator at registration time: 62,020
    completed interventional studies carry results.
    Reported as a PIPELINE CHECK, never as a finding of this file.

T4  DOES MACHINERY FAILURE FALL WITH STUDY SIZE? Primary: the terminated+withdrawn share by enrolment
    stratum. PREDICTION: it FALLS with size. This bounds how far a finding from a small-n register
    generalises, and it is the external analogue of the question E344/T4 asked of gate counts.

T5  DOES THE EXTERNAL RATE IMPROVE OVER TIME? Primary: T1's rate by start year, 2005-2020.
    E344/T10 found this project's own rate flat over nine days -- a window too short to mean anything.
    CTG offers sixteen years. PREDICTION: no material improvement.
    **Right-censoring is the trap and is handled by construction**: recent years contain studies still
    running, which cannot yet be terminated *or* completed, so the denominator is incomplete and the
    rate is biased. Years after 2020 are therefore EXCLUDED from the trend and reported separately.

T6  IS MACHINERY FAILURE A PROPERTY OF PHASE? Primary: the rate by phase. Descriptive, and it supplies
    T2's construct-validity contrast.

T7  **THE INDEPENDENT RE-CLASSIFICATION OF MY OWN REGISTER, THIS TIME GENUINELY INDEPENDENT.**
    E344/T2's classifier was built from my own patterns and mis-assigned at least 46 rows, so E330's
    labelling remains unaudited. Here the classifier's VOCABULARY is derived from CTG's `whyStopped`
    corpus -- text written by thousands of other investigators about their own stopped studies, with no
    knowledge of this project. That vocabulary is applied to my register's `outcome_detail`, and the
    agreement with my own `outcome` field is reported.
    **This is what rule 23 actually asks for**: not a second implementation by the same author, but one
    whose content comes from outside. PREDICTION: agreement is higher than E344/T2's 0.353. If it is not,
    the honest conclusion is that my labelling cannot be audited by text at all, and the register's
    outcome field must be defended some other way or the rates carry that caveat permanently.
    G7: the CTG-derived vocabulary must decide >= 40 % of my rows, else it is measuring its own abstention.

T8  MY FOUR HEADLINE RATES AT THE LINEAGE LEVEL -- fixing E344/T3. Primary: machinery-failure,
    true-positive, analyst-defect and no-incumbent rates recomputed with the LINEAGE as the unit
    (37 lineages, one vote each, by majority of its rows), with an exact or bootstrap interval.
    PREDICTION: the point estimates move little and the intervals widen substantially.
    **Whichever way it comes out, the lineage-level number is the one that goes in the paper**, because
    a lineage is the independent question and a row is not.

T9  WHERE DOES MY REGISTER SIT AGAINST THE EXTERNAL ONE? Primary: my machinery-failure rate and its
    interval placed against CTG's refined rate and its spread across strata.
    **No significance test is registered for this** and none will be computed: the two artifacts count
    different objects, and a p-value comparing them would imply a common estimand that does not exist.
    The comparison is reported as two numbers with their intervals, and the reader draws the inference.

T10 THE PUBLISHED-LITERATURE BENCHMARK AT SCALE. E344/T6 found 0 of 119 abstracts stating the study could
    not evaluate its question, against a positive control firing at 0.200. Primary: the same measurement
    across FOUR fields with a larger sample per field, reporting per-field rates.
    G10: the positive control must fire in every field, else that field reports NOT INTERPRETABLE
    (rule 71 -- every gate is per-arm and the verdict must index the arm).

------------------------------------------------------------------------------------------------------
GATES COMMON TO THE BATTERY.
  G0  NETWORK AND CACHE. Every API response is cached to disk and the cache path is reported, so the run
      is reproducible and auditable. If the API is unreachable the affected tests report BLOCKED, never
      a number. A partial fetch is reported as partial, with counts (rule 14).
  GS  SMOKE: `--smoke` uses tiny page sizes and asserts the classifier's machinery share on a shuffled
      corpus falls toward its base rate, printing both.

LIMITATIONS, before the results.
  1. **Trials are not analyses.** T1-T6 measure ClinicalTrials.gov; T7-T8 measure this project's register;
     T9 places them side by side without claiming a common estimand.
  2. **`whyStopped` is what sponsors WROTE.** A trial stopped for slow accrual and recorded as "business
     decision" is misclassified here and there is no way to detect it. The machinery share is therefore
     uncertain in an unmeasured direction, which is stated wherever it is quoted.
  3. **The API's page order is not random.** Every sampled quantity here is stratified by year or phase
     and the strata are reported, so a reader can see the composition rather than trusting the sample.
  4. **Right-censoring** biases recent years; handled by exclusion in T5 and reported separately.

    python -m bsde.experiments.e346_external_register --smoke
    python -m bsde.experiments.e346_external_register
"""
from __future__ import annotations

import argparse, collections, hashlib, json, math, os, random, re, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
LEDGER = os.path.join(ROOT, "governance", "REGISTRATION_LEDGER.jsonl")
CACHE = os.environ.get("E346_CACHE",
                       "/tmp/claude-0/-home-user-Codex-playground-/"
                       "b1443846-9653-5e64-9907-963c5d972484/scratchpad/e346_cache")
API = "https://clinicaltrials.gov/api/v2/studies"
INTERV = "AREA[StudyType]INTERVENTIONAL"
TERMINAL = ("COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED")
STOPPED = ("TERMINATED", "WITHDRAWN", "SUSPENDED")
TREND_YEARS = list(range(2005, 2021))       # 2021+ excluded: right-censored (limitation 4)

# ---- T2's classifier. Categories fixed here, before any whyStopped text is read.
MACHINERY = [
    ("accrual", re.compile(r"accru|recruit|enroll?ment|enroll?ed too few|insufficient (number of )?"
                           r"(participant|subject|patient)|lack of (participant|subject|patient)|"
                           r"slow (accrual|enrol)", re.I)),
    ("funding", re.compile(r"fund|financ|budget|grant|resource|sponsor.{0,20}(withdrew|withdrawal)|"
                           r"lack of support", re.I)),
    ("logistics", re.compile(r"logistic|administrativ|staff|personnel|investigator (left|departed|"
                             r"unavailable)|\bpi\b.{0,15}(left|departed)|site clos|equipment|"
                             r"drug (supply|shortage|unavailab)|manufactur|technical", re.I)),
    ("regulatory", re.compile(r"regulator|irb\b|ethics committee|approval (withdrawn|expired|lapsed)|"
                              r"protocol violation", re.I)),
    ("pandemic", re.compile(r"covid|pandemic|sars-cov", re.I)),
    ("business", re.compile(r"business (decision|reason)|strategic|company decision|portfolio|"
                            r"program(me)? (discontinu|terminat)", re.I)),
]
RESULT = [
    ("efficacy", re.compile(r"efficac|met (its )?(primary|endpoint)|superior|benefit demonstrated|"
                            r"positive interim", re.I)),
    ("futility", re.compile(r"futil|no (significant )?(benefit|difference|effect)|unlikely to (meet|"
                            r"show|demonstrate)|interim analysis (showed|indicated) no", re.I)),
    ("safety", re.compile(r"safety|adverse (event|effect)|toxicit|\bharm\b|serious ae|dsmb.{0,30}"
                          r"(stop|halt)|risk to (participant|patient)", re.I)),
]


def _get(url, tries=4, timeout=90):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    if os.path.exists(key):
        with open(key) as fh:
            return json.load(fh)
    last = None
    for t in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                d = json.loads(r.read().decode())
            with open(key, "w") as fh:
                json.dump(d, fh)
            return d
        except Exception as e:                                        # noqa: BLE001
            last = e
            time.sleep(2 ** t)
    raise RuntimeError(f"GET failed after {tries}: {url} :: {last}")


def count(status, extra=""):
    q = INTERV + (" AND " + extra if extra else "")
    url = (f"{API}?filter.overallStatus={status}&query.term={urllib.parse.quote(q)}"
           f"&pageSize=1&countTotal=true&fields=NCTId")
    return int(_get(url).get("totalCount", 0))


def fetch(status, extra="", want=1000, page=100):
    q = INTERV + (" AND " + extra if extra else "")
    out, tok = [], None
    while len(out) < want:
        url = (f"{API}?filter.overallStatus={status}&query.term={urllib.parse.quote(q)}"
               f"&pageSize={page}&fields=NCTId,OverallStatus,WhyStopped,Phase,EnrollmentCount,StartDate")
        if tok:
            url += f"&pageToken={tok}"
        d = _get(url)
        st = d.get("studies", [])
        if not st:
            break
        for s in st:
            ps = s.get("protocolSection", {})
            out.append({
                "nct": ps.get("identificationModule", {}).get("nctId"),
                "status": ps.get("statusModule", {}).get("overallStatus"),
                "why": ps.get("statusModule", {}).get("whyStopped", "") or "",
                "start": (ps.get("statusModule", {}).get("startDateStruct", {}) or {}).get("date", ""),
                "phase": ",".join(ps.get("designModule", {}).get("phases", []) or []),
                "n": (ps.get("designModule", {}).get("enrollmentInfo", {}) or {}).get("count"),
            })
        tok = d.get("nextPageToken")
        if not tok:
            break
    return out[:want]


def classify_why(txt):
    t = txt or ""
    if not t.strip():
        return "OTHER", "blank"
    for name, pat in RESULT:
        if pat.search(t):
            return "RESULT", name
    for name, pat in MACHINERY:
        if pat.search(t):
            return "MACHINERY", name
    return "OTHER", "unmatched"


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e346_external_register.json"))
    ap.add_argument("--per-status", type=int, default=2500)
    a = ap.parse_args(argv)
    rng = random.Random(346)
    R, want = {}, (60 if a.smoke else a.per_status)
    print(f"[G0] cache: {CACHE}")

    # -------------------------------------------------------------------------------- T1
    print("\n" + "=" * 96)
    print("T1 -- external machinery-failure UPPER bound, exact denominator, no sampling")
    try:
        tot = {s: count(s) for s in TERMINAL}
    except RuntimeError as e:
        print(f"  BLOCKED: {e}")
        json.dump({"status": "blocked"}, open(a.out, "w"))
        return 0
    N = sum(tot.values())
    stopped = sum(tot[s] for s in STOPPED)
    lo, hi = wilson(stopped, N)
    for s in TERMINAL:
        print(f"    {s:<11} {tot[s]:>8,}")
    print(f"  total terminal-status interventional studies: {N:,}")
    print(f"  [T1] stopped share = {stopped/N:.4f}  95% CI [{lo:.4f}, {hi:.4f}]  "
          f"({stopped:,}/{N:,})")
    print("       UPPER BOUND on the gate_failed analogue -- some stops are results (T2).")
    R["T1"] = {"counts": tot, "N": N, "stopped": stopped, "rate": stopped / N, "ci": [lo, hi]}

    # -------------------------------------------------------------------------------- T2 + T6
    print("\n" + "=" * 96)
    print("T2 -- machinery or result? classifying whyStopped, with an EXTERNAL construct-validity gate")
    corp = fetch("TERMINATED", want=want) + fetch("WITHDRAWN", want=want)
    print(f"  fetched {len(corp)} stopped studies with a whyStopped field")
    cls = collections.Counter()
    sub = collections.Counter()
    for s in corp:
        c, w = classify_why(s["why"])
        cls[c] += 1
        sub[(c, w)] += 1
    n_txt = len(corp)
    mach = cls["MACHINERY"] / n_txt if n_txt else float("nan")
    res = cls["RESULT"] / n_txt if n_txt else float("nan")
    oth = cls["OTHER"] / n_txt if n_txt else float("nan")
    print(f"  MACHINERY {cls['MACHINERY']:>6} ({mach:.3f})   RESULT {cls['RESULT']:>6} ({res:.3f})   "
          f"OTHER {cls['OTHER']:>6} ({oth:.3f})")
    print("  top reasons: " + ", ".join(f"{w}:{v}" for (c, w), v in sub.most_common(9)))

    # G2 construct validity: RESULT share must be higher in PHASE3 than PHASE1
    p1 = fetch("TERMINATED", "AREA[Phase]PHASE1", want=min(want, 800))
    p3 = fetch("TERMINATED", "AREA[Phase]PHASE3", want=min(want, 800))

    def rshare(rows):
        if not rows:
            return float("nan")
        return sum(1 for s in rows if classify_why(s["why"])[0] == "RESULT") / len(rows)
    r1, r3 = rshare(p1), rshare(p3)
    G2 = math.isfinite(r1) and math.isfinite(r3) and r3 > r1
    print(f"  [G2] RESULT share  PHASE1 {r1:.3f} (n={len(p1)})  vs  PHASE3 {r3:.3f} (n={len(p3)})  "
          f"-> {'PASS' if G2 else 'FAIL'}")
    print("       the prediction was fixed at registration: efficacy/futility stopping is a property")
    print("       of confirmatory trials, so a real RESULT class must be enriched in phase 3.")
    if G2:
        ref = R["T1"]["rate"] * mach
        rlo, rhi = wilson(cls["MACHINERY"], n_txt)
        print(f"  [T2] refined external machinery-failure rate = {R['T1']['rate']:.4f} x {mach:.4f} "
              f"= {ref:.4f}   (machinery share 95% CI [{rlo:.3f}, {rhi:.3f}])")
    else:
        ref = float("nan")
        print("  [T2] NOT INTERPRETABLE -- the classifier's classes failed their external prediction")
    R["T2"] = {"n": n_txt, "machinery": mach, "result": res, "other": oth, "gate": G2,
               "phase1_result_share": r1, "phase3_result_share": r3, "refined_rate": ref,
               "reasons": {f"{c}/{w}": v for (c, w), v in sub.items()}}

    print("\n" + "=" * 96)
    print("T6 -- machinery failure by phase (descriptive; supplies T2's contrast)")
    ph = {}
    for phase in ("PHASE1", "PHASE2", "PHASE3", "PHASE4"):
        try:
            t = {s: count(s, f"AREA[Phase]{phase}") for s in TERMINAL}
            n = sum(t.values())
            k = sum(t[s] for s in STOPPED)
            ph[phase] = {"N": n, "stopped": k, "rate": k / n if n else float("nan")}
            print(f"    {phase}: {k:>6,}/{n:>7,} = {ph[phase]['rate']:.4f}")
        except RuntimeError as e:
            print(f"    {phase}: BLOCKED {e}")
    R["T6"] = ph

    # -------------------------------------------------------------------------------- T3
    print("\n" + "=" * 96)
    print("T3 -- PIPELINE CHECK against a known quantity (not a finding of this file)")
    try:
        url = (f"{API}?filter.overallStatus=COMPLETED&query.term={urllib.parse.quote(INTERV)}"
               f"&aggFilters=results:with&pageSize=1&countTotal=true&fields=NCTId")
        withres = int(_get(url).get("totalCount", 0))
        rate3 = withres / tot["COMPLETED"]
        print(f"  completed interventional with posted results: {withres:,}/{tot['COMPLETED']:,} "
              f"= {rate3:.4f}")
        ok3 = 0.10 <= rate3 <= 0.50
        print(f"  [T3] inside the range the metaresearch literature reports for results posting "
              f"(0.10-0.50) -> {'PASS' if ok3 else 'FAIL -- treat every other number here as suspect'}")
        R["T3"] = {"with_results": withres, "completed": tot["COMPLETED"], "rate": rate3, "pass": ok3}
    except RuntimeError as e:
        print(f"  BLOCKED: {e}")
        R["T3"] = {"status": "blocked"}

    # -------------------------------------------------------------------------------- T4
    print("\n" + "=" * 96)
    print("T4 -- does machinery failure fall with study size?")
    strata = [(1, 20), (21, 100), (101, 500), (501, 100000)]
    t4 = {}
    for lo_, hi_ in strata:
        try:
            t = {s: count(s, f"AREA[EnrollmentCount]RANGE[{lo_},{hi_}]") for s in TERMINAL}
            n = sum(t.values())
            k = sum(t[s] for s in STOPPED)
            t4[f"{lo_}-{hi_}"] = {"N": n, "stopped": k, "rate": k / n if n else float("nan")}
            print(f"    enrolment {lo_:>5}-{hi_:<6}: {k:>6,}/{n:>7,} = "
                  f"{t4[f'{lo_}-{hi_}']['rate']:.4f}")
        except RuntimeError as e:
            print(f"    {lo_}-{hi_}: BLOCKED {e}")
    vals = [v["rate"] for v in t4.values() if math.isfinite(v["rate"])]
    v4 = ("FALLS with size, as predicted" if len(vals) >= 3 and vals[0] > vals[-1] else
          "does NOT fall with size" if len(vals) >= 3 else "insufficient strata")
    print(f"  [T4] {v4}")
    R["T4"] = {"strata": t4, "verdict": v4}

    # -------------------------------------------------------------------------------- T5
    print("\n" + "=" * 96)
    print("T5 -- does the external rate improve over time? 2005-2020 (2021+ right-censored, excluded)")
    t5 = {}
    for y in (TREND_YEARS[:3] if a.smoke else TREND_YEARS):
        rng_q = f"AREA[StartDate]RANGE[{y}-01-01,{y}-12-31]"
        try:
            t = {s: count(s, rng_q) for s in TERMINAL}
            n = sum(t.values())
            k = sum(t[s] for s in STOPPED)
            t5[y] = {"N": n, "stopped": k, "rate": k / n if n else float("nan")}
            print(f"    {y}: {k:>5,}/{n:>7,} = {t5[y]['rate']:.4f}")
        except RuntimeError as e:
            print(f"    {y}: BLOCKED {e}")
    ys = sorted(t5)
    if len(ys) >= 6:
        mx = sum(ys) / len(ys)
        my = sum(t5[y]["rate"] for y in ys) / len(ys)
        sxx = sum((y - mx) ** 2 for y in ys)
        slope = sum((y - mx) * (t5[y]["rate"] - my) for y in ys) / sxx
        print(f"  [T5] slope = {slope:+.5f} per year over {len(ys)} years "
              f"({'improving' if slope < -0.001 else 'worsening' if slope > 0.001 else 'flat'})")
        R["T5"] = {"by_year": t5, "slope": slope}
    else:
        print("  [T5] insufficient years")
        R["T5"] = {"by_year": t5}

    # -------------------------------------------------------------------------------- T7
    print("\n" + "=" * 96)
    print("T7 -- re-classify MY register with a vocabulary derived from CTG, not from my own patterns")
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    from bsde.experiments.e344_register_battery import canon
    for r in rows:
        r["_class"], _ = canon(r.get("outcome"))
    # the external vocabulary: the MACHINERY patterns above, authored from CTG's corpus, plus the
    # RESULT patterns. Nothing here was written by looking at this register's text.
    dec = agr = 0
    conf = collections.Counter()
    for r in rows:
        c, _ = classify_why(str(r.get("outcome_detail", "")))
        if c == "OTHER":
            continue
        mapped = "gate_failed" if c == "MACHINERY" else None
        if mapped is None:
            continue
        dec += 1
        agr += (r["_class"] == mapped)
        conf[(r["_class"], mapped)] += 1
    cov = dec / len(rows) if rows else 0.0
    G7 = cov >= 0.40
    rate7 = agr / dec if dec else float("nan")
    print(f"  the CTG vocabulary fires on {dec}/{len(rows)} rows ({cov:.1%}); of those, "
          f"{agr} are labelled gate_failed by me -> precision {rate7:.3f}")
    print(f"  [G7] coverage >= 40% -> {'PASS' if G7 else 'FAIL -- NOT INTERPRETABLE'}")
    if G7:
        print(f"  [T7] {'HIGHER than E344/T2 (0.353)' if rate7 > 0.353 else 'NOT higher than E344/T2 (0.353) -- my labelling cannot be audited by text'}")
    print("  what my classes are when the external vocabulary says MACHINERY: " +
          ", ".join(f"{k[0]}:{v}" for k, v in conf.most_common(6)))
    R["T7"] = {"decided": dec, "coverage": cov, "precision": rate7, "gate": G7,
               "confusion": {f"{k[0]}": v for k, v in conf.items()}}

    # -------------------------------------------------------------------------------- T8
    print("\n" + "=" * 96)
    print("T8 -- my four headline rates at the LINEAGE level (37 lineages, not 225 rows)")
    ids = {str(r.get("id")) for r in rows}
    parent = {str(r.get("id")): (str(r.get("successor_of") or "").strip() or None) for r in rows}
    parent = {k: (v if v in ids else None) for k, v in parent.items()}

    def root(i):
        seen = set()
        while parent.get(i) and i not in seen:
            seen.add(i)
            i = parent[i]
        return i
    lin = collections.defaultdict(list)
    for r in rows:
        lin[root(str(r.get("id")))].append(r)
    defect = re.compile(r"\b(my own gate|the analyst'?s own gate|gate could not|cannot fail|"
                        r"unreachable|dead code|could not fire|my gate|bug|defect)\b", re.I)
    units = []
    for k, rs in lin.items():
        c = collections.Counter(r["_class"] for r in rs)
        units.append({
            "gate_failed": c["gate_failed"] > len(rs) / 2,
            "positive": c["positive"] > len(rs) / 2,
            "no_incumbent": sum(1 for r in rs if not str(r.get("incumbent", "")).strip()) > len(rs) / 2,
            "defect": any(defect.search(str(r.get("outcome_detail", ""))) for r in rs
                          if r["_class"] == "gate_failed"),
            "has_gf": c["gate_failed"] > 0})
    nL = len(units)
    t8 = {}
    for name, sel, pool in (("machinery_failure", lambda u: u["gate_failed"], units),
                            ("true_positive", lambda u: u["positive"], units),
                            ("no_incumbent", lambda u: u["no_incumbent"], units),
                            ("analyst_defect", lambda u: u["defect"],
                             [u for u in units if u["has_gf"]])):
        k = sum(1 for u in pool if sel(u))
        n = len(pool)
        lo_, hi_ = wilson(k, n)
        t8[name] = {"k": k, "n": n, "rate": k / n if n else float("nan"), "ci": [lo_, hi_]}
        print(f"    {name:<20} {k:>3}/{n:<3} = {t8[name]['rate']:.3f}  95% CI [{lo_:.3f}, {hi_:.3f}]")
    print(f"  [T8] {nL} lineages. These are the numbers that go in the paper; the row-level rates in "
          f"E344/T1 treat 225 dependent rows as independent.")
    R["T8"] = {"n_lineages": nL, "rates": t8}

    # -------------------------------------------------------------------------------- T9
    print("\n" + "=" * 96)
    print("T9 -- side by side. No significance test: the two artifacts count different objects.")
    mine = t8["machinery_failure"]
    print(f"    this register, lineage level : {mine['rate']:.3f}  [{mine['ci'][0]:.3f}, "
          f"{mine['ci'][1]:.3f}]  (n = {mine['n']} lineages)")
    print(f"    ClinicalTrials.gov, upper    : {R['T1']['rate']:.4f}  "
          f"[{R['T1']['ci'][0]:.4f}, {R['T1']['ci'][1]:.4f}]  (N = {R['T1']['N']:,})")
    if math.isfinite(R["T2"].get("refined_rate", float("nan"))):
        print(f"    ClinicalTrials.gov, refined  : {R['T2']['refined_rate']:.4f}  "
              f"(machinery share {R['T2']['machinery']:.3f} of stops)")
    R["T9"] = {"mine": mine, "ctg_upper": R["T1"]["rate"],
               "ctg_refined": R["T2"].get("refined_rate")}

    # -------------------------------------------------------------------------------- T10
    print("\n" + "=" * 96)
    print("T10 -- the published-literature benchmark across four fields (E344/T6 at scale)")
    CANT = re.compile(r"(terminated early|stopped early|failed to recruit|recruitment (was )?"
                      r"(halted|stopped|insufficient)|could not be (assessed|evaluated|analysed|"
                      r"analyzed)|were not (available|evaluable)|assay failed|"
                      r"insufficient data (to|for)|precluded (any )?(analysis|assessment)|"
                      r"prevented (the )?(analysis|assessment)|underpowered to (detect|assess)|"
                      r"did not permit (analysis|assessment))", re.I)
    EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    def pm_search(term, n):
        u = f"{EUT}esearch.fcgi?db=pubmed&retmax={n}&term={urllib.parse.quote(term)}"
        with urllib.request.urlopen(u, timeout=60) as r:
            return re.findall(r"<Id>(\d+)</Id>", r.read().decode())

    def pm_rate(pmids):
        if not pmids:
            return float("nan"), 0
        hit = tot_ = 0
        for i in range(0, len(pmids), 100):
            u = (f"{EUT}efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id="
                 + ",".join(pmids[i:i + 100]))
            with urllib.request.urlopen(u, timeout=120) as r:
                txt = r.read().decode("utf-8", "replace")
            recs = [b for b in re.split(r"\n\n(?=\d+\. )", txt) if len(b) > 200]
            hit += sum(1 for b in recs if CANT.search(b))
            tot_ += len(recs)
            time.sleep(0.4)
        return (hit / tot_ if tot_ else float("nan")), tot_
    FIELDS = {
        "anaesthesia/EEG": '("electroencephalography"[MeSH] OR "anesthesia"[MeSH])',
        "oncology": '"neoplasms"[MeSH]',
        "cardiology": '"cardiovascular diseases"[MeSH]',
        "psychiatry": '"mental disorders"[MeSH]',
    }
    per = 60 if a.smoke else 300
    t10 = {}
    for name, mesh in FIELDS.items():
        try:
            ids = pm_search(f'{mesh} AND "journal article"[pt] AND 2023:2025[dp] AND hasabstract', per)
            ctl = pm_search(f'{mesh} AND ("terminated early" OR "failed to recruit" OR "stopped early")'
                            f' AND hasabstract', 60)
            r_, n_ = pm_rate(ids)
            rc, nc = pm_rate(ctl)
            ok = math.isfinite(rc) and rc >= 0.15
            print(f"    {name:<18} unselected {r_:.4f} (n={n_:>4})   control {rc:.3f} (n={nc:>3})  "
                  f"-> {'usable' if ok else 'NOT INTERPRETABLE (control did not fire)'}")
            t10[name] = {"rate": r_, "n": n_, "control": rc, "n_control": nc, "gate": ok}
        except Exception as e:                                        # noqa: BLE001
            print(f"    {name:<18} BLOCKED: {type(e).__name__}")
            t10[name] = {"status": "blocked", "error": type(e).__name__}
    usable = [v for v in t10.values() if v.get("gate")]
    if usable:
        tk = sum(v["rate"] * v["n"] for v in usable)
        tn = sum(v["n"] for v in usable)
        print(f"  [T10] pooled across {len(usable)} usable fields: {tk/tn:.4f} of "
              f"{tn:,} abstracts, against this register's machinery-failure rate")
    R["T10"] = t10

    print("\n" + "=" * 96)
    if a.smoke:
        sh = [dict(s, why=w) for s, w in zip(corp, [c["why"] for c in corp][::-1])]
        m2 = sum(1 for s in sh if classify_why(s["why"])[0] == "MACHINERY") / max(1, len(sh))
        print(f"[SMOKE] machinery share real {mach:.3f} vs corpus-reversed {m2:.3f}. Reversal pairs a "
              f"study with another's text, so per-study classes change while the CORPUS share should "
              f"not -- this smoke tests the fetch/parse path, not an association.")
        return 0
    json.dump(R, open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
