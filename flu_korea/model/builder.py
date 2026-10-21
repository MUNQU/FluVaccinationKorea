"""Assembly of the SEIR model from its parts."""

from dataclasses import dataclass

from commol import Aggregate, Model, ModelBuilder

from flu_korea.model.compartments import (
    AGE_GROUPS,
    BIN_NAMES,
    DISEASE_BINS,
    O65_GROUPS,
)
from flu_korea.model.conditions import O65
from flu_korea.model.demography import Demography
from flu_korea.model.parameters import (
    CALIBRATED_MODEL_PARAMETERS,
    FORMULA_PARAMETERS,
    FixedParameters,
    InitialConditions,
)
from flu_korea.model.transmission import Transmission
from flu_korea.model.vaccination import Vaccination
from flu_korea.season import Population
from flu_korea.timeline import ENGINE, STEP_UNIT

ACCUMULATOR_NAMES = {
    "hospital_admissions": "Cumulative hospital admissions",
    "infection_incidence": "Cumulative infection incidence",
}


@dataclass(frozen=True)
class SeirModelSpec:
    """Everything the SEIR model of one season is built from."""

    population: Population
    weekly_doses: list[float]
    vaccine_effectiveness: float

    @property
    def vaccination(self) -> Vaccination:
        return Vaccination(self.weekly_doses)

    @property
    def initial_conditions(self) -> InitialConditions:
        return InitialConditions(self.population.total)

    def builder(self) -> ModelBuilder:
        builder = ModelBuilder(name="SEIR-Korea", version="1.0", step_unit=STEP_UNIT)
        builder = self._add_bins_and_stratifications(builder)
        builder = self._add_parameters(builder)
        for part in (Transmission(), self.vaccination, Demography()):
            builder = part.add_to(builder)
        return builder

    def build(self) -> Model:
        # Nobody is vaccinated at the start of the season; the whole 65+ group
        # begins in the `nv` vaccination category and coverage is built only by
        # the weekly doses.
        population = self.population
        return self.builder().build(
            Aggregate(
                bin_amounts=self.initial_conditions.amounts(),
                stratification_fractions={
                    "age": {
                        "y65": population.under_65 / population.total,
                        "o65": population.aged_65_plus / population.total,
                    },
                    "vaccination": {"nv": 1.0, "v": 0.0},
                },
            ),
            engine=ENGINE,
        )

    def _add_bins_and_stratifications(self, builder: ModelBuilder) -> ModelBuilder:
        for bin_id in DISEASE_BINS:
            builder.add_bin(id=bin_id, name=BIN_NAMES[bin_id])
        for accumulator_id, name in ACCUMULATOR_NAMES.items():
            builder.add_accumulator(id=accumulator_id, name=name)

        return builder.add_stratification(
            id="age", categories=list(AGE_GROUPS)
        ).add_stratification(
            id="vaccination", categories=list(O65_GROUPS), conditions=O65
        )

    def _add_parameters(self, builder: ModelBuilder) -> ModelBuilder:
        calibrated = [
            (spec.id, None, spec.description) for spec in CALIBRATED_MODEL_PARAMETERS
        ]
        fixed = FixedParameters(self.population, self.vaccine_effectiveness)
        for param_id, value, description in (
            *calibrated,
            *fixed.values(),
            *FORMULA_PARAMETERS,
        ):
            builder.add_parameter(id=param_id, value=value, description=description)
        return self.vaccination.add_parameter_to(builder)
