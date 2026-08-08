#!/usr/bin/env python3
"""E344 -- a ten-test battery on the pre-registration register and on the dissociation criterion.

PRE-REGISTRATION. Committed before any statistic in it exists. Ten numbered tests, each with its own
primary, its own prediction, its own gates and its own verdict branch (rule 97: one gate per claim it can
invalidate). A test that fails its gate reports NOT INTERPRETABLE and does not contaminate the others.

WHY THESE TEN. E330/E331 measured this project's own register -- 24.0 % of designs died on machinery
before testing anything, a 31.6 % true-positive rate against the 100 % a positives-only literature
implies, 29.6 % of machinery failures being the analyst's own gate, 64.0 % naming no incumbent. Those are
the strongest numbers this programme has that are not limited by any cohort. **They are also reported
without a single interval, without an independence check, and without an external benchmark**, and each
of those is the first thing a referee will ask for. T1-T7 and T10 supply them, including the answers that
would damage the claim. T8 and T9 turn the same scepticism on the dissociation criterion E321/E342 use.

------------------------------------------------------------------------------------------------------
T1  UNCERTAINTY ON THE HEADLINE RATES.
    Primary: bootstrap 95 % intervals for machinery-failure, true-positive, analyst-defect and
    no-incumbent rates, at TWO levels -- resampling registrations, and resampling CHALLENGES (rule 69:
    registrations inside a challenge share a cohort, a deposit and a design lineage, so they are not
    independent units).
    PREDICTION: the challenge-level intervals are materially wider than the registration-level ones.
    WRONG IF they are comparable, which would mean challenge membership carries no clustering and the
    simpler interval is honest.

T2  INDEPENDENT RE-CLASSIFICATION (rule 23 -- validate against an independent implementation).
    E330's classes come from the `outcome` field, which is analyst-assigned. Primary: re-derive each
    row's class from `outcome_detail` ALONE with a keyword classifier that never reads `outcome`, and
    report agreement.
    PREDICTION: agreement is high (>= 0.75) on the rows the classifier can decide.
    WRONG IF agreement is low -- then E330's rates rest on an unaudited labelling and must be reported
    with that caveat foremost. **Named first because it is the outcome that costs the most.**
    G2a: the classifier must decide a non-trivial share of rows (>= 50 %), else it is measuring its own
    abstention. G2b (rule 40): planted texts of each class must be classified correctly.

T3  LINEAGE NON-INDEPENDENCE -- how many independent questions does the register actually contain?
    Primary: the number of lineage roots under `successor_of`, and the size distribution of lineages.
    PREDICTION: substantially fewer roots than rows, so the effective n is well below 225.
    This is reported as a LIMIT on every rate in T1, not as a finding in itself.

T4  IS THE MACHINERY-FAILURE RATE A PROPERTY OF THE FORMAT RATHER THAN OF THE SCIENCE?
    Primary: P(gate_failed) as a function of how many gates a registration carries, with a permutation
    placebo that shuffles outcomes across registrations.
    PREDICTION: it RISES with gate count -- more gates, more chances to refuse.
    WRONG IF flat or falling; then gating is not mechanically buying refusals and 24.0 % is a statement
    about the designs. **Both directions are interesting and the verdict branch states each.**

T5  DOES NAMING AN INCUMBENT CHANGE THE OUTCOME DISTRIBUTION?
    Primary: P(positive | incumbent named) - P(positive | none), with a permutation null on the
    incumbent flag.
    PREDICTION: NEGATIVE -- naming a bar makes a positive harder. If it holds, the 31.6 % true-positive
    rate is itself inflated by the 64 % of registrations that named no bar, which SHARPENS the
    overstatement claim rather than weakening it.
    WRONG IF the difference is positive or null.

T6  THE EXTERNAL BENCHMARK -- how often does the published literature say a study could not test its
    hypothesis? Without this number, "24.0 % die on machinery" has nothing to be compared to.
    Primary: among a PubMed sample of research abstracts in matched fields, the fraction whose abstract
    states the study could not evaluate its primary question (recruitment failure, data unavailable,
    assay failure, insufficient power stated as a reason the question was not answered).
    PREDICTION: far below the register's rate -- low single digits.
    G6a NETWORK: if E-utilities is unreachable the test reports BLOCKED, never a number.
    G6b (rule 40): the classifier must fire on a positive-control query built to contain such statements
    and stay low on an unselected sample. Both printed. **A keyword classifier over abstracts measures
    what authors WROTE, not what happened**, and that gap is the point -- it is stated as the estimand,
    because the claim being tested is precisely that the literature does not report these events.

T7  HELD-OUT PROSPECTIVE CHECK. E330 was computed over the register as it stood. Rows registered after
    E330's own registration date are a held-out sample it could not have seen.
    Primary: the outcome distribution in the held-out rows against the rest.
    PREDICTION: comparable. WRONG IF the held-out rows differ, which would mean E330 described a period
    rather than a practice.
    G7: >= 25 held-out rows, else NOT INTERPRETABLE.

T8  IS THE DISSOCIATION CRITERION BIASED TOWARD NOISY MEASURES? -- the methodological test in this
    battery, and the one with reach beyond this project.
    E321/E342's criterion is (a) wake-N3 excludes zero, (b) REM-N3 excludes zero with the same sign,
    (c) drug-N3 does NOT exclude zero. Criterion (c) is an ACCEPTANCE of a null, so a measure too noisy
    to reject anything satisfies it for free. Primary: on synthetic measures built with a KNOWN drug
    response, P(classified as dissociating) as a function of measurement noise.
    PREDICTION: P(dissociates | truly HAS a drug response) rises with noise -- the criterion rewards
    imprecision. WRONG IF flat, which would mean (c) is safe as used and E321/E342 need no caveat.
    G8 (rule 40, both ways): a noiseless truly-dissociating measure must be classified as dissociating,
    and a noiseless measure with a drug response must not. Both printed before the sweep is read.

T9  HOW STABLE IS THE DISSOCIATING SET? E342 reported 6 of 17 measures dissociating. Primary: a
    patient-level bootstrap of E342's P2, reporting each measure's selection frequency.
    PREDICTION: the set is UNSTABLE -- most measures' selection frequency lies between 0.2 and 0.8, so
    "6 of 17" is a draw from a distribution and must be reported as one.
    WRONG IF frequencies are near 0 or 1, in which case membership is a stable property and E342's list
    can be quoted as a list.

T10 DOES THE MACHINERY-FAILURE RATE FALL AS THE PROGRAMME ACCUMULATES RULES?
    Primary: P(gate_failed) by registration date, early half against late half, with a permutation null.
    **This CANNOT be attributed to the catalogue**, because catalogue size and calendar time are
    perfectly collinear (E343's limitation 3). It is registered as a TIME trend and will be reported as
    one. PREDICTION: no improvement.

------------------------------------------------------------------------------------------------------
GATES COMMON TO THE BATTERY.
  G0  The register must parse, carry >= 200 rows, and its `outcome` field must be canonicalisable. Rows
      whose outcome is free text rather than the enum are COUNTED AND REPORTED, never silently dropped
      (rule 14), and the count is itself a finding about whether the format was enforced.
  GS  SMOKE: under `--smoke` every outcome label is permuted across registrations. Every test that
      claims an association must weaken. The file prints the before/after for T4, T5 and T10.

SCOPE. One register, one analyst, one programme. T1-T5, T7 and T10 are descriptive statistics of that
artifact with honest intervals; they are not estimates of a population of laboratories. T6's comparison
is between what this register RECORDS and what published abstracts REPORT, which are different acts, and
the difference between them is the estimand rather than a confound.

    python -m bsde.experiments.e344_register_battery
"""
from __future__ import annotations

import argparse, collections, json, math, os, random, re, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
RESULTS = os.path.join(ROOT, "results")
LEDGER = os.path.join(ROOT, "governance", "REGISTRATION_LEDGER.jsonl")
KRAUSE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
REGISTERED_REPS = 5000
E330_DATE = "2026-08-07"          # E330's own registration date; rows after it are held out for T7

CANON = ("positive", "negative", "gate_failed", "absent", "withdrawn", "blocked", "closed", "mixed")


def canon(o):
    """Map a free-text outcome onto the enum. Returns (class, was_free_text)."""
    s = str(o or "").strip().lower()
    if s in CANON:
        return s, False
    for k in ("gate_failed", "withdrawn", "blocked", "closed", "mixed"):
        if s.startswith(k):
            return k, True
    if s.startswith("positive"):
        return "positive", True
    if s.startswith("negative") or s.startswith("not confirmed"):
        return "negative", True
    if s.startswith("confirmed"):
        return "positive", True
    if s.startswith("suggestive"):
        return "mixed", True
    return "unclassified", True


def boot_ci(vals, rng, reps, stat):
    if not vals:
        return (float("nan"), float("nan"), float("nan"))
    obs = stat(vals)
    draws = []
    n = len(vals)
    for _ in range(reps):
        draws.append(stat([vals[rng.randrange(n)] for _ in range(n)]))
    draws.sort()
    return obs, draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws))]


def frac(pred):
    return lambda xs: (sum(1 for x in xs if pred(x)) / len(xs)) if xs else float("nan")


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=REGISTERED_REPS)
    ap.add_argument("--seed", type=int, default=344)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e344_register_battery.json"))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-network", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    for r in rows:
        r["_class"], r["_freetext"] = canon(r.get("outcome"))
    n_free = sum(1 for r in rows if r["_freetext"])
    n_unc = sum(1 for r in rows if r["_class"] == "unclassified")
    G0 = len(rows) >= 200 and n_unc == 0
    print(f"[G0] {len(rows)} registrations; {n_free} carried FREE TEXT rather than the enum "
          f"({n_free/len(rows):.1%}); {n_unc} could not be canonicalised -> "
          f"{'PASS' if G0 else 'FAIL'}")
    print(f"     the free-text share is itself a finding: the format's outcome vocabulary was not "
          f"enforced by the tool that wrote these rows.")
    print(f"     classes: {collections.Counter(r['_class'] for r in rows).most_common()}")
    R["G0"] = {"n": len(rows), "free_text": n_free, "unclassified": n_unc, "pass": G0,
               "classes": dict(collections.Counter(r["_class"] for r in rows))}

    if a.smoke:
        labs = [r["_class"] for r in rows]
        rng.shuffle(labs)
        for r, l in zip(rows, labs):
            r["_class"] = l
        print("[SMOKE] outcome classes permuted across registrations")

    # ------------------------------------------------------------------------------------ T1
    print("\n" + "=" * 96)
    print("T1 -- uncertainty on the headline rates, at two levels of clustering")
    defect = re.compile(r"\b(my own gate|the analyst'?s own gate|gate could not|cannot fail|"
                        r"unreachable|dead code|could not fire|my gate|bug|defect)\b", re.I)
    stats = {
        "machinery_failure": frac(lambda r: r["_class"] == "gate_failed"),
        "true_positive": frac(lambda r: r["_class"] == "positive"),
        "no_incumbent": frac(lambda r: not str(r.get("incumbent", "")).strip()),
    }
    gf = [r for r in rows if r["_class"] == "gate_failed"]
    stats_gf = {"analyst_defect": frac(lambda r: bool(defect.search(str(r.get("outcome_detail", "")))))}
    by_ch = collections.defaultdict(list)
    for r in rows:
        by_ch[str(r.get("challenge", "?"))].append(r)
    chs = sorted(by_ch)
    t1 = {}
    print(f"  {'statistic':<20}{'point':>8}{'registration-level 95% CI':>30}{'challenge-level 95% CI':>28}")
    for name, st in list(stats.items()) + list(stats_gf.items()):
        pool = gf if name == "analyst_defect" else rows
        o, lo, hi = boot_ci(pool, rng, a.reps, st)

        def chstat(sel):
            flat = [x for c in sel for x in by_ch[c] if (x in gf or name != "analyst_defect")]
            return st(flat) if flat else float("nan")
        cd = []
        for _ in range(a.reps):
            sel = [chs[rng.randrange(len(chs))] for _ in range(len(chs))]
            v = chstat(sel)
            if math.isfinite(v):
                cd.append(v)
        cd.sort()
        clo, chi = (cd[int(0.025 * len(cd))], cd[int(0.975 * len(cd))]) if cd else (float("nan"),) * 2
        w1, w2 = hi - lo, chi - clo
        t1[name] = {"point": o, "reg_ci": [lo, hi], "chal_ci": [clo, chi],
                    "reg_width": w1, "chal_width": w2}
        print(f"  {name:<20}{o:>8.3f}   [{lo:.3f}, {hi:.3f}]  w={w1:.3f}      "
              f"[{clo:.3f}, {chi:.3f}]  w={w2:.3f}")
    wider = sum(1 for v in t1.values() if v["chal_width"] > v["reg_width"] * 1.3)
    print(f"  [T1] challenge-level interval >= 1.3x wider for {wider} of {len(t1)} statistics -> "
          f"{'PREDICTION MET' if wider >= 3 else 'PREDICTION NOT MET -- quote the simpler interval'}")
    R["T1"] = {"stats": t1, "n_wider": wider, "n_challenges": len(chs)}

    # ------------------------------------------------------------------------------------ T2
    print("\n" + "=" * 96)
    print("T2 -- independent re-classification from outcome_detail alone (rule 23)")
    PAT = [("gate_failed", re.compile(r"gate (failed|refused)|not interpretable|never tested|"
                                      r"could not be interpreted|refused the run", re.I)),
           ("withdrawn", re.compile(r"withdraw|retract|overturn", re.I)),
           ("blocked", re.compile(r"\bblocked\b|no access|credential|could not run|unavailable", re.I)),
           ("absent", re.compile(r"\babsent\b|found nothing|no effect|at chance|null result", re.I)),
           ("negative", re.compile(r"refut|\bnegative\b|did not hold|fails|prediction not met|"
                                   r"does not support", re.I)),
           ("positive", re.compile(r"\bconfirm|\bpositive\b|prediction (met|held)|supported|"
                                   r"survives|holds", re.I))]

    def indep(txt):
        for cls, pat in PAT:
            if pat.search(txt or ""):
                return cls
        return None
    dec, agr = 0, 0
    conf = collections.Counter()
    for r in rows:
        g = indep(str(r.get("outcome_detail", "")))
        if g is None:
            continue
        dec += 1
        agr += (g == r["_class"])
        conf[(r["_class"], g)] += 1
    plant = {"gate_failed": "G2 failed and the gate refused the run, so it is NOT INTERPRETABLE.",
             "positive": "the registered prediction was met and the effect survives.",
             "negative": "the hypothesis is refuted; the prediction did not hold.",
             "blocked": "could not run: no access, credentials unavailable."}
    ok_plant = all(indep(v) == k for k, v in plant.items())
    for k, v in plant.items():
        print(f"    plant[{k:<12}] -> {indep(v)}")
    covered = dec / len(rows) if rows else 0.0
    rate = agr / dec if dec else float("nan")
    G2 = bool(ok_plant and covered >= 0.50)
    print(f"  decided {dec}/{len(rows)} rows ({covered:.1%}); agreement with the analyst-assigned "
          f"field = {rate:.3f}")
    print(f"  [G2] planted texts classified correctly = {ok_plant}; coverage >= 50% = "
          f"{covered >= 0.50} -> {'PASS' if G2 else 'FAIL'}")
    if not G2:
        print("  [T2] NOT INTERPRETABLE")
    else:
        print(f"  [T2] {'PREDICTION MET' if rate >= 0.75 else 'PREDICTION NOT MET -- E330 rests on an unaudited labelling'}")
    print("  most common disagreements: " +
          ", ".join(f"{k[0]}->{k[1]}:{v}" for k, v in conf.most_common(6) if k[0] != k[1]))
    R["T2"] = {"decided": dec, "coverage": covered, "agreement": rate, "gate": G2,
               "plants_ok": ok_plant,
               "confusion": {f"{k[0]}->{k[1]}": v for k, v in conf.items()}}

    # ------------------------------------------------------------------------------------ T3
    print("\n" + "=" * 96)
    print("T3 -- lineage: how many independent questions does the register contain?")
    parent = {}
    ids = {str(r.get("id")) for r in rows}
    for r in rows:
        p = str(r.get("successor_of") or "").strip()
        parent[str(r.get("id"))] = p if p and p in ids else None

    def root(i, seen=None):
        seen = seen or set()
        while parent.get(i) and i not in seen:
            seen.add(i)
            i = parent[i]
        return i
    roots = collections.Counter(root(str(r.get("id"))) for r in rows)
    sizes = sorted(roots.values(), reverse=True)
    print(f"  {len(rows)} rows resolve to {len(roots)} lineage roots")
    print(f"  largest lineages: {sizes[:8]}; singletons: {sum(1 for s in sizes if s == 1)}")
    print(f"  effective n if a lineage is one question: {len(roots)} "
          f"({len(roots)/len(rows):.1%} of the row count)")
    print("  [T3] this is a LIMIT on every rate above, not a result on its own.")
    R["T3"] = {"n_rows": len(rows), "n_roots": len(roots), "sizes": sizes[:20],
               "singletons": sum(1 for s in sizes if s == 1)}

    # ------------------------------------------------------------------------------------ T4
    print("\n" + "=" * 96)
    print("T4 -- does P(gate_failed) rise with how many gates a design carries?")

    def slope_by_gates(rs):
        xs = [len(r.get("gates", []) or []) for r in rs]
        ys = [1.0 if r["_class"] == "gate_failed" else 0.0 for r in rs]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        return (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx) if sxx > 0 else float("nan")
    obs4 = slope_by_gates(rows)
    tab = collections.defaultdict(list)
    for r in rows:
        tab[len(r.get("gates", []) or [])].append(r["_class"] == "gate_failed")
    for k in sorted(tab):
        v = tab[k]
        print(f"    {k} gates: n={len(v):>3}  P(gate_failed) = {sum(v)/len(v):.3f}")
    null4 = []
    labs = [r["_class"] for r in rows]
    for _ in range(a.reps):
        sh = labs[:]
        rng.shuffle(sh)
        tmp = [dict(r, _class=l) for r, l in zip(rows, sh)]
        v = slope_by_gates(tmp)
        if math.isfinite(v):
            null4.append(v)
    null4.sort()
    p4hi = sum(1 for v in null4 if v >= obs4) / len(null4) if null4 else float("nan")
    print(f"  slope = {obs4:+.4f} per gate; permutation null 95th = "
          f"{null4[int(0.95*len(null4))]:+.4f}; p(one-sided, rising) = {p4hi:.4f}")
    v4 = ("RISES -- the machinery-failure rate is partly a property of the format" if p4hi < 0.05 else
          "FALLS -- heavily gated designs fail LESS, so gating tracks care, not refusals"
          if p4hi > 0.95 else "FLAT -- gate count does not buy refusals")
    print(f"  [T4] {v4}")
    R["T4"] = {"slope": obs4, "p_rising": p4hi, "verdict": v4,
               "by_gate_count": {str(k): [len(v), sum(v)] for k, v in sorted(tab.items())}}

    # ------------------------------------------------------------------------------------ T5
    print("\n" + "=" * 96)
    print("T5 -- does naming an incumbent change P(positive)?")
    has = [r for r in rows if str(r.get("incumbent", "")).strip()]
    non = [r for r in rows if not str(r.get("incumbent", "")).strip()]
    ph = sum(1 for r in has if r["_class"] == "positive") / len(has) if has else float("nan")
    pn = sum(1 for r in non if r["_class"] == "positive") / len(non) if non else float("nan")
    d5 = ph - pn
    flags = [bool(str(r.get("incumbent", "")).strip()) for r in rows]
    cls = [r["_class"] for r in rows]
    null5 = []
    for _ in range(a.reps):
        sh = flags[:]
        rng.shuffle(sh)
        h = [c for c, f in zip(cls, sh) if f]
        nn = [c for c, f in zip(cls, sh) if not f]
        if h and nn:
            null5.append(sum(1 for c in h if c == "positive") / len(h)
                         - sum(1 for c in nn if c == "positive") / len(nn))
    null5.sort()
    p5 = sum(1 for v in null5 if abs(v) >= abs(d5)) / len(null5) if null5 else float("nan")
    print(f"  incumbent named  n={len(has):>3}  P(positive) = {ph:.3f}")
    print(f"  none named       n={len(non):>3}  P(positive) = {pn:.3f}")
    print(f"  difference = {d5:+.4f}; two-sided permutation p = {p5:.4f}")
    v5 = ("NEGATIVE as predicted -- naming a bar makes a positive harder, so the true-positive rate is "
          "inflated by the registrations that named none" if (d5 < 0 and p5 < 0.05) else
          "POSITIVE -- against prediction; naming an incumbent goes with MORE positives"
          if (d5 > 0 and p5 < 0.05) else "NULL -- the incumbent field does not move the outcome")
    print(f"  [T5] {v5}")
    R["T5"] = {"p_positive_incumbent": ph, "p_positive_none": pn, "diff": d5, "p": p5,
               "n": [len(has), len(non)], "verdict": v5}

    # ------------------------------------------------------------------------------------ T6
    print("\n" + "=" * 96)
    print("T6 -- external benchmark: how often does a published abstract say the study could not")
    print("      evaluate its question? Estimand is what authors WROTE, not what happened.")
    CANT = re.compile(r"(terminated early|stopped early|failed to recruit|recruitment (was )?"
                      r"(halted|stopped|insufficient)|could not be (assessed|evaluated|analysed|"
                      r"analyzed)|were not (available|evaluable)|assay failed|"
                      r"insufficient data (to|for)|precluded (any )?(analysis|assessment)|"
                      r"prevented (the )?(analysis|assessment)|underpowered to (detect|assess)|"
                      r"did not permit (analysis|assessment))", re.I)

    def esearch(term, n=120):
        u = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax=%d&term=%s"
             % (n, urllib.request.quote(term)))
        return re.findall(r"<Id>(\d+)</Id>", urllib.request.urlopen(u, timeout=40).read().decode())

    def efetch(pmids):
        u = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=abstract&"
             "retmode=text&id=" + ",".join(pmids))
        return urllib.request.urlopen(u, timeout=90).read().decode("utf-8", "replace")
    t6 = {"status": "not run"}
    if a.no_network:
        print("  BLOCKED by --no-network")
        t6 = {"status": "blocked"}
    else:
        try:
            neu = esearch('("electroencephalography"[MeSH] OR "anesthesia"[MeSH]) AND '
                          '"journal article"[pt] AND 2023:2025[dp] AND hasabstract', 120)
            pos = esearch('("terminated early" OR "failed to recruit" OR "stopped early") AND '
                          '"journal article"[pt] AND hasabstract', 60)
            print(f"  fetched {len(neu)} unselected and {len(pos)} positive-control records")

            def rate(pmids, label):
                if not pmids:
                    return float("nan"), 0
                txt = efetch(pmids)
                recs = [b for b in re.split(r"\n\n(?=\d+\. )", txt) if len(b) > 200]
                hit = sum(1 for b in recs if CANT.search(b))
                print(f"    {label}: {hit}/{len(recs)} = {hit/len(recs) if recs else float('nan'):.3f}")
                return (hit / len(recs) if recs else float("nan")), len(recs)
            rp, np_ = rate(pos, "positive control")
            rn, nn_ = rate(neu, "unselected sample ")
            G6 = math.isfinite(rp) and math.isfinite(rn) and rp > rn and rp >= 0.20
            print(f"  [G6b] control fires ({rp:.3f}) above the unselected rate ({rn:.3f}) and clears "
                  f"0.20 -> {'PASS' if G6 else 'FAIL'}")
            if G6:
                print(f"  [T6] published abstracts stating the question could not be evaluated: "
                      f"{rn:.1%}, against this register's machinery-failure rate of "
                      f"{R['T1']['stats']['machinery_failure']['point']:.1%}")
            else:
                print("  [T6] NOT INTERPRETABLE -- the classifier was not shown able to detect the "
                      "statement it is counting")
            t6 = {"status": "ok", "unselected_rate": rn, "n_unselected": nn_,
                  "control_rate": rp, "n_control": np_, "gate": G6}
        except Exception as e:                                    # noqa: BLE001
            print(f"  BLOCKED: {type(e).__name__}: {e}")
            t6 = {"status": "blocked", "error": f"{type(e).__name__}: {e}"}
    R["T6"] = t6

    # ------------------------------------------------------------------------------------ T7
    print("\n" + "=" * 96)
    print("T7 -- held-out prospective check against rows E330 could not have seen")
    held = [r for r in rows if str(r.get("registered_date", "")) > E330_DATE]
    seen = [r for r in rows if str(r.get("registered_date", "")) and
            str(r.get("registered_date", "")) <= E330_DATE]
    G7 = len(held) >= 25
    print(f"  held out (registered after {E330_DATE}): {len(held)}; earlier and dated: {len(seen)}")
    if not G7:
        print(f"  [G7] FAIL -- fewer than 25 held-out rows. NOT INTERPRETABLE, and that is the "
              f"honest outcome: this register has no prospective sample yet.")
        R["T7"] = {"gate": False, "n_held": len(held), "n_seen": len(seen)}
    else:
        a7 = collections.Counter(r["_class"] for r in held)
        b7 = collections.Counter(r["_class"] for r in seen)
        print(f"    held out: {dict(a7)}")
        print(f"    earlier : {dict(b7)}")
        gh = a7["gate_failed"] / len(held)
        gs = b7["gate_failed"] / len(seen)
        print(f"  P(gate_failed): held-out {gh:.3f} vs earlier {gs:.3f}, diff {gh-gs:+.3f}")
        R["T7"] = {"gate": True, "n_held": len(held), "n_seen": len(seen),
                   "held": dict(a7), "seen": dict(b7), "diff_gate_failed": gh - gs}

    # ------------------------------------------------------------------------------------ T8
    print("\n" + "=" * 96)
    print("T8 -- is the dissociation criterion biased toward NOISY measures?")
    print("     Criterion (c) ACCEPTS a null, so a measure too imprecise to reject anything passes free.")
    NP, REPS8 = 18, 400

    def synth_trial(noise, drug_effect, arousal=1.0, rem=1.0):
        """One synthetic measure over NP patients: wake, REM, N3 and drug blocks."""
        d1 = [arousal + rng.gauss(0, noise) for _ in range(NP)]
        d2 = [rem + rng.gauss(0, noise) for _ in range(NP)]
        d3 = [drug_effect + rng.gauss(0, noise) for _ in range(NP)]

        def sf(d):
            o = med(d)
            hits = sum(1 for _ in range(200)
                       if abs(med([x if rng.random() < 0.5 else -x for x in d])) >= abs(o))
            return o, hits / 200
        o1, p1 = sf(d1)
        o2, p2 = sf(d2)
        o3, p3 = sf(d3)
        return (p1 < 0.05) and (p2 < 0.05 and o1 * o2 > 0) and (p3 >= 0.05)
    ok_pos = sum(synth_trial(0.15, 0.0) for _ in range(60)) / 60
    ok_neg = sum(synth_trial(0.15, 1.0) for _ in range(60)) / 60
    G8 = ok_pos >= 0.80 and ok_neg <= 0.20
    print(f"  [G8] noiseless-ish capability: truly dissociating classified as dissociating "
          f"{ok_pos:.2f} (need >= 0.80); truly drug-responsive classified as dissociating "
          f"{ok_neg:.2f} (need <= 0.20) -> {'PASS' if G8 else 'FAIL'}")
    sweep = {}
    for noise in (0.15, 0.3, 0.5, 0.8, 1.2, 2.0, 3.0):
        f_false = sum(synth_trial(noise, 1.0) for _ in range(REPS8)) / REPS8
        f_true = sum(synth_trial(noise, 0.0) for _ in range(REPS8)) / REPS8
        sweep[noise] = (f_false, f_true)
        print(f"    noise {noise:>4.2f}:  P(dissociates | HAS a drug response) = {f_false:.3f}   "
              f"P(dissociates | truly dissociating) = {f_true:.3f}")
    if not G8:
        v8 = "NOT INTERPRETABLE -- the criterion was not shown to work in the easy case"
    else:
        lo, hi = sweep[0.15][0], max(sweep[n][0] for n in sweep)
        v8 = (f"BIASED -- the false-dissociation rate rises from {lo:.3f} to {hi:.3f} as noise grows, "
              f"so criterion (c) rewards imprecision" if hi > lo + 0.10 else
              "NOT BIASED -- the false-dissociation rate does not rise with noise")
    print(f"  [T8] {v8}")
    R["T8"] = {"gate": G8, "capability": [ok_pos, ok_neg],
               "sweep": {str(k): v for k, v in sweep.items()}, "verdict": v8}

    # ------------------------------------------------------------------------------------ T9
    print("\n" + "=" * 96)
    print("T9 -- how stable is E342's dissociating set under a patient-level bootstrap?")
    try:
        from bsde.experiments.e342_reducibility2 import (
            SKIP as S2, SLEEP as SL2, DRUG_U as DU2, ALL_STATES as AS2, WAKE as W2, REM as RM2,
            DEEP as DP2, f as f2, med as m2, iqr as i2, criteria as crit2)
        import csv as _csv
        rr = list(_csv.DictReader(open(KRAUSE)))
        cols2 = [c for c in rr[0] if c not in S2]
        by2 = {}
        for r in rr:
            by2.setdefault((r["patientID"], r["label"]), []).append(r)
        pats2 = sorted({p for p, l in by2 if l == W2} & {p for p, l in by2 if l == RM2}
                       & {p for p, l in by2 if l == DP2})
        Z2 = {}
        for p in pats2:
            blocks = {st: by2.get((p, st), []) for st in AS2 if (p, st) in by2}
            for c in cols2:
                raw = {st: [f2(x.get(c)) for x in rs] for st, rs in blocks.items()}
                pool = [v for st in SL2 for v in raw.get(st, []) if math.isfinite(v)]
                m0, s0 = m2(pool), i2(pool)
                if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                    continue
                Z2[(p, c)] = {st: (m2(v) - m0) / s0 for st, v in raw.items() if m2(v) == m2(v)}
        B9 = 300
        sel = collections.Counter()
        for _ in range(B9):
            samp = [pats2[rng.randrange(len(pats2))] for _ in range(len(pats2))]
            # de-duplicate keys by suffixing, so a patient drawn twice contributes twice
            Zb, pb = {}, []
            for k, p in enumerate(samp):
                tag = f"{p}#{k}"
                pb.append(tag)
                for c in cols2:
                    if (p, c) in Z2:
                        Zb[(tag, c)] = Z2[(p, c)]
            for c in cols2:
                if crit2(Zb, c, pb, rng, 200)["dissociates"]:
                    sel[c] += 1
        print(f"  {B9} patient-level bootstrap resamples of {len(pats2)} patients")
        real = {"NmlzCmplx", "EffDim", "allEnvCorr", "AvgGamma", "parietalDelta", "frontwPLI"}
        for c in sorted(cols2, key=lambda x: -sel[x]):
            mark = "  <- in E342's set" if c in real else ""
            print(f"    {c:<20} selected in {sel[c]/B9:.3f} of resamples{mark}")
        mid = [c for c in cols2 if 0.2 <= sel[c] / B9 <= 0.8]
        v9 = (f"UNSTABLE -- {len(mid)} of {len(cols2)} measures have a selection frequency between "
              f"0.2 and 0.8, so 'six of seventeen dissociate' is one draw from a distribution"
              if len(mid) >= len(cols2) / 3 else
              f"STABLE -- only {len(mid)} of {len(cols2)} measures are near the boundary; the set can "
              f"be quoted as a set")
        print(f"  [T9] {v9}")
        R["T9"] = {"n_boot": B9, "n_patients": len(pats2), "verdict": v9,
                   "selection_frequency": {c: sel[c] / B9 for c in cols2}}
    except Exception as e:                                        # noqa: BLE001
        print(f"  BLOCKED: {type(e).__name__}: {e}")
        R["T9"] = {"status": "blocked", "error": f"{type(e).__name__}: {e}"}

    # ------------------------------------------------------------------------------------ T10
    print("\n" + "=" * 96)
    print("T10 -- does P(gate_failed) fall over calendar time? (NOT attributable to the catalogue)")
    dated = sorted((r for r in rows if str(r.get("registered_date", "")).strip()),
                   key=lambda r: r["registered_date"])
    if len(dated) < 60:
        print(f"  NOT INTERPRETABLE -- only {len(dated)} dated rows")
        R["T10"] = {"gate": False, "n_dated": len(dated)}
    else:
        h = len(dated) // 2
        e_, l_ = dated[:h], dated[h:]
        pe = sum(1 for r in e_ if r["_class"] == "gate_failed") / len(e_)
        pl = sum(1 for r in l_ if r["_class"] == "gate_failed") / len(l_)
        cl = [r["_class"] for r in dated]
        nl = []
        for _ in range(a.reps):
            sh = cl[:]
            rng.shuffle(sh)
            nl.append(sum(1 for c in sh[h:] if c == "gate_failed") / len(l_)
                      - sum(1 for c in sh[:h] if c == "gate_failed") / len(e_))
        nl.sort()
        d10 = pl - pe
        p10 = sum(1 for v in nl if abs(v) >= abs(d10)) / len(nl)
        print(f"  early half ({e_[0]['registered_date']}..{e_[-1]['registered_date']}, n={len(e_)}): "
              f"P(gate_failed) = {pe:.3f}")
        print(f"  late  half ({l_[0]['registered_date']}..{l_[-1]['registered_date']}, n={len(l_)}): "
              f"P(gate_failed) = {pl:.3f}")
        print(f"  difference {d10:+.4f}, two-sided permutation p = {p10:.4f}")
        v10 = ("IMPROVED over time" if (d10 < 0 and p10 < 0.05) else
               "WORSENED over time" if (d10 > 0 and p10 < 0.05) else
               "NO CHANGE -- the machinery-failure rate is flat across the programme")
        print(f"  [T10] {v10}. This is a TIME trend. Catalogue size and time are collinear, so it "
              f"cannot be attributed to the catalogue (E343 limitation 3).")
        R["T10"] = {"gate": True, "early": pe, "late": pl, "diff": d10, "p": p10, "verdict": v10,
                    "span": [e_[0]["registered_date"], l_[-1]["registered_date"]]}

    print("\n" + "=" * 96)
    if a.smoke:
        print("[SMOKE] T4 slope, T5 difference and T10 difference must all weaken against the real run.")
        print(f"  T4 slope {R['T4']['slope']:+.4f} | T5 diff {R['T5']['diff']:+.4f} | "
              f"T10 diff {R.get('T10', {}).get('diff', float('nan')):+.4f}")
        return 0
    if a.reps != REGISTERED_REPS:
        print(f"NOT WRITING {a.out}: --reps {a.reps} != registered {REGISTERED_REPS} (rule 100).")
        return 0
    json.dump(R, open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
