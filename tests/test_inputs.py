import pandas as pd

from flu_korea.adapters.model_inputs import ModelInputs
from flu_korea.settings import Settings


def test_season_data_stops_at_the_calibration_window():
    settings = Settings()
    study = ModelInputs(settings).study()
    timeline, data = study.timeline, study.data
    weeks = [week_idx for week_idx, *_ in data.hospitalizations]
    assert weeks == list(range(timeline.week_idx_from_label("2017-10") + 1))
    raw = pd.read_csv(settings.data_file)
    assert sum(data.weekly_doses) == raw["Vaccinations"].sum()


def test_population_matches_the_inputs_file():
    population = ModelInputs(Settings()).population()
    assert population.total == population.under_65 + population.aged_65_plus
    assert population.aged_65_plus > 0


def test_resolve_seed_prefers_the_caller():
    assert Settings(seed=1).resolve_seed(7) == 7
    assert Settings(seed=1).resolve_seed() == 1
