import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, Inbox, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react'
import { api } from '../lib/api'
import type { Lead } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'
import { LeadDrawer } from '../components/LeadDrawer'

const STATUSES = [
  'NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED',
  'NO_RESPONSE', 'NOT_QUALIFIED', 'CLOSED',
]

const SORTS = [
  { key: 'newest', label: 'Newest first' },
  { key: 'oldest', label: 'Oldest first' },
  { key: 'score_desc', label: 'Score: high to low' },
  { key: 'score_asc', label: 'Score: low to high' },
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
  const [destinations, setDestinations] = useState<string[]>([])
  const [courses, setCourses] = useState<string[]>([])
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState('newest')
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [previewLead, setPreviewLead] = useState<Lead | null>(null)

  const classification = params.get('classification') ?? ''
  const status = params.get('status') ?? ''
  const subreddit = params.get('subreddit') ?? ''
  const destination = params.get('destination') ?? ''
  const course = params.get('course') ?? ''

  useEffect(() => {
    api.settings().then((s) => setSubreddits(s.subreddits ?? [])).catch(() => setSubreddits([]))
    api.analytics().then((a) => {
      setDestinations(Object.keys(a.destination_distribution).sort())
      setCourses(Object.keys(a.course_distribution).sort())
    }).catch(() => {})
  }, [])

  useEffect(() => {
    setPage(0)
  }, [classification, status, subreddit, destination, course, search])

  useEffect(() => {
    setLoading(true)
    setError(null)
    api
      .leads({
        classification: classification || undefined,
        status: status || undefined,
        subreddit: subreddit || undefined,
        destination: destination || undefined,
        course: course || undefined,
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
  }, [classification, status, subreddit, destination, course, search, page, reloadKey])

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  // Sorting is applied client-side to the current page — the backend
  // always returns newest-first; no backend change needed for this.
  const sortedLeads = useMemo(() => {
    const copy = [...leads]
    switch (sort) {
      case 'oldest':
        return copy.reverse()
      case 'score_desc':
        return copy.sort((a, b) => (b.lead_score ?? 0) - (a.lead_score ?? 0))
      case 'score_asc':
        return copy.sort((a, b) => (a.lead_score ?? 0) - (b.lead_score ?? 0))
      default:
        return copy
    }
  }, [leads, sort])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasActiveFilters = classification || status || subreddit || destination || course || search

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl text-[--color-navy]">Leads</h1>
          <p className="mt-1 text-sm text-[--color-muted]">
            Prioritize conversations with genuine study-abroad intent · {total} total
          </p>
        </div>
        <div className="relative">
          <label htmlFor="lead-search" className="sr-only">
            Search lead titles
          </label>
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[--color-muted]" />
          <input
            id="lead-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles…"
            aria-label="Search lead titles"
            className="w-full rounded-[--radius-input] border border-[--color-border] bg-[--color-surface] py-2 pl-9 pr-3 text-sm outline-none focus:border-[--color-royal] sm:w-64"
          />
        </div>
      </div>

      {/* Toolbar */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-2">
          {['', 'HOT', 'WARM', 'COLD'].map((c) => (
            <button
              key={c || 'all'}
              onClick={() => setFilter('classification', c)}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
                classification === c
                  ? 'bg-[--color-navy] text-white'
                  : 'border border-[--color-border] bg-[--color-surface] text-[--color-text-soft] hover:bg-[--color-bg]'
              }`}
            >
              {c || 'All priority'}
            </button>
          ))}
        </div>

        <div className="ml-0 flex flex-wrap gap-2 sm:ml-auto">
          <FilterSelect label="All statuses" value={status} onChange={(v) => setFilter('status', v)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace('_', ' ')}</option>
            ))}
          </FilterSelect>

          <FilterSelect label="All subreddits" value={subreddit} onChange={(v) => setFilter('subreddit', v)}>
            {subreddits.map((s) => <option key={s} value={s}>r/{s}</option>)}
          </FilterSelect>

          <FilterSelect label="All destinations" value={destination} onChange={(v) => setFilter('destination', v)}>
            {destinations.map((d) => <option key={d} value={d}>{d}</option>)}
          </FilterSelect>

          <FilterSelect label="All courses" value={course} onChange={(v) => setFilter('course', v)}>
            {courses.map((c) => <option key={c} value={c}>{c}</option>)}
          </FilterSelect>

          <div className="relative">
            <ArrowUpDown size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[--color-muted]" />
            <label className="sr-only" htmlFor="sort-select">Sort leads</label>
            <select
              id="sort-select"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="rounded-[--radius-input] border border-[--color-border] bg-[--color-surface] py-1.5 pl-7 pr-3 text-[13px] text-[--color-text-soft] outline-none focus:border-[--color-royal]"
            >
              {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
        </div>
      )}

      {loading && <SkeletonRows rows={6} />}

      {!error && !loading && leads.length === 0 && (
        <EmptyState
          icon={<Inbox size={22} />}
          title={hasActiveFilters ? 'No leads match this view.' : 'No leads yet.'}
          description={
            hasActiveFilters
              ? 'Try a different filter, or run a Reddit scan to discover new study-abroad conversations.'
              : 'Your FutureGrad intelligence workspace is ready. Run a Reddit scan to discover relevant study-abroad conversations.'
          }
        />
      )}

      {!loading && leads.length > 0 && (
        <>
          <div className="fg-card overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr className="border-b border-[--color-border] text-[11.5px] text-[--color-muted]">
                  <th className="px-5 py-3 font-medium">Score</th>
                  <th className="px-5 py-3 font-medium">Lead</th>
                  <th className="px-5 py-3 font-medium">Intent</th>
                  <th className="px-5 py-3 font-medium">Destination</th>
                  <th className="px-5 py-3 font-medium">Course</th>
                  <th className="px-5 py-3 font-medium">Service</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[--color-border]">
                {sortedLeads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => setPreviewLead(lead)}
                    className="cursor-pointer transition-colors hover:bg-[--color-bg]"
                  >
                    <td className="px-5 py-3.5">
                      <PriorityBadge classification={lead.lead_classification} score={lead.lead_score} size="sm" />
                    </td>
                    <td className="max-w-xs px-5 py-3.5">
                      <Link
                        to={`/leads/${lead.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="line-clamp-1 text-[--color-text] hover:text-[--color-royal] hover:underline"
                      >
                        {lead.title}
                      </Link>
                      <div className="text-[11.5px] text-[--color-muted]">u/{lead.username}</div>
                    </td>
                    <td className="px-5 py-3.5 capitalize text-[--color-text-soft]">{lead.intent ?? '—'}</td>
                    <td className="px-5 py-3.5 text-[--color-text-soft]">{lead.destination ?? '—'}</td>
                    <td className="px-5 py-3.5 text-[--color-text-soft]">{lead.course ?? '—'}</td>
                    <td className="max-w-[160px] px-5 py-3.5 text-[--color-text-soft]">
                      {lead.service_needed.length ? lead.service_needed.join(', ') : '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="rounded-md bg-[--color-bg] px-2 py-0.5 text-[11.5px] font-medium text-[--color-text-soft]">
                        {lead.lead_status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[--color-muted]">
                      r/{lead.subreddit}
                      <div className="text-[11.5px]">{timeAgo(lead.processed_at)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-[--color-text-soft]">
              <span>Page {page + 1} of {totalPages}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  aria-label="Previous page"
                  className="flex items-center gap-1 rounded-lg border border-[--color-border] bg-[--color-surface] px-3 py-1.5 disabled:opacity-40"
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  aria-label="Next page"
                  className="flex items-center gap-1 rounded-lg border border-[--color-border] bg-[--color-surface] px-3 py-1.5 disabled:opacity-40"
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <LeadDrawer lead={previewLead} onClose={() => setPreviewLead(null)} />
    </div>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  children: React.ReactNode
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-[--radius-input] border border-[--color-border] bg-[--color-surface] px-3 py-1.5 text-[13px] text-[--color-text-soft] outline-none focus:border-[--color-royal]"
    >
      <option value="">{label}</option>
      {children}
    </select>
  )
}
