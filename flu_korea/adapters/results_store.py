"""Write and read the files of a calibration run in `results/`."""

import gzip
import importlib.metadata
import json
import pathlib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel

from commol import BootstrapResult, CalibrationResult, ObservedDataPoint

from flu_korea.calibration.fit import Fit
from flu_korea.commol_gaps import AppliedParameters
from flu_korea.reporting.ensemble import RunEnsemble
from flu_korea.scenarios.comparison import SCENARIO_LABELS, ScenarioComparison
from flu_korea.settings import Settings
from flu_korea.timeline import STEP_UNIT, STEPS_PER_DAY, STEPS_PER_WEEK

# Numeric arrays with at least this many entries are written on one line, so
# a series takes one line of the file, as in `Model.to_json`.
INLINE_ARRAY_MIN_LENGTH = 8
_INLINE_TOKEN = re.compile(r'"@@inline:(\d+)@@"')


def _is_number(value: object) -> bool:
    """A JSON number or null; a boolean is not a number."""
    return value is None or (
        isinstance(value, int | float) and not isinstance(value, bool)
    )


def _is_numeric_array(values: list[object]) -> bool:
    """A flat array of numbers, or an array of such arrays."""
    return all(_is_number(item) for item in values) or all(
        isinstance(item, list) and all(_is_number(entry) for entry in item)
        for item in values
    )


def _inline_arrays(payload: object, inlined: list[str]) -> object:
    """Replace each long numeric array by a placeholder of its one-line form."""
    if isinstance(payload, list):
        if len(payload) >= INLINE_ARRAY_MIN_LENGTH and _is_numeric_array(payload):
            inlined.append(json.dumps(payload))
            return f"@@inline:{len(inlined) - 1}@@"
        return [_inline_arrays(item, inlined) for item in payload]
    if isinstance(payload, dict):
        return {key: _inline_arrays(value, inlined) for key, value in payload.items()}
    return payload


def _render_json(payload: object) -> str:
    """
    JSON in declaration order, with long numeric arrays on one line.

    The arrays go through placeholders, so no pattern is applied to the data.
    """
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    inlined: list[str] = []
    rendered = json.dumps(_inline_arrays(payload, inlined), indent=2)
    return _INLINE_TOKEN.sub(lambda match: inlined[int(match.group(1))], rendered)


def _commol_provenance() -> dict[str, object]:
    """Version of commol and, for a git install, the commit it was built from."""
    distribution = importlib.metadata.distribution("commol")
    direct_url = distribution.read_text("direct_url.json")
    return {
        "version": distribution.version,
        "source": json.loads(direct_url) if direct_url else None,
    }


def _calibration_metadata(
    result: CalibrationResult | BootstrapResult,
) -> dict[str, object]:
    """
    How the fit went, as the only record of it now that the calibrated values
    themselves live in `applied_parameters.json`.
    """
    fit = result.fit if isinstance(result, BootstrapResult) else result
    metadata: dict[str, object] = {
        "converged": fit.converged,
        "iterations": fit.iterations,
        "final_loss": fit.final_loss,
        "termination_reason": fit.termination_reason,
    }
    if isinstance(result, BootstrapResult):
        diagnostics = result.diagnostics
        metadata["bootstrap"] = {
            "method": "bayesian_block_bootstrap",
            "replicates": len(result.sample),
            "block_length": diagnostics.block_length,
            # Estimated block length of each series, when it was "auto".
            "block_length_estimates": diagnostics.block_length_estimates,
            "failed": diagnostics.failed,
            "not_converged": diagnostics.not_converged,
        }
    return metadata


@dataclass(frozen=True)
class SavedCalibration:
    """The parameter sets a previous calibration produced."""

    kind: str
    point: dict[str, float]
    # Empty for a deterministic run.
    members: list[dict[str, float]]
    confidence_level: float | None
    # The rebuilt calibration problem has to match it.
    calibrated_against_reported_cases: bool


@dataclass(frozen=True)
class RunStore:
    """The directory of one calibration run, and the files in it."""

    directory: pathlib.Path

    @classmethod
    def create(cls, results_dir: pathlib.Path, kind: str) -> "RunStore":
        """A new, empty run directory named by its kind and the time."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory = results_dir / f"{kind}_{timestamp}"
        directory.mkdir(parents=True, exist_ok=False)
        return cls(directory)

    def path(self, name: str) -> pathlib.Path:
        return self.directory / name

    def fresh_subdirectory(self, name: str) -> "RunStore":
        """
        An empty subdirectory. It is rebuilt, so writing it again never leaves
        a mix of old and new files.
        """
        directory = self.path(name)
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        return RunStore(directory)

    def write_json(self, name: str, payload: object) -> None:
        self.path(name).write_text(_render_json(payload), encoding="utf-8")

    def write_json_gz(self, name: str, payload: object) -> None:
        """Write gzipped JSON, for the full-resolution per-member simulations."""
        with gzip.open(self.path(name), "wt", encoding="utf-8") as handle:
            handle.write(_render_json(payload))

    def save_fit(self, fit: Fit, settings: Settings) -> None:
        """Write the parameters, model and metadata of a calibration."""
        result = fit.result
        if result is None:
            raise ValueError("A fit read back from a run has no result to save.")
        bootstrap = isinstance(result, BootstrapResult)
        calibration = result.fit if bootstrap else result
        self.write_json(
            "metadata.json",
            {
                "kind": fit.kind,
                "csv_path": str(settings.data_file),
                "seed": fit.seed,
                "calibrated_against_reported_cases": (
                    settings.calibrate_against_reported_cases
                ),
                "calibration_last_week": settings.calibration_last_week,
                "vaccine_effectiveness": settings.vaccine_effectiveness,
                "commol": _commol_provenance(),
                "step_unit": STEP_UNIT,
                "steps_per_day": STEPS_PER_DAY,
                "steps_per_week": STEPS_PER_WEEK,
                "simulation_weeks": settings.simulation_weeks,
                "output_resolution": settings.output_resolution,
                "calibration": _calibration_metadata(result),
            },
        )
        if bootstrap and settings.save_full_probabilistic_result:
            self.write_json("calibration_result_full.json", result)
        self.write_json(
            "applied_parameters.json",
            AppliedParameters(fit.model, fit.problem).report(
                calibration,
                sample=result.sample if bootstrap else None,
                confidence_level=settings.confidence_level if bootstrap else None,
            ),
        )
        self.write_json(
            "calibrated_parameters.json",
            {
                "kind": fit.kind,
                "calibrated_against_reported_cases": (
                    settings.calibrate_against_reported_cases
                ),
                "confidence_level": settings.confidence_level if bootstrap else None,
                "point": calibration.best_parameters,
                "members": list(result.sample.draws()) if bootstrap else [],
            },
        )
        fit.model.to_json(self.path("calibrated_model.json"))
        description = fit.model.describe()
        description.save(self.path("equations.txt"))
        description.save(self.path("equations.tex"))

    def save_run(self, fit: Fit, ensemble: RunEnsemble, resolution: str) -> None:
        """
        Write the reduced results of the runs of a fit, and the raw runs behind
        them.
        """
        self.write_json(
            "simulation_results.json",
            ensemble.results_report(fit.kind, fit.problem.observed_data, resolution),
        )
        self.write_json_gz(
            "simulation_raw.json.gz",
            ensemble.raw_report(
                fit.kind,
                fit.model,
                fit.problem,
                fit.point_parameters,
                member_parameters=fit.member_parameters,
            ),
        )

    def save_scenarios(
        self,
        comparison: ScenarioComparison,
        observed_data: list[ObservedDataPoint],
        resolution: str,
    ) -> None:
        """Write the report of each scenario and the comparison."""
        for scenario in SCENARIO_LABELS:
            self.write_json(
                f"{scenario}.json",
                comparison.scenario_report(scenario, observed_data, resolution),
            )
        self.write_json("comparison.json", comparison.report())

    def load_calibration(self, default_reported_cases: bool) -> SavedCalibration:
        """
        Read the parameter sets of the calibration saved here.

        `default_reported_cases` applies to runs that do not record whether the
        reported-case series was fitted.

        Raises
        ------
        FileNotFoundError
            If the directory holds no `calibrated_parameters.json`.
        """
        path = self.path("calibrated_parameters.json")
        if not path.exists():
            raise FileNotFoundError(
                f"No calibrated parameters in '{self.directory}'. Expected "
                f"{path.name}, which every calibration run writes."
            )
        saved = json.loads(path.read_text(encoding="utf-8"))
        return SavedCalibration(
            kind=saved.get("kind", "calibration"),
            point=saved["point"],
            members=saved.get("members") or [],
            confidence_level=saved.get("confidence_level"),
            calibrated_against_reported_cases=saved.get(
                "calibrated_against_reported_cases", default_reported_cases
            ),
        )
