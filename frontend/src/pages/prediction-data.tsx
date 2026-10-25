import { Clock, Layers, TrendingUp } from 'lucide-react'
import { useState } from 'react'

import { AsyncSection, EmptyState } from '@/components/data-state'
import { DeliveryDatePicker } from '@/components/delivery-date-picker'
import { EvolutionChart } from '@/components/evolution-chart'
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
import { formatDateLabel, formatDateTime } from '@/lib/format'
import { api } from '@/services/api'

const FALLBACK_DATE = '2026-01-15'

export function PredictionDataPage() {
  const { data: health } = useHealth()
  const [dateOverride, setDateOverride] = useState<string | null>(null)
  const date = dateOverride ?? health?.delivery_from ?? FALLBACK_DATE

  const series = useApi(() => api.forecasts(date), [date])
  const evolution = useApi(() => api.evolution(date), [date])

  const intervals = series.data?.intervals ?? []
  const forecastIntervals = intervals.filter((interval) => interval.has_forecast).length
  const totalIntervals = series.data?.interval_count ?? 48

  const publications = evolution.data?.publications ?? []
  const eligibleCount = publications.filter((item) => item.eligible_before_cutoff).length
  const latestEligible = [...publications]
    .reverse()
    .find((item) => item.eligible_before_cutoff)

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-normal">
            {evolution.data?.decision_cutoff_description ??
              '10:00 Europe/London, day before delivery'}
          </Badge>
          <Badge variant="outline" className="font-normal">
            Decision cutoff: {formatDateTime(evolution.data?.decision_cutoff)} UTC
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
          title="Eligible publications"
          value={`${eligibleCount} / ${publications.length || '—'}`}
          icon={Layers}
          loading={evolution.loading}
          description="Versions available when the purchase decision is made"
        />
        <MetricCard
          title="Post-cutoff revisions"
          value={publications.length ? String(publications.length - eligibleCount) : null}
          icon={TrendingUp}
          loading={evolution.loading}
          description="Published after the decision cutoff (not usable)"
        />
        <MetricCard
          title="Latest eligible forecast"
          value={latestEligible ? formatDateTime(latestEligible.publish_time) : null}
          icon={Clock}
          loading={evolution.loading}
          description="Most recent version the buyer could have used"
        />
        <MetricCard
          title="Forecast intervals"
          value={`${forecastIntervals} / ${totalIntervals}`}
          loading={series.loading}
          description="Half-hours with an eligible forecast"
        />
      </div>

      {/* Revisions */}
      <Card>
        <CardHeader>
          <CardTitle>Forecast revisions for {formatDateLabel(date)}</CardTitle>
          <CardDescription>
            Forecast MW for a chosen target hour across every publication, split at the decision
            cutoff
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AsyncSection
            state={evolution}
            render={(data) =>
              data.publication_count > 0 ? (
                <EvolutionChart publications={data.publications} />
              ) : (
                <EmptyState
                  title="No forecast history"
                  message="No WINDFOR publication covers this delivery date."
                />
              )
            }
          />
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle>Predicted generation</CardTitle>
          <CardDescription>
            Selected (latest eligible) forecast per interval for {formatDateLabel(date)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AsyncSection
            state={series}
            render={(data) => <IntervalTable intervals={data.intervals} mode="forecast" />}
          />
        </CardContent>
      </Card>
    </div>
  )
}
