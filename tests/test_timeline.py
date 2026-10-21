from datetime import date

from flu_korea.timeline import AXIS, STEPS_PER_WEEK, SeasonTimeline

TIMELINE = SeasonTimeline.from_week_label("2016-36", simulation_weeks=33)


def test_origin_is_the_sunday_of_kdca_2016_week_36():
    assert TIMELINE.origin == date(2016, 8, 28)
    assert TIMELINE.week_label(0) == "2016-36"


def test_2016_has_53_kdca_weeks():
    assert TIMELINE.week_label(17) == "2016-53"
    assert TIMELINE.week_label(18) == "2017-01"


def test_labels_and_indices_are_inverse():
    for week_idx in range(60):
        assert TIMELINE.week_idx_from_label(TIMELINE.week_label(week_idx)) == week_idx


def test_week_before_origin_has_no_index():
    assert TIMELINE.week_idx_from_label("2016-35") is None


def test_another_season_has_its_own_origin():
    later = SeasonTimeline.from_week_label("2017-36", simulation_weeks=33)
    assert later.week_label(0) == "2017-36"
    assert TIMELINE.week_idx_from_label("2017-36") == 53


def test_week_end_step_closes_its_week():
    for week_idx in range(33):
        step = AXIS.week_end_step(week_idx)
        assert AXIS.step_to_week_idx(step) == week_idx
        assert AXIS.step_to_week_idx(step - STEPS_PER_WEEK + 1) == week_idx


def test_weekly_output_steps_are_the_week_ends():
    assert TIMELINE.output_steps("weekly") == [AXIS.week_end_step(w) for w in range(33)]
    assert TIMELINE.final_step == 33 * STEPS_PER_WEEK
