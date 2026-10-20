# NHIS: influenza care episodes

## What it is

The National Health Insurance Service of Korea (NHIS, 국민건강보험공단) publishes dataset
15089429 on the Public Data Portal:
`국민건강보험공단_감염성질환(인플루엔자) 의료이용정보` (healthcare use for influenza).

- Page: <https://www.data.go.kr/data/15089429/fileData.do>
- Licence: "이용허락범위 제한 없음" (no restriction on use).
- Update: yearly. The downloaded release has a cut-off date of **2025-12-31** and was
  registered on 2026-07-24.

## What it describes

Korean health insurance covers the whole population. The data is therefore a census, not a
sample.

- **Case:** an insurance claim with ICD-10 code J09, J10 or J11 (influenza), as the primary
  or a secondary diagnosis.
- **Episode:** NHIS joins claims of the same person less than 28 days apart into one
  episode. The value is a number of episodes, not of persons or visits.
- **Date:** the first day of care (`FST_DT`).
- **No laboratory confirmation.** J11 is "influenza, virus not identified". The data
  measures influenza diagnosed by a physician.

The workbook has three sheets:

| Sheet | Content | Rows | `category` in the common format |
|---|---|---|---|
| `외래입원주부상병` | Outpatient **or** inpatient care, primary or secondary diagnosis | 942,534 | `setting=outpatient_or_inpatient` |
| `입원주부상병` | Inpatient care only, primary or secondary diagnosis | 391,949 | `setting=inpatient` |
| `시도코드` | Province code table | 20 | (not used) |

The inpatient sheet is a **subset** of the first sheet. Do not add the two.

Columns of the two data sheets: `FST_DT` (date), `SIDO` (province), `GEN_NM` (sex),
`AGG_NM` (age band), `CNT` (episodes).

## Coverage

- **Dates:** 2006-01-01 to 2025-12-31, daily.
- **Age:** six fixed bands: 0-5, 6-11, 12-17, 18-44, 45-64 and 65+. One single episode has
  no age (`unknown`).
- **Sex:** male and female.
- **Region:** 17 provinces. NHIS recodes the whole series with the current codes: Gangwon
  is `51` and Jeonbuk is `52` in all years. The old codes `42`, `45` and `49` do not occur.
- **Zeros:** combinations without episodes are absent from the original file.

Totals of the 2025-12-31 release: 30,526,317 episodes in total and 2,082,142 inpatient
episodes.

## Output files

| File | Content |
|---|---|
| `data/raw/nhis/nhis_influenza_<cut-off>.xlsx` | Original workbook |
| `data/processed/nhis_daily.csv.gz` | Original rows: day × province × sex × age × setting. No zeros |
| `data/processed/nhis_weekly.csv` | Complete epi weeks, whole country. Includes totals (`sex=all`, `age_group=all`) and explicit zeros |

In the weekly file, the week is the KDCA epi week (Sunday to Saturday). The script drops the
last week, because the cut-off date leaves it incomplete. The first week starts on
2006-01-01, which is a Sunday.

Indicator: `flu_care_episodes`, unit `count`.

## How to run

```bash
.venv/bin/python -E -s scripts/nhis.py
```

The script reads the dataset page, asks `/tcs/dss/selectFileDataDownload.do` for the file
identifier, and downloads the workbook from `/cmm/cmm/fileDownload.do`. The local file name
includes the cut-off date. If the file already exists, the script does not download it again.

## Checks

The repository `woosikson/age-rt-smoother` publishes a fingerprint of the release with a
2023-12-31 cut-off. For data up to that date, the 2025 release gives:

| | 2023 release (GitHub) | 2025 release (this one) |
|---|---|---|
| Rows, sheet 1 | 820,906 | 819,715 |
| Episodes | 23,656,347 | 23,672,254 (+0.07%) |
| 65+ | 1,731,296 | 1,732,369 |

**NHIS revises old data in each release.** The differences are small, but another release
cannot reproduce an analysis exactly. Keep the original workbook.

## Limits

- No vaccination status and no comorbidities. Hospitalizations of vaccinated and
  unvaccinated persons cannot be separated.
- The age bands do not allow a cut at 60 years (the cut of `FluVaccinationLoRegne`). The
  nearest band is 65+.
- "Hospitalization with a secondary diagnosis of influenza" is not the same as "admission
  for confirmed influenza". Compare magnitudes with other regions with care.
- The date is the start of the episode (`요양개시일`). The documentation does not say if, in
  the inpatient sheet, it is the admission date or the first visit of the episode. This is
  not verified.
