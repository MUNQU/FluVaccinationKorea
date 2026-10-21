import pytest
from commol import Simulation

from flu_korea.calibration.observations import Observations
from flu_korea.model import SeirModelSpec
from flu_korea.model.compartments import DISEASE_BINS
from flu_korea.model.parameters import CALIBRATED_MODEL_PARAMETERS
from flu_korea.model.vaccination import VACCINATION_EFFECT_DELAY_STEPS, Vaccination
from flu_korea.season import Population, SeasonData
from flu_korea.timeline import STEPS_PER_WEEK

POPULATION = Population(
    under_65=900_000,
    aged_65_plus=100_000,
    births_per_week=150.0,
    aging_weekly_probability=1e-4,
    death_under_65_weekly_probability=1e-5,
    death_65plus_weekly_probability=5e-4,
)


def test_calibrated_parameter_order_is_fixed():
    # A seeded calibration only reproduces while this order is unchanged.
    assert [spec.id for spec in CALIBRATED_MODEL_PARAMETERS] == [
        "beta",
        "t_latency",
        "t_recovery",
        "t_hospitalization_nv",
        "t_hospitalization_v",
        "t_hospitalization_recovery_nv",
        "t_hospitalization_recovery_v",
        "p_h_y",
        "p_h_nv",
    ]


def test_dose_series_keeps_the_weekly_doses():
    weekly = [0.0, 5_600.0, 1_120.0]
    pulses = Vaccination(weekly).dose_series()
    assert sum(doses for _, doses in pulses) == pytest.approx(sum(weekly))
    assert pulses[0][0] == VACCINATION_EFFECT_DELAY_STEPS


def test_doses_reach_the_65plus_without_negative_compartments():
    weekly_doses = [0.0, 20_000.0, 20_000.0]
    model = SeirModelSpec(POPULATION, weekly_doses, vaccine_effectiveness=0.2).build()
    # No transmission, so the doses are the only flow into `v`.
    model.update_parameters(
        {spec.id: spec.initial_guess or 0.0 for spec in CALIBRATED_MODEL_PARAMETERS}
    )
    simulation = Simulation(model)
    results = simulation.run(6 * STEPS_PER_WEEK)
    assert min(min(series) for series in results.values()) >= -1e-6
    vaccinated = sum(results[f"{bin_id}_o65_v"][-1] for bin_id in DISEASE_BINS)
    assert vaccinated == pytest.approx(sum(weekly_doses), rel=0.01)


def test_one_observation_per_age_group_and_week():
    data = SeasonData([], [(0, 10.0, 20.0), (1, 11.0, 21.0)], [])
    points = Observations(data, POPULATION.total).points(use_reported_cases=False)
    assert [point.label for point in points] == [
        "hospital_admissions_y65",
        "hospital_admissions_o65",
    ] * 2
    assert points[1].outputs == [
        "hospital_admissions_o65_nv",
        "hospital_admissions_o65_v",
    ]
