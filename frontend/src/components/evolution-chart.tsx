import { useMemo, useState } from 'react'
import { CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatDateTime, timeOfDay } from '@/lib/format'
import type { EvolutionPublication } from '@/types/forecast'

const chartConfig = {
  eligible: { label: 'Eligible at cutoff', color: 'var(--chart-1)' },
  revised: { label: 'Published after cutoff', color: 'var(--chart-2)' },
} satisfies ChartConfig

interface EvolutionChartProps {
  publications: EvolutionPublication[]
}

/**
 * How the forecast for one target hour changed across publications.
 * Split into "eligible at cutoff" and "published after cutoff" series, with a
 * marker on the last publication the buyer could have used.
 */
export function EvolutionChart({ publications }: EvolutionChartProps) {
  const hours = useMemo(() => {
    const collected = new Set<string>()
    for (const publication of publications) {
      for (const point of publication.points) collected.add(timeOfDay(point.start_time))
    }
    return Array.from(collected).sort()
  }, [publications])

  const [hourOverride, setHourOverride] = useState<string | null>(null)

  // Derived during render: fall back to noon (or the middle hour) when the
  // chosen hour does not exist for this delivery day.
  const hour =
    hourOverride !== null && hours.includes(hourOverride)
      ? hourOverride
      : hours.includes('12:00')
        ? '12:00'
        : hours[Math.floor(hours.length / 2)]

  const data = publications.map((publication) => {
    const point = publication.points.find((item) => timeOfDay(item.start_time) === hour)
    const value = point?.forecast_mw ?? null
    return {
      publish: formatDateTime(publication.publish_time),
      eligible: publication.eligible_before_cutoff ? value : null,
      revised: publication.eligible_before_cutoff ? null : value,
    }
  })

  const lastEligible = [...publications]
    .reverse()
    .find((publication) => publication.eligible_before_cutoff)
  const cutoffX = lastEligible ? formatDateTime(lastEligible.publish_time) : null

  if (hours.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No forecast history for this date.</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-2">
        <span className="text-xs text-muted-foreground">Target hour</span>
        <Select value={hour} onValueChange={setHourOverride}>
          <SelectTrigger className="h-8 w-[112px] text-xs" aria-label="Target hour">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {hours.map((value) => (
              <SelectItem key={value} value={value}>
                {value} UTC
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <ChartContainer config={chartConfig} className="h-[300px] w-full">
        <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="publish"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={24}
            fontSize={12}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            width={54}
            fontSize={12}
            tickFormatter={(value: number) => value.toLocaleString('en-GB')}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(label) => `Published ${label} UTC`}
                formatter={(value) => [`${Number(value).toLocaleString('en-GB')} MW`]}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          {cutoffX && (
            <ReferenceLine
              x={cutoffX}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              label={{ value: 'Decision cutoff', position: 'insideTopRight', fontSize: 11 }}
            />
          )}
          <Line
            dataKey="eligible"
            type="monotone"
            stroke="var(--color-eligible)"
            strokeWidth={2}
            dot={{ r: 3 }}
            name="Eligible at cutoff"
          />
          <Line
            dataKey="revised"
            type="monotone"
            stroke="var(--color-revised)"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 3 }}
            name="Published after cutoff"
          />
        </ComposedChart>
      </ChartContainer>
    </div>
  )
}
