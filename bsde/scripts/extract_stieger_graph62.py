"""Stieger network measures on ALL 62 channels, with null-normalised variants and a non-graph family.

WHY THIS EXISTS, and it is a correction to E73's instrument rather than a new idea.

E73 returned Challenge B's first interpretable null on `wpli_alpha_global_efficiency`, and the finding
underneath it was that the primary was not a network measure at all: across 62 subject means it correlated
with `wpli_alpha_mean_degree` at **+0.9962** and with plain `wpli_alpha` at **+0.8639**. Rule 60 was
written from that.

**The mechanism has since been located and it is worse than a bad choice of statistic.**
`extract_stieger_features.py` computes every connectivity measure on a **10-channel** montage
(`Fp1 Fp2 F3 F4 C3 C4 P3 P4 O1 O2`) -- confirmed, `n_channels_used` is 10 in all 185 rows. On a
near-complete 10-node weighted graph there is almost no topology for a graph measure to express: nearly
every shortest path is the direct edge, so efficiency IS mean weight. **E73's own registration gave
"Stieger's 62 channels carry inter-channel phase; every previous Challenge B deposit could not" as the
reason the design could finally be run, and then ran it on ten of them.** That does not invalidate E73's
null -- the primary was computed as specified and its gates passed -- but it does mean the null is not
about network topology, and it is why this pass exists.

WHAT CHANGES, AND WHAT DELIBERATELY DOES NOT. All 62 channels; `wpli_matrix` (validated pair-by-pair
against the tested `wpli` in `tests/test_wpli_matrix.py`) instead of a Python loop over pairs, which is
what makes 1,891 pairs per epoch affordable where 45 was the previous budget. Epoch selection, band edges,
the 2 s pre-cue window and the median-across-epochs reduction are unchanged, so this table is comparable
to the existing one on the measures they share.

THE MEASURES, and why each is here (rule 60: a measure chosen for escaping a family must be SHOWN to
escape it -- the check is run before any registration, in `e80` prep, not asserted here):

    ge, cl, deg            global efficiency, Onnela clustering, mean degree -- the E73 three, recomputed
                           at 62 nodes so the orthogonality check can be repeated at a scale where a graph
                           measure can differ from mean strength
    ge_norm, cl_norm       each divided by its mean over `N_NULL` weight-SHUFFLED graphs. Shuffling the
                           off-diagonal weights preserves the weight distribution exactly and destroys
                           topology, **so overall connection strength cancels by construction** -- this is
                           the standard small-worldness normalisation and it is the direct fix for the
                           defect E73 exposed
    smallworld             cl_norm / ge_norm
    modularity             Newman Q from a spectral bipartition of the weighted graph, normalised by total
                           edge weight and therefore scale-free
    strength_cv            coefficient of variation of node strength -- heterogeneity, not amount
    iaf, alpha_prom        individual alpha frequency and its prominence ABOVE the fitted aperiodic
                           component. A different family entirely: a periodic-component property, not a
                           connectivity or an amplitude summary, and a documented correlate of BCI aptitude

Written to `stieger_graph62.csv`, a NEW table joined on (subject, session). The existing
`stieger_features.csv` is untouched, so every number E41, E68 and E73 report stays reproducible against
the file each actually used.

    python bsde/scripts/extract_stieger_graph62.py --sessions-per-subject 3
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from bsde.features.connectivity import wpli_matrix                          # noqa: E402

OUT = os.path.join(HERE, "..", "results", "stieger_graph62.csv")
FIGSHARE = "https://api.figshare.com/v2/articles/13123148/files?page_size=1000"
NAME = re.compile(r"^S(\d+)_Session_(\d+)\.mat$")

SFREQ = 1000.0
PRE_CUE_S = 2.0
MAX_EPOCHS = 120
ALPHA = (8.0, 13.0)
N_NULL = 20
SEED = 20260731

GRAPH = ["ge", "cl", "deg", "ge_norm", "cl_norm", "smallworld", "modularity", "strength_cv"]
PERIODIC = ["iaf", "alpha_prom"]
FIELDS = ["subject", "session", "n_epochs", "n_channels_used"] + GRAPH + PERIODIC


def file_index():
    with urllib.request.urlopen(FIGSHARE, timeout=120) as fh:
        import json
        return json.loads(fh.read().decode())


def _efficiency(A):
    n = A.shape[0]
    with np.errstate(divide="ignore"):
        D = np.where(A > 0, 1.0 / A, np.inf)
    np.fill_diagonal(D, 0.0)
    for k in range(n):
        D = np.minimum(D, D[:, k][:, None] + D[k, :][None, :])
    off = ~np.eye(n, dtype=bool)
    v = D[off]
    v = v[np.isfinite(v) & (v > 0)]
    return float(np.mean(1.0 / v)) if v.size else float("nan")


def _clustering(A):
    Aw = A / (A.max() if A.max() > 0 else 1.0)
    cub = np.cbrt(Aw)
    tri = np.diag(cub @ cub @ cub)
    k = (A > 0).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(k > 1, tri / (k * (k - 1)), np.nan)
    return float(np.nanmean(c))


def _modularity(A):
    """Newman Q for the best spectral bipartition of a weighted graph. Q is a fraction of total weight,
    so it cannot be inflated by scaling every edge -- which is the property rule 60 asks for."""
    s = A.sum(axis=1)
    m2 = A.sum()
    if m2 <= 0:
        return float("nan")
    B = A - np.outer(s, s) / m2
    w, v = np.linalg.eigh((B + B.T) / 2.0)
    lead = v[:, int(np.argmax(w))]
    g = np.where(lead >= 0, 1.0, -1.0)
    same = (g[:, None] == g[None, :]).astype(float)
    return float((B * same).sum() / m2)


def _null_graphs(A, rng, n_null=N_NULL):
    """Weight-shuffled nulls: the multiset of off-diagonal weights is preserved EXACTLY and the topology
    is destroyed, so any ratio against these is independent of overall connection strength."""
    n = A.shape[0]
    iu = np.triu_indices(n, k=1)
    vals = A[iu]
    out = []
    for _ in range(n_null):
        B = np.zeros_like(A)
        p = rng.permutation(vals)
        B[iu] = p
        B = B + B.T
        out.append(B)
    return out


def graph_features(W, rng):
    A = np.clip(np.nan_to_num(W, nan=0.0), 0, None)     # debiased wPLI can be negative; clip at 0
    np.fill_diagonal(A, 0.0)
    n = A.shape[0]
    ge, cl = _efficiency(A), _clustering(A)
    deg = float(A.sum(axis=1).mean() / max(1, n - 1))
    nulls = _null_graphs(A, rng)
    ge_n = float(np.nanmean([_efficiency(B) for B in nulls]))
    cl_n = float(np.nanmean([_clustering(B) for B in nulls]))
    s = A.sum(axis=1)
    return {"ge": ge, "cl": cl, "deg": deg,
            "ge_norm": ge / ge_n if ge_n and np.isfinite(ge_n) and ge_n > 0 else float("nan"),
            "cl_norm": cl / cl_n if cl_n and np.isfinite(cl_n) and cl_n > 0 else float("nan"),
            "smallworld": ((cl / cl_n) / (ge / ge_n)
                           if all(np.isfinite([cl_n, ge_n, ge])) and cl_n > 0 and ge_n > 0 and ge > 0
                           else float("nan")),
            "modularity": _modularity(A),
            "strength_cv": float(s.std() / s.mean()) if s.mean() > 0 else float("nan")}


def periodic_features(X):
    """Individual alpha frequency and its prominence ABOVE the aperiodic fit, median over channels.

    Not `relative_alpha_power` under another name: that is the band's total power including the aperiodic
    background, while this is the position and height of the periodic bump on top of it.
    """
    from bsde.features.aperiodic import fit_aperiodic, welch_psd
    iafs, proms = [], []
    for c in range(X.shape[0]):
        try:
            f, p = welch_psd(X[c], SFREQ, window_s=1.0, overlap=0.5)
            fit = fit_aperiodic(f, p, 1.0, 40.0, "loglog_robust")
            bg = 10.0 ** (fit["offset"] - fit["exponent"] * np.log10(np.clip(f, 1e-9, None)))
            band = (f >= 7.0) & (f <= 13.0)
            if band.sum() < 2:
                continue
            resid = np.log10(np.clip(p[band], 1e-30, None)) - np.log10(np.clip(bg[band], 1e-30, None))
            k = int(np.argmax(resid))
            iafs.append(float(f[band][k]))
            proms.append(float(resid[k]))
        except Exception:                                                   # noqa: BLE001
            continue
    return {"iaf": float(np.nanmedian(iafs)) if iafs else float("nan"),
            "alpha_prom": float(np.nanmedian(proms)) if proms else float("nan")}


def session_features(path, subject, session, rng):
    from scipy.io import loadmat
    bci = loadmat(path, struct_as_record=False, squeeze_me=True)["BCI"]
    labels = [str(x) for x in np.atleast_1d(bci.chaninfo.label)]
    data = bci.data
    n_pre = int(PRE_CUE_S * SFREQ)
    n_ep = min(MAX_EPOCHS, len(data))
    wmats, per_ep_periodic = [], []
    for e in range(n_ep):
        seg = np.asarray(data[e], float)[:, :n_pre]
        if seg.shape[0] != len(labels) or not np.isfinite(seg).all():
            continue
        wmats.append(wpli_matrix(seg, SFREQ, *ALPHA, window_s=0.5))
        if len(per_ep_periodic) < 20:                  # the PSD fit is the expensive part; 20 is plenty
            per_ep_periodic.append(periodic_features(seg))
    if not wmats:
        raise ValueError("no usable epochs")
    W = np.nanmedian(np.stack(wmats), axis=0)
    out = graph_features(W, rng)
    out.update({k: float(np.nanmedian([p[k] for p in per_ep_periodic])) for k in PERIODIC})
    out.update({"subject": subject, "session": session,
                "n_epochs": len(wmats), "n_channels_used": len(labels)})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions-per-subject", type=int, default=3, dest="k")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--tmp", default="/tmp/eeg_probe/stieger_g62")
    a = ap.parse_args(argv)

    files = file_index()
    want = []
    for f in files:
        m = NAME.match(f["name"])
        if m and int(m.group(2)) <= a.k:
            want.append((m.group(1), m.group(2), f))
    want.sort(key=lambda t: (int(t[0]), int(t[1])))

    out_path = os.path.abspath(a.out)
    done = set()
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        with open(out_path, newline="") as fh:
            done = {(r["subject"], r["session"]) for r in csv.DictReader(fh)}
    todo = [t for t in want if (t[0], t[1]) not in done]
    print(f"{len(want)} sessions wanted, {len(done)} done, {len(todo)} to go", flush=True)

    os.makedirs(a.tmp, exist_ok=True)
    new = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    rng = np.random.default_rng(SEED)
    with open(out_path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i, (subj, sess, f) in enumerate(todo, 1):
            dest = os.path.join(a.tmp, f["name"])
            try:
                urllib.request.urlretrieve(f["download_url"], dest)
                row = session_features(dest, subj, sess, rng)
                w.writerow({k: row.get(k, "") for k in FIELDS})
                fh.flush()
                print(f"   [{i}/{len(todo)}] S{subj} s{sess}: {row['n_epochs']} epochs, "
                      f"{row['n_channels_used']} ch, ge {row['ge']:.4f}, cl_norm {row['cl_norm']:.4f}, "
                      f"iaf {row['iaf']:.2f}", flush=True)
            except Exception as e:                                          # noqa: BLE001
                print(f"   [{i}/{len(todo)}] S{subj} s{sess}: FAIL {type(e).__name__}: {e}", flush=True)
            finally:
                if os.path.exists(dest):
                    os.remove(dest)
    print(f"   wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
