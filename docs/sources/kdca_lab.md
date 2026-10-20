# Laboratory surveillance (WHO FluNet, Korean data)

## What the source is

The Power BI link in `drafts/Korea FLU.md` ("Confirmed cases") **is not a KDCA report**.
It is the public **WHO FluNet** dashboard ("Influenza virus detections reported to
FluNet"). The data model is `GIP_PublicOutputs_FluNet_DownloadData` (Global Influenza
Programme). The dashboard has data for all countries. Korea sends its data to FluNet
through its national influenza centre (KDCA).

WHO publishes the same table in the xMart OData API:
`https://xmart-api-public.who.int/FLUMART/VIW_FNT`. The script downloads the data from
this API and compares a sample with the Power BI dashboard. The two sources give the same
values in all 1,096 Korean weeks (`data/raw/kdca_lab/cross_check.txt`).

## What it describes

Weekly laboratory results of respiratory specimens tested for influenza:

- Specimens received and specimens tested.
- Influenza A detections by subtype: A(H1N1)pdm09, seasonal A(H1), A(H3), A(H5),
  A(H7N9), other subtypes and A not subtyped.
- Influenza B detections by lineage: Victoria, Yamagata and lineage not determined.
- Total influenza A, total influenza B and total influenza (A + B). Negative specimens.
- RSV (respiratory syncytial virus) detections, only from 2020.
- Origin of the data (`ORIGIN_SOURCE`): `SENTINEL` (sentinel surveillance) or
  `NOTDEFINED` (the country did not state the system).

The data are **national**. There is no breakdown by age, sex or region.

## Coverage

| Period | System | Notes |
|---|---|---|
| 2001-2008 | `not_defined` | Few weeks per year. 2006-2008 have no specimens tested |
| 2009 (week 21) to 2020 (week 5) | `not_defined` | Continuous series, about 11,000-15,000 specimens per year |
| 2020 (week 6) to 2020 (week 35) | — | No data (start of COVID-19) |
| 2020 (week 36) to present | `sentinel` | Continuous series, with RSV. Last week downloaded: 2026-10-04 |

The 2016-2017 season is complete (A(H3) peak in weeks 51-52 of 2016, with 55%
positivity, and an influenza B wave in March-April 2017).

## Output format

File: `data/processed/kdca_lab_flunet.csv` (common format, `docs/data-format.md`).

- `source` = `who_flunet` (the file name keeps the `kdca_lab` prefix).
- `period_type` = `week`. `date_start` is the Sunday that starts the FluNet MMWR week
  (Sunday to Saturday). The weeks are the same 7 days as the KDCA weeks, but the
  **numbering** is different: MMWR puts week 1 on the first week with 4 days in January,
  and the KDCA puts it on the week that contains 1 January. For this reason, the script
  calculates `year` and `week` from `date_start` with the KDCA rule (`common.epi_week`).
  The `MMWR_YEAR` and `MMWR_WEEK` columns and the ISO week (Monday to Sunday) stay in the
  raw file.
- `region_code` = `00`, `age_group` = `all`, `sex` = `all`.
- `category`: `system=<sentinel|not_defined>` and, where it applies, `virus=<subtype>`.

| `indicator` | `unit` | FluNet column |
|---|---|---|
| `specimens_received` | `count` | `SPEC_RECEIVED_NB` |
| `specimens_tested` | `count` | `SPEC_PROCESSED_NB` |
| `flu_detections` | `count` | `INF_ALL`, `INF_A`, `AH1N12009`, `AH1`, `AH3`, `AH5`, `AH7N9`, `AOTHER_SUBTYPE`, `ANOTSUBTYPED`, `INF_B`, `BVIC_NODEL`, `BYAM`, `BNOTDETERMINED` |
| `flu_negative` | `count` | `INF_NEGATIVE` |
| `rsv_detections` | `count` | `RSV` |
| `positivity_pct` | `percent` | Calculated: `100 · INF_ALL / SPEC_PROCESSED_NB` |

### Corrections applied (`clean` in the script)

1. The week of 2021-09-05 appears twice (`NOTDEFINED` and `SENTINEL`, with the same
   values). The script keeps only the `SENTINEL` row.
2. `INF_ALL` is empty in weeks with no detections. If `INF_A` and `INF_B` exist, the
   script sets `INF_ALL = INF_A + INF_B`.

Empty FluNet cells do not become zero: they have no row.

## How the extraction works

`scripts/kdca_lab.py`:

1. **Main download.** `GET VIW_FNT?$format=csv&$filter=COUNTRY_CODE eq 'KOR'` on the xMart
   API. It saves `data/raw/kdca_lab/flunet_kor.csv`.
2. **Check against Power BI.**
   - The `r=` parameter of the link is base64 JSON: report key (`k`) and tenant (`t`).
   - `GET /public/routing/cluster/{tenant}` returns the cluster
     (`wabi-north-europe-n-primary`). The script adds the suffix `-api` to the host name.
   - `GET /public/reports/{k}/modelsAndExploration?preferReadOnlySession=true`, with the
     header `X-PowerBI-ResourceKey`, returns the pages, the visuals and the model id.
   - `POST /public/reports/querydata?synchronous=true` with a
     `SemanticQueryDataShapeCommand` on the `FluNet_Country` table, filtered by
     `ISO3 = 'KOR'`.
   - `decode_dsr` decodes the compressed DSR format. Each row holds only the values that
     change. Bit *i* of `R` repeats the previous value of column *i*, bit *i* of `Ø` marks
     a null, and `ValueDicts` holds the strings.
   - It compares specimens tested, A(H3) and total influenza by week and system.
3. **Common format.** `clean` and `tidy`, then `write_tidy` from `scripts/common.py`.

Raw files in `data/raw/kdca_lab/`: `flunet_kor.csv`, `models_and_exploration.json`,
`querydata_kor_sample.json`, `cross_check.txt` and `conceptual_schema.json`. The last file
holds the column names of the model (`POST /public/reports/conceptualschema`). It was
downloaded by hand once, and the script does not update it.

## How to re-run

```bash
.venv/bin/python -E -s scripts/kdca_lab.py
```

It takes less than one minute. WHO updates FluNet every week. Each run can add new weeks
and correct earlier weeks.

## Limits

- **The Power BI endpoints have no public documentation** and can change without notice.
  The script uses them only for the check. If they fail, the main download (xMart API)
  does not change.
- `api.powerbi.com` sometimes does not answer the routing call. The script then tries the
  default cluster of the public viewer.
- Before 2020, the origin system is `not_defined`. It is not known if all specimens are
  sentinel specimens. For this reason, the series before and after 2020 may not be
  comparable in volume.
- There are no data by age or by region. For age-structured models, this source gives
  only the subtype mix and the national positivity.
- No value could be compared with a report published by the KDCA. The sentinel bulletins
  ([kdca_sentinel.md](kdca_sentinel.md)) can serve for this check.
