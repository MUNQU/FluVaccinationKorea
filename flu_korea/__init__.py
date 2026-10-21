"""SEIR model of the 2016-2017 influenza season in South Korea.

Adapted from `flu.py` of FluVaccinationLoRegne (Valencian Community), so that
the two calibrations can be compared. Differences, all forced by the Korean
data (see docs/model.md):

- Age groups <65 and 65+ (NHIS age bands), not <60 and >=60.
- No comorbidity strata (no Korean data by comorbidity).
- Both age groups can be hospitalized, and the fit uses the weekly NHIS
  inpatient episodes of both groups.
- Hospitalization of vaccinated persons is fixed by the vaccine effectiveness:
  p_h_v = (1 - ve) * p_h_nv.
- Vaccine doses go to the non-vaccinated 65+ who are susceptible or recovered,
  in proportion to their size, not to the susceptible only.
- KDCA epi weeks (Sunday to Saturday), season from 2016 W36.

A run is a chain of objects, from the data to the results:

    Settings -> ModelInputs -> Study -> Fit -> RunEnsemble, ScenarioComparison
             -> RunStore, Figures

`workflows.pipeline.Pipeline` runs the chain.

Layers. A module imports only from its own layer or from a layer above it in
this list:

1. Domain: `commol_gaps`, `timeline` (`ModelAxis`, `SeasonTimeline`),
   `season` (`Population`, `SeasonData`), `model` (`SeirModelSpec` with
   `Transmission`, `Vaccination`, `Demography`). No input or output.
2. Application: `calibration` (`Observations`, `CalibrationSetup`, `Study`,
   `Fit`), `reporting` (`RunEnsemble`, `ObservedData`), `scenarios`
   (`ScenarioComparison`). No input or output.
3. Adapters: `adapters` (`ModelInputs`, `RunStore`, `Figures`, `Console`).
4. Workflows: `workflows` (`Pipeline`).
5. Entry point: `cli`.

The package uses the classes of commol only. The operations that commol gives
as functions alone are behind the classes of `commol_gaps`, the one module
that calls them.

`settings` holds the run options. It imports nothing from the package, and
only the adapters, the workflows and the entry point read it.
"""
