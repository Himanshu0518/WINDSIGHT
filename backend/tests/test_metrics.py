"""Unit tests for the accuracy metrics.

Every expected value below is calculated by hand from the fixture intervals,
including the sign conventions (positive bias = forecast overestimated wind)
and the documented missing-data rules.
"""

from __future__ import annotations

import pytest

from app.services.forecast_selection import CutoffRule, ForecastIndex, build_intervals
from app.services.metrics import daily_summaries, summarise
from app.timeutils import parse_utc as ts


def interval(forecast, actual, start="2026-01-15T00:00:00Z", publish=None):
    from app.services.forecast_selection import Interval

    return Interval(
        start_time=ts(start),
        forecast_mw=forecast,
        actual_mw=actual,
        forecast_publish_time=ts(publish) if publish else None,
    )


# --- core formulas --------------------------------------------------------
class TestErrorMetrics:
    def test_mae_rmse_and_bias_by_hand(self):
        # errors: +10 and -20
        metrics = summarise([interval(100, 90), interval(80, 100)])
        assert metrics.matched_intervals == 2
        assert metrics.mae_mw == pytest.approx(15.0)          # (10 + 20) / 2
        assert metrics.rmse_mw == pytest.approx(15.811, abs=1e-3)  # sqrt((100 + 400) / 2)
        assert metrics.bias_mw == pytest.approx(-5.0)         # (+10 - 20) / 2

    def test_overestimate_gives_positive_bias(self):
        metrics = summarise([interval(1200, 1000)])
        assert metrics.bias_mw == pytest.approx(200.0)
        assert metrics.mae_mw == pytest.approx(200.0)

    def test_underestimate_gives_negative_bias(self):
        metrics = summarise([interval(800, 1000)])
        assert metrics.bias_mw == pytest.approx(-200.0)

    def test_zero_error_metrics(self):
        metrics = summarise([interval(1000, 1000), interval(2000, 2000)])
        assert metrics.mae_mw == 0.0
        assert metrics.rmse_mw == 0.0
        assert metrics.bias_mw == 0.0
        assert metrics.mape_percent == 0.0


# --- MAPE -----------------------------------------------------------------
class TestMape:
    def test_mape_excludes_zero_actuals(self):
        # Only the non-zero actual contributes: |50 - 100| / 100 = 50%
        metrics = summarise([interval(100, 0), interval(50, 100)])
        assert metrics.mape_percent == pytest.approx(50.0)
        assert metrics.mape_excluded_intervals == 1
        assert metrics.matched_intervals == 2  # still matched for MAE/RMSE/bias

    def test_mape_none_when_every_actual_is_zero(self):
        metrics = summarise([interval(100, 0)])
        assert metrics.mape_percent is None
        assert metrics.mape_excluded_intervals == 1

    def test_mape_none_without_matched_intervals(self):
        metrics = summarise([interval(None, 100)])
        assert metrics.mape_percent is None


# --- missing data ---------------------------------------------------------
class TestMissingData:
    def test_missing_actual_is_excluded_and_counted(self):
        metrics = summarise([interval(1000, None), interval(1100, 1000)])
        assert metrics.total_intervals == 2
        assert metrics.matched_intervals == 1
        assert metrics.missing_actual_intervals == 1
        assert metrics.missing_forecast_intervals == 0
        # Only the matched interval contributes; missing data never becomes zero.
        assert metrics.mae_mw == pytest.approx(100.0)

    def test_missing_forecast_is_excluded_and_counted(self):
        metrics = summarise([interval(None, 1000), interval(1200, 1000)])
        assert metrics.matched_intervals == 1
        assert metrics.missing_forecast_intervals == 1
        assert metrics.missing_actual_intervals == 0
        assert metrics.bias_mw == pytest.approx(200.0)

    def test_coverage_percent(self):
        metrics = summarise([interval(1000, 1000), interval(None, 1), interval(1, None)])
        assert metrics.coverage_percent == pytest.approx(33.33, abs=0.01)

    def test_interval_missing_both_values_counts_once_in_each_bucket(self):
        metrics = summarise([interval(None, None)])
        assert metrics.matched_intervals == 0
        assert metrics.missing_forecast_intervals == 1
        assert metrics.missing_actual_intervals == 1
        assert metrics.mae_mw is None
        assert metrics.coverage_percent == 0.0

    def test_empty_input_returns_none_metrics(self):
        metrics = summarise([])
        assert metrics.total_intervals == 0
        assert metrics.coverage_percent is None
        assert metrics.mae_mw is None
        assert metrics.rmse_mw is None
        assert metrics.bias_mw is None
        assert metrics.mape_percent is None

    def test_rounding_is_applied(self):
        metrics = summarise([interval(1000.123456, 1000.0)])
        assert metrics.mae_mw == 0.123  # rounded to 3 decimals


# --- daily vs monthly -----------------------------------------------------
class TestDailySummaries:
    @pytest.fixture()
    def two_days(self):
        return [
            interval(1010, 1000, start="2026-01-15T00:00:00Z"),
            interval(1030, 1000, start="2026-01-15T00:30:00Z"),
            interval(1040, 1000, start="2026-01-16T00:00:00Z"),
        ]

    def test_groups_by_local_delivery_date(self, two_days):
        daily = daily_summaries(two_days, "Europe/London")
        assert [day for day, _ in daily] == [ts("2026-01-15").date(), ts("2026-01-16").date()]
        assert daily[0][1].matched_intervals == 2
        assert daily[1][1].matched_intervals == 1

    def test_monthly_mae_is_the_count_weighted_mean_of_daily_mae(self, two_days):
        daily = daily_summaries(two_days, "Europe/London")
        total = summarise(two_days)
        weighted = sum(m.mae_mw * m.matched_intervals for _, m in daily) / sum(
            m.matched_intervals for _, m in daily
        )
        assert total.mae_mw == pytest.approx(weighted, abs=0.01)
        assert total.mae_mw == pytest.approx(26.667, abs=0.01)  # (10 + 30 + 40) / 3

    def test_monthly_counts_match_daily_counts(self, two_days):
        daily = daily_summaries(two_days, "Europe/London")
        total = summarise(two_days)
        assert sum(m.matched_intervals for _, m in daily) == total.matched_intervals
        assert sum(m.total_intervals for _, m in daily) == total.total_intervals
        assert sum(m.missing_forecast_intervals for _, m in daily) == total.missing_forecast_intervals


# --- integration with selection -------------------------------------------
class TestMetricsOnBuiltIntervals:
    def test_metrics_over_a_built_day(self):
        from app.services.forecast_selection import ForecastRecord

        index = ForecastIndex(
            [ForecastRecord(ts("2026-01-14T09:30:00Z"), ts("2026-01-15T00:00:00Z"), 1000.0)]
        )
        actuals = {ts("2026-01-15T00:00:00Z"): 900.0, ts("2026-01-15T00:30:00Z"): 950.0}
        intervals = build_intervals(
            index, actuals, ts("2026-01-15").date(), ts("2026-01-15").date(), CutoffRule()
        )
        metrics = summarise(intervals)
        # Forecast covers 00:00 and 00:30 (broadcast); actuals only for those two.
        assert metrics.total_intervals == 48
        assert metrics.matched_intervals == 2
        assert metrics.missing_actual_intervals == 46
        assert metrics.mae_mw == pytest.approx(75.0)  # (100 + 50) / 2
        assert metrics.bias_mw == pytest.approx(75.0)  # (100 + 50) / 2
