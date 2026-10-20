"""NHIS influenza care episodes (data.go.kr dataset 15089429) -> common format.

Writes:
- data/processed/nhis_daily.csv.gz: rows as published (day x province x sex x age).
- data/processed/nhis_weekly.csv: complete epi weeks, whole country, with
  totals over age and sex and explicit zeros.
"""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import requests

from common import RAW, REGIONS, epi_week, epi_week_start, season_of, write_tidy

DATASET = "15089429"
PORTAL = "https://www.data.go.kr"
RAW_DIR = RAW / "nhis"

SHEETS = {
    "외래입원주부상병": "setting=outpatient_or_inpatient",
    "입원주부상병": "setting=inpatient",
}
SEXES = {"남자": "male", "여자": "female"}
AGES = {
    "1. 0-5세": "0-5",
    "2. 6-11세": "6-11",
    "3. 12-17세": "12-17",
    "4. 18-44세": "18-44",
    "5. 45-64세": "45-64",
    "6. 65세 이상": "65+",
}


def download() -> Path:
    """Download the current release of the workbook, named by its cut-off date."""
    page = requests.get(f"{PORTAL}/data/{DATASET}/fileData.do", timeout=60).text
    detail_pk = page.split('name="publicDataDetailPk" value="')[1].split('"')[0]
    info = requests.post(
        f"{PORTAL}/tcs/dss/selectFileDataDownload.do",
        data={
            "publicDataDetailPk": detail_pk,
            "publicDataPk": DATASET,
            "atchFileId": "",
            "fileDetailSn": "1",
            "publicDataTyCode": "PR0051",
        },
        timeout=60,
    ).json()
    cutoff = info["dataSetFileDetailInfo"]["dataNm"].rsplit("_", 1)[1]
    path = RAW_DIR / f"nhis_influenza_{cutoff}.xlsx"
    if path.exists():
        return path
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        f"{PORTAL}/cmm/cmm/fileDownload.do",
        params={"atchFileId": info["atchFileId"], "fileDetailSn": info["fileDetailSn"]},
        timeout=600,
    )
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def read(path: Path) -> pd.DataFrame:
    frames = []
    for sheet, category in SHEETS.items():
        df = pd.read_excel(path, sheet_name=sheet, dtype={"SIDO": str})
        df["category"] = category
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["FST_DT"]).dt.date
    df["region_code"] = df["SIDO"].str.zfill(2)
    df["sex"] = df["GEN_NM"].map(SEXES)
    df["age_group"] = df["AGG_NM"].map(AGES).fillna("unknown")
    df["value"] = df["CNT"].astype(int)
    if df["sex"].isna().any():
        raise ValueError(
            f"unknown sex labels: {df.loc[df['sex'].isna(), 'GEN_NM'].unique()}"
        )
    return df[["date", "region_code", "sex", "age_group", "category", "value"]]


def _with_time(df: pd.DataFrame) -> pd.DataFrame:
    weeks = {d: epi_week(d) for d in df["date"].unique()}
    df["year"] = df["date"].map(lambda d: weeks[d][0])
    df["week"] = df["date"].map(lambda d: weeks[d][1])
    df["season"] = [season_of(y, w) for y, w in zip(df["year"], df["week"])]
    return df


def daily(df: pd.DataFrame) -> pd.DataFrame:
    df = _with_time(df.copy())
    df["date_start"] = df["date"]
    df["date_end"] = df["date"]
    df["period_type"] = "day"
    return _finish(df)


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Whole-country epi weeks with totals over sex and age. Drops partial weeks."""
    df = _with_time(df.copy())
    first, last = df["date"].min(), df["date"].max()
    keys = ["year", "week", "season", "category"]
    parts = []
    for sex_all in (False, True):
        for age_all in (False, True):
            by = (
                keys + ([] if sex_all else ["sex"]) + ([] if age_all else ["age_group"])
            )
            part = df.groupby(by, as_index=False)["value"].sum()
            if sex_all:
                part["sex"] = "all"
            if age_all:
                part["age_group"] = "all"
            parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    # Explicit zeros: every week x category x sex x age cell.
    grid = pd.MultiIndex.from_product(
        [
            out[["year", "week", "season"]].drop_duplicates().itertuples(index=False),
            out["category"].unique(),
            out["sex"].unique(),
            out["age_group"].unique(),
        ]
    ).to_frame(index=False, name=["yws", "category", "sex", "age_group"])
    grid[["year", "week", "season"]] = pd.DataFrame(grid.pop("yws").tolist())
    out = grid.merge(out, how="left").fillna({"value": 0})
    out["date_start"] = [epi_week_start(y, w) for y, w in zip(out["year"], out["week"])]
    out["date_end"] = out["date_start"] + timedelta(days=6)
    out = out[(out["date_start"] >= first) & (out["date_end"] <= last)]
    out["region_code"] = "00"
    out["period_type"] = "week"
    return _finish(out)


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df["source"] = "nhis"
    df["indicator"] = "flu_care_episodes"
    df["unit"] = "count"
    df["region_name"] = df["region_code"].map(REGIONS)
    df["value"] = df["value"].astype(int)
    return df.sort_values(["category", "date_start", "region_code", "sex", "age_group"])


def main() -> None:
    path = download()
    df = read(path)
    print(f"{path.name}: {len(df)} rows, {df['date'].min()} to {df['date'].max()}")
    print(df.groupby("category")["value"].sum().to_string())
    print(write_tidy(daily(df), "nhis_daily", compress=True))
    print(write_tidy(weekly(df), "nhis_weekly"))


if __name__ == "__main__":
    main()
