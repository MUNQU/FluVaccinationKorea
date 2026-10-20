# KDCA: influenza National Immunization Program (NIP) coverage

## What it is

Two sources give the influenza vaccination of the NIP target groups. The NIP vaccinates
persons aged 65+, children and (from 2019-2020) pregnant women free of charge.

1. **KDCA registry, final coverage per season.** Public Data Portal dataset 15142108,
   `질병관리청_인플루엔자 시군구별 국가예방접종 현황_20250429` (influenza NIP status by
   district).
   - Page: <https://www.data.go.kr/data/15142108/fileData.do>
   - Data from the Korea Immunization Registry (예방접종통합관리시스템) as registered on
     2025-04-29. One-time release (no update planned).
   - Licence: public work, attribution required (공공저작물 출처표시, type 1).
2. **KCDC press release of 2016-10-31**, "65세 이상 547만명 인플루엔자 접종 완료"
   (5.47 million persons aged 65+ vaccinated). It gives the persons aged 65+ vaccinated per
   period in October 2016.
   - Page: <https://mohw.go.kr/board.es?act=view&bid=0027&list_no=335003&mid=a10503010200&nPage=670&tag=>
   - Copy: `data/raw/nip/mohw_press_2016-10-31.html`.

## What the registry describes

- **Value:** cumulative count of vaccinated persons at the end of the campaign, the
  target population, and the coverage (%).
- **Seasons:** 2015-2016 to 2023-2024.
- **Target groups and their age** (from the column dictionary of the dataset page,
  `data/raw/nip/data_go_kr_15142108_page.html`):

| Season | 65+ | Children (`age_group`) | Pregnant women |
|---|---|---|---|
| 2015-2016 | yes | — | — |
| 2016-2017 | yes | 6-11 months (`6-11mo`) | — |
| 2017-2018 | yes | 6-59 months (`6-59mo`) | — |
| 2018-2019 | yes | 6 months to 12 years (`6mo-12`) | — |
| 2019-2020 | yes | 6 months to 12 years (`6mo-12`) | yes |
| 2020-2021 to 2023-2024 | yes | 6 months to 13 years (`6mo-13`) | yes |

- **Breakdown:** sex, and provider (health centre 보건소 or designated clinic 의료기관).
  Pregnant women have vaccinated counts only (no sex, no target population, no coverage).
- **Regions:** whole country, 17 provinces and the health-centre districts. In the original
  file, a row whose district name is equal to the province name is the province total.

Whole country, 65+:

| Season | Target population | Vaccinated | Coverage |
|---|---|---|---|
| 2015-2016 | 6,719,188 | 5,472,024 | 81.4% |
| 2016-2017 | 6,944,490 | 5,748,445 | 82.8% |
| 2017-2018 | 7,312,187 | 6,080,368 | 83.2% |
| 2018-2019 | 7,596,452 | 6,357,491 | 83.7% |
| 2019-2020 | 7,959,200 | 6,642,936 | 83.5% |
| 2020-2021 | 8,422,901 | 6,511,742 | 77.3% |
| 2021-2022 | 8,859,885 | 7,134,384 | 80.5% |
| 2022-2023 | 9,309,805 | 7,630,244 | 82.0% |
| 2023-2024 | 9,768,519 | 8,059,747 | 82.5% |

The vaccinated totals are sums of the published counts by sex and provider. Each total
divided by the target population gives the published coverage. Districts, provinces and the
whole country give the same totals.

## What the press release describes

Persons aged 65+ vaccinated per period, 2016-2017 campaign. The percentage is the share of
6,936,921 persons (population aged 65+ in September 2016):

| Period | Epi week | Vaccinated | % of 65+ | Cumulative % |
|---|---|---|---|---|
| 4-8 Oct 2016 (Tue-Sat) | 2016 W41 | 2,263,357 | 32.63 | 32.63 |
| 9-15 Oct | 2016 W42 | 2,565,769 | 36.99 | 69.62 |
| 16-22 Oct | 2016 W43 | 485,686 | 7.00 | 76.62 |
| 23-27 Oct (Sun-Thu) | 2016 W44 (part) | 158,675 | 2.29 | 78.91 |

- Persons aged 75+ could start on 4 October 2016, and persons aged 65-74 on 10 October
  (Seoul Shinmun, 2016-09-22, reporting the KCDC plan; not in the release itself).
- The release gives no figures after 27 October. The registry gives 82.8% at the end of
  the season, so about 4% of the 65+ population was vaccinated after 27 October.
- The two sources use different denominators (6,936,921 and 6,944,490). The difference is
  0.1%.

`data/raw/nip/kcdc_weekly_doses_2016.csv` is a manual transcription of the table of the
release. The script checks that each percentage is equal to the count divided by the
denominator.

## Output files

| File | Content |
|---|---|
| `data/raw/nip/nip_influenza_<cut-off>.csv` | Registry file (CP949, wide format) |
| `data/raw/nip/data_go_kr_15142108_page.html` | Dataset page, with the column dictionary |
| `data/raw/nip/mohw_press_2016-10-31.html` | Press release page |
| `data/raw/nip/kcdc_weekly_doses_2016.csv` | Transcribed table of the press release |
| `data/processed/nip_coverage.csv` | Registry, common format (`source=kdca_nip`) |
| `data/processed/nip_weekly_2016.csv` | Press release, common format (`source=kcdc_press`) |

In `nip_coverage.csv`:

- `indicator`: `target_population` (persons), `vaccinated` (persons), `coverage_pct`
  (percent).
- `period_type=season`; `date_start` and `date_end` are epi week 36 to week 35 of the season.
- `category`: `target=<65+|children|pregnant>;provider=<all|health_centre|clinic>`, plus
  `;district_name=<name>` for district rows. `provider` is `all` for the population and the
  coverage.
- Rows with `provider=all` for `vaccinated` are sums made by the script.

In `nip_weekly_2016.csv`: `indicator` is `vaccinated` or `coverage_increment_pct`,
`period_type=week`, and `date_start`/`date_end` are the dates of the period in the release
(not always a full week).

## How to run

```bash
.venv/bin/python -E -s scripts/nip_vaccination.py
```

The script downloads the registry file with `scripts/datagokr.py` (the same method as NHIS)
if it does not exist.

## Limits

- The registry gives final values only. The weekly uptake is known only for October 2016,
  from the press release.
- Only NIP doses are counted. Doses paid outside the program are not in the data. Their
  share among persons aged 65+ is not known.
- The registry release of 2025 can differ a little from the figures published at the time
  (Yun et al. 2017 give 82.4% for 2016-2017).
