import { createContext, useContext, type ReactNode } from 'react'

import { useApi, type ApiState } from '@/hooks/use-api'
import { api } from '@/services/api'
import type { HealthResponse } from '@/types/forecast'

const HealthContext = createContext<ApiState<HealthResponse> | null>(null)

/**
 * Loads `/health` once for the whole app: drives the data-source indicator in
 * the header and the delivery-period bounds of the date pickers.
 */
export function HealthProvider({ children }: { children: ReactNode }) {
  const state = useApi(() => api.health(), [])
  return <HealthContext.Provider value={state}>{children}</HealthContext.Provider>
}

export function useHealth(): ApiState<HealthResponse> {
  const state = useContext(HealthContext)
  if (!state) throw new Error('useHealth must be used inside <HealthProvider>')
  return state
}
