"""The only module that calls functions of commol.

commol gives these operations as functions only. Each class here puts one of
them behind an object, so the rest of the package uses objects alone. When
commol gives the operation as a method of one of its classes, the class here
goes, and its callers use that method. Each class names the issue of commol
that does it.
"""

from commol import (
    CalibrationProblem,
    Model,
    ObservedDataPoint,
    Simulation,
    SimulationResults,
    applied_parameters_report,
    member_statistics,
    simulation_report,
    window_end,
    window_index,
    window_start,
    windowed_totals,
)


class WindowGrid:
    """
    Consecutive windows of one width from position 0 (commol: the window grid
    as methods of `AxisUnits`, N7).
    """

    def __init__(self, width: float) -> None:
        self.width = width

    def start(self, index: int) -> float:
        return window_start(index, self.width)

    def end(self, index: int) -> float:
        return window_end(index, self.width)

    def index(self, at: float) -> int:
        return window_index(at, self.width)


class OutputSum:
    """
    The sum of some outputs of one run (commol: `Simulation.total_series` and
    `Simulation.windowed_totals` that take output names, N6, and a reader of a
    series at positions, #245).
    """

    def __init__(self, run: SimulationResults, outputs: tuple[str, ...]) -> None:
        self.positions = run.positions
        self.values = [
            sum(values)
            for values in zip(*(run[output] for output in outputs), strict=True)
        ]

    def at(self, positions: list[int]) -> list[float]:
        """The value at each position, which must be a position of the run."""
        index = {position: i for i, position in enumerate(self.positions)}
        return [self.values[index[position]] for position in positions]

    def gains(self, window: float, ends: list[int]) -> list[float]:
        """What entered the sum over each window that closes at `ends`."""
        return windowed_totals(self.values, self.positions, window, ends)


class MemberSpread:
    """
    The spread of a quantity across the members of a sample (commol: the
    quantities of N1 read on a sample, and the scenarios of #246).
    """

    def __init__(self, confidence_level: float) -> None:
        self.confidence_level = confidence_level

    def of(self, per_member: list) -> dict:
        return member_statistics(per_member, self.confidence_level)


class AppliedParameters:
    """
    The full parameter set of a model (commol: reports as methods, N8).
    """

    def __init__(self, model: Model, problem: CalibrationProblem) -> None:
        self.model = model
        self.problem = problem

    def report(self, values: object, **options: object) -> object:
        return applied_parameters_report(self.model, values, self.problem, **options)


class SeriesReport:
    """
    Observed values, series and accumulators of a run (commol: reports as
    methods, N8).
    """

    def __init__(self, simulation: Simulation) -> None:
        self.simulation = simulation

    def report(
        self,
        results: SimulationResults,
        steps: list[int],
        window: int,
        windows: int,
        observed_data: list[ObservedDataPoint],
        accumulators: tuple[str, ...],
        ensemble_runs: list[SimulationResults] | None,
        confidence_level: float | None,
    ) -> dict:
        return simulation_report(
            self.simulation,
            results,
            steps,
            window,
            windows,
            observed_data=observed_data,
            accumulators=accumulators,
            ensemble_runs=ensemble_runs,
            confidence_level=confidence_level,
        )
