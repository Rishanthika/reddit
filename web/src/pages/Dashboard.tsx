import { Link } from 'react-router-dom'
import { RadarIcon, Flame, Layers, Snowflake, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { PriorityBadge } from '../components/PriorityBadge'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { useApiData } from '../hooks/useApiData'

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function Dashboard() {
  const { data, loading, error, reload } = useApiData(() =>
    Promise.all([api.dashboard(), api.leads({ classification: 'HOT', limit: 5 })])
  )
  const stats = data?.[0] ?? null
  const hotLeads = data?.[1].items ?? []

  const kpis = stats
    ? [
        { label: 'Total Leads', value: stats.total_leads, icon: Layers, color: 'text-[--color-royal]', bg: 'bg-[--color-royal-soft]' },
        { label: 'HOT', value: stats.hot, icon: Flame, color: 'text-[--color-hot]', bg: 'bg-[--color-hot-soft]' },
        { label: 'WARM', value: stats.warm, icon: Sparkles, color: 'text-[--color-warm]', bg: 'bg-[--color-warm-soft]' },
        { label: 'COLD', value: stats.cold, icon: Snowflake, color: 'text-[--color-cold]', bg: 'bg-[--color-cold-soft]' },
        { label: 'New Today', value: stats.new_today, icon: RadarIcon, color: 'text-[--color-teal]', bg: 'bg-[--color-teal-soft]' },
      ]
    : []

  return (
    <div>
      {/* Hero — the visual centerpiece, per the brief */}
      <div className="fg-gradient relative overflow-hidden px-4 py-10 sm:px-6 lg:px-10 lg:py-14">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, var(--color-electric) 0%, transparent 70%)' }}
        />
        <div className="relative mx-auto max-w-6xl">
          <div className="mb-1 text-sm text-white/60">{greeting()}</div>
          <h1 className="font-display text-[40px] leading-[1.05] text-white sm:text-[44px]">
            Lead Intelligence
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-white/75">
            Find the study-abroad conversations that actually need FutureGrad.
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link
              to="/scan"
              className="inline-flex items-center gap-2 rounded-lg bg-[--color-gold] px-4 py-2.5 text-sm font-semibold text-[--color-navy] shadow-[0_4px_14px_-2px_rgba(201,154,46,0.5)] transition-transform hover:-translate-y-px"
            >
              <RadarIcon size={16} />
              Scan Reddit
            </Link>
            <Link
              to="/leads?classification=HOT"
              className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-medium text-white backdrop-blur-sm transition-colors hover:bg-white/15"
            >
              <Flame size={16} />
              View HOT Leads
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
        {error && <ErrorState message={error} onRetry={reload} />}

        {!error && !loading && stats && (
          <div className="-mt-16 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {kpis.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-[--color-line] bg-[--color-paper-raised] p-5 shadow-[0_8px_24px_-12px_rgba(16,26,51,0.18)]"
              >
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${s.bg}`}>
                  <s.icon size={15} className={s.color} />
                </div>
                <div className="mt-3 font-mono-num text-[28px] font-medium text-[--color-navy]">{s.value}</div>
                <div className="mt-0.5 text-[12.5px] text-[--color-ink-faint]">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-12">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-xl text-[--color-navy]">Latest HOT leads</h2>
            <Link to="/leads" className="text-sm text-[--color-ink-soft] hover:text-[--color-royal]">
              View all leads →
            </Link>
          </div>

          {!error && !loading && hotLeads.length === 0 && (
            <EmptyState
              icon={<RadarIcon size={22} />}
              title="No leads yet."
              description="Your FutureGrad intelligence workspace is ready. Run a Reddit scan to discover relevant study-abroad conversations."
              action={
                <Link
                  to="/scan"
                  className="inline-flex items-center gap-2 rounded-lg bg-[--color-royal] px-4 py-2.5 text-sm font-medium text-white hover:bg-[--color-royal]/90"
                >
                  Scan Reddit
                </Link>
              }
            />
          )}

          {!error && hotLeads.length > 0 && (
            <div className="divide-y divide-[--color-line] rounded-xl border border-[--color-line] bg-[--color-paper-raised]">
              {hotLeads.map((lead) => (
                <Link
                  key={lead.id}
                  to={`/leads/${lead.id}`}
                  className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-[--color-paper]"
                >
                  <PriorityBadge classification={lead.lead_classification} score={lead.lead_score} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] text-[--color-ink]">{lead.title}</div>
                    <div className="mt-0.5 text-[12px] text-[--color-ink-faint]">
                      r/{lead.subreddit}
                      {lead.destination ? ` · ${lead.destination}` : ''}
                      {lead.course ? ` · ${lead.course}` : ''}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
