"""The study of one season: its inputs, and the calibrations they allow."""

from dataclasses import dataclass
from typing import Literal

from commol import (
    CalibrationProblem,
    Calibrator,
    ParticleSwarmConfig,
    Simulation,
)

from flu_korea.calibration.fit import Fit
from flu_korea.calibration.observations import Observations
from flu_korea.calibration.problem import (
    DEFAULT_BOOTSTRAP_REPLICATES,
    DEFAULT_PROBABILISTIC_PSO_ITERATIONS,
    DEFAULT_PROBABILISTIC_PSO_PARTICLES,
    CalibrationSetup,
)
from flu_korea.model import SeirModelSpec
from flu_korea.season import Population, SeasonData
from flu_korea.timeline import SeasonTimeline


@dataclass(frozen=True)
class Study:
    """The inputs of one season, and the fits that can be made of them."""

    timeline: SeasonTimeline
    population: Population
    data: SeasonData
    vaccine_effectiveness: float
    use_reported_cases: bool

    @property
    def spec(self) -> SeirModelSpec:
        return SeirModelSpec(
            self.population, self.data.weekly_doses, self.vaccine_effectiveness
        )

    def problem(
        self,
        seed: int,
        use_reported_cases: bool | None = None,
        optimization_config: ParticleSwarmConfig | None = None,
    ) -> CalibrationProblem:
        if use_reported_cases is None:
            use_reported_cases = self.use_reported_cases
        observations = Observations(self.data, self.population.total)
        return CalibrationSetup(self.population.total, use_reported_cases).problem(
            observations.points(use_reported_cases), seed, optimization_config
        )

    def calibrate(self, seed: int) -> Fit:
        """Fit one parameter set."""
        problem = self.problem(seed)
        model = self.spec.build()
        result = Calibrator(Simulation(model), problem).run()
        model.apply_calibration_parameters(result, problem)
        return Fit(
            kind="calibration",
            spec=self.spec,
            timeline=self.timeline,
            model=model,
            problem=problem,
            seed=seed,
            point_parameters=result.best_parameters,
            member_parameters=None,
            confidence_level=None,
            result=result,
        )

    def calibrate_probabilistic(
        self,
        seed: int,
        confidence_level: float,
        block_length: int | Literal["auto"] = "auto",
        replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
        pso_particles: int = DEFAULT_PROBABILISTIC_PSO_PARTICLES,
        pso_iterations: int = DEFAULT_PROBABILISTIC_PSO_ITERATIONS,
    ) -> Fit:
        """Fit a Bayesian block bootstrap ensemble."""
        problem = self.problem(
            seed,
            optimization_config=CalibrationSetup.particle_swarm(
                num_particles=pso_particles, max_iterations=pso_iterations
            ),
        )
        model = self.spec.build()
        result = Calibrator(Simulation(model), problem).uncertainty(
            CalibrationSetup.bootstrap(replicates=replicates, block_length=block_length)
        )
        model.apply_calibration_parameters(result.fit, problem)
        return Fit(
            kind="probabilistic_calibration",
            spec=self.spec,
            timeline=self.timeline,
            model=model,
            problem=problem,
            seed=seed,
            point_parameters=result.fit.best_parameters,
            member_parameters=[dict(draw) for draw in result.sample.draws()],
            confidence_level=confidence_level,
            result=result,
        )

    def resume(
        self,
        kind: str,
        point_parameters: dict[str, float],
        member_parameters: list[dict[str, float]] | None,
        confidence_level: float | None,
        use_reported_cases: bool,
        seed: int,
    ) -> Fit:
        """The fit of a previous calibration, from its parameter sets."""
        problem = self.problem(seed, use_reported_cases=use_reported_cases)
        model = self.spec.build()
        model.apply_calibration_parameters(point_parameters, problem)
        return Fit(
            kind=kind,
            spec=self.spec,
            timeline=self.timeline,
            model=model,
            problem=problem,
            seed=seed,
            point_parameters=point_parameters,
            member_parameters=member_parameters,
            confidence_level=confidence_level,
        )
