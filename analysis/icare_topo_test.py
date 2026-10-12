#!/usr/bin/env python3
"""Does the SPATIAL distribution of slowing carry outcome information the median-across-channels measures lost?

THE GAP THIS ATTACKS. R358-R360 found the clinician's "generalized slowing" flag still carries
-0.752 [-1.075, -0.434] after adjusting for suppression burden AND our intra-burst 8-30 Hz measure. B3 then
showed the whole-record background spectrum does not explain that residual either -- the two spectral measures
turned out mutually redundant. The ledger names four candidates for what the human reader is seeing that we are
not. Only one of them is measurable in this schema: **spatial distribution**. Every spectral feature this
project has computed takes a median across channels, which discards topography by construction.

REGISTERED, before the data was looked at (see `analysis/icare_topography.py` for the same text at extraction
time, which is the version that matters):

  T1  PRIMARY. The antero-posterior gradient in relative slow power (frontal - posterior) is HIGHER in good
      outcome: a preserved posterior faster background steepens it, diffuse injury flattens it.
  T2  SECONDARY. Across-channel SD of relative slow power is LOWER in poor outcome -- uniform injury slows
      uniformly.
  T3  DECISIVE. The pre-specified topographic block {ap_slow_grad, slow_sd, lr_asym} carries outcome
      information after adjusting for burden AND whole-record slow fraction AND intra-burst 8-30 Hz content.
      FALSIFIED IF it adds nothing, in which case the spatial dimension is not what the human reader is seeing
      and two of the four named candidates remain.
  T4  COVERAGE, as in B4. Report performance among the patients the morphology channel structurally cannot see.

MULTIPLICITY, declared rather than discovered. T1 is the single primary test. slow_sd, sef_sd, slow_range,
lr_asym and ap_sef_grad are secondary and are reported together so that the reader can see the whole family
rather than the best member of it. T3 uses a fixed three-term block chosen before looking, not the subset that
performed best in T1/T2.

THE LIMIT THAT TRAVELS WITH THIS. The clinician flag is a HEEDB variable; I-CARE has no equivalent. This
therefore cannot show that topography explains the flag residual. It tests the necessary condition -- that
spatial information carries outcome signal the non-spatial measures do not. A negative here kills the
hypothesis; a positive is suggestive and not confirmatory.
"""
import csv, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icare_morph_replication import logit_fit, auc, cv_auc, oob_increment

COHORT = os.environ.get("ICARE_COHORT", "/tmp/eeg_probe/icare_cohort.csv")
TOPO = os.environ.get("ICARE_TOPO_OUT", "/tmp/eeg_probe/icare_topo.csv")
BG = os.environ.get("ICARE_BG_OUT", "/tmp/eeg_probe/icare_background.csv")
MORPH = os.environ.get("ICARE_MORPH_OUT", "/tmp/eeg_probe/icare_morph2.csv")
NBOOT = int(os.environ.get("NBOOT", "600"))

SECONDARY = ["slow_sd", "sef_sd", "slow_range", "lr_asym", "ap_sef_grad"]
BLOCK = ["ap_slow_grad", "slow_sd", "lr_asym"]      # T3, fixed in advance


def load_num(path, fields, key="pid"):
    out = {}
    for r in csv.DictReader(open(path)):
        pid = (r.get(key) or "").strip()
        if not pid:
            continue
        try:
            d = {f: float(r[f]) for f in fields}
        except (KeyError, TypeError, ValueError):
            continue
        if all(v == v and abs(v) < 1e12 for v in d.values()):
            out[pid] = d
    return out


def diff_ci(x, y, rng, reps):
    """Bootstrap CI for mean(good) - mean(poor)."""
    n = len(y); bs = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        a0, a1 = x[i][y[i] == 0], x[i][y[i] == 1]
        if len(a0) > 10 and len(a1) > 10:
            bs.append(a0.mean() - a1.mean())
    if len(bs) < 50:
        return float("nan"), float("nan")
    return tuple(np.percentile(bs, [2.5, 97.5]))


def main():
    rng = np.random.default_rng(20260727)

    coh = {}
    for r in csv.DictReader(open(COHORT)):
        pid = (r.get("pid") or "").strip()
        try:
            cpc = float(r.get("cpc"))
        except (TypeError, ValueError):
            continue
        if pid and cpc == cpc:
            coh[pid] = 1.0 if cpc >= 3 else 0.0

    topo = load_num(TOPO, ["ap_slow_grad", "ap_sef_grad", "slow_sd", "sef_sd", "slow_range",
                           "lr_asym", "burden", "med_slow", "n_pairs"])
    bg = load_num(BG, ["w_slow_frac"])
    morph = load_num(MORPH, ["alpha_beta"])

    # Rule 5 of the error catalogue: an empty result is not evidence until the join is shown able to match.
    assert topo, f"{TOPO} produced no usable rows -- extraction incomplete or column names changed"
    assert bg, f"{BG} produced no usable rows"
    assert morph, f"{MORPH} produced no usable rows"

    both = sorted(p for p in topo if p in coh)
    n = len(both)
    print(f"I-CARE patients with topography and an outcome: {n:,}")
    if n < 150:
        print("*** extraction still running; rerun when it completes")
        return 1
    y = np.array([coh[p] for p in both])
    print(f"   poor outcome {100*y.mean():.1f}%   "
          f"median derivations per patient {np.median([topo[p]['n_pairs'] for p in both]):.0f}")

    def col(name, keys=None):
        return np.array([topo[p][name] for p in (keys or both)])

    # ---- T1 --------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("T1  PRIMARY -- IS THE ANTERO-POSTERIOR SLOWING GRADIENT STEEPER IN GOOD OUTCOME?")
    print("=" * 96)
    g = col("ap_slow_grad")
    d = g[y == 0].mean() - g[y == 1].mean()
    lo, hi = diff_ci(g, y, rng, NBOOT)
    print(f"   frontal-minus-posterior slow fraction:  good {g[y==0].mean():+.4f}   poor {g[y==1].mean():+.4f}")
    print(f"   difference (good - poor) {d:+.4f} [{lo:+.4f},{hi:+.4f}]   "
          f"{'CONFIRMED' if lo > 0 else ('REVERSED -- the gradient is steeper in POOR outcome' if hi < 0 else 'null')}")
    print(f"   AUC of the gradient alone: {auc(y, -g):.3f}")

    # ---- T2 and the rest of the family -------------------------------------------------------------
    print("\n" + "=" * 96)
    print("T2 + SECONDARY FAMILY -- reported whole, not best-of")
    print("=" * 96)
    print(f"{'measure':>14} {'good':>10} {'poor':>10} {'diff':>10} {'95% CI':>22} {'AUC':>7}")
    print("-" * 96)
    for name in SECONDARY:
        v = col(name)
        dd = v[y == 0].mean() - v[y == 1].mean()
        l2, h2 = diff_ci(v, y, rng, NBOOT)
        a = auc(y, -v)
        star = "*" if (l2 > 0 or h2 < 0) else " "
        print(f"{name:>14} {v[y==0].mean():>10.4f} {v[y==1].mean():>10.4f} {dd:>+10.4f} "
              f"[{l2:>+8.4f},{h2:>+8.4f}]{star} {max(a, 1-a):>7.3f}")
    print("   * = bootstrap CI excludes zero.  These are five secondary tests; read them as a family.")

    # ---- T3 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("T3  DECISIVE -- DOES THE TOPOGRAPHIC BLOCK ADD OVER BURDEN + BACKGROUND + INTRA-BURST?")
    print("=" * 96)
    tri = sorted(p for p in both if p in bg and p in morph)
    m = len(tri)
    print(f"   patients with all four measurement families: {m:,}")
    if m < 150:
        print("   too few for the decisive arm")
        return 0
    yy = np.array([coh[p] for p in tri])
    o = np.ones(m)
    bur = np.array([topo[p]["burden"] for p in tri])
    slw = np.array([bg[p]["w_slow_frac"] for p in tri])
    ab = np.array([morph[p]["alpha_beta"] for p in tri])
    blk = np.column_stack([col(k, tri) for k in BLOCK])

    Xbase = np.column_stack([o, bur, slw, ab])
    Xtopo = np.column_stack([Xbase, blk])
    inc, l3, h3, k3 = oob_increment(Xbase, Xtopo, yy, rng)
    print(f"   burden + background slow + intra-burst 8-30 Hz   CV AUC {cv_auc(Xbase, yy, rng):.3f}")
    print(f"   + topographic block {BLOCK}")
    print(f"                                                    CV AUC {cv_auc(Xtopo, yy, rng):.3f}")
    print(f"   out-of-bag increment {inc:+.3f} [{l3:+.3f},{h3:+.3f}] ({k3} reps)")
    print(f"   T3 {'CONFIRMED -- spatial information is not redundant with the non-spatial measures' if l3 > 0 else 'FALSIFIED -- topography adds nothing beyond what we already measure'}")

    # a cheaper, more interpretable companion: burden alone -> + topography
    Xb = np.column_stack([o, bur])
    i2, l4, h4, _ = oob_increment(Xb, np.column_stack([Xb, blk]), yy, rng)
    print(f"\n   companion: over BURDEN ALONE the same block adds {i2:+.3f} [{l4:+.3f},{h4:+.3f}]"
          f"  ({'adds' if l4 > 0 else 'n.s.'})")
    print("   If it adds over burden but not over burden+spectra, topography is a third view of the same")
    print("   spectral factor rather than a new one -- the same verdict B3 reached for the background.")

    # ---- T4 ----------------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("T4  COVERAGE -- the patients the morphology channel structurally cannot see")
    print("=" * 96)
    nom = [p for p in both if p not in morph]
    print(f"   topography measurable but morphology NOT: {len(nom):,} patients")
    if len(nom) >= 40:
        yn = np.array([coh[p] for p in nom])
        bn = np.array([topo[p]["burden"] for p in nom])
        print(f"   their poor-outcome rate {100*yn.mean():.1f}%   median burden {np.median(bn):.3f}")
        if 0 < yn.sum() < len(yn):
            for name in ["ap_slow_grad"] + SECONDARY:
                v = np.array([topo[p][name] for p in nom])
                a = auc(yn, -v)
                print(f"      {name:>14} AUC in this subgroup {max(a, 1-a):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
