import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { EMPTY, formatDateTime, formatMw, formatSignedMw, timeOfDay } from '@/lib/format'
import type { IntervalPoint } from '@/types/forecast'

export type IntervalTableMode = 'full' | 'forecast' | 'actual'

interface IntervalTableProps {
  intervals: IntervalPoint[]
  /** Which columns to show: combined (dashboard), forecast-only or actual-only. */
  mode?: IntervalTableMode
}

function statusOf(interval: IntervalPoint): { label: string; variant: 'outline' | 'secondary' | 'destructive' } {
  if (!interval.has_forecast) return { label: 'No forecast', variant: 'destructive' }
  if (!interval.has_actual) return { label: 'No actual', variant: 'secondary' }
  return { label: 'Matched', variant: 'outline' }
}

/** Half-hourly delivery intervals with explicit missing-data indicators. */
export function IntervalTable({ intervals, mode = 'full' }: IntervalTableProps) {
  return (
    <div className="max-h-[420px] overflow-auto rounded-md border">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-background">
          <TableRow>
            <TableHead>Time (UTC)</TableHead>
            {(mode === 'full' || mode === 'forecast') && <TableHead className="text-right">Forecast</TableHead>}
            {(mode === 'full' || mode === 'actual') && <TableHead className="text-right">Actual</TableHead>}
            {mode === 'full' && <TableHead className="text-right">Error</TableHead>}
            {mode === 'forecast' && <TableHead>Published at</TableHead>}
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {intervals.map((interval) => {
            const status = statusOf(interval)
            return (
              <TableRow key={interval.start_time}>
                <TableCell className="tabular-nums">{timeOfDay(interval.start_time)}</TableCell>
                {(mode === 'full' || mode === 'forecast') && (
                  <TableCell className="text-right tabular-nums">
                    {interval.has_forecast ? formatMw(interval.forecast_mw) : EMPTY}
                  </TableCell>
                )}
                {(mode === 'full' || mode === 'actual') && (
                  <TableCell className="text-right tabular-nums">
                    {interval.has_actual ? formatMw(interval.actual_mw) : EMPTY}
                  </TableCell>
                )}
                {mode === 'full' && (
                  <TableCell className="text-right tabular-nums">
                    {interval.error_mw === null ? EMPTY : formatSignedMw(interval.error_mw)}
                  </TableCell>
                )}
                {mode === 'forecast' && (
                  <TableCell className="tabular-nums text-muted-foreground">
                    {formatDateTime(interval.forecast_publish_time)}
                  </TableCell>
                )}
                <TableCell>
                  <Badge variant={status.variant} className="font-normal">
                    {status.label}
                  </Badge>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
