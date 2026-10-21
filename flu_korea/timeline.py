"""Time of the model: the axis of the steps and the calendar of a season."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from commol import AxisUnits

from flu_korea.commol_gaps import WindowGrid
from scripts.common import epi_week, epi_week_start

DAYS_PER_WEEK = 7
ENGINE = "DifferenceEquations"
# Unit of one simulation step. Examples: "day", "hour", "minute".
STEP_UNIT = "hour"


class ModelAxis:
    """The steps of the model, their weeks, and the rates of one step."""

    def __init__(self, units: AxisUnits) -> None:
        self.units = units
        self.steps_per_hour = units.steps(1, "hour")
        self.steps_per_day = int(units.steps(1, "day"))
        self.steps_per_week = int(units.steps(1, "week"))
        self._weeks = WindowGrid(self.steps_per_week)

    def week_start_step(self, week_idx: int) -> int:
        """First simulation step belonging to `week_idx`."""
        return int(self._weeks.start(week_idx))

    def week_end_step(self, week_idx: int) -> int:
        """
        Step closing `week_idx`, so that the window [step - steps_per_week,
        step] covers exactly that week. Weekly observations are anchored here.
        """
        return int(self._weeks.end(week_idx))

    def step_to_week_idx(self, step: float) -> int:
        """
        Week a step belongs to: the exact inverse of `week_end_step`, and the
        containing week for any step in between (step 0 maps to week 0).
        """
        return self._weeks.index(step)

    def rate_from_mean_days(self, days: float) -> float:
        return self.units.rate_from_mean_span(days, "day")

    def rate_from_weekly_probability(self, probability: float) -> float:
        return self.units.rate_from_probability(probability, 1, "week")


AXIS = ModelAxis(AxisUnits(step_unit=STEP_UNIT, engine=ENGINE))
STEPS_PER_HOUR = AXIS.steps_per_hour
STEPS_PER_DAY = AXIS.steps_per_day
STEPS_PER_WEEK = AXIS.steps_per_week


@dataclass(frozen=True)
class SeasonTimeline:
    """
    Calendar of one simulated season.

    Week index 0 is the KDCA epi week that starts on `origin`. KDCA weeks run
    Sunday to Saturday and some years have 53 of them, so labels come from
    dates, not from a week count.
    """

    origin: date
    simulation_weeks: int
    axis: ModelAxis = field(default=AXIS, compare=False)

    @classmethod
    def from_week_label(cls, label: str, simulation_weeks: int) -> "SeasonTimeline":
        """The season that starts on the KDCA epi week 'YYYY-WW'."""
        year, week = (int(part) for part in label.split("-"))
        return cls(epi_week_start(year, week), simulation_weeks)

    @property
    def final_step(self) -> int:
        return self.simulation_weeks * self.axis.steps_per_week

    def week_idx(self, year: int, week: int) -> int | None:
        """Week index of a KDCA year-week, or None if before the origin."""
        days = (epi_week_start(year, week) - self.origin).days
        return days // DAYS_PER_WEEK if days >= 0 else None

    def week_idx_from_label(self, label: str) -> int | None:
        """Week index of a 'YYYY-WW' label, or None if before the origin."""
        year, week = (int(part) for part in label.split("-"))
        return self.week_idx(year, week)

    def week_label(self, week_idx: int) -> str:
        """KDCA year-week label of a week index (e.g. '2016-37')."""
        year, week = epi_week(self.origin + timedelta(weeks=week_idx))
        return f"{year}-{week:02d}"

    def step_label(self, step: float) -> str:
        """Year-week label of the week a simulation step belongs to."""
        return self.week_label(self.axis.step_to_week_idx(step))

    def week_labels(self) -> list[str]:
        """Label of every simulated week."""
        return [self.week_label(week) for week in range(self.simulation_weeks)]

    def week_anchors(self, series_length: int) -> list[int]:
        """
        Week-end steps a series of this length covers.

        A trajectory is not always the full season: an ensemble median stops at
        the last observation, which is earlier than the simulation horizon.
        """
        ends = (self.axis.week_end_step(w) for w in range(self.simulation_weeks))
        return [step for step in ends if step < series_length]

    def output_steps(self, resolution: str) -> list[int]:
        """Steps the reported series are sampled at, for each resolution."""
        if resolution == "step":
            return list(range(self.final_step + 1))
        if resolution == "daily":
            return list(range(0, self.final_step + 1, self.axis.steps_per_day))
        return [self.axis.week_end_step(w) for w in range(self.simulation_weeks)]
