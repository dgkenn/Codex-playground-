"""Check that `bsde.pkpd.interaction` reproduces every statement Hannivoort's abstract actually makes.

The equation is an INFERENCE from the abstract (the paper is paywalled), so the tests are written against
the source's own quoted claims rather than against the implementation's internals. If the inference is
wrong, one of these fails.

Quoted (PMID 27106965): "Sevoflurane and propofol interact additively, whereas remifentanil interacts in a
strongly synergistic manner. The effect-site concentrations of sevoflurane and propofol at a PTOL of 50%
(Ce50; se) were 2.59 (0.13) vol % and 7.58 (0.49) ug ml(-1). A CeREMI of 1.36 (0.15) ng ml(-1) reduced the
Ce50 of sevoflurane and propofol by 50%. The common slope factor was 5.22 (0.52)."
"""
import unittest

try:
    import numpy as np
except ImportError:                                                      # pragma: no cover
    np = None


@unittest.skipIf(np is None, "numpy not installed")
class TestHannivoortStatements(unittest.TestCase):
    def setUp(self):
        from bsde.pkpd import interaction as I
        self.I = I

    # ---- the two quoted Ce50 values ---------------------------------------------------------------
    def test_sevoflurane_alone_reaches_ptol_50_at_2_59_vol_pct(self):
        self.assertAlmostEqual(float(self.I.ptol(ce_sevo=2.59)), 0.5, places=9)

    def test_propofol_alone_reaches_ptol_50_at_7_58_ug_ml(self):
        self.assertAlmostEqual(float(self.I.ptol(ce_prop=7.58)), 0.5, places=9)

    # ---- "interact additively" ---------------------------------------------------------------------
    def test_sevoflurane_and_propofol_are_additive(self):
        """Half of each Ce50 must reach PTOL 50 exactly. Additivity has no free parameter, so this is a
        hard equality rather than a tolerance."""
        self.assertAlmostEqual(float(self.I.ptol(ce_sevo=2.59 / 2, ce_prop=7.58 / 2)), 0.5, places=9)
        for f in (0.25, 0.4, 0.75):
            self.assertAlmostEqual(
                float(self.I.ptol(ce_sevo=2.59 * f, ce_prop=7.58 * (1 - f))), 0.5, places=9,
                msg=f"additivity fails at sevo fraction {f}")

    # ---- "a CeREMI of 1.36 reduced the Ce50 of sevoflurane and propofol by 50%" ----------------------
    def test_remifentanil_at_1_36_halves_both_ce50s(self):
        self.assertAlmostEqual(float(self.I.ptol(ce_sevo=2.59 / 2, ce_remi=1.36)), 0.5, places=9)
        self.assertAlmostEqual(float(self.I.ptol(ce_prop=7.58 / 2, ce_remi=1.36)), 0.5, places=9)

    def test_the_halving_is_specific_to_1_36(self):
        """Rule 40: a check that cannot fail is not a check. At a different opioid concentration the
        halving must NOT hold, or the test above is passing on an identity."""
        self.assertNotAlmostEqual(float(self.I.ptol(ce_prop=7.58 / 2, ce_remi=2.72)), 0.5, places=3)
        self.assertNotAlmostEqual(float(self.I.ptol(ce_prop=7.58 / 2, ce_remi=0.0)), 0.5, places=3)

    # ---- "strongly synergistic", and Bouillon's independent observation ------------------------------
    def test_remifentanil_alone_does_nothing(self):
        """Bouillon 2004 (PMID 15166553) measured this directly: 'Remifentanil alone had no appreciable
        effect on response to shaking and shouting or response to laryngoscopy.' A model in which the
        opioid entered ADDITIVELY would fail here, which is why the form is multiplicative."""
        for c in (0.5, 1.36, 5.0, 50.0):
            self.assertAlmostEqual(float(self.I.ptol(ce_remi=c)), 0.0, places=12,
                                   msg=f"remifentanil alone produced an effect at {c} ng/ml")

    def test_synergy_is_supra_additive_not_merely_additive(self):
        """'Strongly synergistic' has to mean more than the sum of parts. Compare the real combination
        against a hypothetical in which the opioid contributed its own additive units on the same
        normalised scale."""
        u_real = float(self.I.potency_units(ce_prop=7.58 / 2, ce_remi=1.36))
        u_additive_opioid = 0.5 + 1.0          # half the hypnotic plus one opioid Ce50-equivalent
        self.assertGreater(u_real, 0.99)       # the real combination reaches the PTOL-50 surface
        self.assertLess(u_real, u_additive_opioid)
        # ... and doubling the hypnotic in the presence of opioid must beat doubling the opioid alone,
        # since the opioid multiplies whatever hypnotic is present.
        self.assertGreater(float(self.I.potency_units(ce_prop=7.58, ce_remi=1.36)),
                           float(self.I.potency_units(ce_prop=7.58 / 2, ce_remi=2.72)))

    # ---- the slope, and the claim that rank statistics do not depend on it --------------------------
    def test_ptol_is_strictly_increasing_in_potency_units(self):
        """The module claims every rank-based statistic is invariant to the slope factor. That claim is
        only true if PTOL is a strictly increasing function of U, so it is checked rather than asserted."""
        u = np.linspace(0.01, 4.0, 400)
        for slope in (2.0, 5.22, 9.0):
            p = self.I.ptol(ce_prop=u * 7.58, slope=slope)
            self.assertTrue(np.all(np.diff(p) > 0), f"PTOL not strictly increasing at slope {slope}")
        # The ORDERING must be identical across slopes -- that is the invariance being relied on.
        a = np.argsort(self.I.ptol(ce_prop=u * 7.58, slope=2.0))
        b = np.argsort(self.I.ptol(ce_prop=u * 7.58, slope=9.0))
        self.assertTrue(np.array_equal(a, b), "the slope factor changed the ordering")

    def test_slope_5_22_at_twice_the_ce50(self):
        """A direct read of the quoted slope: at U = 2, PTOL = 2^5.22 / (1 + 2^5.22)."""
        want = 2.0 ** 5.22 / (1.0 + 2.0 ** 5.22)
        self.assertAlmostEqual(float(self.I.ptol(ce_prop=2 * 7.58)), want, places=12)

    # ---- defensive behaviour ------------------------------------------------------------------------
    def test_vectorised_and_nan_safe(self):
        out = self.I.ptol(ce_prop=np.array([0.0, 7.58, np.nan, -1.0, 1e9]))
        self.assertEqual(out.shape, (5,))
        self.assertTrue(np.all(np.isfinite(out)))
        self.assertAlmostEqual(float(out[1]), 0.5, places=9)
        self.assertAlmostEqual(float(out[0]), 0.0, places=12)
        self.assertAlmostEqual(float(out[2]), 0.0, places=12)    # NaN treated as absent, not propagated
        self.assertAlmostEqual(float(out[4]), 1.0, places=12)

    def test_mac_conversion_refuses_rather_than_guessing(self):
        with self.assertRaises(NotImplementedError):
            self.I.mac_to_vol_pct_sevo(1.0, age_years=40)


if __name__ == "__main__":
    unittest.main()
