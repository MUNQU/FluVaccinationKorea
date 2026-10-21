"""A calibrated model and the parameter sets it was calibrated to."""

from dataclasses import dataclass

from commol import (
    BootstrapResult,
    CalibrationProblem,
    CalibrationResult,
    Calibrator,
    Model,
    Predictive,
    Simulation,
)

from flu_korea.model import SeirModelSpec
from flu_korea.reporting.ensemble import RunEnsemble
from flu_korea.scenarios.comparison import ScenarioComparison
from flu_korea.timeline import SeasonTimeline


@dataclass(frozen=True)
class Fit:
    """
    The result of a calibration: the calibrated model, its point parameters
    and, for a probabilistic calibration, the parameters of every member.

    A fit read back from a run directory has no `result`.
    """

    kind: str
    spec: SeirModelSpec
    timeline: SeasonTimeline
    model: Model
    problem: CalibrationProblem
    seed: int
    point_parameters: dict[str, float]
    member_parameters: list[dict[str, float]] | None
    confidence_level: float | None
    result: CalibrationResult | BootstrapResult | None = None

    def simulate(self) -> RunEnsemble:
        """
        The run of the point parameters and, for a probabilistic calibration,
        the run of every member of its sample.
        """
        if not isinstance(self.result, BootstrapResult):
            simulation = Simulation(self.model)
            point = simulation.run(self.timeline.final_step)
            return RunEnsemble(simulation, point, self.timeline)

        self.model.apply_calibration_parameters(self.point_parameters, self.problem)
        simulation = Simulation(self.model)
        point = simulation.run(self.timeline.final_step)
        # A simulation that has already run makes every draw of the predictive
        # infeasible (commol af3b38d), so the predictive gets a fresh one.
        predictive = Predictive(
            Calibrator(Simulation(self.model), self.problem),
            self.result.sample,
            positions=list(range(self.timeline.final_step + 1)),
        )
        # The predictive runs every draw of the sample, in the order of `draws`.
        return RunEnsemble(
            simulation,
            point,
            self.timeline,
            members=predictive.runs(),
            confidence_level=self.confidence_level,
            predictive=predictive,
        )

    def compare_scenarios(self) -> ScenarioComparison:
        """Every scenario, run with the parameter sets of this fit."""
        return ScenarioComparison.run(
            self.spec.build(),
            self.problem,
            self.timeline,
            self.point_parameters,
            self.member_parameters,
            self.confidence_level,
        )
