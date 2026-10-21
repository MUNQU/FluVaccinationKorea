"""Calibration problem: parameters, optimizer and uncertainty method."""

from dataclasses import dataclass
from typing import Literal

from commol import (
    BayesianBootstrap,
    CalibrationConstraint,
    CalibrationParameter,
    CalibrationProblem,
    ObservedDataPoint,
    ParticleSwarmConfig,
)

from flu_korea.model.compartments import INITIAL_CONDITION_REMAINDER
from flu_korea.model.parameters import (
    CALIBRATED_MODEL_PARAMETERS,
    CASE_REPORTING_RATE_PARAMETER,
    InitialConditions,
    ModelParameterSpec,
)

DEFAULT_PSO_PARTICLES = 50
DEFAULT_PSO_ITERATIONS = 400

# Every bootstrap replicate is a full particle-swarm fit, so the swarm of a
# probabilistic run is smaller than the one of a single calibration.
DEFAULT_BOOTSTRAP_REPLICATES = 40
DEFAULT_PROBABILISTIC_PSO_PARTICLES = 50
DEFAULT_PROBABILISTIC_PSO_ITERATIONS = 200

# Season attack-rate constraints (MIN/MAX_INFECTED_FRACTION, bounding the
# season's infected fraction via the `infection_incidence` accumulator) were
# removed: the epidemic size is no longer artificially bounded during
# calibration and is read from the fitted result instead.
#
# The accumulator counts S->E crossings; with no waning immunity in the model
# each person can cross at most once, so it counts unique infected people
# rather than prevalence.


@dataclass(frozen=True)
class CalibrationSetup:
    """What is calibrated, against what, and with which optimizer."""

    population_size: float
    use_reported_cases: bool

    @staticmethod
    def particle_swarm(
        num_particles: int = DEFAULT_PSO_PARTICLES,
        max_iterations: int = DEFAULT_PSO_ITERATIONS,
    ) -> ParticleSwarmConfig:
        return (
            ParticleSwarmConfig(
                num_particles=num_particles,
                max_iterations=max_iterations,
                initialization="latin_hypercube",
            )
            .inertia("chaotic", w_min=0.4, w_max=0.9)
            .acceleration("constant")
            .velocity(clamp_factor=0.2, mutation_threshold=0.001)
            .mutation("cauchy", scale=0.1, probability=0.1, application="all_particles")
        )

    @staticmethod
    def bootstrap(
        replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
        block_length: int | Literal["auto"] = "auto",
    ) -> BayesianBootstrap:
        return BayesianBootstrap(replicates=replicates, block_length=block_length)

    def parameters(self) -> list[CalibrationParameter]:
        # Order is load-bearing: it fixes the optimizer's parameter vector, so
        # a seeded run only reproduces while this sequence is unchanged.
        parameters = [
            *[
                self._parameter(spec, "parameter")
                for spec in CALIBRATED_MODEL_PARAMETERS
            ],
            *[
                self._parameter(spec, "initial_condition")
                for spec in InitialConditions(self.population_size).calibrated()
                if spec.initial_guess is not None
            ],
        ]

        # `case_reporting_rate` only scales the reported-case observations, so
        # it has no effect on the loss when that series is excluded.
        if self.use_reported_cases:
            parameters.append(
                self._parameter(
                    CASE_REPORTING_RATE_PARAMETER,
                    "factor",
                    CASE_REPORTING_RATE_PARAMETER.required_initial_guess(),
                )
            )
        return parameters

    def constraints(self) -> list[CalibrationConstraint]:
        # No season attack-rate bounds: both the minimum and maximum infected
        # fraction constraints were removed.
        return []

    def problem(
        self,
        observed_data: list[ObservedDataPoint],
        seed: int,
        optimization_config: ParticleSwarmConfig | None = None,
    ) -> CalibrationProblem:
        return CalibrationProblem(
            observed_data=observed_data,
            parameters=self.parameters(),
            constraints=self.constraints(),
            loss_function="sse",
            normalize_observations=True,
            optimization_config=optimization_config or self.particle_swarm(),
            initial_condition_remainder=INITIAL_CONDITION_REMAINDER,
            seed=seed,
        )

    @staticmethod
    def _parameter(
        spec: ModelParameterSpec,
        parameter_type: str,
        initial_guess: float | None = None,
    ) -> CalibrationParameter:
        return CalibrationParameter(
            id=spec.id,
            parameter_type=parameter_type,
            min_bound=spec.min_value,
            max_bound=spec.max_value,
            initial_guess=(
                spec.initial_guess if initial_guess is None else initial_guess
            ),
        )
