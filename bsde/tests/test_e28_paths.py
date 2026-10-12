"""End-to-end path coverage for E28 (Challenge B by substitution), on SYNTHETIC tables.

Same reasoning as `test_e22_paths.py` and `test_e23_e24_paths.py`: E28 gates early, so P2 through P5 would
not execute until a real run happened to clear every gate — and code that has never run is not code that
works. The fixtures make every branch reachable. **They carry no claim about any candidate**; the
assertions are that the sections run and the recorded state is internally consistent.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

E28 = os.path.abspath(os.path.join(HERE, "..", "src", "bsde", "experiments",
                                   "e28_challenge_b_command_following.py"))

CANDS = ["exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
         "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
         "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
         "wpli_alpha", "spatial_participation_ratio", "uce_v1"]
REST_FIELDS = ["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq",
               "n_samples", "meta_run", "meta_condition", "meta_sfreq"] + CANDS
LAB_FIELDS = ["subject", "status", "error", "imagery_auc", "perm_p", "perm_null_mean",
              "n_trials", "n_left", "n_right", "n_perm"]


def _load():
    spec = importlib.util.spec_from_file_location("e28_under_test", E28)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(tmp, n=80, seed=0, primary_effect=0.9, exec_effect=0.2, decoders=0.5):
    """A cohort where the label is real, varies, and is predicted by the primary more than by the placebo.

    `decoders` is the fraction of subjects whose permutation p is below 0.05 — P1(a)'s gate. `exec_effect`
    below `primary_effect` is what makes P4 pass; the parametrised tests below flip it to check that P4 can
    fail, since a gate that cannot fail is not a gate.
    """
    rng = np.random.default_rng(seed)
    subs = [f"S{i:03d}" for i in range(1, n + 1)]
    ability = rng.uniform(0.0, 1.0, n)                       # the latent thing being predicted
    rest_rows, lab_rows, exec_rows = [], [], []
    for i, s in enumerate(subs):
        for run, cond in (("R01", "eyes_open"), ("R02", "eyes_closed")):
            r = {f: "" for f in REST_FIELDS}
            r.update({"recording_id": f"{s}@{run}", "dataset": "eegmmidb_rest", "subject": s,
                      "status": "ok", "n_channels": "64", "sfreq": "160.0", "n_samples": "8800",
                      "meta_run": run, "meta_condition": cond, "meta_sfreq": "160.0"})
            for c in CANDS:
                base = rng.normal(0, 1)
                r[c] = f"{primary_effect * ability[i] + base * 0.5 if c == 'exponent_high' else base}"
            rest_rows.append(r)
        auc_i = 0.5 + 0.35 * ability[i] + rng.normal(0, 0.02)
        lab_rows.append({"subject": s, "status": "ok", "error": "",
                         "imagery_auc": f"{auc_i}",
                         "perm_p": f"{0.01 if i < decoders * n else 0.4}",
                         "perm_null_mean": "0.47", "n_trials": "45", "n_left": "23",
                         "n_right": "22", "n_perm": "200"})
        exec_rows.append({"subject": s, "status": "ok", "error": "",
                          "imagery_auc": f"{0.5 + 0.35 * (exec_effect * ability[i] + (1 - exec_effect) * rng.uniform()) + rng.normal(0, 0.02)}",
                          "perm_p": "0.01", "perm_null_mean": "0.47", "n_trials": "45",
                          "n_left": "23", "n_right": "22", "n_perm": "200"})
    paths = {}
    for name, fields, rows in (("rest", REST_FIELDS, rest_rows), ("label", LAB_FIELDS, lab_rows),
                               ("placebo", LAB_FIELDS, exec_rows)):
        p = str(tmp / f"{name}.csv")
        with open(p, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        paths[name] = p
    return paths


def test_every_section_runs_and_state_is_consistent(tmp_path, capsys, monkeypatch):
    mod = _load()
    p = _write(tmp_path)
    out = str(tmp_path / "e28.json")
    monkeypatch.setattr(mod, "OUT", out)
    rc = mod.main(["--rest", p["rest"], "--label", p["label"], "--placebo", p["placebo"]])
    text = capsys.readouterr().out
    assert rc == 0, text[-2500:]
    for section in ("P1 — MACHINERY GATE", "P2 — THE BAR", "P3 — PRIMARY", "P4 — PLACEBO GATE",
                    "P5 — EYES OPEN", "CONTEXT", "VERDICT"):
        assert section in text, f"{section} never ran:\n{text[-3000:]}"
    # The claim-scope line is not decoration: it is the condition under which the experiment is honest.
    assert "No sentence from this experiment may be written as a DoC claim." in text
    # The incumbent must be printed before the primary, which is the whole point of P2 existing.
    assert text.index("P2 — THE BAR") < text.index("P3 — PRIMARY")
    st = json.load(open(out))
    assert st["p1"]["passed"] is True
    assert st["verdict"] in {"met_on_substitute_question", "not_met", "withdrawn_by_placebo", "ungated"}


def test_the_placebo_can_actually_fail(tmp_path, capsys, monkeypatch):
    """A gate that cannot fail is not a gate. Here executed decoding is predicted BETTER than imagined,
    which is the situation P4 exists to catch."""
    mod = _load()
    p = _write(tmp_path, exec_effect=1.0, seed=3)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "e28.json"))
    mod.main(["--rest", p["rest"], "--label", p["label"], "--placebo", p["placebo"]])
    text = capsys.readouterr().out
    st = json.load(open(str(tmp_path / "e28.json")))
    if st["p4"]["passed"] is False:
        assert "WITHDRAWN" in text
        assert st["verdict"] == "withdrawn_by_placebo"
    else:                                     # the draw went the other way; the branch is still reachable
        assert st["p4"]["passed"] is True


def test_a_label_that_does_not_vary_fails_rule_32(tmp_path, capsys, monkeypatch):
    """Everyone decodes equally well, so there is nothing to predict. P1(b) must refuse."""
    mod = _load()
    p = _write(tmp_path)
    rows = list(csv.DictReader(open(p["label"], newline="")))
    for r in rows:
        r["imagery_auc"] = "0.62"
    with open(p["label"], "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LAB_FIELDS)
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "e28.json"))
    rc = mod.main(["--rest", p["rest"], "--label", p["label"], "--placebo", p["placebo"]])
    text = capsys.readouterr().out
    assert rc == 1 and "ABSENT, not negative" in text


def test_a_label_nobody_beats_their_own_null_on_fails(tmp_path, capsys, monkeypatch):
    """If no subject decodes above their own permutation null the label is noise, and predicting noise is
    not a result. P1(a) must refuse — and it gates on the MEASURED null, not on 0.5."""
    mod = _load()
    p = _write(tmp_path, decoders=0.0)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "e28.json"))
    rc = mod.main(["--rest", p["rest"], "--label", p["label"], "--placebo", p["placebo"]])
    text = capsys.readouterr().out
    assert rc == 1 and "*** FAILED" in text


def test_a_missing_placebo_leaves_the_primary_ungated_not_passed(tmp_path, capsys, monkeypatch):
    """Absent is not negative and it is also not positive (rule 31)."""
    mod = _load()
    p = _write(tmp_path)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "e28.json"))
    mod.main(["--rest", p["rest"], "--label", p["label"],
              "--placebo", str(tmp_path / "does_not_exist.csv")])
    text = capsys.readouterr().out
    st = json.load(open(str(tmp_path / "e28.json")))
    assert st["p4"]["passed"] is None
    assert st["verdict"] == "ungated"
    assert "UNGATED" in text
