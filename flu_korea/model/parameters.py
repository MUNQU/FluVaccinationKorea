"""Parameters of the SEIR model: calibrated, fixed and formula parameters."""

from dataclasses import dataclass

from flu_korea.model.compartments import (
    DISEASE_BINS,
    FIXED_BIN_INITIAL_CONDITIONS,
    INITIAL_CONDITION_REMAINDER,
)
from flu_korea.season import Population
from flu_korea.timeline import AXIS


@dataclass(frozen=True)
class ModelParameterSpec:
    id: str
    min_value: float
    max_value: float
    initial_guess: float | None
    unit: str
    description: str

    def required_initial_guess(self) -> float:
        """Return ``initial_guess`` for a spec that must define one."""
        if self.initial_guess is None:
            raise ValueError(f"Parameter '{self.id}' requires an initial_guess")
        return self.initial_guess


TRANSMISSION_PARAMETER = ModelParameterSpec(
    id="beta",
    min_value=1e-05,
    max_value=0.125,
    initial_guess=None,
    unit="per step",
    description="Transmission rate (S -> E)",
)

HOSPITALIZATION_PROBABILITY_PARAMETERS = (
    ModelParameterSpec(
        id="p_h_y",
        min_value=1e-05,
        max_value=0.2,
        initial_guess=0.005,
        unit="probability",
        description="Hospitalization percentage <65 (E_y65 -> IH_y65)",
    ),
    ModelParameterSpec(
        id="p_h_nv",
        min_value=0.001,
        max_value=0.2,
        initial_guess=0.01,
        unit="probability",
        description="Hospitalization percentage 65+ not vaccinated (E -> IH)",
    ),
)

DURATION_PARAMETERS = (
    ModelParameterSpec(
        id="t_latency",
        min_value=AXIS.rate_from_mean_days(4.0),
        max_value=AXIS.rate_from_mean_days(0.5),
        initial_guess=AXIS.rate_from_mean_days(3.0),
        unit="per step, from mean days 1/4 to 1/0.5",
        description="Latency time (E -> I)",
    ),
    ModelParameterSpec(
        id="t_recovery",
        min_value=AXIS.rate_from_mean_days(3.0),
        max_value=AXIS.rate_from_mean_days(1.0),
        initial_guess=AXIS.rate_from_mean_days(2.0),
        unit="per step, from mean days 1/3 to 1/1",
        description="Recovery time (I -> R)",
    ),
    ModelParameterSpec(
        id="t_hospitalization_nv",
        min_value=AXIS.rate_from_mean_days(9.05),
        max_value=AXIS.rate_from_mean_days(8.9),
        initial_guess=AXIS.rate_from_mean_days(9.0),
        unit="per step, from mean days 1/9.05 to 1/8.9",
        description="Hospitalization time (I_nv -> H_nv)",
    ),
    ModelParameterSpec(
        id="t_hospitalization_v",
        min_value=AXIS.rate_from_mean_days(8.61),
        max_value=AXIS.rate_from_mean_days(8.37),
        initial_guess=AXIS.rate_from_mean_days(8.5),
        unit="per step, from mean days 1/8.61 to 1/8.37",
        description="Hospitalization time vaccinated (I_v -> H_v)",
    ),
    ModelParameterSpec(
        id="t_hospitalization_recovery_nv",
        min_value=AXIS.rate_from_mean_days(7.74),
        max_value=AXIS.rate_from_mean_days(6.9),
        initial_guess=AXIS.rate_from_mean_days(7.2),
        unit="per step, from mean days 1/7.74 to 1/6.9",
        description="Hospitalization recovery time non vaccinated (H_nv -> R_nv)",
    ),
    ModelParameterSpec(
        id="t_hospitalization_recovery_v",
        min_value=AXIS.rate_from_mean_days(9.0),
        max_value=AXIS.rate_from_mean_days(7.7),
        initial_guess=AXIS.rate_from_mean_days(8.3),
        unit="per step, from mean days 1/9.0 to 1/7.7",
        description="Hospitalization recovery time vaccinated (H_v -> R_v)",
    ),
)

# Order is load-bearing: it fixes the optimizer's parameter vector, so a
# seeded run only reproduces while this sequence is unchanged.
CALIBRATED_MODEL_PARAMETERS = (
    TRANSMISSION_PARAMETER,
    *DURATION_PARAMETERS,
    *HOSPITALIZATION_PROBABILITY_PARAMETERS,
)

CASE_REPORTING_RATE_PARAMETER = ModelParameterSpec(
    id="case_reporting_rate",
    min_value=0.001,
    max_value=1.0,
    initial_guess=0.1,
    unit="fraction",
    description="Fraction of true infections reported by sentinel surveillance",
)

# Evaluated after the calibrated and fixed parameters, so they can use both.
FORMULA_PARAMETERS = (
    (
        "p_h_v",
        "(1 - ve) * p_h_nv",
        "Hospitalization percentage vaccinated 65+ (fixed by ve)",
    ),
)


@dataclass(frozen=True)
class InitialConditions:
    """
    Initial amounts of the season, in people.

    R is the remainder (see `compartments.INITIAL_CONDITION_REMAINDER`), and H
    starts fixed.
    """

    population_size: float

    def calibrated(self) -> tuple[ModelParameterSpec, ...]:
        """The initial amounts the calibration fits, with their bounds."""
        size = self.population_size
        return (
            ModelParameterSpec(
                id="S",
                min_value=0.4 * size,
                max_value=0.7 * size,
                initial_guess=0.55 * size,
                unit="people, from population fraction 0.4 to 0.7",
                description="Initial susceptible population",
            ),
            ModelParameterSpec(
                id="E",
                min_value=1e-08 * size,
                max_value=0.0001 * size,
                initial_guess=1e-06 * size,
                unit="people, from population fraction 1e-8 to 1e-4",
                description="Initial exposed population",
            ),
            ModelParameterSpec(
                id="IR",
                min_value=1e-08 * size,
                max_value=0.0001 * size,
                initial_guess=1e-06 * size,
                unit="people, from population fraction 1e-8 to 1e-4",
                description="Initial infectious (recover) population",
            ),
            ModelParameterSpec(
                id="IH",
                min_value=1e-08 * size,
                max_value=0.0001 * size,
                initial_guess=1e-06 * size,
                unit="people, from population fraction 1e-8 to 1e-4",
                description="Initial infectious (hospital-bound) population",
            ),
        )

    def amounts(self) -> dict[str, float]:
        """
        Initial people per bin: the initial guesses, H fixed, and the remainder
        holding the rest of the population, so the model runs before
        calibration.
        """
        amounts = {
            spec.id: spec.required_initial_guess() for spec in self.calibrated()
        } | FIXED_BIN_INITIAL_CONDITIONS
        amounts[INITIAL_CONDITION_REMAINDER] = self.population_size - sum(
            amounts.values()
        )
        return {bin_id: amounts[bin_id] for bin_id in DISEASE_BINS}


@dataclass(frozen=True)
class FixedParameters:
    """The parameters the calibration keeps fixed: demography and vaccine."""

    population: Population
    vaccine_effectiveness: float

    def values(self) -> tuple[tuple[str, float, str], ...]:
        """(id, value, description) of each parameter."""
        population = self.population
        return (
            (
                "births",
                population.births_per_week / AXIS.steps_per_week,
                "Birth rate",
            ),
            (
                "aging",
                AXIS.rate_from_weekly_probability(population.aging_weekly_probability),
                "Aging rate (<65 -> 65+)",
            ),
            (
                "death_y65",
                AXIS.rate_from_weekly_probability(
                    population.death_under_65_weekly_probability
                ),
                "Death rate younger 65",
            ),
            (
                "death_o65",
                AXIS.rate_from_weekly_probability(
                    population.death_65plus_weekly_probability
                ),
                "Death rate 65 and older",
            ),
            (
                "ve",
                self.vaccine_effectiveness,
                "Vaccine effectiveness against hospitalization",
            ),
            # The scenarios set it to 0 to withdraw this season's campaign.
            ("campaign", 1.0, "Fraction of this season's doses given"),
        )
