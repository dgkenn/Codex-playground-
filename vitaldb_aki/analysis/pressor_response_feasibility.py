"""pressor_response_feasibility.py -- the MAKE-OR-BREAK gate for the A-line
responder-prediction tool (user pivot #1).

The question
------------
Can we identify, in VitalDB, enough *discrete treatment-change events* with a
CLEAN, measurable short-term MAP/CO response to TRAIN a model that predicts how
responsive a hypotensive patient is to a pressor (and, if possible, to fluid)?
A deep-learning responder-predictor is only worth building if the *labels* exist:
many events, each with a measurable Delta-MAP / Delta-CO after the intervention.

What the track index already tells us (cache/trks.csv, NO download)
-------------------------------------------------------------------
PRESSOR pumps are continuous infusions with titration steps recorded as
``Orchestra/<DRUG>_RATE`` time-series:
    PHEN (phenylephrine) ~127 cases, NEPI (norepi) ~88, DOPA ~33, EPI/DOBU/VASO few.
Each case's pump is titrated up/down many times -> many *change events* per case.
Short-term MAP response is read from ``Solar8000/ART_MBP`` (invasive, ~2 s) and CO
from ``EV1000/CO`` / ``Vigileo/CO`` where present. These are all SMALL numeric
tracks (no 50 MB SNUADC waveform) -> the gate is fast and disk-light.

FLUID boluses, by contrast, have NO scalable time-series: the only fluid-rate
track is ``FMS/FLOW_RATE`` (~15 cases). Crystalloid/colloid otherwise exist only
as end-of-case totals (no timing) -> fluid-bolus events cannot be labelled at
scale from VitalDB. This module quantifies both arms honestly.

What this module does
---------------------
1. Build the event cohort from cache/trks.csv (pressor-pump cases that also have
   ART_MBP; flag the CO-monitor subset). Report N for each arm + the fluid arm.
2. Download a SAMPLE of cases' pump RATE + ART_MBP (+ CO) -- numeric only -- and
   detect UP-titration change events. For each event measure:
     baseline MAP  = mean ART_MBP over [t-120s, t-15s]
     response MAP  = mean ART_MBP over [t+45s, t+165s]   (pressor onset ~30-60 s)
     dMAP = response - baseline ; responsiveness = dMAP / dose_step
     dCO likewise where a CO track is present.
   A *clean* event needs enough pre/post samples, a physiologic baseline MAP, an
   isolated step (no second pump moving in the window), and a real dose step.
3. Aggregate the gate metrics: clean events total, events/case, fraction with a
   measurable response, BETWEEN-patient spread in responsiveness (the quantity a
   model would predict), and the extrapolated yield over the full cohort.
4. Write a GO / NO-GO verdict per arm + docs/PRESSOR_RESPONSE_FEASIBILITY.md.

stdlib only at import; numpy lazy. Incrementally writes per-event rows to
cache/pressor_response_events.csv so a container reap never loses extracted work
(already-processed caseids are skipped on restart).

Run: python3 -m vitaldb_aki.analysis.pressor_response_feasibility [--limit N]
"""
from __future__ import annotations
import csv as _csv
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CACHE = os.path.join(_ROOT, "vitaldb_aki", "cache")
_DOCS = os.path.join(_ROOT, "vitaldb_aki", "docs")
SEED = 20260628

# Pressor pumps (vasoconstrictors/inotropes that RAISE MAP) -> their RATE tracks.
PRESSOR_DRUGS = ("PHEN", "NEPI", "DOPA", "EPI", "DOBU", "VASO")
PRESSOR_RATE = tuple(f"Orchestra/{d}_RATE" for d in PRESSOR_DRUGS)
MAP_TRACK = "Solar8000/ART_MBP"
CO_TRACKS = ("EV1000/CO", "Vigileo/CO")
FLUID_RATE = "FMS/FLOW_RATE"   # the ONLY scalable fluid-rate time-series

# response windows (seconds) relative to the titration step
BASE_LO, BASE_HI = -120.0, -15.0     # pre-step baseline
RESP_LO, RESP_HI = 45.0, 165.0       # post-step response (pressor onset ~30-60s)
MIN_SAMPLES = 6                      # min ART_MBP samples in each window
MAP_MIN, MAP_MAX = 20.0, 200.0       # physiologic ART_MBP gate
MEASURABLE_DMAP = 3.0                # |dMAP| (mmHg) counted as a measurable response
EVENTS_CSV = os.path.join(_CACHE, "pressor_response_events.csv")
_FIELDS = ["caseid", "drug", "t_event", "dose_from", "dose_to", "dose_step",
           "base_map", "resp_map", "dmap", "responsiveness", "n_base", "n_resp",
           "isolated", "base_co", "resp_co", "dco", "co_source"]


def _cohort_from_trks(trks_path):
    """Return (pressor_cases:set, by_drug:dict, co_cases:set, fluid_cases:set,
    map_cases:set) from the track index -- NO download."""
    pressor_by_drug = {d: set() for d in PRESSOR_DRUGS}
    co_cases, fluid_cases, map_cases = set(), set(), set()
    with open(trks_path, "r", newline="", encoding="utf-8") as fh:
        r = _csv.DictReader(fh)
        for row in r:
            cid, tn = row["caseid"], row["tname"]
            if tn == MAP_TRACK:
                map_cases.add(cid)
            elif tn in CO_TRACKS:
                co_cases.add(cid)
            elif tn == FLUID_RATE:
                fluid_cases.add(cid)
            elif tn.startswith("Orchestra/") and tn.endswith("_RATE"):
                drug = tn[len("Orchestra/"):-len("_RATE")]
                if drug in pressor_by_drug:
                    pressor_by_drug[drug].add(cid)
    pressor_cases = set().union(*pressor_by_drug.values()) if pressor_by_drug else set()
    return pressor_cases, pressor_by_drug, co_cases, fluid_cases, map_cases


def _win_mean(series, lo, hi, vmin=None, vmax=None):
    """Mean of values with lo <= t < hi (and optional range gate). Returns (mean, n)."""
    import numpy as np
    vals = [v for (t, v) in series if lo <= t < hi and
            (vmin is None or (vmin <= v <= vmax))]
    if not vals:
        return None, 0
    return float(np.mean(vals)), len(vals)


def _detect_steps(rate_series, min_step=0.01):
    """Detect UP-titration steps in a pump RATE series. Returns list of
    (t, dose_from, dose_to). A step = the rate increases vs the running value."""
    steps = []
    prev = None
    for t, v in rate_series:
        if v < 0:
            continue
        if prev is None:
            prev = v
            continue
        if v - prev > min_step and v > 0:
            steps.append((t, prev, v))
        prev = v
    return steps


def _other_pump_moves(cfg, cid, drug, t, all_drugs_present):
    """True if a *different* pressor pump also changed within the response window
    (confounds the attribution). Cheap: re-scan the cached series."""
    from vitaldb_aki.data.tracks import download_track
    for d in all_drugs_present:
        if d == drug:
            continue
        s = download_track(cfg, cid, f"Orchestra/{d}_RATE")
        for (tt, _v), (_pt, _pv) in zip(s[1:], s[:-1]):
            if t + BASE_LO <= tt <= t + RESP_HI and abs(_v - _pv) > 0.01:
                return False  # not isolated
    return True


def _process_case(cfg, cid, drugs_present):
    """Extract clean pressor-change events for one case. Returns list of event dicts.
    Downloads only small numeric tracks; purges them after."""
    from vitaldb_aki.data.tracks import download_track, purge_track
    map_s = download_track(cfg, cid, MAP_TRACK)
    if len(map_s) < 2 * MIN_SAMPLES:
        purge_track(cfg, cid, MAP_TRACK)
        return []
    # CO (optional)
    co_s, co_src = [], ""
    for ct in CO_TRACKS:
        s = download_track(cfg, cid, ct)
        if len(s) >= 4:
            co_s, co_src = s, ct
            break
    events = []
    for drug in drugs_present:
        rate_s = download_track(cfg, cid, f"Orchestra/{drug}_RATE")
        for (t, dfrom, dto) in _detect_steps(rate_s):
            bmap, nb = _win_mean(map_s, t + BASE_LO, t + BASE_HI, MAP_MIN, MAP_MAX)
            rmap, nr = _win_mean(map_s, t + RESP_LO, t + RESP_HI, MAP_MIN, MAP_MAX)
            if bmap is None or rmap is None or nb < MIN_SAMPLES or nr < MIN_SAMPLES:
                continue
            iso = _other_pump_moves(cfg, cid, drug, t, drugs_present) if len(drugs_present) > 1 else True
            step = dto - dfrom
            bco, rco, dco = None, None, None
            if co_s:
                bco, _ = _win_mean(co_s, t + BASE_LO, t + BASE_HI, 0.5, 15.0)
                rco, _ = _win_mean(co_s, t + RESP_LO, t + RESP_HI, 0.5, 15.0)
                if bco is not None and rco is not None:
                    dco = round(rco - bco, 3)
            events.append({
                "caseid": cid, "drug": drug, "t_event": round(t, 1),
                "dose_from": round(dfrom, 4), "dose_to": round(dto, 4),
                "dose_step": round(step, 4), "base_map": round(bmap, 2),
                "resp_map": round(rmap, 2), "dmap": round(rmap - bmap, 2),
                "responsiveness": round((rmap - bmap) / step, 3) if step > 0 else None,
                "n_base": nb, "n_resp": nr, "isolated": int(iso),
                "base_co": round(bco, 3) if bco is not None else None,
                "resp_co": round(rco, 3) if rco is not None else None,
                "dco": dco, "co_source": co_src})
        purge_track(cfg, cid, f"Orchestra/{drug}_RATE")
    purge_track(cfg, cid, MAP_TRACK)
    if co_src:
        purge_track(cfg, cid, co_src)
    return events


def _load_done():
    done = set()
    if os.path.exists(EVENTS_CSV):
        with open(EVENTS_CSV, newline="") as fh:
            for row in _csv.DictReader(fh):
                done.add(row["caseid"])
    return done


def _append_events(rows):
    new = not os.path.exists(EVENTS_CSV)
    with open(EVENTS_CSV, "a", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=_FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def extract(limit):
    from common.config import load_yaml
    cfg = load_yaml(os.path.join(_ROOT, "vitaldb_aki", "config.yaml"))
    trks = os.path.join(_CACHE, "trks.csv")
    pressor_cases, by_drug, co_cases, fluid_cases, map_cases = _cohort_from_trks(trks)
    drug_of_case = {}
    for d, cs in by_drug.items():
        for c in cs:
            drug_of_case.setdefault(c, []).append(d)
    # the trainable cohort: pressor pump AND invasive MAP
    cohort = sorted(pressor_cases & map_cases, key=lambda c: (c not in co_cases, int(c)))
    done = _load_done()
    todo = [c for c in cohort if c not in done]
    if limit:
        todo = todo[:limit]
    print(f"[prf] cohort: {len(cohort)} pressor+ART_MBP cases "
          f"({len(pressor_cases & map_cases & co_cases)} also have CO); "
          f"{len(done)} done, processing {len(todo)} now", flush=True)
    for i, cid in enumerate(todo, 1):
        try:
            ev = _process_case(cfg, cid, drug_of_case.get(cid, []))
            _append_events(ev)
            print(f"[prf]  [{i}/{len(todo)}] case {cid}: {len(ev)} clean events "
                  f"(drugs={drug_of_case.get(cid)})", flush=True)
        except Exception as exc:  # bounded: one bad case never kills the run
            print(f"[prf]  [{i}/{len(todo)}] case {cid} FAILED: {exc}", flush=True)
    return {"cohort_pressor_map": len(cohort),
            "cohort_pressor_map_co": len(pressor_cases & map_cases & co_cases),
            "cohort_fluid_fms": len(fluid_cases),
            "by_drug": {d: len(cs) for d, cs in by_drug.items()}}


def summarize(cohort_info):
    import numpy as np
    if not os.path.exists(EVENTS_CSV):
        return {"available": False}
    rows = list(_csv.DictReader(open(EVENTS_CSV, newline="")))
    def col(name, cast=float):
        out = []
        for r in rows:
            v = r.get(name, "")
            if v not in ("", "None", None):
                try:
                    out.append(cast(v))
                except ValueError:
                    pass
        return out
    n_cases = len({r["caseid"] for r in rows})
    n_events = len(rows)
    iso = [r for r in rows if r.get("isolated") == "1"]
    dmap = np.array([float(r["dmap"]) for r in iso if r.get("dmap") not in ("", "None")])
    resp = np.array([float(r["responsiveness"]) for r in iso
                     if r.get("responsiveness") not in ("", "None")])
    measurable = int(np.sum(np.abs(dmap) >= MEASURABLE_DMAP)) if dmap.size else 0
    n_co = len([r for r in iso if r.get("dco") not in ("", "None")])
    # between-patient spread in responsiveness (median per case, then IQR across cases)
    per_case = {}
    for r in iso:
        v = r.get("responsiveness")
        if v not in ("", "None"):
            per_case.setdefault(r["caseid"], []).append(float(v))
    case_med = np.array([np.median(v) for v in per_case.values() if v])
    full_cohort = cohort_info.get("cohort_pressor_map", 0)
    yield_per_case = n_events / n_cases if n_cases else 0
    s = {
        "available": True,
        "cases_processed": n_cases,
        "events_total": n_events,
        "events_isolated_clean": len(iso),
        "events_per_case": round(yield_per_case, 2),
        "extrapolated_clean_events_full_cohort": int(round(yield_per_case * full_cohort)),
        "dmap_median": round(float(np.median(dmap)), 2) if dmap.size else None,
        "dmap_iqr": [round(float(np.percentile(dmap, 25)), 2),
                     round(float(np.percentile(dmap, 75)), 2)] if dmap.size else None,
        "frac_measurable_response": round(measurable / dmap.size, 3) if dmap.size else None,
        "responsiveness_median_mmHg_per_unit": round(float(np.median(resp)), 3) if resp.size else None,
        "responsiveness_between_patient_iqr": [round(float(np.percentile(case_med, 25)), 3),
                                               round(float(np.percentile(case_med, 75)), 3)]
        if case_med.size > 3 else None,
        "events_with_CO_response": n_co,
    }
    return s


# GO thresholds for the gate (pre-declared)
GATE = {"min_clean_events": 300, "min_events_per_case": 2.0,
        "min_frac_measurable": 0.5, "min_co_events": 30}


def _verdict(s, cohort_info):
    if not s.get("available"):
        return "NO DATA -- run extraction first."
    go_pressor = (s["events_isolated_clean"] >= GATE["min_clean_events"] and
                  s["events_per_case"] >= GATE["min_events_per_case"] and
                  (s["frac_measurable_response"] or 0) >= GATE["min_frac_measurable"])
    co_go = s["events_with_CO_response"] >= GATE["min_co_events"]
    fluid_go = cohort_info.get("cohort_fluid_fms", 0) >= 100
    v = []
    v.append(("PRESSOR-RESPONSE arm (MAP): **GO**" if go_pressor else
              "PRESSOR-RESPONSE arm (MAP): borderline/NO-GO") +
             f" -- {s['events_isolated_clean']} clean isolated events over "
             f"{s['cases_processed']} sampled cases ({s['events_per_case']}/case), "
             f"{int((s['frac_measurable_response'] or 0)*100)}% with a measurable "
             f">={MEASURABLE_DMAP} mmHg response; extrapolates to "
             f"~{s['extrapolated_clean_events_full_cohort']} clean events over the full "
             f"{cohort_info.get('cohort_pressor_map')}-case pressor+ART_MBP cohort.")
    v.append(("CO-RESPONSE sub-arm: **GO**" if co_go else "CO-RESPONSE sub-arm: thin") +
             f" -- {s['events_with_CO_response']} events also carry an EV1000/Vigileo CO "
             f"response ({cohort_info.get('cohort_pressor_map_co')} cohort cases have CO).")
    v.append(("FLUID-BOLUS arm: **NO-GO at scale**") +
             f" -- the only fluid-rate time-series is FMS/FLOW_RATE ({cohort_info.get('cohort_fluid_fms')} "
             "cases); crystalloid/colloid are end-of-case totals (no timing), so fluid boluses "
             "cannot be event-labelled across the DB. A fluid-responder arm needs the FMS-15 "
             "cases (too few) or an external waveform+fluid dataset.")
    return "\n\n".join(v)


def _doc(s, cohort_info, verdict):
    L = ["# A-line pressor-response feasibility gate (user pivot #1)\n",
         "Make-or-break check: are there enough *discrete treatment-change events* with a "
         "clean, measurable short-term MAP/CO response to TRAIN a responder-prediction model? "
         "Built from the VitalDB track index (cache/trks.csv) + a sampled extraction of small "
         "numeric tracks (pump RATE, ART_MBP, CO) -- no 50 MB waveform download.\n",
         "## Cohort (from the track index, no download)",
         f"- Pressor pump (PHEN/NEPI/DOPA/EPI/DOBU/VASO) **and** invasive ART_MBP: "
         f"**{cohort_info.get('cohort_pressor_map')} cases**.",
         f"- ...of which also have a CO monitor (EV1000/Vigileo): "
         f"**{cohort_info.get('cohort_pressor_map_co')} cases**.",
         f"- Per-drug pump availability: {cohort_info.get('by_drug')}.",
         f"- Fluid-rate time-series (FMS/FLOW_RATE): **{cohort_info.get('cohort_fluid_fms')} cases** "
         "(crystalloid/colloid otherwise = end-of-case totals, no timing).\n",
         "## Sampled event extraction"]
    if s.get("available"):
        L += [f"- Cases processed: **{s['cases_processed']}**; clean isolated up-titration events: "
              f"**{s['events_isolated_clean']}** (total detected {s['events_total']}; "
              f"{s['events_per_case']}/case).",
              f"- Short-term MAP response: median dMAP **{s['dmap_median']} mmHg** "
              f"(IQR {s['dmap_iqr']}); **{int((s['frac_measurable_response'] or 0)*100)}%** of events "
              f"had a measurable |dMAP| >= {MEASURABLE_DMAP} mmHg.",
              f"- Pressor responsiveness (dMAP per unit dose step): median "
              f"**{s['responsiveness_median_mmHg_per_unit']}**; between-patient IQR of per-case "
              f"median responsiveness = **{s['responsiveness_between_patient_iqr']}** "
              "(this between-patient spread is exactly what a responder model would predict).",
              f"- Events also carrying a CO response: **{s['events_with_CO_response']}**.",
              f"- Extrapolated clean events over the full cohort: "
              f"**~{s['extrapolated_clean_events_full_cohort']}**.\n"]
    else:
        L.append("- _no events extracted yet._\n")
    L += ["## Verdict", verdict, "",
          "## What a GO unlocks (the high-impact build)",
          "- **A-line -> pressor-responsiveness predictor.** From the pre-titration arterial "
          "waveform/morphology, predict the patient's dMAP-per-unit-norepi (responsiveness). "
          "High responsiveness -> small dose suffices; blunted responsiveness -> vasoplegia, "
          "escalate/seek a cause. This is the responder half of the fluid-vs-pressor idea, and "
          "it is directly trainable here (labels = the measured dMAP at each titration step).",
          "- It also **feeds Pivot 2**: pressor responsiveness is the dynamic, "
          "intervention-anchored validation of the static 'vascular tone' waveform signal -- a "
          "blunted dMAP response is vasoplegia observed through treatment, not just morphology.",
          "- The fluid arm is NOT abandoned but RE-SCOPED: it requires an external arterial-"
          "waveform + fluid-bolus-timing dataset (or the FMS-instrumented subset), stated as "
          "future work, not blocked on here.",
          "",
          "## Honest caveats baked in",
          "- **Confounding by indication:** clinicians titrate *because* MAP is low and often in "
          "response to the same waveform -- so dMAP at a step is the treated response, not a clean "
          "dose-response. The model target is 'observed responsiveness under care'; causal "
          "dose-response needs the isolated-step + covariate-adjusted design (isolated-event flag "
          "already captured).",
          "- **Onset/timing:** phenylephrine/norepi act in ~30-60 s; the 45-165 s response window "
          "is chosen for that. Sensitivity to the window is future work.",
          "- **Single-centre (SNUH/VitalDB).** External replication is required for any claim.",
          f"\n_GATE thresholds (pre-declared): {json.dumps(GATE)}._"]
    open(os.path.join(_DOCS, "PRESSOR_RESPONSE_FEASIBILITY.md"), "w").write("\n".join(L) + "\n")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.environ.get("PRF_LIMIT", "40")))
    ap.add_argument("--summarize-only", action="store_true")
    a = ap.parse_args()
    trks = os.path.join(_CACHE, "trks.csv")
    if a.summarize_only:
        pc, by_drug, co, fl, mc = _cohort_from_trks(trks)
        cohort_info = {"cohort_pressor_map": len(pc & mc),
                       "cohort_pressor_map_co": len(pc & mc & co),
                       "cohort_fluid_fms": len(fl),
                       "by_drug": {d: len(cs) for d, cs in by_drug.items()}}
    else:
        cohort_info = extract(a.limit)
    s = summarize(cohort_info)
    verdict = _verdict(s, cohort_info)
    out = {"seed": SEED, "gate": GATE, "cohort": cohort_info, "summary": s, "verdict": verdict}
    json.dump(out, open(os.path.join(_CACHE, "pressor_response_feasibility.json"), "w"),
              indent=2, default=float)
    _doc(s, cohort_info, verdict)
    print("\n[prf] VERDICT:\n" + verdict, flush=True)
    print("[prf] -> docs/PRESSOR_RESPONSE_FEASIBILITY.md", flush=True)


if __name__ == "__main__":
    main()
