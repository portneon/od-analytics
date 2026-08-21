type Tone = 'neutral' | 'good' | 'warning' | 'critical'

const TONE_STYLES: Record<Tone, string> = {
  neutral: 'text-slate-900',
  good: 'text-emerald-600',
  warning: 'text-amber-600',
  critical: 'text-red-600',
}

export function StatTile({ label, value, tone = 'neutral', hint }: { label: string; value: string | number; tone?: Tone; hint?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold ${TONE_STYLES[tone]}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  )
}

export function rateTone(rate: number, kind: 'delivery' | 'bounce' | 'failure'): Tone {
  if (kind === 'delivery') {
    if (rate >= 95) return 'good'
    if (rate >= 85) return 'warning'
    return 'critical'
  }
  if (rate <= 2) return 'good'
  if (rate <= 8) return 'warning'
  return 'critical'
}
