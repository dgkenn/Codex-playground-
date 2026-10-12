"""End-to-end path coverage for E23 (suppression confound) and E24 (Challenge C), on SYNTHETIC tables.

Same reasoning as `test_e22_paths.py`: both experiments gate early, so their later sections would otherwise
never execute until the day a real table happens to clear every gate — and code that has never run is not
code that works. The fixtures are built so every branch is reachable. **They carry no claim about any
candidate**; the assertions are that the sections run and that the recorded state is internally consistent,
never that a particular number came out.
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

EXP = os.path.abspath(os.path.join(HERE, "..", "src", "bsde", "experiments"))

BASE_FIELDS = ["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq",
               "n_samples", "meta_caseid", "meta_subjectid", "meta_t_s", "meta_rel_anestart_s",
               "meta_rel_aneend_s", "meta_anestart_s", "meta_aneend_s", "meta_opstart_s", "meta_opend_s",
               "meta_agents_present", "meta_age", "meta_sex", "meta_asa", "meta_bmi", "meta_emop",
               "meta_intraop_ppf", "meta_intraop_mdz", "meta_intraop_rocu", "meta_intraop_vecu",
               "meta_bis", "meta_sqi", "meta_sr", "meta_emg", "meta_sensor_off", "meta_nan_fraction"]

CANDS = ["exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
         "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
         "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
         "emg_beta_gamma_fraction", "emg_kurtosis", "emg_index", "exponent_gamma",
         "spatial_participation_ratio", "uce_v1", "wpli_alpha"]


def _load(fname, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(EXP, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path, n_per_drug=22, n_deep=22, n_light=8, seed=0):
    """A table with a deep phase that becomes light, and suppression present in part of the deep phase.

    Every patient gets: deep windows (BIS 35-55), of which the first third are scored suppressed (SR > 0),
    then light windows (BIS 85-95). That gives E23 both SR strata inside the deep arm and gives E24 a clean
    emergence landmark preceded by many deep windows. The candidate columns carry a state difference and a
    drift toward emergence so that every downstream branch computes; the sizes are arbitrary.
    """
    rng = np.random.default_rng(seed)
    fields = BASE_FIELDS + CANDS
    rows = []
    for di, drug in enumerate(("propofol", "sevoflurane", "desflurane")):
        for p in range(n_per_drug):
            sid = f"subj{drug[:4]}{p}"
            t = 0.0
            for k in range(n_deep + n_light):
                light = k >= n_deep
                suppressed = (not light) and k < n_deep // 3
                t += 300.0
                approach = max(0.0, 1.0 - abs(n_deep - k) / 6.0)      # rises as emergence nears
                val = 2.0 + 0.1 * di + 0.6 * light + 0.3 * approach + rng.normal(0, 0.2)
                r = {f: "" for f in fields}
                r.update({"recording_id": f"{sid}@t{t:.0f}", "dataset": "vitaldb_grid", "subject": sid,
                          "status": "ok", "n_channels": "1", "sfreq": "128.0", "n_samples": "3840",
                          "meta_caseid": f"{di}{p}", "meta_subjectid": sid, "meta_t_s": f"{t}",
                          "meta_rel_aneend_s": f"{t - 7000.0}", "meta_agents_present": drug,
                          "meta_bis": f"{rng.uniform(85, 95) if light else rng.uniform(35, 55)}",
                          "meta_sqi": "95.0",
                          "meta_sr": f"{rng.uniform(5, 40) if suppressed else 0.0}",
                          "meta_emg": f"{rng.uniform(45, 60) if light else rng.uniform(25, 35)}",
                          "meta_sensor_off": "False", "meta_nan_fraction": "0.0"})
                for c in CANDS:
                    r[c] = f"{val + rng.normal(0, 0.15)}"
                rows.append(r)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


def test_e23_runs_every_section(tmp_path, capsys, monkeypatch):
    mod = _load("e23_suppression_confound.py", "e23_under_test")
    table = _write(str(tmp_path / "vitaldb_grid.csv"))
    out = str(tmp_path / "e23.json")
    monkeypatch.setattr(mod, "OUT", out)
    rc = mod.main(["--table", table])
    text = capsys.readouterr().out
    assert rc == 0, text[-2500:]
    for section in ("P1 — GATE", "P2 — HOW MUCH", "P3 — PRIMARY", "P4 — THE CONVERSE", "VERDICT"):
        assert section in text, f"{section} never ran:\n{text[-3000:]}"
    state = json.load(open(out))
    assert state["p1"]["passed"] is True
    # Both SR strata must be present inside the deep arm -- that IS the rule-32 gate.
    assert state["p1"]["n_both"] >= 15
    assert set(state["p3"]["strata"]) == {"all unresp windows", "SR == 0 only"}
    assert state["verdict"] in {"survives_suppression_restriction", "is_substantially_suppression",
                                "absent"}


def test_e23_gate_fails_when_suppression_never_varies(tmp_path, capsys, monkeypatch):
    """Rule 32 directly: if SR is 0 everywhere, the restriction is not a restriction and P3 is untestable.

    The gate must FAIL rather than pass vacuously on a stratum that is the whole arm.
    """
    mod = _load("e23_suppression_confound.py", "e23_flat_sr")
    table = str(tmp_path / "vitaldb_grid.csv")
    _write(table)
    with open(table, newline="") as fh:
        rd = csv.DictReader(fh)
        fields, rows = list(rd.fieldnames), list(rd)
    for r in rows:
        r["meta_sr"] = "0.0"
    with open(table, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "e23.json"))
    rc = mod.main(["--table", table])
    text = capsys.readouterr().out
    assert rc == 1 and "*** FAILED" in text
    assert "ABSENT, not negative" in text


def test_e24_runs_every_section(tmp_path, capsys, monkeypatch):
    mod = _load("e24_challenge_c_ahead_of_monitor.py", "e24_under_test")
    table = _write(str(tmp_path / "vitaldb_grid.csv"))
    out = str(tmp_path / "e24.json")
    monkeypatch.setattr(mod, "OUT", out)
    rc = mod.main(["--table", table])
    text = capsys.readouterr().out
    assert rc == 0, text[-2500:]
    for section in ("P1 — MACHINERY GATE", "P2 — THE BAR", "P3 — PRIMARY", "P4 — PLACEBO GATE",
                    "P5 — LEAD TIME", "VERDICT"):
        assert section in text, f"{section} never ran:\n{text[-3000:]}"
    state = json.load(open(out))
    assert state["p1"]["passed"] is True
    assert 0.10 <= state["p1"]["base_rate"] <= 0.90
    # The incumbent's score is recorded, and it is recorded BEFORE any candidate by construction.
    assert "bis_auc" in state["p2"]
    assert text.index("P2 — THE BAR") < text.index("P3 — PRIMARY")
    assert state["verdict"] in {"met", "no_increment", "withdrawn_by_placebo", "ungated"}


def test_e24_gate_fails_without_landmarks(tmp_path, capsys, monkeypatch):
    """No patient ever reaches BIS >= 80, so there is no transition to be ahead of."""
    mod = _load("e24_challenge_c_ahead_of_monitor.py", "e24_no_landmark")
    table = str(tmp_path / "vitaldb_grid.csv")
    _write(table)
    with open(table, newline="") as fh:
        rd = csv.DictReader(fh)
        fields, rows = list(rd.fieldnames), list(rd)
    for r in rows:
        if float(r["meta_bis"]) >= 80.0:
            r["meta_bis"] = "65.0"
    with open(table, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(mod, "OUT", str(tmp_path / "e24.json"))
    rc = mod.main(["--table", table])
    text = capsys.readouterr().out
    assert rc == 1 and "ABSENT, not negative" in text


def test_oob_increment_is_not_fooled_by_a_noise_column():
    """The estimator E24's primary rests on. A column of pure noise must not buy an increment."""
    from bsde.verifier.stats import oob_auc_increment
    rng = np.random.default_rng(3)
    n_s, n_w = 60, 8
    subj = np.repeat([f"s{i}" for i in range(n_s)], n_w)
    y = rng.integers(0, 2, n_s * n_w).astype(float)
    base = rng.normal(size=n_s * n_w)
    one = np.ones(n_s * n_w)
    Xa = np.column_stack([one, base])
    Xb = np.column_stack([one, base, rng.normal(size=n_s * n_w)])
    inc, lo, hi, n = oob_auc_increment(Xa, Xb, y, subj, rng, reps=200)
    assert n >= 30
    assert lo <= 0.0 <= hi, f"a noise column bought an increment: {inc} [{lo}, {hi}]"
