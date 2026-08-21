import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { askQuestion } from '@/services/ai'
import type { AskResult } from '@/types/api'

const SUGGESTED_QUESTIONS = [
  'Why did failures increase?',
  'Which domain has the highest bounce rate?',
  'Show me the top problematic recipients',
  'Which subjects have the highest failure rate?',
  'Which application workflow generates the most failures?',
]

interface ConversationEntry {
  question: string
  result: AskResult
}

export function AskTab() {
  const { datasetId } = useParams()
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<ConversationEntry[]>([])

  const mutation = useMutation({
    mutationFn: (q: string) => askQuestion(datasetId!, q),
    onSuccess: (result, q) => setHistory((prev) => [...prev, { question: q, result }]),
  })

  function handleAsk(q: string) {
    if (!q.trim()) return
    mutation.mutate(q)
    setQuestion('')
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      {history.length === 0 && (
        <div className="card p-6 text-center">
          <p className="text-sm font-medium text-slate-700">Ask your data</p>
          <p className="mt-1 text-sm text-slate-400">Ask a question in plain language. Every number comes directly from this dataset.</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button key={q} className="btn-secondary text-xs" onClick={() => handleAsk(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {history.map((entry, i) => (
          <div key={i} className="space-y-2">
            <div className="ml-auto max-w-[80%] rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">{entry.question}</div>
            <div className="card max-w-[90%] p-4">
              {!entry.result.ai_available && (
                <p className="mb-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                  AI narrative unavailable — showing underlying data directly.
                </p>
              )}
              <p className="whitespace-pre-wrap text-sm text-slate-700">{entry.result.answer}</p>
              {entry.result.tool_calls.length > 0 && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-medium text-slate-400">
                    View underlying data ({entry.result.tool_calls.map((c) => c.tool).join(', ')})
                  </summary>
                  <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-600">
                    {JSON.stringify(entry.result.tool_calls, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}
        {mutation.isPending && <p className="text-sm text-slate-400">Analyzing…</p>}
      </div>

      <form
        className="sticky bottom-4 flex gap-2 rounded-lg border border-slate-200 bg-white p-2 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault()
          handleAsk(question)
        }}
      >
        <input
          className="input border-none focus:ring-0"
          placeholder="Ask a question about this dataset…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="btn-primary" type="submit" disabled={mutation.isPending}>
          Ask
        </button>
      </form>
    </div>
  )
}
