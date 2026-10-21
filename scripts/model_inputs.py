"""Inputs of the 2016-2017 model, built from the processed data.

Writes:
- data/model/2016-2017.csv: one row per KDCA epi week from 2016 W36, with the
  persons aged 65+ vaccinated and the NHIS inpatient episodes of the <65 and
  65+ groups. The `Week` label (`YYYY-WW`) matches the file of
  FluVaccinationLoRegne.
- data/model/2016-2017.json: population and demographic rates, with their
  derivation.

See docs/model-inputs.md.
"""

import json
from datetime import timedelta

import pandas as pd

from common import PROCESSED, ROOT, epi_week, epi_week_start

OUT_DIR = ROOT / "data" / "model"
SEASON = "2016-2017"
FIRST_WEEK = (2016, 36)
WEEKS = 52
DAYS_PER_YEAR = 365.25

# Persons aged 65+ vaccinated after the last period of the press release
# (27 Oct 2016): the registry total minus the press-release periods. They are
# spread over W45-W48 with weights that halve each week (an assumption: the
# press release asks the rest to get the vaccine in November).
TAIL_WEEKS = ((2016, 45), (2016, 46), (2016, 47), (2016, 48))
TAIL_WEIGHTS = (8, 4, 2, 1)


def _tidy(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / f"{name}.csv", dtype={"region_code": str})


def weeks() -> pd.DataFrame:
    start = epi_week_start(*FIRST_WEEK)
    dates = [start + timedelta(weeks=i) for i in range(WEEKS)]
    labels = [epi_week(d) for d in dates]
    return pd.DataFrame(
        {
            "Week": [f"{y}-{w:02d}" for y, w in labels],
            "year": [y for y, _ in labels],
            "week": [w for _, w in labels],
            "week_start": dates,
        }
    )


def vaccinations(frame: pd.DataFrame) -> tuple[pd.Series, dict]:
    press = _tidy("nip_weekly_2016")
    press = press[press["indicator"] == "vaccinated"]
    registry = _tidy("nip_coverage")
    registry = registry[
        (registry["season"] == SEASON)
        & (registry["region_code"] == "00")
        & (registry["age_group"] == "65+")
        & (registry["sex"] == "all")
        & (registry["category"] == "target=65+;provider=all")
    ].set_index("indicator")["value"]
    final, target = registry["vaccinated"], registry["target_population"]
    by_week = {(int(r.year), int(r.week)): r.value for r in press.itertuples()}
    tail = final - sum(by_week.values())
    for key, weight in zip(TAIL_WEEKS, TAIL_WEIGHTS):
        by_week[key] = by_week.get(key, 0.0) + tail * weight / sum(TAIL_WEIGHTS)
    series = pd.Series(
        [by_week.get((y, w), 0.0) for y, w in zip(frame["year"], frame["week"])],
        index=frame.index,
    )
    provenance = {
        "registry_vaccinated_65plus": final,
        "registry_target_population_65plus": target,
        "press_release_vaccinated": sum(press["value"]),
        "tail_after_27_oct": tail,
        "tail_weeks": [f"{y}-{w:02d}" for y, w in TAIL_WEEKS],
        "tail_weights": list(TAIL_WEIGHTS),
    }
    return series, provenance


def admissions(frame: pd.DataFrame) -> pd.DataFrame:
    nhis = _tidy("nhis_weekly")
    nhis = nhis[(nhis["category"] == "setting=inpatient") & (nhis["sex"] == "all")]
    by_age = nhis.pivot(index="date_start", columns="age_group", values="value")
    by_age.index = pd.to_datetime(by_age.index).date
    under_65 = by_age[["0-5", "6-11", "12-17", "18-44", "45-64"]].sum(axis=1)
    out = pd.DataFrame(index=frame.index)
    out["Hospitalized Under 65"] = frame["week_start"].map(under_65)
    out["Hospitalized 65+"] = frame["week_start"].map(by_age["65+"])
    return out


def population() -> dict:
    """Population on 31-12-2016 and demographic rates from MOIS 2015-2016.

    - births: persons aged 0 on 31-12-2016 (a proxy: births of 2016 minus
      infant deaths and migration).
    - aging: persons aged 64 on 31-12-2015, who turn 65 during 2016.
    - deaths: the change of each group not explained by births and aging.
      Migration and registration changes are inside this residual, so the
      value for <65 is biased low.
    """
    mois = _tidy("mois_population")
    mois = mois[
        (mois["region_code"] == "00")
        & (mois["sex"] == "all")
        & (mois["age_group"] != "all")
        & mois["year"].isin([2015, 2016])
    ].copy()
    mois["age"] = mois["age_group"].str.rstrip("+").astype(int)
    pop = mois.pivot(index="age", columns="year", values="value")
    young = {y: int(pop.loc[:64, y].sum()) for y in (2015, 2016)}
    old = {y: int(pop.loc[65:, y].sum()) for y in (2015, 2016)}
    aging = int(pop.loc[64, 2015])
    births = int(pop.loc[0, 2016])
    deaths_old = old[2015] + aging - old[2016]
    deaths_young = young[2015] + births - aging - young[2016]
    weeks_per_year = DAYS_PER_YEAR / 7
    return {
        "date": "2016-12-31",
        "population_under_65": young[2016],
        "population_65plus": old[2016],
        "births_per_week": births / weeks_per_year,
        "aging_weekly_probability": aging / weeks_per_year / young[2016],
        "death_under_65_weekly_probability": deaths_young
        / weeks_per_year
        / young[2016],
        "death_65plus_weekly_probability": deaths_old / weeks_per_year / old[2016],
        "derivation": {
            "births_2016_proxy_age_0": births,
            "aging_2016_age_64_on_2015_12_31": aging,
            "deaths_65plus_2016_residual": deaths_old,
            "deaths_under_65_2016_residual": deaths_young,
            "population_2015": {"under_65": young[2015], "65plus": old[2015]},
        },
    }


def main() -> None:
    frame = weeks()
    doses, vaccination_provenance = vaccinations(frame)
    frame["Vaccinations"] = doses.round(0)
    frame = pd.concat([frame, admissions(frame)], axis=1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = [
        "Week",
        "week_start",
        "Vaccinations",
        "Hospitalized Under 65",
        "Hospitalized 65+",
    ]
    frame[columns].to_csv(OUT_DIR / f"{SEASON}.csv", index=False)
    meta = {
        "season": SEASON,
        "first_week": f"{FIRST_WEEK[0]}-{FIRST_WEEK[1]:02d}",
        "week_rule": "KDCA: Sunday to Saturday, week 1 contains 1 January",
        "population": population(),
        "vaccination": vaccination_provenance,
        "admissions": "NHIS inpatient episodes (ICD-10 J09-J11, primary or "
        "secondary diagnosis), by start date of the episode",
    }
    (OUT_DIR / f"{SEASON}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=float) + "\n"
    )
    print(frame[columns].to_string(index=False))
    print(json.dumps(meta["population"], indent=2, default=float))


if __name__ == "__main__":
    main()
