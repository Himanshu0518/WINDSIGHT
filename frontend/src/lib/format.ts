/** Formatting helpers. All timestamps from the API are ISO-8601 UTC. */

const numberFormatter = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
const numberFormatter2 = new Intl.NumberFormat('en-GB', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const timeFormatter = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'UTC',
})
const dateTimeFormatter = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'UTC',
})

export const EMPTY = '—'

export function formatMw(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined) return EMPTY
  const formatter = decimals > 0 ? numberFormatter2 : numberFormatter
  return `${formatter.format(value)} MW`
}

export function formatSignedMw(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${numberFormatter.format(Math.abs(value))} MW`
}

/** '+1,110' / '−1,110' without a unit, for signed KPI values. */
export function formatSignedNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${numberFormatter.format(Math.abs(value))}`
}

export function formatNumber(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined) return EMPTY
  return `${numberFormatter2.format(value)}${suffix}`
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  return `${numberFormatter2.format(value)}%`
}

/** '10:30' from an ISO timestamp (UTC). */
export function timeOfDay(iso: string): string {
  return timeFormatter.format(new Date(iso))
}

/** '14 Jan, 09:30' from an ISO timestamp (UTC). */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return EMPTY
  return `${dateTimeFormatter.format(new Date(iso))}`
}

/** '14 Jan 2026' from a YYYY-MM-DD string. */
export function formatDateLabel(isoDate: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${isoDate}T00:00:00Z`))
}
