import { CartesianGrid, Line, ComposedChart, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { timeOfDay } from '@/lib/format'
import type { IntervalPoint } from '@/types/forecast'

const chartConfig = {
  forecast: { label: 'Forecast', color: 'var(--chart-1)' },
  actual: { label: 'Actual', color: 'var(--chart-2)' },
} satisfies ChartConfig

export function ForecastChart({ intervals }: { intervals: IntervalPoint[] }) {
  const data = intervals.map((interval) => ({
    time: timeOfDay(interval.start_time),
    forecast: interval.forecast_mw,
    actual: interval.actual_mw,
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[320px] w-full">
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="time"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={28}
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
              indicator="dot"
              labelFormatter={(label) => `Delivery ${label} UTC`}
              formatter={(value) => [`${Number(value).toLocaleString('en-GB')} MW`]}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        <Line
          dataKey="forecast"
          type="monotone"
          stroke="var(--color-forecast)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
        <Line
          dataKey="actual"
          type="monotone"
          stroke="var(--color-actual)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </ComposedChart>
    </ChartContainer>
  )
}
