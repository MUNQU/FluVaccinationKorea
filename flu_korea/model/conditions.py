"""Stratum conditions and stratified rates used by the transitions."""

from dataclasses import dataclass

from flu_korea.model.compartments import O65_GROUPS

# The shape of a condition of `ModelBuilder.add_stratification` and
# `ModelBuilder.add_transition`.
Condition = dict[str, str]

Y65: list[Condition] = [{"stratification": "age", "category": "y65"}]
O65: list[Condition] = [{"stratification": "age", "category": "o65"}]


def _o65_group(vaccination: str) -> list[Condition]:
    return [*O65, {"stratification": "vaccination", "category": vaccination}]


O65_GROUP = {vaccination: _o65_group(vaccination) for vaccination in O65_GROUPS}


@dataclass(frozen=True)
class StratifiedRate:
    """A rate that applies to the compartments that match its conditions."""

    conditions: list[Condition]
    rate: str

    @classmethod
    def per_o65_group(cls, template: str) -> list["StratifiedRate"]:
        """One rate per o65 group, from a template using `{v}`."""
        return [
            cls(O65_GROUP[vaccination], template.format(v=vaccination))
            for vaccination in O65_GROUPS
        ]

    def entry(self) -> dict[str, object]:
        """The entry of `ModelBuilder.add_transition(stratified_rates=...)`."""
        return {"conditions": self.conditions, "rate": self.rate}
