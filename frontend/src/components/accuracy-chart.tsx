import { Bar, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { DailyMetric } from '@/types/forecast'

const chartConfig = {
  mae: { label: 'MAE', color: 'var(--chart-1)' },
  bias: { label: 'Bias', color: 'var(--chart-2)' },
} satisfies ChartConfig

/** Daily MAE (bars) and signed bias (line) across the delivery period. */
export function AccuracyChart({ daily }: { daily: DailyMetric[] }) {
  const data = daily.map((entry) => ({
    day: entry.delivery_date.slice(8),
    mae: entry.metrics.mae_mw,
    bias: entry.metrics.bias_mw,
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[260px] w-full">
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="day"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          fontSize={12}
          interval={2}
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
              labelFormatter={(_, payload) => {
                const row = payload?.[0]?.payload as { day?: string } | undefined
                return row?.day ? `January ${row.day}` : ''
              }}
              formatter={(value) => [`${Number(value).toLocaleString('en-GB')} MW`]}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="mae" fill="var(--color-mae)" radius={[3, 3, 0, 0]} maxBarSize={18} />
        <Line
          dataKey="bias"
          type="monotone"
          stroke="var(--color-bias)"
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ChartContainer>
  )
}
