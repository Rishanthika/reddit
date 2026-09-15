import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, Inbox, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import type { Lead } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'

const STATUSES = [
  'NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED',
  'NO_RESPONSE', 'NOT_QUALIFIED', 'CLOSED',
]

const PAGE_SIZE = 25

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function Leads() {
  const [params, setParams] = useSearchParams()
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState(params.get('search') ?? '')
  const [subreddits, setSubreddits] = useState<string[]>([])
  const [page, setPage] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const classification = params.get('classification') ?? ''
  const status = params.get('status') ?? ''
  const subreddit = params.get('subreddit') ?? ''

  useEffect(() => {
    api.settings().then((s) => setSubreddits(s.subreddits ?? [])).catch(() => setSubreddits([]))
  }, [])

  useEffect(() => {
    setPage(0)
  }, [classification, status, subreddit, search])

  useEffect(() => {
    setLoading(true)
    setError(null)
    api
      .leads({
        classification: classification || undefined,
        status: status || undefined,
        subreddit: subreddit || undefined,
        search: search || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      .then((res) => {
        setLeads(res.items)
        setTotal(res.total)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load leads.')
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classification, status, subreddit, search, page, reloadKey])

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl text-[--color-ink]">Leads</h1>
          <p className="mt-1 text-sm text-[--color-ink-faint]">{total} total</p>
        </div>
        <div className="relative">
          <label htmlFor="lead-search" className="sr-only">
            Search lead titles
          </label>
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[--color-ink-faint]" />
          <input
            id="lead-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles…"
            aria-label="Search lead titles"
            className="w-full rounded-lg border border-[--color-line] bg-[--color-paper-raised] py-2 pl-9 pr-3 text-sm outline-none focus:border-[--color-gold] sm:w-64"
          />
        </div>
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-2">
          {['', 'HOT', 'WARM', 'COLD'].map((c) => (
            <button
              key={c || 'all'}
              onClick={() => setFilter('classification', c)}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
                classification === c
                  ? 'bg-[--color-ink] text-white'
                  : 'bg-[--color-paper-raised] text-[--color-ink-soft] border border-[--color-line] hover:bg-[--color-paper]'
              }`}
            >
              {c || 'All priority'}
            </button>
          ))}
        </div>

        <div className="ml-0 flex flex-wrap gap-2 sm:ml-auto">
          <label className="sr-only" htmlFor="status-filter">Filter by status</label>
          <select
            id="status-filter"
            value={status}
            onChange={(e) => setFilter('status', e.target.value)}
            className="rounded-lg border border-[--color-line] bg-[--color-paper-raised] px-3 py-1.5 text-[13px] text-[--color-ink-soft] outline-none focus:border-[--color-gold]"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace('_', ' ')}
              </option>
            ))}
          </select>

          <label className="sr-only" htmlFor="subreddit-filter">Filter by subreddit</label>
          <select
            id="subreddit-filter"
            value={subreddit}
            onChange={(e) => setFilter('subreddit', e.target.value)}
            className="rounded-lg border border-[--color-line] bg-[--color-paper-raised] px-3 py-1.5 text-[13px] text-[--color-ink-soft] outline-none focus:border-[--color-gold]"
          >
            <option value="">All subreddits</option>
            {subreddits.map((s) => (
              <option key={s} value={s}>
                r/{s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
        </div>
      )}

      {!error && !loading && leads.length === 0 && (
        <EmptyState
          icon={<Inbox size={22} />}
          title="No leads match this view."
          description="Try a different filter, or run a Reddit scan to discover new study-abroad conversations."
        />
      )}

      {leads.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl border border-[--color-line] bg-[--color-paper-raised]">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-[--color-line] text-[11.5px] text-[--color-ink-faint]">
                  <th className="px-5 py-3 font-medium">Priority</th>
                  <th className="px-5 py-3 font-medium">Title</th>
                  <th className="px-5 py-3 font-medium">Destination</th>
                  <th className="px-5 py-3 font-medium">Course</th>
                  <th className="px-5 py-3 font-medium">Service</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[--color-line]">
                {leads.map((lead) => (
                  <tr key={lead.id} className="transition-colors hover:bg-[--color-paper]">
                    <td className="px-5 py-3.5">
                      <PriorityBadge classification={lead.lead_classification} score={lead.lead_score} size="sm" />
                    </td>
                    <td className="max-w-xs px-5 py-3.5">
                      <Link to={`/leads/${lead.id}`} className="line-clamp-1 text-[--color-ink] hover:underline">
                        {lead.title}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-[--color-ink-soft]">{lead.destination ?? '—'}</td>
                    <td className="px-5 py-3.5 text-[--color-ink-soft]">{lead.course ?? '—'}</td>
                    <td className="max-w-[160px] px-5 py-3.5 text-[--color-ink-soft]">
                      {lead.service_needed.length ? lead.service_needed.join(', ') : '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="rounded-md bg-[--color-paper] px-2 py-0.5 text-[11.5px] font-medium text-[--color-ink-soft]">
                        {lead.lead_status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[--color-ink-faint]">
                      r/{lead.subreddit}
                      <div className="text-[11.5px]">{timeAgo(lead.processed_at)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-[--color-ink-soft]">
              <span>
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  aria-label="Previous page"
                  className="flex items-center gap-1 rounded-lg border border-[--color-line] bg-[--color-paper-raised] px-3 py-1.5 disabled:opacity-40"
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  aria-label="Next page"
                  className="flex items-center gap-1 rounded-lg border border-[--color-line] bg-[--color-paper-raised] px-3 py-1.5 disabled:opacity-40"
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
