#!/usr/bin/env python3
"""Which suppression series were glued shut across a dropout, and must be excluded from the BSP analysis?

`icare_seq_gap_check.py` re-read 24 random recordings and found the median interior-dropped fraction is
0.000 % -- but one recording had 50.5 % of its frames dropped from the MIDDLE, a 1,817 s hole closed up so that
the two halves became adjacent. For a burden that is harmless: an average over frames does not care about
order. For BSP it is not harmless at all, because the entire model is about how the state moves from one
one-second bin to the next, and a closed-up hole presents as an abrupt jump that never happened. The
pre-declared rule in that check therefore fires: exclude recordings with interior gaps.

DOING IT WITHOUT A SECOND FULL PASS. The extraction did not record where the gaps were, and re-reading 602
hour-long recordings to find out would cost another full pass over the signal data. It is not necessary: the
WFDB header states the sample count, headers are a few hundred bytes each, and the extraction already recorded
how many one-second bins survived. Their ratio is the dropped fraction.

    dropped = 1 - (n_bins * 10 frames) / floor(samples / frame_length)

The 24-recording audit found edge drops of 0.00 % in every case, so total dropped is a faithful stand-in for
interior dropped here; where it is not, it errs toward excluding a merely edge-trimmed recording, which costs
a little sample size and cannot bias a result.

THRESHOLD, fixed before looking at the distribution: exclude any recording losing more than 1 % of its frames.
At 0.1 s frames that is 3.6 s in an hour -- below the point where glue could matter for a one-second-bin random
walk, and far below the 50 % case that prompted this.
"""
import csv, os, re, sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_topography import AP, ROOT, HOUR, FRAME_S, FRAMES_PER_BIN, s3c, parse_hea

TOPO = os.environ.get("ICARE_TOPO_OUT", "/tmp/eeg_probe/icare_topo.csv")
OUT = os.environ.get("ICARE_KEEP_OUT", "/tmp/eeg_probe/icare_seq_keep.csv")
MAX_DROP = float(os.environ.get("MAX_DROP", "0.01"))


def one(pid, nb, s3):
    try:
        r = s3.list_objects_v2(Bucket=AP, Prefix=f"{ROOT}{pid}/", MaxKeys=1000)
        eeg = [o["Key"] for o in r.get("Contents", []) if o["Key"].endswith("_EEG.mat")]
        if not eeg:
            return None

        def hr(k):
            m = re.match(r"^\d+_\d+_(\d+)_EEG\.mat$", k.split("/")[-1])
            return int(m.group(1)) if m else 10 ** 6
        eeg.sort(key=lambda k: abs(hr(k) - HOUR))
        key = eeg[0]
        txt = s3.get_object(Bucket=AP, Key=key[:-4] + ".hea")["Body"].read().decode("utf-8", "replace")
        head = [l for l in txt.splitlines() if l.strip()][0].split()
        fs = float(head[2]); nsamp = int(head[3])
        fr = max(1, int(FRAME_S * fs))
        nframes = nsamp // fr
        if nframes <= 0:
            return None
        drop = 1.0 - (nb * FRAMES_PER_BIN) / nframes
        return dict(pid=pid, dur_s=nsamp / fs, n_bins=nb, drop=drop)
    except Exception:
        return None


def main():
    rows = []
    for r in csv.DictReader(open(TOPO)):
        try:
            rows.append((r["pid"].strip(), int(float(r["n_bins"]))))
        except (KeyError, TypeError, ValueError):
            continue
    assert rows, f"{TOPO} has no usable n_bins column"
    print(f"checking {len(rows):,} recordings against their WFDB headers", flush=True)

    s3 = s3c()
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = [x for x in ex.map(lambda t: one(t[0], t[1], s3), rows) if x]
    assert res, "no header could be read -- the check failed rather than passed"
    d = np.array([x["drop"] for x in res])
    print(f"   headers read for {len(res):,} of {len(rows):,}")
    print(f"   dropped-frame fraction: median {100*np.median(d):.3f}%, "
          f"p90 {100*np.percentile(d,90):.3f}%, max {100*d.max():.2f}%")
    for q in (0.001, 0.01, 0.05, 0.20):
        print(f"      over {100*q:>5.1f}%: {int((d > q).sum()):>4} recordings")

    keep = [x for x in res if x["drop"] <= MAX_DROP]
    print(f"\n   KEEP {len(keep):,} of {len(res):,} at a {100*MAX_DROP:.0f}% threshold "
          f"({len(res)-len(keep):,} excluded)")
    worst = sorted(res, key=lambda x: -x["drop"])[:8]
    print("   worst offenders:")
    for x in worst:
        print(f"      {x['pid']}  duration {x['dur_s']:>6.0f} s  bins {x['n_bins']:>5}  "
              f"dropped {100*x['drop']:>6.2f}%")
    # ---- rule 14: an exclusion is not reportable until it has been checked for outcome-relatedness -----
    # 12 % of recordings is a large exclusion. If the excluded patients differ in outcome, every downstream
    # estimate is conditioned on a variable related to the endpoint and the exclusion is not innocent.
    coh = {}
    for r in csv.DictReader(open(os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv"))):
        pid = (r.get("pid") or "").strip()
        try:
            c = float(r.get("cpc"))
        except (TypeError, ValueError):
            continue
        if pid and c == c:
            coh[pid] = 1.0 if c >= 3 else 0.0
    kp = {x["pid"] for x in keep}
    yk = [coh[x["pid"]] for x in res if x["pid"] in coh and x["pid"] in kp]
    ye = [coh[x["pid"]] for x in res if x["pid"] in coh and x["pid"] not in kp]
    print("\n   OUTCOME-RELATEDNESS OF THE EXCLUSION")
    if len(yk) > 20 and len(ye) > 5:
        pk, pe = float(np.mean(yk)), float(np.mean(ye))
        rng = np.random.default_rng(20260727)
        bs = [float(np.mean(rng.choice(yk, len(yk)))) - float(np.mean(rng.choice(ye, len(ye))))
              for _ in range(2000)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"      kept     n={len(yk):>4}  poor outcome {100*pk:>5.1f}%")
        print(f"      excluded n={len(ye):>4}  poor outcome {100*pe:>5.1f}%")
        print(f"      difference (kept - excluded) {100*(pk-pe):+.1f} pp "
              f"[{100*lo:+.1f},{100*hi:+.1f}]")
        print(f"      {'NOT outcome-related -- the exclusion is innocent' if lo < 0 < hi else 'OUTCOME-RELATED -- every downstream estimate is conditioned on it and must say so'}")
    else:
        print("      too few in one arm to test")

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pid", "dur_s", "n_bins", "drop"])
        for x in sorted(keep, key=lambda x: x["pid"]):
            w.writerow([x["pid"], f"{x['dur_s']:.1f}", x["n_bins"], f"{x['drop']:.5f}"])
    print(f"   wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
