#!/usr/bin/env python3
"""E280-E289 -- fourth battery. The confound battery 3 did not check, and the calibration screen it earned.

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY E280 COMES FIRST AND WHY IT COULD SINK EVERYTHING ABOVE IT. E271 found leakage rises monotonically
with anaesthetic depth in 6 of 6 candidates. E260/E270/E273 all compare arms at maintenance. **Nothing has
checked whether the arms SIT AT DIFFERENT DEPTHS.** If sevoflurane cases are run deeper than propofol
cases, then a between-arm contrast at "maintenance" is partly a depth contrast, and E271's own result is
the reason to worry: whatever separates depths will separate arms. This is rule 87's shape -- a property
of practice standing in for a property of the drug -- and it is checkable in one pass.

COHORTS. PERI = 2,589 cases peri-landmark. CTRL = 740 cases at maintenance (arms 249/244/247, analytic
leakage null95 ~ 0.0511). SCOPE unchanged: the label is the AIRWAY RECORD, a brainstem behavioural
output, not consciousness.

======================================================================================================
E280 -- DO THE ARMS SIT AT DIFFERENT DEPTHS?  *the confound check, run before anything else*

Compare control-window median BIS across arms.

PREDICTION: **the arms differ, |AUC-0.5| >= 0.10 for at least one pair.** Volatile and TCI practice
differ, and BIS is not equipotent across agents (Kuizenga 2019: 46.7 propofol vs 68 sevoflurane at
matched behavioural depth), so a BIS difference is expected even at matched true depth.
WRONG IF: the arms are at indistinguishable BIS, which would clear the confound outright.
NOTE THE ASYMMETRY, STATED IN ADVANCE: because BIS is itself non-equipotent, a BIS difference does NOT
prove a true depth difference. E280 can raise the alarm; it cannot settle it, and E281 is the remedy that
does not depend on resolving it.

E281 -- LEAKAGE AFTER MATCHING THE ARMS ON CONTROL-WINDOW BIS

For each pair, retain a subset in which the two arms' control-window BIS distributions overlap
(joint 10-90th percentile trim, then nearest-neighbour 1:1 matching on BIS).

PREDICTION: **leakage retains >= 60 % of its unmatched value** for the top candidates. The drug signature
is not merely a depth difference.
WRONG IF: it collapses below 60 %, which would mean maintenance leakage is substantially a depth contrast
and E260/E270/E271/E273 all need restating. Matching costs n, so the floor rises -- reported alongside.

E282 -- E271'S MONOTONE CURVE AGAINST A PROPER NULL

6 of 6 monotone reads as decisive but was never tested. Permute the BIS values ACROSS CASES WITHIN ARM
(destroying the depth axis, preserving arm composition and tercile sizes) and recount monotone candidates.

PREDICTION: **the permuted count is <= 2 of 6 at the 95th percentile.**
WRONG IF: monotone runs are common under permutation, in which case 6/6 means little and E271 is
descriptive only.

E283 -- PER-DRUG CALIBRATION: WHAT LEAKAGE SURVIVES MEDIAN CENTRING, AND IS IT ABOVE ITS NULL?

E272 showed per-arm median subtraction removes 51-98 %. It never asked whether the RESIDUAL is
significant. Recompute residual leakage with a patient-level permutation null at both states.
**FRAMING, STATED IN ADVANCE:** per-drug centring requires knowing the agent. In the operating theatre
the agent IS known, so this is a deployable calibration and not a cheat -- but it is a different object
from an agent-blind representation, and Challenge A's wording asks for the latter.

PREDICTION: **residual leakage is at or below its null for a majority of top candidates at CTRL.**
WRONG IF: residuals remain significant, meaning the arms differ in shape and no per-drug constant fixes it.

E284 -- WHAT DOES CALIBRATION COST THE STATE AXIS?

Recompute P2 after per-arm median centring.

PREDICTION: **state tracking is essentially unchanged, retaining >= 95 %.** Centring is a per-arm constant
and P2 is a within-patient rank statistic, so it should be almost exactly invariant.
WRONG IF: it moves, which would mean the centring is doing something other than removing a constant --
and would be a warning that the arms differ within patient somehow.
**Registered as a near-tautology on purpose**: if it does NOT come back ~1.0, the pipeline is wrong, so
this doubles as a machinery check (rule 40's positive direction, rule 81).

E285 -- THE CHALLENGE A SCREEN, REDONE AFTER CALIBRATION

E279's screen returned only `emg_index`, the artefact channel. Rerun it on residual leakage.

PREDICTION: **at least one genuine EEG candidate survives.** If the leakage is largely a removable
constant, the post-calibration screen should not be empty.
WRONG IF: still empty or still only muscle, which would say the problem is not a calibration problem.

E286 -- CROSS-DRUG TRANSPORT OF A STATE THRESHOLD, WITH A PLACEBO THAT MATCHES THE DECISION (rule 94)

Fit a before/after decision threshold on one arm's PERI windows, apply it to another arm, and record the
accuracy drop. **The placebo is NOT a random threshold** -- rule 94 records that a random-parameter
placebo tests whether the parameter is special, not whether it transports, and cannot fire at a ceiling.
The placebo here is a threshold learned for a DIFFERENT candidate on the same source arm, which shares
the fitting procedure and the source cohort and differs only in carrying the wrong measure's information.

PREDICTION: **the top state trackers transport with < 0.10 accuracy loss and beat the wrong-measure
placebo.**
WRONG IF: transport loss is large, which would make the state axis itself agent-specific and would matter
more than any leakage number.

E287 -- DOES THE STATE AXIS ITSELF DEPEND ON DEPTH?

Stratify PERI cases by pre-landmark median BIS tercile and recompute P2.

PREDICTION: **state tracking is present in all three terciles**, |signed mean| >= 0.15 for the top
candidates in each.
WRONG IF: it is confined to one stratum, which would narrow every P2 claim to that depth range.

E288 -- DOES THE CTRL LEAKAGE ESTIMATE ITSELF REPLICATE?

Split the control cohort at random into halves and recompute leakage in each.

PREDICTION: **Spearman between half-estimates >= +0.6 across candidates**, and the top candidates agree
within 0.10 in absolute value.
WRONG IF: the halves disagree, in which case 740 cases is too few to rank candidates at maintenance and
every CTRL ranking in battery 3 is under-resolved.

E289 -- RULE 12 AT THE OTHER STATE: LEVEL VERSUS CHANGE, AT MAINTENANCE

E254 found leakage lives in the level peri-landmark. At maintenance there is no transition, so any
"change" across the control window is drift.

PREDICTION: **level dominates change even more decisively at CTRL than at PERI** -- level out-leaks change
in >= 16 of 19 candidates.
WRONG IF: change carries appreciable leakage at maintenance, which would mean agents differ in short-term
drift and would be a genuinely new observation.

    python -m bsde.experiments.e280_battery4
"""
from __future__ import annotations

import argparse, csv, glob, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
ARMS = ("sevo", "des", "ppf")
PAIRS = (("sevo", "des"), ("sevo", "ppf"), ("des", "ppf"))
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def midranks(vals):
    o = sorted(range(len(vals)), key=lambda i: vals[i]); r = [0.0] * len(vals); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and vals[o[j + 1]] == vals[o[i]]:
            j += 1
        av = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[o[k]] = av
        i = j + 1
    return r


def auc(p, n):
    p = [x for x in p if math.isfinite(x)]; n = [x for x in n if math.isfinite(x)]
    if not p or not n:
        return float("nan")
    r = midranks(p + n)
    return (sum(r[:len(p)]) - len(p) * (len(p) + 1) / 2.0) / (len(p) * len(n))


def lk(a_, b_):
    a_ = [x for x in a_ if math.isfinite(x)]; b_ = [x for x in b_ if math.isfinite(x)]
    if len(a_) < 8 or len(b_) < 8:
        return float("nan")
    return abs(auc(a_, b_) - 0.5)


def lk_p(a_, b_, rng, reps=1000):
    a_ = [x for x in a_ if math.isfinite(x)]; b_ = [x for x in b_ if math.isfinite(x)]
    if len(a_) < 8 or len(b_) < 8:
        return float("nan"), float("nan")
    obs = abs(auc(a_, b_) - 0.5)
    pool = a_ + b_; n1 = len(a_); null = []
    for _ in range(reps):
        rng.shuffle(pool)
        v = auc(pool[:n1], pool[n1:])
        if math.isfinite(v):
            null.append(abs(v - 0.5))
    null.sort()
    return obs, (null[int(0.95 * len(null))] if null else float("nan"))


def pau(vals, aft):
    k = [(v, a) for v, a in zip(vals, aft) if math.isfinite(v)]
    if len(k) < 4:
        return float("nan")
    v = [x[0] for x in k]; a = [x[1] for x in k]
    n1 = sum(1 for x in a if x); n2 = len(a) - n1
    if not n1 or not n2:
        return float("nan")
    r = midranks(v)
    return (sum(rr for rr, aa in zip(r, a) if aa) - n1 * (n1 + 1) / 2.0) / (n1 * n2)


def pear(x, y):
    p = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(p) < 3:
        return float("nan")
    n = len(p); mx = sum(q[0] for q in p) / n; my = sum(q[1] for q in p) / n
    sxy = sum((q[0] - mx) * (q[1] - my) for q in p)
    sxx = sum((q[0] - mx) ** 2 for q in p); syy = sum((q[1] - my) ** 2 for q in p)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spear(x, y):
    p = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(p) < 4:
        return float("nan")
    return pear(midranks([q[0] for q in p]), midranks([q[1] for q in p]))


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def pct(v, q):
    v = sorted(x for x in v if math.isfinite(x))
    return v[min(len(v) - 1, int(q * len(v)))] if v else float("nan")


def read(pattern, lm):
    rows, cols = [], None
    for p in sorted(glob.glob(pattern)):
        rd = csv.DictReader(open(p))
        if cols is None:
            cols = [c for c in (rd.fieldnames or []) if not c.startswith("meta_") and c not in SKIP]
        for r in rd:
            if r.get("status") == "ok" and r.get("meta_caseid") in lm:
                rows.append(r)
    by = {}
    for r in rows:
        by.setdefault(r["meta_caseid"], []).append(r)
    return {k: v for k, v in by.items() if len(v) >= 15}, cols, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=280)
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e280_battery4.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    R = {}

    lm = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "vitaldb_vent_landmarks.s?.csv"))):
        for r in csv.DictReader(open(p)):
            if not r.get("error") and r.get("arm") in ARMS:
                lm[r["caseid"]] = r
    peri, cols, prows = read(os.path.join(RESULTS, "vitaldb_ventwin.s?.csv"), lm)
    ctrl, _, _ = read(os.path.join(RESULTS, "vitaldb_ctrlwin.s?.csv"), lm)
    fin = {c: sum(1 for r in prows if math.isfinite(f(r.get(c)))) for c in cols}
    cols = [c for c in cols if fin[c] >= 0.20 * len(prows)]
    arm = {k: lm[k]["arm"] for k in set(peri) | set(ctrl)}
    if a.smoke:
        ks = sorted(arm); vs = [arm[k] for k in ks]; rng.shuffle(vs); arm = dict(zip(ks, vs))
        print("[SMOKE] arm labels permuted; all leakage recomputed under it")
    rec = [k for k in peri if lm[k].get("rec_ok") == "1"]
    t0 = {k: f(lm[k]["t_rec_s"]) for k in rec}
    print(f"[cohorts] PERI {len(peri)} / CTRL {len(ctrl)} / {len(cols)} candidates")

    cmed, cchg, pre, ST, pbis = {}, {}, {}, {}, {}
    for cid, rs in ctrl.items():
        ts = sorted(f(r.get("meta_t_s")) for r in rs)
        mid = ts[len(ts) // 2]
        for c in cols + ["meta_bis"]:
            cmed.setdefault(c, {})[cid] = med([f(r.get(c)) for r in rs])
            hi = med([f(r.get(c)) for r in rs if f(r.get("meta_t_s")) > mid])
            lo = med([f(r.get(c)) for r in rs if f(r.get("meta_t_s")) <= mid])
            cchg.setdefault(c, {})[cid] = hi - lo
    for cid in rec:
        rs = peri[cid]; offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
        aft = [o > 0 for o in offs]
        for c in cols:
            pre.setdefault(c, {})[cid] = med([f(r.get(c)) for r, o in zip(rs, offs) if o < 0])
            ST.setdefault(c, {})[cid] = pau([f(r.get(c)) for r in rs], aft)
        pbis[cid] = med([f(r.get("meta_bis")) for r, o in zip(rs, offs) if o < 0])

    CB = {i: cmed["meta_bis"][i] for i in ctrl if math.isfinite(cmed["meta_bis"][i])}
    CTRL_LK = {c: {f"{x}_vs_{y}": lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                                     [cmed[c][i] for i in ctrl if arm.get(i) == y])
                   for x, y in PAIRS} for c in cols}
    TOP = sorted(cols, key=lambda c: -max(v for v in CTRL_LK[c].values() if math.isfinite(v)))[:6]

    # ------------------------------------------------------------------ E280
    print("\n" + "=" * 92 + "\nE280 -- do the arms sit at different depths?")
    e280 = {}
    for x, y in PAIRS:
        va = [CB[i] for i in CB if arm.get(i) == x]; vb = [CB[i] for i in CB if arm.get(i) == y]
        v, p95 = lk_p(va, vb, rng, a.reps)
        e280[f"{x}_vs_{y}"] = {"leak": v, "null95": p95, "med_a": med(va), "med_b": med(vb),
                               "n": [len(va), len(vb)]}
        print(f"  {x}_vs_{y:5s} BIS medians {med(va):.1f} vs {med(vb):.1f}   "
              f"|AUC-0.5| = {v:.4f} (null95 {p95:.4f})")
    met = any(v["leak"] >= 0.10 for v in e280.values() if math.isfinite(v["leak"]))
    print(f"  PREDICTED >= 0.10 for at least one pair  ->  {'MET' if met else 'NOT MET'}")
    print("  NOTE (registered in advance): BIS is not equipotent across agents, so a BIS difference "
          "does NOT prove a true depth difference. E281 is the remedy that does not depend on it.")
    R["E280"] = {"detail": e280, "prediction_met": met}

    # ------------------------------------------------------------------ E281
    print("\n" + "=" * 92 + "\nE281 -- leakage after matching the arms on control-window BIS")
    e281, rets = {}, []
    for x, y in PAIRS:
        ax = [i for i in CB if arm.get(i) == x]; ay = [i for i in CB if arm.get(i) == y]
        lo = max(pct([CB[i] for i in ax], 0.10), pct([CB[i] for i in ay], 0.10))
        hi = min(pct([CB[i] for i in ax], 0.90), pct([CB[i] for i in ay], 0.90))
        ax2 = sorted([i for i in ax if lo <= CB[i] <= hi], key=lambda i: CB[i])
        ay2 = sorted([i for i in ay if lo <= CB[i] <= hi], key=lambda i: CB[i])
        pool = list(ay2); ma, mb = [], []
        for i in ax2:
            if not pool:
                break
            j = min(range(len(pool)), key=lambda k: abs(CB[pool[k]] - CB[i]))
            if abs(CB[pool[j]] - CB[i]) <= 3.0:
                ma.append(i); mb.append(pool.pop(j))
        d = {}
        for c in TOP:
            full = CTRL_LK[c][f"{x}_vs_{y}"]
            m = lk([cmed[c][i] for i in ma], [cmed[c][i] for i in mb])
            d[c] = {"full": full, "matched": m,
                    "retained": m / full if full and full > 0 else float("nan")}
            if math.isfinite(d[c]["retained"]):
                rets.append(d[c]["retained"])
        e281[f"{x}_vs_{y}"] = {"n_matched": len(ma), "null95_matched":
                               1.959964 * math.sqrt((2 * len(ma) + 1) / (12.0 * len(ma) ** 2))
                               if ma else float("nan"), "features": d}
        print(f"  {x}_vs_{y:5s} matched {len(ma)} pairs (floor rises to "
              f"{e281[f'{x}_vs_{y}']['null95_matched']:.4f}): "
              + ", ".join(f"{c[:16]} {d[c]['full']:.3f}->{d[c]['matched']:.3f}" for c in TOP[:3]))
    met = sum(1 for r in rets if r >= 0.60) / len(rets) > 0.5 if rets else False
    print(f"  PREDICTED most retain >= 60%  ->  {'MET' if met else 'NOT MET'}")
    R["E281"] = {"detail": e281, "median_retained": med(rets), "prediction_met": met}

    # ------------------------------------------------------------------ E282
    print("\n" + "=" * 92 + "\nE282 -- E271's monotone curve against a permutation null")

    def monotone_count(bmap):
        q1, q2 = pct(list(bmap.values()), 0.333), pct(list(bmap.values()), 0.667)
        terc = {"deep": [i for i in bmap if bmap[i] <= q1],
                "mid": [i for i in bmap if q1 < bmap[i] <= q2],
                "light": [i for i in bmap if bmap[i] > q2]}
        n = 0
        for c in TOP:
            vs = []
            for nm in ("deep", "mid", "light"):
                ids = terc[nm]
                vs.append(max(lk([cmed[c][i] for i in ids if arm.get(i) == x],
                                 [cmed[c][i] for i in ids if arm.get(i) == y])
                              for x, y in PAIRS))
            if all(math.isfinite(v) for v in vs) and vs[0] >= vs[1] >= vs[2]:
                n += 1
        return n
    obs_m = monotone_count(CB)
    null = []
    for _ in range(200):
        perm = {}
        for x in ARMS:
            ids = [i for i in CB if arm.get(i) == x]
            vals = [CB[i] for i in ids]
            rng.shuffle(vals)
            perm.update(dict(zip(ids, vals)))
        null.append(monotone_count(perm))
    null.sort()
    p95 = null[int(0.95 * len(null))]
    pv = sum(1 for v in null if v >= obs_m) / len(null)
    print(f"  observed monotone {obs_m} of {len(TOP)};  permuted null 95th = {p95}, "
          f"mean {sum(null)/len(null):.2f}, p = {pv:.4f}")
    met = p95 <= 2
    print(f"  PREDICTED permuted 95th <= 2  ->  {'MET' if met else 'NOT MET'}")
    R["E282"] = {"observed": obs_m, "null_p95": p95, "null_mean": sum(null) / len(null),
                 "p": pv, "prediction_met": met}

    # ------------------------------------------------------------------ E283
    print("\n" + "=" * 92 + "\nE283 -- residual leakage after per-drug median centring")
    e283, below = {}, 0
    for c in TOP:
        d = {}
        for x, y in PAIRS:
            va = [cmed[c][i] for i in ctrl if arm.get(i) == x]
            vb = [cmed[c][i] for i in ctrl if arm.get(i) == y]
            ma, mb = med(va), med(vb)
            res, p95 = lk_p([v - ma for v in va], [v - mb for v in vb], rng, a.reps)
            d[f"{x}_vs_{y}"] = {"raw": lk(va, vb), "residual": res, "null95": p95,
                                "at_null": res <= p95}
            if res <= p95:
                below += 1
        e283[c] = d
        print(f"  {c:26s} " + "  ".join(f"{k[:9]} {v['residual']:.3f}"
              f"{'<=null' if v['at_null'] else '>NULL'}" for k, v in d.items()))
    tot = sum(len(v) for v in e283.values())
    met = below / tot > 0.5
    print(f"  residual at or below null in {below} of {tot}  ->  "
          f"PREDICTION {'MET' if met else 'NOT MET'}")
    R["E283"] = {"detail": e283, "n_at_null": below, "n_total": tot, "prediction_met": met}

    # ------------------------------------------------------------------ E284
    print("\n" + "=" * 92 + "\nE284 -- what does calibration cost the state axis? (machinery check)")
    e284 = {}
    for c in TOP:
        raw = [ST[c][i] - 0.5 for i in rec if math.isfinite(ST[c][i])]
        r0 = sum(raw) / len(raw)
        adj = []
        for cid in rec:
            rs = peri[cid]; offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
            m = med([f(r.get(c)) for r in rs])
            v = pau([f(r.get(c)) - m for r in rs], [o > 0 for o in offs])
            if math.isfinite(v):
                adj.append(v - 0.5)
        r1 = sum(adj) / len(adj) if adj else float("nan")
        e284[c] = {"raw": r0, "centred": r1, "retained": r1 / r0 if r0 else float("nan")}
        print(f"  {c:26s} raw {r0:+.4f} -> per-case centred {r1:+.4f}  "
              f"retained {e284[c]['retained']:.3f}")
    rr = [v["retained"] for v in e284.values() if math.isfinite(v["retained"])]
    met = all(r >= 0.95 for r in rr) if rr else False
    print(f"  PREDICTED >= 0.95 (near-tautology; a miss means the pipeline is wrong)  ->  "
          f"{'MET' if met else 'NOT MET'}")
    R["E284"] = {"detail": e284, "prediction_met": met}

    # ------------------------------------------------------------------ E285
    print("\n" + "=" * 92 + "\nE285 -- the Challenge A screen after calibration")
    p2doc = json.load(open(os.path.join(RESULTS, "e249_gate_completion.json")))["p2"]
    p1doc = json.load(open(os.path.join(RESULTS, "e248_agent_leakage.json")))["pairs"]
    STATE = {c: abs(p2doc[c]["obs"]) for c in cols if c in p2doc}
    resid_ctrl, resid_peri = {}, {}
    for c in cols:
        rc, rp = [], []
        for x, y in PAIRS:
            va = [cmed[c][i] for i in ctrl if arm.get(i) == x]
            vb = [cmed[c][i] for i in ctrl if arm.get(i) == y]
            rc.append(lk([v - med(va) for v in va], [v - med(vb) for v in vb]))
            pa = [pre[c][i] for i in rec if arm.get(i) == x]
            pb = [pre[c][i] for i in rec if arm.get(i) == y]
            rp.append(lk([v - med(pa) for v in pa], [v - med(pb) for v in pb]))
        resid_ctrl[c] = max(v for v in rc if math.isfinite(v)) if any(map(math.isfinite, rc)) else float("nan")
        resid_peri[c] = max(v for v in rp if math.isfinite(v)) if any(map(math.isfinite, rp)) else float("nan")
    ms = med([STATE[c] for c in STATE])
    mc = med([resid_ctrl[c] for c in cols]); mp = med([resid_peri[c] for c in cols])
    surv = [c for c in cols if c in STATE and STATE[c] > ms
            and resid_peri[c] < mp and resid_ctrl[c] < mc]
    print(f"  medians: state {ms:.4f}, residual PERI {mp:.4f}, residual CTRL {mc:.4f}")
    for c in sorted(STATE, key=lambda k: -STATE[k])[:8]:
        fl = "  <== SURVIVES" if c in surv else ""
        print(f"  {c:28s} state {STATE[c]:.4f}  residPERI {resid_peri[c]:.4f}  "
              f"residCTRL {resid_ctrl[c]:.4f}{fl}")
    genuine = [c for c in surv if not c.startswith("emg")]
    print(f"  SURVIVORS: {surv if surv else 'NONE'}   (non-muscle: {genuine if genuine else 'NONE'})")
    met = len(genuine) >= 1
    print(f"  PREDICTED >= 1 genuine EEG candidate  ->  {'MET' if met else 'NOT MET'}")
    R["E285"] = {"survivors": surv, "genuine": genuine, "prediction_met": met}

    # ------------------------------------------------------------------ E286
    print("\n" + "=" * 92 + "\nE286 -- cross-drug transport of a state threshold (rule-94 placebo)")
    e286 = {}
    for c in TOP[:4]:
        d = {}
        for src, tgt in (("sevo", "ppf"), ("ppf", "sevo"), ("sevo", "des")):
            def acc(thr, ids, sign):
                ok = n = 0
                for cid in ids:
                    rs = peri[cid]; offs = [f(r.get("meta_t_s")) - t0[cid] for r in rs]
                    for r, o in zip(rs, offs):
                        v = f(r.get(c))
                        if not math.isfinite(v) or o == 0:
                            continue
                        n += 1
                        pred = (v > thr) if sign > 0 else (v < thr)
                        ok += 1 if pred == (o > 0) else 0
                return ok / n if n else float("nan")
            sids = [i for i in rec if arm.get(i) == src]
            tids = [i for i in rec if arm.get(i) == tgt]
            vals = [f(r.get(c)) for i in sids for r in peri[i]]
            cand = [pct(vals, q / 20.0) for q in range(3, 18)]
            sgn = 1 if sum(ST[c][i] - 0.5 for i in sids if math.isfinite(ST[c][i])) > 0 else -1
            best = max(cand, key=lambda t: acc(t, sids[:120], sgn))
            a_src = acc(best, sids[:120], sgn); a_tgt = acc(best, tids[:120], sgn)
            # rule-94 placebo: a threshold fitted for a DIFFERENT candidate on the SAME source arm
            other = [k for k in TOP if k != c][0]
            ovals = [f(r.get(other)) for i in sids for r in peri[i]]
            othr = pct(ovals, 0.5)
            a_plac = acc(othr, tids[:120], sgn)
            d[f"{src}->{tgt}"] = {"src_acc": a_src, "tgt_acc": a_tgt,
                                  "loss": a_src - a_tgt, "placebo_acc": a_plac}
        e286[c] = d
        print(f"  {c:26s} " + "  ".join(
            f"{k}: {v['src_acc']:.3f}->{v['tgt_acc']:.3f} (loss {v['loss']:+.3f}, "
            f"placebo {v['placebo_acc']:.3f})" for k, v in d.items()))
    losses = [v["loss"] for c in e286 for v in e286[c].values() if math.isfinite(v["loss"])]
    beats = [1 for c in e286 for v in e286[c].values()
             if math.isfinite(v["tgt_acc"]) and math.isfinite(v["placebo_acc"])
             and v["tgt_acc"] > v["placebo_acc"]]
    met = (med(losses) < 0.10) and (len(beats) > len(losses) / 2)
    print(f"  median transport loss {med(losses):+.4f}; beats placebo in {len(beats)} of "
          f"{len(losses)}  ->  PREDICTION {'MET' if met else 'NOT MET'}")
    R["E286"] = {"detail": e286, "median_loss": med(losses), "n_beat_placebo": len(beats),
                 "n_total": len(losses), "prediction_met": met}

    # ------------------------------------------------------------------ E287
    print("\n" + "=" * 92 + "\nE287 -- does the state axis itself depend on depth?")
    pb = {i: pbis[i] for i in rec if math.isfinite(pbis[i])}
    q1, q2 = pct(list(pb.values()), 0.333), pct(list(pb.values()), 0.667)
    terc = {"deep": [i for i in pb if pb[i] <= q1], "mid": [i for i in pb if q1 < pb[i] <= q2],
            "light": [i for i in pb if pb[i] > q2]}
    print(f"  pre-landmark BIS terciles <= {q1:.1f} / <= {q2:.1f}; "
          f"n = {({k: len(v) for k, v in terc.items()})}")
    e287, allpass = {}, 0
    for c in sorted(STATE, key=lambda k: -STATE[k])[:6]:
        d = {}
        for nm, ids in terc.items():
            vals = [ST[c][i] - 0.5 for i in ids if math.isfinite(ST[c][i])]
            d[nm] = sum(vals) / len(vals) if vals else float("nan")
        e287[c] = d
        if all(math.isfinite(v) and abs(v) >= 0.15 for v in d.values()):
            allpass += 1
        print(f"  {c:28s} deep {d['deep']:+.4f}  mid {d['mid']:+.4f}  light {d['light']:+.4f}")
    met = allpass >= 4
    print(f"  |signed mean| >= 0.15 in all three terciles for {allpass} of 6  ->  "
          f"{'MET' if met else 'NOT MET'}")
    R["E287"] = {"detail": e287, "n_all_terciles": allpass, "prediction_met": met}

    # ------------------------------------------------------------------ E288
    print("\n" + "=" * 92 + "\nE288 -- does the CTRL leakage estimate replicate?")
    ids = sorted(ctrl); rng.shuffle(ids)
    H = [set(ids[:len(ids) // 2]), set(ids[len(ids) // 2:])]
    hv = []
    for Hs in H:
        hv.append([max(lk([cmed[c][i] for i in Hs if arm.get(i) == x],
                          [cmed[c][i] for i in Hs if arm.get(i) == y]) for x, y in PAIRS)
                   for c in cols])
    r = spear(hv[0], hv[1])
    diffs = [abs(u - v) for u, v in zip(hv[0], hv[1]) if math.isfinite(u) and math.isfinite(v)]
    print(f"  Spearman between half-estimates = {r:+.4f} over {len(cols)} candidates; "
          f"median |difference| = {med(diffs):.4f}")
    met = math.isfinite(r) and r >= 0.60
    print(f"  PREDICTED >= +0.60  ->  {'MET' if met else 'NOT MET'}")
    R["E288"] = {"spearman": r, "median_abs_diff": med(diffs), "prediction_met": met}

    # ------------------------------------------------------------------ E289
    print("\n" + "=" * 92 + "\nE289 -- level versus change at maintenance (rule 12 at the other state)")
    wins = 0
    e289 = {}
    for c in cols:
        n = 0
        for x, y in PAIRS:
            l_ = lk([cmed[c][i] for i in ctrl if arm.get(i) == x],
                    [cmed[c][i] for i in ctrl if arm.get(i) == y])
            ch = lk([cchg[c][i] for i in ctrl if arm.get(i) == x],
                    [cchg[c][i] for i in ctrl if arm.get(i) == y])
            if math.isfinite(l_) and math.isfinite(ch) and l_ > ch:
                n += 1
        e289[c] = n
        if n >= 2:
            wins += 1
    print(f"  level out-leaks change in >= 2 of 3 pairs for {wins} of {len(cols)} candidates")
    met = wins >= 16
    print(f"  PREDICTED >= 16 of 19  ->  {'MET' if met else 'NOT MET'}")
    R["E289"] = {"level_wins": wins, "n": len(cols), "prediction_met": met}

    print("\n" + "=" * 92)
    for k in sorted(R):
        v = R[k].get("prediction_met")
        print(f"  {k}: prediction {'MET' if v else 'NOT MET' if v is False else 'descriptive'}")
    if not a.smoke:
        json.dump(R, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    else:
        print("\n[SMOKE] complete; nothing above is a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
