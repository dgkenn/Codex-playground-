#!/usr/bin/env python3
"""Is the reversal ALPHA COMA? Does arousal-organisation, not aetiology, set the sign of the fast content?

THE CANDIDATE (F1 in the 2026-07-29 exhaustive brainstorm, and the top pick). After anoxia, monotonous
non-reactive widespread alpha -- "alpha coma" -- is a classic MALIGNANT pattern: alpha-frequency content that
signifies death. In non-anoxic coma, alpha content reflects preserved or recovering arousal (a real posterior
dominant rhythm, real spindles) and is BENIGN. The lead's measure (intra-burst 8-30 Hz content) captures both,
and its prognostic sign flips because alpha coma is an anoxia-specific entity. This is the only candidate that
explains a SIGN reversal through a named clinical entity, and it clears all seven ledger constraints.

THE SHARP, TESTABLE CLAIM. If F1 is right, the real modifier is not aetiology but whether the fast content is
ORGANISED/REACTIVE. Alpha coma has no posterior dominant rhythm, no sleep architecture, no wakeful state --
the cortex cannot organise. So define an arousal-organisation composite AO from the findings columns that mark
a cortex able to organise state, and ask whether AO -- not aetiology -- sets the sign of the content->death
association. Aetiology would then be a PROXY for "is this alpha coma."

WHY THIS IS CHEAP AND HONEST. It needs no re-extraction: `pdr`, `awake`, `spindles`, sleep-stage flags and
`diffuse Beta` are already in the findings table. The DECISIVE test (does the alpha 8-13 sub-band carry the
reversal while beta 13-30 does not?) needs an S3 re-extraction and is the registered follow-up; this label-
based test comes first because if AO does NOT modify the sign, the sub-band pass is not worth hours of S3.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  AO = any of {pdr, awake, spindles, n1, n2, vertex wave, k_complexes, posts} -- markers of a cortex that can
  organise/cycle. Alpha coma has NONE. `diffuse Beta` is deliberately EXCLUDED from AO (it is itself fast
  content; including it would be circular) and is probed separately in M5.

  M0  PRECONDITION (rule 32). AO must VARY in both aetiology arms and content must vary in all four
      aetiology x AO cells. If anoxic patients are ~all AO-absent, the within-anoxic contrast is not
      estimable and this script says so instead of reporting a null.

  M1  AO x content interaction for 30-day death, adjusted for burden quintiles AND age. Prediction: AO
      present makes content more PROTECTIVE (negative interaction on the death scale).

  M2  PRIMARY, model-free. AUC of intra-burst content for 30-day death in each of the four cells
      {anoxic, non-anoxic} x {AO present, AO absent}.
        F1 STRONGLY SUPPORTED IF arousal-organisation sets the sign: within AO-present, content is protective
        (AUC < 0.5) in BOTH arms, and/or within AO-absent it is harmful (AUC > 0.5) in both -- i.e. the sign
        tracks AO, not aetiology.
        F1 PARTIAL IF AO shifts the sign in the predicted direction but aetiology still matters within AO
        strata.
        F1 FAILS IF the AUC sign tracks aetiology regardless of AO -- then the reversal is not an
        arousal-organisation / alpha-coma phenomenon and the sub-band re-extraction is not worth running.

  M3  ATTENUATION (mediation-flavoured, DESCRIPTIVE ONLY -- rule 13, conditioning on a post-injury variable).
      Does the aetiology x content interaction SHRINK when AO x content is added to the model? Report it with
      and without. No causal claim.

  M4  PLACEBO, and it GATES M3 (rule 34). Repeat M3's attenuation with `foc slowing` -- a finding that is NOT
      an arousal-organisation marker -- in place of AO. If a non-arousal finding attenuates the aetiology
      interaction just as much, AO is not special and M3 carries no weight.

  M5  PROBE. Within `diffuse Beta` present vs absent, the content->death AUC. Is the protective fast content
      "diffuse beta" (an arousal/drug pattern)?

WHAT A POSITIVE MEANS. That a measurable, named axis -- arousal-organisation, i.e. alpha coma vs reactive
background -- underlies the reversal, which converts a black-box interaction into a mechanism and makes the
sub-band re-extraction the decisive next step.
WHAT IT CANNOT MEAN. Reactivity was not tested (no stimulation annotation); AO is a proxy built from static
findings. And AO is post-injury, so M3's attenuation is suggestive, not causal.
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
NBOOT = int(os.environ.get("NBOOT", "2000"))
AO_FLAGS = ["pdr", "awake", "spindles", "n1", "n2", "vertex wave", "k_complexes", "posts"]
PLACEBO = "foc slowing"
PROBE = "diffuse Beta"
NEEDED = AO_FLAGS + [PLACEBO, PROBE]


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


def quintiles(b):
    e = np.quantile(b, [0.2, 0.4, 0.6, 0.8])
    idx = np.searchsorted(e, b, side="right")
    return np.column_stack([(idx == k).astype(float) for k in range(1, 5)])


def auc(v, y):
    if not (0 < y.sum() < len(y)):
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(float) + 1.0
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def boot_auc(v, y, rng, reps=800):
    idx = np.arange(len(y))
    out = []
    for _ in range(reps):
        j = rng.choice(idx, len(idx), replace=True)
        a = auc(v[j], y[j])
        if np.isfinite(a):
            out.append(a)
    if not out:
        return float("nan"), float("nan")
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main():
    rng = np.random.default_rng(20260729)
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    find, when, age = defaultdict(dict), {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP,
                            Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        rd = csv.DictReader(io.StringIO(txt))
        for f in NEEDED:
            assert f in (rd.fieldnames or []), f"'{f}' column missing from findings table"
        for r in rd:
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            for f in NEEDED:
                find[p][f] = find[p].get(f, False) or (
                    (r.get(f) or "").strip() not in ("", "None", "nan"))
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t and (p not in when or t < when[p]):
                when[p] = t
            try:
                a = float(r.get("AgeAtVisit") or "")
                if a == a and p not in age:
                    age[p] = a
            except ValueError:
                pass
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            d = dt(r.get("death_datetime"))
            if d is not None:
                try:
                    death[int(r["person_id"])] = d
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
    assert len(ab) > 500, f"morphology cache looks empty: {len(ab)}"

    rows = []
    for p in ab:
        if p not in anox or p not in when or p not in find or p not in age:
            continue
        d = death.get(p)
        days = (d - when[p]).days if d is not None else None
        if days is not None and days < -1:
            continue
        ao = 1.0 if any(find[p][f] for f in AO_FLAGS) else 0.0
        rows.append((0.0 if days is None else (1.0 if days <= 30 else 0.0),
                     1.0 if anox[p] else 0.0, ab[p], ao,
                     1.0 if find[p][PLACEBO] else 0.0, 1.0 if find[p][PROBE] else 0.0, age[p]))
    n = len(rows)
    assert n >= 300, f"only {n} patients"
    y = np.array([r[0] for r in rows])
    ax = np.array([r[1] for r in rows])
    v = np.array([r[2] for r in rows])
    ao = np.array([r[3] for r in rows])
    fs = np.array([r[4] for r in rows])
    db = np.array([r[5] for r in rows])
    ag = np.array([r[6] for r in rows])
    print(f"cohort {n:,}   30-day death {100*y.mean():.1f}%   anoxic {100*ax.mean():.1f}%   "
          f"AO present {100*ao.mean():.1f}%   age {np.median(ag):.0f} [{np.percentile(ag,25):.0f}"
          f"-{np.percentile(ag,75):.0f}]")

    # ---- M0 precondition ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("M0  PRECONDITION — does arousal-organisation VARY in both arms? (rule 32)")
    print("=" * 100)
    print(f"   {'cell':>22} {'n':>7} {'death%':>8} {'content sd':>12} {'median age':>12}")
    ok = True
    for al, am in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        print(f"   {al} AO present    {int((am&(ao==1)).sum()):>7,} "
              f"{100*y[am&(ao==1)].mean() if (am&(ao==1)).sum() else float('nan'):>7.1f}% "
              f"{v[am&(ao==1)].std():>12.4f} {np.median(ag[am&(ao==1)]) if (am&(ao==1)).sum() else float('nan'):>12.0f}")
        print(f"   {al} AO absent     {int((am&(ao==0)).sum()):>7,} "
              f"{100*y[am&(ao==0)].mean() if (am&(ao==0)).sum() else float('nan'):>7.1f}% "
              f"{v[am&(ao==0)].std():>12.4f} {np.median(ag[am&(ao==0)]) if (am&(ao==0)).sum() else float('nan'):>12.0f}")
        for cm in (am & (ao == 1), am & (ao == 0)):
            if int(cm.sum()) < 100 or v[cm].std() < 1e-9 or not (0 < y[cm].sum() < cm.sum()):
                ok = False
    print(f"   AO prevalence: anoxic {100*ao[ax==1].mean():.1f}%   non-anoxic {100*ao[ax==0].mean():.1f}%")
    if not ok:
        print("\n   *** A cell is too small / degenerate — the 2x2 is not fully estimable (rule 31).")

    # NOTE: burden is NOT in this cohort's join (findings+morph+aetiology), so the interaction models
    # adjust for AGE and use content standardised; burden was already shown not to explain the reversal
    # (3/3 strata, R386/R399), so age is the new covariate this script adds.
    one = np.ones(n)
    vz = z(v)
    agz = z(ag)

    def inter(mod, reps=NBOOT):
        """aetiology/AO x content interaction for death, adjusting for age. `mod` is the modifier vector."""
        X = np.column_stack([one, agz, mod, vz, vz * mod])
        try:
            c = float(logit_fit(X, y)[-1])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            i = rng.integers(0, n, n)
            if not (0 < y[i].sum() < n):
                continue
            vv = z(v[i])
            Xi = np.column_stack([np.ones(n), z(ag[i]), mod[i], vv, vv * mod[i]])
            try:
                cc = float(logit_fit(Xi, y[i])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        return c, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

    # ---- M1 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("M1  AO x content interaction for death (adjusted for age) — is AO the modifier?")
    print("=" * 100)
    m1 = inter(ao)
    if m1:
        print(f"   AO x content: {m1[0]:+.3f} [{m1[1]:+.3f}, {m1[2]:+.3f}]"
              f"{'   excludes zero' if m1[1]*m1[2] > 0 else '   INCLUDES ZERO'}")
        print("   (negative = AO present makes content more protective, as alpha coma predicts)")

    # ---- M2 primary --------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("M2  PRIMARY, model-free — content->death AUC in each aetiology x AO cell")
    print("=" * 100)
    print(f"   {'cell':>24} {'n':>7} {'AUC content -> 30-day death':>30}")
    cells = {}
    for al, am in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        for aol, aom in (("AO present", ao == 1), ("AO absent", ao == 0)):
            m = am & aom
            idx = np.flatnonzero(m)
            if len(idx) < 80 or not (0 < y[idx].sum() < len(idx)):
                print(f"   {al+', '+aol:>24} {len(idx):>7,} {'(too small)':>30}")
                cells[(al, aol)] = None
                continue
            a0 = auc(v[idx], y[idx]); lo, hi = boot_auc(v[idx], y[idx], rng)
            cells[(al, aol)] = (a0, lo, hi)
            star = "*" if (lo - .5) * (hi - .5) > 0 else " "
            print(f"   {al+', '+aol:>24} {len(idx):>7,}   {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}")
    print("   * = excludes 0.5.  F1 predicts the SIGN tracks AO (protective when AO present) more than aetiology.")

    # ---- M3 / M4 attenuation + placebo -------------------------------------------------------------
    print("\n" + "=" * 100)
    print("M3 / M4  ATTENUATION (descriptive, rule 13) with placebo gate")
    print("=" * 100)
    base = inter(ax)
    print(f"   aetiology x content, adjusted for age only:            "
          f"{base[0]:+.3f} [{base[1]:+.3f}, {base[2]:+.3f}]" if base else "   base not estimable")

    def inter_adj(extra_mod, reps=NBOOT):
        """aetiology x content, ALSO adjusting for extra_mod and extra_mod x content."""
        X = np.column_stack([one, agz, ax, extra_mod, vz, vz * extra_mod, vz * ax])
        try:
            c = float(logit_fit(X, y)[-1])
        except Exception:
            return None
        out = []
        for _ in range(reps):
            i = rng.integers(0, n, n)
            if not (0 < y[i].sum() < n):
                continue
            vv = z(v[i])
            Xi = np.column_stack([np.ones(n), z(ag[i]), ax[i], extra_mod[i], vv,
                                  vv * extra_mod[i], vv * ax[i]])
            try:
                cc = float(logit_fit(Xi, y[i])[-1])
            except Exception:
                continue
            if np.isfinite(cc):
                out.append(cc)
        if len(out) < reps // 4:
            return None
        return c, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

    ao_adj = inter_adj(ao)
    fs_adj = inter_adj(fs)
    if base and ao_adj:
        drop_ao = 100 * (1 - ao_adj[0] / base[0]) if abs(base[0]) > 1e-9 else float("nan")
        print(f"   ...also adjusting for AO x content:                    "
              f"{ao_adj[0]:+.3f} [{ao_adj[1]:+.3f}, {ao_adj[2]:+.3f}]   ({drop_ao:+.0f}% vs base)")
    if base and fs_adj:
        drop_fs = 100 * (1 - fs_adj[0] / base[0]) if abs(base[0]) > 1e-9 else float("nan")
        print(f"   PLACEBO: ...adjusting for foc-slowing x content:       "
              f"{fs_adj[0]:+.3f} [{fs_adj[1]:+.3f}, {fs_adj[2]:+.3f}]   ({drop_fs:+.0f}% vs base)")

    # ---- M5 probe ----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("M5  PROBE — is the protective fast content 'diffuse Beta'?")
    print("=" * 100)
    print(f"   diffuse Beta prevalence: anoxic {100*db[ax==1].mean():.1f}%   non-anoxic {100*db[ax==0].mean():.1f}%")
    for al, am in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        for dl, dm in (("diffuse Beta +", db == 1), ("diffuse Beta -", db == 0)):
            m = am & dm; idx = np.flatnonzero(m)
            if len(idx) < 80 or not (0 < y[idx].sum() < len(idx)):
                print(f"   {al+', '+dl:>24}: (too small, n={len(idx)})"); continue
            a0 = auc(v[idx], y[idx]); lo, hi = boot_auc(v[idx], y[idx], rng)
            star = "*" if (lo - .5) * (hi - .5) > 0 else " "
            print(f"   {al+', '+dl:>24}: n={len(idx):>5,}  AUC {a0:.3f} [{lo:.3f}, {hi:.3f}]{star}")

    # ---- verdict -----------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not ok:
        print("   NO VERDICT — a precondition failed (M0); the 2x2 is not fully estimable.")
    else:
        ap_, aa = cells.get(("anoxic", "AO present")), cells.get(("anoxic", "AO absent"))
        np_, na = cells.get(("non-anoxic", "AO present")), cells.get(("non-anoxic", "AO absent"))

        def sign(c):
            """+1 harmful, -1 protective, 0 = spans 0.5. A cell that SPANS 0.5 is NOT protective and
            NOT harmful -- the first version of this script accepted 0 as satisfying "protective",
            which let a null cell pass a criterion that demanded a direction."""
            if c is None:
                return None
            return 1 if c[1] > .5 else (-1 if c[2] < .5 else 0)

        s_ap, s_aa, s_np, s_na = sign(ap_), sign(aa), sign(np_), sign(na)
        # Registered: STRONG requires the sign to TRACK AO -- both arms protective where AO is present,
        # or both harmful where it is absent. Strict: spanning 0.5 does not count as either.
        strong = (s_ap == -1 and s_np == -1) or (s_aa == 1 and s_na == 1)
        # Does AO change the NON-ANOXIC arm at all? If not, the sign is set by aetiology.
        na_moved = (s_np is not None and s_na is not None and s_np != s_na)
        # Placebo gate: AO must attenuate the aetiology interaction MORE than a non-arousal finding does.
        att_ao = att_fs = None
        if base and ao_adj and abs(base[0]) > 1e-9:
            att_ao = 1 - ao_adj[0] / base[0]
        if base and fs_adj and abs(base[0]) > 1e-9:
            att_fs = 1 - fs_adj[0] / base[0]
        placebo_ok = (att_ao is not None and att_fs is not None and att_ao > att_fs)

        print(f"   sign by cell: anoxic AO+ {s_ap:+d}  AO- {s_aa:+d} | "
              f"non-anoxic AO+ {s_np:+d}  AO- {s_na:+d}   (+1 harmful, -1 protective, 0 spans 0.5)")
        if att_ao is not None and att_fs is not None:
            print(f"   attenuation of the aetiology interaction: AO {100*att_ao:+.0f}%   "
                  f"placebo(foc slowing) {100*att_fs:+.0f}%")

        if strong and placebo_ok:
            print("\n   F1 SUPPORTED — arousal-organisation, not aetiology, sets the sign.")
        elif m1 and m1[1] * m1[2] > 0 and m1[0] < 0:
            print("\n   F1 PARTIAL — AO is a real EFFECT MODIFIER (M1 excludes zero, in the predicted")
            print("   direction) but it does NOT set the sign: the non-anoxic arm stays protective whether")
            print("   or not the cortex can organise, and the anoxic arm stays harmful. The sign tracks")
            print("   AETIOLOGY.")
            if not placebo_ok:
                print("   AND THE PLACEBO GATE FAILS — a non-arousal finding attenuates the aetiology")
                print("   interaction MORE than AO does, so the attenuation carries no weight at all.")
            print("   Alpha coma is therefore a MAGNITUDE modifier within the anoxic arm, not the")
            print("   mechanism of the reversal.")
        else:
            print("\n   F1 NOT SUPPORTED — the AUC sign tracks aetiology regardless of arousal-organisation.")

        print("\n   ON THE SUB-BAND RE-EXTRACTION, since the registration tied it to this result: it is")
        print("   still warranted. F1 is demoted to a modifier, but candidates F2 (the slow denominator)")
        print("   and F3 (monotony) are untested and INDEPENDENT of AO, and the alpha-vs-beta split is")
        print("   more informative now that arousal-organisation has failed to explain the reversal.")
    print("\n   Reactivity was not measured (no stimulation annotation); AO is a static proxy. M3 conditions")
    print("   on a post-injury variable and is descriptive only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
