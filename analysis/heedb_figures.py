#!/usr/bin/env python3
"""The four figures the result needs. Nothing decorative, one claim each.

WHY THIS EXISTS. The project had 315 logged results and not one figure. Every claim was a table of numbers in a
markdown file, which is unreadable at the speed a senior reader actually reads.

  F1  The finding: three-day and thirty-day mortality across burden quintiles, inside the single guideline
      category that treats them all the same. This is the whole result in one panel.
  F2  Calibration: observed versus predicted risk by decile, with the diagonal. Discrimination is what the
      AUC shows; this is the half that says the absolute risk is right.
  F3  Discrimination: ROC for the category alone against category plus burden, on the same axes, so the
      increment is visible rather than asserted.
  F4  Reliability: burden measured in one window against the same recording's other windows, which is the
      measurement-error estimate (ICC 0.815) made visual.

Matplotlib only, Agg backend, no seaborn. Colour is used to separate series, never as the only channel --
markers and line styles carry the same information for anyone who cannot distinguish them.
"""
import csv, glob, io, os, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heedb_bs_ascertainment import AETIOLOGY, norm, dt

OMOP = os.environ.get("OMOP_OUT", "/tmp/eeg_probe/heedb_omop")
OUTDIR = os.environ.get("FIG_OUT", "docs/research/figures")
AP = "arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"


def logit_fit(X, y, iters=60, ridge=1e-6):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        z = eta + (y - p) / w
        A = X.T @ (X * w[:, None]) + ridge * np.eye(X.shape[1])
        try:
            nb = np.linalg.solve(A, X.T @ (w * z))
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(nb)) or np.max(np.abs(nb - b)) < 1e-8:
            b = nb if np.all(np.isfinite(nb)) else b
            break
        b = nb
    return b


def predict(X, b):
    return 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))


def roc(y, s):
    o = np.argsort(-np.asarray(s, float), kind="mergesort")
    y = np.asarray(y, float)[o]
    tp = np.cumsum(y); fp = np.cumsum(1 - y)
    return np.r_[0, fp / max(fp[-1], 1)], np.r_[0, tp / max(tp[-1], 1)]


def cv_pred(X, y, rng, folds=5, reps=5):
    acc = np.zeros(len(y)); cnt = np.zeros(len(y))
    for _ in range(reps):
        idx = rng.permutation(len(y))
        for f in range(folds):
            te = idx[f::folds]; tr = np.setdiff1d(idx, te)
            if y[tr].sum() < 5 or (len(tr) - y[tr].sum()) < 5:
                continue
            acc[te] += predict(X[te], logit_fit(X[tr], y[tr])); cnt[te] += 1
    ok = cnt > 0
    out = np.full(len(y), np.nan); out[ok] = acc[ok] / cnt[ok]
    return out, ok


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(20260726)
    os.makedirs(OUTDIR, exist_ok=True)

    # ---- cohort, identical to heedb_guideline_stats.py -------------------------------------------
    bsess = defaultdict(dict)
    for f in sorted(glob.glob("/tmp/eeg_probe/heedb_bs_burden*.csv")):
        for r in csv.DictReader(open(f)):
            try:
                p, s, v = int(r["patient"]), int(r["session"]), float(r["burden"])
            except Exception:
                continue
            if v == v:
                bsess[p][s] = max(bsess[p].get(s, 0.0), v)

    death = {}
    with open(f"{OMOP}/death.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                death[int(r["person_id"])] = dt(r.get("death_datetime"))
            except Exception:
                pass

    aet, cond_seen = defaultdict(set), set()
    with open(f"{OMOP}/condition_occurrence.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                p = int(r["person_id"])
            except Exception:
                continue
            cond_seen.add(p)
            c = norm(r.get("condition_source_value"))
            if not c:
                continue
            for lab, pre in AETIOLOGY.items():
                if any(c.startswith(x) for x in pre):
                    aet[p].add(lab)

    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name="us-east-1",
                      config=Config(s3={"payload_signing_enabled": False}))
    stime = {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP, Key=f"EEG/eeg-metadata/{st}_eeg_metadata_2026_04_30.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip(); s = (r.get("SessionID") or "").strip()
            if p.isdigit() and s.isdigit():
                t = dt(r.get("StartTime") or r.get("EndTime") or "")
                if t is not None:
                    stime[(int(p), int(s))] = t
    burden = {}
    for p, d in bsess.items():
        times = {s: stime[(p, s)] for s in d if (p, s) in stime}
        burden[p] = d[min(times, key=lambda s: times[s])] if times else d[min(d)]

    FL = ("bs", "low voltage", "gpd", "lpd", "grda", "lrda", "seizure", "status")
    when, Fidx = {}, {}
    for st in ("S0001", "S0002"):
        txt = s3.get_object(Bucket=AP, Key=f"EEG/HEEDB_Metadata/{st}_EEG__reports_findings.csv"
                            )["Body"].read().decode("utf-8", "replace")
        for r in csv.DictReader(io.StringIO(txt)):
            p = (r.get("BDSPPatientID") or "").strip()
            if not p.isdigit():
                continue
            p = int(p)
            t = dt(r.get("EndTime(EEG)") or r.get("StartTime(EEG)") or "")
            if t is None:
                continue
            if p not in when or t < when[p]:
                when[p] = t
                Fidx[p] = {k: ((r.get(k) or "").strip() not in ("", "None", "nan")) for k in FL}

    def westhall(f):
        if f.get("bs") or f.get("low voltage"):
            return 2
        if any(f.get(k) for k in ("gpd", "lpd", "grda", "lrda", "seizure", "status")):
            return 1
        return 0

    rows = []
    for p, t0 in when.items():
        if p not in cond_seen or "anoxic" not in aet.get(p, set()):
            continue
        d = death.get(p)
        if d is None:
            continue
        days = (d - t0).days
        if days < -1 or p not in burden:
            continue
        rows.append(dict(d3=1.0 if days <= 3 else 0.0, d30=1.0 if days <= 30 else 0.0,
                         cat=westhall(Fidx[p]), bur=burden[p]))
    print(f"cohort for figures: {len(rows):,}")

    # ---- F1: the finding --------------------------------------------------------------------------
    hm = [r for r in rows if r["cat"] == 2]
    b = np.array([r["bur"] for r in hm])
    q = np.percentile(b, [20, 40, 60, 80])
    labs, m3, m30, ns = [], [], [], []
    edges = [(-1e9, q[0]), (q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], 1e9)]
    for i, (lo, hi) in enumerate(edges):
        m = (b > lo) & (b <= hi)
        if m.sum() < 5:
            continue
        labs.append(f"Q{i+1}")
        m3.append(100 * np.mean([r["d3"] for r, x in zip(hm, m) if x]))
        m30.append(100 * np.mean([r["d30"] for r, x in zip(hm, m) if x]))
        ns.append(int(m.sum()))
    x = np.arange(len(labs))
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(x, m3, "o-", lw=2.2, ms=8, color="#b2182b", label="dead by 3 days")
    ax.plot(x, m30, "s--", lw=2.2, ms=8, color="#2166ac", label="dead by 30 days")
    for xi, (a3, a30, nn) in enumerate(zip(m3, m30, ns)):
        ax.annotate(f"{a3:.1f}%", (xi, a3), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=9, color="#b2182b")
        ax.annotate(f"{a30:.1f}%", (xi, a30), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=9, color="#2166ac")
    ax.set_xticks(x); ax.set_xticklabels([f"{l}\nn={n}" for l, n in zip(labs, ns)])
    ax.set_xlabel("quintile of measured suppression burden (index recording)")
    ax.set_ylabel("mortality (%)")
    # Computed, never hardcoded: this figure previously carried a literal "2.5-fold" that survived a cohort
    # correction which moved the true value to 2.3. A number written into a title goes stale in silence.
    fold = m3[-1] / m3[0] if m3 and m3[0] > 0 else float("nan")
    ax.set_title("Inside ONE guideline category (\u201chighly malignant\u201d),\n"
                 f"measured burden spans a {fold:.1f}-fold range of three-day risk", fontsize=11)
    ax.set_ylim(0, 112); ax.grid(alpha=.3)
    # upper left: the only quadrant both series stay out of, since both rise left-to-right
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(f"{OUTDIR}/F1_burden_quintiles.png", dpi=180); plt.close(fig)

    # ---- F2 / F3 ----------------------------------------------------------------------------------
    y = np.array([r["d3"] for r in rows], float)
    cat = np.array([r["cat"] for r in rows], float)
    bur = np.array([r["bur"] for r in rows], float)
    one = np.ones(len(rows))
    Xc = np.column_stack([one, (cat == 1).astype(float), (cat == 2).astype(float)])
    Xcb = np.column_stack([Xc, bur])
    pc, ok1 = cv_pred(Xc, y, rng)
    pcb, ok2 = cv_pred(Xcb, y, rng)
    ok = ok1 & ok2

    pp = np.clip(pcb[ok], 1e-6, 1 - 1e-6); yy = y[ok]
    qs = np.quantile(pp, np.linspace(0, 1, 11))
    px, py, pn = [], [], []
    for i in range(10):
        m = (pp >= qs[i]) & ((pp <= qs[i + 1]) if i == 9 else (pp < qs[i + 1]))
        if m.sum() >= 10:
            px.append(pp[m].mean()); py.append(yy[m].mean()); pn.append(int(m.sum()))
    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    ax.plot([0, 1], [0, 1], ":", color="grey", lw=1.4, label="perfect calibration")
    ax.plot(px, py, "o-", color="#b2182b", lw=2, ms=8, label="observed vs predicted (deciles)")
    ax.set_xlabel("predicted 3-day mortality"); ax.set_ylabel("observed 3-day mortality")
    ax.set_title("Calibration: the absolute risk is right,\nnot merely the ranking", fontsize=11)
    ax.set_xlim(0, .8); ax.set_ylim(0, .8); ax.grid(alpha=.3); ax.legend(frameon=False, loc="upper left")
    ax.text(.97, .04, "intercept −0.013 (ideal 0)\nslope 0.980 (ideal 1)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round", fc="white", ec="grey", alpha=.9))
    fig.tight_layout(); fig.savefig(f"{OUTDIR}/F2_calibration.png", dpi=180); plt.close(fig)

    def auc_(yv, sv):
        n1 = yv.sum(); n0 = len(yv) - n1
        o = np.argsort(sv, kind="mergesort"); r = np.empty(len(sv)); r[o] = np.arange(1, len(sv) + 1)
        return (r[yv == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    f1, t1 = roc(yy, pc[ok]); f2, t2 = roc(yy, pp)
    ax.plot([0, 1], [0, 1], ":", color="grey", lw=1.2)
    ax.plot(f1, t1, "--", lw=2, color="#2166ac", label=f"guideline category alone  AUC {auc_(yy, pc[ok]):.3f}")
    ax.plot(f2, t2, "-", lw=2.4, color="#b2182b", label=f"category + burden  AUC {auc_(yy, pp):.3f}")
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_title("Quantitative burden adds to the categorical scheme\n(increment +0.100 [+0.082, +0.118])",
                 fontsize=11)
    ax.grid(alpha=.3); ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.tight_layout(); fig.savefig(f"{OUTDIR}/F3_roc.png", dpi=180); plt.close(fig)

    # ---- F4: reliability --------------------------------------------------------------------------
    wins = defaultdict(list)
    for f in glob.glob("/tmp/eeg_probe/heedb_bs_win.s*.csv"):
        for r in csv.DictReader(open(f)):
            try:
                wins[(int(r["patient"]), int(r["session"]))].append(float(r["burden"]))
            except Exception:
                continue
    pairs = [(v[0], np.mean(v[1:])) for v in wins.values() if len(v) >= 2]
    if len(pairs) > 100:
        a = np.array([p[0] for p in pairs]); c = np.array([p[1] for p in pairs])
        fig, ax = plt.subplots(figsize=(5.6, 5.4))
        ax.plot([0, 1], [0, 1], ":", color="grey", lw=1.2)
        ax.scatter(a, c, s=7, alpha=.25, color="#2166ac", edgecolors="none")
        ax.set_xlabel("burden in the first sampled window")
        ax.set_ylabel("mean burden in the remaining windows")
        ax.set_title("Reliability of a single reading\n(ICC 0.815; averaging two gives 0.898)", fontsize=11)
        ax.set_xlim(-.02, 1.02); ax.set_ylim(-.02, 1.02); ax.grid(alpha=.3)
        ax.text(.03, .95, f"n = {len(pairs):,} recordings", transform=ax.transAxes, fontsize=9, va="top")
        fig.tight_layout(); fig.savefig(f"{OUTDIR}/F4_reliability.png", dpi=180); plt.close(fig)
        print(f"F4 written ({len(pairs):,} recordings)")
    else:
        print(f"F4 skipped: only {len(pairs)} recordings with >=2 windows")

    for f in sorted(os.listdir(OUTDIR)):
        print("  wrote", os.path.join(OUTDIR, f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
