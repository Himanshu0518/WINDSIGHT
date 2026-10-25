/**
 * Types mirroring the FastAPI response schemas (see backend/app/schemas/forecast.py).
 * Timestamps are ISO-8601 UTC strings, dates are YYYY-MM-DD, values in MW.
 * `null` always means *missing data* - never zero.
 */

export interface IntervalPoint {
  start_time: string
  forecast_mw: number | null
  actual_mw: number | null
  error_mw: number | null
  forecast_publish_time: string | null
  has_forecast: boolean
  has_actual: boolean
}

export interface Metrics {
  total_intervals: number
  matched_intervals: number
  missing_forecast_intervals: number
  missing_actual_intervals: number
  mape_excluded_intervals: number
  coverage_percent: number | null
  mae_mw: number | null
  rmse_mw: number | null
  bias_mw: number | null
  mape_percent: number | null
}

export interface ForecastsResponse {
  delivery_date: string
  timezone: string
  decision_cutoff: string
  decision_cutoff_description: string
  resolution_minutes: number
  interval_count: number
  intervals: IntervalPoint[]
}

export interface OverviewResponse {
  delivery_date: string
  timezone: string
  decision_cutoff: string
  decision_cutoff_description: string
  metrics: Metrics
  first_forecast_publish_time: string | null
  latest_eligible_publish_time: string | null
  has_data: boolean
}

export interface DailyMetric {
  delivery_date: string
  metrics: Metrics
}

export interface AccuracyResponse {
  date_from: string
  date_to: string
  timezone: string
  summary: Metrics
  daily: DailyMetric[]
}

export interface EvolutionPoint {
  start_time: string
  forecast_mw: number | null
}

export interface EvolutionPublication {
  publish_time: string
  eligible_before_cutoff: boolean
  points: EvolutionPoint[]
}

export interface ForecastEvolutionResponse {
  delivery_date: string
  timezone: string
  decision_cutoff: string
  decision_cutoff_description: string
  publication_count: number
  publications: EvolutionPublication[]
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  version: string
  data_loaded: boolean
  detail: string | null
  generated_at: string | null
  delivery_from: string | null
  delivery_to: string | null
  expected_intervals: number | null
  loaded_intervals: number | null
  coverage_percent: number | null
  decision_cutoff: string | null
}
