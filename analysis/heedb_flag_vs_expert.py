#!/usr/bin/env python3
"""Is the report-text "generalized slowing" flag measuring what it says? An independent expert annotation says.

WHY THIS MATTERS MORE THAN IT LOOKS. The largest open constraint in the project is R360: the clinician's
generalized-slowing flag carries **-0.752 [-1.075, -0.434]** after adjusting for suppression burden and our
intra-burst 8-30 Hz measure. Three candidate explanations have since been eliminated or measured -- the
whole-record background spectrum (B3), spatial topography (T3), and temporal evolution (R378, confirmed but
without predictive increment). Not one of them touched the possibility that the *flag itself* is the problem:
it is a single binary extracted from free-text reports written by many readers, and reader heterogeneity is
limitation #3 of the whole programme. It has never been validated against anything.

The MORGOTH 1.0 release supplies exactly the missing instrument. Its model code and checkpoint are not public
(the repository is unreleased and the checkpoint ships via a link inside it), so the model cannot be used --
but the **labelled task sets are in S3 and readable**, and one of them is GENSLOWING: 5,396 expert-annotated
generalized-slowing events, one per patient, keyed by `bdsp_mrn` in the same identifier space as our cohort.
That is a second, methodologically independent read of the same construct.

WHAT MAKES A ROW APPEAR IN THAT TABLE, asked before building on it (catalogue rule 7). GENSLOWING is
**positives only** -- every one of the 5,396 rows carries the label "generalized slowing", and there are no
negatives. It was assembled to train a detector, not to survey a cohort. So absence from it is **not** evidence
that a patient lacks slowing, and a naive join treating "not in GENSLOWING" as a negative would be the exact
error rule 5 exists to prevent. Everything below is therefore built as a **one-sided** test: among patients the
experts positively annotated, what does the report-text flag say?

  F1  SENSITIVITY OF THE FLAG. Among our patients carrying an independent expert generalized-slowing
      annotation, what fraction have the report-text flag set? A flag that is a faithful reading of the record
      should be positive in most of them. This is a proportion with a confidence interval, not a test.

  F2  IS THE DISAGREEMENT RANDOM OR STRUCTURED? If the flag simply misses slowing at random, the missed
      patients should look like the caught ones on our quantitative measures. If the misses are structured --
      concentrated at high suppression burden, say, where a reader may call the record "suppressed" rather
      than "slow" -- then the flag is not a noisy version of the construct but a different one.

  F3  WHAT IT MEANS FOR R360, and the direction is the point. Non-differential misclassification of a binary
      exposure attenuates its coefficient toward zero. The flag carries -0.752 **despite** whatever noise it
      has, so a cleaner label should make that residual LARGER, not smaller. If F2 shows the misses are
      instead structured by burden, that reasoning fails and the residual could be partly artefact -- which
      would be the first serious challenge to a finding three experiments have failed to explain.

WHAT THIS CANNOT DO. It cannot estimate specificity, because there are no annotated negatives. It cannot
establish that the expert annotation is the better instrument -- only that the two disagree, and how.
"""
import csv, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The sandbox exports placeholder AWS_* env vars that shadow the real profile -- common/awsenv.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.awsenv import sanitize as _aws_sanitize; _aws_sanitize()

AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
MORGOTH_AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-projects-ap"
GENSLOW_KEY = "morgoth1/data/internal_dataset/GENSLOWING/list_events_gensloing_20241121.xlsx"
CACHE = os.environ.get("GENSLOW_XLSX", "/tmp/eeg_probe/genslowing.xlsx")
BURDEN = os.environ.get("HEEDB_BURDEN", "/tmp/eeg_probe/heedb_bs_burden_win.s0.csv")
MORPH = os.environ.get("HEEDB_MORPH", "/tmp/eeg_probe/heedb_burst_morph.s0.csv")
NBOOT = int(os.environ.get("NBOOT", "2000"))


def s3():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name="us-east-1",
                        config=Config(s3={"payload_signing_enabled": False}))


def expert_positives():
    import pandas as pd
    if not os.path.exists(CACHE):
        import boto3
        from botocore.config import Config
        c = boto3.Session(profile_name="physionet").client(
            "s3", region_name="us-east-1", config=Config(s3={"payload_signing_enabled": False}))
        c.download_file(MORGOTH_AP, GENSLOW_KEY, CACHE)
    df = pd.read_excel(CACHE)
    labs = set(df["label"].astype(str).str.strip().unique())
    assert labs == {"generalized slowing"}, f"expected a positives-only table, found labels {labs}"
    return {int(x) for x in df["bdsp_mrn"] if str(x).strip().isdigit()}


def report_flags():
    """Report-text findings per patient: the generalized-slowing flag, plus burst suppression for context."""
    c = s3()
    flag, bs = {}, {}
    for st in ("S0001", "S0002"):
        txt = c.get_object(Bucket=AP,
                           Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                           )["Body"].read().decode("utf-8", "replace")
        rd = csv.DictReader(io.StringIO(txt))
        assert "gen slowing" in (rd.fieldnames or []), \
            f"'gen slowing' column absent from {st} findings; columns are {rd.fieldnames}"
        for r in rd:
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            v = (r.get("gen slowing") or "").strip() not in ("", "None", "nan")
            flag[p] = flag.get(p, False) or v
            b = (r.get("bs") or "").strip() not in ("", "None", "nan")
            bs[p] = bs.get(p, False) or b
    return flag, bs


def load_measure(path, col):
    out = defaultdict(list)
    if not os.path.exists(path):
        return {}
    for r in csv.DictReader(open(path)):
        p = (r.get("patient") or "").strip()
        try:
            v = float(r[col])
        except (KeyError, TypeError, ValueError):
            continue
        if p.isdigit() and v == v:
            out[int(p)].append(v)
    return {p: float(np.median(v)) for p, v in out.items()}


def prop_ci(k, n, rng, reps):
    if n == 0:
        return float("nan"), float("nan")
    x = np.zeros(n); x[:k] = 1.0
    bs = [x[rng.integers(0, n, n)].mean() for _ in range(reps)]
    return tuple(np.percentile(bs, [2.5, 97.5]))


def main():
    rng = np.random.default_rng(20260727)
    exp = expert_positives()
    print(f"expert GENSLOWING positives (MORGOTH 1.0 internal dataset): {len(exp):,} patients")
    print("   POSITIVES ONLY -- there are no annotated negatives, so specificity is not estimable here")

    flag, bsflag = report_flags()
    print(f"HEEDB report-text findings available for {len(flag):,} patients")
    burden = load_measure(BURDEN, "burden")
    print(f"quantitative burden available for {len(burden):,} patients")

    overlap = sorted(exp & set(flag))
    n = len(overlap)
    assert n >= 50, (f"only {n} patients have both an expert annotation and a report finding -- "
                     "too few to say anything, and an empty join is not a result")
    print(f"\npatients with BOTH an expert annotation and a report-text finding: {n:,}")

    # ---- F1 -----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("F1  SENSITIVITY -- among expert-annotated slowing, how often is the report-text flag set?")
    print("=" * 96)
    k = sum(1 for p in overlap if flag[p])
    lo, hi = prop_ci(k, n, rng, NBOOT)
    print(f"   flag set in {k:,}/{n:,} = {100*k/n:.1f}% [{100*lo:.1f},{100*hi:.1f}]")
    print(f"   for reference, the flag is set in {100*np.mean([1.0 if v else 0.0 for v in flag.values()]):.1f}% "
          f"of all {len(flag):,} patients with a report")
    if k / n < 0.8:
        print("   The flag misses a substantial share of records an expert annotated as generalized slowing.")
    else:
        print("   The flag agrees with the expert annotation in most annotated records.")

    # ---- F2 -----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("F2  IS THE DISAGREEMENT RANDOM, OR STRUCTURED BY SUPPRESSION BURDEN?")
    print("=" * 96)
    have = [p for p in overlap if p in burden]
    print(f"   of those, {len(have):,} also have a quantitative burden")
    if len(have) >= 60:
        caught = np.array([burden[p] for p in have if flag[p]])
        missed = np.array([burden[p] for p in have if not flag[p]])
        print(f"   flag SET   n={len(caught):>4}  median burden {np.median(caught):.3f}")
        print(f"   flag UNSET n={len(missed):>4}  median burden {np.median(missed):.3f}")
        if len(caught) > 10 and len(missed) > 10:
            d = float(missed.mean() - caught.mean())
            bs = []
            for _ in range(NBOOT):
                a = caught[rng.integers(0, len(caught), len(caught))]
                b = missed[rng.integers(0, len(missed), len(missed))]
                bs.append(b.mean() - a.mean())
            l2, h2 = np.percentile(bs, [2.5, 97.5])
            print(f"   difference in mean burden (missed - caught) {d:+.4f} [{l2:+.4f},{h2:+.4f}]")
            if l2 > 0:
                print("   STRUCTURED: the records the flag misses are MORE suppressed. A reader who calls a")
                print("   record 'suppressed' rather than 'slow' would produce exactly this, which makes the")
                print("   flag differential with respect to burden -- and burden is the adjustment variable in")
                print("   R360. That is a mechanism by which the residual could be partly artefact.")
            elif h2 < 0:
                print("   STRUCTURED the other way: missed records are LESS suppressed.")
            else:
                print("   Not distinguishable from random with respect to burden: the misses look like the")
                print("   catches, which is what non-differential misclassification predicts.")
        # and how often is the BS flag set instead, among the missed?
        miss_ids = [p for p in have if not flag[p]]
        if miss_ids:
            alt = np.mean([1.0 if bsflag.get(p) else 0.0 for p in miss_ids])
            catch_ids = [p for p in have if flag[p]]
            alt2 = np.mean([1.0 if bsflag.get(p) else 0.0 for p in catch_ids]) if catch_ids else float("nan")
            print(f"\n   burst-suppression flag set in {100*alt:.1f}% of the MISSED versus "
                  f"{100*alt2:.1f}% of the CAUGHT")
            print("   If the missed records are disproportionately flagged as burst suppression instead, the")
            print("   reader saw the record and described it with a different word -- not an oversight but a")
            print("   competing description.")

    print("\n" + "=" * 96)
    print("F3  WHAT THIS DOES TO R360")
    print("=" * 96)
    print("   Non-differential misclassification of a binary exposure attenuates toward the null, so if the")
    print("   flag's errors were random the -0.752 [-1.075, -0.434] residual would be an UNDERSTATEMENT and a")
    print("   cleaner label would enlarge it. That reasoning holds only if F2 came out random. If the misses")
    print("   are structured by burden -- the very variable R360 adjusts for -- the attenuation argument does")
    print("   not apply and part of the residual may be misclassification rather than signal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
