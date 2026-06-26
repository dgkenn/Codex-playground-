"""Tests for the PK / drug-exposure module (Protocol Sec 8) -- stdlib only, offline.

Unit tests exercise the Eleveld propofol model and the exposure-integral helpers
on synthetic series with known properties (no network). The real-data validation
(coverage + Eleveld-vs-pump Ce Spearman correlation) lives under __main__ so the
unit suite stays offline and deterministic.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from vitaldb_aki.features.base import audit_specs, names_for_set
from vitaldb_aki.features import pk


# Reference adult for the propofol tests: 40 yr, 70 kg, 170 cm male.
REF = dict(age=40.0, weight=70.0, height=170.0, sex_male=True)


def _const_infusion(mg_per_min: float, seconds: int) -> tuple[list[float], list[float]]:
    """Constant infusion of mg/min delivered on a 1 Hz mg/s grid."""
    mg_s = [mg_per_min / 60.0] * seconds
    times = [float(i) for i in range(seconds + 1)]
    return mg_s, times


class TestContract(unittest.TestCase):
    def test_specs_pass_leakage_audit(self):
        audit_specs(pk.SPECS)  # no postop feature; no dup names

    def test_all_pk_and_intraop(self):
        for s in pk.SPECS:
            self.assertEqual(s.fset, "pk", s.name)
            self.assertEqual(s.timing, "intraop", s.name)

    def test_pk_is_superset_of_comprehensive_membership(self):
        # the +PK nested set includes pk-tagged names (Sec 9)
        names = names_for_set(pk.SPECS, "pk")
        self.assertIn("ppf_ce_peak", names)
        self.assertIn("pk_available", names)


class TestEleveldParams(unittest.TestCase):
    def test_reference_individual_matches_paper(self):
        # 35 yr / 70 kg / 170 cm male == Eleveld reference: V1=6.28, V2=25.5,
        # V3=273, CL=1.79, Q2=1.75, Q3=1.11, ke0=0.146 (BJA 2018).
        p = pk.eleveld_params(35.0, 70.0, 170.0, True)
        self.assertAlmostEqual(p["v1"], 6.28, places=2)
        self.assertAlmostEqual(p["v2"], 25.5, places=1)
        self.assertAlmostEqual(p["v3"], 273.0, delta=1.0)
        self.assertAlmostEqual(p["cl"], 1.79, places=2)
        self.assertAlmostEqual(p["q2"], 1.75, places=2)
        self.assertAlmostEqual(p["q3"], 1.11, places=2)
        self.assertAlmostEqual(p["ke0"], 0.146, places=3)

    def test_female_has_higher_reference_clearance_scaling(self):
        # theta15 (female CL ref 2.10) > theta04 (male 1.79) at the reference pt.
        pm = pk.eleveld_params(35.0, 70.0, 170.0, True)
        pf = pk.eleveld_params(35.0, 70.0, 170.0, False)
        self.assertGreater(pf["cl"], pm["cl"])


class TestEleveldCe(unittest.TestCase):
    def test_zero_infusion_stays_zero(self):
        mg_s = [0.0] * 600
        times = [float(i) for i in range(601)]
        ce = pk.eleveld_ce(mg_s, times, **REF)
        self.assertEqual(len(ce), 601)
        self.assertTrue(all(abs(x) < 1e-12 for x in ce))

    def test_constant_infusion_rises_monotonically(self):
        # 30 min constant infusion -> Ce should rise (monotone non-decreasing).
        mg_s, times = _const_infusion(120.0, 30 * 60)  # 120 mg/min
        ce = pk.eleveld_ce(mg_s, times, **REF)
        # sample every minute; each minute's Ce >= previous (allow tiny eps)
        mins = ce[::60]
        for a, b in zip(mins, mins[1:]):
            self.assertGreaterEqual(b, a - 1e-9)
        self.assertGreater(ce[-1], ce[60])  # clearly risen after the first minute

    def test_ce_decays_after_infusion_stops(self):
        # 10 min infusion then 30 min off -> Ce peaks then decays.
        on = [120.0 / 60.0] * (10 * 60)
        off = [0.0] * (30 * 60)
        mg_s = on + off
        times = [float(i) for i in range(len(mg_s) + 1)]
        ce = pk.eleveld_ce(mg_s, times, **REF)
        peak = max(ce)
        peak_idx = ce.index(peak)
        # peak occurs after the infusion stops (effect-site lag) but Ce at the end
        # is well below peak -> decay happened.
        self.assertLess(ce[-1], peak * 0.9)
        self.assertGreater(peak_idx, 60)

    def test_induction_bolus_peak_in_plausible_range(self):
        # ~2 mg/kg induction (140 mg) over 30 s -> effect-site peak a few ug/mL.
        dose_mg = 140.0
        secs = 30
        mg_s = [dose_mg / secs] * secs + [0.0] * (5 * 60)  # then 5 min observe
        times = [float(i) for i in range(len(mg_s) + 1)]
        ce = pk.eleveld_ce(mg_s, times, **REF)
        peak = max(ce)
        # clinical induction effect-site peak is roughly 2-8 ug/mL.
        self.assertTrue(1.5 < peak < 12.0, f"induction Ce peak {peak:.2f} ug/mL out of range")


class TestExposureIntegrals(unittest.TestCase):
    def test_constant_rate_known_area(self):
        # 60 mL/h for 10 min, drug 100 ug/mL.
        #   rate = 100 ug/mL * 60 mL/h / 60 = 100 ug/min
        #   AUC over 10 min = 1000 ug.min ; cum dose (no VOL) = integral = 1000 ug
        rate = [(float(t), 60.0) for t in range(0, 601, 30)]  # 0..600 s, 60 mL/h
        ex = pk.infusion_exposure(rate, [], conc_per_ml=100.0, t0=0.0, t1=600.0)
        self.assertAlmostEqual(ex["peak_rate"], 100.0, places=3)
        self.assertAlmostEqual(ex["auc_dose"], 1000.0, delta=1.0)
        self.assertAlmostEqual(ex["cum_dose"], 1000.0, delta=1.0)
        self.assertAlmostEqual(ex["dur_min"], 10.0, delta=0.1)

    def test_cum_dose_from_vol_preferred(self):
        # _VOL goes 0 -> 5 mL over the window; conc 100 ug/mL -> 500 ug cumulative.
        rate = [(float(t), 30.0) for t in range(0, 601, 60)]
        vol = [(0.0, 0.0), (300.0, 2.5), (600.0, 5.0)]
        ex = pk.infusion_exposure(rate, vol, conc_per_ml=100.0, t0=0.0, t1=600.0)
        self.assertAlmostEqual(ex["cum_dose"], 500.0, delta=1.0)

    def test_window_excludes_post_opend_samples(self):
        # samples past t1 (opend) must NOT contribute (Sec 11 leakage).
        rate = [(t, 60.0) for t in (0.0, 300.0, 600.0, 900.0, 1200.0)]
        ex_in = pk.infusion_exposure(rate, [], conc_per_ml=100.0, t0=0.0, t1=600.0)
        ex_all = pk.infusion_exposure(rate, [], conc_per_ml=100.0, t0=0.0, t1=1200.0)
        self.assertLess(ex_in["auc_dose"], ex_all["auc_dose"])
        self.assertAlmostEqual(ex_in["dur_min"], 10.0, delta=0.1)

    def test_absent_infusion_returns_none(self):
        ex = pk.infusion_exposure([], [], conc_per_ml=100.0, t0=0.0, t1=600.0)
        self.assertIsNone(ex["auc_dose"])
        self.assertIsNone(ex["peak_rate"])

    def test_time_weighted_summary(self):
        # flat value 2.0 for 10 min -> peak 2, mean 2, AUC 20 (value.min)
        series = [(float(t), 2.0) for t in range(0, 601, 60)]
        peak, mean, auc = pk._time_weighted_summary(series, 600.0)
        self.assertAlmostEqual(peak, 2.0)
        self.assertAlmostEqual(mean, 2.0, places=3)
        self.assertAlmostEqual(auc, 20.0, delta=0.1)


if __name__ == "__main__":
    # --- Offline unit tests first ------------------------------------------
    # (run with: python3 -m unittest vitaldb_aki.tests.test_pk -v)
    #
    # --- Real-subset validation (network) ----------------------------------
    # Run explicitly:  python3 vitaldb_aki/tests/test_pk.py --real
    if "--real" in sys.argv:
        import csv
        from common.config import load_yaml
        from vitaldb_aki.data.client import fetch_cases
        from vitaldb_aki.data.tracks import available_tracks
        from vitaldb_aki.features import pk as pkmod

        cfg = load_yaml(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml"))
        cohort_path = os.path.join(cfg["data"]["cache_dir"], "cohort.csv")
        with open(cohort_path, encoding="utf-8", newline="") as fh:
            cohort = list(csv.DictReader(fh))
        cases = {c["caseid"]: c for c in fetch_cases(cfg)}

        # find ~20 cohort cases that HAVE propofol infusion
        picked = []
        for r in cohort:
            cid = r["caseid"]
            if cid not in cases:
                continue
            try:
                av = set(available_tracks(cfg, cid))
            except Exception:
                continue
            if pkmod.PPF_RATE in av:
                picked.append(cid)
            if len(picked) >= 20:
                break
        print(f"picked {len(picked)} propofol cases: {picked}")

        feats = pkmod.extract(cfg, cases, picked)
        n_ppf = sum(1 for cid in picked if feats[cid].get("ppf_ce_auc") is not None)
        n_pump = sum(1 for cid in picked if feats[cid].get("ppf_ce_auc_pump") is not None)
        n_rftn = sum(1 for cid in picked if feats[cid].get("rftn_ce_auc") is not None)
        n_mac = sum(1 for cid in picked if feats[cid].get("mac_hours") is not None)
        print(f"coverage: Eleveld PPF Ce={n_ppf}/{len(picked)}  pump PPF Ce={n_pump}  "
              f"RFTN Ce={n_rftn}  MAC={n_mac}")

        # Spearman between Eleveld ppf_ce_auc and pump ppf_ce_auc_pump
        pairs = [(feats[cid]["ppf_ce_auc"], feats[cid]["ppf_ce_auc_pump"])
                 for cid in picked
                 if feats[cid].get("ppf_ce_auc") is not None
                 and feats[cid].get("ppf_ce_auc_pump") is not None]
        print(f"paired cases for correlation: {len(pairs)}")

        def _spearman(xy):
            n = len(xy)
            if n < 3:
                return None
            xs = [a for a, _ in xy]
            ys = [b for _, b in xy]

            def rank(vals):
                order = sorted(range(n), key=lambda i: vals[i])
                rk = [0.0] * n
                i = 0
                while i < n:
                    j = i
                    while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                        j += 1
                    avg = (i + j) / 2.0 + 1.0
                    for k in range(i, j + 1):
                        rk[order[k]] = avg
                    i = j + 1
                return rk

            rx, ry = rank(xs), rank(ys)
            mx = sum(rx) / n
            my = sum(ry) / n
            num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
            den = (sum((rx[i] - mx) ** 2 for i in range(n)) *
                   sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
            return num / den if den else None

        rho = _spearman(pairs)
        print(f"Spearman(Eleveld ppf_ce_auc, pump ppf_ce_auc_pump) = {rho}")
        sys.exit(0)

    unittest.main(verbosity=2)
