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
import { useApiData } from '../hooks/useApiData'
import { BarChart3 } from 'lucide-react'

const PRIORITY_COLORS: Record<string, string> = {
  HOT: '#b8402a',
  WARM: '#c9822e',
  COLD: '#64748b',
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
    <div className="rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-5">
      <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">{title.toUpperCase()}</div>
      {data.length === 0 ? (
        <div className="flex h-[180px] items-center justify-center text-[13px] text-[--color-ink-faint]">
          Not enough historical data yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e4e1d8" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              width={110}
              tick={{ fontSize: 12, fill: '#4a5578' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: '#f6f5f1' }}
              contentStyle={{ borderRadius: 8, border: '1px solid #e4e1d8', fontSize: 12.5 }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#14213d" maxBarSize={16} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export function Analytics() {
  const { data, loading, error, reload } = useApiData(() => api.analytics())

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-ink]">Analytics</h1>
        <div className="mt-8">
          <ErrorState message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (loading || !data) return null

  if (data.total_leads === 0) {
    return (
      <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <h1 className="font-display text-3xl text-[--color-ink]">Analytics</h1>
        <EmptyState
          icon={<BarChart3 size={22} />}
          title="Not enough historical data yet."
          description="Run a Reddit scan to start building lead intelligence analytics."
        />
      </div>
    )
  }

  const priorityData = Object.entries(data.priority_distribution).map(([name, value]) => ({
    name,
    value,
  }))

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-ink]">Analytics</h1>
      <p className="mt-1 text-sm text-[--color-ink-faint]">{data.total_leads} leads analyzed.</p>

      <div className="mt-8 rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-5">
        <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">
          PRIORITY DISTRIBUTION
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={priorityData} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e4e1d8" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 12.5, fill: '#4a5578' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #e4e1d8', fontSize: 12.5 }} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={24}>
              {priorityData.map((entry) => (
                <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name] ?? '#64748b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4">
        <ChartCard title="Pipeline conversion" record={data.pipeline_distribution} />
        <ChartCard title="Subreddit distribution" record={data.subreddit_distribution} />
        <ChartCard title="Destination distribution" record={data.destination_distribution} />
        <ChartCard title="Course distribution" record={data.course_distribution} />
        <ChartCard title="Service demand" record={data.service_demand} />
      </div>
    </div>
  )
}
