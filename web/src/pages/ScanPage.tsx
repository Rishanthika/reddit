import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { RadarIcon, CheckCircle2, AlertTriangle, ArrowRight, Loader2, Zap } from 'lucide-react'
import { api } from '../lib/api'
import type { ScanRun, ScanState, SettingsStatus } from '../lib/types'
import { ErrorState } from '../components/ErrorState'
import { useToast } from '../lib/toast'

const STAGES = [
  { key: 'discovering', label: 'Discovering' },
  { key: 'filtering', label: 'Filtering' },
  { key: 'analyzing', label: 'AI Qualification' },
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

function duration(start: string | null, end: string | null) {
  if (!start || !end) return '—'
  const secs = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

export function ScanPage() {
  const toast = useToast()
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
          if (state.status === 'done') {
            toast.show(`Scan complete — ${state.hot} HOT, ${state.warm} WARM, ${state.cold} COLD`)
          } else {
            toast.show('Scan failed', 'error')
          }
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
      toast.show('Reddit scan started')
      poll()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start scan.')
    }
  }

  const running = scan?.status === 'starting' || scan?.status === 'running'
  const idx = scan ? stageIndex(scan.stage) : -1
  const lastRun = recent[0]

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl text-[--color-navy]">Scan Reddit</h1>
          <p className="mt-1 text-sm text-[--color-muted]">Discover fresh study-abroad conversations from Reddit, live via Apify.</p>
        </div>
        {running && (
          <span className="fg-pulse hidden items-center gap-1.5 rounded-full bg-[--color-hot-soft] px-3 py-1 text-[11.5px] font-semibold text-[--color-hot] sm:inline-flex">
            <Zap size={11} /> LIVE
          </span>
        )}
      </div>

      {/* Summary bar — real data from the most recent persisted scan run */}
      {lastRun && (
        <div className="mt-5 grid grid-cols-2 gap-3 rounded-xl border border-[--color-border] bg-[--color-surface] p-4 sm:grid-cols-4">
          <SummaryCell label="Last Scan" value={timeAgo(lastRun.started_at)} />
          <SummaryCell label="Duration" value={duration(lastRun.started_at, lastRun.finished_at)} />
          <SummaryCell label="Posts Retrieved" value={String(lastRun.discovered ?? '—')} />
          <SummaryCell label="Leads Found" value={String((lastRun.hot ?? 0) + (lastRun.warm ?? 0) + (lastRun.cold ?? 0))} />
        </div>
      )}

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
      <div className={`mt-6 overflow-hidden rounded-2xl border ${running ? 'border-[--color-royal]/30' : 'border-[--color-border]'} bg-[--color-surface] shadow-[0_8px_28px_-14px_rgba(7,24,39,0.2)]`}>
        <div className={`px-6 py-5 ${running ? 'fg-gradient' : 'bg-[--color-bg]'}`}>
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${running ? 'fg-pulse bg-[--color-gold]' : scan?.status === 'error' ? 'bg-[--color-hot]' : 'bg-[--color-emerald]'}`} />
            <span className={`text-[13px] font-semibold tracking-wide ${running ? 'text-white' : 'text-[--color-text]'}`}>
              {running ? 'SCANNING REDDIT' : scan?.status === 'error' ? 'SCAN FAILED' : scan?.status === 'done' ? 'SCAN COMPLETE' : 'READY TO SCAN'}
            </span>
          </div>
        </div>

        <div className="p-6">
          {!running && scan?.status !== 'done' && (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">Sources</div>
                  <div className="mt-1 text-[15px] text-[--color-text]">{settings?.subreddits?.length ?? '—'} communities</div>
                </div>
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">Post limit</div>
                  <select
                    value={postLimit}
                    onChange={(e) => setPostLimit(Number(e.target.value))}
                    aria-label="Posts to retrieve per subreddit"
                    className="mt-1 rounded-md border border-[--color-border] bg-[--color-surface] px-2 py-1 text-[15px] text-[--color-text] outline-none focus:border-[--color-royal]"
                  >
                    {allowedLimits.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">AI Provider</div>
                  <div className="mt-1 text-[15px] text-[--color-text]">{settings?.ai_provider ?? '—'}</div>
                </div>
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">Storage</div>
                  <div className="mt-1 text-[15px] text-[--color-text]">SQLite</div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-1.5">
                {(settings?.subreddits ?? []).map((s) => (
                  <span key={s} className="rounded-md bg-[--color-royal-soft] px-2 py-0.5 text-[12px] font-medium text-[--color-royal]">r/{s}</span>
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
                        <span className="h-4 w-4 rounded-full border-2 border-[--color-border]" />
                      )}
                      <span className={`text-[13.5px] ${done ? 'text-[--color-muted] line-through' : active ? 'font-medium text-[--color-royal]' : 'text-[--color-muted]'}`}>
                        {stage.label}
                      </span>
                    </div>
                  )
                })}
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3 border-t border-[--color-border] pt-5 sm:grid-cols-7">
                {[
                  ['Retrieved', scan.discovered], ['Filtered', scan.filtered], ['Analyzed', scan.analyzed],
                  ['HOT', scan.hot], ['WARM', scan.warm], ['COLD', scan.cold],
                ].map(([label, value]) => (
                  <div key={label as string}>
                    <div className="font-mono-num text-xl font-medium text-[--color-navy]">{idx >= 0 ? value : '—'}</div>
                    <div className="text-[11px] text-[--color-muted]">{label}</div>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-[11.5px] text-[--color-muted]">Last updated: {new Date().toLocaleTimeString()}</p>
            </>
          )}

          {!running && scan?.status === 'done' && (
            <>
              <div className="grid grid-cols-3 gap-4 sm:grid-cols-7">
                {[
                  ['Retrieved', scan.discovered, ''], ['Filtered', scan.filtered, ''], ['Analyzed', scan.analyzed, ''],
                  ['HOT', scan.hot, 'text-[--color-hot]'], ['WARM', scan.warm, 'text-[--color-warm]'], ['COLD', scan.cold, 'text-[--color-cold]'],
                ].map(([label, value, accent]) => (
                  <div key={label as string}>
                    <div className={`font-mono-num text-xl font-medium ${accent || 'text-[--color-navy]'}`}>{value}</div>
                    <div className="text-[11px] text-[--color-muted]">{label}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px] text-[--color-muted]">
                <span>Completed {timeAgo(scan.finished_at)}</span>
                <span>Sources: {(scan.sources ?? []).map((s) => `r/${s}`).join(', ')}</span>
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                <Link to="/leads" className="inline-flex items-center gap-2 rounded-lg bg-[--color-royal] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[--color-royal]/90">
                  View New Leads <ArrowRight size={14} />
                </Link>
                <Link to="/activity" className="inline-flex items-center gap-2 rounded-lg border border-[--color-border] px-4 py-2.5 text-sm font-medium text-[--color-text-soft] hover:bg-[--color-bg]">
                  View Activity
                </Link>
              </div>
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
        <h2 className="mb-3 font-display text-lg text-[--color-navy]">Recent Scan History</h2>
        {recent.length === 0 ? (
          <p className="text-sm text-[--color-muted]">No scans have been run yet.</p>
        ) : (
          <div className="fg-card overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead>
                <tr className="border-b border-[--color-border] text-[11px] text-[--color-muted]">
                  <th className="px-4 py-2.5 font-medium">Started</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Retrieved</th>
                  <th className="px-4 py-2.5 font-medium">Filtered</th>
                  <th className="px-4 py-2.5 font-medium">HOT</th>
                  <th className="px-4 py-2.5 font-medium">WARM</th>
                  <th className="px-4 py-2.5 font-medium">COLD</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[--color-border]">
                {recent.map((run) => (
                  <tr key={run.id}>
                    <td className="whitespace-nowrap px-4 py-3 text-[--color-muted]">{timeAgo(run.started_at)}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-md px-2 py-0.5 text-[11.5px] font-medium ${
                        run.status === 'done' ? 'bg-[--color-teal-soft] text-[--color-teal]' : run.status === 'error' ? 'bg-[--color-hot-soft] text-[--color-hot]' : 'bg-[--color-royal-soft] text-[--color-royal]'
                      }`}>
                        {run.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[--color-text-soft]">{duration(run.started_at, run.finished_at)}</td>
                    <td className="px-4 py-3 text-[--color-text-soft]">{run.discovered ?? '—'}</td>
                    <td className="px-4 py-3 text-[--color-text-soft]">{run.filtered ?? '—'}</td>
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

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10.5px] font-medium uppercase tracking-wide text-[--color-muted]">{label}</div>
      <div className="font-mono-num mt-0.5 text-[16px] font-semibold text-[--color-navy]">{value}</div>
    </div>
  )
}
