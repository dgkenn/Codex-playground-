"""Physiology tests. Every formula is checked against a published worked example or table value.

The point of this file is that a wrong constant in ``physiology.py`` misprescribes every workout
downstream and would be invisible without these.
"""

from __future__ import annotations

import math

import pytest

from marathon_engine.physiology import (
    DECOUPLING_OK, RIEGEL_EXPONENT, RIEGEL_NOVICE_EXPONENT, decoupling, efficiency_factor,
    fmt_pace, five_zone_model, grade_adjusted_pace, grade_adjusted_pace_factor,
    heat_pace_factor, hr_at_reserve_fraction, hr_max_estimate, minetti_cost, parse_pace,
    pace_to_speed, pct_vo2max_for_duration, reserve_fraction_at_hr, riegel_predict,
    seiler_three_zone, speed_to_pace, training_paces, vdot_from_hr_pace, vdot_from_race,
    velocity_at_vo2, vo2_at_velocity, wbgt_estimate, zone_for_hr,
)


# ---- units -------------------------------------------------------------------------------

def test_pace_speed_roundtrip():
    for pace in (240.0, 300.0, 360.0, 420.0):
        assert speed_to_pace(pace_to_speed(pace)) == pytest.approx(pace)


def test_fmt_and_parse_pace():
    assert fmt_pace(330) == "5:30"
    assert fmt_pace(305) == "5:05"
    assert parse_pace("5:30") == 330.0
    # 8:00/mile is 4:58/km.
    assert parse_pace("8:00", per_mile=True) == pytest.approx(298.3, abs=0.5)
    assert fmt_pace(298.3, per_mile=True) == "8:00"


def test_pace_rejects_nonpositive():
    with pytest.raises(ValueError):
        pace_to_speed(0)
    with pytest.raises(ValueError):
        speed_to_pace(-1)


# ---- heart rate --------------------------------------------------------------------------

def test_tanaka_hrmax_at_30():
    # 208 - 0.7*30 = 187
    assert hr_max_estimate(30) == pytest.approx(187.0)


def test_hrmax_formula_variants_differ_as_published():
    assert hr_max_estimate(40, formula="tanaka") == pytest.approx(180.0)
    assert hr_max_estimate(40, formula="gellish") == pytest.approx(179.0)
    assert hr_max_estimate(40, formula="fox") == pytest.approx(180.0)
    # Fox over-predicts the young relative to Tanaka -- the documented failure mode.
    assert hr_max_estimate(20, formula="fox") > hr_max_estimate(20, formula="tanaka")


def test_hrmax_rejects_absurd_age():
    with pytest.raises(ValueError):
        hr_max_estimate(0)
    with pytest.raises(ValueError):
        hr_max_estimate(200)


def test_karvonen_roundtrip():
    hr = hr_at_reserve_fraction(0.70, 187, 55)
    assert hr == pytest.approx(55 + 0.70 * 132)
    assert reserve_fraction_at_hr(hr, 187, 55) == pytest.approx(0.70)


def test_karvonen_rejects_inverted_anchors():
    with pytest.raises(ValueError):
        hr_at_reserve_fraction(0.5, 100, 120)


def test_five_zones_are_ordered_and_contiguous():
    m = five_zone_model(187, 55)
    assert [z.index for z in m.zones] == [1, 2, 3, 4, 5]
    for a, b in zip(m.zones, m.zones[1:]):
        assert a.high_bpm == b.low_bpm, "zones must be contiguous or HR can fall in no zone"


def test_lthr_pins_the_z3_z4_boundary():
    """A measured threshold must override the population %HRR guess -- this is the whole point."""
    m = five_zone_model(187, 55, lthr=158)
    assert m.zones[2].high_bpm == 158
    assert m.zones[3].low_bpm == 158
    # And zones stay contiguous after pinning.
    for a, b in zip(m.zones, m.zones[1:]):
        assert a.high_bpm == b.low_bpm


def test_zone_for_hr_clamps_outside_range():
    m = five_zone_model(187, 55)
    assert zone_for_hr(40, m).index == 1
    assert zone_for_hr(250, m).index == 5


def test_seiler_three_zone_uses_lthr_as_lt2():
    m = seiler_three_zone(187, 55, lthr=160)
    assert m.zones[1].high_bpm == 160
    assert m.zones[2].low_bpm == 160


# ---- VDOT --------------------------------------------------------------------------------

def test_gilbert_vo2_velocity_roundtrip():
    for v in (150.0, 200.0, 250.0, 300.0):
        assert velocity_at_vo2(vo2_at_velocity(v)) == pytest.approx(v, abs=1e-6)


def test_pct_vo2max_curve_shape():
    """Shorter races are run at a higher fraction of VO2max; the curve exceeds 1.0 when short."""
    assert pct_vo2max_for_duration(2) > 1.0
    assert pct_vo2max_for_duration(30) > pct_vo2max_for_duration(60)
    assert pct_vo2max_for_duration(180) < 0.85


def test_vdot_from_known_daniels_equivalents():
    """Daniels' table: a 5K in 19:57 is VDOT 50; 3:00 marathon is about VDOT 53-54."""
    assert vdot_from_race(5000, 19 * 60 + 57) == pytest.approx(50.0, abs=0.5)
    assert vdot_from_race(42195, 3 * 3600) == pytest.approx(53.5, abs=1.0)


def test_vdot_rises_with_performance():
    assert vdot_from_race(5000, 20 * 60) > vdot_from_race(5000, 25 * 60)


def test_training_paces_reproduce_daniels_table_vdot50():
    """The calibration that matters. Daniels VDOT 50 prints E 5:35-6:04, M 4:41, T 4:15, I 3:57 /km.

    If this test fails, every prescribed pace in the app is wrong -- which is exactly why the
    percentages in ``_PACE_FAMILIES`` are fitted to the printed tables rather than copied from
    Daniels' prose description of the intensity bands.
    """
    p = training_paces(50.0)
    assert fmt_pace(p.marathon) == "4:41"
    assert p.threshold == pytest.approx(255, abs=3)      # 4:15 = 255 s
    assert p.interval == pytest.approx(237, abs=4)       # 3:57 = 237 s
    # Easy band brackets Daniels' printed 5:35-6:04.
    fast, slow = p.easy_range
    assert 330 <= fast <= 345, f"easy fast end {fmt_pace(fast)} should be near 5:35"
    assert 358 <= slow <= 372, f"easy slow end {fmt_pace(slow)} should be near 6:04"


def test_easy_pace_is_never_faster_than_marathon_pace():
    """Regression guard for the prose-vs-table bug: taking Daniels' '59-74% VO2max' literally made
    the fast end of Easy faster than marathon pace, i.e. the app would prescribe a tempo run every
    time it said 'easy'."""
    for vdot in (28, 35, 42, 50, 60):
        p = training_paces(vdot)
        assert p.easy_range[0] > p.marathon, f"VDOT {vdot}: easy fast end overlaps marathon pace"
        assert p.easy > p.marathon > p.threshold > p.interval > p.repetition


def test_prescribed_easy_sits_in_the_slow_half_of_the_band():
    p = training_paces(40.0)
    midpoint = (p.easy_range[0] + p.easy_range[1]) / 2.0
    assert p.easy >= midpoint, "easy should be prescribed at or slower than the band midpoint"


def test_training_paces_rejects_nonpositive_vdot():
    with pytest.raises(ValueError):
        training_paces(0)


def test_vdot_from_hr_pace_rejects_out_of_band_hr():
    with pytest.raises(ValueError):
        vdot_from_hr_pace(hr=100, pace_sec_km=400, hr_max=187, hr_rest=55)   # ~34% HRR


def test_vdot_from_hr_pace_is_plausible_in_band():
    v = vdot_from_hr_pace(hr=150, pace_sec_km=330, hr_max=187, hr_rest=55)
    assert 30 < v < 80


# ---- prediction --------------------------------------------------------------------------

def test_riegel_doubling_uses_the_exponent():
    t = riegel_predict(5000, 25 * 60, 10000)
    assert t == pytest.approx(25 * 60 * 2 ** RIEGEL_EXPONENT)


def test_novice_exponent_predicts_slower_marathon():
    trained = riegel_predict(5000, 25 * 60, 42195, exponent=RIEGEL_EXPONENT)
    novice = riegel_predict(5000, 25 * 60, 42195, exponent=RIEGEL_NOVICE_EXPONENT)
    assert novice > trained
    # The gap should be large -- tens of minutes -- or the adjustment is pointless.
    assert novice - trained > 20 * 60


# ---- terrain and environment -------------------------------------------------------------

def test_minetti_flat_cost_matches_published_constant():
    assert minetti_cost(0.0) == pytest.approx(3.6)


def test_minetti_minimum_is_downhill_not_flat():
    """Minetti's key finding: gentle downhill running is cheaper than flat."""
    costs = {g: minetti_cost(g) for g in (-0.25, -0.20, -0.15, -0.10, -0.05, 0.0)}
    best = min(costs, key=lambda g: costs[g])
    assert -0.20 <= best <= -0.05
    assert costs[best] < minetti_cost(0.0)


def test_minetti_uphill_costs_more_and_is_clamped():
    assert minetti_cost(0.10) > minetti_cost(0.05) > minetti_cost(0.0)
    # Outside the validated range the polynomial is clamped, not extrapolated.
    assert minetti_cost(0.9) == minetti_cost(0.45)
    assert minetti_cost(-0.9) == minetti_cost(-0.45)


def test_grade_adjusted_pace_makes_uphill_equivalent_faster():
    # 6:00/km up a 5% grade is worth appreciably faster on the flat.
    gap = grade_adjusted_pace(360.0, 0.05)
    assert gap < 360.0
    assert grade_adjusted_pace_factor(0.05) == pytest.approx(minetti_cost(0.05) / 3.6)


def test_grade_adjusted_pace_penalises_downhill_equivalent():
    assert grade_adjusted_pace(360.0, -0.05) > 360.0


def test_heat_factor_is_monotonic_and_capped():
    assert heat_pace_factor(5) == 1.0
    assert heat_pace_factor(10) == 1.0
    vals = [heat_pace_factor(t) for t in range(10, 40)]
    assert all(b >= a for a, b in zip(vals, vals[1:])), "must be non-decreasing in WBGT"
    assert max(vals) <= 1.20


def test_wbgt_rises_with_temp_and_humidity():
    assert wbgt_estimate(30, 70) > wbgt_estimate(20, 70)
    assert wbgt_estimate(25, 90) > wbgt_estimate(25, 40)
    assert wbgt_estimate(25, 70, solar=True) > wbgt_estimate(25, 70, solar=False)


# ---- within-run analysis ------------------------------------------------------------------

def test_efficiency_factor_rises_with_speed_at_fixed_hr():
    assert efficiency_factor(3.0, 150) > efficiency_factor(2.5, 150)


def test_decoupling_zero_when_ef_constant():
    first = [(3.0, 150.0)] * 10
    second = [(3.0, 150.0)] * 10
    assert decoupling(first, second) == pytest.approx(0.0)


def test_decoupling_positive_when_hr_drifts_up():
    """The canonical case: same pace, higher HR in the second half."""
    first = [(3.0, 150.0)] * 10
    second = [(3.0, 160.0)] * 10
    d = decoupling(first, second)
    assert d > 0
    assert d == pytest.approx(160 / 150 - 1, abs=1e-6)


def test_decoupling_positive_when_pace_falls_at_same_hr():
    first = [(3.0, 150.0)] * 10
    second = [(2.8, 150.0)] * 10
    assert decoupling(first, second) > 0


def test_decoupling_threshold_constant_is_five_percent():
    assert DECOUPLING_OK == 0.05


def test_decoupling_ignores_invalid_samples():
    first = [(3.0, 150.0), (0.0, 150.0), (3.0, 0.0)]
    second = [(3.0, 150.0)]
    assert decoupling(first, second) == pytest.approx(0.0)


def test_decoupling_raises_when_a_half_is_all_invalid():
    with pytest.raises(ValueError):
        decoupling([(0.0, 0.0)], [(3.0, 150.0)])
