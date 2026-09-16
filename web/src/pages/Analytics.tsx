import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts'
import { api } from '../lib/api'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonCards } from '../components/Skeleton'
import { useApiData } from '../hooks/useApiData'
import { BarChart3 } from 'lucide-react'

const PRIORITY_COLORS: Record<string, string> = {
  HOT: '#e11d48',
  WARM: '#d97706',
  COLD: '#3b82f6',
}

function toChartData(record: Record<string, number>) {
  return Object.entries(record)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }))
}

function ChartCard({ title, record }: { title: string; record: Record<string, number> }) {
  const data = toChartData(record)
  return (
    <div className="fg-card p-5">
      <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">{title.toUpperCase()}</div>
      {data.length === 0 ? (
        <div className="flex h-[180px] items-center justify-center text-[13px] text-[--color-muted]">
          Not enough historical data yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 12.5 }} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#2547d0" maxBarSize={16} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export function Analytics() {
  const { data, loading, error, reload } = useApiData(() =>
    Promise.all([api.analytics(), api.leads({ limit: 200 })])
  )
  const analytics = data?.[0] ?? null
  const sample = data?.[1]?.items ?? []

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-navy]">Analytics</h1>
        <div className="mt-8"><ErrorState message={error} onRetry={reload} /></div>
      </div>
    )
  }

  if (loading || !analytics) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-navy]">Analytics</h1>
        <div className="mt-8"><SkeletonCards count={4} /></div>
      </div>
    )
  }

  if (analytics.total_leads === 0) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-navy]">Analytics</h1>
        <EmptyState
          icon={<BarChart3 size={22} />}
          title="Not enough historical data yet."
          description="Run a Reddit scan to start building lead intelligence analytics."
        />
      </div>
    )
  }

  const priorityData = Object.entries(analytics.priority_distribution).map(([name, value]) => ({ name, value }))
  const { hot = 0, warm = 0 } = analytics.priority_distribution
  const qualificationRate = analytics.total_leads > 0 ? Math.round(((hot + warm) / analytics.total_leads) * 100) : 0

  const scored = sample.filter((l) => l.lead_score != null)
  const avgScore = scored.length ? Math.round(scored.reduce((s, l) => s + (l.lead_score ?? 0), 0) / scored.length) : null

  const confident = sample.filter((l) => l.ai_confidence != null)
  const avgConfidence = confident.length
    ? Math.round((confident.reduce((s, l) => s + (l.ai_confidence ?? 0), 0) / confident.length) * 100)
    : null

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-navy]">Analytics</h1>
      <p className="mt-1 text-sm text-[--color-muted]">{analytics.total_leads} leads analyzed.</p>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Qualification Rate" value={`${qualificationRate}%`} />
        <Kpi label="Average Score" value={avgScore != null ? String(avgScore) : '—'} note={scored.length < analytics.total_leads ? `of ${scored.length} sampled` : undefined} />
        <Kpi label="Average Confidence" value={avgConfidence != null ? `${avgConfidence}%` : '—'} note={confident.length < analytics.total_leads ? `of ${confident.length} sampled` : undefined} />
        <Kpi label="Total Leads" value={String(analytics.total_leads)} />
      </div>

      <div className="mt-6 fg-card p-5">
        <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">PRIORITY DISTRIBUTION</div>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={priorityData} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 12.5, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 12.5 }} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={24}>
              {priorityData.map((entry) => (
                <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name] ?? '#64748b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ChartCard title="Pipeline conversion" record={analytics.pipeline_distribution} />
        <ChartCard title="Subreddit distribution" record={analytics.subreddit_distribution} />
        <ChartCard title="Destination distribution" record={analytics.destination_distribution} />
        <ChartCard title="Course distribution" record={analytics.course_distribution} />
        <ChartCard title="Service demand" record={analytics.service_demand} />
      </div>
    </div>
  )
}

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="fg-card p-4">
      <div className="font-mono-num text-[22px] font-semibold text-[--color-navy]">{value}</div>
      <div className="mt-0.5 text-[12px] text-[--color-muted]">{label}</div>
      {note && <div className="mt-0.5 text-[10.5px] text-[--color-muted]">({note})</div>}
    </div>
  )
}
