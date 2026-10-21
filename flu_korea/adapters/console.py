"""Progress messages of a run on the console."""

import pathlib

from commol import BootstrapResult

from flu_korea.calibration.fit import Fit


class Console:
    """Messages of the steps of a run."""

    def seed(self, seed: int) -> None:
        print(f"Seed: {seed}")

    def fit(self, fit: Fit, confidence_level: float) -> None:
        """How the calibration went, and the calibrated values."""
        result = fit.result
        if isinstance(result, BootstrapResult):
            diagnostics = result.diagnostics
            print(f"Fit loss: {result.fit.final_loss:.4e}")
            print(f"Replicates: {len(result.sample)}")
            print(f"Block length (weeks): {diagnostics.block_length}")
            print(f"Failed replicates: {len(diagnostics.failed)}")
            print(f"Not converged: {diagnostics.not_converged}")
            intervals = result.sample.interval(confidence_level)
            for param_id, value in result.fit.best_parameters.items():
                lower, upper = intervals[param_id]
                print(f"  {param_id} = {value:.6e}, ci=[{lower:.6e}, {upper:.6e}]")
        elif result is not None:
            print(f"Converged: {result.converged}")
            print(f"Iterations: {result.iterations}")
            print(f"Final loss: {result.final_loss:.4e}")
            print(f"Reason: {result.termination_reason}")
            for param_id, value in result.best_parameters.items():
                print(f"  {param_id} = {value:.6e}")

    def saved(self, what: str, directory: pathlib.Path) -> None:
        print(f"{what} saved to: {directory}")

    def reusing(self, directory: pathlib.Path) -> None:
        print(f"Reusing calibrated parameters from: {directory}")
