"""Vaccination of the 65+: weekly doses as a pulse series, and the transitions."""

from dataclasses import dataclass

from commol import ModelBuilder

from flu_korea.model.compartments import VACCINATED_BINS
from flu_korea.model.conditions import O65, StratifiedRate
from flu_korea.timeline import AXIS, DAYS_PER_WEEK

VACCINATION_HOURS_PER_DAY = 8
VACCINATION_EFFECT_DELAY_DAYS = 7
VACCINATION_EFFECT_DELAY_STEPS = VACCINATION_EFFECT_DELAY_DAYS * AXIS.steps_per_day

# A dose moves a person aged 65+ from `nv` to `v`.
VACCINATION_CONDITIONS = [
    *O65,
    {"stratification": "vaccination", "category": "nv", "to": "v"},
]


@dataclass(frozen=True)
class Vaccination:
    """The doses of the season, given to the non-vaccinated 65+."""

    weekly_doses: list[float]

    def dose_series(self) -> list[tuple[float, float]]:
        """
        Doses per step, as (step, doses) points of a pulse series.

        Each week's doses are given in eight daily hours, every day of the
        week, and take effect VACCINATION_EFFECT_DELAY_DAYS later (as in
        LoRegne).
        """
        if AXIS.steps_per_hour >= 1:
            active_offsets = [
                int(hour * AXIS.steps_per_hour)
                for hour in range(VACCINATION_HOURS_PER_DAY)
            ]
        else:
            active_offsets = [0]

        pulses_per_week = DAYS_PER_WEEK * len(active_offsets)
        return [
            (
                float(
                    AXIS.week_start_step(week)
                    + day * AXIS.steps_per_day
                    + offset
                    + VACCINATION_EFFECT_DELAY_STEPS
                ),
                weekly_count / pulses_per_week,
            )
            for week, weekly_count in enumerate(self.weekly_doses)
            for day in range(DAYS_PER_WEEK)
            for offset in active_offsets
        ]

    def add_parameter_to(self, builder: ModelBuilder) -> ModelBuilder:
        return builder.add_parameter(
            id="doses",
            value=self.dose_series(),
            mode="pulse",
            description="Vaccine doses given to 65+ per step",
        )

    def add_to(self, builder: ModelBuilder) -> ModelBuilder:
        """
        Move the doses of each step from `nv` to `v` among the 65+.

        A dose goes to a non-vaccinated person who is not infected and not in
        hospital, so it splits between S and R in proportion to their size. A
        dose given to R changes no outcome, but keeps the vaccinated share of
        the group equal to the coverage.
        """
        eligible = " + ".join(f"{bin_id}_o65_nv" for bin_id in VACCINATED_BINS)
        for bin_id in VACCINATED_BINS:
            rate = f"campaign * doses * {bin_id}_o65_nv / ({eligible})"
            builder.add_transition(
                id=f"vaccination_{bin_id}",
                source=[bin_id],
                target=[bin_id],
                stratified_rates=[StratifiedRate(VACCINATION_CONDITIONS, rate).entry()],
            )
        return builder
