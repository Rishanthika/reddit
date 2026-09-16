import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity as ActivityIcon, RadarIcon, ShieldCheck, StickyNote, ArrowRightLeft, Search } from 'lucide-react'
import { api } from '../lib/api'
import type { ActivityItem } from '../lib/types'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'
import { useApiData } from '../hooks/useApiData'

const ICONS: Record<string, typeof RadarIcon> = {
  scan_completed: RadarIcon,
  scan_failed: RadarIcon,
  validation_completed: ShieldCheck,
  note_added: StickyNote,
  status_changed: ArrowRightLeft,
}

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function groupLabel(iso: string): 'Today' | 'Yesterday' | 'Earlier' {
  const date = new Date(iso)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfYesterday = new Date(startOfToday.getTime() - 86400000)
  if (date >= startOfToday) return 'Today'
  if (date >= startOfYesterday) return 'Yesterday'
  return 'Earlier'
}

function Row({ item }: { item: ActivityItem }) {
  const Icon = ICONS[item.event_type] ?? ActivityIcon
  const content = (
    <div className="flex items-start gap-3 rounded-lg px-3 py-3 transition-colors hover:bg-[--color-bg]">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[--color-gold-soft] text-[--color-navy]">
        <Icon size={13} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] text-[--color-text]">{item.message}</div>
        <div className="mt-0.5 text-[11.5px] text-[--color-muted]">{timeAgo(item.created_at)}</div>
      </div>
    </div>
  )
  return item.lead_id ? <Link to={`/leads/${item.lead_id}`}>{content}</Link> : <div>{content}</div>
}

export function ActivityPage() {
  const { data: items, loading, error, reload } = useApiData(() => api.activity(150))
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!items) return []
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter((i) => i.message.toLowerCase().includes(q))
  }, [items, search])

  const groups = useMemo(() => {
    const buckets: Record<string, ActivityItem[]> = { Today: [], Yesterday: [], Earlier: [] }
    for (const item of filtered) {
      buckets[groupLabel(item.created_at)].push(item)
    }
    return buckets
  }, [filtered])

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl text-[--color-navy]">Activity</h1>
          <p className="mt-1 text-sm text-[--color-muted]">A live record of scans, validations, and pipeline changes.</p>
        </div>
        {items && items.length > 0 && (
          <div className="relative">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[--color-muted]" />
            <label htmlFor="activity-search" className="sr-only">Search activity</label>
            <input
              id="activity-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search activity…"
              className="w-full rounded-[--radius-input] border border-[--color-border] bg-[--color-surface] py-2 pl-8 pr-3 text-[13px] outline-none focus:border-[--color-royal] sm:w-56"
            />
          </div>
        )}
      </div>

      {error && <div className="mt-8"><ErrorState message={error} onRetry={reload} /></div>}
      {loading && <div className="mt-8"><SkeletonRows rows={6} /></div>}

      {!error && !loading && items && items.length === 0 && (
        <EmptyState
          icon={<ActivityIcon size={22} />}
          title="No activity yet."
          description="Activity appears here as soon as you run a scan, validate the classifier, or move a lead through the pipeline."
        />
      )}

      {!error && !loading && items && items.length > 0 && (
        <div className="mt-8 space-y-6">
          {(['Today', 'Yesterday', 'Earlier'] as const).map((label) =>
            groups[label].length > 0 ? (
              <div key={label}>
                <div className="mb-1.5 px-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">{label.toUpperCase()}</div>
                <div className="space-y-0.5">
                  {groups[label].map((item) => <Row key={item.id} item={item} />)}
                </div>
              </div>
            ) : null
          )}
          {filtered.length === 0 && (
            <p className="px-3 text-[13px] text-[--color-muted]">No activity matches "{search}".</p>
          )}
        </div>
      )}
    </div>
  )
}
