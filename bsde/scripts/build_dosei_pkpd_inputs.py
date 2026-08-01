"""Assemble the PHARMACOLOGY side of DOSE-I: the full-resolution propofol dose record, the demographic
and comorbidity covariates, and the procedural stimulus indicator -- everything needed to predict sedation
depth WITHOUT looking at the EEG.

WHY THIS EXISTS. `docs/DEPTH_TARGET_STRATEGY.md` argues the EEG should be scored against the RESIDUAL a
pharmacological model cannot predict, not against BIS (circular) and not against concentration (redundant
with the infusion pump). That requires a pharmacology-only predictor of clinical state, built from the drug
record alone. DOSE-I is the only deposit in this project that can supply one, because it carries a
clinician-assigned MOAA/S alongside the dose.

THE DOSE COLUMN IS AN EVENT SERIES, NOT A CONCENTRATION, AND IT MUST BE READ AT FULL RESOLUTION.
`pEEG_parameter_description.txt` column 46 reads verbatim:

    Column 46: Propofol administration (in multiples of 10 mg)

so a `2` at second t is a 20 mg bolus at second t, and the column is 0 for the other ~99.4 % of seconds
(270,347 zeros against 2,095 non-zero seconds across 171 recordings; median 12 dosing seconds per
recording, minimum 1, maximum 28). **The existing feature extracts sample every 5th second, which would
silently drop about four fifths of the dose events** -- this script therefore reads the 1 Hz pEEG table
directly rather than reusing `dosei_features.csv`.

WHAT IS WRITTEN, and nothing else: one row per (recording, second) that carries a dose, plus one row per
recording of covariates. No concentration is computed here and no model is fitted here -- that is
`bsde.pkpd.propofol` and E122 respectively, kept separate so the extraction can be checked on its own.

COVARIATES COME FROM THE DEPOSIT'S OWN STATIC TABLE, and the readme's wording is preserved rather than
interpreted. `drugs_opioids` etc. are documented only as "use of opioids; bool" -- the readme does not say
whether that is chronic medication or intra-procedural administration. The `Drug-related Events` section of
the metadata readme lists ONLY `PROP_sum` ("cumulative amount of Propofol given"), and `other_events` is
documented as containing "only 'PARA' marking paravasation of Propofol", so no second drug is recorded
anywhere in the deposit. Read together those two facts say DOSE-I is propofol mono-sedation and the
`drugs_*` booleans are pre-existing medication -- i.e. tolerance covariates. That reading is an INFERENCE
from two documented facts (rule 42) and it is written down here so a reader can check the gap.

EXTRAVASATION IS AN EXCLUSION AND IT IS PRE-SPECIFIED HERE, BEFORE ANY FIT. The metadata readme says
`PROP_sum` "does not account for possible extravasation; check the `other_events` parameter". Two
recordings carry `['PARA']`. In those the dose record overstates the drug that reached the circulation by
an unknown amount, which is exactly the quantity a PK model integrates, so they are flagged `para=1` and
E122 drops them.

    python bsde/scripts/build_dosei_pkpd_inputs.py
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
PEEG_ZIP = os.path.join(RESULTS, "dosei_pEEG.zip")
STATIC_URL = "https://zenodo.org/records/18483292/files/static.zip?download=1"
META_URL = "https://zenodo.org/records/18483292/files/metadata.zip?download=1"

DOSE_OUT = os.path.join(RESULTS, "dosei_dose_events.csv")
COVAR_OUT = os.path.join(RESULTS, "dosei_covariates.csv")

DOSE_FIELDS = ["recording", "t_abs_s", "dose_mg"]
COVAR_FIELDS = ["recording", "age", "sex", "height_cm", "weight_kg", "bmi", "asa",
                "chronic_bblocker", "chronic_opioids", "chronic_neuroleptics",
                "chronic_benzodiazepines", "chronic_antiepileptics",
                "cond_ohs", "cond_sas", "cond_ohe", "cond_chf",
                "care_type", "endoscopy_type", "prop_sum_mg", "dose_reconstructed_mg", "dose_complete",
                "record_len_s", "para"]


def _boolcol(v: str) -> str:
    return "1" if str(v).strip().lower() in ("true", "1", "yes") else "0"


def _zip_from_url(url: str) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url).read()))


def dose_events():
    """(recording, absolute clock seconds, mg) for every second with a non-zero Propofol entry.

    THE TIME ORIGIN IS THE DE-IDENTIFIED ABSOLUTE CLOCK, not either table's first row, and that choice is
    load-bearing. `extract_dosei_features.py` writes `t_s` as elapsed seconds from the first RAW EEG
    sample, while the pEEG table starts about ten seconds later -- so an origin taken from the pEEG file
    would shift every dose by that gap, in a direction that varies by recording. Both tables carry the same
    de-identified wall clock (2022-01-01 plus elapsed), so seconds-since-2022-01-01 is the one axis both
    can be placed on, and `_check_alignment` verifies it against the feature file rather than assuming it.

    Never index positionally: a missing second would shift every later dose (rule 27's sibling)."""
    from datetime import datetime
    z = zipfile.ZipFile(PEEG_ZIP)
    for m in sorted(z.namelist()):
        if not m.endswith("_pEEG.csv"):
            continue
        rec = m.split("/")[-1].split("_")[0]
        rows = list(csv.DictReader(io.StringIO(z.read(m).decode("utf8", "replace"))))
        if not rows:
            continue

        def ts(s):
            f = "%Y-%m-%d %H:%M:%S.%f" if "." in s else "%Y-%m-%d %H:%M:%S"
            return datetime.strptime(s, f)

        t0 = datetime(2022, 1, 1)
        for r in rows:
            v = (r.get("Propofol") or "").strip()
            if not v or v in ("0", "0.0", "?"):
                continue
            try:
                mult = float(v)
            except ValueError:
                continue
            if mult == 0.0:
                continue
            yield rec, (ts(r["Time"]) - t0).total_seconds(), mult * 10.0


def clock_offsets(feature_paths, out_path: str):
    """Per-recording offset carrying a feature-file `t_s` onto the de-identified absolute clock.

    THE TWO PIPELINES DO NOT SHARE AN ORIGIN AND THE GAP IS NOT A CONSTANT. `extract_dosei_features.py`
    writes `t_s` as elapsed seconds from the first RAW EEG sample; the dose events above are seconds since
    2022-01-01. The raw record starts at its own second in each recording, so the offset is per-recording.
    Assuming it away was the first thing tried here and it fails: matching feature-visible dose events at a
    global shift of 0 hits 14 of 221, and the per-recording best shifts run from -50 s to +58 s.

    THE OFFSET IS RECOVERED, NOT GUESSED, AND THE SEARCH IS EXHAUSTIVE RATHER THAN WINDOWED. Both files
    carry the depositors' own 1 Hz `PE31`, `SEF95`, `MOAAS` and `SOC`; the feature file copies all four
    verbatim. The candidate offsets are exactly `{pEEG second} - {first feature second}`, which is a few
    hundred values per recording and cannot miss the answer -- a +/-300 s window was tried first and missed
    `10-087`, whose pEEG series starts at 00:14:51. Scoring on the four-tuple rather than on `PE31` alone
    matters too: several recordings ship `PE31` and `SEF95` empty throughout, and `MOAAS`/`SOC` still pin
    the offset because the candidate set is already narrow.

    Aligning on a dose event instead would be circular: the dose record is the thing being placed.

    Rule 65 in one line: validate a time index against the signal, never against the assumption that
    produced it."""
    from datetime import datetime
    z = zipfile.ZipFile(PEEG_ZIP)
    have = {n.split("/")[-1].replace("_pEEG.csv", "") for n in z.namelist() if n.endswith("_pEEG.csv")}

    feats = {}
    for p in feature_paths:
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, newline="")):
            key = tuple((r.get(c) or "").strip()
                        for c in ("their_pe31", "their_sef95", "moaas", "soc"))
            feats.setdefault(r["recording"], {})[int(float(r["t_s"]))] = key

    rows, undetermined = [], []
    for rec in sorted(feats):
        if rec not in have:
            continue
        peeg = {}
        for r in csv.DictReader(io.StringIO(z.read(f"pEEG/pEEG/{rec}_pEEG.csv").decode("utf8", "replace"))):
            t = int((datetime.strptime(r["Time"], "%Y-%m-%d %H:%M:%S.%f" if "." in r["Time"]
                                       else "%Y-%m-%d %H:%M:%S") - datetime(2022, 1, 1)).total_seconds())
            peeg[t] = tuple((r.get(c) or "").strip() for c in ("PE31", "SEF95", "MOAAS", "SOC"))
        ev = feats[rec]
        t0f = min(ev)
        best, best_n = None, -1
        for s in sorted({t - t0f for t in peeg}):
            n = sum(1 for t, k in ev.items() if peeg.get(t + s) == k)
            if n > best_n:
                best, best_n = s, n
        frac = best_n / max(1, len(ev))
        if frac < 0.99:
            undetermined.append((rec, best, best_n, len(ev)))
            continue
        rows.append({"recording": rec, "offset_s": best, "matched": best_n, "n_rows": len(ev)})

    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["recording", "offset_s", "matched", "n_rows"])
        w.writeheader()
        w.writerows(rows)
    vals = sorted({r["offset_s"] for r in rows})
    print(f"clock offsets: {len(rows)} recordings determined (>=99 % of pEEG rows reproduced exactly), "
          f"{len(undetermined)} undetermined; offsets span {vals[0]} .. {vals[-1]} s "
          f"({len(vals)} distinct) -> {out_path}")
    for rec, s, n, k in undetermined[:5]:
        print(f"   UNDETERMINED {rec}: best shift {s} reproduced {n}/{k} rows")
    assert len(rows) > 0.9 * (len(rows) + len(undetermined)), "too many undetermined offsets"
    return rows


def check_alignment(dose_path: str, offsets, feature_paths) -> None:
    """Now that the clocks agree, confirm the DOSE record lands where the feature file says it does.

    `extract_dosei_features.py` copies the pEEG `Propofol` cell into every window it writes, so a feature
    row with a non-zero `propofol` is a dose event seen through the other pipeline. Shifting it by the
    recovered offset must reproduce the dose event exactly. This is a genuinely independent check --
    the offsets above were fitted on `PE31`/`SEF95` and never saw the dose column."""
    off = {r["recording"]: int(r["offset_s"]) for r in offsets}
    dose = {}
    for r in csv.DictReader(open(dose_path, newline="")):
        dose.setdefault(r["recording"], {})[int(r["t_abs_s"])] = float(r["dose_mg"])
    hit = tot = 0
    misses = []
    for p in feature_paths:
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, newline="")):
            v = (r.get("propofol") or "").strip()
            rec = r["recording"]
            if not v or v in ("0", "0.0") or rec not in off:
                continue
            tot += 1
            t = int(float(r["t_s"])) + off[rec]
            if abs(dose.get(rec, {}).get(t, -1.0) - float(v) * 10.0) < 1e-6:
                hit += 1
            elif len(misses) < 5:
                misses.append((rec, r["t_s"], v))
    print(f"dose alignment: {hit}/{tot} feature-visible dose events reproduced at the recovered offset")
    for m in misses:
        print(f"   MISS {m}")
    assert tot and hit == tot, "dose events do not land on the recovered clock -- do not proceed"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dose-out", default=DOSE_OUT)
    ap.add_argument("--covar-out", default=COVAR_OUT)
    a = ap.parse_args(argv)

    n_dose, per_rec = 0, {}
    with open(a.dose_out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DOSE_FIELDS)
        w.writeheader()
        for rec, t, mg in dose_events():
            w.writerow({"recording": rec, "t_abs_s": f"{t:.0f}", "dose_mg": f"{mg:.0f}"})
            n_dose += 1
            per_rec[rec] = per_rec.get(rec, 0.0) + mg
    # Rule 5: empty is not evidence of absence. A dose record that came back empty, or a recording set that
    # disagrees with the deposit's own count, means the parse is wrong rather than the patients undosed.
    assert n_dose > 0, "no dose events parsed -- check the Propofol column name"
    assert len(per_rec) > 100, f"only {len(per_rec)} recordings carry a dose event"

    stat = _zip_from_url(STATIC_URL)
    srows = {r["ID"]: r for r in csv.DictReader(
        io.StringIO(stat.read("static/DOSE-I_static_data.csv").decode("utf8", "replace")))}
    meta = _zip_from_url(META_URL)
    mrows = {r["ID"]: r for r in csv.DictReader(
        io.StringIO(meta.read("metadata/DOSE-I_metadata.csv").decode("utf8", "replace")))}

    # The pEEG members are named `10-003`; the static/metadata tables key on `3`. Strip the site prefix and
    # the zero padding rather than assuming either side's format.
    def sid(rec: str) -> str:
        return str(int(rec.split("-")[-1]))

    n_cov, n_para, n_missing = 0, 0, 0
    with open(a.covar_out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COVAR_FIELDS)
        w.writeheader()
        for rec in sorted(per_rec):
            s, m = srows.get(sid(rec)), mrows.get(sid(rec))
            if s is None or m is None:
                n_missing += 1
                continue
            para = 1 if "PARA" in (m.get("other_events") or "") else 0
            n_para += para
            got = per_rec[rec]
            want = float(m["PROP_sum"]) if (m.get("PROP_sum") or "").strip() else float("nan")
            complete = 1 if abs(want - got) < 1e-6 else 0
            w.writerow({
                "dose_reconstructed_mg": f"{got:.0f}", "dose_complete": complete,
                "recording": rec, "age": s["age"], "sex": s["sex"], "height_cm": s["height"],
                "weight_kg": s["weight"], "bmi": s["bmi"], "asa": s["ASA"],
                "chronic_bblocker": _boolcol(s["drugs_bblocker"]),
                "chronic_opioids": _boolcol(s["drugs_opioids"]),
                "chronic_neuroleptics": _boolcol(s["drugs_neuroleptics"]),
                "chronic_benzodiazepines": _boolcol(s["drugs_benzodiazepines"]),
                "chronic_antiepileptics": _boolcol(s["drugs_antiepileptics"]),
                "cond_ohs": _boolcol(s["conditions_OHS"]), "cond_sas": _boolcol(s["conditions_SAS"]),
                "cond_ohe": _boolcol(s["conditions_oHE"]), "cond_chf": _boolcol(s["conditions_CHF"]),
                "care_type": s["care_type"], "endoscopy_type": s["endoscopy_type"],
                "prop_sum_mg": m.get("PROP_sum", ""), "record_len_s": m.get("length", ""),
                "para": para})
            n_cov += 1

    # The deposit publishes its own cumulative dose. Reconstructing it from the event column is a free
    # end-to-end check on the parse, and a disagreement means the multiplier or the row filter is wrong.
    agree, disagree = 0, []
    for rec, mg in per_rec.items():
        m = mrows.get(sid(rec))
        if not m or not (m.get("PROP_sum") or "").strip():
            continue
        want = float(m["PROP_sum"])
        if abs(want - mg) < 1e-6:
            agree += 1
        else:
            disagree.append((rec, want, mg))

    print(f"dose events: {n_dose} over {len(per_rec)} recordings -> {a.dose_out}")
    print(f"covariates : {n_cov} recordings ({n_para} with propofol extravasation -> excluded downstream; "
          f"{n_missing} with no static/metadata row) -> {a.covar_out}")
    print(f"PROP_sum reproduction: {agree} exact, {len(disagree)} disagree -> dose_complete=0")
    for rec, want, got in disagree[:10]:
        print(f"   {rec}: deposit {want} mg, reconstructed {got} mg, missing {want - got:.0f} mg")
    fpaths = [os.path.join(RESULTS, "dosei_features.csv"),
              os.path.join(RESULTS, "dosei_holdout_features.csv")]
    offs = clock_offsets(fpaths, os.path.join(RESULTS, "dosei_clock_offsets.csv"))
    check_alignment(a.dose_out, offs, fpaths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
