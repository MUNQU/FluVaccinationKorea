"""Infection, hospitalization and recovery transitions."""

from commol import ModelBuilder

from flu_korea.model.conditions import O65_GROUP, StratifiedRate


class Transmission:
    """The course of an infection, from S to R, with or without hospital."""

    def add_to(self, builder: ModelBuilder) -> ModelBuilder:
        # With `per_compartment`, the source bin of a rate (S, E, IR, IH, H)
        # reads the compartment that flows; any other bin (IR + IH below) is
        # its total. The default rate is the one of <65; the 65+ rates override
        # it only where a parameter depends on the vaccination status.
        def per_o65_group(template: str) -> list[dict[str, object]]:
            return [rate.entry() for rate in StratifiedRate.per_o65_group(template)]

        def vaccinated(rate: str) -> list[dict[str, object]]:
            return [StratifiedRate(O65_GROUP["v"], rate).entry()]

        return (
            builder.add_transition(
                id="susceptble_to_latent",
                source=["S"],
                target=["E"],
                accumulators=["infection_incidence"],
                # Hospital-bound infectious (IH) transmit at the same rate as
                # community-recovering infectious (IR), as in LoRegne.
                rate="beta * S * (IR + IH) / total",
                per_compartment=True,
            )
            .add_transition(
                id="exposed_to_infectious",
                source=["E"],
                target=["IR"],
                rate="(1 - p_h_y) * t_latency * E",
                per_compartment=True,
                stratified_rates=per_o65_group("(1 - p_h_{v}) * t_latency * E"),
            )
            .add_transition(
                id="exposed_to_hospital_bound_infectious",
                source=["E"],
                target=["IH"],
                rate="p_h_y * t_latency * E",
                per_compartment=True,
                stratified_rates=per_o65_group("p_h_{v} * t_latency * E"),
            )
            .add_transition(
                id="infectious_to_recovered",
                source=["IR"],
                target=["R"],
                rate="t_recovery * IR",
                per_compartment=True,
            )
            .add_transition(
                id="hospital_bound_infectious_to_hospitalized",
                source=["IH"],
                target=["H"],
                accumulators=["hospital_admissions"],
                rate="t_hospitalization_nv * IH",
                per_compartment=True,
                stratified_rates=vaccinated("t_hospitalization_v * IH"),
            )
            .add_transition(
                id="hospitalized_to_recovered",
                source=["H"],
                target=["R"],
                rate="t_hospitalization_recovery_nv * H",
                per_compartment=True,
                stratified_rates=vaccinated("t_hospitalization_recovery_v * H"),
            )
        )
