import { Activity, Maximize2, Minimize2, Timer } from 'lucide-react'
import { useMemo, useState } from 'react'

import { ActualChart } from '@/components/actual-chart'
import { AsyncSection } from '@/components/data-state'
import { DeliveryDatePicker } from '@/components/delivery-date-picker'
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
import { formatDateLabel, formatMw } from '@/lib/format'
import { api } from '@/services/api'

const FALLBACK_DATE = '2026-01-15'

interface ActualStats {
  mean: number | null
  min: number | null
  max: number | null
  count: number
}

function computeStats(intervals: { actual_mw: number | null; has_actual: boolean }[]): ActualStats {
  const values = intervals
    .filter((interval) => interval.has_actual && interval.actual_mw !== null)
    .map((interval) => interval.actual_mw as number)

  if (values.length === 0) return { mean: null, min: null, max: null, count: 0 }

  const sum = values.reduce((total, value) => total + value, 0)
  return {
    mean: sum / values.length,
    min: Math.min(...values),
    max: Math.max(...values),
    count: values.length,
  }
}

export function ActualDataPage() {
  const { data: health } = useHealth()
  const [dateOverride, setDateOverride] = useState<string | null>(null)
  const date = dateOverride ?? health?.delivery_from ?? FALLBACK_DATE

  const series = useApi(() => api.forecasts(date), [date])
  const intervals = useMemo(() => series.data?.intervals ?? [], [series.data])
  const stats = useMemo(() => computeStats(intervals), [intervals])
  const totalIntervals = series.data?.interval_count ?? 48

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-normal">
            Source: Elexon BMRS FUELHH
          </Badge>
          <Badge variant="outline" className="font-normal">
            Half-hourly average MW (UTC)
          </Badge>
        </div>
        <DeliveryDatePicker
          value={date}
          onChange={setDateOverride}
          min={health?.delivery_from}
          max={health?.delivery_to}
        />
      </div>

      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Mean actual"
          value={formatMw(stats.mean)}
          icon={Activity}
          loading={series.loading}
          description={`Delivery day average · ${formatDateLabel(date)}`}
        />
        <MetricCard
          title="Minimum"
          value={formatMw(stats.min)}
          icon={Minimize2}
          loading={series.loading}
          description="Lowest half-hour outturn"
        />
        <MetricCard
          title="Maximum"
          value={formatMw(stats.max)}
          icon={Maximize2}
          loading={series.loading}
          description="Highest half-hour outturn"
        />
        <MetricCard
          title="Intervals with data"
          value={`${stats.count} / ${totalIntervals}`}
          icon={Timer}
          loading={series.loading}
          description="Half-hours with a metered value"
        />
      </div>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Actual wind generation</CardTitle>
          <CardDescription>
            {formatDateLabel(date)} · metered outturn, half-hourly averages in MW
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AsyncSection
            state={series}
            render={(data) => <ActualChart intervals={data.intervals} />}
          />
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle>Generation detail</CardTitle>
          <CardDescription>Recorded actual generation per delivery interval</CardDescription>
        </CardHeader>
        <CardContent>
          <AsyncSection
            state={series}
            render={(data) => <IntervalTable intervals={data.intervals} mode="actual" />}
          />
        </CardContent>
      </Card>

      {/* Coverage note */}
      <AsyncSection
        state={series}
        render={(data) => {
          const missing = data.intervals.filter((interval) => !interval.has_actual).length
          return (
            <p className="text-xs text-muted-foreground">
              {missing === 0
                ? `All ${data.interval_count} delivery intervals have metered actual generation for ${formatDateLabel(date)}.`
                : `${missing} of ${data.interval_count} delivery intervals have no metered actual generation for ${formatDateLabel(date)}; they are excluded from error metrics.`}
            </p>
          )
        }}
      />
    </div>
  )
}
