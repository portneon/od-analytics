import type { PageMeta } from '@/types/api'

export function Pagination({ meta, onPageChange }: { meta: PageMeta; onPageChange: (page: number) => void }) {
  if (meta.total_pages <= 1) return null
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2 text-sm text-slate-500">
      <span>
        {meta.total} total · page {meta.page} of {meta.total_pages}
      </span>
      <div className="flex gap-2">
        <button className="btn-secondary px-2 py-1" disabled={meta.page <= 1} onClick={() => onPageChange(meta.page - 1)}>
          Previous
        </button>
        <button className="btn-secondary px-2 py-1" disabled={meta.page >= meta.total_pages} onClick={() => onPageChange(meta.page + 1)}>
          Next
        </button>
      </div>
    </div>
  )
}
