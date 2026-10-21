"""Run the model with the options in `Settings`."""

import logging

import matplotlib.pyplot as plt

from flu_korea.settings import Settings
from flu_korea.workflows.pipeline import Pipeline


def main(settings: Settings | None = None) -> None:
    pipeline = Pipeline(settings or Settings())
    # Show progress logs, including the warnings of failed bootstrap replicates.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    pipeline.run()
    plt.show()
