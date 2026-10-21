"""Observed data arranged for comparison with model outputs."""

from dataclasses import dataclass

from commol import ObservedDataPoint

from flu_korea.timeline import AXIS


@dataclass(frozen=True)
class ObservedData:
    """The observations of a fit, grouped by the outputs they are compared with."""

    points: list[ObservedDataPoint]

    @staticmethod
    def outputs_of(point: ObservedDataPoint) -> frozenset[str]:
        """Model outputs an observation is compared with (their sum)."""
        return frozenset(point.outputs or [point.label])

    def labels(self) -> dict[frozenset[str], str]:
        """The label of each observed series, keyed by its outputs."""
        return {self.outputs_of(point): point.label for point in self.points}

    def series(self) -> dict[frozenset[str], dict[int, float]]:
        """Observed values keyed by their set of outputs, then by week."""
        series: dict[frozenset[str], dict[int, float]] = {}
        for point in self.points:
            series.setdefault(self.outputs_of(point), {})[
                AXIS.step_to_week_idx(point.at)
            ] = point.value
        return series

    def for_panel(self, outputs: tuple[str, ...]) -> tuple[list[int], list[float]]:
        """
        Observed weeks and values for a panel.

        A panel showing several outputs is compared against the sum of the
        observed series that fit inside it. An observed series counts only if
        all its outputs are in the panel (the 65+ series covers `nv` and `v`),
        and the panel gets data only if those series cover outputs of every
        observed kind in it; an output with no data of its own, such as one
        whose transition does not exist for that group, contributes nothing.
        Only weeks present in every contributing series can be summed.
        """
        panel = set(outputs)
        series = self.series()
        inside = [weeks for key, weeks in series.items() if key <= panel]
        observed_outputs = set().union(*series) if series else set()
        covered = set().union(*(key for key in series if key <= panel))
        if not inside or (panel & observed_outputs) != covered:
            return [], []
        weeks = sorted(set.intersection(*(set(weeks) for weeks in inside)))
        return weeks, [sum(weeks_of[week] for weeks_of in inside) for week in weeks]
