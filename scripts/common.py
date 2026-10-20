"""Common tidy format shared by every processed dataset.

Each processed file in `data/processed/` is a long-format CSV (UTF-8) with the
columns in `COLUMNS`. One row holds one value for one period, region, age
group, sex and category. See `docs/data-format.md`.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

COLUMNS = [
    "source",
    "indicator",
    "unit",
    "period_type",
    "date_start",
    "date_end",
    "year",
    "week",
    "season",
    "region_code",
    "region_name",
    "age_group",
    "sex",
    "category",
    "value",
]

PERIOD_TYPES = {"day", "week", "season", "year", "snapshot"}
SEXES = {"all", "male", "female"}

# First epi week of a KDCA influenza season.
SEASON_START_WEEK = 36

# Province codes of Statistics Korea (2-digit). "00" is the whole country.
REGIONS = {
    "00": "Korea",
    "11": "Seoul",
    "26": "Busan",
    "27": "Daegu",
    "28": "Incheon",
    "29": "Gwangju",
    "30": "Daejeon",
    "31": "Ulsan",
    "36": "Sejong",
    "41": "Gyeonggi",
    "42": "Gangwon",
    "43": "Chungbuk",
    "44": "Chungnam",
    "45": "Jeonbuk",
    "46": "Jeonnam",
    "47": "Gyeongbuk",
    "48": "Gyeongnam",
    "49": "Jeju",
    "50": "Jeju",
    # Codes in use after the special self-governing province reforms.
    "51": "Gangwon",
    "52": "Jeonbuk",
}


def _sunday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def epi_week_start(year: int, week: int) -> date:
    """Sunday that opens a KDCA epi week.

    KDCA week 1 is the Sunday-to-Saturday week that contains 1 January, as the
    date ranges printed in the sentinel bulletins show. This differs from the
    MMWR rule when 1 January falls on Thursday to Saturday.
    """
    return _sunday_on_or_before(date(year, 1, 1)) + timedelta(weeks=week - 1)


def epi_week(d: date) -> tuple[int, int]:
    """KDCA epi week (year, week) of a date: the inverse of `epi_week_start`."""
    sunday = _sunday_on_or_before(d)
    year = (
        sunday.year + 1 if epi_week_start(sunday.year + 1, 1) <= sunday else sunday.year
    )
    return year, (sunday - epi_week_start(year, 1)).days // 7 + 1


def mmwr_week_start(year: int, week: int) -> date:
    """Sunday that opens an MMWR week (week 1 has at least four days in January).

    WHO FluNet labels weeks with this rule. Use it only to read such labels.
    """
    return _sunday_on_or_before(date(year, 1, 4)) + timedelta(weeks=week - 1)


def season_of(year: int, week: int) -> str:
    """Season label ("2016-2017") of an epi week. Seasons start at week 36."""
    start = year if week >= SEASON_START_WEEK else year - 1
    return f"{start}-{start + 1}"


def write_tidy(df: pd.DataFrame, name: str, compress: bool = False) -> Path:
    """Validate a frame against the common format and write it as CSV.

    `compress` writes `<name>.csv.gz` for large files.
    """
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")
    df = df[COLUMNS]
    bad_period = set(df["period_type"]) - PERIOD_TYPES
    if bad_period:
        raise ValueError(f"{name}: unknown period_type {bad_period}")
    bad_sex = set(df["sex"]) - SEXES
    if bad_sex:
        raise ValueError(f"{name}: unknown sex {bad_sex}")
    bad_region = set(df["region_code"].astype(str)) - set(REGIONS)
    if bad_region:
        raise ValueError(f"{name}: unknown region_code {bad_region}")
    if df[["source", "indicator", "date_start", "region_code"]].isna().any().any():
        raise ValueError(f"{name}: empty key fields")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / (f"{name}.csv.gz" if compress else f"{name}.csv")
    df.to_csv(path, index=False)
    return path
