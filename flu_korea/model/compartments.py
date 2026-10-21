"""Compartments, strata and accumulators of the SEIR model."""

AGE_GROUPS = ("y65", "o65")
O65_GROUPS = ("nv", "v")
# Bins that vaccination moves from `nv` to `v`: persons who are neither
# infected nor in hospital. Doses split between them in proportion to size.
VACCINATED_BINS = ("S", "R")
DISEASE_BINS = ("S", "E", "IR", "IH", "H", "R")
AGING_BINS = ("S", "E", "IR", "IH", "R")
ACCUMULATOR_IDS = ("infection_incidence", "hospital_admissions")

BIN_NAMES = {
    "S": "Susceptible",
    "E": "Exposed",
    "IR": "Infectious",
    "IH": "Infected hospital-bound",
    "H": "Hospitalized",
    "R": "Recovered",
}

# R is the remainder: it takes whatever the calibrated bins leave of the
# population, so the season always starts with exactly the whole population
# and R is not calibrated itself.
INITIAL_CONDITION_REMAINDER = "R"
# H(0) is the one disease bin the calibration neither fits nor derives.
FIXED_BIN_INITIAL_CONDITIONS = {"H": 0.0}
