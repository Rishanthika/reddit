import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { RadarIcon, CheckCircle2, AlertTriangle, ArrowRight, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import type { ScanRun, ScanState, SettingsStatus } from '../lib/types'
import { ErrorState } from '../components/ErrorState'

const STAGES = [
  { key: 'discovering', label: 'Discovering' },
  { key: 'filtering', label: 'Filtering' },
  { key: 'analyzing', label: 'Analyzing' },
  { key: 'scoring', label: 'Scoring' },
  { key: 'saving', label: 'Saving' },
]

function stageIndex(stage: string) {
  const i = STAGES.findIndex((s) => s.key === stage)
  return i === -1 ? (stage === 'complete' ? STAGES.length : -1) : i
}

function timeAgo(iso: string | null) {
  if (!iso) return '—'
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function ScanPage() {
  const [settings, setSettings] = useState<SettingsStatus | null>(null)
  const [scan, setScan] = useState<ScanState | null>(null)
  const [recent, setRecent] = useState<ScanRun[]>([])
  const [postLimit, setPostLimit] = useState<number>(25)
  const [allowedLimits, setAllowedLimits] = useState<number[]>([10, 25, 50, 100])
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadRecent = () => {
    api.recentScans(5).then(setRecent).catch(() => {})
  }

  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s)
      if (s.post_limit) setPostLimit(s.post_limit)
    }).catch(() => setSettings(null))
    api.scanStatus().then(setScan).catch(() => setScan(null))
    api.scanLimits().then((r) => setAllowedLimits(r.allowed)).catch(() => {})
    loadRecent()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const poll = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const state = await api.scanStatus()
        setScan(state)
        if (state.status === 'done' || state.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          loadRecent()
        }
      } catch (e) {
        if (pollRef.current) clearInterval(pollRef.current)
        setError(e instanceof Error ? e.message : 'Lost connection to the backend while scanning.')
      }
    }, 1000)
  }

  const handleStart = async () => {
    setError(null)
    try {
      const res = await api.startScan(postLimit)
      if (!res.started) {
        setError('A scan is already running.')
        return
      }
      poll()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start scan.')
    }
  }

  const running = scan?.status === 'starting' || scan?.status === 'running'
  const idx = scan ? stageIndex(scan.stage) : -1

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-navy]">Scan Reddit</h1>
      <p className="mt-1 text-sm text-[--color-ink-faint]">
        Discover fresh study-abroad conversations from Reddit, live via Apify.
      </p>

      {error && (
        <div className="mt-6">
          <ErrorState
            message={error}
            onRetry={() => {
              setError(null)
              api.scanStatus().then(setScan).catch(() => {})
            }}
          />
        </div>
      )}

      {/* Main scan console */}
      <div
        className={`mt-6 overflow-hidden rounded-2xl border ${
          running ? 'border-[--color-royal]/30' : 'border-[--color-line]'
        } bg-[--color-paper-raised] shadow-[0_8px_28px_-14px_rgba(16,26,51,0.2)]`}
      >
        <div className={`px-6 py-5 ${running ? 'fg-gradient' : 'bg-[--color-paper]'}`}>
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                running ? 'fg-pulse bg-[--color-gold]' : scan?.status === 'error' ? 'bg-[--color-hot]' : 'bg-emerald-500'
              }`}
            />
            <span className={`text-[13px] font-semibold tracking-wide ${running ? 'text-white' : 'text-[--color-ink]'}`}>
              {running
                ? 'SCANNING REDDIT'
                : scan?.status === 'error'
                  ? 'SCAN FAILED'
                  : scan?.status === 'done'
                    ? 'SCAN COMPLETE'
                    : 'READY TO SCAN'}
            </span>
          </div>
        </div>

        <div className="p-6">
          {!running && scan?.status !== 'done' && (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-ink-faint]">Sources</div>
                  <div className="mt-1 text-[15px] text-[--color-ink]">
                    {settings?.subreddits?.length ?? '—'} communities
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-ink-faint]">Post limit</div>
                  <select
                    value={postLimit}
                    onChange={(e) => setPostLimit(Number(e.target.value))}
                    aria-label="Posts to retrieve per subreddit"
                    className="mt-1 rounded-md border border-[--color-line] bg-[--color-paper-raised] px-2 py-1 text-[15px] text-[--color-ink] outline-none focus:border-[--color-royal]"
                  >
                    {allowedLimits.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-ink-faint]">Mode</div>
                  <div className="mt-1 text-[15px] text-[--color-ink]">Live retrieval</div>
                </div>
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-ink-faint]">Storage</div>
                  <div className="mt-1 text-[15px] text-[--color-ink]">SQLite</div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-1.5">
                {(settings?.subreddits ?? []).map((s) => (
                  <span key={s} className="rounded-md bg-[--color-royal-soft] px-2 py-0.5 text-[12px] font-medium text-[--color-royal]">
                    r/{s}
                  </span>
                ))}
              </div>

              <button
                onClick={handleStart}
                className="fg-gradient mt-6 flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-[14px] font-semibold text-white shadow-[0_6px_20px_-4px_rgba(37,71,208,0.5)] transition-transform hover:-translate-y-px"
              >
                <RadarIcon size={17} />
                SCAN REDDIT
              </button>
            </>
          )}

          {running && scan && (
            <>
              <div className="space-y-2.5">
                {STAGES.map((stage, i) => {
                  const done = i < idx
                  const active = i === idx
                  return (
                    <div key={stage.key} className="flex items-center gap-3">
                      {done ? (
                        <CheckCircle2 size={16} className="text-[--color-teal]" />
                      ) : active ? (
                        <Loader2 size={16} className="animate-spin text-[--color-royal]" />
                      ) : (
                        <span className="h-4 w-4 rounded-full border-2 border-[--color-line]" />
                      )}
                      <span
                        className={`text-[13.5px] ${
                          done ? 'text-[--color-ink-faint] line-through' : active ? 'font-medium text-[--color-royal]' : 'text-[--color-ink-faint]'
                        }`}
                      >
                        {stage.label}
                      </span>
                    </div>
                  )
                })}
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3 border-t border-[--color-line] pt-5 sm:grid-cols-7">
                {[
                  ['Retrieved', scan.discovered],
                  ['Filtered', scan.filtered],
                  ['Analyzed', scan.analyzed],
                  ['HOT', scan.hot],
                  ['WARM', scan.warm],
                  ['COLD', scan.cold],
                ].map(([label, value]) => (
                  <div key={label as string}>
                    <div className="font-mono-num text-xl font-medium text-[--color-navy]">
                      {idx >= 0 ? value : '—'}
                    </div>
                    <div className="text-[11px] text-[--color-ink-faint]">{label}</div>
                  </div>
                ))}
              </div>

              <p className="mt-4 text-[11.5px] text-[--color-ink-faint]">
                Last updated: {new Date().toLocaleTimeString()}
              </p>
            </>
          )}

          {!running && scan?.status === 'done' && (
            <>
              <div className="grid grid-cols-3 gap-4 sm:grid-cols-7">
                {[
                  ['Retrieved', scan.discovered],
                  ['Filtered', scan.filtered],
                  ['Analyzed', scan.analyzed],
                  ['HOT', scan.hot, 'text-[--color-hot]'],
                  ['WARM', scan.warm, 'text-[--color-warm]'],
                  ['COLD', scan.cold, 'text-[--color-cold]'],
                ].map(([label, value, accent]) => (
                  <div key={label as string}>
                    <div className={`font-mono-num text-xl font-medium ${accent ?? 'text-[--color-navy]'}`}>{value}</div>
                    <div className="text-[11px] text-[--color-ink-faint]">{label}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px] text-[--color-ink-faint]">
                <span>Completed {timeAgo(scan.finished_at)}</span>
                <span>Sources: {(scan.sources ?? []).map((s) => `r/${s}`).join(', ')}</span>
              </div>
              <Link
                to="/leads"
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[--color-royal] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[--color-royal]/90"
              >
                View New Leads <ArrowRight size={14} />
              </Link>
            </>
          )}

          {scan?.status === 'error' && (
            <div className="flex items-start gap-3 rounded-lg bg-[--color-hot-soft] p-4">
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[--color-hot]" />
              <div className="text-[13.5px] text-[--color-hot]">{scan.error}</div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Scans */}
      <div className="mt-10">
        <h2 className="mb-3 font-display text-lg text-[--color-navy]">Recent Scans</h2>
        {recent.length === 0 ? (
          <p className="text-sm text-[--color-ink-faint]">No scans have been run yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-[--color-line] bg-[--color-paper-raised]">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-[--color-line] text-[11px] text-[--color-ink-faint]">
                  <th className="px-4 py-2.5 font-medium">Started</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Sources</th>
                  <th className="px-4 py-2.5 font-medium">Retrieved</th>
                  <th className="px-4 py-2.5 font-medium">Filtered</th>
                  <th className="px-4 py-2.5 font-medium">HOT</th>
                  <th className="px-4 py-2.5 font-medium">WARM</th>
                  <th className="px-4 py-2.5 font-medium">COLD</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[--color-line]">
                {recent.map((run) => (
                  <tr key={run.id}>
                    <td className="whitespace-nowrap px-4 py-3 text-[--color-ink-faint]">{timeAgo(run.started_at)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[11.5px] font-medium ${
                          run.status === 'done'
                            ? 'bg-[--color-teal-soft] text-[--color-teal]'
                            : run.status === 'error'
                              ? 'bg-[--color-hot-soft] text-[--color-hot]'
                              : 'bg-[--color-royal-soft] text-[--color-royal]'
                        }`}
                      >
                        {run.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[--color-ink-soft]">{run.sources.length}</td>
                    <td className="px-4 py-3 text-[--color-ink-soft]">{run.discovered ?? '—'}</td>
                    <td className="px-4 py-3 text-[--color-ink-soft]">{run.filtered ?? '—'}</td>
                    <td className="px-4 py-3 text-[--color-hot]">{run.hot ?? '—'}</td>
                    <td className="px-4 py-3 text-[--color-warm]">{run.warm ?? '—'}</td>
                    <td className="px-4 py-3 text-[--color-cold]">{run.cold ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
