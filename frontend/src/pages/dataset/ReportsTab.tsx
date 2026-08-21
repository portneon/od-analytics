import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { generateReport } from '@/services/datasets'

export function ReportsTab() {
  const { datasetId } = useParams()
  const [downloading, setDownloading] = useState<'pdf' | 'csv' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleDownload(format: 'pdf' | 'csv') {
    setDownloading(format)
    setError(null)
    try {
      const blob = await generateReport(datasetId!, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `email-intelligence-report.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      setError('Could not generate the report. Please try again.')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <div className="card p-6">
        <h2 className="text-sm font-semibold text-slate-700">Executive Report</h2>
        <p className="mt-1 text-sm text-slate-400">
          Includes overview metrics, top problem domains &amp; recipients, bounce analysis, and recommendations.
        </p>
        <div className="mt-4 flex gap-2">
          <button className="btn-primary" onClick={() => handleDownload('pdf')} disabled={downloading !== null}>
            {downloading === 'pdf' ? 'Generating…' : 'Download PDF'}
          </button>
          <button className="btn-secondary" onClick={() => handleDownload('csv')} disabled={downloading !== null}>
            {downloading === 'csv' ? 'Generating…' : 'Download CSV'}
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  )
}
