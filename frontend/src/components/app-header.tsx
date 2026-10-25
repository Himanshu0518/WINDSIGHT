import { CircleDot } from 'lucide-react'
import { useLocation } from 'react-router-dom'

import { ThemeToggle } from '@/components/theme-toggle'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { useHealth } from '@/health-context'
import { formatDateTime } from '@/lib/format'

const PAGE_META: Record<string, { title: string; description: string }> = {
  '/': {
    title: 'Dashboard',
    description: 'Forecast vs. actual wind generation for the selected delivery day',
  },
  '/predictions': {
    title: 'Prediction Data',
    description: 'Every published forecast version and how it was revised',
  },
  '/actuals': {
    title: 'Actual Data',
    description: 'Metered half-hourly wind generation outturn (FUELHH)',
  },
}

export function AppHeader() {
  const { pathname } = useLocation()
  const { data: health } = useHealth()
  const meta = PAGE_META[pathname] ?? PAGE_META['/']

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4 md:px-6">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-5" />
      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="truncate text-base font-semibold leading-tight">{meta.title}</h1>
        <p className="hidden truncate text-xs text-muted-foreground md:block">{meta.description}</p>
      </div>

      <div className="flex items-center gap-2">
        {health?.data_loaded ? (
          <Badge variant="outline" className="gap-1.5 font-normal">
            <CircleDot className="size-3 text-emerald-500" />
            Data loaded {formatDateTime(health.generated_at)} UTC
          </Badge>
        ) : (
          <Badge variant="destructive" className="font-normal">
            Dataset unavailable
          </Badge>
        )}
        <ThemeToggle />
      </div>
    </header>
  )
}
