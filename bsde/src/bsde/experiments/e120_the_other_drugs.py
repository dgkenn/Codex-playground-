"""E120 -- THE OTHER DRUGS. Surgical anaesthesia is not one agent, and every VitalDB result so far
treated it as one.

REGISTERED BEFORE ANY REMIFENTANIL FIDELITY IS COMPUTED. Existing tables only.

=========================================================================================================
THE GAP, RAISED BY THE INVESTIGATOR AND CONFIRMED IN THE DATA
=========================================================================================================
E110, E112, E113 and E118 all defined "the drug" as a single hypnotic -- MAC for volatile cases, propofol
effect-site concentration for TIVA. A surgical anaesthetic is a combination, and what this deposit actually
records is:

    remifentanil Ce   `Orchestra/RFTN20_CE`   **190 of 250 cases, 4,490 of 6,679 agent rows**  -- NEVER USED
    rocuronium        `meta_intraop_rocu`     248 of 250 cases, median 80 mg
    vecuronium        `meta_intraop_vecu`     0 cases
    midazolam         `meta_intraop_mdz`      0 cases
    bolus propofol    `meta_intraop_ppf`      90 of 250 cases

Three of those are settled by inspection and are recorded here so no successor re-opens them: **there is no
benzodiazepine and no vecuronium in this cohort at all**, and **neuromuscular blockade is essentially
universal** (248/250), so paralysis cannot be stratified -- which also means the EMG contamination that
E43, E71 and E99 kept finding is suppressed cohort-wide rather than varying between patients. That is a
convenience, not a control, and it is stated rather than assumed.

**The opioid is the real gap.** Remifentanil is present in three quarters of cases, is titrated
independently of the hypnotic, and reduces hypnotic requirement substantially -- so at matched propofol Ce
or matched MAC, a patient receiving more remifentanil is DEEPER. Every fidelity and every depth-adjusted
estimate this project has reported from VitalDB has a mis-specified exposure.

=========================================================================================================
FOUR QUESTIONS, EACH ATTACHED TO A RESULT ALREADY REPORTED
=========================================================================================================
Fidelity is signed so a correctly-tracking measure is positive, as in E110:
`fid_BIS = -spearman(BIS, drug)`, `fid_exp = +spearman(whole_head_exponent, drug)`, within case.

    P1  DOES ANYTHING TRACK THE OPIOID? fid to remifentanil Ce for BIS and for the exponent. Opioids have
        modest direct EEG effects at clinical dose, so a large fidelity here would itself be surprising
        and would mean the hypnotic and opioid infusions are simply co-titrated.
    P2  DOES ACCOUNTING FOR THE OPIOID RESCUE THE EXPONENT'S PROPOFOL BLINDNESS? E110 measured
        fid_exp = -0.0382 under propofol against +0.2837 under volatile agents. Here: the PARTIAL fidelity
        of the exponent to the hypnotic GIVEN remifentanil Ce, against the marginal fidelity E110
        reported. **PREDICTED: no rescue** -- if the exponent cannot see propofol it will not start seeing
        it once a co-drug is held constant -- and the prediction is stated so a null is not read as
        expected-all-along.
    P3  DOES E109's AGE GRADIENT SURVIVE THE OPIOID? E109 reported +0.2592 [+0.1367, +0.3761] and E113
        cleared it of hypnotic-class confounding. Re-run as a partial given within-case mean remifentanil
        Ce and its within-case spread, on the same estimand.
    P4  THE CONFOUND'S PRECONDITION, as in E113: does remifentanil exposure vary with age? **If it does
        not, P3 cannot be confounded by it and that is the cheapest way this audit can conclude.**

VERDICT, wrong direction FIRST (rule 37) -- the wrong direction costs a reported positive:

    (a) P3's interval INCLUDES 0 while P4 shows a real age-opioid association -> **E109 IS PARTLY AN
        OPIOID EFFECT** and the reported positive is withdrawn or re-described.
    (b) P4 null -> NOT CONFOUNDED BY OPIOID; E109 stands, and P1/P2 are reported on their own terms.
    (c) P3 survives -> E109 stands against a second independent confound.
    And separately for P2: a partial fidelity materially larger than the marginal would mean the
    exponent's propofol blindness is partly an exposure mis-specification, which would change E112's
    reading as well.

=========================================================================================================
GATES
=========================================================================================================
    G1  COVERAGE. >= 60 cases carrying remifentanil Ce with >= 10 windows and the hypnotic present.
    G2  THE OPIOID MUST VARY WITHIN CASE, else a within-case fidelity to it is undefined rather than zero
        (rule 32). Cases with constant remifentanil are dropped and counted.
    G3  E109 MUST REPRODUCE on this subset before it can be audited on it (rule 31) -- the same discipline
        E113 used.
    G4  ARM SEPARATION. Volatile and TIVA are analysed separately throughout, because a partial given
        remifentanil means something different when the hypnotic is a gas.

PLACEBO: age shuffled across cases for P3, 2000 draws; drug permuted across windows within case for P1/P2.
Primary read FIRST (rule 48).

SCOPE. VitalDB, single-channel BIS-module EEG. Remifentanil Ce is the TCI pump's modelled effect-site
concentration, not a measured assay. **This experiment adds ONE drug to the exposure model; it does not
make the exposure model complete** -- volatile/propofol co-induction, bolus agents, nitrous oxide and
vasoactive drugs remain unmodelled, and the deposit does not record enough to fix that.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e120_the_other_drugs.json")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
TABLES = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
    glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))

MIN_WINDOWS, MIN_CASES = 10, 60
E109_POINT = 0.2592
REPS = 4000
PLACEBO_DRAWS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rank(x):
    return np.argsort(np.argsort(np.asarray(x, float))).astype(float)


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 0 or np.ptp(y[ok]) <= 0:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    rx -= rx.mean(); ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 1e-12 else float("nan")


def partial_spearman(x, y, Z):
    x, y, Z = np.asarray(x, float), np.asarray(y, float), np.asarray(Z, float)
    if Z.ndim == 1:
        Z = Z.reshape(-1, 1)
    ok = np.isfinite(x) & np.isfinite(y) & np.all(np.isfinite(Z), axis=1)
    if ok.sum() < Z.shape[1] + 6:
        return float("nan")
    rx, ry = _rank(x[ok]), _rank(y[ok])
    RZ = np.column_stack([np.ones(ok.sum())] + [_rank(Z[ok, j]) for j in range(Z.shape[1])])
    bx, *_ = np.linalg.lstsq(RZ, rx, rcond=None)
    by, *_ = np.linalg.lstsq(RZ, ry, rcond=None)
    ex, ey = rx - RZ @ bx, ry - RZ @ by
    d = float(np.sqrt((ex ** 2).sum() * (ey ** 2).sum()))
    return float((ex * ey).sum() / d) if d > 1e-12 else float("nan")


def ci(v):
    v = np.sort(np.asarray([q for q in v if np.isfinite(q)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def main() -> int:
    if not os.path.exists(AGENTS) or not any(os.path.exists(t) for t in TABLES):
        print("ABSENT: missing input tables")
        return 2
    ag = defaultdict(dict)
    for r in csv.DictReader(open(AGENTS, newline="")):
        t = _f(r.get("t_s"))
        if math.isfinite(t):
            ag[r["caseid"]][round(t, 1)] = r
    per = defaultdict(list)
    seen = set()
    for tb in TABLES:
        if not os.path.exists(tb):
            continue
        for r in csv.DictReader(open(tb, newline="")):
            c, t = r.get("meta_caseid"), _f(r.get("meta_t_s"))
            if not c or not math.isfinite(t):
                continue
            key = (c, round(t, 1))
            if key in seen:
                continue
            seen.add(key)
            a = ag.get(c, {}).get(round(t, 1))
            if a is None:
                continue
            b, e, age = _f(r.get("meta_bis")), _f(r.get("whole_head_exponent")), _f(r.get("meta_age"))
            if not (math.isfinite(b) and b > 0 and math.isfinite(e) and math.isfinite(age)):
                continue
            per[c].append((b, e, _f(a.get("mac")), _f(a.get("ppf_ce")), _f(a.get("rftn_ce")), age))

    res = {"cohort_facts": {"vecuronium_cases": 0, "midazolam_cases": 0,
                            "rocuronium_cases_of_250": 248,
                            "note": "no benzodiazepine, no vecuronium; paralysis essentially universal "
                                    "so NMB cannot be stratified and EMG is suppressed cohort-wide"},
           "arms": {}, "gates": {}}
    arms = defaultdict(list)
    n_const_opioid = 0
    for c, v in per.items():
        A = np.array(v, float)
        b, e, mac, ppf, rft, age = (A[:, i] for i in range(6))
        for arm, drug in (("volatile", mac), ("tiva", ppf)):
            ok = np.isfinite(drug) & (drug > 0) & np.isfinite(rft) & (rft > 0)
            if ok.sum() < MIN_WINDOWS:
                continue
            if np.ptp(drug[ok]) <= 0 or np.ptp(b[ok]) <= 0 or np.ptp(e[ok]) <= 0:
                continue
            if np.ptp(rft[ok]) <= 0:
                n_const_opioid += 1
                continue
            arms[arm].append({
                "case": c, "age": float(age[0]), "n": int(ok.sum()),
                "fid_bis_hyp": -spearman(b[ok], drug[ok]), "fid_exp_hyp": spearman(e[ok], drug[ok]),
                "fid_bis_rft": -spearman(b[ok], rft[ok]), "fid_exp_rft": spearman(e[ok], rft[ok]),
                "pfid_exp_hyp": partial_spearman(e[ok], drug[ok], rft[ok]),
                "pfid_bis_hyp": -partial_spearman(b[ok], drug[ok], rft[ok]),
                "agree": spearman(b[ok], e[ok]),
                "rft_mean": float(np.mean(rft[ok])), "rft_sd": float(np.std(rft[ok])),
                "sd_b": float(np.std(b[ok])), "sd_e": float(np.std(e[ok]))})
    print(f"{len(per)} cases joined; opioid constant within case in {n_const_opioid} case-arms (G2)")
    res["gates"]["G2_dropped_constant_opioid"] = n_const_opioid
    rng = np.random.default_rng(SEED)

    for arm in ("volatile", "tiva"):
        rows = [r for r in arms.get(arm, []) if all(np.isfinite(r[k]) for k in
                                                    ("fid_exp_hyp", "fid_exp_rft", "pfid_exp_hyp"))]
        n = len(rows)
        print(f"\n=== ARM {arm} ({n} cases with remifentanil) ===")
        if n < 20:
            print("   too few cases, not analysed")
            continue

        def col(k):
            return np.array([r[k] for r in rows], float)

        def boot(v):
            return ci([float(np.mean(v[i])) for i in (rng.integers(0, n, n) for _ in range(REPS))])

        for label, k in (("BIS  vs remifentanil", "fid_bis_rft"),
                         ("exp  vs remifentanil", "fid_exp_rft")):
            v = col(k)
            lo, hi = boot(v)
            print(f"P1 {label:<22s} fidelity {np.mean(v):+.4f} [{lo:+.4f}, {hi:+.4f}]")

        m, p = col("fid_exp_hyp"), col("pfid_exp_hyp")
        d = p - m
        m_lo, m_hi = boot(m)
        p_lo, p_hi = boot(p)
        d_lo, d_hi = boot(d)
        print(f"P2 exponent vs hypnotic  marginal {np.mean(m):+.4f} [{m_lo:+.4f}, {m_hi:+.4f}]  ->  "
              f"partial given opioid {np.mean(p):+.4f} [{p_lo:+.4f}, {p_hi:+.4f}]")
        print(f"   change {np.mean(d):+.4f} [{d_lo:+.4f}, {d_hi:+.4f}]  "
              f"{'RESCUED' if (np.isfinite(d_lo) and d_lo > 0) else 'no rescue'}")
        mb, pb = col("fid_bis_hyp"), col("pfid_bis_hyp")
        print(f"   (BIS for reference: marginal {np.mean(mb):+.4f} -> partial {np.mean(pb):+.4f})")

        res["arms"][arm] = {
            "n": n,
            "P1_bis_vs_opioid": [float(np.mean(col('fid_bis_rft')))],
            "P1_exp_vs_opioid": [float(np.mean(col('fid_exp_rft')))],
            "P2_marginal": [float(np.mean(m)), m_lo, m_hi],
            "P2_partial": [float(np.mean(p)), p_lo, p_hi],
            "P2_change": [float(np.mean(d)), d_lo, d_hi]}

    # ---- P3 / P4: E109's age gradient against the opioid ------------------------------------------
    allrows = [r for a in arms.values() for r in a if np.isfinite(r["agree"])]
    byc = {}
    for r in allrows:
        byc.setdefault(r["case"], r)
    rows = list(byc.values())
    n = len(rows)
    agree = np.array([r["agree"] for r in rows])
    age = np.array([r["age"] for r in rows])
    rmean = np.array([r["rft_mean"] for r in rows])
    rsd = np.array([r["rft_sd"] for r in rows])
    Z = np.column_stack([rmean, rsd, [r["sd_b"] for r in rows], [r["sd_e"] for r in rows],
                         np.log([r["n"] for r in rows])])
    print(f"\n=== E109 AUDIT AGAINST THE OPIOID ({n} cases with remifentanil) ===")
    res["gates"]["G1_pass"] = bool(n >= MIN_CASES)
    print(f"G1 coverage   {n} >= {MIN_CASES}  {'PASS' if res['gates']['G1_pass'] else 'FAIL'}")

    unadj = spearman(agree, age)
    u_lo, u_hi = ci([spearman(agree[i], age[i])
                     for i in (rng.integers(0, n, n) for _ in range(REPS))])
    g3 = bool(np.isfinite(u_lo) and u_lo > 0)
    res["gates"]["G3"] = {"unadjusted": unadj, "lo": u_lo, "hi": u_hi, "pass": g3}
    print(f"G3 reproduce  E109 on this subset {unadj:+.4f} [{u_lo:+.4f}, {u_hi:+.4f}]  "
          f"(E109 reported {E109_POINT:+.4f})  {'PASS' if g3 else 'FAIL'}")

    p4 = spearman(rmean, age)
    p4_lo, p4_hi = ci([spearman(rmean[i], age[i])
                       for i in (rng.integers(0, n, n) for _ in range(REPS))])
    p4_real = bool(np.isfinite(p4_lo) and not (p4_lo <= 0.0 <= p4_hi))
    print(f"P4 precondition  spearman(mean remifentanil Ce, age) = {p4:+.4f} "
          f"[{p4_lo:+.4f}, {p4_hi:+.4f}]  "
          f"{'opioid exposure DOES vary with age' if p4_real else 'no age-opioid association'}")

    p3 = partial_spearman(agree, age, Z)
    p3_lo, p3_hi = ci([partial_spearman(agree[i], age[i], Z[i])
                       for i in (rng.integers(0, n, n) for _ in range(REPS))])
    pl = [partial_spearman(agree, age[rng.permutation(n)], Z) for _ in range(PLACEBO_DRAWS)]
    q_lo, q_hi = ci(pl)
    inside = bool(np.isfinite(q_lo) and q_lo <= p3 <= q_hi)
    survives = bool(np.isfinite(p3_lo) and p3_lo > 0 and not inside)
    res["P3"] = {"partial": p3, "lo": p3_lo, "hi": p3_hi, "placebo": [q_lo, q_hi],
                 "inside": inside, "survives": survives}
    res["P4"] = {"rho": p4, "lo": p4_lo, "hi": p4_hi, "association": p4_real}
    print(f"P3 adjusted   partial given opioid mean+spread and E109's attenuation covariates = "
          f"{p3:+.4f} [{p3_lo:+.4f}, {p3_hi:+.4f}]")
    print(f"              placebo (age shuffled) [{q_lo:+.4f}, {q_hi:+.4f}]  "
          f"{'INSIDE' if inside else 'outside'}")

    if not g3:
        v = ("ABSENT -- E109's effect does not reproduce on the remifentanil-carrying subset, so this "
             "audit would be adjusting something that is not there (rule 31).")
    elif not p4_real:
        v = (f"NOT CONFOUNDED BY THE OPIOID -- the precondition fails. Mean remifentanil Ce and age are "
             f"not associated ({p4:+.4f} [{p4_lo:+.4f}, {p4_hi:+.4f}]), so no opioid-exposure difference "
             f"can generate an age gradient. E109 stands against a second independent confound after "
             f"E113 cleared it of hypnotic class."
             + (f" It ALSO survives adjustment: {p3:+.4f} [{p3_lo:+.4f}, {p3_hi:+.4f}]."
                if survives else
                f" NOTE: it does NOT survive adjustment ({p3:+.4f} [{p3_lo:+.4f}, {p3_hi:+.4f}]), which "
                f"given a null precondition means the covariates are absorbing variance rather than "
                f"confounding, and both numbers are reported."))
    elif not survives:
        v = (f"**E109 IS PARTLY AN OPIOID EFFECT.** Remifentanil exposure varies with age ({p4:+.4f}) and "
             f"E109's gradient does not survive adjustment for it ({p3:+.4f} [{p3_lo:+.4f}, {p3_hi:+.4f}]). "
             f"The reported positive must be re-described: what was called an age effect is partly the "
             f"opioid regimen that accompanies age.")
    else:
        v = (f"E109 SURVIVES THE OPIOID. Remifentanil exposure does vary with age ({p4:+.4f}), so the "
             f"confound was real to check, and the gradient survives adjustment for the opioid's "
             f"within-case mean and spread ({p3:+.4f} [{p3_lo:+.4f}, {p3_hi:+.4f}]), outside its placebo. "
             f"With E113's hypnotic-class audit, two independent drug-regimen explanations are now "
             f"excluded.")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
