"""Vaccination scenarios: the calibrated model with and without the campaign."""

from collections.abc import Callable
from dataclasses import dataclass

from commol import (
    CalibrationProblem,
    Model,
    ObservedDataPoint,
    Simulation,
    SimulationResults,
)

from flu_korea.commol_gaps import MemberSpread
from flu_korea.reporting.ensemble import RunEnsemble
from flu_korea.timeline import SeasonTimeline

BASELINE_SCENARIO = "baseline"
NO_VACCINATION_SCENARIO = "no_vaccination"

SCENARIO_LABELS = {
    BASELINE_SCENARIO: "With vaccination campaign",
    NO_VACCINATION_SCENARIO: "Without vaccination campaign",
}

# Value of the `campaign` parameter in each scenario. `no_vaccination` withdraws
# this season's doses only; the 65+ start the season non-vaccinated either way.
SCENARIO_CAMPAIGN = {BASELINE_SCENARIO: 1.0, NO_VACCINATION_SCENARIO: 0.0}

# Series the scenarios are compared on, as bin or accumulator ids.
COMPARED_ACCUMULATORS = ("infection_incidence", "hospital_admissions")
COMPARED_STOCKS = {"hospital_occupancy": ("H",), "infectious": ("IR", "IH")}

# A quantity of all the scenarios of one parameter set, keyed by scenario.
PairedReduction = Callable[[dict[str, SimulationResults]], float]


@dataclass
class ScenarioComparison:
    """The runs of every scenario, with the same parameter sets in each."""

    runs: dict[str, RunEnsemble]
    confidence_level: float | None

    @classmethod
    def run(
        cls,
        model: Model,
        problem: CalibrationProblem,
        timeline: SeasonTimeline,
        point_parameters: dict[str, float],
        member_parameters: list[dict[str, float]] | None,
        confidence_level: float | None,
    ) -> "ScenarioComparison":
        """
        Run every scenario once per parameter set.

        `model` must be a fresh model: the scenarios change its parameters.
        Every set is simulated in full and reduced afterwards. Feeding an
        ensemble median or an interval bound in as parameter values would
        instead simulate a parameter set that was never calibrated.
        """
        parameter_sets = [point_parameters, *(member_parameters or [])]
        runs = {}
        for scenario in SCENARIO_LABELS:
            model.update_parameters({"campaign": SCENARIO_CAMPAIGN[scenario]})
            results = []
            for parameters in parameter_sets:
                model.apply_calibration_parameters(parameters, problem)
                results.append(Simulation(model).run(timeline.final_step))
            runs[scenario] = RunEnsemble(
                simulation=Simulation(model),
                point=results[0],
                timeline=timeline,
                members=results[1:],
                confidence_level=confidence_level,
            )
        return cls(runs, confidence_level)

    @property
    def baseline(self) -> RunEnsemble:
        return self.runs[BASELINE_SCENARIO]

    def scenario_report(
        self,
        scenario: str,
        observed_data: list[ObservedDataPoint],
        resolution: str,
    ) -> dict[str, object]:
        """Summary and series of one scenario."""
        ensemble = self.runs[scenario]
        return {
            "scenario": scenario,
            "label": SCENARIO_LABELS[scenario],
            "probabilistic": bool(ensemble.members),
            "confidence_level": self.confidence_level if ensemble.members else None,
            **ensemble.series_report(observed_data, resolution),
        }

    def report(self) -> dict[str, object]:
        """
        What each scenario produced over the season, and what the campaign
        averted.

        `averted` is the baseline subtracted from the scenario, so a positive
        value is a case the campaign prevented.
        """
        simulation = self.baseline.simulation

        def final(run: SimulationResults, accumulator_id: str) -> float:
            return simulation.total_series(run, [accumulator_id])[-1]

        def peak(run: SimulationResults, ids: tuple[str, ...]) -> float:
            return max(simulation.total_series(run, list(ids)))

        quantities: dict[str, object] = {}
        for accumulator_id in COMPARED_ACCUMULATORS:
            entry: dict[str, object] = {}
            for scenario in self.runs:
                entry[scenario] = self._paired(
                    lambda runs, s=scenario, acc=accumulator_id: final(runs[s], acc)
                )
            entry["averted"] = self._paired(
                lambda runs, acc=accumulator_id: (
                    final(runs[NO_VACCINATION_SCENARIO], acc)
                    - final(runs[BASELINE_SCENARIO], acc)
                )
            )
            quantities[accumulator_id] = entry

        for name, source_ids in COMPARED_STOCKS.items():
            entry = {}
            for scenario in self.runs:
                entry[scenario] = self._paired(
                    lambda runs, s=scenario, ids=source_ids: peak(runs[s], ids)
                )
            entry["averted"] = self._paired(
                lambda runs, ids=source_ids: (
                    peak(runs[NO_VACCINATION_SCENARIO], ids)
                    - peak(runs[BASELINE_SCENARIO], ids)
                )
            )
            quantities[f"peak_{name}"] = entry

        return {
            "scenarios": SCENARIO_LABELS,
            "probabilistic": self.confidence_level is not None,
            "confidence_level": self.confidence_level,
            "members": self._member_count(),
            "quantities": quantities,
        }

    def _member_count(self) -> int:
        return min((len(run.members) for run in self.runs.values()), default=0)

    def _paired(self, reduce_fn: PairedReduction) -> object:
        """
        A quantity spanning the scenarios, with its spread across the members.

        Members are paired by index, so each reduction sees the scenarios as
        run with one and the same parameter set. Reducing per member before
        taking percentiles is what makes an interval on a difference
        meaningful; the difference of two separate intervals would not be.
        """
        count = self._member_count()
        if not count or self.confidence_level is None:
            return reduce_fn({s: run.point for s, run in self.runs.items()})
        return MemberSpread(self.confidence_level).of(
            [
                reduce_fn({s: run.members[index] for s, run in self.runs.items()})
                for index in range(count)
            ]
        )
