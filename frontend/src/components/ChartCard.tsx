import { useEffect, useState } from 'react'

/** Wraps a chart in the standard card with a title and an expand button that
 * opens the same chart full-screen. `children` is a render function so each
 * chart can render itself at a larger height when expanded. */
export function ChartCard({ title, children }: { title: string; children: (expanded: boolean) => React.ReactNode }) {
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (!expanded) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [expanded])

  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        <button
          type="button"
          aria-label="Expand chart"
          className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          onClick={() => setExpanded(true)}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 3H3v6M15 3h6v6M9 21H3v-6M15 21h6v-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      {children(false)}

      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6"
          onClick={() => setExpanded(false)}
        >
          <div
            className="max-h-full w-full max-w-5xl overflow-auto rounded-lg bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-800">{title}</h2>
              <button
                type="button"
                aria-label="Close"
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                onClick={() => setExpanded(false)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
            {children(true)}
          </div>
        </div>
      )}
    </div>
  )
}
