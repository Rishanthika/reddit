import { useEffect, useRef, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import type { ValidationState } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'

export function Validation() {
  const [state, setState] = useState<ValidationState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    api.validationStatus().then(setState).catch(() => setState(null))
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const poll = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.validationStatus()
        setState(s)
        if (s.status === 'done' || s.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
        }
      } catch (e) {
        if (pollRef.current) clearInterval(pollRef.current)
        setError(e instanceof Error ? e.message : 'Lost connection to the backend while validating.')
      }
    }, 1200)
  }

  const handleStart = async () => {
    setError(null)
    try {
      const res = await api.startValidation()
      if (!res.started) {
        setError('A validation run is already in progress.')
        return
      }
      poll()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start validation.')
    }
  }

  const running = state?.status === 'running'

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-[--color-ink]/5 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-[--color-ink-soft]">
        <ShieldCheck size={12} /> READ-ONLY VALIDATION
      </div>
      <h1 className="font-display text-3xl text-[--color-ink]">Validation</h1>
      <p className="mt-1 max-w-xl text-sm text-[--color-ink-faint]">
        Validation runs do not write leads to the database. Use this to QA the classifier
        against real Reddit samples before trusting production scans.
      </p>

      <button
        onClick={handleStart}
        disabled={running}
        className="mt-6 rounded-lg bg-[--color-ink] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[--color-ink]/90 disabled:opacity-50"
      >
        {running ? 'Running validation…' : 'Run Validation'}
      </button>
      {error && <p className="mt-2 text-[13px] text-[--color-hot]">{error}</p>}

      {state?.status === 'error' && (
        <div className="mt-6 rounded-xl border border-[--color-hot]/30 bg-[--color-hot-soft] p-5 text-[13.5px] text-[--color-hot]">
          {state.error}
        </div>
      )}

      {state?.summary && (
        <div className="mt-8 flex divide-x divide-[--color-line] overflow-x-auto rounded-xl border border-[--color-line] bg-[--color-paper-raised] text-center lg:grid lg:grid-cols-7 lg:overflow-visible">
          <SummaryStat label="Retrieved" value={state.summary.retrieved} />
          <SummaryStat label="Filtered" value={state.summary.filtered_out} />
          <SummaryStat label="Classified" value={state.summary.sent_to_classifier} />
          <SummaryStat label="Errors" value={state.summary.ai_errors} />
          <SummaryStat label="HOT" value={state.summary.hot} accent="text-[--color-hot]" />
          <SummaryStat label="WARM" value={state.summary.warm} accent="text-[--color-warm]" />
          <SummaryStat label="COLD" value={state.summary.cold} accent="text-[--color-cold]" />
        </div>
      )}

      {state && state.results.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-xl border border-[--color-line] bg-[--color-paper-raised]">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-[--color-line] text-[11.5px] text-[--color-ink-faint]">
                <th className="px-4 py-2.5 font-medium">Score</th>
                <th className="px-4 py-2.5 font-medium">Title</th>
                <th className="px-4 py-2.5 font-medium">Lead</th>
                <th className="px-4 py-2.5 font-medium">Intent</th>
                <th className="px-4 py-2.5 font-medium">Destination</th>
                <th className="px-4 py-2.5 font-medium">Course</th>
                <th className="px-4 py-2.5 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[--color-line]">
              {state.results.map((r) => (
                <tr key={r.reddit_post_id}>
                  <td className="px-4 py-3">
                    {r.error ? (
                      <span className="text-[--color-hot]">Error</span>
                    ) : (
                      <PriorityBadge classification={r.classification ?? null} score={r.score} size="sm" />
                    )}
                  </td>
                  <td className="max-w-xs px-4 py-3">
                    <div className="line-clamp-1 text-[--color-ink]">{r.title}</div>
                  </td>
                  <td className="px-4 py-3 text-[--color-ink-soft]">{r.error ? '—' : String(r.is_lead)}</td>
                  <td className="px-4 py-3 text-[--color-ink-soft]">{r.intent ?? '—'}</td>
                  <td className="px-4 py-3 text-[--color-ink-soft]">{r.destination ?? '—'}</td>
                  <td className="px-4 py-3 text-[--color-ink-soft]">{r.course ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-[--color-ink-faint]">r/{r.subreddit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SummaryStat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="shrink-0 px-3 py-4" style={{ minWidth: '90px' }}>
      <div className={`font-mono-num text-2xl font-medium ${accent ?? 'text-[--color-ink]'}`}>{value}</div>
      <div className="mt-0.5 whitespace-nowrap text-[11px] text-[--color-ink-faint]">{label}</div>
    </div>
  )
}
