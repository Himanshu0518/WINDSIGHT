import { Activity, Gauge, Percent, Scale } from 'lucide-react'
import { useState } from 'react'

import { AccuracyChart } from '@/components/accuracy-chart'
import { AsyncSection } from '@/components/data-state'
import { DeliveryDatePicker } from '@/components/delivery-date-picker'
import { ForecastChart } from '@/components/forecast-chart'
import { IntervalTable } from '@/components/interval-table'
import { MetricCard } from '@/components/metric-card'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useHealth } from '@/health-context'
import { useApi } from '@/hooks/use-api'
import {
  formatDateLabel,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatSignedNumber,
} from '@/lib/format'
import { api } from '@/services/api'

const FALLBACK_DATE = '2026-01-15'

export function DashboardPage() {
  const { data: health } = useHealth()
  const [dateOverride, setDateOverride] = useState<string | null>(null)
  const date = dateOverride ?? health?.delivery_from ?? FALLBACK_DATE

  const overview = useApi(() => api.overview(date), [date])
  const series = useApi(() => api.forecasts(date), [date])
  const accuracy = useApi(() => api.accuracy(), [])

  const metrics = overview.data?.metrics
  const missingIntervals =
    (metrics?.missing_forecast_intervals ?? 0) + (metrics?.missing_actual_intervals ?? 0)
  const totalIntervals = metrics?.total_intervals ?? 48

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-normal">
            Cutoff: {overview.data?.decision_cutoff_description ?? '10:00 Europe/London, day before delivery'}
          </Badge>
          <Badge variant="outline" className="font-normal">
            Selected forecast:{' '}
            {formatDateTime(overview.data?.latest_eligible_publish_time)} UTC
          </Badge>
        </div>
        <DeliveryDatePicker
          value={date}
          onChange={setDateOverride}
          min={health?.delivery_from}
          max={health?.delivery_to}
        />
      </div>

      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Forecast MAE"
          value={formatNumber(metrics?.mae_mw)}
          unit="MW"
          icon={Activity}
          loading={overview.loading}
          description={`Mean absolute error · ${metrics?.matched_intervals ?? 0}/${totalIntervals} intervals`}
        />
        <MetricCard
          title="Forecast bias"
          value={formatSignedNumber(metrics?.bias_mw)}
          unit="MW"
          icon={Scale}
          loading={overview.loading}
          description="Signed error · positive means over-forecast"
        />
        <MetricCard
          title="Forecast RMSE"
          value={formatNumber(metrics?.rmse_mw)}
          unit="MW"
          icon={Gauge}
          loading={overview.loading}
          description="Root mean squared error · penalises large misses"
        />
        <MetricCard
          title="Forecast coverage"
          value={formatNumber(metrics?.coverage_percent)}
          unit="%"
          icon={Percent}
          loading={overview.loading}
          description={`Matched data coverage · ${totalIntervals} half-hours`}
        />
      </div>

      {missingIntervals > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
          <Badge variant="outline" className="border-amber-500/50 text-amber-700 dark:text-amber-400">
            Partial data
          </Badge>
          <span className="text-muted-foreground">
            {metrics?.missing_forecast_intervals ?? 0} intervals without an eligible forecast,{' '}
            {metrics?.missing_actual_intervals ?? 0} without actual generation on{' '}
            {formatDateLabel(date)}.
          </span>
        </div>
      )}

      {/* Main chart */}
      <Card>
        <CardHeader>
          <CardTitle>Wind generation: forecast vs. actual</CardTitle>
          <CardDescription>
            {formatDateLabel(date)} · half-hourly delivery intervals, values in MW (UTC)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AsyncSection state={series} render={(data) => <ForecastChart intervals={data.intervals} />} />
        </CardContent>
      </Card>

      {/* Daily trend + detail table */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Daily accuracy trend</CardTitle>
            <CardDescription>
              MAE (bars) and signed bias (line) per delivery day, January 2026
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AsyncSection
              state={accuracy}
              render={(data) =>
                data.daily.length > 0 ? (
                  <AccuracyChart daily={data.daily} />
                ) : (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    No daily metrics in this range.
                  </p>
                )
              }
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Forecast vs. actual detail</CardTitle>
            <CardDescription>All 48 delivery intervals for {formatDateLabel(date)}</CardDescription>
          </CardHeader>
          <CardContent>
            <AsyncSection
              state={series}
              render={(data) => <IntervalTable intervals={data.intervals} mode="full" />}
            />
          </CardContent>
        </Card>
      </div>

      {/* Month summary */}
      <AsyncSection
        state={accuracy}
        render={(data) => (
          <p className="text-xs text-muted-foreground">
            {formatDateLabel(data.date_from)} – {formatDateLabel(data.date_to)} summary:{' '}
            {data.summary.total_intervals} intervals · MAE {formatNumber(data.summary.mae_mw)} MW ·
            RMSE {formatNumber(data.summary.rmse_mw)} MW · bias{' '}
            {formatSignedNumber(data.summary.bias_mw)} MW · MAPE{' '}
            {formatPercent(data.summary.mape_percent)} · coverage{' '}
            {formatPercent(data.summary.coverage_percent)}
          </p>
        )}
      />
    </div>
  )
}
