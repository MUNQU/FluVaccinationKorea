"""Births, aging from <65 to 65+, and deaths."""

from commol import ModelBuilder

from flu_korea.model.compartments import AGING_BINS, DISEASE_BINS
from flu_korea.model.conditions import O65, Y65, StratifiedRate

# Aging moves a person from <65 to the non-vaccinated 65+.
AGING_CONDITIONS = [
    {"stratification": "age", "category": "y65", "to": "o65"},
    {"stratification": "vaccination", "to": "nv"},
]


class Demography:
    """Births into <65, aging into 65+, and deaths from every bin."""

    def add_to(self, builder: ModelBuilder) -> ModelBuilder:
        builder.add_transition(
            id="births",
            source=[],
            target=["S"],
            stratified_rates=[StratifiedRate(Y65, "births").entry()],
        )

        for bin_id in AGING_BINS:
            builder.add_transition(
                id=f"{bin_id}_y65_to_{bin_id}_o65",
                source=[bin_id],
                target=[bin_id],
                per_compartment=True,
                stratified_rates=[
                    StratifiedRate(AGING_CONDITIONS, f"aging * {bin_id}").entry()
                ],
            )

        # One transition per bin: a `$compartment` rate over several sources
        # would read the total of each bin, not the compartment that flows.
        for bin_id in DISEASE_BINS:
            builder.add_transition(
                id=f"{bin_id}_death",
                source=[bin_id],
                target=[],
                rate=f"death_y65 * {bin_id}",
                per_compartment=True,
                stratified_rates=[StratifiedRate(O65, f"death_o65 * {bin_id}").entry()],
            )
        return builder
