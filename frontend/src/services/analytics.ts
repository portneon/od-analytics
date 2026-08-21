import { apiGet, apiGetWithMeta } from './api'
import type {
  Anomaly,
  ApplicationRow,
  BounceReason,
  DailyPoint,
  DayOfWeekPoint,
  DomainProfile,
  EmailEventRow,
  EntityMetric,
  HourlyPoint,
  Insight,
  Overview,
  PageMeta,
  RecipientProfile,
} from '@/types/api'

export function getOverview(datasetId: string) {
  return apiGet<Overview>(`/datasets/${datasetId}/analytics/overview`)
}

export function getDailyTimeline(datasetId: string) {
  return apiGet<DailyPoint[]>(`/datasets/${datasetId}/analytics/timeline`, { granularity: 'daily' })
}

export function getHourlyTimeline(datasetId: string) {
  return apiGet<HourlyPoint[]>(`/datasets/${datasetId}/analytics/timeline`, { granularity: 'hourly' })
}

export function getDayOfWeekTimeline(datasetId: string) {
  return apiGet<DayOfWeekPoint[]>(`/datasets/${datasetId}/analytics/timeline`, { granularity: 'day_of_week' })
}

interface ListParams {
  page?: number
  page_size?: number
  sort_by?: string
}

export async function listEntities(
  datasetId: string,
  kind: 'domains' | 'recipients' | 'subjects' | 'senders',
  params: ListParams = {},
): Promise<{ items: EntityMetric[]; meta: PageMeta }> {
  const { data, meta } = await apiGetWithMeta<EntityMetric[]>(`/datasets/${datasetId}/analytics/${kind}`, params as Record<string, unknown>)
  return { items: data, meta: meta as unknown as PageMeta }
}

export function getBounceReasons(datasetId: string) {
  return apiGet<BounceReason[]>(`/datasets/${datasetId}/analytics/bounces`)
}

export function getInfrastructure(datasetId: string, componentType?: string) {
  return apiGet<
    { component_type: string; component_value: string; total_emails: number; delivery_rate: number; bounce_rate: number; failure_rate: number; unique_recipients: number }[]
  >(`/datasets/${datasetId}/analytics/infrastructure`, componentType ? { component_type: componentType } : undefined)
}

export function getApplicationMetrics(datasetId: string) {
  return apiGet<ApplicationRow[]>(`/datasets/${datasetId}/analytics/applications`)
}

export function getAnomalies(datasetId: string) {
  return apiGet<Anomaly[]>(`/datasets/${datasetId}/anomalies`)
}

export function getInsights(datasetId: string) {
  return apiGet<Insight[]>(`/datasets/${datasetId}/insights`)
}

export function getRootCause(datasetId: string, metric: 'bounce_rate' | 'failure_rate', onDate?: string) {
  return apiGet(`/datasets/${datasetId}/root-cause`, { metric, on_date: onDate })
}

export function getRecipientProfile(datasetId: string, recipientId: string) {
  return apiGet<RecipientProfile>(`/datasets/${datasetId}/recipients/${recipientId}`)
}

export function getDomainProfile(datasetId: string, domainId: string) {
  return apiGet<DomainProfile>(`/datasets/${datasetId}/domains/${domainId}`)
}

export interface EventFilters {
  recipient_id?: string
  domain_id?: string
  subject_id?: string
  status?: string
  bounce_type?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export async function listEvents(datasetId: string, filters: EventFilters = {}): Promise<{ items: EmailEventRow[]; meta: PageMeta }> {
  const { data, meta } = await apiGetWithMeta<EmailEventRow[]>(`/datasets/${datasetId}/events`, filters as Record<string, unknown>)
  return { items: data, meta: meta as unknown as PageMeta }
}

export function getEvent(datasetId: string, eventId: string) {
  return apiGet<EmailEventRow>(`/datasets/${datasetId}/events/${eventId}`)
}
