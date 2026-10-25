"""Unit tests for forecast selection and interval matching.

These cover the edge cases required by the assignment: eligible-vs-late
publications, missing forecasts, duplicate records, matching by timestamp and
correct timezone handling around daylight-saving changes.
"""

from __future__ import annotations

from datetime import date


from app.services.forecast_selection import (
    CutoffRule,
    ForecastIndex,
    ForecastRecord,
    build_intervals,
    filter_intervals,
)
from app.timeutils import expected_interval_count, parse_utc as ts


def record(publish: str, start: str, mw: float | None) -> ForecastRecord:
    return ForecastRecord(
        publish_time=ts(publish), start_time=ts(start), generation_mw=mw
    )


# --- cutoff rule ----------------------------------------------------------
class TestCutoffRule:
    def test_january_cutoff_is_utc_day_before_at_10(self):
        rule = CutoffRule()  # 10:00 Europe/London, day before delivery
        cutoff = rule.for_delivery(ts("2026-01-15T12:00:00Z"))
        assert cutoff == ts("2026-01-14T10:00:00Z")

    def test_cutoff_is_independent_of_delivery_time_of_day(self):
        rule = CutoffRule()
        assert rule.for_delivery(ts("2026-01-15T00:30:00Z")) == ts("2026-01-14T10:00:00Z")
        assert rule.for_delivery(ts("2026-01-15T23:30:00Z")) == ts("2026-01-14T10:00:00Z")

    def test_cutoff_converts_bst_to_utc(self):
        # July is BST (UTC+1), so 10:00 local is 09:00 UTC.
        rule = CutoffRule()
        cutoff = rule.for_delivery(ts("2026-07-15T12:00:00Z"))
        assert cutoff == ts("2026-07-14T09:00:00Z")

    def test_cutoff_across_spring_forward_transition(self):
        rule = CutoffRule()
        # 29 March 2026 is the BST start day, so the decision day (28 Mar) is still GMT.
        assert rule.for_delivery(ts("2026-03-29T12:00:00Z")) == ts("2026-03-28T10:00:00Z")
        # 30 March delivery -> decision day 29 March is already BST.
        assert rule.for_delivery(ts("2026-03-30T12:00:00Z")) == ts("2026-03-29T09:00:00Z")

    def test_cutoff_across_autumn_back_transition(self):
        rule = CutoffRule()
        # 25 October 2026 is the GMT start day; the decision day (24 Oct) is still BST.
        assert rule.for_delivery(ts("2026-10-25T12:00:00Z")) == ts("2026-10-24T09:00:00Z")
        assert rule.for_delivery(ts("2026-10-26T12:00:00Z")) == ts("2026-10-25T10:00:00Z")

    def test_custom_cutoff_time_and_lead_days(self):
        rule = CutoffRule(hour=16, minute=30, lead_days=2)
        cutoff = rule.for_delivery(ts("2026-01-15T12:00:00Z"))
        assert cutoff == ts("2026-01-13T16:30:00Z")

    def test_description_mentions_time_and_timezone(self):
        assert "10:00" in CutoffRule().description
        assert "Europe/London" in CutoffRule().description


# --- selection ------------------------------------------------------------
class TestForecastSelection:
    TARGET = "2026-01-15T12:00:00Z"
    CUTOFF = ts("2026-01-14T10:00:00Z")

    def test_selects_latest_eligible_publication(self):
        index = ForecastIndex(
            [
                record("2026-01-14T07:30:00Z", self.TARGET, 4000),
                record("2026-01-14T09:30:00Z", self.TARGET, 4200),
            ]
        )
        chosen = index.select(ts(self.TARGET), self.CUTOFF)
        assert chosen is not None
        assert chosen.generation_mw == 4200
        assert chosen.publish_time == ts("2026-01-14T09:30:00Z")

    def test_excludes_publication_after_cutoff(self):
        index = ForecastIndex(
            [
                record("2026-01-14T11:30:00Z", self.TARGET, 5000),
                record("2026-01-14T15:30:00Z", self.TARGET, 5100),
            ]
        )
        assert index.select(ts(self.TARGET), self.CUTOFF) is None

    def test_falls_back_to_earlier_publication_when_later_is_late(self):
        index = ForecastIndex(
            [
                record("2026-01-14T09:30:00Z", self.TARGET, 4100),
                record("2026-01-14T11:30:00Z", self.TARGET, 5500),
            ]
        )
        chosen = index.select(ts(self.TARGET), self.CUTOFF)
        assert chosen is not None and chosen.generation_mw == 4100

    def test_no_forecast_for_target_returns_none(self):
        index = ForecastIndex([record("2026-01-14T09:30:00Z", "2026-01-16T12:00:00Z", 3000)])
        assert index.select(ts(self.TARGET), self.CUTOFF) is None

    def test_publication_exactly_at_cutoff_is_eligible(self):
        index = ForecastIndex([record("2026-01-14T10:00:00Z", self.TARGET, 4400)])
        chosen = index.select(ts(self.TARGET), self.CUTOFF)
        assert chosen is not None and chosen.generation_mw == 4400

    def test_selection_is_independent_per_target_hour(self):
        index = ForecastIndex(
            [
                record("2026-01-14T09:30:00Z", "2026-01-15T11:00:00Z", 3000),
                record("2026-01-14T07:30:00Z", "2026-01-15T12:00:00Z", 3100),
            ]
        )
        assert index.select(ts("2026-01-15T11:00:00Z"), self.CUTOFF).generation_mw == 3000
        assert index.select(ts("2026-01-15T12:00:00Z"), self.CUTOFF).generation_mw == 3100

    def test_null_generation_treated_as_missing(self):
        index = ForecastIndex([record("2026-01-14T09:30:00Z", self.TARGET, None)])
        assert index.select(ts(self.TARGET), self.CUTOFF) is None

    def test_duplicate_records_are_dropped_and_counted(self):
        records = [
            record("2026-01-14T09:30:00Z", self.TARGET, 4200),
            record("2026-01-14T09:30:00Z", self.TARGET, 4200),  # exact duplicate
            record("2026-01-14T07:30:00Z", self.TARGET, 4000),
        ]
        index = ForecastIndex(records)
        assert index.duplicates_dropped == 1
        assert len(index.records) == 2
        chosen = index.select(ts(self.TARGET), self.CUTOFF)
        assert chosen is not None and chosen.generation_mw == 4200


# --- interval matching ----------------------------------------------------
class TestBuildIntervals:
    def test_covers_every_half_hour_of_the_range(self):
        index = ForecastIndex([])
        intervals = build_intervals(
            index, {}, date(2026, 1, 1), date(2026, 1, 31), CutoffRule()
        )
        assert len(intervals) == expected_interval_count(date(2026, 1, 1), date(2026, 1, 31))
        assert len(intervals) == 1488
        assert intervals[0].start_time == ts("2026-01-01T00:00:00Z")
        assert intervals[-1].start_time == ts("2026-01-31T23:30:00Z")

    def test_hourly_forecast_is_broadcast_to_both_half_hours(self):
        index = ForecastIndex(
            [record("2026-01-14T09:30:00Z", "2026-01-15T12:00:00Z", 5300)]
        )
        actuals = {
            ts("2026-01-15T12:00:00Z"): 5000.0,
            ts("2026-01-15T12:30:00Z"): 5200.0,
        }
        intervals = build_intervals(
            index, actuals, date(2026, 1, 15), date(2026, 1, 15), CutoffRule()
        )
        by_start = {i.start_time: i for i in intervals}
        noon = by_start[ts("2026-01-15T12:00:00Z")]
        half = by_start[ts("2026-01-15T12:30:00Z")]
        assert noon.forecast_mw == 5300 == half.forecast_mw
        assert noon.actual_mw == 5000 and half.actual_mw == 5200
        assert noon.error_mw == 300 and half.error_mw == 100

    def test_missing_actual_is_not_treated_as_zero(self):
        index = ForecastIndex(
            [record("2026-01-14T09:30:00Z", "2026-01-15T00:00:00Z", 5000)]
        )
        intervals = build_intervals(
            index, {}, date(2026, 1, 15), date(2026, 1, 15), CutoffRule()
        )
        first = intervals[0]
        assert first.forecast_mw == 5000
        assert first.actual_mw is None
        assert first.error_mw is None
        assert not first.has_actual

    def test_missing_forecast_is_recorded_as_missing(self):
        index = ForecastIndex([])
        intervals = build_intervals(
            index, {ts("2026-01-15T00:00:00Z"): 4000.0},
            date(2026, 1, 15), date(2026, 1, 15), CutoffRule(),
        )
        first = intervals[0]
        assert first.forecast_mw is None
        assert first.forecast_publish_time is None
        assert first.error_mw is None

    def test_forecast_published_after_cutoff_is_never_used(self):
        index = ForecastIndex(
            [record("2026-01-15T09:30:00Z", "2026-01-15T12:00:00Z", 9999)]
        )
        intervals = build_intervals(
            index, {}, date(2026, 1, 15), date(2026, 1, 15), CutoffRule()
        )
        by_start = {i.start_time: i for i in intervals}
        assert by_start[ts("2026-01-15T12:00:00Z")].forecast_mw is None

    def test_error_sign_conventions(self):
        index = ForecastIndex(
            [
                record("2026-01-14T09:30:00Z", "2026-01-15T01:00:00Z", 1000),
                record("2026-01-14T09:30:00Z", "2026-01-15T02:00:00Z", 500),
            ]
        )
        actuals = {
            ts("2026-01-15T01:00:00Z"): 900.0,  # over-forecast
            ts("2026-01-15T01:30:00Z"): 900.0,
            ts("2026-01-15T02:00:00Z"): 600.0,  # under-forecast
            ts("2026-01-15T02:30:00Z"): 600.0,
        }
        intervals = build_intervals(
            index, actuals, date(2026, 1, 15), date(2026, 1, 15), CutoffRule()
        )
        by_start = {i.start_time: i for i in intervals}
        assert by_start[ts("2026-01-15T01:00:00Z")].error_mw == 100  # positive = over
        assert by_start[ts("2026-01-15T02:00:00Z")].error_mw == -100  # negative = under


# --- filtering ------------------------------------------------------------
class TestFilterIntervals:
    def test_filters_by_local_delivery_date(self):
        index = ForecastIndex([])
        intervals = build_intervals(
            index, {}, date(2026, 1, 1), date(2026, 1, 31), CutoffRule()
        )
        selected = filter_intervals(
            intervals, date(2026, 1, 15), date(2026, 1, 15), "Europe/London"
        )
        assert len(selected) == 48
        assert all(i.start_time.day == 15 for i in selected)

    def test_no_bounds_returns_everything(self):
        index = ForecastIndex([])
        intervals = build_intervals(
            index, {}, date(2026, 1, 1), date(2026, 1, 2), CutoffRule()
        )
        assert filter_intervals(intervals) == intervals
