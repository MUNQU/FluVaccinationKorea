# Data sources

This document summarizes the sources listed in `drafts/Korea FLU.md`: what each one
describes and which files it produces. Each source has its own page in `docs/sources/`. The
file format is in [data-format.md](data-format.md).

## Summary

| Source | What it describes | Time | Breakdown | Coverage | Processed file | Page |
|---|---|---|---|---|---|---|
| **NHIS** (data.go.kr 15089429) | Care episodes for diagnosed influenza (ICD-10 J09-J11): outpatient or inpatient, and inpatient only. Whole population | Daily | 6 age bands (0-5, 6-11, 12-17, 18-44, 45-64, 65+), sex, province | 2006-01-01 to 2025-12-31 | `nhis_daily.csv.gz`, `nhis_weekly.csv` | [nhis.md](sources/nhis.md) |
| **KDCA sentinel** (bulletins and portal) | ILI per 1,000 outpatients, epidemic threshold, influenza inpatients in the hospital ARI network, SARI, virus positivity | Weekly | Age (from 2013-14), province (2026-27 only) | Total ILI from 2003-04 | `kdca_sentinel_ili.csv`, `_threshold`, `_hospital`, `_virus`, `_bulletins` | [kdca_sentinel.md](sources/kdca_sentinel.md) |
| **WHO FluNet** (the Power BI link) | Specimens tested and influenza detections by subtype and lineage, RSV | Weekly | National only | 2009 W21 to 2026, gap 2020 W6-W35 | `kdca_lab_flunet.csv` | [kdca_lab.md](sources/kdca_lab.md) |
| **MOIS** (jumin.mois.go.kr) | Registered population on 31 December | Yearly | Single year of age, sex, province | 2008 to 2025 | `mois_population.csv` | [mois.md](sources/mois.md) |
| **KOSIS** DT_INFLUENZA | % of adults (19+) who report a flu vaccination in the last year. Community Health Survey | Yearly | Province and district (si-gun-gu). No age or sex | 2008 to 2025 | `kosis_vaccination.csv` | [kosis_vaccination.md](sources/kosis_vaccination.md) |
| **GitHub** `woosikson/age-rt-smoother` | 6×6 contact matrices (Son 2025 survey, Prem 2017 and 2021) | — | The 6 NHIS age bands | — | `contact_matrices.csv` | [contact_matrices.md](sources/contact_matrices.md) |

## Key findings

- **The Power BI link is not a KDCA report.** It is the public WHO FluNet dashboard. Korea
  sends its laboratory data there. The script downloads the WHO OData API and checks it
  against Power BI. All 1,096 weeks match.
- **KDCA numbers its weeks with its own rule.** Week 1 is the week that contains 1 January,
  not the MMWR week 1. The whole project now uses the KDCA rule. See
  [data-format.md](data-format.md).
- **The ILI series changes level in 2013-2014.** The sentinel network was reformed, and the
  threshold goes from 4.0 to 12.1. Do not compare levels before and after without an
  adjustment.
- **NHIS revises old data in each release.** Up to 2023, the 2025 release has 0.07% more
  episodes than the 2023 release. Keep the original workbook of each analysis.
- **The "쯔쯔가무시증" bulletins are about scrub typhus.** They contain no influenza data.
- **KOSIS coverage comes from an adult survey.** It is self-reported and has no age bands.
  The survey of year `Y` mostly describes the campaign of season `Y-1`–`Y`.

## What each source covers for the 2016-2017 season

`FluVaccinationLoRegne` calibrates the 2016-2017 season (week 37 of 2016 to week 17 of
2017). For that season, the Korean data are:

| LoRegne model input | Korean data available | Difference |
|---|---|---|
| Weekly admissions, age ≥60, by vaccination × comorbidity | NHIS inpatient sheet, 65+, weekly | Cut at 65, not 60. No vaccination status, no comorbidity. Clinical diagnosis, not laboratory-confirmed |
| Admissions (second source) | KDCA hospital ARI network | **Starts in 2017 W24.** Does not cover 2016-2017 |
| Weekly doses, age ≥60 | KOSIS: yearly adult coverage by province | These sources have no weekly doses and no 65+ coverage |
| Population ≥60, and share with ≥2 chronic conditions | MOIS: population by single year of age (31-12-2016) | No comorbidity data |
| — | Sentinel ILI by age (5 bands), FluNet by subtype | Extra data that LoRegne does not use: epidemic shape and dominant subtype (A(H3)) |

## How to run everything

From the repository root:

```bash
UV_PROJECT_ENVIRONMENT=$HOME/.virtualenvs/FluVaccinationKorea uv sync --extra dev
ln -sfn $HOME/.virtualenvs/FluVaccinationKorea .venv
.venv/bin/playwright install chromium   # KOSIS only

.venv/bin/python -E -s scripts/nhis.py
.venv/bin/python -E -s scripts/mois.py
.venv/bin/python -E -s scripts/contact_matrices.py
.venv/bin/python -E -s scripts/kdca_lab.py
.venv/bin/python -E -s scripts/kosis_vaccination.py
.venv/bin/python -E -s scripts/kdca_sentinel_download.py db         # ~10 min
.venv/bin/python -E -s scripts/kdca_sentinel_download.py bulletins  # ~1 h, ~2.7 GB
.venv/bin/python -E -s scripts/kdca_sentinel_bulletins.py
.venv/bin/python -E -s scripts/kdca_sentinel_process.py
```

The scripts do not download a file again if it already exists (except
`kosis_vaccination.py --refresh`). They run with `-E -s`, not `-I`, because `-I` prevents
the import of `scripts/common.py`. Downloaded data is never on `sys.path`.

## What is not in git

The sentinel bulletins (`data/raw/kdca_sentinel/bulletins/`, ~2.7 GB) and their text cache
are not in git. `data/raw/kdca_sentinel/manifest.csv` lists each file and its origin. The
other raw and processed data take about 65 MB.

## Open points

- Region `18` of the sentinel portal (merged Jeonnam-Gwangju, 2026) has no code in
  `common.REGIONS`. The script skips it. This affects only the provincial ILI of 2026-2027.
- The fieldwork dates of the Community Health Survey (16 Aug – 31 Oct) and the definition of
  the denominator follow the usual survey design. No official document confirms them yet.
- The hospital and virus series of the bulletins come from text patterns. They were
  checked for continuity only. ILI, SARI new patients and influenza positivity were
  checked against an independent build by Dr. Woo-Sik Son (`drafts/data/`): see
  "Cross-check with an independent dataset" in
  [kdca_sentinel.md](sources/kdca_sentinel.md).
