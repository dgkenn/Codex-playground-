#!/usr/bin/env python3
"""E157 -- does the MGH agent signature replicate where the two agents are actually separate?

REGISTERED 2026-08-01 BEFORE THE EXTRACTION FINISHED and before any candidate has been compared against
the agent label in VitalDB. The registration is in the ledger; this file implements it. What has been
looked at is the manifest of one completed shard and it is disclosed at the end.

=========================================================================================================
THE CLAIM UNDER TEST, AND WHY VITALDB IS A SHARPER TEST THAN THE COHORT THAT PRODUCED IT
=========================================================================================================
E156, on the MGH OR cohort, found two features separating the arms at matched unresponsiveness after
overlap weighting on case duration, against a cluster-level null over 39 cases:

    alpha_peak_hz   weighted |AUC-0.5| **0.4703**   signed AUC(mixed) **0.0886** -- markedly LOWER
    rel_theta       weighted |AUC-0.5| **0.4506**   signed AUC(mixed) **0.9457** -- markedly HIGHER

both at permutation p = 0.0000 and Holm p = 0.0000, with the named depth indices staying quiet
(`rel_alpha` 0.0732, `spectral_edge_95` 0.1499, both below the null). Those are the directions the
anaesthesia literature predicts for sevoflurane against propofol. **It was not claimed**, for two reasons
recorded in its ledger row: two gates failed on statistic-properties rather than on data, and rule 58
forbade a third gate revision.

**And the deeper problem was never the gates.** The MGH contrast is `pure_propofol` (27) against `mixed`
(16), because that deposit has exactly **one** sevoflurane-alone case. So E156 measured "did this case
also receive sevoflurane", inside a single centre, with **no age, sex, ASA or BMI recorded** — a
care-pathway variable with no covariates.

VitalDB fixes all of that:

    MGH OR                                  VitalDB
    propofol-only vs propofol+sevoflurane   **propofol alone vs sevoflurane alone**, both present
    39 cases                                ~236 cases across four shards
    no covariates at all                    meta_age, meta_sex, meta_asa, meta_bmi
    quality flag only                       BIS, SQI and suppression ratio ride along

=========================================================================================================
DESIGN
=========================================================================================================
    ARMS        `meta_agents_present` exactly `propofol` or exactly `sevoflurane`. Mixtures and
                desflurane cases are EXCLUDED, not folded, so the contrast is between two agents rather
                than between two care pathways.
    STATE       intra-operative maintenance windows only (after `meta_opstart_s`, before `meta_aneend_s`)
                -- every patient is unconscious there, which is the analogue of MGH's unconscious epochs.
                **BIS is NOT used to match state**: it is computed from the same EEG and conditioning on
                it would be circular (`DEPTH_TARGET_STRATEGY.md`).
    SUMMARY     the median of each candidate over the case's FIRST `N_WINDOWS` maintenance windows,
                identical for every case. E154 measured case duration identifying the agent at 0.3771 on
                MGH; a fixed-count summary means length cannot enter it at all.
    STATISTIC   |AUC - 0.5| for arm at CASE level, against a cluster-level permutation null (the cluster
                and the row coincide by construction), plus **the SIGNED AUC**, which is what carries the
                registered prediction.
    ADJUSTMENT  overlap weighting on the propensity of arm given age, sex, ASA and BMI -- covariates MGH
                does not record and which are the obvious confounders of agent choice.

=========================================================================================================
GATES
=========================================================================================================
G1  >= 40 cases per arm after the maintenance and window-count filters.
G2  **RULE 60 ESCAPE CHECK.** |rank correlation| of `alpha_peak_hz` with `relative_alpha_power` across
    cases must be below 0.9, or it is an amplitude measure wearing a frequency label and the frequency
    interpretation is withdrawn.
G3  **NUISANCE PLACEBOS.** Case duration, maintenance window count, age, sex, ASA and BMI are each pushed
    through the identical path. Any that exceeds the median candidate's raw legibility is named; the
    covariate ones are what the weighting exists to remove, and GATE Q below checks it did.
G4  **GATE Q, FRACTIONAL (E156's repaired form, and the reason it is fractional is in E155's row):** the
    adjusted legibility of each covariate must fall to <= 20 % of its raw value.
G5  **GATE P, TWO-SIDED:** a synthetic arm-driven probe orthogonal to the covariates must retain within
    [0.70, 1.50] after weighting. Retention above 1.50 is inflation, not preservation, and fails.

=========================================================================================================
PRIMARY -- DIRECTION FIRST, AND A REVERSED SIGN IS A REFUTATION (rule 37, fourth-occurrence lesson)
=========================================================================================================
    PREDICTED   `rel_theta` HIGHER under sevoflurane (signed AUC > 0.5)
                `alpha_peak_hz` LOWER under sevoflurane (signed AUC < 0.5)

**A magnitude that clears the null with the WRONG sign is a REFUTATION, not a partial confirmation.**
That is written before the run because E43's fourth-occurrence entry exists precisely for verdicts that
enumerate "includes the null" and "excludes the null" and forget "excludes it on the wrong side".

**IF BOTH REPLICATE with the predicted direction**, the MGH result stands as a real agent signature
measured twice, in two countries, on two monitors, with covariate adjustment in one of them. For
Challenge A that is **unfavourable news about the features**: a candidate that identifies the agent at
matched depth is carrying exactly the drug-identification information the brief penalises, and
`alpha_peak_hz` is also E153's only behavioural-threshold survivor -- a feature that does both is a good
state marker and a bad Challenge A candidate.

**IF NEITHER REPLICATES**, the MGH finding was a property of that cohort -- most plausibly the
care-pathway contrast, since `mixed` there is not an agent so much as a kind of operation -- and it is
withdrawn rather than qualified.

**IF THEY SPLIT**, the one that replicates is reported and the one that does not is withdrawn; no
composite claim is made from a half-replication.

**REGISTERED PREDICTION: both replicate with the predicted direction.** Made in the ledger before the
extraction finished and repeated here.

WHAT WAS ALREADY SEEN (rule 41). One completed shard's manifest: 1,527 rows over 59 cases, and the
`meta_agents_present` distribution (sevoflurane 469 rows, propofol|sevoflurane 401, desflurane|propofol
268, propofol 204, desflurane|propofol|sevoflurane 101) -- which is how the clean-arm filter was chosen
and how it was established that VitalDB has a real sevoflurane-alone arm where MGH has one case. No
candidate has been compared against the agent label.

    python bsde/src/bsde/experiments/e157_vitaldb_agent_replication.py
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import auc, auc_abs, spearman                         # noqa: E402

sys.path.insert(0, HERE)
from e141_family_split_quality_audit_v2 import _logit, ranks, wauc             # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e157_vitaldb_agent_replication.json")
SHARDS = os.path.join(RESULTS, "vitaldb_agentprobe.s*.csv")

PRIMARY = {"relative_theta_power": "higher", "alpha_peak_hz": "lower"}
CANDIDATES = ["relative_theta_power", "alpha_peak_hz", "relative_alpha_power", "relative_delta_power",
              "spectral_edge_95", "spectral_entropy", "whole_head_exponent", "exponent_low",
              "exponent_high", "lempel_ziv", "wpli_alpha"]
COVARS = ["meta_age", "meta_sex", "meta_asa", "meta_bmi"]
NUISANCE = ["duration_s", "n_windows"] + COVARS
N_WINDOWS = 8
MIN_PER_ARM = 40
PERMS = 20000
RETAIN_LO, RETAIN_HI = 0.70, 1.50
REMOVAL = 0.80


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load():
    rows = defaultdict(list)
    for p in sorted(glob.glob(SHARDS)):
        for r in csv.DictReader(open(p, newline="")):
            if r.get("status") != "ok":
                continue
            ag = (r.get("meta_agents_present") or "").strip()
            if ag not in ("propofol", "sevoflurane"):
                continue
            rows[r["meta_caseid"]].append(r)
    cases = {}
    for c, rs in rows.items():
        rs.sort(key=lambda r: _f(r["meta_t_s"]))
        keep = []
        for r in rs:
            t, o, a = _f(r["meta_t_s"]), _f(r["meta_opstart_s"]), _f(r["meta_aneend_s"])
            if math.isfinite(t) and math.isfinite(o) and math.isfinite(a) and o <= t <= a:
                keep.append(r)
        if len(keep) < N_WINDOWS:
            continue
        seg = keep[:N_WINDOWS]
        d = {"arm": 1 if rs[0]["meta_agents_present"] == "sevoflurane" else 0,
             "duration_s": _f(rs[-1]["meta_t_s"]) - _f(rs[0]["meta_t_s"]),
             "n_windows": float(len(keep))}
        for cv in COVARS:
            v = seg[0].get(cv, "")
            d[cv] = _f(v) if cv != "meta_sex" else (1.0 if str(v).upper().startswith("M") else 0.0)
        for f in CANDIDATES:
            vals = [_f(r.get(f, "")) for r in seg]
            vals = [v for v in vals if math.isfinite(v)]
            d[f] = float(np.median(vals)) if vals else float("nan")
        cases[c] = d
    return cases


def main(argv=None) -> int:
    rng = np.random.default_rng(157)
    cases = load()
    ids = sorted(cases)
    if not ids:
        print("ABSENT -- no clean-arm cases yet; the extraction is still running.")
        return 2
    arm = np.array([cases[c]["arm"] for c in ids])
    n_sevo, n_prop = int(arm.sum()), int((1 - arm).sum())
    out = {"experiment": "E157", "n_cases": len(ids), "n_sevoflurane": n_sevo,
           "n_propofol": n_prop, "n_windows": N_WINDOWS, "perms": PERMS}

    g1 = n_sevo >= MIN_PER_ARM and n_prop >= MIN_PER_ARM
    print(f"G1 MANIFEST  {len(ids)} clean-arm cases: {n_prop} propofol alone, {n_sevo} sevoflurane "
          f"alone (floor {MIN_PER_ARM} each) -> {'PASS' if g1 else 'FAIL'}")

    cols = {k: np.array([cases[c].get(k, float("nan")) for c in ids], float)
            for k in CANDIDATES + NUISANCE}
    for s in (0.5, 1.0, 2.0):
        cols[f"P:arm_sigma{s}"] = arm + s * rng.standard_normal(len(ids))

    # ---- G2 rule 60 escape check ----------------------------------------------------------------------
    m = np.isfinite(cols["alpha_peak_hz"]) & np.isfinite(cols["relative_alpha_power"])
    rho60 = spearman(list(cols["alpha_peak_hz"][m]), list(cols["relative_alpha_power"][m]))
    g2 = abs(rho60) < 0.9
    print(f"G2 RULE-60 ESCAPE  rho(alpha_peak_hz, relative_alpha_power) = {rho60:+.4f} "
          f"(bar |rho| < 0.9) -> {'PASS' if g2 else 'FAIL -- it is an amplitude measure renamed'}")

    # ---- overlap weighting on the covariates -----------------------------------------------------------
    C = np.column_stack([ranks(cols[c]) if np.isfinite(cols[c]).all() else
                         ranks(np.nan_to_num(cols[c], nan=np.nanmedian(cols[c]))) for c in COVARS])
    C = (C - C.mean(0)) / (C.std(0) + 1e-12)
    X = np.c_[np.ones(len(ids)), C]
    e = 1.0 / (1.0 + np.exp(-X @ _logit(X, arm.astype(float))))
    w = np.where(arm == 1, 1 - e, e)
    print(f"   propensity(arm | age, sex, ASA, BMI) range {e.min():.3f}-{e.max():.3f}")

    def raw(v, lab):
        k = np.isfinite(v)
        if len(set(lab[k].tolist())) < 2 or len(set(v[k].tolist())) < 2:
            return float("nan")
        return auc_abs(list(lab[k]), list(v[k])) - 0.5

    def wtd(v, lab, ww):
        k = np.isfinite(v)
        if len(set(lab[k].tolist())) < 2 or len(set(v[k].tolist())) < 2:
            return float("nan")
        a = wauc(list(lab[k]), list(v[k]), ww[k])
        return abs(a - 0.5) if math.isfinite(a) else float("nan")

    obs_r = {k: raw(v, arm) for k, v in cols.items()}
    obs_w = {k: wtd(v, arm, w) for k, v in cols.items()}
    null = {k: np.empty(PERMS) for k in cols}
    for i in range(PERMS):
        p = rng.permutation(arm)
        ep = 1.0 / (1.0 + np.exp(-X @ _logit(X, p.astype(float))))
        wp = np.where(p == 1, 1 - ep, ep)
        for k, v in cols.items():
            null[k][i] = wtd(v, p, wp)
    q95 = {k: float(np.nanquantile(null[k], 0.95)) for k in cols}
    pval = {k: float(np.nanmean(null[k] >= obs_w[k])) for k in cols}
    med_cand = float(np.nanmedian([obs_r[c] for c in CANDIDATES]))

    print(f"\nG3 NUISANCE PLACEBOS  median candidate raw legibility {med_cand:+.4f}")
    for k in NUISANCE:
        print(f"   {k:16s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  null p95 {q95[k]:.4f}  "
              f"p={pval[k]:.4f}  {'ABOVE the median candidate (raw)' if obs_r[k] >= med_cand else 'ok'}")
    print(f"G4 GATE Q  each covariate must lose >= {REMOVAL:.0%} of its raw legibility")
    g4 = True
    for k in COVARS:
        rem = 1.0 - (obs_w[k] / obs_r[k]) if obs_r[k] else float("nan")
        ok = math.isfinite(rem) and rem >= REMOVAL
        g4 &= ok
        print(f"   {k:16s} removed {rem:6.1%}  {'ok' if ok else 'FAIL'}")
    print(f"G5 GATE P  arm probes orthogonal to the covariates must retain within "
          f"[{RETAIN_LO:.0%}, {RETAIN_HI:.0%}]")
    g5 = True
    for k in [c for c in cols if c.startswith("P:")]:
        ret = obs_w[k] / obs_r[k] if obs_r[k] else float("nan")
        ok = math.isfinite(ret) and RETAIN_LO <= ret <= RETAIN_HI
        g5 &= ok
        print(f"   {k:16s} raw {obs_r[k]:+.4f} -> weighted {obs_w[k]:+.4f}  retains {ret:6.1%}  "
              f"{'ok' if ok else 'FAIL'}")
    out.update({"G1": bool(g1), "G2": {"pass": bool(g2), "rho": rho60},
                "G4": bool(g4), "G5": bool(g5),
                "nuisance": {k: {"raw": obs_r[k], "weighted": obs_w[k], "p": pval[k]} for k in NUISANCE}})

    gates = g1 and g2 and g4 and g5
    print(f"\nGATES {'ALL PASS' if gates else 'NOT ALL PASSED -- no verdict is issued'}\n")

    hp = holm([pval[c] for c in CANDIDATES], CANDIDATES)
    print(f"{'candidate':22s} {'raw':>8s} {'weighted':>9s} {'null p95':>9s} {'p':>8s} {'p_holm':>8s} "
          f"{'signed AUC(sevo)':>17s}")
    res = {}
    for c in sorted(CANDIDATES, key=lambda x: -obs_w[x]):
        k = np.isfinite(cols[c])
        sa = auc(list(arm[k]), list(cols[c][k])) if len(set(arm[k].tolist())) > 1 else float("nan")
        note = ""
        if c in PRIMARY:
            got = "higher" if sa > 0.5 else "lower"
            note = f"  predicted {PRIMARY[c]}, observed {got}"
        res[c] = {"raw": obs_r[c], "weighted": obs_w[c], "null_p95": q95[c], "p": pval[c],
                  "p_holm": hp[c], "signed_auc_sevo": sa,
                  "clears": bool(hp[c] < 0.05 and obs_w[c] > q95[c]),
                  "direction_ok": (None if c not in PRIMARY else
                                   bool((sa < 0.5) == (PRIMARY[c] == "lower")))}
        print(f"{c:22s} {obs_r[c]:8.4f} {obs_w[c]:9.4f} {q95[c]:9.4f} {pval[c]:8.4f} {hp[c]:8.4f} "
              f"{sa:17.4f}{note}")
    out["per_candidate"] = res

    rep = [c for c in PRIMARY if res[c]["clears"] and res[c]["direction_ok"]]
    wrong = [c for c in PRIMARY if res[c]["clears"] and not res[c]["direction_ok"]]
    if not gates:
        verdict = "NO VERDICT -- a gate failed"
    elif wrong:
        verdict = (f"REFUTED BY SIGN -- {', '.join(wrong)} clear the null with the WRONG direction "
                   f"(signed AUC(sevo) "
                   f"{ {c: round(res[c]['signed_auc_sevo'], 4) for c in wrong} }). Something separates "
                   f"these arms and it is not the pharmacology the MGH result was attributed to. Not a "
                   f"partial confirmation.")
    elif len(rep) == len(PRIMARY):
        verdict = (f"REPLICATED -- {', '.join(rep)} separate propofol from sevoflurane at matched "
                   f"intra-operative state, in the predicted directions, on {len(ids)} cases with age, "
                   f"sex, ASA and BMI weighted out. The MGH signature stands. For Challenge A this is "
                   f"UNFAVOURABLE news about the features: they carry exactly the drug-identification "
                   f"information the brief penalises, and alpha_peak_hz is also E153's only "
                   f"behavioural-threshold survivor.")
    elif rep:
        verdict = (f"HALF-REPLICATED -- {', '.join(rep)} replicates; "
                   f"{', '.join(c for c in PRIMARY if c not in rep)} does not and is withdrawn. No "
                   f"composite claim is made from a half-replication.")
    else:
        verdict = (f"NOT REPLICATED -- neither primary clears the cluster-level null on {len(ids)} cases "
                   f"with real separate agents and covariate adjustment. The MGH finding was a property "
                   f"of that cohort, most plausibly its care-pathway contrast, and is WITHDRAWN rather "
                   f"than qualified.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
