"""Convert KDCA sentinel ILI data to the common format.

Inputs (from `kdca_sentinel_download.py`):
- `data/raw/kdca_sentinel/db/*.json`: dportal statistics table (latest revision).
- `data/processed/kdca_sentinel_bulletins.csv`: values read from the weekly
  bulletins (`kdca_sentinel_bulletins.py`), one row per value and report week.

Outputs in `data/processed/`:
- `kdca_sentinel_ili.csv`: weekly ILI per 1,000 outpatients, national and by
  age, plus provinces when published. dportal values first; bulletin values
  only fill the age data of 2013-2014 to 2016-2017, which dportal lacks.
- `kdca_sentinel_threshold.csv`: epidemic threshold of each season.
- `kdca_sentinel_hospital.csv`: influenza inpatients of the hospital ARI
  network and SARI counts, latest bulletin value of each week.
- `kdca_sentinel_virus.csv`: clinic-level influenza virus tests, latest
  bulletin value of each week.

Usage: .venv/bin/python -E -s scripts/kdca_sentinel_process.py
"""

import json
import re
from datetime import timedelta

import pandas as pd

from common import PROCESSED, RAW, REGIONS, epi_week_start, write_tidy

DB = RAW / "kdca_sentinel" / "db"
SOURCE = "kdca_sentinel"
FIRST_DB_AGE_SEASON = "2017-2018"

# dportal province codes -> Statistics Korea codes. "05" (Gwangju) and "13"
# (Jeonnam) are out of use and hold only zeros. "18" (merged Jeonnam-Gwangju,
# 2026) has no code in common.REGIONS yet, so it is skipped too.
DB_SIDO_TO_REGION = {
    "01": "11",
    "02": "26",
    "03": "27",
    "04": "28",
    "06": "30",
    "07": "31",
    "17": "36",
    "08": "41",
    "09": "51",
    "10": "43",
    "11": "44",
    "12": "52",
    "14": "47",
    "15": "48",
    "16": "50",
}


def age_label(title: str) -> str:
    title = title.replace(" ", "").replace("세", "")
    if title.startswith("전체"):
        return "all"
    if title.endswith("이상"):
        return title.replace("이상", "") + "+"
    return title


def week_rows(value: dict, season_start: int) -> list[tuple[int, int, str, str]]:
    """(year, week, row title, value) for every non-empty cell."""
    weeks = [int(h["TITLE"].replace("주", "")) for h in value["headerList"]]
    out = []
    for row in value["data"]:
        cells = row["VALUE"].split("`")
        for week, cell in zip(weeks, cells):
            year = season_start if week >= 36 else season_start + 1
            out.append((year, week, row["TITLE"], cell))
    return out


def tidy(
    year: int, week: int, region: str, age: str, value: float, category: str = "all"
) -> dict:
    start = epi_week_start(year, week)
    season = year if week >= 36 else year - 1
    return {
        "source": SOURCE,
        "indicator": "ili_per_1000",
        "unit": "per_1000",
        "period_type": "week",
        "date_start": start.isoformat(),
        "date_end": (start + timedelta(days=6)).isoformat(),
        "year": year,
        "week": week,
        "season": f"{season}-{season + 1}",
        "region_code": region,
        "region_name": REGIONS[region],
        "age_group": age,
        "sex": "all",
        "category": category,
        "value": value,
    }


def number(cell: str) -> float | None:
    cell = cell.strip()
    return float(cell) if re.fullmatch(r"\d+(\.\d+)?", cell) else None


def load_all_seasons() -> list[dict]:
    """National ILI of every season from the all-season query. Rows are
    titled "전체(2005-2006절기)". Zeros are missing weeks: a national ILI of
    0.0 does not occur (all seasons before 2003-2004 are zeros)."""
    value = json.loads((DB / "influ_all_total.json").read_text(encoding="utf-8"))
    rows = []
    for row in value["data"]:
        start = int(re.search(r"\((\d{4})-", row["TITLE"]).group(1))
        one = {"headerList": value["headerList"], "data": [row]}
        for year, week, _, cell in week_rows(one, start):
            v = number(cell)
            if v:
                rows.append(tidy(year, week, "00", "all", v))
    return rows


def load_db() -> pd.DataFrame:
    rows = load_all_seasons()
    for path in sorted(DB.glob("influ_*_*_*.json")):
        start, kind = re.fullmatch(
            r"influ_(\d{4})_\d{4}_(\w+)\.json", path.name
        ).groups()
        start = int(start)
        value = json.loads(path.read_text(encoding="utf-8"))
        if kind == "total":
            continue  # national series comes from the all-season query
        if kind.startswith("sido"):
            region = DB_SIDO_TO_REGION.get(kind[4:])
            if region is None:
                continue
        else:
            region = "00"
        for year, week, title, cell in week_rows(value, start):
            v = number(cell)
            if v is None:
                continue
            age = "all" if kind != "age" else age_label(title)
            rows.append(tidy(year, week, region, age, v))
    df = pd.DataFrame(rows)
    # Before the 2017-2018 season dportal's age table is corrupt: mostly
    # zeros, and in 2013-2014 the 65+ rate is above the school-age rate. The
    # bulletins replace it.
    by_age = df["age_group"] != "all"
    return df[~(by_age & (df["season"] < FIRST_DB_AGE_SEASON))]


def agrees(bulletin: float, db: float) -> bool:
    return abs(bulletin - db) <= max(0.3, 0.1 * db)


def latest(df: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """Keep the value of the latest bulletin (most revised) for each key."""
    df = df.sort_values("reported_in").drop_duplicates(key, keep="last")
    return df.drop(columns="reported_in").assign(category="all")


def main() -> None:
    db = load_db()
    frames = [db]
    bulletins_path = PROCESSED / "kdca_sentinel_bulletins.csv"
    if bulletins_path.exists():
        b = pd.read_csv(
            bulletins_path,
            dtype={"region_code": str},
            keep_default_na=False,
            na_values=[""],
        )
        b["reported_in"] = b["category"].str.extract(r"reported_in=(\d{4}-\d{2})")[0]
        b["week"] = b["week"].astype("Int64")
        key = ["year", "week", "region_code", "age_group"]

        # A bulletin table is trusted for a week only if its national value
        # agrees with dportal's national value for that week.
        ili = b[b["indicator"] == "ili_per_1000"].copy()
        national = db[(db["region_code"] == "00") & (db["age_group"] == "all")]
        national = national.set_index(["year", "week"])["value"]
        totals = ili[ili["age_group"] == "all"].set_index(
            ["reported_in", "year", "week"]
        )["value"]
        checked = totals.reset_index().assign(
            db=lambda d: [national.get((y, w)) for y, w in zip(d["year"], d["week"])]
        )
        checked = checked.dropna(subset=["db"])
        checked["ok"] = [agrees(v, d) for v, d in zip(checked["value"], checked["db"])]
        agree = checked["ok"].sum()
        print(f"bulletin vs dportal national ILI: {agree}/{len(checked)} agree")
        good = set(
            map(tuple, checked[checked["ok"]][["reported_in", "year", "week"]].values)
        )
        bad = set(
            map(tuple, checked[~checked["ok"]][["reported_in", "year", "week"]].values)
        )
        ages = ili[ili["age_group"] != "all"]
        trusted = [
            (r, y, w) in good or ((r, y, w) not in bad and (y, w) not in national.index)
            for r, y, w in zip(ages["reported_in"], ages["year"], ages["week"])
        ]
        ages = latest(ages[trusted], key)
        # From 2017-2018 on, dportal has every age group; bulletin rows would
        # only add stray old-style bands. Exception: weeks where dportal gives
        # 0 for every age band while the national rate is above 0 (2019 W17).
        # The bulletins replace those weeks.
        db_by_age = db["age_group"] != "all"
        week_sum = (
            db[db_by_age & (db["region_code"] == "00")]
            .groupby(["year", "week"])["value"]
            .sum()
        )
        empty = {yw for yw, s in week_sum.items() if s == 0 and national.get(yw, 0) > 0}
        db_empty = [(y, w) in empty for y, w in zip(db["year"], db["week"])]
        frames[0] = db[~(db_by_age & pd.Series(db_empty, index=db.index))]
        refill = pd.Series(
            [(y, w) in empty for y, w in zip(ages["year"], ages["week"])],
            index=ages.index,
        )
        ages = ages[(ages["season"] < FIRST_DB_AGE_SEASON) | refill]
        print(f"dportal age weeks replaced by bulletins: {sorted(empty)}")
        frames.append(ages)

        threshold = b[b["indicator"] == "ili_epidemic_threshold"]
        write_tidy(
            latest(threshold, ["season"]).sort_values("season"),
            "kdca_sentinel_threshold",
        )

        hospital = b[
            b["indicator"].isin(
                ["hosp_flu_inpatients", "sari_new_patients", "sari_flu_positive"]
            )
        ]
        hospital = latest(hospital, ["indicator", *key]).sort_values(
            ["indicator", "date_start"]
        )
        print(write_tidy(hospital, "kdca_sentinel_hospital"), len(hospital))

        virus = b[b["indicator"].str.startswith("flu_")]
        virus = latest(virus, ["indicator", *key]).sort_values(
            ["indicator", "date_start"]
        )
        print(write_tidy(virus, "kdca_sentinel_virus"), len(virus))
    ili = pd.concat(frames, ignore_index=True)
    ili = ili.sort_values(["region_code", "age_group", "date_start"])
    print(write_tidy(ili, "kdca_sentinel_ili"), len(ili))


if __name__ == "__main__":
    main()
