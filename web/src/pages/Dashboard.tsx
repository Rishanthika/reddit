import { Link } from 'react-router-dom'
import { RadarIcon, Flame, Layers, Snowflake, Sparkles, ArrowRight, Clock } from 'lucide-react'
import { api } from '../lib/api'
import { PriorityBadge } from '../components/PriorityBadge'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonCards, SkeletonRows } from '../components/Skeleton'
import { MiniDonut, MiniBarList } from '../components/MiniCharts'
import { useApiData } from '../hooks/useApiData'

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function timeAgo(iso: string | null) {
  if (!iso) return '—'
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

const PIPELINE_ORDER = ['NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED']

export function Dashboard() {
  const { data, loading, error, reload } = useApiData(() =>
    Promise.all([
      api.dashboard(),
      api.leads({ classification: 'HOT', limit: 6 }),
      api.analytics(),
      api.activity(6),
      api.recentScans(1),
    ])
  )
  const stats = data?.[0] ?? null
  const hotLeads = data?.[1].items ?? []
  const analytics = data?.[2] ?? null
  const recentActivity = data?.[3] ?? []
  const lastScan = data?.[4]?.[0] ?? null

  const kpis = stats
    ? [
        { label: 'Total Leads', value: stats.total_leads, icon: Layers, color: 'text-[--color-royal]', bg: 'bg-[--color-royal-soft]' },
        { label: 'HOT', value: stats.hot, icon: Flame, color: 'text-[--color-hot]', bg: 'bg-[--color-hot-soft]' },
        { label: 'WARM', value: stats.warm, icon: Sparkles, color: 'text-[--color-warm]', bg: 'bg-[--color-warm-soft]' },
        { label: 'COLD', value: stats.cold, icon: Snowflake, color: 'text-[--color-cold]', bg: 'bg-[--color-cold-soft]' },
        { label: 'New Today', value: stats.new_today, icon: RadarIcon, color: 'text-[--color-teal]', bg: 'bg-[--color-teal-soft]' },
      ]
    : []

  const qualifiedRate =
    stats && stats.total_leads > 0 ? Math.round(((stats.hot + stats.warm) / stats.total_leads) * 100) : null

  return (
    <div>
      <div className="fg-gradient relative overflow-hidden px-4 py-10 sm:px-6 lg:px-10 lg:py-14">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, var(--color-electric) 0%, transparent 70%)' }}
        />
        <div className="relative mx-auto max-w-7xl">
          <div className="mb-1 text-sm text-white/60">{greeting()}</div>
          <h1 className="font-display text-[36px] leading-[1.05] text-white sm:text-[40px]">
            FutureGrad Lead Intelligence
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-white/75">
            Monitor intent. Prioritize prospects. Convert students.
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link
              to="/scan"
              className="inline-flex items-center gap-2 rounded-lg bg-[--color-gold] px-4 py-2.5 text-sm font-semibold text-[--color-navy] shadow-[0_4px_14px_-2px_rgba(212,160,23,0.5)] transition-transform hover:-translate-y-px"
            >
              <RadarIcon size={16} />
              Scan Reddit
            </Link>
            <Link
              to="/leads?classification=HOT"
              className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-medium text-white backdrop-blur-sm transition-colors hover:bg-white/15"
            >
              <Flame size={16} />
              View Hot Leads
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
        {error && <ErrorState message={error} onRetry={reload} />}

        {loading && <SkeletonCards count={5} />}

        {!error && !loading && stats && (
          <div className="-mt-16 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {kpis.map((s) => (
              <div key={s.label} className="fg-card fg-card-hover p-5 shadow-[0_8px_24px_-12px_rgba(7,24,39,0.18)]">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${s.bg}`}>
                  <s.icon size={15} className={s.color} />
                </div>
                <div className="mt-3 font-mono-num text-[28px] font-medium text-[--color-navy]">{s.value}</div>
                <div className="mt-0.5 text-[12.5px] text-[--color-muted]">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {!error && !loading && (
          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left / main column */}
            <div className="lg:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-display text-xl text-[--color-navy]">Priority Queue</h2>
                <Link to="/leads" className="flex items-center gap-1 text-sm text-[--color-text-soft] hover:text-[--color-royal]">
                  View all leads <ArrowRight size={13} />
                </Link>
              </div>

              {hotLeads.length === 0 ? (
                <EmptyState
                  icon={<RadarIcon size={22} />}
                  title="No leads yet."
                  description="Your FutureGrad intelligence workspace is ready. Run a Reddit scan to discover relevant study-abroad conversations."
                  action={
                    <Link to="/scan" className="inline-flex items-center gap-2 rounded-lg bg-[--color-royal] px-4 py-2.5 text-sm font-medium text-white hover:bg-[--color-royal]/90">
                      Scan Reddit
                    </Link>
                  }
                />
              ) : (
                <div className="fg-card divide-y divide-[--color-border]">
                  {hotLeads.map((lead) => (
                    <Link
                      key={lead.id}
                      to={`/leads/${lead.id}`}
                      className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-[--color-bg]"
                    >
                      <PriorityBadge classification={lead.lead_classification} score={lead.lead_score} size="sm" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[14px] text-[--color-text]">{lead.title}</div>
                        <div className="mt-0.5 text-[12px] text-[--color-muted]">
                          r/{lead.subreddit}
                          {lead.destination ? ` · ${lead.destination}` : ''}
                          {lead.course ? ` · ${lead.course}` : ''}
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}

              {/* Pipeline funnel — real counts across the actual tracked
                  pipeline stages (NEW..CONVERTED). */}
              {analytics && (
                <div className="fg-card mt-6 p-5">
                  <h3 className="mb-4 font-display text-[15px] text-[--color-navy]">Lead Pipeline</h3>
                  <div className="flex flex-wrap items-stretch gap-2">
                    {PIPELINE_ORDER.map((stage, i) => {
                      const count = analytics.pipeline_distribution[stage] ?? 0
                      return (
                        <div key={stage} className="flex items-center gap-2">
                          <div className="rounded-lg border border-[--color-border] bg-[--color-bg] px-3 py-2 text-center">
                            <div className="font-mono-num text-[17px] font-semibold text-[--color-navy]">{count}</div>
                            <div className="text-[10.5px] text-[--color-muted]">{stage}</div>
                          </div>
                          {i < PIPELINE_ORDER.length - 1 && (
                            <ArrowRight size={13} className="shrink-0 text-[--color-muted]" />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Right column */}
            <div className="space-y-6">
              {stats && stats.total_leads > 0 && (
                <div className="fg-card p-5">
                  <h3 className="mb-4 font-display text-[15px] text-[--color-navy]">Priority Distribution</h3>
                  <div className="flex items-center gap-5">
                    <MiniDonut
                      segments={[
                        { label: 'HOT', value: stats.hot, color: 'var(--color-hot)' },
                        { label: 'WARM', value: stats.warm, color: 'var(--color-warm)' },
                        { label: 'COLD', value: stats.cold, color: 'var(--color-cold)' },
                      ]}
                    />
                    <div className="space-y-1.5 text-[12.5px]">
                      <Legend color="var(--color-hot)" label="Hot" value={stats.hot} />
                      <Legend color="var(--color-warm)" label="Warm" value={stats.warm} />
                      <Legend color="var(--color-cold)" label="Cold" value={stats.cold} />
                    </div>
                  </div>
                  {qualifiedRate !== null && (
                    <div className="mt-4 border-t border-[--color-border] pt-3 text-[12.5px] text-[--color-text-soft]">
                      Qualified rate (HOT+WARM):{' '}
                      <span className="font-mono-num font-semibold text-[--color-text]">{qualifiedRate}%</span>
                    </div>
                  )}
                </div>
              )}

              {analytics && Object.keys(analytics.subreddit_distribution).length > 0 && (
                <div className="fg-card p-5">
                  <h3 className="mb-4 font-display text-[15px] text-[--color-navy]">Lead Sources</h3>
                  <MiniBarList
                    items={Object.entries(analytics.subreddit_distribution)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 5)
                      .map(([label, value]) => ({ label: `r/${label}`, value }))}
                    color="var(--color-royal)"
                  />
                </div>
              )}

              <div className="fg-card p-5">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="font-display text-[15px] text-[--color-navy]">Live Activity</h3>
                  <Link to="/activity" className="text-[12px] text-[--color-text-soft] hover:text-[--color-royal]">
                    View all
                  </Link>
                </div>
                {recentActivity.length === 0 ? (
                  <p className="text-[13px] text-[--color-muted]">No activity recorded yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {recentActivity.map((a) => (
                      <li key={a.id} className="flex gap-2.5 text-[12.5px]">
                        <Clock size={13} className="mt-0.5 shrink-0 text-[--color-muted]" />
                        <div className="min-w-0">
                          <div className="text-[--color-text]">{a.message}</div>
                          <div className="text-[--color-muted]">{timeAgo(a.created_at)}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {lastScan && (
                <div className="fg-card p-5">
                  <h3 className="mb-3 font-display text-[15px] text-[--color-navy]">Recent Scan Summary</h3>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <ScanStat label="Retrieved" value={lastScan.discovered} />
                    <ScanStat label="HOT" value={lastScan.hot} accent="text-[--color-hot]" />
                    <ScanStat label="WARM" value={lastScan.warm} accent="text-[--color-warm]" />
                  </div>
                  <div className="mt-3 text-[11.5px] text-[--color-muted]">
                    {timeAgo(lastScan.finished_at ?? lastScan.started_at)} · {lastScan.status.toUpperCase()}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {loading && (
          <div className="mt-8">
            <SkeletonRows rows={5} />
          </div>
        )}
      </div>
    </div>
  )
}

function Legend({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      <span className="text-[--color-text-soft]">{label}</span>
      <span className="font-mono-num text-[--color-text]">{value}</span>
    </div>
  )
}

function ScanStat({ label, value, accent }: { label: string; value: number | null; accent?: string }) {
  return (
    <div>
      <div className={`font-mono-num text-[16px] font-semibold ${accent ?? 'text-[--color-navy]'}`}>{value ?? '—'}</div>
      <div className="text-[10.5px] text-[--color-muted]">{label}</div>
    </div>
  )
}
