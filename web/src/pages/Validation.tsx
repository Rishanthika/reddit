import { useEffect, useRef, useState, Fragment } from 'react'
import { ShieldCheck, ChevronDown, ChevronUp, Info } from 'lucide-react'
import { api } from '../lib/api'
import type { ValidationState } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'

export function Validation() {
  const [state, setState] = useState<ValidationState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
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
      <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-[--color-violet-soft] px-2.5 py-1 text-[11px] font-semibold tracking-wide text-[--color-violet]">
        <ShieldCheck size={12} /> READ-ONLY VALIDATION
      </div>
      <h1 className="font-display text-3xl text-[--color-navy]">AI Validation</h1>
      <p className="mt-1 max-w-xl text-sm text-[--color-muted]">
        Validation runs do not write leads to the database. Use this to QA the classifier
        against real Reddit samples before trusting production scans.
      </p>

      <button
        onClick={handleStart}
        disabled={running}
        className="fg-gradient-ai mt-6 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-transform hover:-translate-y-px disabled:opacity-50"
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
        <div className="mt-8 flex divide-x divide-[--color-border] overflow-x-auto rounded-xl border border-[--color-border] bg-[--color-surface] text-center lg:grid lg:grid-cols-7 lg:overflow-visible">
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
        <>
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-[--color-bg] px-3.5 py-2.5 text-[12px] text-[--color-muted]">
            <Info size={13} className="mt-0.5 shrink-0" />
            Precision/recall metrics require labeled ground truth this system doesn't track yet —
            expand a row to review the AI's own stated reasoning instead.
          </div>
          <div className="mt-3 fg-card overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-[--color-border] text-[11.5px] text-[--color-muted]">
                  <th className="px-4 py-2.5 font-medium">Score</th>
                  <th className="px-4 py-2.5 font-medium">Title</th>
                  <th className="px-4 py-2.5 font-medium">Lead</th>
                  <th className="px-4 py-2.5 font-medium">Intent</th>
                  <th className="px-4 py-2.5 font-medium">Destination</th>
                  <th className="px-4 py-2.5 font-medium">Course</th>
                  <th className="px-4 py-2.5 font-medium">Source</th>
                  <th className="px-4 py-2.5 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[--color-border]">
                {state.results.map((r) => (
                  <Fragment key={r.reddit_post_id}>
                    <tr
                      onClick={() => setExpanded(expanded === r.reddit_post_id ? null : r.reddit_post_id)}
                      className="cursor-pointer hover:bg-[--color-bg]"
                    >
                      <td className="px-4 py-3">
                        {r.error ? <span className="text-[--color-hot]">Error</span> : <PriorityBadge classification={r.classification ?? null} score={r.score} size="sm" />}
                      </td>
                      <td className="max-w-xs px-4 py-3"><div className="line-clamp-1 text-[--color-text]">{r.title}</div></td>
                      <td className="px-4 py-3 text-[--color-text-soft]">{r.error ? '—' : String(r.is_lead)}</td>
                      <td className="px-4 py-3 text-[--color-text-soft]">{r.intent ?? '—'}</td>
                      <td className="px-4 py-3 text-[--color-text-soft]">{r.destination ?? '—'}</td>
                      <td className="px-4 py-3 text-[--color-text-soft]">{r.course ?? '—'}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-[--color-muted]">r/{r.subreddit}</td>
                      <td className="px-4 py-3 text-[--color-muted]">
                        {expanded === r.reddit_post_id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </td>
                    </tr>
                    {expanded === r.reddit_post_id && (
                      <tr className="bg-[--color-bg]">
                        <td colSpan={8} className="px-4 py-3 text-[13px] text-[--color-text-soft]">
                          {r.error ?? r.reason ?? 'No reasoning recorded.'}
                          {typeof r.confidence === 'number' && (
                            <span className="ml-3 text-[--color-muted]">Confidence: {Math.round(r.confidence * 100)}%</span>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function SummaryStat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="shrink-0 px-3 py-4" style={{ minWidth: '90px' }}>
      <div className={`font-mono-num text-2xl font-medium ${accent ?? 'text-[--color-navy]'}`}>{value}</div>
      <div className="mt-0.5 whitespace-nowrap text-[11px] text-[--color-muted]">{label}</div>
    </div>
  )
}
