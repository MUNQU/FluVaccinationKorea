"""Figures of a calibration run and of the scenario comparison."""

import math
import pathlib
from dataclasses import dataclass

import matplotlib.pyplot as plt
from commol import CalibrationResult, Predictive, SimulationPlotter

from flu_korea.model.compartments import ACCUMULATOR_IDS, BIN_NAMES, DISEASE_BINS
from flu_korea.reporting.ensemble import RunEnsemble
from flu_korea.reporting.observed import ObservedData
from flu_korea.scenarios.comparison import (
    BASELINE_SCENARIO,
    NO_VACCINATION_SCENARIO,
    SCENARIO_LABELS,
    ScenarioComparison,
)

SCENARIO_COLOURS = {BASELINE_SCENARIO: "#1f77b4", NO_VACCINATION_SCENARIO: "#d62728"}


@dataclass(frozen=True)
class Figures:
    """The figures of one directory, compared with the same observed data."""

    directory: pathlib.Path
    observed: ObservedData

    @staticmethod
    def _panel_layout(count: int) -> tuple[int, int]:
        """Subplot grid for a number of panels, as the calibration figures use."""
        if count == 1:
            return (1, 1)
        if count == 2:
            return (1, 2)
        if count <= 4:
            return (2, 2)
        columns = math.ceil(math.sqrt(count))
        return (math.ceil(count / columns), columns)

    def observed_fit(self, ensemble: RunEnsemble, name: str = "observed_fit") -> None:
        """
        Model against data, one panel per observed series.

        The commol plotter draws one model output or bin per panel, and the 65+
        series is the sum of two outputs, so this figure is drawn here.
        """
        labels = self.observed.labels()
        figure, axes = plt.subplots(
            1, len(labels), figsize=(5.5 * len(labels), 3.6), squeeze=False
        )
        for axis, (outputs, label) in zip(axes[0], labels.items(), strict=True):
            central, lower, upper = ensemble.weekly_band(tuple(sorted(outputs)), True)
            weeks = range(len(central))
            axis.plot(weeks, central, label="Model")
            if lower is not None and upper is not None:
                axis.fill_between(weeks, lower, upper, alpha=0.2, linewidth=0)
            observed_weeks, values = self.observed.for_panel(tuple(outputs))
            axis.scatter(
                observed_weeks, values, color="black", s=14, label="Observed", zorder=5
            )
            axis.set_title(label, fontsize=10)
            ticks = list(weeks)[::4]
            axis.set_xticks(ticks)
            axis.set_xticklabels(
                [ensemble.timeline.week_label(week) for week in ticks],
                rotation=45,
                ha="right",
                fontsize=8,
            )
            axis.legend(fontsize=8)
        figure.tight_layout()
        figure.savefig(self.directory / f"{name}.png", dpi=150)
        plt.close(figure)

    def calibration(
        self,
        ensemble: RunEnsemble,
        calibration_result: CalibrationResult | Predictive,
    ) -> None:
        """The fit to the data, every bin together, and one figure per group."""
        if ensemble.confidence_level is None:
            plotter = SimulationPlotter(ensemble.simulation, ensemble.point)
        else:
            plotter = SimulationPlotter(
                ensemble.simulation,
                ensemble.point,
                confidence_level=ensemble.confidence_level,
            )

        def plot(name: str, **options: object) -> None:
            plotter.plot_series(
                output_file=str(self.directory / f"{name}.png"),
                observed_data=self.observed.points,
                calibration_result=calibration_result,
                position_label=ensemble.timeline.step_label,
                tick_every=4 * ensemble.timeline.axis.steps_per_week,
                **options,
            )

        self.observed_fit(ensemble)
        plot("all_bins", show_legend=False, x_label="Week")
        for group, outputs in plotter.simulation.group_outputs(
            [*DISEASE_BINS, *ACCUMULATOR_IDS]
        ).items():
            plot(group, series=outputs)

    def scenarios(self, comparison: ScenarioComparison) -> None:
        """
        Overlay the scenarios on every subpopulation, one figure per group.

        Each figure holds the group total followed by one panel per stratified
        output, the same breakdown the calibration figures show.
        """
        baseline = comparison.baseline
        weeks = baseline.timeline.week_labels()

        for group in (*DISEASE_BINS, *ACCUMULATOR_IDS):
            outputs = baseline.simulation.outputs_for(group)
            windowed = group in ACCUMULATOR_IDS
            name = BIN_NAMES.get(group, group.replace("_", " ").capitalize())
            panels: list[tuple[str, tuple[str, ...]]] = [
                (f"{name} (total)", tuple(outputs)),
                *((output, (output,)) for output in outputs),
            ]

            rows, columns = self._panel_layout(len(panels))
            figure, axes = plt.subplots(
                rows, columns, figsize=(5.5 * columns, 3.4 * rows), squeeze=False
            )
            flat = [axis for row in axes for axis in row]

            for axis, (title, source_ids) in zip(flat, panels, strict=False):
                for scenario, ensemble in comparison.runs.items():
                    central, lower, upper = ensemble.weekly_band(source_ids, windowed)
                    axis.plot(
                        range(len(central)),
                        central,
                        label=SCENARIO_LABELS[scenario],
                        color=SCENARIO_COLOURS[scenario],
                    )
                    if lower is not None and upper is not None:
                        axis.fill_between(
                            range(len(central)),
                            lower,
                            upper,
                            color=SCENARIO_COLOURS[scenario],
                            alpha=0.2,
                            linewidth=0,
                        )
                observed_weeks, observed_values = self.observed.for_panel(source_ids)
                if observed_weeks:
                    axis.scatter(
                        observed_weeks,
                        observed_values,
                        label="Observed",
                        color="black",
                        s=14,
                        alpha=0.7,
                        zorder=5,
                    )
                axis.set_title(title, fontsize=10)
                axis.set_xticks(range(0, len(weeks), 6))
                axis.set_xticklabels(weeks[::6], rotation=45, ha="right", fontsize=8)

            for axis in flat[len(panels) :]:
                axis.set_visible(False)

            handles, labels = flat[0].get_legend_handles_labels()
            figure.legend(handles, labels, loc="lower center", ncol=3)
            figure.suptitle(f"{name} per week" if windowed else name)
            figure.tight_layout(rect=(0, 0.06, 1, 1))
            figure.savefig(self.directory / f"{group}.png", dpi=150)
            plt.close(figure)
