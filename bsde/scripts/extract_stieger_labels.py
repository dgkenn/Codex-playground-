"""Pull per-session BCI accuracy out of Stieger 2021, for Challenge B's label-reliability question.

WHY LABELS ONLY, AND WHY THIS RUNS BEFORE ANY CORRELATION. `docs/QUEUE.md` Q14 step 2, which is E38's
sequencing made standard: **measure the ceiling before running the correlation.** E41's Challenge B null was
an arithmetic problem, not a scientific one -- E38 measured eegmmidb's label reliability at r_sb = 0.2918
[0.1163, 0.4345], capping any predictor at rho ~ 0.54 by attenuation alone, so E41's |rho| = 0.076 against a
minimum detectable 0.272 says nothing about the marker. Stieger's claim on Challenge B is 450 trials per
session against eegmmidb's 45 in total. **That claim is checkable from `BCI.TrialData` with no EEG touched**,
which is why this script reads the label and discards the signal.

TWO RELIABILITIES, NOT ONE, AND THE DISTINCTION IS THE WHOLE POINT. This deposit exists to study BCI
LEARNING, so session-to-session change is partly real improvement and not only noise. Conflating them would
understate reliability and reproduce E38's problem in a new place.

    within-session split-half   odd trials vs even trials in the SAME session. Measurement noise alone;
                                learning cannot occur between interleaved trials. This is the direct
                                successor to E38's estimate and the one that sets the attenuation ceiling.
    across-session             session k vs session k+1 for the same subject. Measurement noise PLUS real
                                change. Necessarily lower, and the gap between the two is the learning.

WHAT IS FETCHED. 599 files, 376.9 GB total (verified through the figshare REST API with `curl`, never a
fetch-tool summary -- rules 25, 39). `--sessions-per-subject` bounds it: 3 sessions x 62 subjects is about
117 GB of transfer and ~470 kB of output. Files are processed one at a time and **deleted immediately**, so
peak disk is one file. Resumable: a session already in the output is never re-fetched.

    python bsde/scripts/extract_stieger_labels.py --sessions-per-subject 3
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

API = "https://api.figshare.com/v2/articles/13123148/files?page_size=1000"
OUT = os.path.join(HERE, "..", "results", "stieger_labels.csv")
NAME = re.compile(r"S(\d+)_Session_(\d+)\.mat")
FIELDS = ["subject", "session", "n_trials", "n_scored", "accuracy", "accuracy_odd", "accuracy_even",
          "accuracy_forced", "n_artifact", "age", "gender", "handedness"]


def file_index(cache="/tmp/eeg_probe/stieger_files.json"):
    if not os.path.exists(cache):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with urllib.request.urlopen(API, timeout=120) as r, open(cache, "wb") as fh:
            fh.write(r.read())
    return json.load(open(cache))


def _scalar(md, key):
    """One metadata field as a plain Python scalar. `squeeze_me=True` already unwraps most of them."""
    v = getattr(md, key, "")
    return v.item() if hasattr(v, "item") else v


def session_row(path: str, subject: str, session: str):
    """Per-session accuracy and its odd/even split, from `BCI.TrialData` alone. No EEG is touched.

    `loadmat(struct_as_record=False, squeeze_me=True)` yields `mat_struct` objects with ATTRIBUTE access,
    not subscripting -- a first version indexed them and failed on every file.

    `result` is NaN on unscored trials (13 of 450 in the sample session), so the odd/even split is taken
    over the SCORED trials in order rather than over all trial slots. Splitting by raw index would put a
    systematically different number of scored trials in each half whenever the unscored ones cluster, and
    the two halves would no longer be exchangeable -- which is the one property a split-half reliability
    estimate needs.
    """
    import numpy as np
    from scipy.io import loadmat
    bci = loadmat(path, struct_as_record=False, squeeze_me=True)["BCI"]
    td = bci.TrialData

    def col(name):
        return np.array([float(getattr(t, name)) if getattr(t, name, None) is not None else np.nan
                         for t in td], float)

    res, forced, art = col("result"), col("forcedresult"), col("artifact")
    ok = np.isfinite(res)
    scored = res[ok]
    odd, even = scored[0::2], scored[1::2]
    md = bci.metadata
    return {"subject": subject, "session": session, "n_trials": int(res.size),
            "n_scored": int(ok.sum()),
            "accuracy": f"{float(scored.mean()):.6f}" if scored.size else "",
            "accuracy_odd": f"{float(odd.mean()):.6f}" if odd.size else "",
            "accuracy_even": f"{float(even.mean()):.6f}" if even.size else "",
            "accuracy_forced": (f"{float(forced[np.isfinite(forced)].mean()):.6f}"
                                if np.isfinite(forced).any() else ""),
            "n_artifact": int(np.nansum(art)) if art.size else 0,
            "age": _scalar(md, "age"), "gender": _scalar(md, "gender"),
            "handedness": _scalar(md, "handedness")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions-per-subject", type=int, default=3, dest="k")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tmp", default="/tmp/eeg_probe/stieger")
    a = ap.parse_args(argv)

    files = file_index()
    want = []
    for f in files:
        mt = NAME.match(f["name"])
        if mt and int(mt.group(2)) <= a.k:
            want.append((mt.group(1), mt.group(2), f))
    want.sort(key=lambda t: (int(t[0]), int(t[1])))
    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["subject"], r["session"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1]) not in done]
    gb = sum(t[2]["size"] for t in todo) / 1e9
    print(f"{len(want)} sessions wanted, {len(done)} already done, {len(todo)} to fetch ({gb:.1f} GB)",
          flush=True)

    os.makedirs(a.tmp, exist_ok=True)
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, (subj, sess, f) in enumerate(todo, 1):
            dest = os.path.join(a.tmp, f["name"])
            try:
                urllib.request.urlretrieve(f["download_url"], dest)
                row = session_row(dest, subj, sess)
                w.writerow(row)
                fh.flush()
                print(f"   [{i}/{len(todo)}] S{subj} sess {sess}: {row['n_scored']}/{row['n_trials']} "
                      f"scored, acc {row['accuracy']}", flush=True)
            except Exception as e:                                           # noqa: BLE001
                print(f"   [{i}/{len(todo)}] S{subj} sess {sess}: FAIL {type(e).__name__}: {e}",
                      flush=True)
            finally:
                if os.path.exists(dest):
                    os.remove(dest)                   # peak disk is one file, always
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
