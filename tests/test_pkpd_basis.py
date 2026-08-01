"""Check the one load-bearing claim in `bsde.pkpd.propofol`: that the exponential basis CONTAINS any
linear compartment model, so a fit over it needs no published parameter table.

The claim is what lets E122 proceed without access to Eleveld 2018's paywalled coefficients, so asserting
it is not enough (rule 23: self-written code plus self-written tests share blind spots; validate against an
INDEPENDENT implementation). The independent implementation here is a numerical ODE integration of a
three-compartment mammillary model with an effect site -- written from the differential equations, sharing
no code with `basis()`, which uses closed-form convolution.

The parameter values used are Marsh-like in magnitude but are NOT presented as Marsh's model and no result
depends on them: the test asks whether the basis can REPRODUCE an arbitrary compartment model, and that is
a property of the function space, not of the particular rate constants.
"""
import math
import unittest

try:
    import numpy as np
except ImportError:                                                     # pragma: no cover
    np = None


def _three_compartment_ce(dose_times_s, dose_mg, eval_times_s, k10, k12, k21, k13, k31, ke0, v1, dt=0.5):
    """Forward Euler on the mammillary ODEs. Deliberately naive and deliberately not the closed form.

    dA1/dt = -(k10+k12+k13) A1 + k21 A2 + k31 A3   (+ instantaneous bolus into A1)
    dA2/dt = k12 A1 - k21 A2
    dA3/dt = k13 A1 - k31 A3
    dCe/dt = ke0 (A1/v1 - Ce)
    """
    t_end = max(max(eval_times_s), max(dose_times_s)) + dt
    n = int(math.ceil(t_end / dt)) + 1
    a1 = a2 = a3 = ce = 0.0
    pending = sorted(zip(dose_times_s, dose_mg))
    p = 0
    grid_t, grid_ce = [], []
    for i in range(n):
        t = i * dt
        while p < len(pending) and pending[p][0] <= t:
            a1 += pending[p][1]
            p += 1
        c1 = a1 / v1
        da1 = -(k10 + k12 + k13) * a1 + k21 * a2 + k31 * a3
        da2 = k12 * a1 - k21 * a2
        da3 = k13 * a1 - k31 * a3
        dce = ke0 * (c1 - ce)
        a1, a2, a3, ce = a1 + da1 * dt, a2 + da2 * dt, a3 + da3 * dt, ce + dce * dt
        grid_t.append(t)
        grid_ce.append(ce)
    return np.interp(np.asarray(eval_times_s, float), np.asarray(grid_t), np.asarray(grid_ce))


@unittest.skipIf(np is None, "numpy not installed")
class TestBasisContainsCompartmentModels(unittest.TestCase):
    def setUp(self):
        from bsde.pkpd.propofol import basis
        self.basis = basis
        # A realistic DOSE-I dosing pattern: an induction bolus then intermittent top-ups over 20 min.
        self.dose_t = [30.0, 32.0, 180.0, 420.0, 610.0, 880.0, 1010.0, 1260.0]
        self.dose_mg = [40.0, 20.0, 20.0, 30.0, 20.0, 20.0, 10.0, 20.0]
        self.eval_t = list(range(60, 1500, 5))

    def _fit_r2(self, target, design):
        w, *_ = np.linalg.lstsq(np.hstack([design, np.ones((design.shape[0], 1))]), target, rcond=None)
        pred = np.hstack([design, np.ones((design.shape[0], 1))]) @ w
        ss_res = float(((target - pred) ** 2).sum())
        ss_tot = float(((target - target.mean()) ** 2).sum())
        return 1.0 - ss_res / ss_tot

    def test_basis_reproduces_a_three_compartment_effect_site(self):
        """The whole justification for not needing Eleveld's table."""
        ce = _three_compartment_ce(
            self.dose_t, self.dose_mg, self.eval_t,
            k10=0.119 / 60, k12=0.112 / 60, k21=0.055 / 60,
            k13=0.042 / 60, k31=0.0033 / 60, ke0=0.26 / 60, v1=0.228 * 70)
        design = self.basis(self.dose_t, self.dose_mg, self.eval_t)
        r2 = self._fit_r2(ce, design)
        self.assertGreater(r2, 0.999, f"basis failed to span a 3-compartment effect site (R2={r2:.6f})")

    def test_it_also_spans_a_quite_different_parameterisation(self):
        """A single parameterisation could be a coincidence; a fast-ke0, fast-redistribution model is a
        different point in the space and must be spanned too."""
        ce = _three_compartment_ce(
            self.dose_t, self.dose_mg, self.eval_t,
            k10=0.40 / 60, k12=0.60 / 60, k21=0.20 / 60,
            k13=0.010 / 60, k31=0.0010 / 60, ke0=1.20 / 60, v1=4.27)
        design = self.basis(self.dose_t, self.dose_mg, self.eval_t)
        r2 = self._fit_r2(ce, design)
        self.assertGreater(r2, 0.999, f"basis failed on the fast parameterisation (R2={r2:.6f})")

    def test_the_test_can_fail(self):
        """Rule 40: a check that cannot fail is not a check. A basis of ONE slow exponential must NOT be
        able to reproduce an effect-site curve with a fast equilibration peak."""
        ce = _three_compartment_ce(
            self.dose_t, self.dose_mg, self.eval_t,
            k10=0.40 / 60, k12=0.60 / 60, k21=0.20 / 60,
            k13=0.010 / 60, k31=0.0010 / 60, ke0=1.20 / 60, v1=4.27)
        design = self.basis(self.dose_t, self.dose_mg, self.eval_t, half_lives_min=(64.0,))
        r2 = self._fit_r2(ce, design)
        self.assertLess(r2, 0.95, f"a single 64 min exponential should NOT span this (R2={r2:.6f})")

    def test_no_look_ahead(self):
        """A dose in the future must contribute nothing. This is the only barrier against look-ahead in
        the whole module (rule 10)."""
        b = self.basis([1000.0], [100.0], [0.0, 500.0, 999.0, 1000.0, 1001.0, 1500.0])
        self.assertTrue(np.all(b[:3] == 0.0), "a future dose leaked backwards")
        self.assertGreater(b[3].sum(), 0.0, "the dose at its own instant did not register")
        self.assertGreater(b[5].sum(), 0.0)

    def test_allometry_moves_in_the_documented_direction(self):
        """A heavier patient must reach a LOWER concentration for the same dose (volume scales with
        weight), and their rates must be SLOWER (clearance scales sublinearly)."""
        light = self.basis(self.dose_t, self.dose_mg, self.eval_t, weight_kg=40.0, allometric=True)
        heavy = self.basis(self.dose_t, self.dose_mg, self.eval_t, weight_kg=140.0, allometric=True)
        self.assertGreater(light.max(), heavy.max(), "allometry did not lower the heavy patient's peak")
        # Slower rates -> a larger fraction of the peak remains at the end of the record.
        tail_light = light[-1].sum() / light.max()
        tail_heavy = heavy[-1].sum() / heavy.max()
        self.assertGreater(tail_heavy, tail_light, "allometry did not slow the heavy patient's decay")


@unittest.skipIf(np is None, "numpy not installed")
class TestInfusionBasis(unittest.TestCase):
    """The infusion kernel must agree with the bolus kernel in the limit, and must not front-load drug."""

    def test_short_infusion_converges_to_a_bolus_at_the_PREDICTED_rate(self):
        """A 100 mg dose delivered over a shrinking window must approach the instantaneous bolus, and it
        must do so at the rate the arithmetic predicts.

        THE TOLERANCE IS DERIVED, NOT CHOSEN (rule 63). An infusion over `[t0, t0+d]` is, to first order,
        a bolus delayed by `d/2`, so for kernel rate `L` the relative error is `L*d/2` -- and the binding
        kernel is the FASTEST one, `L = ln2 / 30 s`. A round-number threshold of 1e-3 was tried first and
        refused a correct implementation at d = 0.5 s, where the predicted error is 1.8e-3. What actually
        distinguishes a right closed form from a wrong one is that the error falls LINEARLY with `d`; a
        sign error or a missing factor would not.
        """
        from bsde.pkpd.propofol import basis, infusion_basis, HALF_LIVES_MIN, _rates_per_s
        ev = list(range(100, 2000, 10))
        bol = basis([50.0], [100.0], ev)
        scale = float(np.max(bol))
        errs = []
        for dur in (8.0, 4.0, 2.0, 1.0, 0.5):
            inf = infusion_basis([50.0], [50.0 + dur], [100.0 / dur], ev)
            errs.append(float(np.max(np.abs(inf - bol))) / scale)
        for a, b in zip(errs, errs[1:]):
            self.assertAlmostEqual(a / b, 2.0, delta=0.2,
                                   msg=f"error did not halve with duration: {errs}")
        lmax = max(_rates_per_s(HALF_LIVES_MIN))
        predicted = lmax * 0.5 / 2.0
        self.assertLess(errs[-1], 2.0 * predicted,
                        f"error {errs[-1]:.2e} exceeds twice the predicted {predicted:.2e}")

    def test_mass_is_conserved(self):
        """At the moment an infusion ends, the slowest kernel must hold essentially the whole dose --
        an infusion that lost or invented drug would show up here."""
        from bsde.pkpd.propofol import infusion_basis, HALF_LIVES_MIN
        slowest = (max(HALF_LIVES_MIN),)
        end = 600.0
        got = infusion_basis([0.0], [end], [200.0 / end], [end], half_lives_min=slowest)[0, 0]
        # Over 600 s the 64 min kernel decays by exp(-ln2*10/64); the delivered 200 mg must be recovered
        # to within that decay, not to within an order of magnitude.
        self.assertGreater(got, 180.0, f"infusion lost drug: {got:.1f} mg of 200")
        self.assertLess(got, 200.0, f"infusion invented drug: {got:.1f} mg of 200")

    def test_no_look_ahead(self):
        from bsde.pkpd.propofol import infusion_basis
        b = infusion_basis([1000.0], [1100.0], [1.0], [0.0, 500.0, 1000.0, 1050.0, 2000.0])
        self.assertTrue(np.all(b[:3] == 0.0), "a future infusion leaked backwards")
        self.assertGreater(b[3].sum(), 0.0)

    def test_merging_equal_rates_is_exactly_equivalent(self):
        """The merge is a performance fix and it must change NOTHING. A 1 Hz hold at a constant rate
        emits one segment per second; merging them is the same integral. Checked against an unmerged
        construction rather than asserted."""
        from bsde.pkpd.propofol import infusion_basis, rate_track_to_segments
        import numpy as _np
        t = list(range(0, 600))
        r = [0.0] * 30 + [600.0] * 200 + [300.0] * 200 + [0.0] * 170
        s0, s1, rate = rate_track_to_segments(t, r, t_end_s=600.0)
        self.assertLessEqual(s0.size, 4, f"equal rates were not merged: {s0.size} segments")
        # Unmerged: one segment per sample, same physical infusion.
        u0 = _np.asarray([x for x, y in zip(t, r) if y > 0], float)
        u1 = u0 + 1.0
        ur = _np.asarray([y for y in r if y > 0], float) * 20.0 / 3600.0
        ev = list(range(0, 600, 5))
        a = infusion_basis(s0, s1, rate, ev)
        b = infusion_basis(u0, u1, ur, ev)
        self.assertLess(float(_np.max(_np.abs(a - b))) / float(_np.max(b)), 1e-12,
                        "merging equal-rate segments changed the concentration")

    def test_zero_order_hold_not_linear_interpolation(self):
        """A rate track is a HOLD. A segment must span from its own sample to the NEXT one."""
        from bsde.pkpd.propofol import rate_track_to_segments
        s0, s1, r = rate_track_to_segments([0.0, 60.0, 120.0], [600.0, 0.0, 300.0], t_end_s=180.0)
        self.assertEqual(list(s0), [0.0, 120.0], "a zero-rate segment was kept, or a hold was split")
        self.assertEqual(list(s1), [60.0, 180.0])
        # 600 mL/h of 20 mg/mL = 12000 mg/h = 3.3333 mg/s
        self.assertAlmostEqual(r[0], 600.0 * 20.0 / 3600.0, places=9)


if __name__ == "__main__":
    unittest.main()
