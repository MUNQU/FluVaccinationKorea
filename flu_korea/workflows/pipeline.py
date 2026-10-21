"""The chain of a run: inputs, fit, simulations, scenarios, files."""

import pathlib

from flu_korea.adapters.console import Console
from flu_korea.adapters.figures import Figures
from flu_korea.adapters.model_inputs import ModelInputs
from flu_korea.adapters.results_store import RunStore
from flu_korea.calibration.fit import Fit
from flu_korea.calibration.study import Study
from flu_korea.reporting.observed import ObservedData
from flu_korea.settings import Settings


class Pipeline:
    """
    One run of the study, from the data to the files of the results:

    `ModelInputs` -> `Study` -> `Fit` -> `RunEnsemble` and `ScenarioComparison`
    -> `RunStore` and `Figures`.
    """

    def __init__(self, settings: Settings, console: Console | None = None) -> None:
        self.settings = settings
        self.console = console or Console()
        self.study: Study = ModelInputs(settings).study()

    def run(self) -> RunStore:
        """The workflow that `settings` selects."""
        if self.settings.compare_scenarios:
            return self.compare_scenarios()
        return self.calibrate()[0]

    def calibrate(
        self,
        probabilistic: bool | None = None,
        seed: int | None = None,
        **calibration_options: int,
    ) -> tuple[RunStore, Fit]:
        """
        Calibrate, then write the fit, its simulations and their figures to a
        new run directory.

        `calibration_options` go to the probabilistic calibration, for
        instance `replicates` or `pso_iterations`.
        """
        settings = self.settings
        if probabilistic is None:
            probabilistic = settings.use_probabilistic_calibration
        seed = settings.resolve_seed(seed)
        self.console.seed(seed)
        if probabilistic:
            fit = self.study.calibrate_probabilistic(
                seed,
                settings.confidence_level,
                block_length=settings.bootstrap_block_length,
                **calibration_options,
            )
        else:
            fit = self.study.calibrate(seed)
        self.console.fit(fit, settings.confidence_level)

        store = RunStore.create(settings.results_dir, fit.kind)
        store.save_fit(fit, settings)
        self.console.saved("Calibration outputs", store.directory)

        ensemble = fit.simulate()
        store.save_run(fit, ensemble, settings.output_resolution)
        figures_dir = store.path("figures")
        figures_dir.mkdir()
        Figures(figures_dir, ObservedData(fit.problem.observed_data)).calibration(
            ensemble, ensemble.predictive or fit.result
        )
        return store, fit

    def resume(self, run_dir: pathlib.Path) -> tuple[RunStore, Fit]:
        """The fit of a previous run, read from its directory."""
        store = RunStore(run_dir)
        saved = store.load_calibration(self.settings.calibrate_against_reported_cases)
        fit = self.study.resume(
            saved.kind,
            saved.point,
            saved.members or None,
            saved.confidence_level,
            saved.calibrated_against_reported_cases,
            self.settings.resolve_seed(),
        )
        self.console.reusing(run_dir)
        return store, fit

    def compare_scenarios(
        self,
        probabilistic: bool | None = None,
        seed: int | None = None,
        load_from: pathlib.Path | None = None,
        **calibration_options: int,
    ) -> RunStore:
        """
        Calibrate (or reuse the fit of `load_from`), then re-simulate the
        calibrated model under each scenario.

        Every calibrated parameter set is simulated in full under every
        scenario, and the results are reduced afterwards, so an interval
        describes runs that were actually performed. With `load_from`, the
        scenario belongs to the calibration it came from, so it is written
        into that run, replacing any earlier scenario of the same name.
        """
        if load_from is not None:
            store, fit = self.resume(load_from)
        else:
            store, fit = self.calibrate(probabilistic, seed, **calibration_options)

        comparison = fit.compare_scenarios()

        # Everything the scenario produces lives together, laid out like the
        # calibration run and using the same figure names.
        scenario_store = store.fresh_subdirectory("vaccination_scenario")
        scenario_store.save_scenarios(
            comparison, fit.problem.observed_data, self.settings.output_resolution
        )
        figures_dir = scenario_store.path("figures")
        figures_dir.mkdir()
        Figures(figures_dir, ObservedData(fit.problem.observed_data)).scenarios(
            comparison
        )
        self.console.saved("Scenario outputs", scenario_store.directory)
        return store
