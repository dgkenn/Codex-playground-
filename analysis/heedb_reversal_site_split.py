#!/usr/bin/env python3
"""Does the aetiology reversal hold independently at each HEEDB hospital?

WHY THIS AND NOT A TRUE EXTERNAL COHORT. The aetiology reversal (R389–R396) has one open weakness:
everything supporting it is HEEDB. The obvious fixes are unavailable and the reasons are recorded rather than
assumed. **I-CARE is entirely cardiac arrest**, so it cannot test a contrast *between* aetiologies at all --
only one arm of it. **TUH carries no outcome field and no diagnosis field** (manifest: recording_id,
patient_id, edf_path, sfreq, age, sex -- ledger R321), so approval to access it, granted 2026-07-27, changes
permission and not contents. No known cohort has EEG + outcome + mixed aetiology besides HEEDB.

So the strongest available test is the **hospital split inside HEEDB**, and this file is explicit that it is
internal validation rather than external replication. HEEDB's two sites have different equipment, different
technologists and different reading clinicians, so a finding present at both is not an artefact of one
hospital's practice -- but they are hospitals in the same regional academic network, which is exactly the
limitation L4 already records for I-CARE. **It is the best available evidence and it is not a second health
system.** A reader should be told that in the same sentence as the result.

------------------------------------------------------------------------------------------------------------
REGISTERED, before the data was looked at.

  H1  PRIMARY. The reversal appears INDEPENDENTLY at both sites: anoxic AUC above 0.5 and non-anoxic below
      0.5, at S0001 and at S0002 separately.
      CONFIRMED IF both sites show the contrast in the same direction.
      FALSIFIED IF it appears at one site only -- in which case the finding is one hospital's, and given that
      S0001 contributes roughly twice the recordings of S0002 that is a live possibility rather than a
      formality.

  H2  HETEROGENEITY, tested rather than eyeballed. Bootstrap the difference between sites in the aetiology
      gap (anoxic AUC minus non-anoxic AUC). If that difference's interval contains zero, the sites are
      consistent. Comparing two intervals by eye is the comparison-of-significance error this project has
      committed before, so it is done properly here.

  H3  COMPOSITION. Report each site's aetiology mix, burden distribution and death rate, so that any
      difference between them can be interpreted rather than guessed at.

COHORT. The R393 convention is primary: no death-ascertainment conditioning, an absent death record treated
as alive. The conditioned version (decedents only) is reported alongside, since the two have opposite
ascertainment biases and agreement across both is what makes either credible.
"""
import csv, glob, io, os, sys
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import auc

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s*.csv")
AETCACHE = os.environ.get("AET_CACHE", "/tmp/eeg_probe/heedb_aetiology.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))


def dt(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def load_morph():
    """Per patient: median alpha_beta, median burden, and the modal site."""
    ab, bur, sites = defaultdict(list), defaultdict(list), defaultdict(Counter)
    for path in sorted(glob.glob(MORPH)):
        for r in csv.DictReader(open(path)):
            p = (r.get("patient") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            for col, d in (("alpha_beta", ab), ("burden", bur)):
                try:
                    v = float(r[col])
                except (KeyError, TypeError, ValueError):
                    continue
                if v == v:
                    d[p].append(v)
            st = (r.get("site") or "").strip()
            if st:
                sites[p][st] += 1
    out = {}
    for p in ab:
        if p in bur and sites.get(p):
            out[p] = (float(np.median(ab[p])), float(np.median(bur[p])), sites[p].most_common(1)[0][0])
    return out


def build_or_load_anoxic():
    """Anoxic flag per patient, cached. Builds from the OMOP condition table if the cache is absent.

    The cache lives in /tmp, which does NOT survive container reclamation -- it was lost once mid-session
    while the 1 GB source table survived. Rebuilding takes about three minutes, so the script does it itself
    rather than failing and making the next session work out why.
    """
    if os.path.exists(AETCACHE):
        return {int(r["pid"]): r["anoxic"] == "1" for r in csv.DictReader(open(AETCACHE))}
    from heedb_bs_ascertainment import AETIOLOGY, norm
    print(f"   [{AETCACHE} absent — rebuilding from the OMOP condition table, ~3 min]", flush=True)
    out = {}
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except (KeyError, TypeError, ValueError):
                continue
            out.setdefault(p, False)
            c = norm(r.get("condition_source_value"))
            if c and any(c.startswith(x) for x in AETIOLOGY["anoxic"]):
                out[p] = True
    with open(AETCACHE, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pid", "anoxic"])
        for p, v in out.items():
            w.writerow([p, 1 if v else 0])
    print(f"   [rebuilt: {len(out):,} patients, {sum(out.values()):,} anoxic]", flush=True)
    return out


def auc_ci(y, s, rng, reps):
    n = len(y); o = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if 0 < y[i].sum() < n:
            a = auc(y[i], s[i])
            if a == a:
                o.append(a)
    if len(o) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(o, [2.5, 97.5]))


def gap_boot(y, a, ax, rng, reps):
    """Bootstrap the aetiology gap (anoxic AUC - non-anoxic AUC) within one site."""
    n = len(y); out = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        ya, aa, xa = y[i], a[i], ax[i]
        m1, m0 = xa == 1, xa == 0
        if m1.sum() < 40 or m0.sum() < 40:
            continue
        if not (0 < ya[m1].sum() < m1.sum()) or not (0 < ya[m0].sum() < m0.sum()):
            continue
        g = auc(ya[m1], aa[m1]) - auc(ya[m0], aa[m0])
        if g == g:
            out.append(g)
    return np.array(out)


def report_site(label, y, a, ax, rng):
    print(f"\n   --- {label} ---")
    res = {}
    for nm, m in (("anoxic", ax == 1), ("non-anoxic", ax == 0)):
        k = int(m.sum())
        if k < 60 or not (0 < y[m].sum() < k):
            print(f"      {nm:<11} n={k:>5}  too few")
            return None
        A = auc(y[m], a[m]); lo, hi = auc_ci(y[m], a[m], rng, NBOOT)
        res[nm] = (A, lo, hi)
        print(f"      {nm:<11} n={k:>5}  30-d death {100*y[m].mean():5.1f}%  AUC {A:.3f} [{lo:.3f},{hi:.3f}]"
              f"  {'-> MORE death' if A > 0.5 else '-> LESS death'}")
    an, no = res["anoxic"], res["non-anoxic"]
    ok = (an[0] - 0.5) * (no[0] - 0.5) < 0 and an[0] > 0.5
    strict = an[1] > 0.5 and no[2] < 0.5
    print(f"      gap (anoxic - non-anoxic) {an[0]-no[0]:+.3f}   "
          f"{'REVERSAL PRESENT' + (' (both intervals exclude 0.5)' if strict else ' (directional; at least one interval spans 0.5)') if ok else 'reversal NOT present'}")
    return res if ok else None


def main():
    rng = np.random.default_rng(20260727)
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
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            p = int(p)
            if t and (p not in when or t < when[p]):
                when[p] = t
    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except (KeyError, TypeError, ValueError):
                pass
    anox = build_or_load_anoxic()

    morph = load_morph()
    assert morph, "morphology table empty"

    rows = []
    for p, (ab, bu, site) in morph.items():
        if p not in when or p not in anox:
            continue
        d = death.get(p)
        if d is not None and (d - when[p]).days < -1:
            continue
        rows.append((site, 1.0 if (d is not None and (d - when[p]).days <= 30) else 0.0,
                     ab, 1.0 if anox[p] else 0.0, 1.0 if d is not None else 0.0, bu))
    assert len(rows) >= 400, f"only {len(rows)} patients"

    site = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows])
    a = np.array([r[2] for r in rows]); ax = np.array([r[3] for r in rows])
    hasrec = np.array([r[4] for r in rows]); bu = np.array([r[5] for r in rows])

    print("=" * 96)
    print("H3  SITE COMPOSITION -- so any difference between sites can be interpreted")
    print("=" * 96)
    print(f"{'site':>8} {'n':>6} {'anoxic':>9} {'30-d death':>11} {'median burden':>14} {'death record':>13}")
    print("-" * 96)
    for st in ("S0001", "S0002"):
        m = site == st
        print(f"{st:>8} {int(m.sum()):>6} {100*ax[m].mean():>8.1f}% {100*y[m].mean():>10.1f}% "
              f"{np.median(bu[m]):>14.3f} {100*hasrec[m].mean():>12.1f}%")

    print("\n" + "=" * 96)
    print("H1  PRIMARY -- DOES THE REVERSAL APPEAR AT EACH SITE INDEPENDENTLY?")
    print("   (no death-ascertainment conditioning; absent record treated as alive)")
    print("=" * 96)
    ok = {}
    for st in ("S0001", "S0002"):
        m = site == st
        ok[st] = report_site(st, y[m], a[m], ax[m], rng) is not None

    print("\n   --- for comparison, the decedents-only conditioning ---")
    for st in ("S0001", "S0002"):
        m = (site == st) & (hasrec == 1)
        report_site(f"{st} (decedents only)", y[m], a[m], ax[m], rng)

    print("\n" + "=" * 96)
    print("H2  HETEROGENEITY -- is the aetiology gap DIFFERENT between the two sites?")
    print("=" * 96)
    g1 = gap_boot(y[site == "S0001"], a[site == "S0001"], ax[site == "S0001"], rng, NBOOT)
    g2 = gap_boot(y[site == "S0002"], a[site == "S0002"], ax[site == "S0002"], rng, NBOOT)
    if len(g1) > 100 and len(g2) > 100:
        k = min(len(g1), len(g2))
        d = g1[:k] - g2[:k]
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"   gap at S0001 {g1.mean():+.3f}   gap at S0002 {g2.mean():+.3f}")
        print(f"   difference between sites {d.mean():+.3f} [{lo:+.3f},{hi:+.3f}]")
        print(f"   {'CONSISTENT -- the interval contains zero, so the sites do not differ detectably' if lo < 0 < hi else 'HETEROGENEOUS -- the sites differ, and the finding is not uniform across them'}")
    else:
        print("   too few usable bootstrap replicates to test heterogeneity")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    both = ok.get("S0001") and ok.get("S0002")
    print(f"   reversal present at S0001: {ok.get('S0001')}     at S0002: {ok.get('S0002')}")
    print(f"   {'H1 CONFIRMED -- present at both hospitals independently' if both else 'H1 FAILED -- not present at both; the finding may be one hospital practice'}")
    print("\n   This is INTERNAL validation. HEEDB's two sites differ in equipment, technologists and reading")
    print("   clinicians, so agreement is not nothing -- but they are hospitals in one regional academic")
    print("   network, which is limitation L4. It is the best available evidence and it is not a second")
    print("   health system, and it should be reported in those words.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
