#!/usr/bin/env python3
"""The window-length question on real EEG, where there is no ground truth -- so we score PREDICTION instead.

On simulated data we can ask which estimator is closest to the true p_t. On real EEG we cannot: no such truth
exists. But we can ask something that needs no truth and is arguably more useful: **given everything observed
up to now, which estimator better predicts what the EEG does next?** That is a proper scoring rule, it is
strictly causal, and it is exactly the setting the estimator was proposed for -- tracking a patient forward.

THE COMPARISON, at each window length W:
    predict the suppression in window k+1 using only data up to the end of window k, with
      ratio       the pooled fraction over window k alone
      cumulative  the pooled fraction over the whole recording so far   <- the baseline that must be beaten
      bsp_last    the causally filtered BSP at the final bin of window k
      bsp_mean    the causally filtered BSP averaged over window k
    scored by binomial log-loss on the observed counts in window k+1 (lower is better).

LOOK-AHEAD CONTROL, because rule 10 of the error catalogue was paid for. sigma^2 is estimated by EM on the
FIRST 30 % of each recording only, then held fixed while the forward filter runs over the rest. Scoring uses
only windows lying entirely after that burn-in. Nothing in the score sees an observation from its own future.
Fitting sigma^2 on the whole recording, which is what a retrospective analysis would do, is exactly the leak
that would make BSP look good for the wrong reason.

REGISTERED PREDICTION. If the simulation result holds -- that BSP's short-window advantage comes from borrowing
strength across time rather than from the model applied to the same data -- then on real EEG the BSP predictors
should beat the single-window ratio at SHORT windows and converge to it at long ones, while the cumulative
baseline should beat everything when the recording is close to stationary. FALSIFIED IF BSP never beats the
trailing ratio at any window length.
"""
import csv, math, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bsp import bsp, _filter

SEQ = os.environ.get("ICARE_SEQ_OUT", "/tmp/eeg_probe/icare_suppseq.csv")
# Recordings whose frames were glued together across an interior dropout are excluded: see
# analysis/icare_seq_gap_check.py, which found one recording in 24 with a 1,817 s hole closed up, and
# analysis/icare_seq_exclusions.py, which identifies them from the WFDB headers. A closed-up hole is
# invisible in a burden and looks to BSP like an abrupt jump that never happened. Set ICARE_KEEP=none to
# reproduce the unfiltered run as a sensitivity comparison.
KEEP = os.environ.get("ICARE_KEEP", "/tmp/eeg_probe/icare_seq_keep.csv")
NFRAMES = 10
WINDOWS = [300, 120, 60, 30, 15, 8, 4, 2, 1]
BURN = 0.30
MIN_BINS = 240          # need enough after burn-in for the long windows to have several instances
EPS = 1e-4


def logloss(p, n, N):
    """Binomial log-loss per frame for a constant predicted probability p over a window."""
    p = min(max(p, EPS), 1 - EPS)
    return -(n.sum() * math.log(p) + (N.sum() - n.sum()) * math.log(1 - p)) / N.sum()


def one_recording(counts):
    n = np.asarray(counts, float)
    T = len(n)
    if T < MIN_BINS:
        return None
    N = np.full(T, float(NFRAMES))
    b = int(T * BURN)
    if b < 30:
        return None

    # sigma^2 from the burn-in ONLY, then frozen. This is the whole look-ahead control.
    try:
        s2 = float(bsp(n[:b], N[:b])["sigma2"])
    except Exception:
        return None
    _, _, xf, _ = _filter(n, N, s2)
    pf = 1.0 / (1.0 + np.exp(-np.clip(xf, -30, 30)))

    out = {}
    for W in WINDOWS:
        # windows must lie entirely at or after the burn-in, and be followed by a full window
        starts = list(range(b, T - 2 * W + 1, W))
        if len(starts) < 3:
            continue
        acc = {k: [] for k in ("ratio", "cumulative", "bsp_last", "bsp_mean")}
        for s in starts:
            cur, nxt = slice(s, s + W), slice(s + W, s + 2 * W)
            nn, NN = n[nxt], N[nxt]
            acc["ratio"].append(logloss(n[cur].sum() / N[cur].sum(), nn, NN))
            acc["cumulative"].append(logloss(n[:s + W].sum() / N[:s + W].sum(), nn, NN))
            acc["bsp_last"].append(logloss(float(pf[s + W - 1]), nn, NN))
            acc["bsp_mean"].append(logloss(float(pf[cur].mean()), nn, NN))
        out[W] = {k: float(np.mean(v)) for k, v in acc.items()}
        out[W]["nwin"] = len(starts)
        # agreement, the real-data analogue of the simulation's correlation column
        r_ratio = np.array([n[s:s + W].sum() / N[s:s + W].sum() for s in starts])
        r_bsp = np.array([pf[s:s + W].mean() for s in starts])
        out[W]["corr"] = (float(np.corrcoef(r_ratio, r_bsp)[0, 1])
                          if r_ratio.std() > 1e-9 and r_bsp.std() > 1e-9 else float("nan"))
    return out


def main():
    if not os.path.exists(SEQ):
        print(f"*** {SEQ} not found -- run analysis/icare_topography.py first")
        return 1
    keep = None
    if KEEP != "none":
        if not os.path.exists(KEEP):
            print(f"*** {KEEP} not found -- run analysis/icare_seq_exclusions.py first, or set "
                  f"ICARE_KEEP=none to run unfiltered")
            return 1
        keep = {r["pid"].strip() for r in csv.DictReader(open(KEEP))}
        assert keep, f"{KEEP} is empty -- the exclusion step failed rather than passed"

    recs, dropped = [], 0
    for r in csv.DictReader(open(SEQ)):
        pid = (r.get("pid") or "").strip()
        c = (r.get("counts_per_second") or "").split()
        if len(c) < MIN_BINS:
            continue
        if keep is not None and pid not in keep:
            dropped += 1
            continue
        try:
            recs.append([int(v) for v in c])
        except ValueError:
            continue
    assert recs, f"{SEQ} yielded no recording with >= {MIN_BINS} bins -- check the extraction"
    print("interior-gap filter: " + ("DISABLED (sensitivity run)" if keep is None else
          f"{dropped:,} recordings excluded for glued-together dropouts"))
    print(f"recordings with at least {MIN_BINS} s of usable signal: {len(recs):,}")
    lens = [len(c) for c in recs]
    print(f"   length: median {np.median(lens):.0f} s, IQR {np.percentile(lens,25):.0f}-"
          f"{np.percentile(lens,75):.0f} s")
    supp = [np.mean(c) / NFRAMES for c in recs]
    print(f"   suppression burden: median {np.median(supp):.3f}")

    res = []
    for i, c in enumerate(recs, 1):
        r = one_recording(c)
        if r:
            res.append(r)
        if i % 50 == 0:
            print(f"   {i}/{len(recs)} recordings ({len(res)} usable)", flush=True)

    print(f"   usable after burn-in: {len(res):,}")
    assert res, "no recording survived the burn-in requirement"

    print("\n" + "=" * 100)
    print("ONE-STEP-AHEAD BINOMIAL LOG-LOSS (lower is better). Strictly causal: sigma^2 from the first 30 %.")
    print("=" * 100)
    print(f"{'window':>7} {'recs':>6} {'ratio':>9} {'cumulative':>11} {'bsp_last':>9} {'bsp_mean':>9} "
          f"{'best':>11} {'corr(ratio,':>12}")
    print(f"{'(s)':>7} {'':>6} {'trailing':>9} {'baseline':>11} {'':>9} {'':>9} {'':>11} {'bsp)':>12}")
    print("-" * 100)
    summary = {}
    for W in WINDOWS:
        rows = [r[W] for r in res if W in r]
        if len(rows) < 20:
            continue
        m = {k: float(np.mean([x[k] for x in rows])) for k in
             ("ratio", "cumulative", "bsp_last", "bsp_mean")}
        cor = float(np.nanmean([x["corr"] for x in rows]))
        best = min(m, key=m.get)
        summary[W] = (m, cor, len(rows), best)
        print(f"{W:>7} {len(rows):>6} {m['ratio']:>9.4f} {m['cumulative']:>11.4f} {m['bsp_last']:>9.4f} "
              f"{m['bsp_mean']:>9.4f} {best:>11} {cor:>12.3f}")

    print("\n" + "=" * 100)
    print("PAIRED, PER-RECORDING: how often does BSP beat the trailing ratio on the same recording?")
    print("=" * 100)
    print(f"{'window':>7} {'bsp_last wins':>15} {'mean improvement':>18} {'95% CI':>26}")
    print("-" * 100)
    rng = np.random.default_rng(20260727)
    for W in WINDOWS:
        rows = [r[W] for r in res if W in r]
        if len(rows) < 20:
            continue
        d = np.array([x["ratio"] - x["bsp_last"] for x in rows])   # positive = BSP better
        bs = [np.mean(d[rng.integers(0, len(d), len(d))]) for _ in range(1000)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"{W:>7} {100*np.mean(d>0):>14.1f}% {np.mean(d):>+18.4f} "
              f"[{lo:>+10.4f},{hi:>+10.4f}]{'  *' if lo > 0 else ''}")
    print("   * = paired bootstrap CI excludes zero, i.e. BSP is genuinely ahead at that window length.")

    if summary:
        beaten = sorted(W for W, (m, c, k, b) in summary.items() if b != "ratio")
        never = sorted(W for W, (m, c, k, b) in summary.items() if b == "ratio")
        print(f"\n   windows where something beats the trailing ratio: {beaten}")
        print(f"   windows where the trailing ratio is best:          {never}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
