#!/usr/bin/env python3
"""E06 — how few channels are enough? A full single-channel sweep on Chennu.

WHY THIS EXPERIMENT EXISTS. `reduced_channel` is one of the ten report items every verifier run is required to
produce (Brief 03's item 9) and **nothing in this project computes it**. It is also the question that decides
whether any of this is deployable: a depth-of-anaesthesia monitor uses a frontal strip, a wearable uses one to
four electrodes, and an ICU montage that needs 91 channels is a research instrument, not a product.

It bears on the science too. If one channel carries what 91 carry, then every spatial construct here is
decorative — UCE v1's frontal/posterior split (already shown redundant by E01/E02 for a different reason), and
wPLI's channel pairs, which cannot exist at all below two channels.

HOW THIS AVOIDS THE OBVIOUS TRAP. The tempting design is "compute it on Fz and see". That cherry-picks: with 91
candidate electrodes, some will look good by chance, and reporting the best one is a search over 91 with a
denominator of 1. So this sweeps **every single channel separately** and reports the whole distribution — median
and range across 91 electrodes — alongside the named-electrode values. The distribution is the result; a single
electrode's number is an anecdote.

Chennu is the right dataset for it: 91 channels, within-subject, four sedation levels, and — uniquely among the
datasets reached so far — **measured plasma propofol concentration**, so channel count can be scored against a
physical quantity rather than against a rating.

THE SCORE. For each candidate and each channel set, the same two quantities used in E05:
    mono  = fraction of the 20 subjects in whom the value rises monotonically with plasma across
            baseline -> mild -> moderate (Spearman > 0)
    auc   = discrimination of baseline (level 1) vs moderate (level 3), subject-paired, direction-free
Both are within-subject, so between-subject variation cannot produce them.

REGISTERED BEFORE RUNNING:
    P1  The conventional 10-20 subset (the ~19 channels in this hybrid montage carrying 10-20 labels) retains
        at least 80 % of the all-91-channel `mono` for `lempel_ziv`, the candidate that scored highest in E05.
    P2  The MEDIAN single channel retains at least half of the all-channel `mono` for `lempel_ziv`. Stated as a
        median rather than a best case precisely so that it cannot be met by cherry-picking.
    P3  STRUCTURAL, and a check on the pipeline rather than the biology: `wpli_alpha` is NOT COMPUTABLE on one
        channel and must return NaN rather than a number, and `uce_v1` is not computable on any single channel
        because no one electrode is both frontal and posterior. If either emits a value, there is a
        substitution bug — which is exactly the failure §9.10 records me making by hand.
    P4  Frontal single channels do NOT beat the median single channel by a wide margin. Rationale: the
        aperiodic exponent and broadband complexity are dominated by global cortical dynamics, not by a focal
        generator, so if a frontal electrode were dramatically better that would suggest the signal is
        regional (or muscle, which is frontal-dominant — a possibility this cannot rule out).

    FALSIFICATION: if the median single channel retains almost nothing, the honest conclusion is that these
    measures need spatial coverage and single-electrode deployment is not supported by this dataset.

SCOPE. 20 healthy volunteers, one drug, one site, one montage, and the deposit is filtered 0.5-45 Hz and
average-referenced — **average referencing is itself a spatial operation**, so a "single channel" here is a
single channel of an average-referenced montage, not what a one-electrode device would actually record. That
limitation is fundamental to this dataset and is not removable by analysis; it means these numbers are an
upper bound on true single-electrode performance.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                       # noqa: E402
from bsde.candidates.seed import seed_registry                       # noqa: E402
from bsde.verifier.stats import auc_abs, spearman                    # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT_LONG = os.path.join(RESULTS, "e06_channel_sweep_long.csv")
PLASMA_BY_LEVEL = {1: 0.0, 2: 438.0, 3: 803.0}      # level medians; only the ORDER is used
TEN_TWENTY = {"FP1", "FP2", "FPZ", "FZ", "F3", "F4", "F7", "F8", "CZ", "C3", "C4",
              "T3", "T4", "T5", "T6", "PZ", "P3", "P4", "O1", "O2", "OZ"}


def _norm(n):
    return "".join(c for c in str(n).upper() if c.isalnum())


def extract(n_epochs=4, limit=None, log=print):
    """One pass over Chennu: load each recording once, evaluate every candidate on every channel set."""
    from bsde.ingestion.chennu import ChennuRemoteZipAdapter
    seed_registry()
    cands = REGISTRY.all()
    adapter = ChennuRemoteZipAdapter(n_epochs=n_epochs)
    refs = adapter.list_recordings()
    if limit:
        refs = refs[:limit]
    done = set()
    if os.path.exists(OUT_LONG):
        with open(OUT_LONG, newline="") as fh:
            done = {r["recording_id"] for r in csv.DictReader(fh)}
        log(f"   resuming: {len(done)} recordings already swept")
    fields = ["recording_id", "subject", "sedation_level", "plasma", "channel_set",
              "n_channels", "candidate", "value"]
    new = not os.path.exists(OUT_LONG) or os.path.getsize(OUT_LONG) == 0
    with open(OUT_LONG, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for i, ref in enumerate(refs, 1):
            if ref.recording_id in done:
                continue
            try:
                data, ch, sf, meta = ref.load()
            except Exception as e:
                log(f"   [{i}] {ref.recording_id}: FAILED {type(e).__name__}: {e}")
                continue
            sets = {"all": list(range(len(ch))),
                    "ten_twenty": [k for k, c in enumerate(ch) if _norm(c) in TEN_TWENTY]}
            for k, c in enumerate(ch):
                sets[f"single:{c}"] = [k]
            rows = []
            for sname, idx in sets.items():
                sub = data[idx, :]
                subch = [ch[k] for k in idx]
                for cand in cands:
                    try:
                        v = cand.fn(sub, subch, sf, meta)
                    except Exception:
                        v = float("nan")
                    rows.append({"recording_id": ref.recording_id, "subject": ref.subject,
                                 "sedation_level": meta.get("sedation_level"),
                                 "plasma": meta.get("plasma_propofol_ug_per_L"),
                                 "channel_set": sname, "n_channels": len(idx),
                                 "candidate": cand.name,
                                 "value": "" if v is None or not np.isfinite(v) else f"{float(v):.10g}"})
            w.writerows(rows)
            fh.flush(); os.fsync(fh.fileno())
            log(f"   [{i}/{len(refs)}] {ref.recording_id[:34]:34s} {len(sets)} channel sets")
    return OUT_LONG


def score():
    """mono and auc per (candidate, channel_set), from the long table."""
    if not os.path.exists(OUT_LONG):
        return {}
    v = defaultdict(dict)          # (cand, cset) -> {(subject, level): value}
    for r in csv.DictReader(open(OUT_LONG, newline="")):
        if r["value"] == "":
            continue
        try:
            lvl = int(float(r["sedation_level"])); val = float(r["value"])
        except (TypeError, ValueError):
            continue
        v[(r["candidate"], r["channel_set"])][(r["subject"], lvl)] = val
    out = {}
    for key, d in v.items():
        subs = sorted({s for s, _ in d})
        mono = [spearman([d[(s, 1)], d[(s, 2)], d[(s, 3)]], [PLASMA_BY_LEVEL[i] for i in (1, 2, 3)])
                for s in subs if all((s, i) in d for i in (1, 2, 3))]
        mono = [m for m in mono if np.isfinite(m)]
        pair = [(d[(s, 1)], d[(s, 3)]) for s in subs if (s, 1) in d and (s, 3) in d]
        if pair:
            y = np.r_[np.zeros(len(pair)), np.ones(len(pair))]
            x = np.r_[[a for a, _ in pair], [b for _, b in pair]]
            a = auc_abs(y, x)
        else:
            a = float("nan")
        out[key] = {"mono": float(np.mean([m > 0 for m in mono])) if mono else float("nan"),
                    "n_mono": len(mono), "auc": a, "n_pairs": len(pair)}
    return out


def main() -> int:
    limit = int(os.environ.get("E06_LIMIT", "0")) or None
    print("E06 — how few channels are enough? full single-channel sweep on Chennu")
    extract(limit=limit)
    sc = score()
    if not sc:
        print("   no scores"); return 1
    cands = sorted({c for c, _ in sc})
    print("\n" + "=" * 100)
    print(f"{'candidate':22s} {'all':>16s} {'ten_twenty':>16s} {'single: median':>16s} {'single: range':>20s}")
    print("=" * 100)
    summary = {}
    for c in cands:
        singles = [(k[1].split(":", 1)[1], m) for k, m in sc.items()
                   if k[0] == c and k[1].startswith("single:") and np.isfinite(m["mono"])]
        smono = np.array([m["mono"] for _, m in singles]) if singles else np.array([])
        a = sc.get((c, "all"), {}).get("mono", float("nan"))
        t = sc.get((c, "ten_twenty"), {}).get("mono", float("nan"))
        if smono.size:
            best = max(singles, key=lambda kv: kv[1]["mono"])
            row = (f"{c:22s} {a:16.3f} {t:16.3f} {np.median(smono):16.3f} "
                   f"{f'[{smono.min():.2f}, {smono.max():.2f}] n={smono.size}':>20s}")
        else:
            best = (None, {"mono": float('nan')})
            row = f"{c:22s} {a:16.3f} {t:16.3f} {'NOT COMPUTABLE':>16s} {'':>20s}"
        print(row)
        summary[c] = {"mono_all": a, "mono_ten_twenty": t,
                      "mono_single_median": float(np.median(smono)) if smono.size else None,
                      "mono_single_min": float(smono.min()) if smono.size else None,
                      "mono_single_max": float(smono.max()) if smono.size else None,
                      "n_single_channels_computable": int(smono.size),
                      "best_single_channel": best[0], "best_single_mono": best[1]["mono"],
                      "auc_all": sc.get((c, "all"), {}).get("auc"),
                      "auc_ten_twenty": sc.get((c, "ten_twenty"), {}).get("auc"),
                      "auc_single_median": (float(np.median([m["auc"] for _, m in singles
                                                             if np.isfinite(m["auc"])]))
                                            if singles else None)}

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    lz = summary.get("lempel_ziv", {})
    p1 = (lz.get("mono_ten_twenty") or 0) >= 0.8 * (lz.get("mono_all") or 1e9)
    p2 = (lz.get("mono_single_median") or 0) >= 0.5 * (lz.get("mono_all") or 1e9)
    p3 = (summary.get("wpli_alpha", {}).get("n_single_channels_computable", 1) == 0 and
          summary.get("uce_v1", {}).get("n_single_channels_computable", 1) == 0)
    fr = [(n, m) for (c, s), m in sc.items() if c == "lempel_ziv" and s.startswith("single:")
          and (n := s.split(":", 1)[1]) and _norm(n) in {"FP1", "FP2", "FZ", "F3", "F4", "F7", "F8"}
          and np.isfinite(m["mono"])]
    frm = float(np.median([m["mono"] for _, m in fr])) if fr else float("nan")
    p4 = np.isfinite(frm) and np.isfinite(lz.get("mono_single_median") or np.nan) and \
        frm <= (lz["mono_single_median"] + 0.15)
    print(f"   P1 10-20 subset keeps >=80% of all-channel mono (lempel_ziv): {'MET' if p1 else 'NOT MET'} "
          f"({lz.get('mono_ten_twenty')} vs {lz.get('mono_all')})")
    print(f"   P2 MEDIAN single channel keeps >=50%                        : {'MET' if p2 else 'NOT MET'} "
          f"({lz.get('mono_single_median')} vs {lz.get('mono_all')})")
    print(f"   P3 wpli_alpha and uce_v1 NOT computable on one channel      : {'MET' if p3 else 'NOT MET'} "
          f"(computable single channels: wpli={summary.get('wpli_alpha', {}).get('n_single_channels_computable')}, "
          f"uce={summary.get('uce_v1', {}).get('n_single_channels_computable')})")
    print(f"   P4 frontal singles do not beat the median by >0.15          : {'MET' if p4 else 'NOT MET'} "
          f"(frontal median {frm:.3f} vs overall single median {lz.get('mono_single_median')})")
    print(f"\n   best single channel for lempel_ziv: {lz.get('best_single_channel')} "
          f"at mono={lz.get('best_single_mono')} -- reported as an ANECDOTE, since it is the maximum over "
          f"{lz.get('n_single_channels_computable')} electrodes and the median is the result.")
    print("\n   SCOPE: the deposit is average-referenced, and average referencing is itself a spatial")
    print("   operation, so a 'single channel' here is one channel OF an average-referenced montage -- not")
    print("   what a one-electrode device records. These numbers are an UPPER BOUND on true single-electrode")
    print("   performance and that limitation cannot be removed by analysis.")

    dst = os.path.join(RESULTS, "e06_channel_sweep.json")
    json.dump({"experiment": "E06", "summary": summary,
               "predictions": {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)},
               "frontal_single_median_mono_lempel_ziv": frm},
              open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
