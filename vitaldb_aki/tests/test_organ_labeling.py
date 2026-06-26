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
      "coagulation_plt":{"enabled":True,"analytes":["plt"],"rule":"nadir_below_or_drop","nadir_below":100.0,"drop_frac_from_baseline":0.5},
      "coagulation_inr":{"enabled":True,"analytes":["ptinr"],"rule":"peak_ge","threshold":1.5},
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
