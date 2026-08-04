"""Time-irreversibility on chennu -- the cohort where the spectral incumbent is NOT at ceiling.

WHY. E133 and E136 both concluded "subsumed by the spectrum" on sleep-EDFx, and both carried the same
unresolved caveat: the 16-column spectral incumbent reached out-of-bag rho **+0.9293** for the depth
ordinal, leaving almost no headroom, so neither null could distinguish *nothing to add* from *nowhere to
add it*.

A probe measured the identical spectral block on chennu:

    reaction time    +0.5583   (n = 78)
    n correct        +0.4003   (n = 80)
    sedation level   +0.1077   (n = 80)

All three leave real headroom, and the first two are BEHAVIOURAL -- a subject's own task performance
rather than a label a scorer read off the same EEG, which also removes the circularity caveat sleep
staging carries. chennu is therefore the deposit on which E133's question can actually be settled, and it
has no irreversibility columns. This makes them.

WHAT IS COMPUTED, and it mirrors `extract_sleep_irreversibility.py` exactly so a cross-deposit difference
cannot be an implementation difference (rule 20): `permutation_irreversibility` at embedding orders 3 and
4, `increment_asymmetry`, and for each a PHASE-RANDOMISED SURROGATE computed on the same segment. The
surrogate is the null the measure was built against -- it preserves the power spectrum exactly while
destroying temporal asymmetry -- and it is carried as a column, never used as a predictor.

FRONTAL AND POSTERIOR SEPARATELY, again as the sleep extraction does. chennu is high-density, so the two
are channel-name selections rather than the two bipolar derivations sleep-EDFx has; the selection is
written here rather than discovered per subject.

SCOPE. This script extracts. It fits nothing, correlates nothing and makes no claim.

    python bsde/scripts/extract_chennu_irreversibility.py --limit 2
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.irreversibility import (increment_asymmetry,            # noqa: E402
                                           permutation_irreversibility, phase_randomise)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RESULTS, "chennu_irreversibility.csv")

FRONTAL = re.compile(r"^(F|AF|FP|FC)", re.I)
POSTERIOR = re.compile(r"^(P|PO|O)", re.I)
FIELDS = ["recording_id", "subject", "status", "error", "n_channels", "sfreq", "n_samples",
          "frontal_irr3", "frontal_irr3_surr", "frontal_irr4", "frontal_irr4_surr",
          "frontal_incr", "frontal_incr_surr",
          "posterior_irr3", "posterior_irr3_surr", "posterior_irr4", "posterior_irr4_surr",
          "posterior_incr", "posterior_incr_surr"]


def _region(x, names, pat, rng):
    """Median over the region's channels of each statistic, so one bad channel cannot carry the result."""
    idx = [i for i, n in enumerate(names) if pat.match(str(n).strip())]
    if not idx:
        return {}
    out = {}
    for tag, fn in (("irr3", lambda s: permutation_irreversibility(s, order=3)),
                    ("irr4", lambda s: permutation_irreversibility(s, order=4)),
                    ("incr", increment_asymmetry)):
        real, surr = [], []
        for i in idx:
            s = np.asarray(x[i], float)
            if not np.isfinite(s).all() or s.size < 512:
                continue
            real.append(float(fn(s)))
            surr.append(float(fn(phase_randomise(s, rng))))
        if real:
            out[tag] = float(np.median(real))
            out[tag + "_surr"] = float(np.median(surr))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=-1)
    ap.add_argument("--of", type=int, default=1)
    a = ap.parse_args(argv)
    if a.shard >= 0:
        root, ext = os.path.splitext(a.out)
        a.out = f"{root}.s{a.shard}{ext}"

    from bsde.ingestion.chennu import ChennuRemoteZipAdapter
    # The adapter's default labels path is repo-root-relative ('results/chennu_labels.csv'); this
    # script is run from anywhere, so the absolute path is passed rather than relying on cwd.
    ad = ChennuRemoteZipAdapter(labels_csv=os.path.join(RESULTS, "chennu_labels.csv"))
    refs = ad.list_recordings()
    refs.sort(key=lambda r: r.recording_id)
    if a.shard >= 0:
        refs = [r for i, r in enumerate(refs) if i % a.of == a.shard]
    if a.limit:
        refs = refs[:a.limit]

    out_path = os.path.abspath(a.out)
    done = set()
    import glob as _glob
    root, ext = os.path.splitext(out_path.replace(f".s{a.shard}", "") if a.shard >= 0 else out_path)
    for p in {out_path, *_glob.glob(f"{root}.s*{ext}"), f"{root}{ext}"}:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            for r in csv.DictReader(open(p, newline="")):
                done.add(r["recording_id"])
    todo = [r for r in refs if r.recording_id not in done]
    print(f"{len(refs)} recordings in shard, {len(done)} done, {len(todo)} to fetch -> {out_path}",
          flush=True)
    if not todo:
        return 0

    # Surrogates are seeded ONCE per run, not per channel, so the null is deterministic and reproducible
    # (CLAUDE.md: never use hash() for seeding; a fixed generator is the reproducible path).
    rng = np.random.default_rng(133)
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, ref in enumerate(todo, 1):
            row = {"recording_id": ref.recording_id, "subject": getattr(ref, "subject", ""),
                   "status": "ok", "error": ""}
            try:
                # LoadResult is a TUPLE (data, channel_names, sfreq, meta) -- see ingestion/base.py.
                # load() lives on the RecordingRef, not on the adapter.
                data, names, sfreq, _meta = ref.load()
                x = np.asarray(data, float)
                names = list(names)
                row.update({"n_channels": x.shape[0], "sfreq": f"{float(sfreq):g}",
                            "n_samples": x.shape[1]})
                for tag, pat in (("frontal", FRONTAL), ("posterior", POSTERIOR)):
                    for k, v in _region(x, names, pat, rng).items():
                        row[f"{tag}_{k}"] = f"{v:.8g}"
                if not any(k.startswith("frontal_irr3") and row.get(k) for k in FIELDS):
                    raise ValueError(f"no frontal channels matched among {names[:6]}")
            except Exception as e:                                          # noqa: BLE001
                row.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:200]})
            w.writerow(row)
            fh.flush()
            print(f"   [{i}/{len(todo)}] {ref.recording_id} {row['status']} "
                  f"f_irr3={row.get('frontal_irr3','')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
