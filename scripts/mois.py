"""MOIS resident registration population (jumin.mois.go.kr) -> common format.

Downloads the year-end population by single year of age, for the whole country
and each province, one CSV per year and sex split. Writes
data/processed/mois_population.csv.
"""

import io
import re
import time
from datetime import date

import pandas as pd
import requests

from common import RAW, REGIONS, write_tidy

URL = "https://jumin.mois.go.kr/downloadCsvAge.do"
RAW_DIR = RAW / "mois"
FIRST_YEAR = 2008
# Column labels: "2016년_계_0세", "2016년_남_100세 이상", ...
COLUMN = re.compile(r"(\d{4})년_(계|남|여)_(.+)")
SEXES = {"계": "all", "남": "male", "여": "female"}


def download(year: int, split: str) -> bytes:
    """Year-end population by single year of age. `split` is "sum" or "gender".

    The portal allows only one of the two for single-year ages.
    """
    path = RAW_DIR / f"mois_population_{year}_{split}.csv"
    if path.exists():
        return path.read_bytes()
    form = {
        "sltOrgType": "1",
        "sltOrgLvl1": "A",
        "sltOrgLvl2": "",
        "gender": "gender" if split == "gender" else "",
        "sum": "sum" if split == "sum" else "",
        "sltUndefType": "",
        "searchYearStart": str(year),
        "searchMonthStart": "12",
        "searchYearEnd": str(year),
        "searchMonthEnd": "12",
        "sltOrderType": "1",
        "sltOrderValue": "ASC",
        "sltArgTypes": "1",
        "sltArgTypeA": "0",
        "sltArgTypeB": "100",
        "category": "year",
    }
    response = requests.post(
        URL, params={"searchYearMonth": "year", "xlsStats": "1"}, data=form, timeout=120
    )
    response.raise_for_status()
    if "attachment" not in response.headers.get("Content-Disposition", ""):
        raise RuntimeError(f"{year} {split}: no file returned")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    time.sleep(1)
    return response.content


def parse(content: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(content), encoding="euc-kr", dtype=str, thousands=",")
    df = df.melt(id_vars=df.columns[0], var_name="column", value_name="value")
    df["region_code"] = df.iloc[:, 0].str.extract(r"\((\d{2})\d{8}\)")[0]
    parts = df["column"].str.extract(COLUMN)
    df["year"] = parts[0].astype(int)
    df["sex"] = parts[1].map(SEXES)
    label = parts[2]
    # "연령구간인구수" (sum over the selected ages) duplicates "총인구수" for 0-100+.
    df = df[label != "연령구간인구수"].copy()
    label = label[df.index]
    df["age_group"] = (
        label.str.replace("총인구수", "all")
        .str.replace("세 이상", "+")
        .str.replace("세", "")
    )
    df["value"] = df["value"].str.replace(",", "").astype(int)
    return df[["region_code", "year", "sex", "age_group", "value"]]


def main() -> None:
    last_year = date.today().year - 1
    frames = []
    for year in range(FIRST_YEAR, last_year + 1):
        for split in ("sum", "gender"):
            frames.append(parse(download(year, split)))
    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    df["source"] = "mois"
    df["indicator"] = "population"
    df["unit"] = "persons"
    df["period_type"] = "snapshot"
    df["date_start"] = [date(y, 12, 31) for y in df["year"]]
    df["date_end"] = df["date_start"]
    df["week"] = pd.NA
    df["season"] = [f"{y}-{y + 1}" for y in df["year"]]
    df["region_name"] = df["region_code"].map(REGIONS)
    df["category"] = "all"
    df = df.sort_values(["year", "region_code", "sex", "age_group"])
    national = df[(df.region_code == "00") & (df.age_group == "all")]
    print(national.pivot(index="year", columns="sex", values="value").to_string())
    print(write_tidy(df, "mois_population"))


if __name__ == "__main__":
    main()
