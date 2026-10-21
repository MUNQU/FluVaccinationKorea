"""Values that describe the season: population and weekly data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Population:
    """Population on 31-12-2016 and demographic rates (MOIS)."""

    under_65: int
    aged_65_plus: int
    births_per_week: float
    aging_weekly_probability: float
    death_under_65_weekly_probability: float
    death_65plus_weekly_probability: float

    @property
    def total(self) -> int:
        return self.under_65 + self.aged_65_plus


@dataclass(frozen=True)
class SeasonData:
    """
    Weekly data of the season, by week index (see `timeline`).

    - weekly_doses: persons aged 65+ vaccinated in each week, from week 0.
    - hospitalizations: (week, admissions <65, admissions 65+), up to the
      last week of the calibration window.
    - reported_cases: (week, reported cases per 100,000).
    """

    weekly_doses: list[float]
    hospitalizations: list[tuple[int, float, float]]
    reported_cases: list[tuple[int, float]]
