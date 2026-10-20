# KOSIS: influenza vaccination coverage (Community Health Survey)

## What it is

- KOSIS table `DT_INFLUENZA` (orgId `177`, KDCA): "시·군·구별 연간 인플루엔자 예방접종률".
  In English: *Influenza Vaccination For A Year*.
- Original source: the KDCA Community Health Survey (지역사회건강조사, CHS). Approved
  statistic no. 117075 (statId `2008057`).
- Link: <https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_INFLUENZA&conn_path=I2&language=ko>
- Last KOSIS update seen: 2026-01-14.

## What it describes

- **Definition (official note of the table):** "최근 1년 동안 인플루엔자(독감) 예방접종을
  받은 적이 있는 분율(%)". It is the percentage of people who say they received an
  influenza vaccine in the last year.
- It is a **self-reported** value from a household survey. The CHS interviews adults
  (19 years or older). The numerator is the people who answer "yes". The denominator is
  the people who answer the question. The percentages use the survey design weights.
- The table has 5 items. All of them go to the processed file:

| KOSIS item | `indicator` | Unit |
|---|---|---|
| 응답자수 (respondents) | `respondents` | persons |
| 조율 (crude rate) | `flu_vaccination_coverage_crude_pct` | percent |
| 조율표준오차 (standard error of the crude rate) | `flu_vaccination_coverage_crude_se` | percent |
| 표준화율 (standardized rate) | `flu_vaccination_coverage_standardized_pct` | percent |
| 표준화율표준오차 (standard error of the standardized rate) | `flu_vaccination_coverage_standardized_se` | percent |

- **Crude rate:** uses the real population structure of that year and region.
- **Standardized rate:** adjusts for age and sex structure with the standard population
  (2005 population estimate, Statistics Korea). Use it to compare years and regions. For a
  model of a real region, use the crude rate.
- In KOSIS, the English label of `조율` says "Crude Death Rate". This is a translation
  error. The value is the crude vaccination rate.

## Coverage

- **Years:** 2008 to 2025, one value per year.
- **Regions:** 17 provinces and 278 districts. There is no national total.
  - Level 1: province. In the file, `region_code` is the 2-digit code and
    `category` = `all`.
  - Level 2: si-gun-gu, or the area of a public health centre (보건소). In the file,
    `category` = `district_code=<KOSIS id>;district_name=<name>`.
  - Level 3: sub-areas of large cities (for example, the gu of Suwon). They also carry
    `parent_district_name=<city>`.
- The number of districts changes: 281 rows in 2008 and 292 in 2022-2025.
- **There is no breakdown by age or sex** in this table.

## Definition and territorial changes (KOSIS notes)

- From 2023, Gunwi county (군위군) moves from Gyeongbuk (code 47) to Daegu (code 27). It
  has two KOSIS ids: `01405` (Gyeongbuk, until 2022) and `00309` (Daegu, from 2023).
- From 2014, Cheongju merges with Cheongwon and goes from 2 to 4 gu.
- Jeju, district "동부": in 2008 the value is the sum of the east and west areas.
- KOSIS uses the current names of Gangwon (강원특별자치도) and Jeonbuk (전북특별자치도)
  for all years. The file uses the new codes `51` and `52`, as NHIS does.

## Processed format

`data/processed/kosis_vaccination.csv` (25,760 rows). Common format
(`docs/data-format.md`) with these rules:

- `source` = `kosis_chs`, `period_type` = `year`, `age_group` = `19+`, `sex` = `all`.
- `date_start` and `date_end` = 16 August to 31 October of the survey year. This is the
  usual CHS fieldwork period (**to be verified** for each year).
- `season` = `<year-1>-<year>`. Reason: the survey runs from August to October and asks
  about the previous 12 months. Those months mostly cover the October campaign of the
  previous year. The campaign of the survey year starts in September or October, so some
  people interviewed in October can already count it.
  **Example:** the 2017 survey → season `2016-2017`.
- Empty cells or cells with "-" in KOSIS produce no rows.

## Limits

- It is a survey: there is sampling error (use the standard errors) and recall bias.
- Adults only. There are no data for children and no age groups. **It does not map
  directly to the 6 NHIS age groups or to the 60 or 65 year cut-off of the model.**
- One value per year, not weekly. It does not give the pace of the campaign.
- The "season" of each year is approximate (see above).
- The level 2 and 3 areas follow the health centre areas. They do not always match the
  official si-gun-gu.

## How the download works

KOSIS blocks direct scripted calls to its download (`downLarge.do` answers
"비정상적인 서비스 이용으로 접근이 차단되었습니다"). For this reason,
`scripts/kosis_vaccination.py` uses a headless browser (playwright, Chromium):

1. Opens the table and waits for the `statHtmlContent.do` frame.
2. Reads the table metadata (`g_jsonStatInfo`): years, items and region ids.
3. Reads the region tree (ids, names, level and parent) and the table notes.
4. Inside the page, requests the "large download" as CSV (`makeLarge.do`, then
   `downLarge.do`). It requests all years, all items and all regions, with the option
   "코드포함" (include codes). Names alone are not enough, because they repeat across
   provinces (for example, "중구") and the CSV order does not follow the tree.

Raw files (`data/raw/kosis/`):

- `kosis_DT_INFLUENZA.csv`: the download (CP949 encoding).
- `kosis_DT_INFLUENZA_info.json`: table metadata.
- `kosis_DT_INFLUENZA_regions.json`: region tree.
- `kosis_DT_INFLUENZA_notes.txt`: table notes (주석).

## How to re-run

```bash
uv pip install --python .venv playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python -E -s scripts/kosis_vaccination.py            # uses the raw CSV if it exists
.venv/bin/python -E -s scripts/kosis_vaccination.py --refresh  # downloads again
```

If KOSIS changes the page, the download can fail. The alternative is the KOSIS OpenAPI
(`statisticsParameterData.do`), which needs a free key.

## Checks done

- All ids in the CSV exist in the region tree. All 278 districts in the tree have data.
- There are no duplicate rows by indicator, year, province and district.
- Example: Seoul, crude rate 2016 = 36.7%. The value is the same in two different
  downloads (with codes and without codes). It was not compared with the web view.
