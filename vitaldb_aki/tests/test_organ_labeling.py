"""Tests for composite end-organ-damage labeling -- stdlib only, no network."""
from __future__ import annotations
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from vitaldb_aki.cohort.organ_labeling import label_organs

H = 3600.0
CFG = {
  "kdigo": {"abs_rise_mgdl":0.3,"abs_window_h":48,"rel_ratio":1.5,"rel_window_h":168},
  "organ_outcomes": {
    "postop_window_h":168,
    "ULN":{"ast":40.0,"alt":40.0,"tbil":1.2},
    "components":{
      "renal":{"enabled":True,"source":"kdigo"},
      "hepatocellular":{"enabled":True,"analytes":["ast","alt"],"rule":"peak_ge_mult_uln","mult_uln":3.0,"exclude_optypes":["Hepatic"]},
      "cholestatic":{"enabled":True,"analytes":["tbil"],"rule":"peak_ge_mult_uln","mult_uln":2.0,"exclude_optypes":["Hepatic"]},
      "coagulation_plt":{"enabled":True,"analytes":["plt"],"rule":"nadir_below_or_drop","nadir_below":100.0,"drop_frac_from_baseline":0.5,"exclude_if_massive_transfusion":True,"massive_ebl_ml":2000.0,"massive_rbc_ml":1000.0},
      "coagulation_inr":{"enabled":True,"analytes":["ptinr"],"rule":"rise_from_normal_baseline","threshold":1.5,"baseline_normal_max":1.3},
      "hypoperfusion":{"enabled":True,"analytes":["lac"],"rule":"peak_ge","threshold":4.0},
      "mortality":{"enabled":True,"source":"death_inhosp"},
    },
    "primary":"composite_any",
  },
}

def _renal(baseline=1.0, postop=None):
    return {"caseid":"c","baseline":baseline,"baseline_source":"preop_cr","postop_cr":postop or []}

class TestOrganLabeling(unittest.TestCase):
    def test_all_negative_composite_zero(self):
        ol = label_organs("c","General",{"ast":20,"alt":20,"tbil":0.8,"plt":250,"ptinr":1.0,"lac":1.0},
                          {"ast":[25],"alt":[25],"tbil":[1.0],"plt":[240],"ptinr":[1.1],"lac":[1.5]},
                          False, _renal(1.0,[(10*H,1.05)]), CFG)
        self.assertEqual(ol.composite, 0)
        self.assertEqual(ol.fired, [])

    def test_hepatocellular_fires(self):
        ol = label_organs("c","General",{"ast":20},{"ast":[200],"alt":[50]},False,_renal(1.0,[]),CFG)
        self.assertEqual(ol.components["hepatocellular"],1)   # 200 >= 3x40
        self.assertEqual(ol.composite,1)
        self.assertIn("hepatocellular",ol.fired)

    def test_hepatic_excluded_for_liver_surgery(self):
        ol = label_organs("c","Hepatic",{"ast":20},{"ast":[400],"alt":[400],"tbil":[5.0]},False,_renal(1.0,[]),CFG)
        self.assertIsNone(ol.components["hepatocellular"])   # excluded optype
        self.assertIsNone(ol.components["cholestatic"])

    def test_platelet_drop_and_nadir(self):
        ol1 = label_organs("c","General",{"plt":300},{"plt":[120,140]},False,_renal(1.0,[]),CFG)
        self.assertEqual(ol1.components["coagulation_plt"],1)  # 120 <= 0.5*300
        ol2 = label_organs("c","General",{"plt":160},{"plt":[90]},False,_renal(1.0,[]),CFG)
        self.assertEqual(ol2.components["coagulation_plt"],1)  # nadir<100

    def test_mortality_always_labelable(self):
        ol = label_organs("c","General",{},{}, True, _renal(1.0,[]), CFG)
        self.assertEqual(ol.components["mortality"],1)
        self.assertEqual(ol.composite,1)

    def test_renal_via_kdigo(self):
        ol = label_organs("c","General",{},{}, False, _renal(1.0,[(10*H,1.4)]), CFG)
        self.assertEqual(ol.components["renal"],1)            # +0.4 within 48h

    def test_unlabelable_when_no_data(self):
        ol = label_organs("c","General",{},{}, False, _renal(None,[]), CFG)
        # alive + no postop organ measured -> composite None (not a false 0)
        self.assertIsNone(ol.composite)

    def test_dead_with_no_labs_is_labelable_positive(self):
        ol = label_organs("c","General",{},{}, True, _renal(None,[]), CFG)
        self.assertEqual(ol.composite, 1)        # death is an observed outcome

    def test_missing_analyte_is_none_not_zero(self):
        ol = label_organs("c","General",{},{"ast":[]}, False, _renal(None,[]), CFG)
        self.assertIsNone(ol.components["hepatocellular"])

    # ---- confound control: INR de-confounded for anticoagulation ------------
    def test_inr_fires_on_rise_from_normal_baseline(self):
        ol = label_organs("c","General",{"ptinr":1.0},{"ptinr":[1.8]},False,_renal(None,[]),CFG)
        self.assertEqual(ol.components["coagulation_inr"],1)   # 1.0 (<1.3) -> 1.8 (>=1.5)

    def test_inr_not_labelable_when_anticoagulated(self):
        # elevated preop INR = likely warfarin/DOAC -> cannot attribute postop INR
        ol = label_organs("c","General",{"ptinr":1.6},{"ptinr":[2.2]},False,_renal(None,[]),CFG)
        self.assertIsNone(ol.components["coagulation_inr"])    # baseline >= 1.3 -> None

    def test_inr_not_labelable_without_preop_baseline(self):
        ol = label_organs("c","General",{},{"ptinr":[2.0]},False,_renal(None,[]),CFG)
        self.assertIsNone(ol.components["coagulation_inr"])    # no documented baseline

    def test_inr_normal_baseline_no_rise_is_zero(self):
        ol = label_organs("c","General",{"ptinr":1.1},{"ptinr":[1.3]},False,_renal(None,[]),CFG)
        self.assertEqual(ol.components["coagulation_inr"],0)   # normal base, no rise

    # ---- confound control: platelet de-confounded for dilution --------------
    def test_platelet_not_labelable_under_massive_transfusion(self):
        case = {"intraop_ebl":3000.0, "intraop_rbc":0.0}      # 3 L blood loss
        ol = label_organs("c","General",{"plt":300},{"plt":[80]},False,_renal(None,[]),CFG,case=case)
        self.assertIsNone(ol.components["coagulation_plt"])    # dilutional -> not injury

    def test_platelet_fires_when_transfusion_below_threshold(self):
        case = {"intraop_ebl":500.0, "intraop_rbc":0.0}       # modest loss
        ol = label_organs("c","General",{"plt":300},{"plt":[80]},False,_renal(None,[]),CFG,case=case)
        self.assertEqual(ol.components["coagulation_plt"],1)   # consumptive -> counts

if __name__ == "__main__":
    unittest.main(verbosity=2)
