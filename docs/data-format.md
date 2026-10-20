# Common data format

Each processed file in `data/processed/` is a long-format CSV, UTF-8, comma separated. One
row holds one value. `scripts/common.py` defines the columns and validates each file before
it writes it (`write_tidy`).

| Column | Content |
|---|---|
| `source` | Short source key: `nhis`, `kdca_sentinel`, `who_flunet`, `mois`, `kosis_chs` |
| `indicator` | What the value measures, in snake case (for example `flu_care_episodes`, `ili_per_1000`) |
| `unit` | `count`, `per_1000`, `percent`, `persons`, … |
| `period_type` | `day`, `week`, `season`, `year` or `snapshot` |
| `date_start`, `date_end` | First and last day of the period (ISO `YYYY-MM-DD`, both included) |
| `year`, `week` | KDCA epi year and epi week. For data that is not weekly, `week` is empty and `year` is the calendar year |
| `season` | Influenza season, for example `2016-2017` |
| `region_code` | 2-digit province code of Statistics Korea. `00` is the whole country |
| `region_name` | Province name in English |
| `age_group` | `all`, a band (`0-5`, `65+`, `19+`) or a single year of age (`42`, `100+`) |
| `sex` | `all`, `male` or `female` |
| `category` | Other strata, as `key=value` pairs joined with `;` (for example `setting=inpatient;virus=A(H3)`). `all` when there are none |
| `value` | The number |

To filter, always use `source`, `indicator`, `unit` and `category`. One file can hold totals
and breakdowns together. For example, `nhis_weekly.csv` has rows with `sex=all` and rows with
`sex=male`. Do not add rows from different levels.

## Time conventions

- **Epi week.** KDCA uses Sunday-to-Saturday weeks. Week 1 is the week that **contains
  1 January**. The date ranges printed in the sentinel bulletins show this. It is not the
  MMWR rule (week 1 = first week with at least four days in January). The two rules differ
  when 1 January falls on Thursday to Saturday. 2011, 2016 and 2022 have a week 53.
- All processed files use the KDCA rule (`common.epi_week`). WHO FluNet numbers its weeks
  with the MMWR rule. `scripts/kdca_lab.py` renumbers them from the start date.
- **Season.** A season starts at epi week 36 and ends at week 35 of the next year (KDCA
  convention since 2008-2009). For daily data, the season comes from the epi week of the day.
- **Comparison with `FluVaccinationLoRegne`.** That project uses `YYYY-WW` labels. To
  compare, join the series on dates (`date_start`), not on week numbers. Korean weeks start
  on Sunday, and the numbering rule can be different.

## What does not fit the format

Contact matrices (`data/processed/contact_matrices.csv`) have their own long format:
`source, matrix, contactee_age_group, infector_age_group, value`.
