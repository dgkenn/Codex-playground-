#!/usr/bin/env python3
"""Is the aetiology reversal a PROPOFOL artefact? This is the largest untested objection to the lead.

THE OBJECTION, stated as a reviewer would. The lead's measure is intra-burst **8-30 Hz** content, and 8-30 Hz
is very close to what GABAergic anaesthetics manufacture: propofol produces frontal alpha and beta, and the
barbiturates and benzodiazepines produce beta. So intra-burst 8-30 Hz content may be, in substantial part, a
pharmacodynamic signature of the drug in the patient rather than a property of the injured brain.

**And sedation practice differs systematically by aetiology.** Post-cardiac-arrest patients are sedated on
protocol for targeted temperature management; patients comatose from status epilepticus, hepatic failure or
sepsis are sedated for other reasons, to other depths, with other agents. A drug effect that differs between
those groups could manufacture an aetiology-dependent association with no neurophysiology involved at all.

WHY THIS HAS NOT BEEN TESTED. Sedation was checked against **suppression burden** (ledger ~line 504, active
infusion at EEG, n = 7,213 of 11,217 with drug data) and against the **clinician-flag residual** (~line 619,
"not accounted for by depth, morphology, persistence, comorbidity, sedation, withdrawal, or scale"). Both
predate R389. The reversal itself has never been put through it.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  D0  PRECONDITION (catalogue rule 32). The stratified test needs BOTH sedated and unsedated patients in BOTH
      aetiology arms. Report the 2x2. If any cell is too small the primary test is impossible and this script
      must say so rather than report an underpowered null as a negative.

  D1  IS THERE A CONFOUNDING PATHWAY AT ALL? Report active-sedation prevalence by aetiology, and mean
      intra-burst content by sedation status within each arm. A confound needs sedation to differ by aetiology
      AND to shift the measure. If neither holds, the objection dissolves on its own terms.

  D2  PRIMARY, and it is DECISIVE. Re-estimate the aetiology x content interaction **within the NOT-ACTIVELY-
      SEDATED stratum**, where a BS-capable agent was not running at the EEG.
      **Stratification, not adjustment, and the choice is deliberate.** Sedation may be a MEDIATOR
      (aetiology -> sedation practice -> intra-burst content), and conditioning on a mediator removes part of
      the very effect being tested — catalogue rule 13. Restricting to patients in whom the drug cannot be
      acting asks a clean question instead.
        SURVIVES IF the unsedated interaction is same-signed as the full-cohort one and excludes zero.
        FAILS IF it includes zero AND the actively-sedated stratum's interaction is clearly larger — the
        effect would then live only where the drug is.

  D3  MATCHED NULL, and without it D2 is uninterpretable (catalogue rule 35). The unsedated stratum is a
      SUBSET, so it has less power by construction. Draw subsamples of the FULL drug-documented cohort
      matched on n, 30-day death rate and anoxic fraction, with NO sedation restriction, and report how often
      such a subsample's interaction fails to exclude zero. That is the failure rate attributable to size
      alone.

  D4  DIRECTION, model-free: per-aetiology AUC within each sedation stratum, so a reversal is shown rather
      than inferred from a coefficient.

  D5  MIRROR. The same interaction within the ACTIVELY SEDATED stratum. Under the drug explanation the effect
      should be concentrated there; under the neurophysiological one it should appear in both.

WHAT A POSITIVE MEANS. That the reversal is present where the drug is not, which retires the single most
obvious pharmacological objection to the lead.
WHAT IT CANNOT MEAN. That no drug contributes. OMOP carries administration records, not infusion rates or
plasma levels, and "not actively sedated" means no BS-capable agent recorded as running at the EEG — residual
drug from earlier administration is invisible here. Patients with NO drug data are EXCLUDED rather than
assumed unsedated, because "no infusion" and "not extracted" are different things (catalogue rule 5).
"""
import csv, glob, io, os, sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()
from icare_morph_replication import logit_fit

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OMOP_Q = os.environ.get("OMOP_QUANT", "/tmp/eeg_probe/heedb_omop_quant")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1500"))
NNULL = int(os.environ.get("NNULL", "300"))
LEAD_H = float(os.environ.get("LEAD_H", "4"))
BS_CAPABLE = ("propofol", "midazolam", "pentobarbital", "thiopental", "phenobarbital")
MIN_CELL = 120


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def main():
    rng = np.random.default_rng(20260729)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    # Aetiology via the compact derived table (~1 MB) rather than the 3.3 GB condition table. Identical
    # reduction, same AETIOLOGY prefixes and same norm(), and it builds itself from the big table on first
    # use. The big file has been reaped by the container twice in one session; this makes that cheap.
    from heedb_aetiology_compact import load_anoxic
    anox = load_anoxic()

    # --- sedation, reusing heedb_infusion_at_eeg.py's validated ACTIVE definition -------------------
    sed_path = f"{OMOP}/drug_sedatives.csv"
    assert os.path.exists(sed_path), f"{sed_path} missing -- rebuild with heedb_omop_extract.py drug_sedatives"
    active, seen_drug = set(), set()
    for r in csv.DictReader(open(sed_path)):
        v = (r.get("drug_source_value") or "").lower()
        if not any(x in v for x in BS_CAPABLE):
            continue
        try:
            p = int(r["person_id"])
        except (KeyError, TypeError, ValueError):
            continue
        seen_drug.add(p)
        t0 = when.get(p)
        if t0 is None:
            continue
        s = dt(r.get("drug_exposure_start_datetime"))
        e = dt(r.get("drug_exposure_end_datetime"))
        if s is None:
            continue
        if e is not None and s <= t0 <= e:
            active.add(p)
        elif -LEAD_H * 3600 <= (t0 - s).total_seconds() <= LEAD_H * 3600:
            active.add(p)

    ab = defaultdict(list)
    for path in sorted(glob.glob(MORPH)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            try:
                v = float(r["alpha_beta"])
            except (KeyError, TypeError, ValueError):
                continue
            if p.isdigit() and v == v:
                ab[int(p)].append(v)
    ab = {p: float(np.median(v)) for p, v in ab.items()}
    assert len(ab) > 500, f"morphology cache looks empty: {len(ab)}"

    rows = []
    for p, v in ab.items():
        # require drug DATA, else "not sedated" silently absorbs "never extracted" (rule 5)
        if p not in seen_drug or p not in anox or p not in when or p not in death:
            continue
        days = (death[p] - when[p]).days
        if days < -1:
            continue
        rows.append((1.0 if days <= 30 else 0.0, 1.0 if anox[p] else 0.0,
                     1.0 if p in active else 0.0, v))
    n = len(rows)
    y = np.array([r[0] for r in rows])
    ax = np.array([r[1] for r in rows])
    sd = np.array([r[2] for r in rows])
    v = np.array([r[3] for r in rows])
    print(f"cohort with morphology + aetiology + DRUG DATA + ascertained death: {n:,}")
    print(f"   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%   "
          f"actively sedated at EEG {100*sd.mean():.1f}%")
    assert n >= 300, f"only {n} patients -- an empty join is not a result"

    # ---- D0 precondition ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("D0  PRECONDITION — is the stratified test even possible? (rule 32)")
    print("=" * 100)
    print(f"   {'':>14} {'sedated':>10} {'not sedated':>13} {'death% sed':>12} {'death% unsed':>14}")
    ok = True
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        a = int((m & (sd == 1)).sum()); b = int((m & (sd == 0)).sum())
        ds = 100 * y[m & (sd == 1)].mean() if a else float("nan")
        du = 100 * y[m & (sd == 0)].mean() if b else float("nan")
        print(f"   {lab:>14} {a:>10,} {b:>13,} {ds:>11.1f}% {du:>13.1f}%")
        if min(a, b) < MIN_CELL:
            ok = False
    if not ok:
        print(f"\n   *** A cell is below {MIN_CELL}. The primary test is UNDERPOWERED BY CONSTRUCTION and")
        print("   any null it returns must NOT be read as evidence against the reversal.")

    # ---- D1 confounding pathway --------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("D1  IS THERE A CONFOUNDING PATHWAY? sedation must differ by aetiology AND shift the measure")
    print("=" * 100)
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        print(f"   {lab:>12}: actively sedated {100*sd[m].mean():>5.1f}%   "
              f"intra-burst content  sedated {v[m & (sd == 1)].mean():>7.4f}   "
              f"unsedated {v[m & (sd == 0)].mean():>7.4f}")
    gap = abs(sd[ax == 1].mean() - sd[ax == 0].mean())
    shift = abs(v[sd == 1].mean() - v[sd == 0].mean()) / (v.std() if v.std() > 0 else 1)
    print(f"\n   sedation prevalence gap between arms: {100*gap:.1f} pp")
    print(f"   sedation's shift in the measure: {shift:.3f} SD")
    print("   Both must be non-trivial for the drug objection to have a mechanism.")

    # ---- interaction machinery ---------------------------------------------------------------------
    def inter(mask, reps=NBOOT):
        idx = np.flatnonzero(mask)
        k = len(idx)
        if k < 150 or not (0 < y[idx].sum() < k):
            return None
        X = np.column_stack([np.ones(k), ax[idx], v[idx], v[idx] * ax[idx]])
        try:
            c = float(logit_fit(X, y[idx])[3])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            j = rng.choice(idx, k, replace=True)
            if not (0 < y[j].sum() < k):
                continue
            Xi = np.column_stack([np.ones(k), ax[j], v[j], v[j] * ax[j]])
            try:
                cc = float(logit_fit(Xi, y[j])[3])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        lo, hi = np.percentile(out, [2.5, 97.5])
        return c, float(lo), float(hi), k

    print("\n" + "=" * 100)
    print("D2 / D5  THE REVERSAL BY SEDATION STRATUM")
    print("=" * 100)
    full = inter(np.ones(n, bool))
    uns = inter(sd == 0)
    sed = inter(sd == 1)
    for lab, r in (("full drug-documented cohort", full),
                   ("NOT actively sedated (PRIMARY)", uns),
                   ("actively sedated (mirror)", sed)):
        if r is None:
            print(f"   {lab:>32}: not estimable")
        else:
            c, lo, hi, k = r
            print(f"   {lab:>32}: n = {k:>5,}   interaction {c:+.3f} [{lo:+.3f}, {hi:+.3f}]"
                  f"{'   excludes zero' if lo * hi > 0 else '   INCLUDES ZERO'}")

    # ---- D3 matched null ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("D3  MATCHED NULL — how often does a same-size subsample FAIL, with no sedation restriction?")
    print("=" * 100)
    verdict_note = ""
    if uns is None:
        print("   not applicable — the unsedated stratum was not estimable")
        frac_fail = float("nan")
    else:
        tgt_n = uns[3]
        tgt_e = float(y[sd == 0].mean())
        tgt_a = float(ax[sd == 0].mean())
        cells = {(yy, aa): np.flatnonzero((y == yy) & (ax == aa))
                 for yy in (0.0, 1.0) for aa in (0.0, 1.0)}
        want = {k: int(round(tgt_n * float(((y[sd == 0] == k[0]) & (ax[sd == 0] == k[1])).mean())))
                for k in cells}
        fails = tot = 0
        if all(want[k] <= len(cells[k]) for k in cells):
            for _ in range(NNULL):
                idx = np.concatenate([rng.choice(cells[k], want[k], replace=False)
                                      for k in cells if want[k] > 0])
                m = np.zeros(n, bool); m[idx] = True
                r = inter(m, reps=250)
                if r is None:
                    continue
                tot += 1
                if r[1] * r[2] <= 0:
                    fails += 1
            frac_fail = fails / tot if tot else float("nan")
            print(f"   matched subsamples (n = {tgt_n:,}, death {100*tgt_e:.1f}%, anoxic {100*tgt_a:.1f}%,"
                  f" NO sedation restriction)")
            print(f"   fraction whose interaction FAILS to exclude zero: {100*frac_fail:.0f}%  "
                  f"({fails}/{tot})")
            verdict_note = (f"a same-size random subsample fails {100*frac_fail:.0f}% of the time")
        else:
            frac_fail = float("nan")
            print("   not estimable — the matched cell composition exceeds the pool")

    # ---- D4 direction ------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("D4  DIRECTION, model-free — per-aetiology AUC within each sedation stratum")
    print("=" * 100)
    print(f"   {'stratum':>20} {'anoxic AUC':>26} {'non-anoxic AUC':>26}")
    for lab, sm in (("not sedated", sd == 0), ("actively sedated", sd == 1)):
        line = f"   {lab:>20}"
        for am in (ax == 1, ax == 0):
            idx = np.flatnonzero(sm & am)
            if len(idx) < 60 or not (0 < y[idx].sum() < len(idx)):
                line += f"   {'(too small)':>24}"
                continue
            a0 = auc(v[idx], y[idx])
            bs = []
            for _ in range(800):
                j = rng.choice(idx, len(idx), replace=True)
                a1 = auc(v[j], y[j])
                if np.isfinite(a1):
                    bs.append(a1)
            lo, hi = np.percentile(bs, [2.5, 97.5])
            star = "*" if (lo - .5) * (hi - .5) > 0 else " "
            line += f"   {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}"
        print(line)
    print("   * = excludes 0.5.  A reversal means the two arms sit on OPPOSITE sides.")

    # ---- verdict -----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if uns is None or full is None:
        print("   NO VERDICT — the primary stratum was not estimable.")
    elif not ok:
        print("   NO VERDICT — D0's precondition failed; this stratum cannot support a decisive test")
        print("   and a null here would be a power statement, not a biological one (rule 31).")
    elif uns[1] * uns[2] > 0 and uns[0] * full[0] > 0:
        print(f"   D2 SURVIVES — the reversal is present where no BS-capable sedative was running")
        print(f"   ({uns[0]:+.3f} [{uns[1]:+.3f}, {uns[2]:+.3f}], n = {uns[3]:,}), same-signed as the full")
        print(f"   cohort ({full[0]:+.3f}). The propofol objection does not account for it.")
    else:
        print(f"   D2 DOES NOT SURVIVE — the unsedated interaction is {uns[0]:+.3f} "
              f"[{uns[1]:+.3f}, {uns[2]:+.3f}].")
        if frac_fail == frac_fail and frac_fail >= 0.25:
            print(f"   BUT READ D3 FIRST: {verdict_note}, so this is substantially a POWER result and")
            print("   must not be reported as the reversal being drug-driven.")
        else:
            print(f"   D3 says a matched subsample fails only {100*frac_fail:.0f}% of the time, so size does")
            print("   not explain it. The drug explanation gains real support and the lead is in trouble.")
    print("\n   Limits: OMOP records administrations, not infusion rates or plasma levels; residual drug")
    print("   from earlier dosing is invisible. Patients without drug data were excluded, not assumed")
    print("   unsedated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
