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
        # new bolus/infusion decomposition features (Sec 7E/8)
        for nm in ("ppf_infused_mg", "ppf_bolus_mg", "ppf_bolus_frac",
                   "ppf_admin_mode", "phe_infused_ug", "phe_bolus_ug",
                   "phe_bolus_frac", "eph_bolus_mg"):
            self.assertIn(nm, names)


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


class TestBolusDecomposition(unittest.TestCase):
    def test_bolus_equals_total_minus_infused(self):
        # total 200 mg, infused 120 mg -> bolus 80 mg, frac 0.4, mode 3 (both).
        d = pk.decompose_dose(total=200.0, infused=120.0)
        self.assertAlmostEqual(d["bolus"], 80.0, places=4)
        self.assertAlmostEqual(d["bolus_frac"], 0.4, places=4)
        self.assertEqual(d["admin_mode"], 3)

    def test_clamp_at_zero_when_infused_exceeds_total(self):
        # rounding: pump VOL x conc slightly exceeds charted total -> clamp to 0.
        d = pk.decompose_dose(total=100.0, infused=100.5)
        self.assertEqual(d["bolus"], 0.0)
        self.assertEqual(d["bolus_frac"], 0.0)
        self.assertEqual(d["admin_mode"], 2)  # infusion-only

    def test_bolus_only_mode(self):
        # ephedrine-like: total present, no infusion track (infused None).
        d = pk.decompose_dose(total=10.0, infused=None)
        self.assertAlmostEqual(d["bolus"], 10.0, places=4)
        self.assertAlmostEqual(d["bolus_frac"], 1.0, places=4)
        self.assertEqual(d["admin_mode"], 1)  # bolus-only

    def test_infusion_only_mode(self):
        # total fully explained by infusion -> bolus 0, mode 2.
        d = pk.decompose_dose(total=120.0, infused=120.0)
        self.assertEqual(d["bolus"], 0.0)
        self.assertEqual(d["admin_mode"], 2)

    def test_none_total_and_zero_dose(self):
        # missing total -> bolus/frac/mode None
        d = pk.decompose_dose(total=None, infused=50.0)
        self.assertIsNone(d["bolus"])
        self.assertIsNone(d["admin_mode"])
        # zero total, zero infused -> mode 0 (none)
        d0 = pk.decompose_dose(total=0.0, infused=0.0)
        self.assertEqual(d0["admin_mode"], 0)
        self.assertEqual(d0["bolus"], 0.0)

    def test_infused_amount_from_vol_window_bounded(self):
        # cumulative VOL 0 -> 5 mL, conc 20 mg/mL -> 100 mg infused; samples past
        # t1 must NOT contribute (Sec 11 leakage).
        vol = [(0.0, 0.0), (300.0, 2.5), (600.0, 5.0), (900.0, 9.0)]
        amt_in = pk.infused_amount(vol, conc_per_ml=20.0, t0=0.0, t1=600.0)
        self.assertAlmostEqual(amt_in, 100.0, places=3)
        amt_all = pk.infused_amount(vol, conc_per_ml=20.0, t0=0.0, t1=900.0)
        self.assertAlmostEqual(amt_all, 180.0, places=3)
        self.assertLess(amt_in, amt_all)

    def test_infused_amount_absent_vol_is_none(self):
        # no VOL track -> cannot attribute infusion -> None (not 0).
        self.assertIsNone(pk.infused_amount([], conc_per_ml=20.0, t0=0.0, t1=600.0))
        # single sample -> 0.0 (present but no delta)
        self.assertEqual(pk.infused_amount([(0.0, 3.0)], 20.0, 0.0, 600.0), 0.0)


class TestEleveldBolus(unittest.TestCase):
    def test_bolus_raises_early_peak_vs_no_bolus(self):
        # same infusion, with vs without an induction bolus: the bolus must raise
        # the effect-site peak (it injects drug the infusion-only path misses).
        mg_s, times = _const_infusion(20.0, 20 * 60)  # gentle 20 mg/min infusion
        ce_no = pk.eleveld_ce(mg_s, times, **REF)
        ce_bo = pk.eleveld_ce(mg_s, times, bolus_mg=140.0, bolus_index=0, **REF)
        self.assertGreater(max(ce_bo), max(ce_no))
        # and the early Ce (first 2 min) is clearly higher with the bolus.
        self.assertGreater(ce_bo[120], ce_no[120] + 0.5)

    def test_bolus_peaks_higher_than_same_dose_slow_infusion(self):
        # 100 mg as an instantaneous bolus vs the SAME 100 mg given as a slow
        # 10-min infusion -> bolus reaches a higher Ce peak (concentrated input).
        secs = 30 * 60
        # bolus: 100 mg at induction, nothing else
        ce_bolus = pk.eleveld_ce([0.0] * secs, [float(i) for i in range(secs + 1)],
                                 bolus_mg=100.0, bolus_index=0, **REF)
        # slow infusion: 100 mg spread over 10 min == 10 mg/min, then observe
        slow = [10.0 / 60.0] * (10 * 60) + [0.0] * (20 * 60)
        ce_slow = pk.eleveld_ce(slow, [float(i) for i in range(len(slow) + 1)], **REF)
        self.assertGreater(max(ce_bolus), max(ce_slow))

    def test_zero_bolus_is_noop(self):
        # bolus_mg=0 must reproduce the legacy infusion-only result exactly.
        mg_s, times = _const_infusion(120.0, 10 * 60)
        ce_legacy = pk.eleveld_ce(mg_s, times, **REF)
        ce_zero = pk.eleveld_ce(mg_s, times, bolus_mg=0.0, **REF)
        self.assertEqual(ce_legacy, ce_zero)

    def test_bolus_index_clamped(self):
        # an out-of-range bolus_index must not crash and still inject the dose.
        mg_s = [0.0] * 60
        times = [float(i) for i in range(61)]
        ce = pk.eleveld_ce(mg_s, times, bolus_mg=100.0, bolus_index=10_000, **REF)
        self.assertGreater(max(ce), 0.0)


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
