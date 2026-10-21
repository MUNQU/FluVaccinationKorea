"""Observed series the model is fitted to."""

from dataclasses import dataclass

from commol import ObservedDataPoint

from flu_korea.model.compartments import O65_GROUPS
from flu_korea.model.parameters import CASE_REPORTING_RATE_PARAMETER
from flu_korea.season import SeasonData
from flu_korea.timeline import AXIS

# Observed series: one per age group. The 65+ series is the sum of the
# vaccinated and non-vaccinated admissions, because NHIS has no vaccination
# status.
HOSPITAL_OBSERVATIONS = (
    ("hospital_admissions_y65", ("hospital_admissions_y65",)),
    (
        "hospital_admissions_o65",
        tuple(f"hospital_admissions_o65_{v}" for v in O65_GROUPS),
    ),
)

# Observation normalization makes every series residual dimensionless. Weights
# therefore express actual relative importance rather than compensating for raw
# count magnitude: reported incidence has the same baseline importance as a
# hospital-admission series, with additional peak emphasis.
REPORTED_CASE_OBSERVATION_WEIGHT = 1.0
# The multiplier is applied before SSE, so the peak residual receives 5x the
# baseline weight and a 25x squared-loss contribution.
PEAK_REPORTED_CASE_WEIGHT_MULTIPLIER = 4.0
PEAK_REPORTED_CASE_WEIGHT_POWER = 2.0


@dataclass(frozen=True)
class Observations:
    """The observed series of a season, as the calibration reads them."""

    data: SeasonData
    population_size: float

    def points(self, use_reported_cases: bool) -> list[ObservedDataPoint]:
        """Admissions, then reported cases when they take part in the fit."""
        points = self.hospitalizations()
        if use_reported_cases:
            points.extend(self.reported_cases())
        return points

    def hospitalizations(self) -> list[ObservedDataPoint]:
        # Column order of the data matches the order of HOSPITAL_OBSERVATIONS.
        return [
            ObservedDataPoint(
                at=AXIS.week_end_step(week_idx),
                label=label,
                outputs=list(outputs),
                value=value,
                window=AXIS.steps_per_week,
            )
            for week_idx, *values in self.data.hospitalizations
            for (label, outputs), value in zip(
                HOSPITAL_OBSERVATIONS, values, strict=True
            )
        ]

    def reported_cases(self) -> list[ObservedDataPoint]:
        rows = list(self.data.reported_cases)
        max_reported = max(
            (reported_per_100k for _, reported_per_100k in rows), default=0.0
        )
        incidence_outputs = (
            "infection_incidence_y65",
            *(f"infection_incidence_o65_{v}" for v in O65_GROUPS),
        )

        observed: list[ObservedDataPoint] = []
        for week_idx, reported_per_100k in rows:
            reported_count = reported_per_100k * self.population_size / 100_000.0
            peak_multiplier = 0.0
            if max_reported > 0.0:
                peak_multiplier = (reported_per_100k / max_reported) ** (
                    PEAK_REPORTED_CASE_WEIGHT_POWER
                )
            weight = REPORTED_CASE_OBSERVATION_WEIGHT * (
                1.0 + PEAK_REPORTED_CASE_WEIGHT_MULTIPLIER * peak_multiplier
            )
            observed.append(
                ObservedDataPoint(
                    at=AXIS.week_end_step(week_idx),
                    label="infection_incidence",
                    outputs=list(incidence_outputs),
                    value=reported_count,
                    weight=weight,
                    factor_id=CASE_REPORTING_RATE_PARAMETER.id,
                    window=AXIS.steps_per_week,
                )
            )
        return observed
