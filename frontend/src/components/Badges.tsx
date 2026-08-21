const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-700 border-red-200',
  HIGH: 'bg-orange-100 text-orange-700 border-orange-200',
  MEDIUM: 'bg-amber-100 text-amber-700 border-amber-200',
  LOW: 'bg-slate-100 text-slate-600 border-slate-200',
  INFO: 'bg-blue-100 text-blue-700 border-blue-200',
}

export function SeverityBadge({ severity }: { severity: string }) {
  const style = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.LOW
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>{severity}</span>
}

export function RiskBadge({ level }: { level: string }) {
  return <SeverityBadge severity={level} />
}

const STATUS_STYLES: Record<string, string> = {
  SUCCESS: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  HARD_BOUNCE: 'bg-red-100 text-red-700 border-red-200',
  SOFT_BOUNCE: 'bg-amber-100 text-amber-700 border-amber-200',
  FAILED: 'bg-red-100 text-red-700 border-red-200',
  DEFERRED: 'bg-amber-100 text-amber-700 border-amber-200',
  UNKNOWN: 'bg-slate-100 text-slate-500 border-slate-200',
}

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.UNKNOWN
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>{status.replace('_', ' ')}</span>
}

const DATASET_STATUS_STYLES: Record<string, string> = {
  COMPLETED: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  PARTIAL: 'bg-amber-100 text-amber-700 border-amber-200',
  FAILED: 'bg-red-100 text-red-700 border-red-200',
  PROCESSING: 'bg-blue-100 text-blue-700 border-blue-200',
  QUEUED: 'bg-slate-100 text-slate-600 border-slate-200',
  UPLOADING: 'bg-slate-100 text-slate-600 border-slate-200',
}

export function DatasetStatusBadge({ status }: { status: string }) {
  const style = DATASET_STATUS_STYLES[status] ?? DATASET_STATUS_STYLES.QUEUED
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>{status}</span>
}
