"""The runs of one model: a point run and, on a probabilistic run, its members."""

from collections.abc import Callable
from dataclasses import dataclass, field

from commol import (
    CalibrationProblem,
    Model,
    ObservedDataPoint,
    Predictive,
    Simulation,
    SimulationResults,
)

from flu_korea.commol_gaps import (
    AppliedParameters,
    MemberSpread,
    OutputSum,
    SeriesReport,
)
from flu_korea.model.compartments import ACCUMULATOR_IDS, DISEASE_BINS
from flu_korea.timeline import SeasonTimeline

# A quantity derived from one run: a scalar summary or a whole series.
Reduction = Callable[[SimulationResults], "float | list[float]"]


def _peak_index(series: list[float]) -> int | None:
    if not series:
        return None
    return max(range(len(series)), key=series.__getitem__)


@dataclass
class RunEnsemble:
    """
    A point run and the runs of the members of a sample, with the simulation
    that made them.

    A deterministic run has no members and no confidence level. On a
    probabilistic run every magnitude becomes member statistics at
    `confidence_level`, and `predictive` holds the predictive of the sample.
    """

    simulation: Simulation
    point: SimulationResults
    timeline: SeasonTimeline
    members: list[SimulationResults] = field(default_factory=list)
    confidence_level: float | None = None
    predictive: Predictive | None = None

    @property
    def probabilistic(self) -> bool:
        return bool(self.members) and self.confidence_level is not None

    def spread(self, reduce_fn: Reduction) -> object:
        """One summary value, or its spread across the members."""
        if not self.members or self.confidence_level is None:
            return reduce_fn(self.point)
        return MemberSpread(self.confidence_level).of(
            [reduce_fn(run) for run in self.members]
        )

    def weekly_total(self, run: SimulationResults, accumulator_id: str) -> list[float]:
        """New entries per week of one accumulator in one run."""
        return self.simulation.windowed_totals(
            run,
            [accumulator_id],
            self.timeline.axis.steps_per_week,
            self.timeline.week_anchors(len(run.positions)),
        )

    def weekly_band(
        self, outputs: tuple[str, ...], windowed: bool
    ) -> tuple[list[float], list[float] | None, list[float] | None]:
        """Central weekly series of the summed outputs, with its interval."""
        runs = self.members or [self.point]
        anchors = self.timeline.week_anchors(
            min(len(next(iter(run.values()))) for run in runs)
        )
        per_run = []
        for run in runs:
            output_sum = OutputSum(run, outputs)
            per_run.append(
                output_sum.gains(self.timeline.axis.steps_per_week, anchors)
                if windowed
                else output_sum.at(anchors)
            )
        if len(per_run) == 1 or self.confidence_level is None:
            return per_run[0], None, None
        statistics = MemberSpread(self.confidence_level).of(per_run)
        return statistics["median"], statistics["ci_lower"], statistics["ci_upper"]

    def summary(self) -> dict[str, object]:
        """
        The handful of numbers the run is usually judged on, so they can be read
        without reducing the series by hand.

        Magnitudes get the same treatment as the series: a plain number on a
        deterministic run, member statistics on a probabilistic one. The
        `*_week` labels are taken from the point run alone, since a median of
        week labels is not a meaningful quantity.
        """
        point = self.point

        def total(run: SimulationResults, ids: list[str]) -> list[float]:
            return self.simulation.total_series(run, ids)

        def week_of_weekly(weekly: list[float]) -> str | None:
            index = _peak_index(weekly)
            return None if index is None else self.timeline.week_label(index)

        def week_of_steps(series: list[float]) -> str | None:
            index = _peak_index(series)
            return None if index is None else self.timeline.step_label(index)

        return {
            "simulation_weeks": self.timeline.simulation_weeks,
            "population_size": total(point, list(DISEASE_BINS))[0],
            "final_population": self.spread(
                lambda run: total(run, list(DISEASE_BINS))[-1]
            ),
            "total_infections": self.spread(
                lambda run: total(run, ["infection_incidence"])[-1]
            ),
            "attack_rate": self.spread(
                lambda run: (
                    total(run, ["infection_incidence"])[-1]
                    / total(run, list(DISEASE_BINS))[0]
                )
            ),
            "peak_weekly_infections": self.spread(
                lambda run: max(
                    self.weekly_total(run, "infection_incidence"), default=0.0
                )
            ),
            "peak_infection_week": week_of_weekly(
                self.weekly_total(point, "infection_incidence")
            ),
            "peak_infectious": self.spread(
                lambda run: max(total(run, ["IR", "IH"]), default=0.0)
            ),
            "peak_infectious_week": week_of_steps(total(point, ["IR", "IH"])),
            "total_hospital_admissions": self.spread(
                lambda run: total(run, ["hospital_admissions"])[-1]
            ),
            "peak_weekly_hospital_admissions": self.spread(
                lambda run: max(
                    self.weekly_total(run, "hospital_admissions"), default=0.0
                )
            ),
            "peak_hospital_admissions_week": week_of_weekly(
                self.weekly_total(point, "hospital_admissions")
            ),
            "peak_hospital_occupancy": self.spread(
                lambda run: max(total(run, ["H"]), default=0.0)
            ),
            "peak_hospital_occupancy_week": week_of_steps(total(point, ["H"])),
            "final_recovered_fraction": self.spread(
                lambda run: total(run, ["R"])[-1] / total(run, list(DISEASE_BINS))[-1]
            ),
        }

    def series_report(
        self, observed_data: list[ObservedDataPoint], resolution: str
    ) -> dict[str, object]:
        """Steps, week labels, summary and series of the runs, at `resolution`."""
        steps = self.timeline.output_steps(resolution)
        return {
            "resolution": resolution,
            "steps": steps,
            "weeks": [self.timeline.step_label(step) for step in steps],
            "summary": self.summary(),
            **SeriesReport(self.simulation).report(
                self.point,
                steps,
                self.timeline.axis.steps_per_week,
                self.timeline.simulation_weeks,
                observed_data=observed_data,
                accumulators=ACCUMULATOR_IDS,
                ensemble_runs=self.members or None,
                confidence_level=self.confidence_level,
            ),
        }

    def results_report(
        self, kind: str, observed_data: list[ObservedDataPoint], resolution: str
    ) -> dict[str, object]:
        """
        Everything a reader needs to judge the run: headline numbers, the data
        that was fitted, the compartment series, and both readings of the
        accumulators.

        On a probabilistic run every magnitude becomes a `{mean, median,
        ci_lower, ci_upper, min, max}` block computed across the members, and
        the layout is otherwise identical, so the same reader handles both.
        """
        series = self.series_report(observed_data, resolution)
        return {
            "kind": kind,
            "probabilistic": self.probabilistic,
            "confidence_level": self.confidence_level if self.probabilistic else None,
            "resolution": series.pop("resolution"),
            "steps": series.pop("steps"),
            "weeks": series.pop("weeks"),
            "observation_weeks": self.timeline.week_labels(),
            **series,
        }

    def raw_report(
        self,
        kind: str,
        model: Model,
        problem: CalibrationProblem,
        point_parameters: dict[str, float],
        member_parameters: list[dict[str, float]] | None = None,
    ) -> dict[str, object]:
        """
        The unreduced runs, at full step resolution and with the parameter set
        each one was run with, so any quantity not covered by the results
        report can still be recomputed after the fact.

        Applying a member's parameters to the model and reading its full
        parameter set back is what makes each entry self-describing, rather
        than only listing the values the calibration varied. The model is left
        with the point parameters applied.
        """
        applied = AppliedParameters(model, problem)
        report: dict[str, object] = {
            "kind": kind,
            "resolution": "step",
            "steps": list(range(self.timeline.final_step + 1)),
            "point": {
                "parameters": applied.report(point_parameters),
                "series": self.point,
            },
        }
        if member_parameters is None or not self.members:
            return report

        members = []
        for index, (parameters, results) in enumerate(
            zip(member_parameters, self.members, strict=True)
        ):
            model.apply_calibration_parameters(parameters, problem)
            members.append(
                {
                    "index": index,
                    "parameters": applied.report(parameters),
                    "series": results,
                }
            )
        model.apply_calibration_parameters(point_parameters, problem)
        report["members"] = members
        return report
