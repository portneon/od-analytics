export interface ApiSuccess<T> {
  success: true
  data: T
  meta: Record<string, unknown>
}

export interface ApiError {
  success: false
  error: { code: string; message: string }
}

export interface PageMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface Dataset {
  id: string
  name: string
  source: string
  file_name: string
  row_count: number | null
  date_start: string | null
  date_end: string | null
  status: 'UPLOADING' | 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL' | 'FAILED'
  schema_version: string
  created_at: string
  updated_at: string
}

export interface DataQualityReport {
  rows: number
  valid_rows: number
  invalid_rows: number
  duplicate_rows: number
  retry_rows: number
  malformed_emails: number
  missing_timestamps: number
  missing_recipient: number
  missing_bounce_information: number
  missing_open_data: boolean
  missing_click_data: boolean
  unmapped_source_columns: string[]
  missing_optional_fields: string[]
  issue_samples: { row_index: number; field: string; issue: string; raw_value: string | null }[]
}

export interface Overview {
  total_emails: number
  unique_recipients: number
  unique_senders: number
  unique_subjects: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  duplicate_rows: number
  retry_rows: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
}

export interface DailyPoint {
  date: string
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
  unique_recipients: number
}

export interface HourlyPoint {
  hour: number
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
}

export interface DayOfWeekPoint {
  day_of_week: string
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
}

export interface EntityMetric {
  id: string
  name: string
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
  risk_score?: number
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  first_seen?: string
  last_seen?: string
  unique_subjects?: number
  unique_senders?: number
  unique_recipients?: number
}

export interface RecipientProfile {
  id: string
  email: string
  domain: string
  metrics: {
    total_emails: number
    successful: number
    hard_bounces: number
    soft_bounces: number
    failures: number
    delivery_rate: number
    bounce_rate: number
    failure_rate: number
    risk_score: number
    risk_level: string
    risk_reasons: string[]
    first_seen: string | null
    last_seen: string | null
    unique_subjects: number
    unique_senders: number
  } | null
  timeline: { id: string; event_time: string; status: string; bounce_category: string | null }[]
}

export interface DomainProfile {
  id: string
  domain: string
  provider: string | null
  metrics: {
    total_emails: number
    successful: number
    hard_bounces: number
    soft_bounces: number
    failures: number
    delivery_rate: number
    bounce_rate: number
    failure_rate: number
    unique_recipients: number
  } | null
}

export interface BounceReason {
  bounce_category: string
  business_label: string
  bounce_code: string | null
  bounce_type: string
  count: number
  percent_of_total: number
}

export interface InfrastructureRow {
  component_type: string
  component_value: string
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
  unique_recipients: number
}

export interface ApplicationRow {
  category: string
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
  unique_recipients: number
}

export interface Anomaly {
  id: string
  metric: string
  entity_type: string
  entity_id: string | null
  observed_value: number
  expected_value: number
  deviation: number
  method: string
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  period_start: string | null
  period_end: string | null
  explanation: string
  contributors: unknown
  recommendations: string[] | null
  detected_at: string
}

export interface Insight {
  id: string
  dataset_id: string
  dataset_name?: string | null
  title: string
  severity: string
  metric: string
  entity_type: string
  entity_id: string | null
  observed: number
  baseline: number
  change_percent: number | null
  explanation: string
  contributors: { dimension: string; value: string; contribution_percent: number }[]
  recommendations: string[]
  detected_at: string
}

export interface ExecutiveRecentDataset {
  id: string
  name: string
  status: Dataset['status']
  row_count: number | null
  date_start: string | null
  date_end: string | null
  created_at: string
}

export interface ExecutiveSummary {
  total_datasets: number
  usable_datasets: number
  status_counts: Record<string, number>
  needs_attention: number
  total_emails: number
  unique_recipients: number
  unique_domains: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
  insights: Insight[]
  recent_datasets: ExecutiveRecentDataset[]
}

export interface ExecutiveDailyPoint {
  date: string
  total_emails: number
  successful: number
  hard_bounces: number
  soft_bounces: number
  failures: number
  delivery_rate: number
  bounce_rate: number
  failure_rate: number
}

export interface EmailEventRow {
  id: string
  event_time: string
  sender_email: string | null
  recipient_email: string | null
  status: string
  bounce_type: string
  bounce_code: string | null
  bounce_category: string
  bounce_reason: string | null
  remote_ip: string | null
  remote_mta: string | null
  relay_server: string | null
  mail_reference: string | null
  processing_time: number | null
  is_retry: boolean
  retry_group_id: string | null
  retry_count: number
  is_duplicate: boolean
  raw_record?: Record<string, unknown>
}

export interface AskResult {
  answer: string
  ai_available: boolean
  tool_calls: { tool: string; arguments: Record<string, unknown>; result: unknown }[]
  error?: string
}
