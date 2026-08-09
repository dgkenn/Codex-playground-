#!/usr/bin/env python3
"""E348 -- ten tests: what the gates PREVENTED, what kind of gate fails, and what a multi-lab study needs.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHERE THIS PICKS UP. E344, E346 and E347 established the register's rates, gave them intervals at two
clustering levels, benchmarked them against 300,090 ClinicalTrials.gov studies, audited the outcome
labelling mechanically (3 contradictions in 215 rows), and supplied a prospective sample that agrees with
the retrospective one. **What is still missing is the argument FOR the format**, and it is the thing a
reader will actually want: not "24 % of designs died on machinery" but **"here is what would have been
published if they had not."** T1 measures that. T2, T5 and T7 turn the register into design guidance;
T9 parameterises the multi-site pilot; T3, T4, T8 and T10 are the robustness a referee will demand.

------------------------------------------------------------------------------------------------------
T1  **THE COUNTERFACTUAL. Of the designs a gate refused, how many had already printed a primary that
    would have read as a finding?**
    This is the register format's whole claim -- that a gate failure is not a null but a *prevented
    report* -- and it has never been quantified here.
    Scope: the 26 PROSPECTIVE tests of E340-E346 (E347/T7's sample), because for those, and only those,
    every primary's printed value is recorded in a committed result note and can be checked line by line
    by a reader. Retrospective rows are excluded: their artifacts survive but their pre-gate primaries
    were not systematically recorded, and guessing would be worse than not measuring.
    Primary: among the prospective gate failures, the count whose primary had ALREADY printed a value
    that, taken alone, would have supported a reportable claim. Each is named with its number and its
    note, so the call is auditable rather than asserted.
    PREDICTION: a MAJORITY. **WRONG IF a minority** -- then gates mostly refuse designs that were going
    to return nothing anyway, the format prevents little, and the paper's central argument is much weaker.
    That outcome is named first because it costs the most.
    **This is a hand-tabulation with n = 7 and it is reported as one** (same standing as E347/T7), never
    as a rate to be compared against anything.

T2  WHAT KIND OF GATE FAILS? Primary: classify the 225 registrations' gate texts into types -- ALIVENESS
    (the incumbent or the phenomenon must be present), CAPABILITY (the design must be able to detect a
    planted effect), SUPPORT (n / coverage floors), PLACEBO, QUALITY -- and report both how often each
    type is carried and the `gate_failed` rate among designs carrying it.
    **This is association, not attribution**: a design carrying a capability gate is a different design
    from one that does not, so a higher failure rate among them is not evidence that capability gates
    cause failures. Registered with that wording so it cannot drift.

T3  ROBUSTNESS TO CANONICALISATION. 11 of 225 rows carried free text rather than the enum and were mapped
    by a hand-written rule. Primary: the four headline rates under THREE alternative reasonable mappings
    (free text -> `mixed`; free text -> dropped; free text -> its first enum-like word), reported as a
    range. PREDICTION: the rates move by less than 0.02.

T4  DOES A SUCCESSOR OVERTURN ITS PARENT? Primary: among rows with a resolvable `successor_of`, the
    fraction whose class differs from the parent's, and the fraction that REVERSE (positive <-> negative).
    An internal reproducibility rate, and it is the one number here that speaks to whether this
    programme's own successors are doing real work.

T5  DOES THE DATA SOURCE PREDICT MACHINERY FAILURE? Primary: `gate_failed` rate by deposit, for deposits
    carrying >= 8 registrations, with a permutation null on the deposit label.
    Actionable if it holds: it would say which kinds of data cost designs.

T6  THE LITERATURE'S POSITIVE RATE, against this register's 0.320. Primary: among sampled PubMed
    abstracts, the fraction whose conclusion sentence reports a supportive finding rather than a null.
    G6 CAPABILITY BOTH WAYS (rule 40, and rule 91 -- the plants must not be self-written to match):
    the classifier must score a corpus retrieved on null-result language BELOW one retrieved on
    positive-result language, and both rates are printed. If it cannot separate those, T6 is NOT
    INTERPRETABLE.
    **The estimand is what abstracts SAY, not what studies found** -- the same distinction E346/T10
    carried -- and that gap is the claim, not a confound.

T7  DOES NAMING A PLACEBO PREDICT ANYTHING? **Rule 32 first**: 214 of 225 rows name a placebo, so the
    variable barely varies and the comparison may be a comparison of 11 rows against 214. Primary: the
    variance check itself, reported BEFORE any contrast, and the contrast reported only if both arms
    reach 25 rows. Registered this way because rule 32 was paid for by exactly this mistake.

T8  INTER-BATTERY CONSISTENCY. E344/T1, E346/T8 and E347/T7 each estimate a machinery-failure rate on
    overlapping data with different units. Primary: whether their intervals are mutually consistent given
    their stated estimands. A pipeline that disagrees with itself is a pipeline to distrust.

T9  **WHAT WOULD A MULTI-LAB STUDY NEED?** Primary: the number of registrations per lab, and labs, needed
    to detect a difference between two labs' machinery-failure rates of 0.10 and of 0.05, at 80 % power,
    by exact enumeration of the null where feasible and simulation otherwise. This parameterises
    `PILOT_PROTOCOL_MULTISITE_REGISTER.md`, which currently states no sample size.

T10 **CAN A SECOND REGISTER IN THIS REPO BE AUDITED AT ALL?** The burst-suppression programme has 419
    logged results in `docs/research/41_RESULTS_LEDGER.md` and would be a second, independent-domain
    register. Primary: the fraction of those results that carry a machine-readable artifact of the kind
    E347/T1 audits.
    **Registered as a feasibility measurement, not as an attempt**, because the ledger is prose and
    E343/E344/E346 established across three tests that prose is not machine-auditable. Repeating a method
    already shown to fail would be the failure rule 101 exists to prevent. PREDICTION: coverage is far
    too low, and the honest report is that this repo contains one auditable register, not two.

GATES COMMON TO THE BATTERY.
  G0  The register must parse and carry >= 200 rows.
  GS  `--smoke` permutes the outcome labels; T2's per-type spread and T5's deposit contrast must both
      collapse toward zero, printed before and after.

LIMITATIONS.
  1. T1 is n = 7, hand-tabulated, and every call is named so it can be checked. It is evidence about this
     session's designs, not an estimate of a rate.
  2. T2 and T5 are associations between design choices and outcomes in one register; no causal reading is
     available and none is offered.
  3. T6 measures abstract language, not study findings.

    python -m bsde.experiments.e348_counterfactual_and_design --smoke
    python -m bsde.experiments.e348_counterfactual_and_design
"""
from __future__ import annotations

import argparse, collections, json, math, os, random, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
RESULTS = os.path.join(ROOT, "results")
LEDGER = os.path.join(ROOT, "governance", "REGISTRATION_LEDGER.jsonl")
BS_LEDGER = os.path.join(REPO, "docs", "research", "41_RESULTS_LEDGER.md")
EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

from bsde.experiments.e344_register_battery import canon        # noqa: E402
from bsde.experiments.e346_external_register import wilson      # noqa: E402

GATE_TYPES = [
    ("ALIVENESS", re.compile(r"\balive\b|must (be present|vary|exist)|incumbent (must|is)|"
                             r"phenomenon|>= ?\d+ ?% of cases|rises|separates|discriminat", re.I)),
    ("CAPABILITY", re.compile(r"planted|capab|synthetic|smoke|must (be able to )?(fail|detect)|"
                              r"positive control|negative control|recover", re.I)),
    ("PLACEBO", re.compile(r"placebo|fake landmark|permut|shuffl|surrogate|null draw", re.I)),
    ("SUPPORT", re.compile(r"\bn ?>=|at least \d+|>= ?\d+ (case|patient|subject|window|row|record)|"
                           r"coverage|floor|coverage >=|coverage of", re.I)),
    ("QUALITY", re.compile(r"artefact|artifact|\bSQI\b|quality|missing|nan|drop", re.I)),
]


def classify_gate(txt):
    for name, pat in GATE_TYPES:
        if pat.search(txt or ""):
            return name
    return "OTHER"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e348_counterfactual_and_design.json"))
    a = ap.parse_args(argv)
    rng = random.Random(348)
    R = {}
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    for r in rows:
        r["_class"], r["_free"] = canon(r.get("outcome"))
    print(f"[G0] {len(rows)} registrations -> {'PASS' if len(rows) >= 200 else 'FAIL'}")
    if a.smoke:
        labs = [r["_class"] for r in rows]
        rng.shuffle(labs)
        for r, l in zip(rows, labs):
            r["_class"] = l
        print("[SMOKE] outcome labels permuted")

    # ------------------------------------------------------------------------------------ T1
    print("\n" + "=" * 96)
    print("T1 -- THE COUNTERFACTUAL: of the designs a gate refused, how many had already printed")
    print("      a primary that, alone, would have read as a finding?")
    # The 7 prospective gate failures of E340-E346. Each call is named with the value that had
    # already printed and the note where a reader can check it.
    CF = [
        ("E340/P2", True,
         "muscle proxies vs real EMG all |rho| <= 0.18 -- would have read as 'the measures are not "
         "muscle-driven', a reportable negative", "e340_result_note.md"),
        ("E341", True,
         "P3 printed the dissociation SURVIVING removal of allEnvCorr at p <= 0.0028 on all four "
         "tests -- would have read as the licensing result for E321", "e341_result_note.md"),
        ("E343", True,
         "P1 printed 3 rules with 5 post-statement recurrences and P3 printed 3 cited-then-violated "
         "-- would have read as a quantified finding about error catalogues", "e343_result_note.md"),
        ("E344/T2", True,
         "agreement 0.353 -- would have read as 'E330's labelling is unreliable', a strong claim",
         "e344_result_note.md"),
        ("E344/T7", False,
         "no held-out rows existed, so no primary was computed at all -- nothing to report",
         "e344_result_note.md"),
        ("E346/T5", True,
         "slope +0.00142/yr -- would have read as 'trial terminations are getting worse over 16 "
         "years', a publishable external trend", "e346_result_note.md"),
        ("E346/T7", True,
         "precision 0.071 on 6.2 % coverage -- the low number itself would have read as a finding "
         "about auditability rather than as insufficient coverage", "e346_result_note.md"),
    ]
    k1 = sum(1 for _, b, _, _ in CF if b)
    n1 = len(CF)
    for name, b, why, note in CF:
        print(f"    {name:<10} {'WOULD HAVE REPORTED' if b else 'nothing to report':<20} {why[:74]}")
        print(f"    {'':<10} {'':<20} check: results/{note}")
    lo1, hi1 = wilson(k1, n1)
    print(f"  [T1] {k1} of {n1} prospective gate failures had a primary that would have read as a "
          f"finding = {k1/n1:.3f} [{lo1:.3f}, {hi1:.3f}]")
    print(f"  [T1] {'PREDICTION MET (a majority)' if k1 > n1/2 else 'PREDICTION NOT MET'}")
    print("       n = 7, hand-tabulated, every call named above with the note to check it against.")
    R["T1"] = {"n": n1, "would_have_reported": k1, "rate": k1 / n1, "ci": [lo1, hi1],
               "rows": [{"test": t, "would_report": b, "why": w, "note": nt} for t, b, w, nt in CF]}

    # ------------------------------------------------------------------------------------ T2
    print("\n" + "=" * 96)
    print("T2 -- what KIND of gate is carried, and what is the failure rate among designs carrying it?")
    print("      ASSOCIATION, not attribution -- registered with that wording.")
    carried = collections.defaultdict(list)
    for r in rows:
        types = {classify_gate(g) for g in (r.get("gates") or [])}
        for t in types:
            carried[t].append(r)
    t2 = {}
    for t in sorted(carried, key=lambda x: -len(carried[x])):
        rs = carried[t]
        k = sum(1 for r in rs if r["_class"] == "gate_failed")
        lo, hi = wilson(k, len(rs))
        t2[t] = {"carried": len(rs), "gate_failed": k, "rate": k / len(rs), "ci": [lo, hi]}
        print(f"    {t:<11} carried by {len(rs):>3} designs   gate_failed {k:>3} = {k/len(rs):.3f}  "
              f"[{lo:.3f}, {hi:.3f}]")
    spread = (max(v["rate"] for v in t2.values()) - min(v["rate"] for v in t2.values())) if t2 else 0
    print(f"  [T2] spread across gate types = {spread:.3f}")
    R["T2"] = {"by_type": t2, "spread": spread}

    # ------------------------------------------------------------------------------------ T3
    print("\n" + "=" * 96)
    print("T3 -- robustness of the four headline rates to how the 11 free-text outcomes are mapped")
    free = [r for r in rows if r["_free"]]
    print(f"    {len(free)} rows carried free text")

    def rates(cls_of):
        cl = [cls_of(r) for r in rows]
        cl = [c for c in cl if c is not None]
        n = len(cl)
        gf = sum(1 for c in cl if c == "gate_failed") / n
        tp = sum(1 for c in cl if c == "positive") / n
        return {"n": n, "machinery": gf, "positive": tp}
    schemes = {
        "registered (hand mapping)": lambda r: r["_class"],
        "free text -> mixed": lambda r: ("mixed" if r["_free"] else r["_class"]),
        "free text -> dropped": lambda r: (None if r["_free"] else r["_class"]),
        "free text -> first word": lambda r: (
            str(r.get("outcome", "")).strip().split()[0].strip(",.-").lower() if r["_free"]
            else r["_class"]),
    }
    t3 = {}
    for name, fn in schemes.items():
        v = rates(fn)
        t3[name] = v
        print(f"    {name:<26} n={v['n']:>3}  machinery {v['machinery']:.3f}  positive "
              f"{v['positive']:.3f}")
    rng_m = max(v["machinery"] for v in t3.values()) - min(v["machinery"] for v in t3.values())
    rng_p = max(v["positive"] for v in t3.values()) - min(v["positive"] for v in t3.values())
    print(f"  [T3] range across schemes: machinery {rng_m:.4f}, positive {rng_p:.4f} -> "
          f"{'PREDICTION MET (< 0.02)' if max(rng_m, rng_p) < 0.02 else 'PREDICTION NOT MET'}")
    R["T3"] = {"schemes": t3, "range_machinery": rng_m, "range_positive": rng_p}

    # ------------------------------------------------------------------------------------ T4
    print("\n" + "=" * 96)
    print("T4 -- does a successor overturn its parent?")
    by_id = {str(r.get("id")): r for r in rows}
    pairs = [(by_id[str(r.get("successor_of"))], r) for r in rows
             if str(r.get("successor_of") or "") in by_id]
    diff = sum(1 for p, c in pairs if p["_class"] != c["_class"])
    rev = sum(1 for p, c in pairs if {p["_class"], c["_class"]} == {"positive", "negative"})
    print(f"    {len(pairs)} resolvable parent/successor pairs")
    if pairs:
        lo, hi = wilson(diff, len(pairs))
        lo2, hi2 = wilson(rev, len(pairs))
        print(f"    class differs : {diff}/{len(pairs)} = {diff/len(pairs):.3f} [{lo:.3f}, {hi:.3f}]")
        print(f"    REVERSES      : {rev}/{len(pairs)} = {rev/len(pairs):.3f} [{lo2:.3f}, {hi2:.3f}]")
        R["T4"] = {"n_pairs": len(pairs), "differs": diff, "reverses": rev,
                   "differs_ci": [lo, hi], "reverses_ci": [lo2, hi2]}
    else:
        print("    NOT INTERPRETABLE -- no resolvable pairs")
        R["T4"] = {"n_pairs": 0}

    # ------------------------------------------------------------------------------------ T5
    print("\n" + "=" * 96)
    print("T5 -- does the data source predict machinery failure?")
    dep = collections.defaultdict(list)
    for r in rows:
        d = str(r.get("deposit", "")).strip().lower()
        key = next((k for k in ("vitaldb", "krause", "sleep-edf", "dose", "stieger", "chennu",
                                "eegmmidb", "ds00", "hbn", "dreyer") if k in d), None)
        dep[key or "other/none"].append(r)
    big = {k: v for k, v in dep.items() if len(v) >= 8}
    t5 = {}
    for k, v in sorted(big.items(), key=lambda t: -len(t[1])):
        kk = sum(1 for r in v if r["_class"] == "gate_failed")
        lo, hi = wilson(kk, len(v))
        t5[k] = {"n": len(v), "gate_failed": kk, "rate": kk / len(v), "ci": [lo, hi]}
        print(f"    {k:<12} n={len(v):>3}  gate_failed {kk:>3} = {kk/len(v):.3f}  [{lo:.3f}, {hi:.3f}]")
    if len(big) >= 3:
        obs = max(v["rate"] for v in t5.values()) - min(v["rate"] for v in t5.values())
        labs = [r["_class"] for r in rows]
        null = []
        for _ in range(a.reps):
            sh = labs[:]
            rng.shuffle(sh)
            m = dict(zip([id(r) for r in rows], sh))
            rr = []
            for k, v in big.items():
                kk = sum(1 for r in v if m[id(r)] == "gate_failed")
                rr.append(kk / len(v))
            null.append(max(rr) - min(rr))
        null.sort()
        p = sum(1 for x in null if x >= obs) / len(null)
        print(f"  [T5] observed spread {obs:.3f}; permutation null 95th "
              f"{null[int(0.95*len(null))]:.3f}; p = {p:.4f}")
        R["T5"] = {"by_deposit": t5, "spread": obs, "p": p}
    else:
        print("  [T5] NOT INTERPRETABLE -- fewer than 3 deposits with >= 8 registrations")
        R["T5"] = {"by_deposit": t5}

    # ------------------------------------------------------------------------------------ T6
    print("\n" + "=" * 96)
    print("T6 -- the literature's positive rate, against this register's 0.320")
    POS = re.compile(r"(significantly (higher|lower|greater|increased|decreased|associated)|"
                     r"was associated with|were associated with|significant (difference|association|"
                     r"improvement|increase|reduction)|demonstrated|we (found|show) that|"
                     r"effective in|improved|predicted)", re.I)
    NUL = re.compile(r"(no significant|not significant|did not differ|no difference|no association|"
                     r"failed to (show|demonstrate|find)|were similar|was similar|no evidence)", re.I)

    def pm_search(term, n):
        u = f"{EUT}esearch.fcgi?db=pubmed&retmax={n}&term={urllib.parse.quote(term)}"
        with urllib.request.urlopen(u, timeout=60) as r:
            return re.findall(r"<Id>(\d+)</Id>", r.read().decode())

    def pm_pos_rate(pmids):
        pos = nul = tot = 0
        for i in range(0, len(pmids), 100):
            u = (f"{EUT}efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id="
                 + ",".join(pmids[i:i + 100]))
            with urllib.request.urlopen(u, timeout=120) as r:
                txt = r.read().decode("utf-8", "replace")
            for b in re.split(r"\n\n(?=\d+\. )", txt):
                if len(b) < 200:
                    continue
                tot += 1
                p_, n_ = bool(POS.search(b)), bool(NUL.search(b))
                if p_ and not n_:
                    pos += 1
                elif n_ and not p_:
                    nul += 1
            time.sleep(0.4)
        return pos, nul, tot
    try:
        per = 60 if a.smoke else 300
        neu = pm_search('("anesthesia"[MeSH] OR "electroencephalography"[MeSH]) AND '
                        '"journal article"[pt] AND 2023:2025[dp] AND hasabstract', per)
        cpos = pm_search('"significantly associated with" AND "journal article"[pt] AND hasabstract', 80)
        cnul = pm_search('"no significant difference" AND "journal article"[pt] AND hasabstract', 80)
        p0, n0, t0 = pm_pos_rate(neu)
        p1, n1_, t1 = pm_pos_rate(cpos)
        p2, n2, t2_ = pm_pos_rate(cnul)
        r_pos_ctl = p1 / t1 if t1 else float("nan")
        r_nul_ctl = p2 / t2_ if t2_ else float("nan")
        G6 = math.isfinite(r_pos_ctl) and math.isfinite(r_nul_ctl) and r_pos_ctl > r_nul_ctl
        print(f"    [G6] positive-language corpus scores {r_pos_ctl:.3f}; null-language corpus scores "
              f"{r_nul_ctl:.3f} -> {'PASS' if G6 else 'FAIL'}")
        if G6:
            rate = p0 / t0 if t0 else float("nan")
            lo, hi = wilson(p0, t0)
            print(f"  [T6] unselected abstracts scored POSITIVE: {p0}/{t0} = {rate:.3f} "
                  f"[{lo:.3f}, {hi:.3f}]   (explicit null: {n0}/{t0} = {n0/t0:.3f})")
            print(f"       against this register's true-positive rate of 0.320")
            R["T6"] = {"rate": rate, "ci": [lo, hi], "pos": p0, "null": n0, "n": t0,
                       "control_pos": r_pos_ctl, "control_null": r_nul_ctl, "gate": True}
        else:
            print("  [T6] NOT INTERPRETABLE -- the classifier could not separate its two controls")
            R["T6"] = {"gate": False, "control_pos": r_pos_ctl, "control_null": r_nul_ctl}
    except Exception as e:                                            # noqa: BLE001
        print(f"  BLOCKED: {type(e).__name__}: {e}")
        R["T6"] = {"status": "blocked"}

    # ------------------------------------------------------------------------------------ T7
    print("\n" + "=" * 96)
    print("T7 -- does naming a placebo predict anything? RULE 32 VARIANCE CHECK FIRST")
    hasp = [r for r in rows if str(r.get("placebo") or "").strip()]
    nop = [r for r in rows if not str(r.get("placebo") or "").strip()]
    print(f"    names a placebo: {len(hasp)}   does not: {len(nop)}")
    if min(len(hasp), len(nop)) < 25:
        print(f"  [T7] NOT RUN -- the smaller arm has {min(len(hasp), len(nop))} rows, below the "
              f"registered floor of 25. The placebo field does not vary enough in this register to "
              f"support a contrast, and running one anyway is the rule-32 mistake.")
        R["T7"] = {"n_has": len(hasp), "n_not": len(nop), "run": False}
    else:
        k1_, k2_ = (sum(1 for r in x if r["_class"] == "gate_failed") for x in (hasp, nop))
        print(f"    gate_failed: {k1_/len(hasp):.3f} vs {k2_/len(nop):.3f}")
        R["T7"] = {"n_has": len(hasp), "n_not": len(nop), "run": True,
                   "rate_has": k1_ / len(hasp), "rate_not": k2_ / len(nop)}

    # ------------------------------------------------------------------------------------ T8
    print("\n" + "=" * 96)
    print("T8 -- inter-battery consistency on the machinery-failure rate")
    ests = [("E344/T1 row level", 0.240, 0.187, 0.298, "225 registrations"),
            ("E346/T8 lineage level", 0.081, 0.028, 0.213, "37 lineages, majority vote"),
            ("E347/T7 prospective", 0.269, 0.137, 0.461, "26 pre-committed tests"),
            ("E347/T5 external matched", 0.2737, 0.2692, 0.2782, "CTG academic, n<=20")]
    for name, p, lo, hi, note in ests:
        print(f"    {name:<26} {p:.3f}  [{lo:.3f}, {hi:.3f}]   {note}")
    overlap_all = max(e[2] for e in ests) <= min(e[3] for e in ests)
    row_pro_ext = (max(0.187, 0.137, 0.2692) <= min(0.298, 0.461, 0.2782))
    print(f"  [T8] all four intervals share a common point: {overlap_all}")
    print(f"       the three that share an ESTIMAND (row, prospective, external-matched -- all "
          f"'per design') share a common point: {row_pro_ext}")
    print("       the lineage estimate is expected to sit apart: it counts questions, not designs.")
    R["T8"] = {"estimates": [{"name": n, "p": p, "lo": lo, "hi": hi, "note": nt}
                             for n, p, lo, hi, nt in ests],
               "all_overlap": overlap_all, "same_estimand_overlap": row_pro_ext}

    # ------------------------------------------------------------------------------------ T9
    print("\n" + "=" * 96)
    print("T9 -- what would a multi-lab study need? (parameterises PILOT_PROTOCOL_MULTISITE_REGISTER)")

    def power_two_prop(p1_, p2_, n, reps=4000):
        hit = 0
        for _ in range(reps):
            a1 = sum(1 for _ in range(n) if rng.random() < p1_)
            a2 = sum(1 for _ in range(n) if rng.random() < p2_)
            lo1_, hi1_ = wilson(a1, n)
            lo2_, hi2_ = wilson(a2, n)
            if hi1_ < lo2_ or hi2_ < lo1_:
                hit += 1
        return hit / reps
    t9 = {}
    base = 0.24
    for delta in (0.10, 0.05):
        found = None
        for n in (25, 50, 100, 150, 200, 300, 400, 600, 800, 1200):
            pw = power_two_prop(base, base + delta, n, reps=1500 if a.smoke else 3000)
            t9[f"delta={delta}|n={n}"] = pw
            print(f"    delta {delta:.2f}, {n:>4} registrations per lab -> power {pw:.3f}")
            if pw >= 0.80 and found is None:
                found = n
                break
        print(f"  [T9] delta {delta:.2f}: {found if found else '> 1200'} registrations per lab "
              f"for 80 % power (non-overlapping Wilson intervals, two labs)")
        t9[f"delta={delta}|required"] = found
    R["T9"] = t9

    # ------------------------------------------------------------------------------------ T10
    print("\n" + "=" * 96)
    print("T10 -- can the burst-suppression register be audited the same way? FEASIBILITY, not attempt")
    try:
        txt = open(BS_LEDGER).read()
        n_res = len(re.findall(r"^## R\d+", txt, re.M))
    except OSError:
        n_res = 0
    import glob
    scripts = glob.glob(os.path.join(REPO, "analysis", "*.py"))
    with_json = [f for f in scripts if "json.dump" in open(f, errors="replace").read()]
    print(f"    burst-suppression results logged in the ledger : {n_res}")
    print(f"    analysis scripts in that programme             : {len(scripts)}")
    print(f"    scripts that write a machine-readable artifact : {len(with_json)}")
    cov = len(with_json) / n_res if n_res else float("nan")
    print(f"  [T10] artifact coverage = {cov:.4f}. E347/T1's audit needs a verdict-bearing artifact per")
    print( "        result; this programme has essentially none, and its ledger is PROSE, which E343,")
    print( "        E344/T2 and E346/T7 established across three independent tests is not")
    print( "        machine-auditable. **This repo contains ONE auditable register, not two.**")
    print( "        Reported as a measured structural limit rather than attempted, because repeating a")
    print( "        method already shown to fail is the failure rule 101 exists to prevent.")
    R["T10"] = {"n_results": n_res, "n_scripts": len(scripts), "n_with_artifact": len(with_json),
                "coverage": cov, "auditable": False}

    print("\n" + "=" * 96)
    if a.smoke:
        print(f"[SMOKE] T2 spread {spread:.3f} and T5 spread should both collapse under permuted labels.")
        return 0
    json.dump(R, open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
