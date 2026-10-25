import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { timeOfDay } from '@/lib/format'
import type { IntervalPoint } from '@/types/forecast'

const chartConfig = {
  actual: { label: 'Actual generation', color: 'var(--chart-3)' },
} satisfies ChartConfig

/** Metered wind generation over the delivery day (solid fill, no gradients). */
export function ActualChart({ intervals }: { intervals: IntervalPoint[] }) {
  const data = intervals.map((interval) => ({
    time: timeOfDay(interval.start_time),
    actual: interval.actual_mw,
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[320px] w-full">
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
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
        <Area
          dataKey="actual"
          type="monotone"
          stroke="var(--color-actual)"
          strokeWidth={2}
          fill="var(--color-actual)"
          fillOpacity={0.15}
          connectNulls
        />
      </AreaChart>
    </ChartContainer>
  )
}
