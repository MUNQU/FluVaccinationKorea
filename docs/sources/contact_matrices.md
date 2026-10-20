# Contact matrices (repository `woosikson/age-rt-smoother`)

## What it is

Code repository of the paper:

> Kim M, Kim J-H, Son W-S. *An Age-Structured Mathematical Modeling with Particle Smoother for
> Instantaneous Reproduction Number Estimation in Influenza Epidemics.* Scientific Reports
> (under revision).

- <https://github.com/woosikson/age-rt-smoother>
- Commit used: `403d8da` (2026-08-14).

The paper uses an age-structured SEIR model (6 age bands) and a particle smoother to
estimate the instantaneous reproduction number by age. The case data are the NHIS data (see
[nhis.md](nhis.md)), seasons 2009-10 to 2018-19 and 2022-23. It is the Korean reference
nearest to our work.

## What we take from the repository

| Original file | Content | Use here |
|---|---|---|
| `data/Pops_Dec2022.csv` | MOIS population on 31-12-2022, single year of age, by province (EUC-KR) | Kept only. The population comes from [mois.md](mois.md), which has all years |
| `data/contact_prem2017.csv` | 6×6 matrix from Prem et al. 2017, aggregated | `contact_matrices.csv`, `matrix=prem2017` |
| `data/contact_prem2021.csv` | 6×6 matrix from Prem et al. 2021, aggregated | `contact_matrices.csv`, `matrix=prem2021` |
| Julia code (`code/02_particle_smoother.jl`, `code/04_nhis.jl`) | Survey matrix of Son et al. 2025, written in the code | `contact_matrices.csv`, `matrix=son2025_survey` |

The survey matrix is the one of the main analysis of the paper. The Prem matrices are
synthetic alternatives for the sensitivity analysis.

## Format

`data/processed/contact_matrices.csv` does not use the common format, because it is not a
time series. Columns: `source, matrix, contactee_age_group, infector_age_group, value`.

Age bands: 0-5, 6-11, 12-17, 18-44, 45-64, 65+ (the same as NHIS).

**Orientation.** `C[i, j]`: row `i` = susceptible person (contactee), column `j` =
infector. The force of infection on group `i` is `χ_i Σ_j C[i, j] I_j / N_j`. The repository
checks this orientation with the reciprocity relation `C[i, j] N_j = C[j, i] N_i`. With the
2022 MOIS population, the relative error is:

| Matrix | Column = infector | Row = infector |
|---|---|---|
| `son2025_survey` | 0.011 | 1.02 |
| `prem2017` | 0.405 | 0.916 |
| `prem2021` | 0.235 | 1.079 |

The survey matrix satisfies reciprocity. The Prem matrices satisfy it less well, because
they are synthetic estimates aggregated from 16 five-year bands.

## How to run

```bash
.venv/bin/python -E -s scripts/contact_matrices.py
```

## Limits

- The matrices have 6 age bands. The `FluVaccinationLoRegne` model uses two bands (<60 and
  ≥60) and homogeneous mixing (`beta * S * (IR + IH) / N`). To use these matrices, aggregate
  them to <65 and 65+ with population weights.
- The survey matrix is written by hand in the source code. If the repository changes,
  update `SON2025` in `scripts/contact_matrices.py`.
