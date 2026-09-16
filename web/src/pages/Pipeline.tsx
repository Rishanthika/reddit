import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { PipelineResponse } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonCards } from '../components/Skeleton'
import { useApiData } from '../hooks/useApiData'
import { KanbanSquare } from 'lucide-react'

const PRIMARY = ['NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED']
const SECONDARY = ['NO_RESPONSE', 'NOT_QUALIFIED', 'CLOSED']

const STRIPE: Record<string, string> = {
  HOT: 'var(--color-hot)',
  WARM: 'var(--color-warm)',
  COLD: 'var(--color-cold)',
}

export function Pipeline() {
  const { data, loading, error, reload } = useApiData(() => api.pipeline())

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-navy]">Pipeline</h1>
        <div className="mt-8"><ErrorState message={error} onRetry={reload} /></div>
      </div>
    )
  }

  if (loading || !data) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-navy]">Pipeline</h1>
        <div className="mt-8"><SkeletonCards count={6} /></div>
      </div>
    )
  }

  const totalLeads = Object.values(data.board).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-navy]">Pipeline</h1>
      <p className="mt-1 text-sm text-[--color-muted]">Move leads through the counsellor workflow.</p>

      {totalLeads === 0 ? (
        <EmptyState
          icon={<KanbanSquare size={22} />}
          title="Nothing in the pipeline yet."
          description="Leads appear here automatically once a Reddit scan discovers them."
        />
      ) : (
        <>
          <div className="mt-8 grid grid-cols-6 gap-3 overflow-x-auto pb-2" style={{ gridAutoColumns: 'minmax(190px, 1fr)', gridAutoFlow: 'column' }}>
            {PRIMARY.map((status) => (
              <Column key={status} status={status} cards={data.board[status] ?? []} />
            ))}
          </div>

          <div className="mt-6 border-t border-[--color-border] pt-6">
            <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">SECONDARY STATUS</div>
            <div className="grid grid-cols-3 gap-3 overflow-x-auto pb-2" style={{ gridAutoColumns: 'minmax(170px, 1fr)', gridAutoFlow: 'column' }}>
              {SECONDARY.map((status) => (
                <Column key={status} status={status} cards={data.board[status] ?? []} compact />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function Column({ status, cards, compact }: { status: string; cards: PipelineResponse['board'][string]; compact?: boolean }) {
  return (
    <div className="min-w-[190px] rounded-2xl border border-[--color-border] bg-[--color-bg]">
      <div className="sticky top-0 flex items-center justify-between rounded-t-2xl border-b border-[--color-border] bg-[--color-surface] px-3 py-2.5">
        <span className="text-[11.5px] font-semibold tracking-wide text-[--color-text-soft]">{status.replace('_', ' ')}</span>
        <span className="rounded-full bg-[--color-bg] px-1.5 text-[11px] text-[--color-muted]">{cards.length}</span>
      </div>
      <div className={`space-y-2 p-2 ${compact ? '' : 'min-h-[220px]'}`}>
        {cards.map((card) => (
          <Link
            key={card.id}
            to={`/leads/${card.id}`}
            className="fg-card-hover relative block overflow-hidden rounded-xl border border-[--color-border] bg-[--color-surface] p-2.5 pl-3.5"
          >
            <span
              className="absolute left-0 top-0 h-full w-1"
              style={{ background: STRIPE[card.lead_classification ?? ''] ?? 'var(--color-muted)' }}
            />
            <PriorityBadge classification={card.lead_classification} score={card.lead_score} size="sm" />
            <div className="mt-1.5 line-clamp-2 text-[12.5px] leading-snug text-[--color-text]">{card.title}</div>
            {(card.destination || card.course) && (
              <div className="mt-1 truncate text-[11px] text-[--color-muted]">
                {[card.destination, card.course].filter(Boolean).join(' · ')}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  )
}
