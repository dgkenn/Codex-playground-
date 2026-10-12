#!/usr/bin/env python3
"""IS BURST SUPPRESSION HOW AGE CAUSES INTRAOPERATIVE HYPOTENSION? — the double-jeopardy question.

WHY THIS RAISES THE STAKES. Two facts are separately well established and have never been joined:

  (1) Older patients reach burst suppression at LOWER anaesthetic concentrations. This is a central result of the
      Purdon/Brown programme on the ageing anaesthetised brain — the same dose produces a profoundly different
      cortical state at 75 than at 35.
  (2) Older patients suffer more intraoperative hypotension, and intraoperative hypotension is the modifiable
      exposure that perioperative medicine actually acts on.

If suppression causes hypotension — which is what the rest of this project argues, with the vasopressor block as
its sharpest evidence — then (1) and (2) are the same story, and burst suppression is a MECHANISM by which age
translates into haemodynamic harm. That reframes the finding from a curiosity about a 0.33 mmHg displacement into
an account of why the population that receives the most anaesthesia is the population it hurts most.

It is also directly falsifiable, and the falsification is informative either way:
    if age -> hypotension is NOT attenuated by suppression, the two facts remain unconnected and the ageing angle
    should be dropped rather than asserted.

DESIGN. This is a CASE-LEVEL mediation, because age is a case-level exposure — the within-case estimator used
everywhere else in this project cannot address it (age does not vary within a patient, so a case fixed effect
absorbs it entirely). That is a real change of estimator and brings back all the between-patient confounding the
within-case design was built to remove. Stated plainly rather than buried.

    exposure   age (per decade)
    mediator   suppression burden -- minutes with any suppression during maintenance
    outcome    hypotensive burden -- minutes with MAP < 65 during maintenance
    adjust     ASA class, sex, BMI, maintenance duration, and MEAN ANAESTHETIC CONCENTRATION.
               The dose adjustment is the crux: without it, "older patients get more suppression" could simply
               mean clinicians give the elderly relatively more drug. Adjusting for mean Ce asks whether age
               produces more suppression AT THE SAME DOSE, which is the Purdon/Brown claim.
    scale      risk-difference / minutes throughout (linear models), because the quantities must be summable and
               because odds ratios are non-collapsible, so an OR change on adding a mediator confounds mediation
               with non-collapsibility.
    inference  case-level nonparametric bootstrap of the whole procedure.

WHAT WOULD MAKE THIS UNINTERPRETABLE, and is therefore reported alongside: duration is both a confounder (longer
operations accumulate more of everything) and partly a consequence of patient factors. Sicker and older patients
have longer, bigger operations. Adjusting for duration is necessary and not innocent, so the analysis is repeated
WITHOUT the duration adjustment so the reader can see how much of the result rests on it.
"""
import csv, os, sys
from collections import defaultdict
import numpy as np

DATA = os.environ.get("EEG_PROBE_DIR", "/tmp/eeg_probe")
SP = os.environ.get("VITAL_SCRATCH",
                    "/tmp/claude-0/-home-user-Codex-playground-/1d26478f-63e5-5b21-a0bb-af4206dc3baa/scratchpad/vitaldb")
NBOOT = int(os.environ.get("NBOOT", "2000"))
rng = np.random.default_rng(20260725)
MAP_LO = float(os.environ.get("MAP_LO", "30"))
MAP_HI = float(os.environ.get("MAP_HI", "150"))
THRESH = 65.0


def _map_ok(raw):
    try:
        v = float(raw) if raw not in ("", None) else float("nan")
    except Exception:
        return float("nan")
    return v if (v == v and MAP_LO <= v <= MAP_HI) else float("nan")


def build():
    per = defaultdict(lambda: dict(bs=[], mbp=[], ce=[]))
    seen = set()
    with open(f"{DATA}/bridge_bins.csv") as fh:
        for d in csv.DictReader(fh):
            try:
                cid = d["caseid"]; t = float(d["bin_t"])
                if (cid, t) in seen:
                    continue
                seen.add((cid, t))
                ce = float(d["ce"]) if d["ce"] else np.nan
                if not (ce == ce and ce >= 1.0):
                    continue
                bs = float(d["bs"])
                if bs != bs:
                    continue
                p = per[cid]
                p["bs"].append(bs); p["mbp"].append(_map_ok(d["mbp"])); p["ce"].append(ce)
            except Exception:
                pass
    meta = {}
    with open(f"{SP}/cases.csv") as fh:
        for r in csv.DictReader(fh):
            cid = r.get("caseid") or r.get("﻿caseid")
            meta[cid] = r
    rows = []
    for cid, p in per.items():
        if len(p["bs"]) < 40:
            continue
        m = meta.get(cid)
        if not m:
            continue
        try:
            age = float(m.get("age")); asa = float((m.get("asa") or "").strip()[0])
            bmi = float(m.get("bmi")); sex = 1.0 if (m.get("sex") or "").upper().startswith("M") else 0.0
        except Exception:
            continue
        if not (18 <= age <= 100):
            continue
        mbp = np.asarray(p["mbp"], float)
        if np.isfinite(mbp).sum() < 40:
            continue
        bs = np.asarray(p["bs"], float)
        rows.append(dict(cid=cid, age=age, asa=asa, bmi=bmi, sex=sex,
                         supp_min=float(np.sum(bs > 0)) * 0.5,
                         hypo_min=float(np.nansum(mbp < THRESH)) * 0.5,
                         ce=float(np.mean(p["ce"])), dur=len(bs) * 0.5))
    return rows


def fit(R, outcome, terms):
    n = len(R)
    X = [np.ones(n)] + [np.asarray([r[t] for r in R], float) for t in terms]
    X = np.column_stack(X)
    y = np.asarray([r[outcome] for r in R], float)
    try:
        return np.linalg.lstsq(X, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None


def run(R, adjust_duration=True):
    base = ["age10", "asa", "bmi", "sex", "ce"] + (["dur"] if adjust_duration else [])
    tot = fit(R, "hypo_min", base)
    med = fit(R, "hypo_min", base + ["supp_min"])
    apath = fit(R, "supp_min", base)
    if tot is None or med is None or apath is None:
        print("   fit failed"); return
    n = len(R)
    bt, bd, bp, ba = [], [], [], []
    for _ in range(NBOOT):
        idx = rng.integers(0, n, n)
        Rs = [R[i] for i in idx]
        t2 = fit(Rs, "hypo_min", base); m2 = fit(Rs, "hypo_min", base + ["supp_min"])
        a2 = fit(Rs, "supp_min", base)
        if t2 is None or m2 is None or a2 is None:
            continue
        bt.append(t2[1]); bd.append(m2[1]); ba.append(a2[1])
        if abs(t2[1]) > 1e-9:
            bp.append(100 * (1 - m2[1] / t2[1]))
    if len(bt) < 100:
        print("   bootstrap failed"); return
    lab = "with duration adjustment" if adjust_duration else "WITHOUT duration adjustment"
    print(f"\n--- {lab} ---")
    lo, hi = np.percentile(ba, [2.5, 97.5])
    print(f"   a-path  age -> suppression minutes   {apath[1]:+6.2f} min/decade [{lo:+6.2f},{hi:+6.2f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}   [at matched dose]")
    lo, hi = np.percentile(bt, [2.5, 97.5])
    print(f"   TOTAL   age -> hypotensive minutes   {tot[1]:+6.2f} min/decade [{lo:+6.2f},{hi:+6.2f}] "
          f"{'*' if (lo>0 or hi<0) else 'ns'}")
    lo2, hi2 = np.percentile(bd, [2.5, 97.5])
    print(f"   DIRECT  (further adj suppression)    {med[1]:+6.2f} min/decade [{lo2:+6.2f},{hi2:+6.2f}] "
          f"{'*' if (lo2>0 or hi2<0) else 'ns'}")
    if (lo > 0 or hi < 0) and len(bp) > 200:
        p = np.array([x for x in bp if np.isfinite(x)])
        pl, ph = np.percentile(p, [2.5, 97.5])
        print(f"   proportion of the age effect mediated by suppression: {np.median(p):.0f} % "
              f"[{pl:.0f} %,{ph:.0f} %]")
    else:
        print("   proportion mediated NOT reported -- it is a ratio and needs a clearly non-null total effect.")


def main():
    R = build()
    for r in R:
        r["age10"] = r["age"] / 10.0
    n = len(R)
    if n < 300:
        print(f"insufficient cases ({n})"); return
    print(f"cases: {n}   median age {np.median([r['age'] for r in R]):.0f}")
    print(f"   suppression minutes: median {np.median([r['supp_min'] for r in R]):.1f}")
    print(f"   hypotensive minutes: median {np.median([r['hypo_min'] for r in R]):.1f}")
    print(f"   MAP filtered to [{MAP_LO},{MAP_HI}]; {NBOOT} case-level bootstrap replicates")
    print("   NOTE: this is a CASE-level estimator. Age cannot vary within a patient, so the within-case design")
    print("   used elsewhere in this project cannot address it, and between-patient confounding is back.")
    run(R, adjust_duration=True)
    run(R, adjust_duration=False)
    print("\n   Duration is both a confounder and partly a consequence of patient factors; both versions are")
    print("   shown so the reader can see how much of the result rests on that adjustment.")


if __name__ == "__main__":
    sys.exit(main())
