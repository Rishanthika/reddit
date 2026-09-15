import { Link } from 'react-router-dom'
import { Activity as ActivityIcon, RadarIcon, ShieldCheck, StickyNote, ArrowRightLeft } from 'lucide-react'
import { api } from '../lib/api'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
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

export function ActivityPage() {
  const { data: items, loading, error, reload } = useApiData(() => api.activity(100))

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-ink]">Activity</h1>
      <p className="mt-1 text-sm text-[--color-ink-faint]">A live record of scans, validations, and pipeline changes.</p>

      {error ? (
        <div className="mt-8">
          <ErrorState message={error} onRetry={reload} />
        </div>
      ) : loading || !items ? null : items.length === 0 ? (
        <EmptyState
          icon={<ActivityIcon size={22} />}
          title="No activity yet."
          description="Activity appears here as soon as you run a scan, validate the classifier, or move a lead through the pipeline."
        />
      ) : (
        <div className="mt-8 space-y-0.5">
          {items.map((item) => {
            const Icon = ICONS[item.event_type] ?? ActivityIcon
            const content = (
              <div className="flex items-start gap-3 rounded-lg px-3 py-3 transition-colors hover:bg-[--color-paper-raised]">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[--color-gold-soft] text-[--color-ink]">
                  <Icon size={13} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[13.5px] text-[--color-ink]">{item.message}</div>
                  <div className="mt-0.5 text-[11.5px] text-[--color-ink-faint]">{timeAgo(item.created_at)}</div>
                </div>
              </div>
            )
            return item.lead_id ? (
              <Link key={item.id} to={`/leads/${item.lead_id}`}>
                {content}
              </Link>
            ) : (
              <div key={item.id}>{content}</div>
            )
          })}
        </div>
      )}
    </div>
  )
}
