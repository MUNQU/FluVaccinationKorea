"""Run options and file locations."""

import pathlib
import secrets
from dataclasses import dataclass
from typing import Literal

ROOT = pathlib.Path(__file__).resolve().parent.parent

Resolution = Literal["step", "daily", "weekly"]


@dataclass(frozen=True)
class Settings:
    """Options of one run. Change a value with `dataclasses.replace`."""

    data_file: pathlib.Path = ROOT / "data" / "model" / "2016-2017.csv"
    results_dir: pathlib.Path = ROOT / "results"
    # KDCA epi week of week index 0, and the number of simulated weeks.
    first_week: str = "2016-36"
    simulation_weeks: int = 33
    # Last week of the calibration window. The season has a second wave of
    # influenza B from March 2017, which a one-strain model cannot fit, so the
    # fit stops at the low point between the two waves (NHIS 65+ inpatients).
    calibration_last_week: str = "2017-10"
    # Vaccine effectiveness against hospitalization, 65+
    # (docs/model-inputs.md).
    vaccine_effectiveness: float = 0.20
    # Probabilistic calibration is a Bayesian block bootstrap: every replicate
    # refits the model to the observations reweighted by blocks of weeks, and
    # the replicate fits are the members the intervals are read from.
    use_probabilistic_calibration: bool = False
    # Calibrate, then re-simulate the calibrated model with and without this
    # season's vaccination campaign and compare the two.
    compare_scenarios: bool = True
    save_full_probabilistic_result: bool = True
    # Whether the reported-case (sentinel incidence) series takes part in the
    # fit. Turning it off also drops `case_reporting_rate` from the calibrated
    # parameters, since that parameter only ever scales this series and would
    # otherwise be unidentifiable. The Korean data file has no `Reported`
    # column yet.
    calibrate_against_reported_cases: bool = False
    # Weeks per bootstrap block. "auto" estimates it from the residuals of the
    # fit (Politis and White), so the autocorrelation of the weekly residuals
    # stays inside a block; 1 treats every week as independent.
    bootstrap_block_length: int | Literal["auto"] = "auto"
    # Level of every interval of a probabilistic run.
    confidence_level: float = 0.95
    # Master seed of the run. Set to None to draw a fresh one; either way the
    # value actually used is resolved in Python and recorded in
    # `metadata.json`, so a run is always reproducible from its own outputs.
    seed: int | None = 12345
    # Time resolution of `simulation_results.json`. `simulation_raw.json.gz`
    # always keeps every step, and the figures are always plotted at full
    # resolution.
    output_resolution: Resolution = "weekly"

    @property
    def inputs_file(self) -> pathlib.Path:
        """Population and demographic rates, built with the data file."""
        return self.data_file.with_suffix(".json")

    def resolve_seed(self, seed: int | None = None) -> int:
        """
        Seed the run will actually use: the caller's, the option, or a draw.

        `CalibrationProblem.seed` is the single seed the library takes; the
        optimizer config and every probabilistic stage derive theirs from it.
        Left as None it would reach the optimizer, which seeds itself from
        entropy and never reports what it drew, so the run could not be
        reproduced from its own outputs. Resolving it here, at every entry
        point that builds a problem, means the seed is always known and always
        recorded in `metadata.json`.
        """
        if seed is not None:
            return seed
        if self.seed is not None:
            return self.seed
        return secrets.randbits(32)
