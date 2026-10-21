"""Read the model inputs built by scripts/model_inputs.py into a `Study`."""

import json
from dataclasses import dataclass

import pandas as pd

from flu_korea.calibration.study import Study
from flu_korea.season import Population, SeasonData
from flu_korea.settings import Settings
from flu_korea.timeline import SeasonTimeline

HOSPITAL_COLUMNS = ("Hospitalized Under 65", "Hospitalized 65+")
OPTIONAL_DATA_COLUMNS = ("Reported",)
DATA_COLUMNS = ("Vaccinations", *HOSPITAL_COLUMNS, *OPTIONAL_DATA_COLUMNS)


@dataclass(frozen=True)
class ModelInputs:
    """The files of `data/model/` that `settings` names."""

    settings: Settings

    def study(self) -> Study:
        """The study of the season, with its inputs read."""
        settings = self.settings
        timeline = SeasonTimeline.from_week_label(
            settings.first_week, settings.simulation_weeks
        )
        return Study(
            timeline=timeline,
            population=self.population(),
            data=self.season_data(timeline),
            vaccine_effectiveness=settings.vaccine_effectiveness,
            use_reported_cases=settings.calibrate_against_reported_cases,
        )

    def population(self) -> Population:
        """Population on 31-12-2016 and demographic rates (MOIS)."""
        path = self.settings.inputs_file
        inputs = json.loads(path.read_text(encoding="utf-8"))["population"]
        return Population(
            under_65=inputs["population_under_65"],
            aged_65_plus=inputs["population_65plus"],
            births_per_week=inputs["births_per_week"],
            aging_weekly_probability=inputs["aging_weekly_probability"],
            death_under_65_weekly_probability=inputs[
                "death_under_65_weekly_probability"
            ],
            death_65plus_weekly_probability=inputs["death_65plus_weekly_probability"],
        )

    def season_data(self, timeline: SeasonTimeline) -> SeasonData:
        """
        Load weekly vaccination, hospitalization, and reported incidence data.

        Hospitalizations are kept up to the last week of the calibration
        window only: they are the fitted observations. Vaccinations cover the
        whole file.
        """
        df = pd.read_csv(
            self.settings.data_file,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            # Only require columns that exist in the raw data file; optional
            # columns (e.g. `Reported`) may be absent.
            usecols=lambda col: col == "Week" or col in DATA_COLUMNS,
        ).where(pd.notna, None)

        week_parts = (
            df["Week"]
            .astype("string")
            .str.strip()
            .str.extract(r"^(?P<year>\d{4})-(?P<week>\d+)$")
        )
        df["year"] = pd.to_numeric(week_parts["year"], errors="coerce")
        df["week"] = pd.to_numeric(week_parts["week"], errors="coerce")
        df = df.dropna(subset=["year", "week"]).copy()
        df[["year", "week"]] = df[["year", "week"]].astype(int)

        df["week_idx"] = [
            timeline.week_idx(year, week)
            for year, week in zip(df["year"], df["week"], strict=True)
        ]
        df = df.dropna(subset=["week_idx"]).copy()
        df["week_idx"] = df["week_idx"].astype(int)
        numeric_columns = [c for c in DATA_COLUMNS if c in df.columns]
        df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors="coerce")

        if "Reported" not in df.columns:
            df["Reported"] = float("nan")

        vacc_by_week = dict(
            df.dropna(subset=["Vaccinations"])[["week_idx", "Vaccinations"]].itertuples(
                index=False,
                name=None,
            )
        )
        last_idx = timeline.week_idx_from_label(self.settings.calibration_last_week)
        fitted = df[df["week_idx"] <= last_idx].dropna(subset=list(HOSPITAL_COLUMNS))
        hospitalizations = [
            (int(week_idx), float(h_y), float(h_o))
            for week_idx, h_y, h_o in fitted[
                ["week_idx", *HOSPITAL_COLUMNS]
            ].itertuples(index=False, name=None)
        ]
        reported_cases = [
            (int(week_idx), float(reported_per_100k))
            for week_idx, reported_per_100k in df.dropna(subset=["Reported"])[
                ["week_idx", "Reported"]
            ].itertuples(index=False, name=None)
        ]

        max_week = max(vacc_by_week, default=0)
        weekly_doses = [float(vacc_by_week.get(i, 0.0)) for i in range(max_week + 1)]
        return SeasonData(weekly_doses, hospitalizations, reported_cases)
