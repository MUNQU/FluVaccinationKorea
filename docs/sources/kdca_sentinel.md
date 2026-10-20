# KDCA: influenza sentinel surveillance

## What it is

The KDCA (Korea Disease Control and Prevention Agency) monitors influenza with a network
of sentinel clinics (의원, primary care clinics). Each week, the clinics report how many
patients meet the influenza-like illness (ILI) case definition and how many patients they
see in total.

- **ILI definition (인플루엔자 의사환자):** sudden fever of 38 °C or more, with cough or
  sore throat.
- **Main indicator:** ILI per 1,000 outpatients
  (`의사환자 수 / 총 진료환자 수 × 1,000`).
- **Epidemic threshold (유행기준):** the KDCA calculates it for each season. It is the mean
  ILI of the non-epidemic periods of the 3 previous seasons plus 2 standard deviations.

The KDCA publishes these data in two forms. We use both.

1. **Statistics table of the portal** (`dportal.kdca.go.kr/pot/is/st/influ.do`). This is
   the revised series. The script reads it from the same JSON service that the page uses
   (`influListAjax.do`).
2. **Weekly bulletins** (portal board `q_bbsSn=1010`). They are PDF or HWP files. Each
   bulletin gives the current week and some previous weeks.

## Bulletin series on the board

The board has 1,401 posts in the class "주간소식지" (query of 2026-10-20). The script
downloads only the posts about influenza (the title contains "표본감시" or "인플루엔자"):
992 posts.

| Series (title) | Period | Influenza content |
|---|---|---|
| 인플루엔자 표본감시 (주간)소식지 | 2008 W1 – 2016 W22 | National ILI, ILI by region (until ~2012), virus isolations by week. ILI by age from 2013-2014 |
| 표본감시 주간소식지 | 2016 W23 – 2017 W23 | Same, plus other sentinel diseases |
| 감염병 표본감시 주간소식지 | 2017 W24 – 2026 W41 | National ILI and ILI by age, viruses, ARI hospitalizations, SARI |
| N절기 인플루엔자 표본감시 결과보고서 | seasons 2001-2002 to 2012-2013 | Annual report. Age data are only in figures |

Other series on the same board have **no** influenza data, and the script does not
download them: 쯔쯔가무시증 (scrub typhus, 2020-2023), 말라리아, SFTS, HIV/AIDS, dengue,
COVID-19 and STIs. The starting document cited "쯔쯔가무시증 환자발생 주간소식지". This is
a scrub typhus series, not an influenza series.

The weekly bulletins cover all weeks from 2008 W1 to 2026 W41, except 2017 W39 (there is
no post; the bulletins for 2017 W38 to W41 were published together on 2017-10-23). The
missing weeks appear in the next bulletins. Titles have spelling variants (for example
"소식시", "소시지").

5 weekly bulletins have no attachment (2008 W1, 2009 W26, 2010 W18, 2013 W31 and
2014 W51): the post exists, but it has no file. Of the 12 season reports, only 3 have a
file (2011-2012, twice, and 2012-2013). The weeks of those 5 bulletins are in the portal
table and in the next bulletins.

## Indicators and coverage

All data are national (`region_code` = `00`), except ILI by province in 2026-2027. Dates
are the Sunday that starts the week.

| File / indicator | Breakdown | From | To | Origin |
|---|---|---|---|---|
| `kdca_sentinel_ili` · `ili_per_1000` | total | 2003-09-28 (2003-2004, 48 weeks) | 2026-10-04 | portal |
| `kdca_sentinel_ili` · `ili_per_1000` | 0-6, 7-18, 19-49, 50-64, 65+ | 2013-09-01 | 2017-08-27 | bulletins |
| `kdca_sentinel_ili` · `ili_per_1000` | 0, 1-6, 7-12, 13-18, 19-49, 50-64, 65+ | 2017-09-03 | 2026-10-04 | portal |
| `kdca_sentinel_ili` · `ili_per_1000` | 15 provinces | 2026-08-30 | 2026-10-04 | portal |
| `kdca_sentinel_threshold` · `ili_epidemic_threshold` | by season | 2007-2008 | 2026-2027 | bulletins (2010-2011 missing) |
| `kdca_sentinel_hospital` · `hosp_flu_inpatients` | total | 2017-06-11 | 2026-10-04 | bulletins |
| `kdca_sentinel_hospital` · `sari_new_patients` | total | 2019-02-03 | 2026-10-04 | bulletins; every week from 2020 W20 |
| `kdca_sentinel_hospital` · `sari_flu_positive` | total | 2019-02-03 | 2026-10-04 | bulletins; no data from 2023 W24 to 2025 W29 |
| `kdca_sentinel_virus` · `flu_specimens_tested`, `flu_specimens_positive` | total | 2008-01-06 | 2020-11-22 | bulletins, with gaps |
| `kdca_sentinel_virus` · `flu_positivity` (%) | total | 2008-01-06 | 2026-10-04 | bulletins, with gaps |

Each ILI season has all its 52 or 53 weeks from 2004-2005. Influenza inpatients
(`hosp_flu_inpatients`) have all weeks from 2017-2018.

Epidemic threshold (ILI per 1,000) by season:

| Season | Threshold | Season | Threshold |
|---|---|---|---|
| 2007-2008 | 3.0 | 2017-2018 | 6.6 |
| 2008-2009 | 2.6 | 2018-2019 | 6.3 |
| 2009-2010 | 2.6 | 2019-2020 | 5.9 |
| 2010-2011 | — | 2020-2021 | 5.8 |
| 2011-2012 | 3.8 | 2021-2022 | 5.8 |
| 2012-2013 | 4.0 | 2022-2023 | 4.9 |
| 2013-2014 | 12.1 | 2023-2024 | 6.5 |
| 2014-2015 | 12.2 | 2024-2025 | 8.6 |
| 2015-2016 | 11.3 | 2025-2026 | 9.1 |
| 2016-2017 | 8.9 | 2026-2027 | 12.9 |

`kdca_sentinel_bulletins.csv` keeps every value read (37,472 rows), with its source
bulletin. Use it to study revisions.

## Definition and system changes

- **Season definition.** Until 2007-2008, the season ran from week 26 to week 25. From
  2008-2009, it runs from week 36 to week 35. All files use the current rule (week 36).
- **2013 reform.** From week 36 of 2013, the network has 200 clinics and the system
  changes. ILI values move to a higher level (threshold 2012-2013: 4.0; threshold
  2013-2014: 12.1). Do not compare levels before and after 2013-2014 without adjustment.
- **Age groups.**
  - Before 2013-2014: the bulletins have no ILI by age.
  - 2013-2014 to 2016-2017: 0-6, 7-18, 19-49, 50-64, 65+.
  - From 2017-2018: 0, 1-6, 7-12, 13-18, 19-49, 50-64, 65+.
- **Network size** (from the bulletin footnotes). About 200 clinics from 2013 W36; about
  300 from 2024; about 780 from the 2026-2027 season. From 2026-2027, the portal gives ILI
  by province.
- **ARI hospitalizations (병원급 급성호흡기감염증).** The bulletins give influenza
  inpatients of the hospital network from 2017 W24. The network had 221 hospitals in
  2025-2026. From 2024 W1, the network total includes COVID-19. The number of hospitals
  changes over time, so the series is not a population rate. From 2026, the bulletins also
  give inpatients of tertiary hospitals (상급종합병원급, section 2.2). The script does
  **not** mix them with the hospital network (section 2.1).
- **SARI (중증급성호흡기감염증).** Network of tertiary hospitals. The definition changes:
  before, "38 °C or more and cough, needs admission, onset in the last 10 days"; in 2026,
  "fever or history of fever and cough, ...".

## Epidemiological weeks

The KDCA uses Sunday-to-Saturday weeks. **Week 1 is the week that contains 1 January.**
This is not the MMWR rule: the two rules differ in years when 1 January falls on Thursday
to Saturday. For example, the KDCA has a week 53 in 2011, 2016 and 2022, but not in 2014
or 2020. Because of this finding, `scripts/common.py` now uses the KDCA rule for all
sources (`epi_week`, `epi_week_start`). The MMWR rule stays only in `mmwr_week_start`, for
the check below.

Check: the script reads the date ranges that the bulletins print (for example
"2025년 5주(2025. 1. 26. ~ 2025. 2. 1.)"). Of 975 weeks with a 7-day range, 962 follow the
KDCA rule and only 567 follow the MMWR rule. The 13 exceptions are almost all from
2008-2010 (Monday-to-Sunday weeks or one-week errors), plus one from 2025 (W31, probably a
typo).

`scripts/kdca_sentinel_process.py` calculates `date_start` and `date_end` with the KDCA
rule (`common.epi_week_start`). The `year` and `week` fields are the ones the KDCA
publishes.

## How the extraction works

1. `scripts/kdca_sentinel_download.py`
   - `db`: asks the portal for the national series of all seasons in one query
     (`influ_all_total.json`, from 2003-2004), and for the table of each season from
     2005-2006 by age and by province. It saves the JSON in `data/raw/kdca_sentinel/db/`.
   - `bulletins`: reads the board list, opens each influenza post and downloads its
     attachments with `/pot/component/file/ND_fileDownload.do` (the path
     `/pot/bbs/fileDownload.do` returns an error page). It waits 0.5 s between requests
     and retries up to 3 times if the server hangs. It writes
     `data/raw/kdca_sentinel/manifest.csv`.
2. `scripts/kdca_sentinel_bulletins.py`
   - Converts each bulletin to text: PDF with `pdftotext -layout`; HWP with `hwp5html`
     (package `pyhwp`), which keeps the tables. It saves the text in
     `data/raw/kdca_sentinel/text/`.
   - Finds the ILI tables in both orientations (weeks in columns or in rows). It accepts a
     table only if the nearest title is about influenza ILI (not hand-foot-and-mouth
     disease or conjunctivitis).
   - Reads the epidemic threshold, influenza inpatients, SARI data and virus tests with
     regular expressions.
   - If the text does not give influenza inpatients, it reads the inpatients-by-pathogen
     table with `pdfplumber` (bulletins from 2023 onward).
   - Each row stores its source bulletin in `category` (`reported_in=YYYY-WW`).
3. `scripts/kdca_sentinel_process.py` merges the two sources (see below).

### Merge rules

- **National ILI and ILI by age from 2017-2018:** portal values (revised series).
- **ILI by age 2013-2014 to 2016-2017:** bulletin values. The portal table for those
  seasons is corrupt (almost all zeros; in 2013-2014 the 65+ group is above the 7-18
  group). The script discards it.
- **Quality control:** the script uses an age table from a bulletin only if the national
  value of the same bulletin and week agrees with the portal (difference ≤ 0.3 or ≤ 10%).
  Result: 8,568 of 8,599 bulletin-week pairs agree. The 31 that do not agree are reads of
  another table in 4 bulletins (2010 W1, 2013 W36-W39, 2015 W52 and 2020 W1). In 2013
  W36-W39, the bulletins still gave values of the old system; the portal gives the values
  of the new system. For 2017-2018 to 2026-2027, the bulletin values by age agree 100% with
  the portal.
- **Single-season table versus all-season table.** The single-season query returns 0.0 for
  some January-February weeks before 2013 (for example 2008 W4-W9). The all-season query
  has those values. The script uses the all-season query for the national series and
  treats a national 0.0 as missing (before 2003-2004 all values are zero).
- **Empty portal weeks:** in 2019 W17 the portal gives 0.0 for every age group, while the
  national rate is 37.3. The bulletins give the real values (for example 18.4 for age 0).
  The script replaces any portal week where all age groups are 0 and the national rate is
  above 0 with the bulletin values. Only 2019 W17 is affected. The other zeros by age
  (2020-2022) are real: the bulletins also give 0.0.
- **Revisions:** when several bulletins give the same week, the script uses the most
  recent bulletin.
- **Provinces (2026-2027):** the portal gives 17 regions. Codes "05" (Gwangju) and "13"
  (Jeonnam) are no longer in use and have only zeros. Code "18" (merged Jeonnam-Gwangju)
  has no code in `common.REGIONS`, and the script skips it.

## Cross-check with an independent dataset

Dr. Woo-Sik Son ([woosikson](https://github.com/woosikson)) built the same series
independently from the same bulletins and from WHO FluNet, and shared the files in
`drafts/data/` (codebook in Korean: `drafts/DICTIONARY.md`). We thank Dr. Son for the data.
In the tables below, "Son build" refers to those files. The two builds were compared on
`week_start_date` (2026-10-20, script `scripts/check_drafts_data.py`):

| Series | Values compared | Equal | Notes |
|---|---|---|---|
| ILI per 1,000 (national and by age) | 5,307 | 5,101 (96.1%) | See below |
| Influenza positivity, total / A / B (FluNet and bulletins) | 1,965 | 1,965 (100%) | — |
| SARI new patients | 335 | 328 (97.9%) | The 7 differences (2026) are revisions: the Son build keeps the first report, this build keeps the latest |

Both builds use the same week rule (week 1 contains 1 January). The 206 ILI differences
were checked against the bulletin text:

| Cause | Values | Correct series |
|---|---|---|
| Age columns shifted by one position in the Son build (2024 W31-W39) | 71 | This build (bulletins confirm) |
| Small differences (≤ 0.6): first report versus revised value, or rounding | 66 | This build keeps the revised value |
| One-week shift in the Son build at the start of 2010, 2012 and 2013 (W1-W10) | 29 | This build (bulletin sentences, for example "2012년도 제2주 … 11.3명") |
| First report versus later reports (2020 W1, 2022 W47, others) | 27 | This build (later bulletins confirm) |
| Week values copied into the next week in the Son build (2020 W49) | 8 | This build |
| 2013 W36-W39: old system (bulletins at the time) versus new system (portal) | 4 | Both are correct for their system. This build is consistent with the new system |
| 2020 W47, age 19-49: bulletin 0.3 versus portal 5.3 | 1 | Unresolved |

The comparison also found two problems in this build, now fixed: the empty portal week
2019 W17 (see the merge rules) and SARI new patients missing after 2023 W23 (new table
layouts in the bulletins).

## Files

| File | Content |
|---|---|
| `data/raw/kdca_sentinel/db/*.json` | Portal responses, one per season and breakdown |
| `data/raw/kdca_sentinel/manifest.csv` | List of bulletins: post, title, date, file, size |
| `data/raw/kdca_sentinel/bulletins/` | PDF and HWP files (several GB; not in git, see `.gitignore`) |
| `data/raw/kdca_sentinel/text/` | Extracted text (cache; not in git) |
| `data/processed/kdca_sentinel_bulletins.csv` | All values read, with the source bulletin |
| `data/processed/kdca_sentinel_ili.csv` | Final weekly ILI (national, by age, by province) |
| `data/processed/kdca_sentinel_threshold.csv` | Epidemic threshold by season |
| `data/processed/kdca_sentinel_hospital.csv` | Influenza inpatients (hospital ARI network) and SARI |
| `data/processed/kdca_sentinel_virus.csv` | Virus tests of the sentinel clinic network |

## Known limits

- All data are provisional (잠정통계). The KDCA corrects them over time.
- ILI is a proportion of consultations, not a population incidence.
- The hospital, SARI and virus indicators come from the bulletin text. Their coverage has
  gaps (see the coverage table). For viruses, the laboratory source (`kdca_lab`) is
  better.
- `sari_flu_positive` has no data from 2023 W24 to 2025 W29: the bulletins of that period
  give the influenza share of SARI in another form, which the script does not read yet.
- One value is unresolved: 2020 W47, age 19-49. The bulletins give 0.3 and the portal
  gives 5.3. The file keeps the portal value.
- The script downloads the season reports (2001-2002 to 2012-2013) but does not process
  them: their age data are only in figures.

## How to re-run

```bash
.venv/bin/python -E -s scripts/kdca_sentinel_download.py db         # ~10 min
.venv/bin/python -E -s scripts/kdca_sentinel_download.py bulletins  # ~1 h, several GB
.venv/bin/python -E -s scripts/kdca_sentinel_bulletins.py           # ~25 min the first time
.venv/bin/python -E -s scripts/kdca_sentinel_process.py
```

Requirements: `pdftotext` (poppler) on the `PATH`; `pdfplumber` and `pyhwp` in the
environment.
