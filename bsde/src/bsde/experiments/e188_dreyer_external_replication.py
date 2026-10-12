"""E188 — the external test E175 could not run, on a deposit that ships a real EMG channel.

REGISTERED BEFORE ANY DREYER TRIAL VALUE HAS BEEN READ. The extraction was launched in the same change and
its feasibility probe (event codes, trial counts, channel list) is quoted in the extractor's docstring.

=========================================================================================================
WHAT NEEDS AN EXTERNAL TEST, AND WHY EEGMMIDB COULD NOT GIVE ONE
=========================================================================================================
**E181 is the one Challenge B finding that has survived**: pre-cue alpha predicts how FAST a followed
command is executed, discovered on 123 held-out Stieger sessions (`mu_mean` 0.4803, p = 0.0000) and
confirmed on session 1 one-sided (0.4799, p = 0.0255), with the collider gate passing and the clock
removed by construction. **E172's binary version did not survive** (E174: 0.4991, one-sided p = 0.5700, BH
keeps nothing), and **E184 showed E181's effect cannot be spent as a gating rule** (throughput worse at all
six cells by 3.5-7.3 s per delivered trial).

All of that is ONE deposit and ONE laboratory. **E175's external test gate-failed for power**: eegmmidb
gives 45 trials per subject and only 8 of 105 subjects reached 20 matched adjacent pairs.

Dreyer 2023 is the deposit that fixes it: **87 subjects, four online runs of 40 trials each**, 512 Hz, 32
channels, a different laboratory and — unlike eegmmidb — **online BCI control with feedback**, which is
Stieger's construct rather than offline imagery.

=========================================================================================================
TWO ARMS, BECAUSE THERE ARE TWO THINGS TO REPLICATE
=========================================================================================================
Dreyer's GDF carries the cue (769 left / 770 right) but no hit/miss code, and its trials are fixed-length,
so neither Stieger's behavioural hit nor its time-to-target is available. Both arms therefore use a
subject-level cross-validated decoder on the POST-cue band powers, with folds over trials and **the
pre-cue features playing no part in it**, so the label cannot see the predictor.

    ARM A — DECODABILITY (binary).   Correct versus incorrect classification of the cue. This is E172's
        construct and E175's registered one. **Two-sided**, because E172's direction was killed by E174 and
        a one-sided test in a dead direction would be indefensible.
    ARM B — LEGIBILITY (graded).     Among CORRECT trials, high-confidence versus low-confidence, split at
        each subject's own median |predicted probability - 0.5| and matched adjacent, which is exactly
        E181's fast/slow construction with confidence in place of speed. **Two-sided**, and that is the
        stricter choice: E181's direction is established on a different outcome in a different deposit, so
        a one-sided test would be importing more than the evidence supports. Stated so it cannot later be
        read as the design having been weak.

**ARM B is the external test of E181.** ARM A is reported beside it because a null there, with E174's,
would close the binary question on two deposits.

=========================================================================================================
THE ARM NEITHER PREVIOUS DEPOSIT COULD SUPPORT
=========================================================================================================
E172 could not score its incumbent: Stieger's `artifact` flag is 0 in **27,705 of 27,900** trials, so
within a pair both members are almost always tied. Rule 57 records what happened the last time this
project used a constructed EMG proxy as ground truth — `emg_index` correlates with a real submental
channel at rho = +0.20 pooled.

**Dreyer ships `EMGg` and `EMGd` as real channels.** `emg_pre` — their log RMS over the identical pre-cue
window — is scored by the identical statistic as a candidate and as the incumbent (rule 45). If muscle
predicts the outcome and alpha does not, the trial-level Challenge B line is a muscle finding; if alpha
survives with muscle in the panel, the confound is excluded for the first time with a real measurement
rather than an argument.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 50 subjects with >= 25 matched pairs in the arm being read. The floor is set from what the deposit
    can supply — 160 trials per subject at a roughly 70/30 correct/incorrect split gives ~45 minority
    trials, so 25 pairs is achievable and 30 (E172's floor) might not be (rule 63).
G2  **THE DECODER MUST BE ALIVE.** Pooled out-of-fold accuracy must beat a within-subject label
    permutation. If the decoder is at chance, "correct" is a coin flip, there is nothing to predict, and a
    null is uninterpretable rather than negative (rule 53).
G3  (a) the pairing is directionally balanced against its own flip null, using E174's balancing;
    (b) trial index scored as a candidate is at chance.
G4  (a) an i.i.d. noise feature is NOT detected; (b) a rho ladder gives the measured floor, and no
    detected rung means every null in that arm is ABSENT rather than negative (rule 31).

=========================================================================================================
VERDICT PER ARM — THE FAILING AND WRONG-DIRECTION CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE   G1, G2, G3 or G4(a) fails in that arm.
  (2) NO POWER            G4(b) detects nothing at any rung.
  (3) MUSCLE              `emg_pre` clears BH and `mu_mean` does not. The trial-level effect is muscle,
                          measured with a real channel, and the Stieger line is re-read in that light.
  (4) REVERSED            the primary excludes 0.5 on the side opposite to Stieger's. Reported as its own
                          finding, not as a partial success.
  (5) ABSENT ABOVE FLOOR  p > 0.05 with a floor established. **E181 is bounded to Stieger**, and with
                          E174 and E175 the trial-level Challenge B line is closed on three deposits.
  (6) REPLICATED          p <= 0.05 in Stieger's direction with a majority sign and `emg_pre` not
                          explaining it. Then pre-cue alpha's relation to command legibility is a
                          two-deposit finding and the flagship application has something to stand on.

**REGISTERED PREDICTION: (5) ABSENT ABOVE FLOOR in arm A, and no prediction in arm B.** Arm A is E172's
construct and E174 already killed it within Stieger, so a positive would be surprising. **Arm B is
genuinely open**: E181 replicated across session sets but the outcome measure changes here from time to
decoder confidence, and I do not have a basis for a direction or a magnitude. Recording "no prediction" is
more honest than manufacturing one, and it is why arm B is two-sided.

    python bsde/src/bsde/experiments/e188_dreyer_external_replication.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import e172_matched_pair_trial_responsiveness as E172                          # noqa: E402
from e174_trial_replication_heldout_sessions import _balanced_pairs            # noqa: E402
from bsde.verifier.stats import auc, logit_fit, predict_proba, screen_candidates  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e188_dreyer_external_replication.json")
SEED = 20260801

GLOB = "dreyer_trials*.csv"
PRIMARY = "mu_mean"
INCUMBENT = "emg_pre"
CANDIDATES = ["mu_mean", "mu_c3", "mu_c4", "mu_lateralisation",
              "relative_alpha_power", "relative_delta_power", "exponent_low", "exponent_high",
              "whole_head_exponent", "spectral_edge_95", "spectral_entropy", "lempel_ziv", "emg_pre"]
POST_COLS = [f"f{i}" for i in range(6)]
MAX_GAP = E172.MAX_GAP
MIN_PAIRS = 25
MIN_SUBJECTS = 50
FOLDS = 5
ALPHA = 0.05
Q = 0.05


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def decode(X, y, rng, folds=FOLDS):
    """Out-of-fold probabilities from a logistic on the POST-cue band powers only."""
    n = len(y)
    order = rng.permutation(n)
    fold = np.empty(n, int)
    fold[order] = np.arange(n) % folds
    p = np.full(n, np.nan)
    A = np.column_stack([np.ones(n), X])
    for k in range(folds):
        te, tr = fold == k, fold != k
        if te.sum() == 0 or len(np.unique(y[tr])) < 2:
            continue
        try:
            p[te] = predict_proba(A[te], logit_fit(A[tr], y[tr]))
        except Exception:                                                  # noqa: BLE001
            continue
    return p


def load():
    seen, rows = set(), []
    for path in sorted(glob.glob(os.path.join(RESULTS, GLOB))):
        if os.path.getsize(path) == 0:
            continue
        for r in csv.DictReader(open(path, newline="")):
            k = (r["subject"], r["run"], r["trial"])
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        by.setdefault(r["subject"], []).append(r)
    for s in by:
        by[s].sort(key=lambda r: (r["run"], int(float(r["trial"]))))
    return by, len(rows)


def build(arm):
    """arm 'A': correct vs incorrect. arm 'B': high- vs low-confidence among CORRECT trials."""
    by, n_rows = load()
    rng = np.random.default_rng(SEED)
    sess, py, pp = [], [], []
    for sub, rr in sorted(by.items()):
        y = np.array([_f(r["y"]) for r in rr])
        X = np.array([[_f(r[c]) for c in POST_COLS] for r in rr], float)
        ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        if ok.sum() < 60 or len(np.unique(y[ok])) < 2:
            continue
        p = decode(X[ok], y[ok], rng)
        good = np.isfinite(p)
        idx = np.flatnonzero(ok)[good]
        py.append(y[ok][good])
        pp.append(p[good])
        correct = ((p[good] >= 0.5).astype(float) == y[ok][good]).astype(float)
        conf = np.abs(p[good] - 0.5)
        target = np.full(len(rr), np.nan)
        if arm == "A":
            target[idx] = correct
        else:
            c_idx = idx[correct > 0.5]
            c_conf = conf[correct > 0.5]
            if c_idx.size < 2 * MIN_PAIRS:
                continue
            med = float(np.median(c_conf))
            target[c_idx] = (c_conf > med).astype(float)     # 1 = MORE legible
        pairs = _balanced_pairs(E172.make_pairs(target, max_gap=MAX_GAP), sub, arm)
        if len(pairs) < MIN_PAIRS:
            continue
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES}
        cols["_index"] = np.arange(len(rr), dtype=float)
        sess.append({"subject": sub, "session": arm, "pairs": pairs, "cols": cols,
                     "n_trials": len(rr)})
    return (sess, n_rows,
            np.concatenate(py) if py else np.array([]),
            np.concatenate(pp) if pp else np.array([]))


def run_arm(arm, name):
    print(f"\n{'=' * 100}\nARM {arm} — {name}")
    sess, n_rows, py, pp = build(arm)
    out = {"arm": arm, "name": name, "n_trial_rows": n_rows, "n_subjects": len(sess),
           "total_pairs": int(sum(len(s["pairs"]) for s in sess))}
    if not sess:
        out["status"] = "ABSENT"
        print("   ABSENT: no subject yields enough pairs.")
        return out
    print(f"   {n_rows} trial rows -> {len(sess)} subjects, {out['total_pairs']} pairs "
          f"(median {np.median([len(s['pairs']) for s in sess]):.0f})")
    out["G1_pass"] = bool(len(sess) >= MIN_SUBJECTS)
    print(f"   G1 {'PASS' if out['G1_pass'] else '*** FAIL'} (floor {MIN_SUBJECTS} subjects, "
          f"{MIN_PAIRS} pairs)")

    rng = np.random.default_rng(SEED)
    acc = float(np.mean((pp >= 0.5).astype(float) == py)) if py.size else float("nan")
    a = float(auc(py.astype(int), pp)) if py.size else float("nan")
    nul = np.asarray([float(np.mean((pp >= 0.5).astype(float) == rng.permutation(py)))
                      for _ in range(200)]) if py.size else np.array([])
    g2 = bool(nul.size and acc > float(np.quantile(nul, 0.95)))
    out["G2"] = {"accuracy": acc, "auc": a,
                 "null_p95": float(np.quantile(nul, 0.95)) if nul.size else float("nan"),
                 "pass": g2}
    print(f"   G2 decoder alive: pooled out-of-fold accuracy {acc:.4f} (AUC {a:.4f}) vs permuted p95 "
          f"{out['G2']['null_p95']:.4f}   {'PASS' if g2 else '*** FAIL'}")
    if not (out["G1_pass"] and g2):
        out["status"] = "NOT-INTERPRETABLE"
        return out

    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gn = np.asarray([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                     for _ in range(2000)])
    lo, hi = float(np.quantile(gn, 0.025)), float(np.quantile(gn, 0.975))
    idx = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io, ip, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 2), reps=1000,
                                  override=idx)
    out["G3"] = {"signed_gap": signed, "null": [lo, hi], "index_mean": float(io),
                 "index_p": float(ip),
                 "pass": bool(lo <= signed <= hi and np.isfinite(ip) and ip > ALPHA)}
    print(f"   G3 signed gap {signed:+.4f} in [{lo:+.4f}, {hi:+.4f}]; trial index {io:.4f}, "
          f"p = {ip:.4f}   {'PASS' if out['G3']['pass'] else '*** FAIL'}")
    _, p0, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 3), reps=1000,
                                 override=E172.synthetic(sess, 0.0, rng))
    out["G4a"] = {"p": float(p0), "pass": bool(np.isfinite(p0) and p0 > ALPHA)}
    print(f"   G4(a) i.i.d. noise p = {p0:.4f}   {'PASS' if out['G4a']['pass'] else '*** FAIL'}")
    if not (out["G3"]["pass"] and out["G4a"]["pass"]):
        out["status"] = "NOT-INTERPRETABLE"
        return out
    floor, ladder = None, []
    for rho in E172.RUNGS:
        _, p, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 4), reps=1000,
                                    override=E172.synthetic(sess, rho, rng))
        ladder.append({"rho": rho, "p": float(p)})
        print(f"   G4(b) rho = {rho:.2f}: p = {p:.4f}")
        if np.isfinite(p) and p <= ALPHA:
            floor = rho
            break
    out["ladder"], out["floor"] = ladder, floor
    print(f"   FLOOR: {'none' if floor is None else '%.2f' % floor}")

    pool = {c: np.concatenate([s["cols"][c] for s in sess]) for c in CANDIDATES}
    usable, dropped = screen_candidates(pool)
    for c, why in dropped.items():
        print(f"   dropped: {c} ({why})")
    names = [c for c in CANDIDATES if c in usable]
    print(f"\n   {'candidate':<24s} {'frac':>8s} {'[95% CI]':>20s} {'same side':>10s} {'p':>8s}")
    table, ps, cn = {}, [], []
    for c in names:
        st = E172.frac_stat(sess, c)
        obs, p, nm, k = E172.flip_null(sess, c, np.random.default_rng(SEED + 11))
        lo_, hi_ = E172.cluster_ci(st, np.random.default_rng(SEED + 12))
        table[c] = {"mean": st["mean"], "ci": [lo_, hi_], "frac_same_side": st["frac_same_side"],
                    "p": float(p), "n_subjects": st["n_sessions"]}
        if c != INCUMBENT:
            ps.append(p)
            cn.append(c)
        print(f"   {c:<24s} {st['mean']:>8.4f} [{lo_:>8.4f},{hi_:>8.4f}] "
              f"{st['frac_same_side']:>10.2f} {p:>8.4f}"
              + ("   <- INCUMBENT (real EMG)" if c == INCUMBENT else ""))
    keep = E172.bh(ps, q=Q)
    out["table"], out["survivors_bh"] = table, [cn[i] for i in sorted(keep)]
    out["status"] = "OK"
    print(f"   BH q={Q}: {out['survivors_bh'] or 'none'}")

    prim = table.get(PRIMARY, {})
    emg = table.get(INCUMBENT, {})
    emg_hit = bool(np.isfinite(emg.get("p", np.nan)) and emg["p"] <= ALPHA)
    if floor is None:
        v, why = "NO-POWER", "no injected within-pair effect is detectable; every null here is ABSENT"
    elif emg_hit and PRIMARY not in out["survivors_bh"]:
        v, why = "MUSCLE", (f"the real EMG channel predicts the outcome (p = {emg['p']:.4f}) and "
                            f"{PRIMARY} does not clear BH -- the trial-level effect is muscle, measured "
                            "rather than argued")
    elif not (np.isfinite(prim.get("p", np.nan)) and prim["p"] <= ALPHA):
        v, why = "ABSENT-ABOVE-FLOOR", (f"{PRIMARY} at {prim.get('mean', float('nan')):.4f}, "
                                        f"p = {prim.get('p', float('nan')):.4f}, floor rho = {floor:.2f}")
    elif np.isfinite(prim["frac_same_side"]) and prim["frac_same_side"] < 0.5:
        v, why = "NOT-CLAIMED", "fewer than half the subjects share the sign"
    else:
        side = "ABOVE" if prim["mean"] > 0.5 else "BELOW"
        v, why = "PRESENT", (f"{PRIMARY} at {prim['mean']:.4f} ({side} 0.5), p = {prim['p']:.4f}, with "
                             f"the real EMG channel at p = {emg.get('p', float('nan')):.4f}")
    out["verdict"], out["why"] = v, why
    print(f"   ARM {arm} VERDICT {v} — {why}")
    return out


def main() -> int:
    print("E188 — external replication on Dreyer 2023, with a real EMG channel in the panel")
    res = {"experiment": "E188", "deposit": "dreyer-bci-2023"}
    res["arm_A"] = run_arm("A", "decodability: correct vs incorrect (E172/E175's construct)")
    res["arm_B"] = run_arm("B", "legibility: high- vs low-confidence among correct trials (E181's shape)")
    A, B = res["arm_A"], res["arm_B"]
    res["verdict"] = (f"A: {A.get('verdict', A.get('status'))} | B: {B.get('verdict', B.get('status'))}")
    print(f"\n{'=' * 100}\nOVERALL  {res['verdict']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
