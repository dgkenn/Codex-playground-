"""Safety-module tests: screening logic, bone loading, hydration, and return-to-run.

These cover the paths where being wrong causes actual harm rather than a suboptimal training week,
so the emphasis is on the *refusals*: symptoms must block training, known disease must require
clearance, and the hydration guidance must never encourage drinking to a schedule.
"""

from __future__ import annotations

import pytest

from marathon_engine.safety import (
    BONE_LOAD_SPIKE_RATIO, MEDICATION_WARNINGS, NEW_RUNNER_BONE_WINDOW_WEEKS, RED_FLAG_SYMPTOMS,
    SUPPLEMENT_CHECKS, ScreeningAnswers, bone_load, hydration_plan, return_to_run,
    screen_participant, single_run_progression,
)


# ---- screening -----------------------------------------------------------------------------

def test_healthy_adult_is_cleared():
    r = screen_participant(ScreeningAnswers(currently_exercising_regularly=True))
    assert r.clearance == "proceed"
    assert r.can_start_training and r.can_do_maximal_test


def test_exertional_chest_pain_blocks_everything():
    r = screen_participant(ScreeningAnswers(symptoms_chest_discomfort=True))
    assert r.clearance == "urgent_review"
    assert not r.can_start_training
    assert not r.can_do_maximal_test


@pytest.mark.parametrize("field", [
    "symptoms_chest_discomfort", "symptoms_dyspnoea_unusual", "symptoms_dizziness_syncope",
    "symptoms_palpitations", "symptoms_ankle_oedema", "symptoms_claudication",
])
def test_any_cardiovascular_symptom_blocks_training(field):
    r = screen_participant(ScreeningAnswers(**{field: True}))
    assert not r.can_start_training, f"{field} must block training"
    assert r.clearance == "urgent_review"


@pytest.mark.parametrize("field", [
    "known_cardiovascular_disease", "known_metabolic_disease", "known_renal_disease",
])
def test_known_disease_requires_clearance(field):
    r = screen_participant(ScreeningAnswers(**{field: True}))
    assert r.clearance == "medical_clearance_first"
    assert not r.can_start_training


def test_clearance_advises_that_light_activity_is_still_encouraged():
    """Screening must not read as 'do not exercise' -- that would be worse advice than the risk."""
    r = screen_participant(ScreeningAnswers(known_metabolic_disease=True))
    assert any("encouraged" in a.lower() for a in r.advisories)


def test_beta_blocker_advisory_warns_zones_are_invalid():
    r = screen_participant(ScreeningAnswers(currently_exercising_regularly=True,
                                            on_beta_blocker=True))
    text = " ".join(r.advisories).lower()
    assert "beta" in text and ("zone" in text or "heart rate" in text)


def test_family_history_advisory_present_without_blocking():
    r = screen_participant(ScreeningAnswers(currently_exercising_regularly=True,
                                            family_history_sudden_death_under_50=True))
    assert r.can_start_training
    assert any("sudden death" in a.lower() for a in r.advisories)


def test_existing_pain_is_flagged():
    r = screen_participant(ScreeningAnswers(currently_exercising_regularly=True,
                                            current_musculoskeletal_pain=True))
    assert any("assessed" in a.lower() for a in r.advisories)


def test_risk_is_contextualised_not_catastrophised():
    """The absolute risk figure must appear, and must be framed as low."""
    r = screen_participant(ScreeningAnswers(currently_exercising_regularly=True))
    text = " ".join(r.advisories)
    assert "184,000" in text
    assert "low" in text.lower()


def test_unknown_activity_history_is_noted_not_assumed():
    r = screen_participant(ScreeningAnswers())
    assert any("conservativ" in a.lower() for a in r.advisories)


def test_red_flag_list_covers_the_serious_presentations():
    for key in ("chest_pain", "dizziness", "focal_bone_pain", "calf_swelling", "confusion"):
        assert key in RED_FLAG_SYMPTOMS
        assert RED_FLAG_SYMPTOMS[key]
    # Hyponatraemia and heat illness present together late in a long effort.
    assert "hyponatraemia" in RED_FLAG_SYMPTOMS["confusion"].lower()


# ---- bone loading --------------------------------------------------------------------------

def test_new_runner_is_in_the_high_risk_window():
    s = bone_load([10.0] * 4)
    assert s.in_high_risk_window
    assert s.band == "building"
    assert any("bone" in g.lower() for g in s.guidance)


def test_bone_guidance_explains_the_blind_spot():
    """The point of this module: HRV and load metrics cannot see bone."""
    s = bone_load([15.0] * 6)
    text = " ".join(s.guidance).lower()
    assert "hrv" in text or "heart" in text
    assert "month" in text or "week" in text


def test_established_runner_leaves_the_window():
    s = bone_load([30.0] * (NEW_RUNNER_BONE_WINDOW_WEEKS + 5))
    assert not s.in_high_risk_window
    assert s.band == "established"


def test_consolidating_band_between():
    s = bone_load([20.0] * 12)
    assert s.band == "consolidating"


def test_cumulative_km_accumulates():
    s = bone_load([10.0, 20.0, 30.0])
    assert s.cumulative_impact_km == pytest.approx(60.0)


def test_zero_weeks_do_not_count_as_running():
    s = bone_load([0.0, 0.0, 10.0])
    assert s.weeks_running == 1


# ---- single-run progression ------------------------------------------------------------------

def test_no_history_returns_ok_with_a_caution():
    band, ratio, msg = single_run_progression(15.0, None)
    assert band == "ok"
    assert "nothing to compare" in msg.lower()


def test_run_no_longer_than_recent_longest_is_ok():
    band, ratio, msg = single_run_progression(10.0, 12.0)
    assert band == "ok"
    assert ratio < 1.0


def test_modest_progression_is_ok_but_says_there_is_no_safe_threshold():
    """The RUNSAFE authors' actual conclusion, which the naive reading inverts."""
    band, ratio, msg = single_run_progression(10.5, 10.0)
    assert band == "ok"
    assert "no magic safe percentage" in msg.lower() or "no safe" in msg.lower()


def test_moderate_jump_is_caution():
    band, ratio, msg = single_run_progression(12.0, 10.0)
    assert band == "caution"
    assert ratio == pytest.approx(1.20)


def test_large_jump_is_high_and_recommends_splitting():
    band, ratio, msg = single_run_progression(20.0, 10.0)
    assert band == "high"
    assert "split" in msg.lower()


def test_spike_ratio_constant_is_not_presented_as_safe():
    """Documented as a flag, not a safe/unsafe boundary."""
    assert BONE_LOAD_SPIKE_RATIO == pytest.approx(1.10)
    band, _, _ = single_run_progression(10.09, 10.0)
    assert band == "ok"


# ---- hydration -----------------------------------------------------------------------------

def test_primary_rule_is_drink_to_thirst():
    p = hydration_plan(180)
    assert "thirst" in str(p["primary_rule"]).lower()


def test_hydration_explicitly_forbids_scheduled_drinking():
    p = hydration_plan(180)
    donts = " ".join(p["do_not"]).lower()
    assert "schedule" in donts
    assert "millilitres-per-hour" in donts or "fixed" in donts


def test_nsaids_are_forbidden_during_long_efforts():
    p = hydration_plan(180)
    assert any("nsaid" in d.lower() for d in p["do_not"])


def test_weight_gain_is_listed_as_the_warning_sign():
    """The clearest and most actionable hyponatraemia marker."""
    p = hydration_plan(180)
    signs = " ".join(p["warning_signs"]).lower()
    assert "gain" in signs


def test_long_efforts_get_sodium_guidance():
    p = hydration_plan(200)
    notes = " ".join(p["notes"]).lower()
    assert "sodium" in notes
    assert "hyponatraemia" in notes or "plain water" in notes


def test_short_run_does_not_get_sodium_lecture():
    p = hydration_plan(45)
    assert not any("sodium" in n.lower() for n in p["notes"])


def test_heat_adds_guidance():
    p = hydration_plan(120, wbgt_c=28)
    assert any("wbgt" in n.lower() or "heat" in n.lower() for n in p["notes"])


def test_cold_notes_thirst_suppression():
    p = hydration_plan(120, wbgt_c=2)
    assert any("cold" in n.lower() for n in p["notes"])


def test_caffeine_dose_scales_with_body_mass():
    p = hydration_plan(180, body_mass_kg=80)
    note = " ".join(p["notes"])
    assert "240" in note and "480" in note      # 3–6 mg/kg of 80 kg


def test_medication_warnings_cover_nsaids_with_the_mechanism():
    w = MEDICATION_WARNINGS["nsaids"].lower()
    assert "hyponatraemia" in w
    assert "kidney" in w


def test_supplement_checks_include_energy_availability():
    items = {s["item"] for s in SUPPLEMENT_CHECKS}
    assert "ferritin" in items and "vitamin D" in items and "energy availability" in items


# ---- return to run ---------------------------------------------------------------------------

def test_not_cleared_while_still_painful():
    r = return_to_run(days_off=10, reason="injury", pain_free=False)
    assert r["clearance"] == "not_yet"
    assert "morning after" in str(r["message"]).lower()


def test_short_break_resumes_near_previous_volume():
    r = return_to_run(days_off=5, reason="work", last_weekly_km=30.0)
    assert r["start_at_pct"] == 90
    assert r["first_week_km"] == pytest.approx(27.0)


def test_three_week_break_explains_tissue_vs_fitness():
    r = return_to_run(days_off=18, reason="holiday", last_weekly_km=40.0)
    msg = str(r["message"]).lower()
    assert "tendon" in msg or "bone" in msg
    assert "aerobic" in msg


def test_two_month_break_restarts_the_ladder():
    r = return_to_run(days_off=70, reason="injury", last_weekly_km=50.0)
    assert r["start_at_pct"] == 0
    assert "ladder" in str(r["message"]).lower()
    assert "not a demotion" in str(r["message"]).lower()


def test_febrile_illness_gets_its_own_rule():
    r = return_to_run(days_off=6, reason="illness_fever", last_weekly_km=30.0)
    assert r["start_at_pct"] == 50
    assert "resting heart rate" in str(r["rule"]).lower() + str(r["message"]).lower()


def test_all_returns_are_serialisable():
    import json
    for days in (3, 10, 30, 90):
        json.dumps(return_to_run(days, "work", last_weekly_km=25.0))


# ---- HRmax capture guards --------------------------------------------------------------------

def _profile(hr_max=187.0, age=30.0):
    from datetime import date as _d
    from marathon_engine.assessment import FitnessProfile
    from marathon_engine.physiology import five_zone_model, training_paces
    return FitnessProfile(as_of=_d(2026, 8, 1), age=age, hr_rest=55.0, hr_max=hr_max,
                          hr_max_source="age_formula", vdot=35.0, vdot_source="test",
                          zones=five_zone_model(hr_max, 55.0), paces=training_paces(35.0))


def _good_candidate(hr=195.0):
    from marathon_engine.assessment import HrMaxCandidate
    return HrMaxCandidate(observed_hr=hr, sustained_s=20.0, elapsed_in_session_s=1800.0,
                          fraction_through_effort=0.95, cadence_spm=170.0, hr_status="ok")


def test_value_above_the_plausibility_ceiling_is_rejected_before_capping():
    """Ordering check: the ceiling guard must fire before the capping logic, so an absurd reading is
    rejected outright rather than quietly becoming a +5 bpm raise."""
    from marathon_engine.assessment import update_hr_max
    _, msg, rej = update_hr_max(_profile(), _good_candidate(215.0))
    assert msg is None
    assert any("plausibility ceiling" in r for r in rej)


def test_valid_candidate_raises_hrmax_but_only_in_a_small_step():
    """Unconfirmed optical peaks move HRmax in capped steps: one artifact adopted as a maximum would
    shift every zone boundary upward and silently turn easy runs into tempo runs."""
    from marathon_engine.assessment import HR_MAX_STEP_UNCONFIRMED, update_hr_max
    p = _profile()
    updated, msg, rej = update_hr_max(p, _good_candidate(205.0))
    assert not rej and msg
    assert updated.hr_max == pytest.approx(p.hr_max + HR_MAX_STEP_UNCONFIRMED)
    assert updated.hr_max_source == "observed_capped"


def test_chest_strap_confirmation_adopts_the_full_value():
    from marathon_engine.assessment import update_hr_max
    p = _profile()
    c = _good_candidate(198.0)
    c.chest_strap_confirmed = True
    updated, msg, rej = update_hr_max(p, c)
    assert not rej
    assert updated.hr_max == pytest.approx(198.0)
    assert updated.hr_max_source == "observed_confirmed"


def test_brief_spike_is_rejected():
    from marathon_engine.assessment import update_hr_max
    c = _good_candidate(); c.sustained_s = 3.0
    _, msg, rej = update_hr_max(_profile(), c)
    assert msg is None
    assert any("spike" in r for r in rej)


def test_early_session_peak_is_rejected():
    from marathon_engine.assessment import update_hr_max
    c = _good_candidate(); c.elapsed_in_session_s = 60.0
    _, msg, rej = update_hr_max(_profile(), c)
    assert msg is None
    assert any("optical signal quality" in r for r in rej)


def test_peak_near_cadence_is_rejected():
    """The specific artifact this guard exists for."""
    from marathon_engine.assessment import update_hr_max
    c = _good_candidate(hr=172.0); c.cadence_spm = 170.0
    _, msg, rej = update_hr_max(_profile(hr_max=165.0), c)
    assert msg is None
    assert any("lock-on" in r for r in rej)


def test_peak_near_half_cadence_is_rejected():
    from marathon_engine.assessment import update_hr_max
    c = _good_candidate(hr=190.0); c.cadence_spm = 380.0
    _, msg, rej = update_hr_max(_profile(), c)
    assert msg is None
    assert any("half cadence" in r for r in rej)


def test_implausible_value_is_rejected():
    from marathon_engine.assessment import update_hr_max
    _, msg, rej = update_hr_max(_profile(), _good_candidate(hr=245.0))
    assert msg is None
    assert any("plausibility ceiling" in r for r in rej)


def test_peak_mid_effort_is_rejected():
    from marathon_engine.assessment import update_hr_max
    c = _good_candidate(); c.fraction_through_effort = 0.3
    _, msg, rej = update_hr_max(_profile(), c)
    assert msg is None
    assert any("through the effort" in r for r in rej)


def test_degraded_sensor_state_is_rejected():
    from marathon_engine.assessment import update_hr_max
    for state in ("frozen", "cadence_lock", "dropout", "warmup"):
        c = _good_candidate(); c.hr_status = state
        _, msg, rej = update_hr_max(_profile(), c)
        assert msg is None, f"{state} must not yield a new HRmax"


def test_cumulative_unconfirmed_raise_is_capped():
    from marathon_engine.assessment import HR_MAX_TOTAL_UNCONFIRMED, update_hr_max
    _, msg, rej = update_hr_max(_profile(), _good_candidate(205.0),
                                total_unconfirmed_raise=HR_MAX_TOTAL_UNCONFIRMED)
    assert msg is None
    assert any("chest strap" in r for r in rej)


def test_lower_observation_changes_nothing():
    from marathon_engine.assessment import update_hr_max
    p = _profile()
    updated, msg, rej = update_hr_max(p, _good_candidate(hr=170.0))
    assert updated is p and msg is None


def test_message_warns_that_load_history_needs_recomputing():
    """Banister TRIMP is a function of HR reserve, so a revised HRmax rewrites every historical
    load value. That must not happen silently."""
    from marathon_engine.assessment import update_hr_max
    _, msg, _ = update_hr_max(_profile(), _good_candidate(195.0))
    assert "recomputing" in msg or "recompute" in msg


# ---- spike clamping (the guard as a limit, not a suggestion) ---------------------------------

def test_clamp_leaves_a_normal_run_alone():
    from marathon_engine.safety import clamp_single_run
    r = clamp_single_run(10.0, 12.0)
    assert not r["clamped"]
    assert r["allowed_km"] == pytest.approx(10.0)


def test_clamp_shortens_a_caution_run_by_default():
    """A warning the athlete can dismiss is a warning that gets dismissed, usually on the morning
    they feel good -- which is the wrong day to allow a step up."""
    from marathon_engine.safety import SPIKE_DEFAULT_CLAMP, clamp_single_run
    r = clamp_single_run(14.0, 10.0)
    assert r["clamped"]
    assert r["allowed_km"] == pytest.approx(10.0 * SPIKE_DEFAULT_CLAMP)
    assert "not lost" in r["message"]


def test_caution_can_be_overridden_explicitly():
    from marathon_engine.safety import clamp_single_run
    r = clamp_single_run(12.0, 10.0, allow_override=True)
    assert not r["clamped"]
    assert "explicit request" in r["message"]


def test_high_band_cannot_be_overridden():
    from marathon_engine.safety import clamp_single_run
    r = clamp_single_run(25.0, 10.0, allow_override=True)
    assert r["clamped"], "the high band is where the cost of being wrong is a stress injury"


def test_bone_window_disables_progression_entirely():
    from marathon_engine.safety import clamp_single_run
    r = clamp_single_run(12.0, 10.0, in_bone_window=True)
    assert r["clamped"]
    assert r["allowed_km"] == pytest.approx(10.0)
    assert "bone-vulnerable" in r["message"]


def test_bone_window_override_is_ignored():
    from marathon_engine.safety import clamp_single_run
    r = clamp_single_run(12.0, 10.0, in_bone_window=True, allow_override=True)
    assert r["clamped"]


def test_no_history_is_not_clamped():
    from marathon_engine.safety import clamp_single_run
    r = clamp_single_run(8.0, None)
    assert not r["clamped"]


def test_bone_window_halves_the_increment_cap():
    from marathon_engine.safety import bone_window_increment_factor
    assert bone_window_increment_factor(bone_load([10.0] * 4)) == 0.5
    assert bone_window_increment_factor(bone_load([30.0] * 30)) == 1.0


def test_bone_window_states_that_it_slows_the_plan_on_purpose():
    s = bone_load([10.0] * 4)
    assert any("on purpose" in g for g in s.guidance)


def test_bone_model_admits_its_own_limits():
    """The window is a simplification and real vulnerability may extend past it."""
    from marathon_engine.safety import bone_window_increment_factor
    doc = bone_window_increment_factor.__doc__
    assert "simplification" in doc and "extend past it" in doc


# ---- time-trial precedence -------------------------------------------------------------------

def _tt(distance_m, seconds, days_ago=0, walked=False):
    from datetime import date, timedelta
    from marathon_engine.assessment import TimeTrial
    return TimeTrial(day=date(2026, 8, 1) - timedelta(days=days_ago),
                     distance_m=distance_m, seconds=seconds, walked=walked)


def test_longest_distance_wins():
    """VDOT comes from the best available result by distance, never averaged across distances: a
    2000 m trial systematically over-estimates long-distance ability in someone without mileage."""
    from marathon_engine.assessment import best_time_trial
    best = best_time_trial([_tt(2000, 700), _tt(10000, 3600), _tt(5000, 1700)])
    assert best.distance_m == 10000


def test_most_recent_wins_within_a_distance():
    from marathon_engine.assessment import best_time_trial
    best = best_time_trial([_tt(5000, 1800, days_ago=90), _tt(5000, 1700, days_ago=5)])
    assert best.seconds == 1700


def test_stale_results_are_dropped_before_precedence_applies():
    """A six-month-old half marathon describes a different athlete, so it must not outrank a fresh
    5K on distance alone."""
    from marathon_engine.assessment import best_time_trial
    best = best_time_trial([_tt(21097.5, 9000, days_ago=400), _tt(5000, 1700, days_ago=3)])
    assert best.distance_m == 5000


def test_walked_trials_are_excluded():
    """A run with walk breaks is not a valid maximal continuous performance."""
    from marathon_engine.assessment import best_time_trial
    best = best_time_trial([_tt(10000, 4000, walked=True), _tt(5000, 1700)])
    assert best.distance_m == 5000


def test_no_usable_trials_returns_none():
    from marathon_engine.assessment import best_time_trial
    assert best_time_trial([]) is None
    assert best_time_trial([_tt(5000, 1700, walked=True)]) is None


def test_unrecognised_distance_still_beats_nothing():
    from marathon_engine.assessment import best_time_trial
    best = best_time_trial([_tt(3000, 900)])
    assert best is not None and best.distance_m == 3000


def test_precedence_order_is_longest_first():
    from marathon_engine.assessment import TT_PRECEDENCE
    assert list(TT_PRECEDENCE) == sorted(TT_PRECEDENCE, reverse=True)
    assert TT_PRECEDENCE[0] == pytest.approx(42195.0)
