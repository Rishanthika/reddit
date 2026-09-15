import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { PipelineResponse } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { useApiData } from '../hooks/useApiData'
import { KanbanSquare } from 'lucide-react'

const PRIMARY = ['NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED']
const SECONDARY = ['NO_RESPONSE', 'NOT_QUALIFIED', 'CLOSED']

export function Pipeline() {
  const { data, loading, error, reload } = useApiData(() => api.pipeline())

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-ink]">Pipeline</h1>
        <div className="mt-8">
          <ErrorState message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (loading || !data) return null

  const totalLeads = Object.values(data.board).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-ink]">Pipeline</h1>
      <p className="mt-1 text-sm text-[--color-ink-faint]">Move leads through the counsellor workflow.</p>

      {totalLeads === 0 ? (
        <EmptyState
          icon={<KanbanSquare size={22} />}
          title="Nothing in the pipeline yet."
          description="Leads appear here automatically once a Reddit scan discovers them."
        />
      ) : (
        <>
          <div className="mt-8 grid grid-cols-6 gap-3 overflow-x-auto pb-2" style={{ gridAutoColumns: 'minmax(180px, 1fr)', gridAutoFlow: 'column' }}>
            {PRIMARY.map((status) => (
              <Column key={status} status={status} cards={data.board[status] ?? []} />
            ))}
          </div>

          <div className="mt-6 border-t border-[--color-line] pt-6">
            <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">
              SECONDARY STATUS
            </div>
            <div className="grid grid-cols-3 gap-3 overflow-x-auto pb-2" style={{ gridAutoColumns: 'minmax(160px, 1fr)', gridAutoFlow: 'column' }}>
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

function Column({
  status,
  cards,
  compact,
}: {
  status: string
  cards: PipelineResponse['board'][string]
  compact?: boolean
}) {
  return (
    <div className="min-w-[180px] rounded-xl border border-[--color-line] bg-[--color-paper-raised]">
      <div className="flex items-center justify-between border-b border-[--color-line] px-3 py-2.5">
        <span className="text-[11.5px] font-semibold tracking-wide text-[--color-ink-soft]">
          {status.replace('_', ' ')}
        </span>
        <span className="rounded-full bg-[--color-paper] px-1.5 text-[11px] text-[--color-ink-faint]">
          {cards.length}
        </span>
      </div>
      <div className={`space-y-2 p-2 ${compact ? '' : 'min-h-[200px]'}`}>
        {cards.map((card) => (
          <Link
            key={card.id}
            to={`/leads/${card.id}`}
            className="block rounded-lg border border-[--color-line] bg-[--color-paper] p-2.5 transition-colors hover:border-[--color-gold]"
          >
            <PriorityBadge classification={card.lead_classification} score={card.lead_score} size="sm" />
            <div className="mt-1.5 line-clamp-2 text-[12.5px] leading-snug text-[--color-ink]">{card.title}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
