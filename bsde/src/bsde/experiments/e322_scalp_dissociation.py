#!/usr/bin/env python3
"""E322 -- does the REM/N3 dissociation hold on SCALP, at 8x the n, with a real muscle channel?

PRE-REGISTRATION. Committed before any statistic in it exists.

WHY. E321 found on 18 intracranial epilepsy-surgery patients that complexity measures place REM with
wake while every delta measure fails, and that drug-induced unresponsiveness sits with N3 on complexity
but near REM on delta. Three weaknesses ride with it: **intracranial electrodes in an epilepsy
population**, **depositor-computed features that cannot be independently re-implemented** (the deposit
ships no raw traces), and **no muscle channel at all**, so REM atonia could not be verified.

Sleep-EDFx answers all three for the REM half. **142 subjects, scalp, five stages each, features computed
by THIS project's own extractor**, and a genuine `EMG submental` channel.

**WHAT THIS CAN AND CANNOT REPLICATE, stated before the run.** Sleep-EDFx contains no anaesthetic, so
E321's discriminating comparison -- the drug check that exposed the delta measures -- **cannot be run
here at all**. This experiment tests only the REM-versus-N3 half. A pass does not revive delta as a
consciousness measure and does not transfer E321's drug result to scalp; it establishes that the
dissociation is not an artefact of intracranial recording or of epilepsy.

COHORT. `sleep_edfx_five_stage.csv`, 710 rows = 142 subjects x {W, N1, N2, N3, REM}, one error row.
**The identifier is structured (`SUBJECT@STAGE`) and is PARSED on the `@` rather than substring-matched**
-- catalogue rule 61 records that substring-matching a structured id silently mislabelled state in two
deposits at once.

STATISTIC, identical to E321. Each measure is standardised WITHIN SUBJECT across that subject's five
stages (median-centred, IQR-scaled). Paired sign-flip null over subjects, 5,000 draws.

    P1  AROUSAL SEPARATION   z(W) - z(N3)     -- must be non-zero for the measure to be usable
    P2  THE DISSOCIATION     z(REM) - z(N3)   -- arousal-like -> ~0; processing-like -> large, sign of P1

PREDICTIONS, carried from E321's directions and not re-tuned:
  * `lempel_ziv`, `spectral_entropy`, `multiscale_entropy_slope` -- complexity analogues of Krause's
    `NmlzCmplx`/`EffDim` -- have P2 excluding zero with the same sign as P1.
  * `relative_delta_power` has P2 excluding zero too, and that is EXPECTED and UNINFORMATIVE: REM is
    low-delta. It is a positive control that the index responds to sleep-stage physiology, not evidence
    about consciousness (rule 21). **Delta cannot be exonerated here because the drug arm is absent.**
  * `uce_v1`, the project's frozen flagship, is computable on this deposit and is reported. No direction
    is predicted for it; it is included because it has never been placed on a dissociation contrast.

GATES.
  G1  >= 100 subjects contribute per measure, else NOT INTERPRETABLE for that measure.
  G2  ALIVENESS: the majority of measures pass P1 (rule 53).
  G3  THE MUSCLE INSTRUMENT IS VALID AND SHOWS ATONIA. Using the real `EMG submental` channel, REM must
      have LOWER muscle tone than N3 (atonia). If it does not, either the staging or the channel is
      wrong and every muscle argument below is void. **This is a gate, not a covariate.**
      **Muscle is deliberately NOT residualised out.** Atonia is part of what REM IS, so concurrent EMG
      is a post-exposure mediator and conditioning on it is catalogue rule 13 -- the error E253 made in
      this same session. The argument is directional instead: if a measure's REM value were driven by
      muscle it would be LOW in REM, so a HIGH value cannot be manufactured by muscle.
  G4  SMOKE BITES: under `--smoke` the stage labels are permuted within subject and the count of
      measures passing P2 is printed; it must fall.

SCOPE. Sleep-EDFx is healthy and mildly sleep-disordered adults, two EEG derivations (Fpz-Cz, Pz-Oz), and
one 30 s-staged night per subject here. **REM is again a proxy for conscious experience without a
report** -- no dream recall was collected, so "REM = conscious" is an inference from the literature and
not a measurement in this cohort (rule 42).

    python -m bsde.experiments.e322_scalp_dissociation
"""
from __future__ import annotations

import argparse, csv, json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(ROOT, "results")
SKIP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
STAGES = ("W", "N1", "N2", "N3", "REM")
WAKE, REM, DEEP = "W", "REM", "N3"
MIN_SUBJ = 100


def f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def med(v):
    v = sorted(x for x in v if math.isfinite(x))
    return v[len(v) // 2] if v else float("nan")


def iqr(v):
    v = sorted(x for x in v if math.isfinite(x))
    if len(v) < 4:
        return float("nan")
    return v[int(0.75 * len(v))] - v[int(0.25 * len(v))]


def signflip(diffs, rng, reps):
    d = [x for x in diffs if math.isfinite(x)]
    if len(d) < 10:
        return float("nan"), float("nan"), 0
    obs = med(d)
    null = [med([x if rng.random() < 0.5 else -x for x in d]) for _ in range(reps)]
    return obs, sum(1 for v in null if abs(v) >= abs(obs)) / len(null), len(d)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=os.path.join(RESULTS, "sleep_edfx_five_stage.csv"))
    ap.add_argument("--emg", default=os.path.join(RESULTS, "sleep_edfx_emg.csv"))
    ap.add_argument("--reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=322)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e322_scalp_dissociation.json"))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    rows = [r for r in csv.DictReader(open(a.features)) if r.get("status") == "ok"]
    cols = [c for c in rows[0] if c not in SKIP]
    val = {}
    for r in rows:
        rid = r["recording_id"]
        if "@" not in rid:            # rule 61: PARSE the entity, never substring-match
            continue
        subj, stage = rid.rsplit("@", 1)
        if stage not in STAGES:
            continue
        val[(subj, stage)] = {c: f(r.get(c)) for c in cols}
    subs = sorted({s for s, _ in val})
    full = [s for s in subs if all((s, st) in val for st in STAGES)]
    print(f"[cohort] {len(subs)} subjects parsed, {len(full)} with all five stages")

    # ---- G3 muscle instrument: does REM show atonia?
    emg = {}
    for r in csv.DictReader(open(a.emg)):
        if r.get("label") in STAGES:
            emg[(r["subject"], r["label"])] = f(r.get("emg_median"))
    d_emg = [emg[(s, REM)] - emg[(s, DEEP)] for s in full
             if (s, REM) in emg and (s, DEEP) in emg
             and math.isfinite(emg[(s, REM)]) and math.isfinite(emg[(s, DEEP)])]
    o_e, p_e, n_e = signflip(d_emg, rng, a.reps)
    G3 = math.isfinite(o_e) and o_e < 0 and math.isfinite(p_e) and p_e < 0.05
    print(f"[G3] real submental EMG, REM - N3 = {o_e:+.4f} (p = {p_e:.4f}, n = {n_e}) "
          f"-> atonia {'CONFIRMED' if G3 else 'NOT CONFIRMED'}")

    # ---- z within subject
    Z = {}
    for s in full:
        for c in cols:
            pool = [val[(s, st)][c] for st in STAGES]
            m0, s0 = med(pool), iqr(pool)
            if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                continue
            zz = {st: (val[(s, st)][c] - m0) / s0 for st in STAGES}
            if a.smoke:
                ks = list(STAGES); vs = [zz[k] for k in ks]; rng.shuffle(vs)
                zz = dict(zip(ks, vs))
            Z[(s, c)] = zz

    print("\n" + "=" * 92)
    print(f"{'measure':28s} {'P1 W-N3':>10s} {'P2 REM-N3':>11s} {'p2':>8s} {'n':>5s}  note")
    res, npass = {}, 0
    for c in cols:
        d1 = [Z[(s, c)][WAKE] - Z[(s, c)][DEEP] for s in full if (s, c) in Z]
        d2 = [Z[(s, c)][REM] - Z[(s, c)][DEEP] for s in full if (s, c) in Z]
        o1, p1, n1 = signflip(d1, rng, a.reps)
        o2, p2, n2 = signflip(d2, rng, a.reps)
        if n2 < MIN_SUBJ:
            res[c] = {"status": "NOT INTERPRETABLE (G1)", "n": n2}
            print(f"{c:28s} {'NOT INTERPRETABLE (G1)':>36s}  n={n2}")
            continue
        same = math.isfinite(o1) and math.isfinite(o2) and o1 * o2 > 0
        ok = math.isfinite(p2) and p2 < 0.05 and same
        if ok:
            npass += 1
        note = "dissociates (same sign as arousal)" if ok else (
            "REM separates but OPPOSITE sign to arousal" if (math.isfinite(p2) and p2 < 0.05)
            else "REM ~ N3")
        res[c] = {"P1": o1, "p1": p1, "P2": o2, "p2": p2, "n": n2, "passes": ok, "note": note}
        print(f"{c:28s} {o1:+10.4f} {o2:+11.4f} {p2:8.4f} {n2:5d}  {note}")

    alive = [c for c in res if math.isfinite(res[c].get("p1", float("nan")))
             and res[c]["p1"] < 0.05]
    testable = [c for c in res if "status" not in res[c]]
    G2 = len(alive) >= len(testable) / 2
    print(f"\n[G2] {len(alive)} of {len(testable)} measures pass P1 -> {'PASS' if G2 else 'FAIL'}")
    print(f"[G4] measures passing P2 {'under PERMUTED stages' if a.smoke else ''}: {npass}")

    COMPLEX = [c for c in ("lempel_ziv", "spectral_entropy", "multiscale_entropy_slope") if c in res]
    hits = [c for c in COMPLEX if res[c].get("passes")]
    verdict = ("NOT INTERPRETABLE" if not (G2 and G3) else
               f"REPLICATES ON SCALP: {', '.join(hits)}" if hits else
               "DOES NOT REPLICATE ON SCALP -- the complexity analogues do not place REM toward wake")
    print(f"\nVERDICT: {verdict}")
    if "uce_v1" in res and "status" not in res["uce_v1"]:
        print(f"  flagship `uce_v1`: P2 = {res['uce_v1']['P2']:+.4f} (p = {res['uce_v1']['p2']:.4f})")
    print("\nSCOPE: no anaesthetic in this deposit, so E321's DRUG CHECK -- the comparison that exposed the "
          "delta measures -- cannot be run here. This replicates the REM half only, and does not "
          "exonerate delta. REM is again a proxy for conscious experience without a report.")

    rep = {"verdict": verdict, "n_subjects": len(full), "results": res,
           "gates": {"G2": G2, "G3_atonia": G3, "emg_rem_minus_n3": o_e, "emg_p": p_e},
           "complexity_hits": hits, "n_pass_P2": npass}
    if not a.smoke:
        json.dump(rep, open(a.out, "w"), indent=1, default=float)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
