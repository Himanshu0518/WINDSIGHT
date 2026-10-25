import type {
  AccuracyResponse,
  ForecastEvolutionResponse,
  ForecastsResponse,
  HealthResponse,
  OverviewResponse,
} from '@/types/forecast'

const DEFAULT_BASE_URL = 'http://localhost:8000'

/** Backend origin, overridable per environment (see frontend/.env.example). */
export const API_BASE_URL = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? DEFAULT_BASE_URL
).replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(
  path: string,
  params: Record<string, string | undefined> = {},
): Promise<T> {
  const url = new URL(path, `${API_BASE_URL}/`)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') url.searchParams.set(key, value)
  }

  let response: Response
  try {
    response = await fetch(url)
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the WindSight API at ${API_BASE_URL}. Is the backend running?`,
    )
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // keep the generic message when the body is not JSON
    }
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  overview: (date: string) => request<OverviewResponse>('/api/overview', { date }),
  forecasts: (date: string) => request<ForecastsResponse>('/api/forecasts', { date }),
  accuracy: (range: { from?: string; to?: string } = {}) =>
    request<AccuracyResponse>('/api/accuracy', range),
  evolution: (date: string) =>
    request<ForecastEvolutionResponse>('/api/forecast-evolution', { date }),
}
