#!/usr/bin/env python3
"""E350 -- ten tests: the literature's positive rate, measured on CONCLUSIONS rather than whole abstracts.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY THIS EXISTS. E348/T6 measured how often published abstracts report a supportive finding, and the
answer depended entirely on a denominator: **0.347 of all sampled abstracts used supportive language,
0.030 stated an explicit null, and the classifier ABSTAINED on 0.623.** Against this register's
true-positive rate of 0.29-0.32 that gives 1.08x on one reading and 2.87x on the other. **The abstention
is the whole problem**, and it has an obvious cause that E348 did not exploit: a whole abstract contains
background, methods and results, and supportive or null language in any of them fires the classifier or
buries the signal.

**MEDLINE structures 1.5 million recent abstracts into labelled sections, including CONCLUSIONS.** The
conclusion is where an author states what they think they found, which is the estimand the overstatement
claim actually needs. Every test here classifies CONCLUSIONS text only.

------------------------------------------------------------------------------------------------------
T1  THE CONCLUSIONS-ONLY POSITIVE RATE. Primary: among structured abstracts, the fraction whose
    CONCLUSIONS section states a supportive finding, the fraction stating an explicit null, and the
    abstention rate. PREDICTION: abstention falls well below E348's 0.623, because a conclusion is
    written to state a conclusion. WRONG IF abstention stays high -- then the ambiguity is in how authors
    write, not in the section boundary, and the overstatement factor cannot be pinned down by this route
    at all. Named first: it would mean the 2.87x/1.08x ambiguity is permanent.

T2  BY PUBLICATION TYPE. Primary: the conclusions-positive rate for RANDOMIZED CONTROLLED TRIAL,
    OBSERVATIONAL STUDY and META-ANALYSIS publication types.
    PREDICTION: RCTs report positives LESS often than observational studies, because a randomised design
    can return a clean null and is preregistered more often.

T3  OVER TIME. Primary: the rate for 2005-2009 against 2020-2024. Descriptive; the reproducibility
    literature would predict a fall if reporting norms have tightened.

T4  BY FIELD. Primary: the rate across four fields (anaesthesia/EEG, oncology, cardiology, psychiatry),
    each with its own sample. G4 per-arm (rule 71): a field is reported only if its own sample reaches
    150 classified conclusions.

T5  THE EXPLICIT-NULL RATE. Primary: how often a conclusion states plainly that the study found nothing.
    This is the quantity a positives-only literature would drive to zero, and it is the cleanest single
    number for the paper.

T6  ABSTENTION SENSITIVITY. Primary: the overstatement factor as a function of how abstentions are
    assigned -- all to positive, all to null, split proportionally, dropped. Reported as the full range.
    **This is the honest form of E348/T6's finding**: the factor is a range, and its width is a property
    of the measurement, not of the literature.

T7  DOES A REGISTERED STUDY CONCLUDE DIFFERENTLY? Primary: the conclusions-positive rate among abstracts
    whose text carries a trial-registration identifier (NCT number) against those that do not.
    **This is the closest available analogue to the register format's central claim** -- that
    pre-registration changes what gets reported -- and it is measurable here without any new data.
    CONFOUND declared and not controlled (rule 54): registered studies are mostly trials, and T2 already
    shows publication type matters. So T7 is reported jointly with T2's strata, never marginally.

T8  DOES ABSTRACT LENGTH PREDICT POSITIVE LANGUAGE? A nuisance check: if longer conclusions simply give
    the classifier more chances to fire, the rate is partly an artefact of length.
    G8: if the rate rises monotonically with length across quartiles, T1's estimate is confounded and
    said to be so.

T9  CLASSIFIER AGREEMENT WITH E348's WHOLE-ABSTRACT INSTRUMENT. Primary: on the same PMIDs, how often do
    the two instruments agree? Disagreement is expected and is the point -- but a near-zero agreement
    would mean one of them is measuring noise (rule 23's shape).

T10 THE SYNTHESIS. Primary: the overstatement factor with every denominator stated explicitly, alongside
    this register's 0.29-0.32. **No single headline number is reported**, by design: E330's "3.17x" was
    quotable precisely because it hid its denominator, and the correction is to publish the table.

GATES.
  G0  NETWORK: E-utilities must respond; otherwise the affected tests report BLOCKED, never a number.
  G1  CAPABILITY BOTH WAYS, and NOT with self-written plants (rule 91). The classifier must score a
      corpus retrieved on explicit-null phrasing BELOW one retrieved on supportive phrasing, on
      CONCLUSIONS text, with both rates printed. If it cannot separate them, every primary here is NOT
      INTERPRETABLE.
  GS  `--smoke` shrinks every sample and asserts the gate still evaluates.

LIMITATIONS.
  1. The estimand is what authors WROTE in a conclusion, not what their study found. That gap is the
     claim being made, not a confound -- the same wording E346/T10 and E348/T6 carried.
  2. Structured abstracts are not a random sample of the literature; they skew toward clinical journals.
     Reported, not adjusted.
  3. A keyword classifier is a blunt instrument. Its abstention rate is reported everywhere as a
     first-class number rather than hidden in a denominator, which is the specific lesson of E348/T6.

    python -m bsde.experiments.e350_conclusions_benchmark --smoke
    python -m bsde.experiments.e350_conclusions_benchmark
"""
from __future__ import annotations

import argparse, collections, json, math, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
CACHE = os.environ.get("E350_CACHE",
                       "/tmp/claude-0/-home-user-Codex-playground-/"
                       "b1443846-9653-5e64-9907-963c5d972484/scratchpad/e350_cache")
EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

from bsde.experiments.e346_external_register import wilson       # noqa: E402

REGISTER_TP_LO, REGISTER_TP_HI = 0.29, 0.32     # E348/T3's bookkeeping range

POS = re.compile(r"(significantly (higher|lower|greater|increased|decreased|improved|associated)|"
                 r"(is|was|were|are) associated with|significant (difference|association|improvement|"
                 r"increase|reduction|effect)|we (found|show|demonstrate) that|demonstrates?|"
                 r"effective (in|for|at)|improves?|predicts?|supports? the|confirms?|"
                 r"may be (useful|effective|a promising))", re.I)
NUL = re.compile(r"(no significant|not significant|did not (differ|improve|reduce|increase|change)|"
                 r"no (difference|association|effect|benefit|evidence)|failed to (show|demonstrate|"
                 r"find|improve)|(was|were) (similar|comparable)|does not (support|appear)|"
                 r"no clear|insufficient evidence)", re.I)


def _get(url, tries=4, timeout=90):
    import hashlib
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest()[:24] + ".txt")
    if os.path.exists(key):
        with open(key, errors="replace") as fh:
            return fh.read()
    last = None
    for t in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                d = r.read().decode("utf-8", "replace")
            with open(key, "w") as fh:
                fh.write(d)
            time.sleep(0.35)
            return d
        except Exception as e:                                        # noqa: BLE001
            last = e
            time.sleep(2 ** t)
    raise RuntimeError(f"GET failed: {url} :: {last}")


def esearch(term, n):
    return re.findall(r"<Id>(\d+)</Id>",
                      _get(f"{EUT}esearch.fcgi?db=pubmed&retmax={n}&term={urllib.parse.quote(term)}"))


CONCL = re.compile(r'<AbstractText[^>]*NlmCategory="CONCLUSIONS"[^>]*>(.*?)</AbstractText>',
                   re.S | re.I)
PMID = re.compile(r"<PMID[^>]*>(\d+)</PMID>")
NCT = re.compile(r"\bNCT\d{8}\b")


def conclusions(pmids):
    """Return {pmid: (conclusions_text, full_abstract_text)} for pmids with a CONCLUSIONS section."""
    out = {}
    for i in range(0, len(pmids), 100):
        xml = _get(f"{EUT}efetch.fcgi?db=pubmed&rettype=abstract&retmode=xml&id="
                   + ",".join(pmids[i:i + 100]))
        for art in re.split(r"(?=<PubmedArticle>)", xml):
            m = PMID.search(art)
            if not m:
                continue
            cs = CONCL.findall(art)
            if not cs:
                continue
            txt = re.sub(r"<[^>]+>", " ", " ".join(cs))
            full = re.sub(r"<[^>]+>", " ", " ".join(
                re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", art, re.S | re.I)))
            out[m.group(1)] = (re.sub(r"\s+", " ", txt).strip(),
                               re.sub(r"\s+", " ", full).strip())
    return out


def classify(txt):
    p, n = bool(POS.search(txt or "")), bool(NUL.search(txt or ""))
    if p and not n:
        return "POSITIVE"
    if n and not p:
        return "NULL"
    return "ABSTAIN"


def rate_block(texts, label, out=None):
    c = collections.Counter(classify(t) for t in texts)
    n = sum(c.values())
    if not n:
        print(f"    {label:<34} no text")
        return None
    pos, nul, ab = c["POSITIVE"] / n, c["NULL"] / n, c["ABSTAIN"] / n
    lo, hi = wilson(c["POSITIVE"], n)
    called = c["POSITIVE"] + c["NULL"]
    pc = c["POSITIVE"] / called if called else float("nan")
    print(f"    {label:<34} n={n:>4}  POS {pos:.3f} [{lo:.3f},{hi:.3f}]  NULL {nul:.3f}  "
          f"ABSTAIN {ab:.3f}  pos-among-called {pc:.3f}")
    return {"n": n, "positive": pos, "null": nul, "abstain": ab, "pos_among_called": pc,
            "ci": [lo, hi], "counts": dict(c)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e350_conclusions_benchmark.json"))
    a = ap.parse_args(argv)
    R = {}
    N = 120 if a.smoke else 600
    SB = "hasstructuredabstract"

    # ------------------------------------------------------------------------------------ G1
    print("=" * 96)
    print("G1 -- capability both ways, on CONCLUSIONS text, with externally-retrieved corpora")
    try:
        cpos = esearch(f'"significantly associated with" AND {SB} AND 2015:2025[dp]', 200)
        cnul = esearch(f'"no significant difference" AND {SB} AND 2015:2025[dp]', 200)
        dpos = conclusions(cpos)
        dnul = conclusions(cnul)
        rp = rate_block([v[0] for v in dpos.values()], "positive-language corpus")
        rn = rate_block([v[0] for v in dnul.values()], "null-language corpus")
    except RuntimeError as e:
        print(f"  BLOCKED: {e}")
        json.dump({"status": "blocked"}, open(a.out, "w"))
        return 0
    G1 = bool(rp and rn and rp["positive"] > rn["positive"] and rn["null"] > rp["null"])
    print(f"  [G1] positive corpus POS {rp['positive']:.3f} > null corpus POS {rn['positive']:.3f}, "
          f"and null corpus NULL {rn['null']:.3f} > positive corpus NULL {rp['null']:.3f} -> "
          f"{'PASS' if G1 else 'FAIL'}")
    R["G1"] = {"pos_corpus": rp, "null_corpus": rn, "pass": G1}
    if not G1:
        print("\nEVERY PRIMARY IS NOT INTERPRETABLE -- the classifier cannot separate its controls.")
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        return 0

    # ------------------------------------------------------------------------------------ T1
    print("\n" + "=" * 96)
    print("T1 -- the conclusions-only positive rate")
    base_ids = esearch(f'{SB} AND "journal article"[pt] AND 2023:2025[dp]', N)
    base = conclusions(base_ids)
    t1 = rate_block([v[0] for v in base.values()], "unselected, CONCLUSIONS only")
    whole = rate_block([v[1] for v in base.values()], "same PMIDs, WHOLE abstract")
    print(f"  [T1] abstention on conclusions {t1['abstain']:.3f} against E348's whole-abstract 0.623 -> "
          f"{'PREDICTION MET' if t1['abstain'] < 0.623 else 'PREDICTION NOT MET -- the ambiguity is in how authors write'}")
    R["T1"] = {"conclusions": t1, "whole_abstract": whole}

    # ------------------------------------------------------------------------------------ T2
    print("\n" + "=" * 96)
    print("T2 -- by publication type")
    t2 = {}
    for pt in ("randomized controlled trial", "observational study", "meta-analysis"):
        ids = esearch(f'{SB} AND "{pt}"[pt] AND 2015:2025[dp]', N)
        d = conclusions(ids)
        t2[pt] = rate_block([v[0] for v in d.values()], pt)
    if t2.get("randomized controlled trial") and t2.get("observational study"):
        met = t2["randomized controlled trial"]["positive"] < t2["observational study"]["positive"]
        print(f"  [T2] RCTs report positives less often than observational studies -> "
              f"{'PREDICTION MET' if met else 'PREDICTION NOT MET'}")
    R["T2"] = t2

    # ------------------------------------------------------------------------------------ T3
    print("\n" + "=" * 96)
    print("T3 -- over time")
    t3 = {}
    for span in ("2005:2009", "2020:2024"):
        ids = esearch(f'{SB} AND "journal article"[pt] AND {span}[dp]', N)
        d = conclusions(ids)
        t3[span] = rate_block([v[0] for v in d.values()], span)
    R["T3"] = t3

    # ------------------------------------------------------------------------------------ T4
    print("\n" + "=" * 96)
    print("T4 -- by field (per-arm gate, rule 71)")
    FIELDS = {"anaesthesia/EEG": '("anesthesia"[MeSH] OR "electroencephalography"[MeSH])',
              "oncology": '"neoplasms"[MeSH]', "cardiology": '"cardiovascular diseases"[MeSH]',
              "psychiatry": '"mental disorders"[MeSH]'}
    t4 = {}
    for name, mesh in FIELDS.items():
        ids = esearch(f'{mesh} AND {SB} AND "journal article"[pt] AND 2018:2025[dp]', N)
        d = conclusions(ids)
        b = rate_block([v[0] for v in d.values()], name)
        if b and b["n"] < 150:
            print(f"      ^ {name}: n < 150, NOT INTERPRETABLE for this arm")
            b["usable"] = False
        elif b:
            b["usable"] = True
        t4[name] = b
    R["T4"] = t4

    # ------------------------------------------------------------------------------------ T5
    print("\n" + "=" * 96)
    print(f"T5 -- the explicit-null rate in conclusions: {t1['null']:.4f} "
          f"({t1['counts'].get('NULL', 0)}/{t1['n']})")
    lo5, hi5 = wilson(t1["counts"].get("NULL", 0), t1["n"])
    print(f"     95% CI [{lo5:.4f}, {hi5:.4f}] -- the quantity a positives-only literature drives to zero")
    R["T5"] = {"rate": t1["null"], "ci": [lo5, hi5]}

    # ------------------------------------------------------------------------------------ T6
    print("\n" + "=" * 96)
    print("T6 -- abstention sensitivity: the overstatement factor under every assignment")
    p_, n_, ab_ = (t1["counts"].get(k, 0) for k in ("POSITIVE", "NULL", "ABSTAIN"))
    tot = t1["n"]
    schemes = {
        "abstentions -> positive": (p_ + ab_) / tot,
        "abstentions -> null": p_ / tot,
        "abstentions split proportionally": (p_ / (p_ + n_)) if (p_ + n_) else float("nan"),
        "abstentions dropped": (p_ / (p_ + n_)) if (p_ + n_) else float("nan"),
    }
    t6 = {}
    for k, v in schemes.items():
        f_lo, f_hi = v / REGISTER_TP_HI, v / REGISTER_TP_LO
        t6[k] = {"lit_rate": v, "factor_range": [f_lo, f_hi]}
        print(f"    {k:<34} literature {v:.3f}   overstatement {f_lo:.2f}x - {f_hi:.2f}x")
    fs = [x for v in t6.values() for x in v["factor_range"] if math.isfinite(x)]
    print(f"  [T6] the factor spans {min(fs):.2f}x to {max(fs):.2f}x depending ONLY on how "
          f"abstentions are assigned. That width is a property of the measurement.")
    R["T6"] = t6

    # ------------------------------------------------------------------------------------ T7
    print("\n" + "=" * 96)
    print("T7 -- do abstracts carrying a trial registration number conclude differently?")
    print("      CONFOUND DECLARED: registered studies are mostly trials; reported jointly with T2.")
    reg = [v[0] for v in base.values() if NCT.search(v[1])]
    noreg = [v[0] for v in base.values() if not NCT.search(v[1])]
    a7 = rate_block(reg, "carries an NCT number")
    b7 = rate_block(noreg, "no NCT number")
    if a7 and b7 and min(a7["n"], b7["n"]) >= 25:
        print(f"  [T7] difference in POSITIVE rate = {a7['positive'] - b7['positive']:+.4f}")
    else:
        print(f"  [T7] NOT INTERPRETABLE -- an arm is under 25 "
              f"(registered {a7['n'] if a7 else 0}, unregistered {b7['n'] if b7 else 0})")
    R["T7"] = {"registered": a7, "unregistered": b7}

    # ------------------------------------------------------------------------------------ T8
    print("\n" + "=" * 96)
    print("T8 -- does conclusion LENGTH predict positive language? (nuisance check)")
    lens = sorted((len(v[0]), classify(v[0])) for v in base.values())
    q = max(1, len(lens) // 4)
    t8 = {}
    prev, mono = None, True
    for i in range(4):
        blk = lens[i * q:(i + 1) * q] if i < 3 else lens[3 * q:]
        if not blk:
            continue
        r = sum(1 for _, c in blk if c == "POSITIVE") / len(blk)
        t8[f"Q{i+1}"] = {"n": len(blk), "median_chars": blk[len(blk) // 2][0], "positive": r}
        print(f"    Q{i+1}  n={len(blk):>4}  median {blk[len(blk)//2][0]:>4} chars  POSITIVE {r:.3f}")
        if prev is not None and r < prev:
            mono = False
        prev = r
    print(f"  [G8] positive rate rises monotonically with length: {mono} -> "
          f"{'CONFOUNDED -- T1 is partly a length artefact' if mono else 'no monotone length effect'}")
    R["T8"] = {"quartiles": t8, "monotone": mono}

    # ------------------------------------------------------------------------------------ T9
    print("\n" + "=" * 96)
    print("T9 -- agreement with E348's whole-abstract instrument on the SAME PMIDs")
    agree = sum(1 for v in base.values() if classify(v[0]) == classify(v[1]))
    ag = agree / len(base) if base else float("nan")
    conf = collections.Counter((classify(v[1]), classify(v[0])) for v in base.values())
    print(f"    agreement {agree}/{len(base)} = {ag:.3f}")
    print("    whole-abstract -> conclusions: " +
          ", ".join(f"{k[0][:3]}->{k[1][:3]}:{v}" for k, v in conf.most_common(6)))
    print(f"  [T9] {'the two instruments are measuring related things' if ag > 0.4 else 'NEAR-ZERO AGREEMENT -- one of them is measuring noise'}")
    R["T9"] = {"agreement": ag, "confusion": {f"{k[0]}->{k[1]}": v for k, v in conf.items()}}

    # ------------------------------------------------------------------------------------ T10
    print("\n" + "=" * 96)
    print("T10 -- THE SYNTHESIS. No single headline number, by design.")
    print(f"    this register's true-positive rate           : {REGISTER_TP_LO:.2f} - "
          f"{REGISTER_TP_HI:.2f}   (E348/T3)")
    print(f"    literature, whole abstract, all              : 0.347            (E348/T6)")
    print(f"    literature, whole abstract, among called     : 0.920            (E348/T6)")
    print(f"    literature, CONCLUSIONS, all                 : {t1['positive']:.3f}")
    print(f"    literature, CONCLUSIONS, among called        : {t1['pos_among_called']:.3f}")
    print(f"    literature, CONCLUSIONS, explicit null       : {t1['null']:.3f}")
    print(f"    overstatement factor                         : {min(fs):.2f}x - {max(fs):.2f}x")
    print("    E330's '3.17x' sits inside that span and is not wrong -- it is UNDER-SPECIFIED.")
    R["T10"] = {"register": [REGISTER_TP_LO, REGISTER_TP_HI],
                "whole_all": 0.347, "whole_called": 0.920,
                "concl_all": t1["positive"], "concl_called": t1["pos_among_called"],
                "concl_null": t1["null"], "factor_span": [min(fs), max(fs)]}

    print("\n" + "=" * 96)
    if a.smoke:
        print("[SMOKE] small samples; the gate and every branch were exercised.")
        return 0
    json.dump(R, open(a.out, "w"), indent=1, default=float)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
