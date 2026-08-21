import { apiGet } from './api'
import type { ExecutiveDailyPoint, ExecutiveSummary } from '@/types/api'

export function getExecutiveSummary() {
  return apiGet<ExecutiveSummary>('/executive/summary')
}

export function getExecutiveTimeline() {
  return apiGet<ExecutiveDailyPoint[]>('/executive/timeline')
}
