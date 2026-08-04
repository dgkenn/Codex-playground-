"""E181 — the same question with a GRADED outcome, discovered on the sessions that killed the binary one.

REGISTERED BEFORE ANY TRIAL-LENGTH STATISTIC HAS BEEN COMPUTED.

=========================================================================================================
WHY A GRADED OUTCOME, AND WHY NOW RATHER THAN AS A CONSOLATION
=========================================================================================================
E172 found a pre-cue alpha effect on Stieger session 1 (0.5176, p = 0.0060) and **E174 did not replicate
it** on 123 held-out sessions with 10,504 pairs — every gate green, a measured floor of rho = 0.05, and
`mu_mean` at 0.4991 with one-sided p = 0.5700. The binary hit/miss question is answered: no.

**The argument for a graded outcome is one this project already made in writing, to someone else.**
`DATA_REQUEST_MGH_RESPONSE_PROBABILITY.md` asks the MGH group for the continuous response-probability
series behind their binary label, on the grounds that *"a graded response probability turns [one usable
observation per subject per transition] into a continuous regression on hundreds of epochs per subject,
which is roughly a two-order-of-magnitude increase in the information available from the same recordings"*.
**Stieger already ships the graded version and this project has never used it**: `triallength`, the
time-to-target on each trial, captured by the per-trial extractor and never analysed.

A binary hit says the command was followed. A time-to-target says **how easily**. If the pre-cue state
matters at all, it should show there before it shows in a coin flip.

=========================================================================================================
THE DESIGN REUSES THE ONE INSTRUMENT THAT PASSED ITS GATES
=========================================================================================================
E167 died twice trying to regress the clock out. E172 and E174 removed it by CONSTRUCTION, pairing trials
that are adjacent in time, and that instrument passed every gate on both cohorts (trial index as a
candidate: 0.4920/p = 0.2070 and 0.5000/p = 0.9900). **So the graded outcome is turned into a matched
contrast rather than a regression**: within each session, hits are split at the running median trial
length into FAST and SLOW, and each fast hit is matched to the nearest slow hit within `MAX_GAP` trials.
Everything else — the statistic, the exact within-pair flip null, the cluster bootstrap over subjects, the
noise control, the rho ladder — is E172's, unchanged, and the pairing is directionally balanced as E174's
one repair established it must be.

=========================================================================================================
DISCOVERY AND CONFIRMATION, DECLARED BEFORE EITHER IS RUN
=========================================================================================================
    DISCOVERY     Stieger sessions 2 and 3 — 123 sessions, ~55,800 trials. **The cohort that killed the
                  binary effect.** Two-sided, because no direction is known for trial length.
    CONFIRMATION  Stieger session 1 — 62 sessions. Run ONLY if discovery returns a positive, and then
                  ONE-SIDED in the direction discovery found.

Session 1 has been used before, for the BINARY question, and never for this estimand — so it is an
untouched test set for trial length and a used one for hit rate. That distinction is stated here rather
than glossed: it is a weaker guarantee than a never-touched deposit, and it is the strongest available.

=========================================================================================================
THE SELECTION PROBLEM, WHICH GETS CODE AND NOT A CAVEAT (rules 13, 54)
=========================================================================================================
Trial length is only defined for a trial that reached the target, so this analysis conditions on SUCCESS —
a variable downstream of the pre-cue state. If pre-cue alpha raised the probability of a hit, then
conditioning on hits would select on the predictor and bias the contrast. That is a collider.

**G4 measures it rather than assuming it away.** The pre-cue predictor's association with hit/miss is
recomputed in this exact cohort by E172's own statistic. E174 measured it at 0.4991 with p = 0.5700, i.e.
absent — but it is re-measured here, and if it is NOT absent the file reports NOT INTERPRETABLE, because
then the graded analysis is conditioning on a collider and no verdict is available.

**G5 checks the outcome is graded rather than censored.** A trial that times out is a miss and is already
excluded; but if the surviving trial lengths pile up against a ceiling the "graded" outcome is a binary
one wearing a continuous label (rule 70's family). The fraction of hits within 5 % of the session's
maximum trial length is printed, and a distribution that is more than `CENSOR_MAX` piled there fails.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 60 discovery sessions with >= 30 fast/slow pairs.
G2  (a) the pairing is directionally balanced against its own flip null; (b) trial index scored as a
    candidate is at chance.
G3  (a) an i.i.d. noise feature is NOT detected; (b) a rho ladder gives the measured floor, and no
    detected rung means every null is ABSENT rather than negative.
G4  the pre-cue predictor does NOT predict hit/miss in this cohort (the collider check above).
G5  the outcome is graded, not censored.

=========================================================================================================
VERDICT — THE FAILING AND UNINFORMATIVE CASES FIRST (rules 31, 37)
=========================================================================================================
  (1) NOT INTERPRETABLE  G1, G2, G3(a), G4 or G5 fails.
  (2) NO POWER           G3(b) detects nothing at any rung.
  (3) ABSENT ABOVE FLOOR the primary's two-sided p > 0.05 with a floor established. **The graded outcome
                         buys nothing over the binary one**, and the pre-cue state does not matter for
                         command-following in this deposit at all — which, with E174, would close the
                         trial-level Challenge B line on Stieger.
  (4) NOT CLAIMED        p <= 0.05 but fewer than half the sessions share the sign.
  (5) DISCOVERED         p <= 0.05 with a majority sign. The confirmation arm on session 1 then runs
                         one-sided, and only a pass there is reported as a finding.

**REGISTERED PREDICTION: (3) ABSENT ABOVE FLOOR.** E174 measured the binary effect at exactly chance on
these sessions, and E176's arithmetic on the same table puts the within-session point-biserial correlation
between `mu_mean` and hit at +0.0255. There is no reason to expect a graded outcome to rescue a signal
that is not there — the graded-outcome argument buys sensitivity, not signal. **This file is worth running
because it costs one run to close the line properly rather than by assumption**, and because a positive
would be genuinely surprising and therefore worth much more than a confirmatory one.

    python bsde/src/bsde/experiments/e181_trial_length_graded_outcome.py
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
from bsde.verifier.stats import screen_candidates                              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e181_trial_length_graded_outcome.json")
SEED = 20260801

DISCOVERY_GLOB = "stieger_holdout_trials*.csv"       # sessions 2 and 3
CONFIRM_GLOB = "stieger_trials.s*.csv"               # session 1
PRIMARY = E172.PRIMARY
CANDIDATES = list(E172.CANDIDATES)
MIN_PAIRS = 30
MIN_SESSIONS = 60
MAX_GAP = E172.MAX_GAP
CENSOR_MAX = 0.25
ALPHA = 0.05
Q = 0.05


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(pattern):
    seen, rows = set(), []
    for p in sorted(glob.glob(os.path.join(RESULTS, pattern))):
        if os.path.getsize(p) == 0:
            continue
        for r in csv.DictReader(open(p, newline="")):
            k = (r["subject"], r["session"], r["trial"])
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    by = {}
    for r in rows:
        by.setdefault((r["subject"], r["session"]), []).append(r)
    for k in by:
        by[k].sort(key=lambda r: int(float(r["trial"])))
    return by, len(rows)


def build_graded(pattern):
    """Sessions with FAST/SLOW hit pairs. `_fast` is 1 on the faster member, so the statistic reads the
    same way as E172's (fraction of pairs where the feature is larger on the 'good' trial)."""
    by, n_rows = load(pattern)
    sess, censored = [], []
    for (subj, s), rr in sorted(by.items()):
        res = np.array([_f(r["result"]) for r in rr])
        tl = np.array([_f(r["triallength"]) for r in rr])
        hit = np.isfinite(res) & (res > 0.5) & np.isfinite(tl) & (tl > 0)
        if hit.sum() < 2 * MIN_PAIRS:
            continue
        v = tl[hit]
        censored.append(float(np.mean(v >= 0.95 * v.max())))
        med = float(np.median(v))
        fast = np.full(len(rr), np.nan)
        fast[hit] = (tl[hit] < med).astype(float)      # 1 = faster than this session's median hit
        pairs = _balanced_pairs(E172.make_pairs(fast, max_gap=MAX_GAP), subj, s)
        if len(pairs) < MIN_PAIRS:
            continue
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES}
        cols["_index"] = np.arange(len(rr), dtype=float)
        cols["_hit"] = np.where(np.isfinite(res), res, np.nan)
        sess.append({"subject": subj, "session": s, "pairs": pairs, "cols": cols,
                     "n_trials": len(rr), "n_hits": int(hit.sum())})
    return sess, n_rows, (float(np.mean(censored)) if censored else float("nan"))


def build_binary(pattern):
    """E172's own hit/miss pairing on the same rows, for the collider check (G4)."""
    by, _ = load(pattern)
    sess = []
    for (subj, s), rr in sorted(by.items()):
        res = np.array([_f(r["result"]) for r in rr])
        if np.isfinite(res).sum() < E172.MIN_PAIRS:
            continue
        pairs = _balanced_pairs(E172.make_pairs(res, max_gap=MAX_GAP), subj, s)
        if len(pairs) < E172.MIN_PAIRS:
            continue
        cols = {c: np.array([_f(r.get(c, "")) for r in rr]) for c in CANDIDATES}
        cols["_index"] = np.arange(len(rr), dtype=float)
        sess.append({"subject": subj, "session": s, "pairs": pairs, "cols": cols,
                     "n_trials": len(rr)})
    return sess


def run_arm(sess, tag, one_sided=None):
    rng = np.random.default_rng(SEED)
    out = {"tag": tag, "n_sessions": len(sess),
           "total_pairs": int(sum(len(s["pairs"]) for s in sess))}
    gaps = np.concatenate([[h - m for (h, m) in s["pairs"]] for s in sess]).astype(float)
    signed = float(gaps.mean())
    gnull = np.asarray([float((gaps * np.where(rng.integers(0, 2, gaps.size) > 0, -1, 1)).mean())
                        for _ in range(2000)])
    lo, hi = float(np.quantile(gnull, 0.025)), float(np.quantile(gnull, 0.975))
    idx = {(s["subject"], s["session"]): s["cols"]["_index"] for s in sess}
    io, ip, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 2), reps=1000,
                                  override=idx)
    out["G2a"] = {"signed_gap": signed, "null": [lo, hi], "pass": bool(lo <= signed <= hi)}
    out["G2b"] = {"mean": float(io), "p": float(ip), "pass": bool(np.isfinite(ip) and ip > ALPHA)}
    print(f"   [{tag}] G2(a) signed gap {signed:+.4f} in [{lo:+.4f}, {hi:+.4f}]   "
          f"{'PASS' if out['G2a']['pass'] else '*** FAIL'}")
    print(f"   [{tag}] G2(b) trial index {io:.4f}, p = {ip:.4f}   "
          f"{'PASS' if out['G2b']['pass'] else '*** FAIL'}")
    _, p0, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 3), reps=1000,
                                 override=E172.synthetic(sess, 0.0, rng))
    out["G3a"] = {"p": float(p0), "pass": bool(np.isfinite(p0) and p0 > ALPHA)}
    print(f"   [{tag}] G3(a) i.i.d. noise p = {p0:.4f}   "
          f"{'PASS' if out['G3a']['pass'] else '*** FAIL'}")
    floor = None
    ladder = []
    for rho in E172.RUNGS:
        _, p, _, _ = E172.flip_null(sess, PRIMARY, np.random.default_rng(SEED + 4), reps=1000,
                                    override=E172.synthetic(sess, rho, rng))
        ladder.append({"rho": rho, "p": float(p)})
        print(f"   [{tag}] G3(b) rho = {rho:.2f}: p = {p:.4f}")
        if np.isfinite(p) and p <= ALPHA:
            floor = rho
            break
    out["ladder"], out["floor"] = ladder, floor

    pool = {c: np.concatenate([s["cols"][c] for s in sess]) for c in CANDIDATES}
    usable, dropped = screen_candidates(pool)
    for c, why in dropped.items():
        print(f"   [{tag}] dropped: {c} ({why})")
    names = [c for c in CANDIDATES if c in usable]
    table, ps = {}, []
    print(f"\n   [{tag}] {'candidate':<24s} {'frac fast>slow':>15s} {'[95% CI]':>20s} "
          f"{'same side':>10s} {'p':>8s}")
    for c in names:
        st = E172.frac_stat(sess, c)
        obs, p, nm, k = E172.flip_null(sess, c, np.random.default_rng(SEED + 11))
        if one_sided is not None and np.isfinite(p):
            p = p / 2.0 if (np.sign(st["mean"] - 0.5) == one_sided) else 1.0 - p / 2.0
        lo_, hi_ = E172.cluster_ci(st, np.random.default_rng(SEED + 12))
        table[c] = {"mean": st["mean"], "ci": [lo_, hi_], "frac_same_side": st["frac_same_side"],
                    "p": float(p), "n_sessions": st["n_sessions"]}
        ps.append(p)
        print(f"   [{tag}] {c:<24s} {st['mean']:>15.4f} [{lo_:>8.4f},{hi_:>8.4f}] "
              f"{st['frac_same_side']:>10.2f} {p:>8.4f}")
    keep = E172.bh(ps, q=Q)
    out["table"], out["survivors_bh"] = table, [names[i] for i in sorted(keep)]
    print(f"   [{tag}] BH q={Q}: {out['survivors_bh'] or 'none'}")
    return out


def main() -> int:
    print("E181 — pre-cue state and TRIAL LENGTH: discovery on the sessions that killed the binary effect")
    res = {"experiment": "E181"}
    sess, n_rows, censor = build_graded(DISCOVERY_GLOB)
    if not sess:
        print("   ABSENT: no discovery sessions yield fast/slow pairs.")
        json.dump(res, open(OUT, "w"), indent=2)
        return 2
    res["discovery_rows"], res["censored_fraction"] = n_rows, censor
    res["G1_pass"] = bool(len(sess) >= MIN_SESSIONS)
    print(f"   {n_rows} discovery trial rows -> {len(sess)} sessions, "
          f"{sum(len(s['pairs']) for s in sess)} fast/slow pairs")
    print(f"   G1 {'PASS' if res['G1_pass'] else '*** FAIL'} (floor {MIN_SESSIONS} sessions)")
    res["G5"] = {"censored_fraction": censor, "pass": bool(np.isfinite(censor) and censor < CENSOR_MAX)}
    print(f"   G5 outcome graded: {censor:.3f} of hits within 5 % of the session maximum   "
          f"{'PASS' if res['G5']['pass'] else '*** FAIL -- the graded outcome is censored'}")
    if not (res["G1_pass"] and res["G5"]["pass"]):
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # G4 -- the collider check
    bsess = build_binary(DISCOVERY_GLOB)
    bobs, bp, _, _ = E172.flip_null(bsess, PRIMARY, np.random.default_rng(SEED + 21), reps=1000)
    res["G4"] = {"hit_miss_stat": float(bobs), "p": float(bp),
                 "pass": bool(np.isfinite(bp) and bp > ALPHA)}
    print(f"   G4 collider check: {PRIMARY} vs hit/miss in this cohort = {bobs:.4f}, p = {bp:.4f}   "
          f"{'PASS -- conditioning on hits does not select on the predictor' if res['G4']['pass'] else '*** FAIL'}")
    if not res["G4"]["pass"]:
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = ("the predictor DOES move hit/miss here, so conditioning on successful trials selects "
                      "on it and the graded contrast is a collider (rule 13)")
        print("\n   VERDICT NOT INTERPRETABLE — " + res["why"])
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    res["discovery"] = run_arm(sess, "discovery")
    d = res["discovery"]
    if not (d["G2a"]["pass"] and d["G2b"]["pass"] and d["G3a"]["pass"]):
        res["verdict"] = "NOT-INTERPRETABLE"
        res["why"] = "a discovery gate failed"
    elif d["floor"] is None:
        res["verdict"] = "NO-POWER"
        res["why"] = "no injected within-pair effect is detectable; every null here is ABSENT"
    else:
        prim = d["table"][PRIMARY]
        if not (np.isfinite(prim["p"]) and prim["p"] <= ALPHA):
            res["verdict"] = "ABSENT-ABOVE-FLOOR"
            res["why"] = (f"the graded outcome buys nothing: {PRIMARY} at {prim['mean']:.4f}, "
                          f"p = {prim['p']:.4f}, with a floor of rho = {d['floor']:.2f}. With E174 this "
                          "closes the trial-level Challenge B line on Stieger")
        elif np.isfinite(prim["frac_same_side"]) and prim["frac_same_side"] < 0.5:
            res["verdict"] = "NOT-CLAIMED"
            res["why"] = "fewer than half the discovery sessions share the sign"
        else:
            side = 1 if prim["mean"] > 0.5 else -1
            print(f"\n   DISCOVERY POSITIVE ({prim['mean']:.4f}, p = {prim['p']:.4f}) — "
                  "running the CONFIRMATION arm on session 1, one-sided in this direction")
            csess, _, _ = build_graded(CONFIRM_GLOB)
            if len(csess) < 40:
                res["verdict"] = "DISCOVERED-UNCONFIRMED"
                res["why"] = f"only {len(csess)} confirmation sessions; the confirmation arm is ABSENT"
            else:
                res["confirmation"] = run_arm(csess, "confirmation", one_sided=side)
                cp = res["confirmation"]["table"][PRIMARY]
                if np.isfinite(cp["p"]) and cp["p"] <= ALPHA:
                    res["verdict"] = "CONFIRMED"
                    res["why"] = (f"discovery {prim['mean']:.4f} (p = {prim['p']:.4f}) and confirmation "
                                  f"{cp['mean']:.4f} (one-sided p = {cp['p']:.4f}) on an untouched "
                                  "estimand in session 1")
                else:
                    res["verdict"] = "DISCOVERED-NOT-CONFIRMED"
                    res["why"] = (f"discovery {prim['mean']:.4f} did not confirm on session 1 "
                                  f"({cp['mean']:.4f}, one-sided p = {cp['p']:.4f})")
    print(f"\n   VERDICT {res['verdict']} — {res['why']}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
