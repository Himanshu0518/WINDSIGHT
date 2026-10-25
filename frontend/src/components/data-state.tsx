import { AlertTriangle, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { ApiState } from '@/hooks/use-api'

/** Loading placeholder matching the shape of a card or chart block. */
export function LoadingState({ blocks = 3 }: { blocks?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: blocks }).map((_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}

/** Error banner with a retry action; the API message is shown verbatim. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
      <div className="flex-1 space-y-1">
        <p className="font-medium">Could not load data</p>
        <p className="text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw />
          Retry
        </Button>
      )}
    </div>
  )
}

/** Empty-state note, e.g. when no eligible forecast exists for a day. */
export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-lg border border-dashed p-6 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{message}</p>
    </div>
  )
}

/**
 * Renders loading / error states around a fetch result so every section of a
 * page handles them consistently.
 */
export function AsyncSection<T>({
  state,
  render,
}: {
  state: ApiState<T>
  render: (data: T) => ReactNode
}) {
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />
  if (state.loading || state.data === null) return <LoadingState />
  return <>{render(state.data)}</>
}
