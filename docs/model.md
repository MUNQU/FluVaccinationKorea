# Model (version 1): 2016-2017 season

The model is the `flu.py` of `FluVaccinationLoRegne` (Valencian Community), adapted to the
Korean data and split into the package `flu_korea/`. The calibration, the reports, the
scenarios and the figures use the same method, so the two projects give results in the same
format. This page lists what changes and why.

## Structure

- Engine: `commol`, `DifferenceEquations`, one step = 1 hour, 33 weeks from 2016 W36
  (KDCA weeks, Sunday to Saturday).
- Bins: S, E, IR (infectious, recovers at home), IH (infectious, goes to hospital), H, R.
- Strata: age `y65` (<65) and `o65` (65+); vaccination `nv`/`v` for `o65` only.
- Transmission: homogeneous mixing, `beta * S * (IR + IH) / total`, as in LoRegne.
- Vaccination: the weekly doses for 65+ (`data/model/2016-2017.csv`), given in 8 daily hours
  every day of the week, with effect 7 days later (as in LoRegne).
- Demography: births into `S_y65`, aging `y65 → o65` (into `nv`), deaths in every bin.

## Differences from LoRegne

| Item | LoRegne | Korea | Reason |
|---|---|---|---|
| Age cut | 60 | 65 | NHIS age bands end at 45-64 / 65+ |
| Comorbidity strata | `nc`/`c` (≥2 chronic conditions) | none | No Korean data by comorbidity |
| Hospitalization of the young group | none | `p_h_y`, calibrated | NHIS gives inpatients of all ages; the <65 series helps to separate transmission (`beta`) from severity (`p_h`) |
| Observed series | 65+ admissions by vaccination × comorbidity (4 series) | Admissions <65 and 65+ (2 series; 65+ = `nv` + `v`) | NHIS has no vaccination status |
| `p_h_v` | Calibrated (2 parameters) | Fixed: `p_h_v = (1 − ve) · p_h_nv`, `ve = 0.20` | Not identifiable without admissions by vaccination status. See [model-inputs.md](model-inputs.md) |
| Who receives a dose | Susceptible only (`S_nv → S_v`) | Susceptible and recovered, in proportion to size (`S`, `R`: `nv → v`) | See below |
| Calibration window | 2016 W37 to 2017 W17 | 2016 W36 to 2017 W10 | Korea has a second wave of influenza B from March 2017. A one-strain model cannot fit it |
| Population and demography | Valencian values | MOIS, 31-12-2016, derived rates | See [model-inputs.md](model-inputs.md) |
| Weeks | ISO (Monday to Sunday) | KDCA (Sunday to Saturday) | Source data |
| `commol` | Local `main` (editable) | Git commit `af3b38d` (the same code) | Reproducible environment |

### Who receives a dose

In LoRegne, every dose moves a person from `S_nv` to `S_v`. In Korea this is not possible:
82.8% of the 65+ group is vaccinated, but the susceptible fraction at the start of the season
is calibrated between 40% and 70% of the population (LoRegne calibrated 57%). The doses would
empty `S_nv` and make it negative.

The Korean model gives each dose to a non-vaccinated person aged 65+ who is not infected and
not in hospital. The dose goes to `S` or `R` in proportion to their size:

```
flow S_o65_nv → S_o65_v = campaign · doses · S_o65_nv / (S_o65_nv + R_o65_nv)
flow R_o65_nv → R_o65_v = campaign · doses · R_o65_nv / (S_o65_nv + R_o65_nv)
```

A dose given to `R` changes no outcome, but the vaccinated share of the group stays equal to
the coverage. `campaign` is 1 in the calibration. The scenario without vaccination sets it
to 0.

**Effect on the comparison.** In LoRegne, all doses go to susceptible persons. With the
calibrated `S` = 0.57 of the population, this puts about 1/0.57 ≈ 1.75 times more doses on
susceptible persons than a proportional allocation. To compare the two regions on equal terms, LoRegne should use
the same proportional allocation. This is a proposal for LoRegne; it is not done.

## Calibration

Same method as LoRegne: particle swarm (50 particles, 400 iterations), loss = SSE of the
normalized series, seed 12345. Calibrated parameters: `beta`, the latency and recovery
rates, the hospital rates (narrow bounds, as in LoRegne), `p_h_y`, `p_h_nv`, and the initial
`S`, `E`, `IR`, `IH` (`R` is the remainder, `H` = 0).

## How to run

```bash
.venv/bin/python -E -s scripts/model_inputs.py   # data/model/2016-2017.csv and .json
.venv/bin/python -E -s flu.py                    # calibration and scenarios -> results/
.venv/bin/python -E -s -m pytest                 # tests
```

The run options (data file, calibration window, VE, seed, probabilistic calibration,
scenarios) are the fields of `flu_korea.settings.Settings`. To change one for a single run:

```python
from dataclasses import replace
from flu_korea.cli import main
from flu_korea.settings import Settings

main(replace(Settings(), vaccine_effectiveness=0.4))
```

## Code layout

`flu.py` only calls `flu_korea.cli.main`, so the entry point has the same name as in
LoRegne. A run is a chain of objects, from the data to the results, and
`workflows.pipeline.Pipeline` runs it:

```
Settings -> ModelInputs -> Study -> Fit -> RunEnsemble, ScenarioComparison -> RunStore, Figures
```

| Object | Module | Role |
|---|---|---|
| `ModelInputs` | `adapters/model_inputs.py` | Reads `data/model/` and gives the `Study` |
| `Study` | `calibration/study.py` | The inputs of a season: `calibrate`, `calibrate_probabilistic`, `resume` give a `Fit` |
| `Fit` | `calibration/fit.py` | The calibrated model and its parameter sets: `simulate` gives a `RunEnsemble`, `compare_scenarios` a `ScenarioComparison` |
| `RunEnsemble` | `reporting/ensemble.py` | A point run and its members: summary, reports, weekly bands |
| `ScenarioComparison` | `scenarios/comparison.py` | Every scenario as a `RunEnsemble`, compared member by member |
| `RunStore`, `Figures` | `adapters/` | The files and figures of a run |

The model is `SeirModelSpec` (`model/builder.py`) with its parts `Transmission`,
`Vaccination` and `Demography`, the parameters `InitialConditions` and `FixedParameters`,
and the time `ModelAxis` and `SeasonTimeline` (`timeline.py`). A module imports only from
its own layer or from a layer above it: domain (`commol_gaps`, `timeline`, `season`,
`model/`), application (`calibration/`, `reporting/`, `scenarios/`), adapters
(`adapters/`), workflows (`workflows/`), entry point (`cli`).

The package uses the classes of commol only. commol gives some operations as functions
alone (the window grid, windowed totals of some outputs, member statistics, the
reports). They are behind the classes of `commol_gaps.py`, the one module that calls
them, and each class names the commol issue that makes it unnecessary.

The season (first week and number of weeks) is in `Settings`, so another season needs no
change of code.

The KDCA week rule comes from `scripts/common.py`, so the model and the data pipeline use the
same weeks.

## First results (run `results/calibration_20261020T142617793029Z`)

Deterministic calibration, VE = 0.20, commol `af3b38d`, seed 12345. The particle swarm
stopped at the iteration limit (400), as in LoRegne. Final loss 2.78.

| Quantity | Value |
|---|---|
| Initial susceptible fraction (`S`) | 0.44 |
| Mean latency / recovery | about 0.7 / 2.1 days |
| `p_h_y` (<65) | 1.09% |
| `p_h_nv` (65+, not vaccinated) | 1.16% |
| Attack rate, 33 weeks | 22.9% |
| Hospital admissions, 33 weeks | 127,121 |
| Admissions averted by the 2016 campaign | 3,293 (2.5% of the scenario without vaccination) |
| Infections averted | 25,708 |

`figures/observed_fit.png` shows the fit to both series. The model follows the peak week
and height of the 65+ series, and peaks a little low and late for <65.

Points to review:

- The initial `E`, `IR` and `IH` are at their lower bound (1e-8 of the population, 0.5
  persons each). The timing of the epidemic then depends on `beta` alone. A later start of
  the simulation or lower bounds may change the fit.
- `p_h_y` and `p_h_nv` are almost equal. With homogeneous mixing, both age groups have the
  same attack rate, so the ratio of the two parameters is the ratio of admissions per
  person, which NHIS gives as similar (0.24% <65 and 0.23% 65+, 2016 W36 to 2017 W10). A
  model with the contact matrix of Son et al. 2025 would separate attack rate and severity
  by age.
- In this model the vaccine reduces hospitalization only, not infection (as in LoRegne).
  The infections averted come from fewer persons in `IH`, who stay infectious longer.
- The result depends on VE. A sensitivity analysis from 0% to 48% is still to do.
