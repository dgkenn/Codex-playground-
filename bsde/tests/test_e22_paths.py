"""End-to-end path coverage for E22, on a SYNTHETIC table.

WHY A SYNTHETIC TABLE AND NOT THE REAL ONE. E22's later sections — the drug probe, the placebo, the muscle
control — only execute when the sections above them pass. On the real part-streamed table the machinery gate
fails, so P4, P5 and P6 had never run at all. That is exactly the situation E15 was in when a smoke test
reported "GATE PASSED (100.0 %)" from a single row: code that has never executed is not code that works.

The table here is built so that every gate passes and every branch is reachable. It carries no claim about
any candidate and its numbers mean nothing — the test asserts that the sections RUN and that the recorded
verdict is internally consistent, never that a particular AUC came out.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

E22_PATH = os.path.abspath(os.path.join(HERE, "..", "src", "bsde", "experiments",
                                        "e22_challenge_a_bis_arms.py"))

FIELDS = ["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples",
          "meta_caseid", "meta_subjectid", "meta_t_s", "meta_rel_anestart_s", "meta_rel_aneend_s",
          "meta_anestart_s", "meta_aneend_s", "meta_opstart_s", "meta_opend_s", "meta_agents_present",
          "meta_age", "meta_sex", "meta_asa", "meta_bmi", "meta_emop", "meta_intraop_ppf",
          "meta_intraop_mdz", "meta_intraop_rocu", "meta_intraop_vecu",
          "meta_bis", "meta_sqi", "meta_sr", "meta_emg", "meta_sensor_off", "meta_nan_fraction"]


def _load_e22():
    spec = importlib.util.spec_from_file_location("e22_under_test", E22_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_table(path, n_per_drug=20, n_deep=20, n_light=8, seed=0):
    """Every drug group gets enough patients to clear the coverage floor, and every patient gets both arms.

    Sized to clear E22's own 1,500-row floor rather than to bypass it: 3 drugs x 20 patients x 28 windows
    is 1,680. Deep windows come early in the case and light ones late, so the direction half of the
    machinery gate passes on the clinical record alone. `exponent_high` is drawn with a real state difference and a small
    drug offset, which is enough to make the probe and the placebo compute; nothing is asserted about the
    values.
    """
    rng = np.random.default_rng(seed)
    cands = ["exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
             "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
             "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
             "emg_beta_gamma_fraction", "emg_kurtosis", "emg_index", "exponent_gamma",
             "spatial_participation_ratio", "uce_v1", "wpli_alpha"]
    fields = FIELDS + cands
    rows = []
    for di, drug in enumerate(("propofol", "sevoflurane", "desflurane")):
        for p in range(n_per_drug):
            sid = f"subj{drug[:4]}{p}"
            t = 0.0
            for k in range(n_deep + n_light):
                light = k >= n_deep
                t += 300.0
                base = 2.0 + 0.10 * di + rng.normal(0, 0.25)
                r = {f: "" for f in fields}
                r.update({"recording_id": f"{sid}@t{t:.0f}", "dataset": "vitaldb_grid", "subject": sid,
                          "status": "ok", "n_channels": "1", "sfreq": "128.0", "n_samples": "3840",
                          "meta_caseid": f"{di}{p}", "meta_subjectid": sid, "meta_t_s": f"{t}",
                          "meta_rel_aneend_s": f"{t - 4000.0}", "meta_agents_present": drug,
                          "meta_bis": f"{rng.uniform(85, 95) if light else rng.uniform(35, 55)}",
                          "meta_sqi": "95.0", "meta_sr": "0.0",
                          "meta_emg": f"{rng.uniform(45, 60) if light else rng.uniform(25, 35)}",
                          "meta_sensor_off": "False", "meta_nan_fraction": "0.0"})
                for c in cands:
                    r[c] = f"{base + (0.6 if light else 0.0) + rng.normal(0, 0.2)}"
                rows.append(r)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


def test_every_section_runs_and_the_verdict_is_recorded(tmp_path, capsys, monkeypatch):
    mod = _load_e22()
    table = _write_table(str(tmp_path / "vitaldb_grid.csv"))
    out = str(tmp_path / "e22.json")
    monkeypatch.setattr(mod, "OUT", out)
    rc = mod.main(["--table", table])
    text = capsys.readouterr().out

    assert rc == 0, text[-2000:]
    for section in ("P1 — MACHINERY GATE", "P2 — RESPONSIVENESS", "P3 — DRUG INVARIANCE",
                    "P4 — DRUG-IDENTITY PROBE", "P5 — PLACEBO", "P6 — MUSCLE CONTROL", "VERDICT"):
        assert section in text, f"{section} never ran:\n{text[-3000:]}"

    state = json.load(open(out))
    assert state["p1"]["passed"] is True
    assert set(state["p2"]["per_arm"]) == {"propofol", "sevoflurane", "desflurane"}
    # All three pairs are covered by construction, so none may come back ABSENT.
    assert len(state["p4"]["pairs"]) == 3
    assert all(v.get("reason") != "underpowered" for v in state["p4"]["pairs"].values())
    assert state["verdict"] in {"met", "failed_drug_probe", "failed_p2", "withdrawn_by_placebo",
                                "ungated", "acceptance_condition_untested"}


def test_the_row_count_floor_refuses_a_thin_table(tmp_path, capsys):
    mod = _load_e22()
    table = _write_table(str(tmp_path / "thin.csv"), n_per_drug=2, n_deep=2, n_light=1)
    rc = mod.main(["--table", table])
    text = capsys.readouterr().out
    assert rc == 2 and "below the registered floor" in text


def test_the_sensor_off_rows_are_excluded_not_read_as_bis_zero(tmp_path, capsys):
    """The E21 defect, pinned: a detached-sensor row must not enter either arm.

    Rows are written with `meta_bis` of exactly 0.0 and `meta_sensor_off` True — the literal shape the
    monitor produces. If they leaked in they would land in the unresponsive arm as the deepest windows in
    the table.
    """
    mod = _load_e22()
    table = str(tmp_path / "vitaldb_grid.csv")
    _write_table(table)
    with open(table, newline="") as fh:
        rd = csv.DictReader(fh)
        fields, rows = list(rd.fieldnames), list(rd)
    extra = []
    for i in range(60):
        r = dict(rows[i])
        r["recording_id"] = r["recording_id"] + "@off"
        r["meta_bis"], r["meta_sqi"], r["meta_sensor_off"] = "0.0", "0.0", "True"
        extra.append(r)
    with open(table, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows + extra)

    out = str(tmp_path / "e22.json")
    mod.OUT = out
    mod.main(["--table", table])
    text = capsys.readouterr().out
    assert "sensor off (SQI = 0, all monitor values void) :    60 rows  EXCLUDED" in text
    state = json.load(open(out))
    assert state["exclusions"]["sensor_off"] == 60


def test_permutation_flag_destroys_the_direction_gate(tmp_path, capsys):
    """Rule 26's smoke test must actually be blind: shuffling BIS within subject should collapse the
    machinery gate that the unpermuted table passes."""
    mod = _load_e22()
    table = _write_table(str(tmp_path / "vitaldb_grid.csv"))
    mod.OUT = str(tmp_path / "e22_perm.json")
    rc = mod.main(["--table", table, "--permute-within-subject"])
    text = capsys.readouterr().out
    assert "NOTHING BELOW IS A RESULT" in text
    assert rc == 1 and "P1 FAILED" in text
