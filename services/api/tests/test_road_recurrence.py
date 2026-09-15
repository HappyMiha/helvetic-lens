from datetime import datetime, timedelta

import pytest
from test_road_feed import feed, first, record

from helvetic_lens.road_evaluation import RoadMateriality, evaluate_record, temporal_state
from helvetic_lens.road_feed import RoadFeedError
from helvetic_lens.road_recurrence import ExpansionBudget
from helvetic_lens.road_topology import RoadIntersection


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def recurrence(start='22:00:00Z', end='06:00:00Z', days=('sunday',), *, extra='', calendar_extra='', kind='validPeriod'):
    return (f'<{kind}><recurringTimePeriodOfDay xsi:type="TimePeriodByHour">'
            f'<startTimeOfPeriod>{start}</startTimeOfPeriod><endTimeOfPeriod>{end}</endTimeOfPeriod>'
            '</recurringTimePeriodOfDay><recurringDayWeekMonthPeriod>'
            + ''.join(f'<applicableDay>{day}</applicableDay>' for day in days)
            + calendar_extra + '</recurringDayWeekMonthPeriod>' + extra + f'</{kind}>')


def source(periods=None, *, end='2026-10-01T00:00:00Z', start='2026-09-13T09:30:00Z'):
    extra = ('' if end is None else f'<overallEndTime>{end}</overallEndTime>') + (recurrence() if periods is None else periods)
    return first(feed(record(validity_extra=extra)).replace('2026-09-13T09:30:00Z', start))


def state(item, clock):
    return temporal_state(item, now=instant(clock))


def test_night_uses_start_day_and_advances_to_next_week_without_false_reopening():
    item = source()
    assert not item.unsupported
    before = state(item, '2026-09-13T21:59:59Z')
    assert before.phase == 'planned' and before.window.start == instant('2026-09-13T22:00:00Z')
    active = state(item, '2026-09-14T05:59:59Z')
    assert active.phase == 'active' and active.window.end == instant('2026-09-14T06:00:00Z')
    after = state(item, '2026-09-14T06:00:00Z')
    assert after.phase == 'planned' and after.window.start == instant('2026-09-20T22:00:00Z')
    assert state(item, '2026-10-01T00:00:00Z').phase == 'expired'
    decision = evaluate_record(item, RoadIntersection('match', 'synthetic'), RoadMateriality(include_planned=False), now=instant('2026-09-14T06:00:00Z'))
    assert decision.state == 'filtered'


def test_exceptions_override_valid_windows_including_after_midnight():
    item = source(recurrence() + recurrence('23:00:00Z', '01:00:00Z', kind='exceptionPeriod'))
    first_window = state(item, '2026-09-13T22:30:00Z')
    assert first_window.window.end == instant('2026-09-13T23:00:00Z')
    excluded = state(item, '2026-09-14T00:30:00Z')
    assert excluded.phase == 'planned' and excluded.window.start == instant('2026-09-14T01:00:00Z')
    last = state(item, '2026-09-14T01:00:00Z')
    assert last.phase == 'active' and last.window.end == instant('2026-09-14T06:00:00Z')


@pytest.mark.parametrize('offset,clock,expected', [('+14:00', '2026-09-13T07:59:59Z', '2026-09-13T08:00:00Z'), ('-10:00', '2026-09-14T07:59:59Z', '2026-09-14T08:00:00Z'), ('+02:00', '2026-10-25T19:59:59Z', '2026-10-25T20:00:00Z')])
def test_explicit_source_offset_is_preserved_not_reinterpreted_as_zurich_dst(offset, clock, expected):
    item = source(recurrence('22:00:00' + offset, '06:00:00' + offset), end='2026-11-01T00:00:00Z', start='2026-09-01T00:00:00Z')
    result = state(item, clock)
    assert result.phase == 'planned' and result.window.start == instant(expected)
    assert result.window.end - result.window.start == timedelta(hours=8)


def test_calendar_intersection_fifth_week_leap_day_and_no_guessed_far_future():
    rules = recurrence('10:00:00Z', '12:00:00Z', ('tuesday',), calendar_extra='<applicableMonth>february</applicableMonth><applicableWeek>fifthWeekOfMonth</applicableWeek>')
    item = source(rules, start='2026-01-01T00:00:00Z', end=None)
    assert state(item, '2027-03-01T00:00:00Z').window.start == instant('2028-02-29T10:00:00Z')
    unavailable = state(item, '2026-03-01T00:00:00Z')
    assert unavailable.phase == 'unknown' and unavailable.reason == 'recurrence_lookahead_exhausted'


def test_multiple_rules_are_stable_under_reordering_and_material_on_reschedule():
    a, b = recurrence(), recurrence('08:00:00Z', '10:00:00Z', ('monday',))
    assert source(a+b).semantic_hash == source(b+a).semantic_hash
    assert source(a+a).semantic_hash == source(a).semantic_hash
    assert source(a).semantic_hash != source(a.replace('22:00:00', '23:00:00')).semantic_hash


@pytest.mark.parametrize('rules', [recurrence('22:00:00', '06:00:00'), recurrence('22:00:00+02:00', '06:00:00+01:00'), recurrence('22:00:00Z', '22:00:00Z'), recurrence(extra='<periodExtension/>'), '<validPeriod><recurringDayWeekMonthPeriod><applicableDay>monday</applicableDay></recurringDayWeekMonthPeriod></validPeriod>'])
def test_ambiguous_clock_or_unsupported_extension_is_unknown(rules):
    item = source(rules)
    assert 'recurring_period' in item.unsupported
    assert state(item, '2026-09-13T23:00:00Z').phase == 'unknown'


@pytest.mark.parametrize('rules', [recurrence('25:00:00Z'), recurrence('22:00:00+14:01'), recurrence(days=('notaday',)), recurrence(calendar_extra='<applicableWeek>sixthWeekOfMonth</applicableWeek>'), recurrence().replace('</endTimeOfPeriod>', '</endTimeOfPeriod><endTimeOfPeriod>07:00:00Z</endTimeOfPeriod>')])
def test_invalid_calendar_or_cardinality_fails_without_guessed_intervals(rules):
    with pytest.raises(RoadFeedError):
        source(rules)


def test_bounded_work_cannot_report_a_closure_after_exhaustion():
    budget = ExpansionBudget(2)
    result = temporal_state(source(end=None), now=instant('2026-09-14T00:00:00Z'), budget=budget)
    assert result.phase == 'unknown' and result.reason == 'recurrence_evaluation_limit'
    assert budget.remaining == 0
    assert temporal_state(source(), now=instant('2026-09-14T00:00:00Z'), budget=budget).phase == 'unknown'


def test_continuous_union_beyond_lookback_is_not_given_a_fabricated_start():
    rules = recurrence('00:00:00Z', '12:00:00Z', ()) + recurrence('12:00:00Z', '24:00:00Z', ())
    item = source(rules, start='2020-01-01T00:00:00Z', end=None)
    result = state(item, '2026-09-14T00:00:00Z')
    assert result.phase == 'unknown' and result.reason == 'recurrence_interval_incomplete'
