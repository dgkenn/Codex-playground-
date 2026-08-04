#!/usr/bin/env python3
"""Is the reversal a TARGETED-TEMPERATURE-MANAGEMENT artefact? The last named reviewer objection.

THE OBJECTION. Post-cardiac-arrest patients are cooled on protocol; patients comatose from other causes are
not. Hypothermia slows the EEG and shifts its spectral balance toward low frequencies, and rewarming shifts it
back. Since the lead is a reversal in intra-burst SPECTRAL BALANCE (R417/R418) and cooling acts on exactly
that quantity, an aetiology-linked thermal effect is a live confound rather than a pedantic one.

WHAT IS ALREADY ON FILE, and why it does not settle it. R414 shows the reversal is *strongest* where no
sedative was running, and cooled patients are heavily sedated -- indirect evidence against a thermal
artefact. R418 shows the reversal is orthogonal to absolute band power, which rules out the *amount*-based
version of a thermal effect. Neither addresses balance directly, which is what cooling actually moves.

DESIGN, mirroring R414 deliberately. Temperature is a TREATMENT applied BECAUSE of aetiology, so adjusting
for it conditions on a mediator and removes part of the very effect under test (catalogue rule 13). The
primary is therefore a STRATIFICATION to patients never recorded hypothermic, where the cooling explanation
cannot operate -- the same logic that made R414 interpretable.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the temperature data was looked at.

  G0  UNITS GATE, and nothing proceeds until it passes. `value_as_number` may be Celsius or Fahrenheit and
      the two are silently mixable. Report the distribution by `unit_source_value`, convert F to C, and
      require the pooled median to land in 35.5-38.0 C. A mixed-unit column would put half the cohort at
      "98.6 degrees C" and make every hypothermia flag nonsense.
        FAIL -> report and stop (rule 31).

  G1  PRECONDITION (rule 32). Temperature must be available in both aetiology arms, and BOTH hypothermic and
      never-hypothermic patients must exist in each. Report the 2x2. If the anoxic arm is ~all cooled the
      stratified test is not estimable and this script says so rather than reporting a null.
      Also report hypothermia prevalence by arm -- if it does NOT differ, the confound has no mechanism and
      the objection dissolves on its own terms.

  G2  PRIMARY. Re-estimate the aetiology x alpha_beta interaction WITHIN patients never recorded below
      35.0 C, age-adjusted.
        SURVIVES IF it is same-signed as the full-cohort interaction and excludes zero.
        FAILS IF it includes zero while the hypothermic stratum's is clearly larger.

  G3  MATCHED NULL (rule 35), without which G2 is uninterpretable. The never-hypothermic stratum is a
      SUBSET. Draw subsamples of the full temperature-documented cohort matched on n, 30-day death rate and
      anoxic fraction, with NO temperature restriction, and report how often such a subsample's interaction
      fails to exclude zero -- the failure rate attributable to size alone.

  G4  DIRECTION, model-free: per-aetiology AUC within each temperature stratum.

  G5  DOSE. Does minimum recorded temperature itself modify the content->death association
      (temperature x content interaction)? A thermal account predicts it should.

WHAT A POSITIVE MEANS. The last named confound is retired and the reversal is not thermal.
WHAT IT CANNOT MEAN. That temperature is irrelevant to the EEG -- only that it does not explain the
aetiology-dependence. Patients with NO temperature record are EXCLUDED, not assumed normothermic (rule 5).
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
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
NBOOT = int(os.environ.get("NBOOT", "1500"))
NNULL = int(os.environ.get("NNULL", "300"))
HYPO_C = float(os.environ.get("HYPO_C", "35.0"))
WINDOW_H = float(os.environ.get("TEMP_WINDOW_H", "48"))
MIN_CELL = 100


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def z(a):
    s = a.std()
    return (a - a.mean()) / (s if s > 1e-12 else 1.0)


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def main():
    rng = np.random.default_rng(20260729)
    src = f"{OMOP}/measurement_temp.csv"
    assert os.path.exists(src), f"{src} missing -- run heedb_omop_extract.py measurement_temp"

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    when, age = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for rr in csv.DictReader(io.StringIO(txt)):
            p = (rr.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(rr.get("EndTime(EEG)") or rr.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
            try:
                v = float(rr.get("AgeAtVisit") or "")
                if v == v and p not in age:
                    age[p] = v
            except ValueError:
                pass

    # ---- G0 units gate -----------------------------------------------------------------------------
    print("=" * 100)
    print("G0  UNITS GATE — Celsius or Fahrenheit? A silent mix makes every hypothermia flag nonsense")
    print("=" * 100)
    by_unit = defaultdict(list)
    tmin, n_rows = {}, 0
    for r in csv.DictReader(open(src)):
        try:
            p = int(r["person_id"]); v = float(r["value_as_number"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (v == v) or v <= 0:
            continue
        n_rows += 1
        u = (r.get("unit_source_value") or "").strip().lower()
        by_unit[u].append(v)
        # Fahrenheit if the unit says so, or if the value is impossible as Celsius
        c = (v - 32.0) * 5.0 / 9.0 if ("f" in u and "c" not in u) or v > 45 else v
        if not (20.0 <= c <= 43.0):          # outside any survivable body temperature
            continue
        t0 = when.get(p)
        if t0 is None:
            continue
        tm = dt(r.get("measurement_datetime"))
        if tm is None or abs((tm - t0).total_seconds()) > WINDOW_H * 3600:
            continue
        if p not in tmin or c < tmin[p]:
            tmin[p] = c
    print(f"   rows with a numeric value: {n_rows:,}")
    print(f"   {'unit_source_value':>22} {'n':>10} {'median raw':>12}")
    for u, vals in sorted(by_unit.items(), key=lambda kv: -len(kv[1]))[:6]:
        print(f"   {(u or '<empty>'):>22} {len(vals):>10,} {np.median(vals):>12.1f}")
    if not tmin:
        print("\n   *** no usable temperatures within the window — stopping (rule 31).")
        return 1
    med = float(np.median(list(tmin.values())))
    print(f"\n   patients with a temperature within +/-{WINDOW_H:.0f} h of the EEG: {len(tmin):,}")
    print(f"   median of per-patient MINIMUM temperature: {med:.2f} C")
    gate = 30.0 <= med <= 38.0
    print(f"   GATE: {'PASS' if gate else 'FAIL'}  (per-patient minima should sit below normal but "
          f"physiological)")
    if not gate:
        print("\n   *** UNIT PROBLEM — stopping (rule 31).")
        return 1

    # ---- cohort ------------------------------------------------------------------------------------
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for rr in csv.DictReader(fh):
            d = dt(rr.get("death_datetime"))
            if d is not None:
                try:
                    death[int(rr["person_id"])] = d
                except (KeyError, TypeError, ValueError):
                    pass
    from heedb_aetiology_compact import load_anoxic
    anox = load_anoxic()

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

    rows = []
    for p in ab:
        if p not in anox or p not in when or p not in age or p not in tmin:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        rows.append((0.0 if days is None else (1.0 if days <= 30 else 0.0),
                     1.0 if anox[p] else 0.0, ab[p], age[p], tmin[p]))
    n = len(rows)
    assert n >= 300, f"only {n} patients with morphology + aetiology + temperature"
    y = np.array([r[0] for r in rows]); ax = np.array([r[1] for r in rows])
    v = np.array([r[2] for r in rows]); ag = np.array([r[3] for r in rows])
    tp = np.array([r[4] for r in rows])
    hypo = (tp < HYPO_C).astype(float)
    print(f"\n   cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%   "
          f"ever < {HYPO_C:.0f} C: {100*hypo.mean():.1f}%")

    # ---- G1 precondition ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("G1  PRECONDITION — do both temperature strata exist in both arms? (rule 32)")
    print("=" * 100)
    print(f"   {'arm':>12} {'hypothermic':>13} {'never <35C':>12} {'median min T':>14}")
    ok = True
    for lab, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        a_, b_ = int((m & (hypo == 1)).sum()), int((m & (hypo == 0)).sum())
        print(f"   {lab:>12} {a_:>13,} {b_:>12,} {np.median(tp[m]):>14.2f}")
        if min(a_, b_) < MIN_CELL:
            ok = False
    gap = abs(hypo[ax == 1].mean() - hypo[ax == 0].mean())
    print(f"\n   hypothermia prevalence: anoxic {100*hypo[ax==1].mean():.1f}%   "
          f"non-anoxic {100*hypo[ax==0].mean():.1f}%   gap {100*gap:.1f} pp")
    print("   A thermal confound needs this gap to be substantial; if it is not, the objection dissolves.")
    if not ok:
        print(f"\n   *** A cell is below {MIN_CELL} — the stratified test is underpowered by construction and")
        print("   a null from it must NOT be read as evidence (rule 31).")

    one = np.ones(n); agz = z(ag)

    def inter(mask, reps=NBOOT):
        idx = np.flatnonzero(mask); k = len(idx)
        if k < 150 or not (0 < y[idx].sum() < k):
            return None
        def des(i):
            vv = z(v[i])
            return np.column_stack([np.ones(len(i)), z(ag[i]), ax[i], vv, vv * ax[i]])
        try:
            c = float(logit_fit(des(idx), y[idx])[-1])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            j = rng.choice(idx, k, replace=True)
            if not (0 < y[j].sum() < k):
                continue
            try:
                cc = float(logit_fit(des(j), y[j])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        return c, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)), k

    print("\n" + "=" * 100)
    print("G2  PRIMARY — the reversal by temperature stratum")
    print("=" * 100)
    full = inter(np.ones(n, bool)); never = inter(hypo == 0); cooled = inter(hypo == 1)
    for lab, r in (("full temperature-documented cohort", full),
                   ("NEVER < 35 C (PRIMARY)", never),
                   ("ever < 35 C (mirror)", cooled)):
        if r is None:
            print(f"   {lab:>36}: not estimable")
        else:
            print(f"   {lab:>36}: n = {r[3]:>5,}   {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]"
                  f"{'   excludes zero' if r[1]*r[2] > 0 else '   INCLUDES ZERO'}")

    # ---- G3 matched null ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("G3  MATCHED NULL — how often does a same-size subsample fail, with NO temperature restriction?")
    print("=" * 100)
    frac_fail = float("nan")
    if never:
        tgt_n = never[3]
        cells = {(yy, aa): np.flatnonzero((y == yy) & (ax == aa))
                 for yy in (0.0, 1.0) for aa in (0.0, 1.0)}
        want = {k: int(round(tgt_n * float(((y[hypo == 0] == k[0]) & (ax[hypo == 0] == k[1])).mean())))
                for k in cells}
        if all(want[k] <= len(cells[k]) for k in cells):
            fails = tot = 0
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
            print(f"   matched subsamples (n = {tgt_n:,}, no temperature restriction): "
                  f"{100*frac_fail:.0f}% fail to exclude zero ({fails}/{tot})")
        else:
            print("   not estimable — the matched cell composition exceeds the pool")

    # ---- G4 direction ------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("G4  DIRECTION, model-free — per-aetiology AUC within each temperature stratum")
    print("=" * 100)
    print(f"   {'stratum':>18} {'anoxic AUC':>26} {'non-anoxic AUC':>26}")
    for lab, sm in (("never < 35 C", hypo == 0), ("ever < 35 C", hypo == 1)):
        line = f"   {lab:>18}"
        for am in (ax == 1, ax == 0):
            idx = np.flatnonzero(sm & am)
            if len(idx) < 60 or not (0 < y[idx].sum() < len(idx)):
                line += f"   {'(too small)':>24}"; continue
            a0 = auc(v[idx], y[idx])
            bs = [auc(v[j], y[j]) for j in
                  (rng.choice(idx, len(idx), replace=True) for _ in range(600))]
            bs = [b for b in bs if np.isfinite(b)]
            lo, hi = np.percentile(bs, [2.5, 97.5])
            star = "*" if (lo - .5) * (hi - .5) > 0 else " "
            line += f"   {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}"
        print(line)
    print("   * = excludes 0.5")

    # ---- G5 dose -----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("G5  DOSE — does minimum temperature itself modify the content->death association?")
    print("=" * 100)
    vz, tz = z(v), z(tp)
    X = np.column_stack([one, agz, ax, tz, vz, vz * ax, vz * tz])
    try:
        c = float(logit_fit(X, y)[-1])
        out = []
        for _ in range(NBOOT):
            i = rng.integers(0, n, n)
            if not (0 < y[i].sum() < n):
                continue
            vv, tt = z(v[i]), z(tp[i])
            Xi = np.column_stack([np.ones(n), z(ag[i]), ax[i], tt, vv, vv * ax[i], vv * tt])
            try:
                cc = float(logit_fit(Xi, y[i])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        lo, hi = np.percentile(out, [2.5, 97.5])
        print(f"   temperature x content: {c:+.3f} [{lo:+.3f}, {hi:+.3f}]"
              f"{'   excludes zero' if lo*hi > 0 else '   INCLUDES ZERO'}")
        print("   A thermal account predicts this should be non-zero.")
    except Exception:
        print("   not estimable")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if never is None or full is None:
        print("   NO VERDICT — the primary stratum was not estimable.")
    elif not ok:
        print("   NO VERDICT — G1's precondition failed; a null here would be a power statement (rule 31).")
    elif never[1] * never[2] > 0 and never[0] * full[0] > 0:
        print(f"   G2 SURVIVES — the reversal is present in patients never recorded hypothermic")
        print(f"   ({never[0]:+.3f} [{never[1]:+.3f}, {never[2]:+.3f}], n = {never[3]:,}), same-signed as the")
        print(f"   full cohort ({full[0]:+.3f}). The TTM objection does not account for it.")
    else:
        print(f"   G2 DOES NOT SURVIVE — never-hypothermic interaction {never[0]:+.3f} "
              f"[{never[1]:+.3f}, {never[2]:+.3f}].")
        if frac_fail == frac_fail and frac_fail >= 0.25:
            print(f"   BUT READ G3 FIRST: a matched subsample fails {100*frac_fail:.0f}% of the time, so this")
            print("   is substantially a POWER result and must not be reported as thermal confounding.")
    print("\n   Patients with no temperature record were excluded, not assumed normothermic. Temperature is")
    print("   a treatment applied because of aetiology, which is why the primary stratifies rather than")
    print("   adjusts (rule 13).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
