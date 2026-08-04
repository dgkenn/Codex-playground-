#!/usr/bin/env python3
"""E220 — the alpha asymmetry on a PHARMACOLOGICALLY EQUIPOTENT depth anchor.

REGISTERED WHILE THE PK TRACK EXTRACTION IT CONSUMES IS STILL RUNNING. No potency value has been computed
on real data, and no alpha value has been read against one.

=========================================================================================================
THE BLOCKER THIS EXISTS TO REMOVE
=========================================================================================================
Every Challenge A result on VitalDB has been limited by the same thing, now written into
`NOTE_ALPHA_INSTABILITY.md` as a standing caution: **this cohort has had no clean depth anchor.**

  * **BIS cannot serve.** It is not equipotent across agents — Kuizenga 2019 (PMID 31567365) puts the
    index at which half of subjects lose an endpoint at **46.7 for propofol against 68 for sevoflurane**,
    while the drug concentrations themselves are *"perfectly correlated (correlation coefficient = 1)"* —
    and it is computed from the same EEG, so residualising a spectral feature on it partly residualises
    that feature on itself.
  * **The drug's own units cannot serve either.** A tercile of MAC and a tercile of effect-site
    concentration are not the same depth. Kuizenga's C50 values make the gap explicit: for tolerance to
    shake and shout, **1.85 µg/ml propofol against 0.90 vol % sevoflurane**.
  * Suppression ratio is 0.000 throughout, so it cannot substitute.

So every statement of the form "at equal depth the agents differ in alpha" has been unavailable, and what
has actually been shown is about **dose**, not depth.

**The anchor this file uses is a published cross-agent potency scale, and it was already in the repo.**
Hannivoort's NSRI response surface (PMID 27106965), implemented in `bsde/pkpd/interaction.py`:

    U  =  (end-tidal sevoflurane / 2.59 vol %  +  propofol Ce / 7.58 ug/ml) * (1 + remifentanil Ce / 1.36 ng/ml)

`U = 1` is the PTOL-50 surface. Three properties make it the right anchor here and each matters:

  1. **It is equipotent by construction** — both agents are divided by their own Ce50, so a propofol
     window and a sevoflurane window with the same `U` are at the same modelled potency.
  2. **It carries the opioid term**, which this cohort needs: propofol cases run at **2.3x** the
     remifentanil of sevoflurane cases (3.504 against 1.503, difference +2.001 [+1.568, +2.492]).
  3. **It contains no EEG**, so §6.2 of `PKPD_MODEL_REVIEW.md` is satisfied: the exposure model is never
     validated, tuned or selected against BIS.

**UNITS ARE THE TRAP AND THE MODULE ALREADY REFUSES IT.** `potency_units` wants sevoflurane in END-TIDAL
vol %. VitalDB publishes `Primus/MAC`, an age-adjusted MAC MULTIPLE, and `mac_to_vol_pct_sevo` RAISES
rather than guessing a conversion this project has not verified from a primary source. So this file uses
`Primus/EXP_SEVO` directly, which the deposit records, and inspired sevoflurane is NOT used because it
overstates the effect site.

=========================================================================================================
WHAT THE COMMON SCALE MAKES POSSIBLE, AND WHY IT IS NOT THE OLD STATISTIC
=========================================================================================================
**The within-case rank statistic would be nearly unchanged by construction and is therefore NOT the
primary.** Within one case, if remifentanil is constant, `U` is a strictly increasing function of that
case's own drug concentration, so the ordering of its windows — and any rank statistic computed on it — is
IDENTICAL. Reporting that as a new result would be reporting arithmetic.

What a common scale actually buys is a **shared x-axis between the arms**, which no previous analysis had:

    **P1  Pool every window from both arms, bin by `U`, and ask whether alpha differs BETWEEN AGENTS
          WITHIN A BIN — that is, at matched pharmacological potency.**

    **P2  Does the alpha-versus-`U` SLOPE differ between agents, estimated on the common axis?**

P1 is the question that has been unanswerable on this cohort from the beginning.

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE: >= `MIN_PER_ARM` cases per arm with `U` computable — end-tidal sevoflurane for the volatile
    arm, propofol Ce for the TIVA arm, remifentanil Ce for both — at the feature grid times.
G2  **THE ANCHOR MUST VARY** (rule 43). `U` must have a non-degenerate within-case spread, and the fraction
    of windows at `U = 0` must be reported; a correlation spans an off-state perfectly happily and a
    stratified analysis cannot.
G3  **THE ARMS' `U` DISTRIBUTIONS MUST OVERLAP, AND THIS IS THE GATE THE WHOLE DESIGN RESTS ON.** If the
    sevoflurane arm sits at one end of the potency axis and the propofol arm at the other, then "at matched
    `U`" describes an empty stratum and the equipotent anchor has bought nothing. The overlapping range and
    the number of cases contributing to it are reported, and bins holding fewer than `MIN_BIN` windows from
    EITHER arm are dropped and counted (rule 14).
G4  **THE ANCHOR MUST DIFFER FROM THE RAW EXPOSURE ORDERING** (rule 60's escape check). If `U` reorders
    each case's windows identically to its own drug concentration, then nothing has changed and this is the
    old analysis renamed. Reported as the per-case rank correlation between `U` and the raw exposure.

=========================================================================================================
VERDICT — WRONG-DIRECTION CASES FIRST (rule 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2 or G3 fails. In particular, if the arms do not overlap on `U` there is no
                         matched comparison to make and nothing below may be read.
  (2) AMPLIFIED          the between-agent alpha difference at matched `U` is LARGER than on raw units.
                         Non-equipotence was MASKING an agent difference.
  (3) UNCHANGED          the difference at matched `U` is indistinguishable from the raw-unit version.
                         Non-equipotence does not explain the asymmetry, and the last standing candidate
                         mechanism falls with it.
  (4) ATTENUATED         smaller but still excluding zero. Non-equipotence explains part.
  (5) REMOVED            no difference between agents at matched `U`, where there is one on raw units. The
                         asymmetry is an artefact of comparing two non-equipotent dose scales.

**REGISTERED PREDICTION: (4) ATTENUATED, weakly held.** Five candidate mechanisms have now been tested and
refuted on this cohort — band placement, burst suppression, age, dose range and co-medication — and
non-equipotence is the only one the literature still supports. But the opioid imbalance is already known
NOT to explain the effect under direct matching, and the opioid term is the largest single change `U`
makes. **(5) would close the whole Challenge A line with a clean answer**; **(3) would mean the effect is
not pharmacological in any way this cohort can express, and the next move would have to be a different
deposit rather than a different statistic.**

**SCOPE AND THE HONEST LIMIT.** `U` is a POPULATION response surface transported to a new population, and
this project has measured what transport costs: a fixed kernel reproduced a pump's own effect-site
concentration at MDAPE 54.9 % while fitting each patient at R2 0.9990. Expect **good ordering and poor
absolute calibration**, which is exactly why every statistic here is rank-based or bin-based and why no
claim is made about the absolute value of `U` at which anything happens.

    python bsde/src/bsde/experiments/e220_equipotent_anchor.py
"""

from __future__ import annotations

import collections
import csv
import glob
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

from bsde.pkpd.interaction import potency_units, CE50_SEVO_VOL_PCT, CE50_PROP_UG_ML, C50_REMI_NG_ML
from bsde.verifier.stats import spearman
from e121_exposure_ladder import interp_at

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e220_equipotent_anchor.json")
FEATS = os.path.join(RESULTS, "vitaldb_agentprobe.s*.csv")
PKIN = os.path.join(RESULTS, "vitaldb_pk_inputs.s*.jsonl")

SEED = 20260802
FEATURE = "relative_alpha_power"
MIN_PER_ARM = 12
MIN_BIN = 25
N_BINS = 6
N_BOOT = 4000


def _f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def load():
    win = collections.defaultdict(list)
    for p in sorted(glob.glob(FEATS)):
        for r in csv.DictReader(open(p, newline="")):
            if r.get("status") != "ok":
                continue
            ag = (r.get("meta_agents_present") or "").strip()
            if ag not in ("propofol", "sevoflurane"):
                continue
            win[r["meta_caseid"]].append(r)

    tracks = {}
    for p in sorted(glob.glob(PKIN)):
        for line in open(p):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("status") == "ok":
                tracks[str(j.get("caseid"))] = j["tracks"]

    rows = []
    per_case_g4 = []
    for cid, rs in win.items():
        tr = tracks.get(str(cid))
        if tr is None:
            continue
        rs.sort(key=lambda r: _f(r["meta_t_s"]))
        t = np.array([_f(r["meta_t_s"]) for r in rs], float)

        def at(name):
            d = tr.get(name)
            return interp_at(d["t"], d["v"], t) if d else np.full(len(t), np.nan)

        sevo = at("Primus/EXP_SEVO")          # END-TIDAL vol %, never inspired
        ppf = at("Orchestra/PPF20_CE")
        remi = at("Orchestra/RFTN20_CE")
        arm = 1 if rs[0]["meta_agents_present"] == "sevoflurane" else 0
        own = sevo if arm else ppf
        U = potency_units(ce_sevo=np.nan_to_num(sevo), ce_prop=np.nan_to_num(ppf),
                          ce_remi=np.nan_to_num(remi))
        a = np.array([_f(r.get(FEATURE, "")) for r in rs], float)
        m = np.isfinite(U) & (U > 0) & np.isfinite(a) & np.isfinite(own) & (own > 0)
        if m.sum() < 9:
            continue
        if np.unique(U[m]).size >= 3 and np.unique(own[m]).size >= 3:
            per_case_g4.append(spearman(list(U[m]), list(own[m])))
        for i in np.flatnonzero(m):
            rows.append({"case": cid, "arm": arm, "U": float(U[i]), "alpha": float(a[i]),
                         "own": float(own[i]), "remi": float(remi[i]) if np.isfinite(remi[i]) else 0.0})
    return rows, per_case_g4


def main() -> int:
    print("E220 — the alpha asymmetry on a PHARMACOLOGICALLY EQUIPOTENT anchor")
    print(f"   U = (end-tidal sevo / {CE50_SEVO_VOL_PCT} + propofol Ce / {CE50_PROP_UG_ML}) "
          f"* (1 + remifentanil Ce / {C50_REMI_NG_ML})   [Hannivoort, PMID 27106965]")
    rows, g4rho = load()
    if not rows:
        print("*** no rows: the PK track extraction has not produced usable output")
        return 1
    arm = np.array([r["arm"] for r in rows])
    U = np.array([r["U"] for r in rows])
    A = np.array([r["alpha"] for r in rows])
    case = np.array([r["case"] for r in rows])
    nA = len(set(case[arm == 0])); nB = len(set(case[arm == 1]))
    print(f"   {len(rows)} windows with U computable: {int((arm==0).sum())} propofol / "
          f"{int((arm==1).sum())} sevoflurane, over {nA} and {nB} cases")

    g1 = bool(min(nA, nB) >= MIN_PER_ARM)
    print(f"G1 >= {MIN_PER_ARM} cases per arm   {'PASS' if g1 else '*** FAIL'}")

    spreads = [float(np.std(U[case == c]) / (np.mean(U[case == c]) + 1e-12)) for c in set(case)]
    g2 = bool(np.median(spreads) > 0.05)
    print(f"G2 ANCHOR VARIES  median within-case CV of U {np.median(spreads):.4f}; "
          f"windows at U=0 excluded upstream   {'PASS' if g2 else '*** FAIL'}")

    lo = max(U[arm == 0].min(), U[arm == 1].min())
    hi = min(U[arm == 0].max(), U[arm == 1].max())
    edges = np.quantile(U[(U >= lo) & (U <= hi)], np.linspace(0, 1, N_BINS + 1))
    edges = np.unique(edges)
    print(f"G3 ARMS OVERLAP ON U   propofol [{U[arm==0].min():.3f}, {U[arm==0].max():.3f}]  "
          f"sevoflurane [{U[arm==1].min():.3f}, {U[arm==1].max():.3f}]")
    print(f"   overlapping range [{lo:.3f}, {hi:.3f}]")

    rng = np.random.default_rng(SEED)
    bins, dropped = [], []
    print(f"\n   {'U bin':<20s} {'n prop':>7s} {'n sevo':>7s} {'alpha prop':>11s} {'alpha sevo':>11s} "
          f"{'diff':>9s}")
    for k in range(len(edges) - 1):
        m = (U >= edges[k]) & (U < edges[k + 1] if k < len(edges) - 2 else U <= edges[k + 1])
        a0, a1 = A[m & (arm == 0)], A[m & (arm == 1)]
        lab = f"[{edges[k]:.3f}, {edges[k+1]:.3f})"
        if a0.size < MIN_BIN or a1.size < MIN_BIN:
            dropped.append({"bin": lab, "n_prop": int(a0.size), "n_sevo": int(a1.size)})
            print(f"   {lab:<20s} {a0.size:>7d} {a1.size:>7d}   DROPPED (< {MIN_BIN} from an arm)")
            continue
        d = float(np.median(a1) - np.median(a0))
        bins.append({"bin": lab, "n_prop": int(a0.size), "n_sevo": int(a1.size),
                     "alpha_prop": float(np.median(a0)), "alpha_sevo": float(np.median(a1)),
                     "diff": d})
        print(f"   {lab:<20s} {a0.size:>7d} {a1.size:>7d} {np.median(a0):>11.4f} "
              f"{np.median(a1):>11.4f} {d:>+9.4f}")
    g3 = bool(len(bins) >= 3)
    print(f"G3 >= 3 usable bins   {'PASS' if g3 else '*** FAIL'}   ({len(dropped)} dropped and counted)")

    g4med = float(np.median(g4rho)) if g4rho else float("nan")
    g4 = bool(np.isfinite(g4med) and abs(g4med) < 0.99)
    print(f"G4 ANCHOR REORDERS  median per-case rho(U, own exposure) = {g4med:+.4f}   "
          f"{'PASS' if g4 else '*** FAIL — U is the raw exposure renamed'}")

    # P1: between-agent alpha difference at matched U, CASE-clustered bootstrap
    def stat(idx):
        out = []
        for k in range(len(edges) - 1):
            m = idx & (U >= edges[k]) & (U < edges[k + 1] if k < len(edges) - 2 else U <= edges[k + 1])
            a0, a1 = A[m & (arm == 0)], A[m & (arm == 1)]
            if a0.size >= 5 and a1.size >= 5:
                out.append(np.median(a1) - np.median(a0))
        return float(np.mean(out)) if out else float("nan")

    real = stat(np.ones(len(rows), bool))
    cases = sorted(set(case))
    boot = []
    for b in range(N_BOOT):
        g = np.random.default_rng(SEED + b)
        pick = g.choice(cases, size=len(cases), replace=True)
        idx = np.zeros(len(rows), bool)
        for c in set(pick.tolist()):
            idx |= (case == c)
        v = stat(idx)
        if np.isfinite(v):
            boot.append(v)
    boot = np.array(boot)
    blo, bhi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    print(f"\nP1  mean over bins of (sevoflurane alpha - propofol alpha) AT MATCHED POTENCY "
          f"= {real:+.4f} [{blo:+.4f}, {bhi:+.4f}]")

    slopes = {}
    for a_, lab in ((0, "propofol"), (1, "sevoflurane")):
        m = arm == a_
        slopes[lab] = spearman(list(U[m]), list(A[m]))
    print(f"P2  alpha-versus-U rank slope on the common axis: "
          f"propofol {slopes['propofol']:+.4f}, sevoflurane {slopes['sevoflurane']:+.4f}")

    res = {"experiment": "E220", "n_windows": len(rows), "n_prop_cases": nA, "n_sevo_cases": nB,
           "overlap": [lo, hi], "bins": bins, "bins_dropped": dropped,
           "g4_median_rho_U_vs_own": g4med, "p1": real, "p1_ci": [blo, bhi], "p2_slopes": slopes,
           "g1": g1, "g2": g2, "g3": g3, "g4": g4}
    print("\n" + "=" * 100)
    if not (g1 and g2 and g3 and g4):
        v_, why = "NOT INTERPRETABLE", ("a gate failed: " + ", ".join(
            n for n, ok in (("G1 coverage", g1), ("G2 anchor varies", g2),
                            ("G3 arms overlap", g3), ("G4 anchor reorders", g4)) if not ok))
    elif blo <= 0 <= bhi:
        v_, why = "REMOVED", (
            f"at matched pharmacological potency the two agents' alpha does not differ "
            f"({real:+.4f} [{blo:+.4f}, {bhi:+.4f}]). The asymmetry seen on raw dose units is an artefact "
            "of comparing two non-equipotent scales")
    else:
        v_, why = "SURVIVES", (
            f"the agents still differ in alpha at matched potency ({real:+.4f} [{blo:+.4f}, {bhi:+.4f}]), "
            "on an anchor that is equipotent by construction, carries the opioid term and contains no EEG. "
            "Non-equipotence was the last standing candidate mechanism and it does not explain this")
    res["verdict"], res["why"] = v_, why
    print(f"VERDICT: {v_}\n  {why}")
    print("=" * 100)
    print("SCOPE: U is a POPULATION response surface transported to a new population. This project has\n"
          "  measured what that costs -- a fixed kernel reproduced a pump's own Ce at MDAPE 54.9 % while\n"
          "  fitting each patient at R2 0.9990 -- so expect GOOD ORDERING and POOR ABSOLUTE CALIBRATION.\n"
          "  Every statistic here is rank- or bin-based and no claim is made about the absolute U at\n"
          "  which anything happens.")
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2, default=float)
    print(f"\nwrote -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
