import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EMPTY } from '@/lib/format'

interface MetricCardProps {
  title: string
  value: string | null | undefined
  unit?: string
  description?: ReactNode
  icon?: LucideIcon
  loading?: boolean
}

/** KPI card used across the dashboard: label, headline value and context line. */
export function MetricCard({ title, value, unit, description, icon: Icon, loading }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden />}
      </CardHeader>
      <CardContent className="pt-0">
        {loading ? (
          <Skeleton className="h-8 w-28" />
        ) : (
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-semibold tabular-nums tracking-tight">
              {value ?? EMPTY}
            </span>
            {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
          </div>
        )}
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  )
}
