"""E58's gates must be constructible into failure (rule 40).

E58 has two machinery gates and one placebo, and each is asserted here against an input built to break it:

  M1 JOIN INTEGRITY  a single disagreeing `meta_bis` between the two tables must stop the run, because both
                     read it from the same source and a disagreement means the join is wrong.
  M2 CAPABILITY      a constant subparameter column must be marked UNUSABLE and dropped from every arm.
                     This is the gate E58's own registration predicts `bis_bsr` will fail on
                     maintenance-only windows, so it must demonstrably fire.
  P1 PLACEBO         a within-case shuffle of the subparameter block must be able to reach the real
                     improvement, or the NOT INFORMATIVE branch is unreachable.

The last test is the complement of the others and matters just as much: a genuinely informative
subparameter must produce the GAIN verdict, or the gates are simply refusing everything.
"""
from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from bsde.experiments import e58_bis_like_index as e58

OURS = ["feat_a", "feat_b"]
GRID_FIELDS = (["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq",
                "n_samples", "meta_caseid", "meta_bis", "meta_sensor_off", "meta_sr", "meta_emg"] + OURS)
BIS_FIELDS = ["recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq",
              "n_samples", "meta_caseid", "meta_bis"] + e58.SUBPARAMS


def _write(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def _cohort(tmp_path, n_cases=24, per_case=12, sfs_beta=6.0, bsr_constant=True,
            bis_mismatch=0, seed=0):
    """Paired tables where `bis_sfs` carries real signal and `bis_bsr` is constant by construction."""
    rng = np.random.default_rng(seed)
    grid, bis = [], []
    for c in range(n_cases):
        for i in range(per_case):
            rid = f"case{c}@t{i}"
            a, b, sfs = rng.normal(size=3)
            y = 45.0 + 4.0 * a + 2.0 * b + sfs_beta * sfs + rng.normal(0, 2.0)
            grid.append({"recording_id": rid, "status": "ok", "meta_caseid": f"case{c}",
                         "meta_bis": f"{y:.10g}", "meta_sensor_off": "0",
                         "meta_sr": "0", "meta_emg": f"{rng.normal(30, 3):.4g}",
                         "feat_a": f"{a:.10g}", "feat_b": f"{b:.10g}"})
            bis.append({"recording_id": rid, "status": "ok", "meta_caseid": f"case{c}",
                        "meta_bis": f"{y:.10g}", "bis_rbr": f"{rng.normal():.10g}",
                        "bis_bsr": "0" if bsr_constant else f"{rng.normal():.10g}",
                        "bis_quazi": f"{rng.normal():.10g}", "bis_sfs": f"{sfs:.10g}"})
    for k in range(bis_mismatch):
        bis[k]["meta_bis"] = f"{float(bis[k]['meta_bis']) + 1.0:.10g}"
    g = tmp_path / "grid.csv"
    b = tmp_path / "bis.csv"
    _write(g, GRID_FIELDS, grid)
    _write(b, BIS_FIELDS, bis)
    return str(g), str(b)


def _run(monkeypatch, tmp_path, **kw):
    g, b = _cohort(tmp_path, **kw)
    out = str(tmp_path / "out.json")
    monkeypatch.setattr(e58, "GRID", g)
    monkeypatch.setattr(e58, "BIS", b)
    monkeypatch.setattr(e58, "OUT", out)
    rc = e58.main()
    return rc, json.load(open(out))


def test_m1_fails_on_a_single_meta_bis_disagreement(monkeypatch, tmp_path):
    """One mismatched row out of 288 must stop the run. A wrong join is not a noisy monitor."""
    rc, res = _run(monkeypatch, tmp_path, bis_mismatch=1)
    assert rc == 1
    assert res["gate_m1"] is False and res["n_mismatch"] == 1


def test_m1_passes_when_the_join_is_clean(monkeypatch, tmp_path):
    rc, res = _run(monkeypatch, tmp_path)
    assert rc == 0 and res["gate_m1"] is True and res["join_rate"] == pytest.approx(1.0)


def test_m2_marks_a_constant_subparameter_unusable(monkeypatch, tmp_path):
    """The gate E58 predicts bis_bsr will fail on maintenance-only windows. It must actually fire."""
    _, res = _run(monkeypatch, tmp_path, bsr_constant=True)
    assert res["capability"]["bis_bsr"]["usable"] is False
    assert res["capability"]["bis_sfs"]["usable"] is True
    assert res["gate_m2_all"] is False


def test_m2_passes_every_column_when_all_of_them_vary(monkeypatch, tmp_path):
    """The complement: M2 must not simply reject things."""
    _, res = _run(monkeypatch, tmp_path, bsr_constant=False)
    assert res["gate_m2_all"] is True


def test_an_informative_subparameter_reaches_the_gain_verdict(monkeypatch, tmp_path):
    """bis_sfs is built to carry real window-level signal, so the GAIN branch must be reachable."""
    _, res = _run(monkeypatch, tmp_path, sfs_beta=6.0)
    assert res["primary_increment_C_minus_A"]["hi"] < 0
    assert res["verdict"].startswith("GAIN")


def test_a_useless_subparameter_reaches_the_no_gain_verdict(monkeypatch, tmp_path):
    """With no signal in any subparameter, the increment must span zero rather than find something."""
    _, res = _run(monkeypatch, tmp_path, sfs_beta=0.0)
    assert not res["verdict"].startswith("GAIN"), res["primary_increment_C_minus_A"]


def test_the_placebo_cannot_beat_a_real_window_level_effect(monkeypatch, tmp_path):
    """The shuffle destroys window-level alignment, so it must NOT match a real window-level gain.

    If it did, the NOT INFORMATIVE branch would fire on every genuine result and the experiment could
    never conclude anything.
    """
    _, res = _run(monkeypatch, tmp_path, sfs_beta=6.0)
    assert res["placebo_within_case"]["mean"] > res["primary_increment_C_minus_A"]["mean"]
