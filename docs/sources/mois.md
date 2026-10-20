# MOIS: registered population

## What it is

The Ministry of the Interior and Safety (MOIS, 행정안전부) publishes the resident
registration statistics (주민등록인구통계) at <https://jumin.mois.go.kr>. The page used is
"연령별 인구현황" (population by age).

## What it describes

- Persons in the resident registration on **31 December** of each year (yearly statistic,
  `searchYearMonth=year`).
- It includes residents, residents with unknown whereabouts (거주불명자) and registered
  Korean nationals abroad (재외국민). **It does not include foreign nationals.**
- Single year of age from 0 to 99, and a `100+` group.
- Whole country (`00`) and the 17 provinces.
- Total and by sex.

## Coverage

Years 2008 to 2025 (the portal starts in 2008). One file per year.

| Year | Total |
|---|---|
| 2016 | 51,696,216 |
| 2022 | 51,439,038 |
| 2025 | 51,117,378 |

The 2022 total is equal to `Pops_Dec2022.csv` of the repository `woosikson/age-rt-smoother`.
In each year, males + females = total.

## Output files

| File | Content |
|---|---|
| `data/raw/mois/mois_population_<year>_sum.csv` | Total by single year of age (EUC-KR) |
| `data/raw/mois/mois_population_<year>_gender.csv` | Males and females by single year of age (EUC-KR) |
| `data/processed/mois_population.csv` | Common format |

In the common format: `indicator=population`, `unit=persons`, `period_type=snapshot`,
`date_start = date_end = 31 December`. `age_group` is the single year of age, `100+` or
`all`. `season` is the season that starts in that year: the population on 31-12-2016 goes
with season `2016-2017`, because it is the nearest date to the peak of that season.

## Province codes

MOIS uses the code in force in each year. Gangwon changes from `42` to `51` in 2023, and
Jeonbuk from `45` to `52` in 2024. NHIS uses `51` and `52` in the whole series. To join the
two sources by province, use the name (`region_name`), not the code.

## How to run

```bash
.venv/bin/python -E -s scripts/mois.py
```

The script submits the CSV download form of the portal (`downloadCsvAge.do`) for each year.
For single years of age, the portal gives the total **or** the breakdown by sex, not both.
The script therefore sends two requests per year. It waits 1 s between requests. If a file
already exists, the script does not download it again.

## Limits

- The population is the year-end population. There is no mid-season population. If
  necessary, interpolate between two years or download the monthly data (the portal has it).
- There is no comorbidity or vaccination data.
