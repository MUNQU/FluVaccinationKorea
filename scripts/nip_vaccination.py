"""Influenza National Immunization Program (NIP) coverage -> common format.

Two sources:
- KDCA registry, data.go.kr dataset 15142108: final coverage per season
  (2015-2016 to 2023-2024), whole country and each health-centre district,
  by target group, sex and provider. Writes data/processed/nip_coverage.csv.
- KCDC press release of 2016-10-31 (data/raw/nip/mohw_press_2016-10-31.html):
  persons aged 65+ vaccinated per period in October 2016, transcribed to
  data/raw/nip/kcdc_weekly_doses_2016.csv. Writes
  data/processed/nip_weekly_2016.csv.
"""

import re
from datetime import date

import pandas as pd

import datagokr
from common import RAW, REGIONS, epi_week, epi_week_start, season_of, write_tidy

DATASET = "15142108"
RAW_DIR = RAW / "nip"
PRESS_URL = (
    "https://mohw.go.kr/board.es?act=view&bid=0027&list_no=335003"
    "&mid=a10503010200&nPage=670&tag="
)
# Denominator of the press release: population aged 65+ in September 2016.
PRESS_DENOMINATOR = 6_936_921

PROVINCES = {
    "전국": "00",
    "서울특별시": "11",
    "부산광역시": "26",
    "대구광역시": "27",
    "인천광역시": "28",
    "광주광역시": "29",
    "대전광역시": "30",
    "울산광역시": "31",
    "세종특별자치시": "36",
    "경기도": "41",
    "충청북도": "43",
    "충청남도": "44",
    "전라남도": "46",
    "경상북도": "47",
    "경상남도": "48",
    "제주특별자치도": "50",
    "강원특별자치도": "51",
    "전북특별자치도": "52",
}
SEXES = {"전체": "all", "남성": "male", "여성": "female"}
PROVIDERS = {"보건소": "health_centre", "의료기관": "clinic"}
# Age of the children target group changes by season (column dictionary of
# the dataset page, data/raw/nip/data_go_kr_15142108_page.html).
CHILD_AGES = {
    "2016-2017": "6-11mo",
    "2017-2018": "6-59mo",
    "2018-2019": "6mo-12",
    "2019-2020": "6mo-12",
}
CHILD_AGES_LATER = "6mo-13"
COLUMN = re.compile(
    r"(?P<season>\d{4}-\d{4})절기 (?P<target>65세 이상|어린이|임신부)"
    r"(?: (?P<sex>전체|남성|여성))?(?: (?P<provider>보건소|의료기관))?"
    r" (?P<measure>인구수|접종자수|접종률)"
)
MEASURES = {
    "인구수": ("target_population", "persons"),
    "접종자수": ("vaccinated", "persons"),
    "접종률": ("coverage_pct", "percent"),
}


def target_fields(target: str, season: str) -> tuple[str, str]:
    """(age_group, target label) of a target group."""
    if target == "65세 이상":
        return "65+", "65+"
    if target == "어린이":
        return CHILD_AGES.get(season, CHILD_AGES_LATER), "children"
    return "all", "pregnant"


def registry(path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949", dtype=str)
    df = df.melt(id_vars=["시도명", "시군구명"], var_name="column", value_name="value")
    parts = df["column"].str.extract(COLUMN)
    if parts["measure"].isna().any():
        unknown = df.loc[parts["measure"].isna(), "column"].unique()
        raise ValueError(f"unknown columns: {unknown}")
    df = pd.concat([df, parts], axis=1).dropna(subset=["value"])
    df["value"] = df["value"].astype(float)
    df["region_code"] = df["시도명"].map(PROVINCES)
    if df["region_code"].isna().any():
        raise ValueError(
            f"unknown provinces: {df.loc[df.region_code.isna(), '시도명'].unique()}"
        )
    df["sex"] = df["sex"].map(SEXES).fillna("all")
    df["indicator"] = df["measure"].map(lambda m: MEASURES[m][0])
    df["unit"] = df["measure"].map(lambda m: MEASURES[m][1])
    fields = [target_fields(t, s) for t, s in zip(df["target"], df["season"])]
    df["age_group"] = [a for a, _ in fields]
    df["target_label"] = [t for _, t in fields]
    df["provider"] = df["provider"].map(PROVIDERS).fillna("all")
    # Rows whose district name equals the province name are province totals.
    is_district = (df["시도명"] != "전국") & (df["시군구명"] != df["시도명"])
    df["district"] = df["시군구명"].where(is_district)
    df = pd.concat([df, _vaccinated_totals(df)], ignore_index=True)

    category = "target=" + df["target_label"]
    category += ";provider=" + df["provider"].where(
        df["indicator"] == "vaccinated", "all"
    )
    category += df["district"].map(
        lambda d: f";district_name={d}" if pd.notna(d) else ""
    )
    first_year = df["season"].str[:4].astype(int)
    return pd.DataFrame(
        {
            "source": "kdca_nip",
            "indicator": df["indicator"],
            "unit": df["unit"],
            "period_type": "season",
            "date_start": [_season_start(y) for y in first_year],
            "date_end": [
                _season_start(y + 1) - pd.Timedelta(days=1) for y in first_year
            ],
            "year": first_year,
            "week": pd.NA,
            "season": df["season"],
            "region_code": df["region_code"],
            "region_name": df["region_code"].map(REGIONS),
            "age_group": df["age_group"],
            "sex": df["sex"],
            "category": category,
            "value": df["value"],
        }
    )


def _vaccinated_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Sums of vaccinated persons over provider, and over provider and sex.

    The file gives vaccinated persons only by sex x provider. Pregnant women
    have no sex split, so their sum over provider is already the total.
    """
    vac = df[df["indicator"] == "vaccinated"]
    keys = [
        "시도명",
        "시군구명",
        "season",
        "target",
        "target_label",
        "age_group",
        "region_code",
        "district",
        "indicator",
        "unit",
        "measure",
    ]
    by_sex = vac.groupby(keys + ["sex"], dropna=False, as_index=False)["value"].sum()
    by_sex["provider"] = "all"
    split = by_sex[by_sex["sex"] != "all"]
    total = split.groupby(keys, dropna=False, as_index=False)["value"].sum()
    total["sex"] = "all"
    total["provider"] = "all"
    return pd.concat([by_sex, total], ignore_index=True)


def _season_start(first_year: int) -> date:
    return epi_week_start(first_year, 36)


def weekly_2016() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "kcdc_weekly_doses_2016.csv", dtype=str)
    rows = []
    for r in df.itertuples():
        start, end = (
            date.fromisoformat(r.period_start),
            date.fromisoformat(r.period_end),
        )
        year, week = epi_week(start)
        if epi_week(end) != (year, week):
            raise ValueError(f"period {r.label} spans two epi weeks")
        for indicator, unit, value in (
            ("vaccinated", "persons", float(r.vaccinated)),
            ("coverage_increment_pct", "percent", float(r.coverage_pct)),
        ):
            rows.append(
                {
                    "source": "kcdc_press",
                    "indicator": indicator,
                    "unit": unit,
                    "period_type": "week",
                    "date_start": start,
                    "date_end": end,
                    "year": year,
                    "week": week,
                    "season": season_of(year, week),
                    "region_code": "00",
                    "region_name": REGIONS["00"],
                    "age_group": "65+",
                    "sex": "all",
                    "category": f"target=65+;denominator={PRESS_DENOMINATOR}",
                    "value": value,
                }
            )
    out = pd.DataFrame(rows)
    vac = out[out["indicator"] == "vaccinated"]["value"]
    pct = out[out["indicator"] == "coverage_increment_pct"]["value"]
    check = (100 * vac.values / PRESS_DENOMINATOR).round(2)
    if not (abs(check - pct.values) <= 0.01).all():
        raise ValueError(
            f"press release percentages do not match: {check} vs {pct.values}"
        )
    return out


def main() -> None:
    path = datagokr.download(DATASET, RAW_DIR, "nip_influenza")
    df = registry(path)
    national = df[
        (df.region_code == "00")
        & (df.age_group == "65+")
        & (df.sex == "all")
        & df.category.eq("target=65+;provider=all")
    ].pivot(index="season", columns="indicator", values="value")
    print(national.to_string())
    print(write_tidy(df, "nip_coverage"), len(df))
    weekly = weekly_2016()
    print(write_tidy(weekly, "nip_weekly_2016"), len(weekly))


if __name__ == "__main__":
    main()
