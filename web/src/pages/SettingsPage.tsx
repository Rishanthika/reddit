import { Radio, Database, Sparkles, Globe, Hash, Tag } from 'lucide-react'
import { api } from '../lib/api'
import { ErrorState } from '../components/ErrorState'
import { SkeletonCards } from '../components/Skeleton'
import { useApiData } from '../hooks/useApiData'

function StatusCard({
  icon: Icon,
  label,
  value,
  ok,
}: {
  icon: typeof Radio
  label: string
  value: string
  ok?: boolean
}) {
  return (
    <div className="fg-card p-5">
      <div className="flex items-center justify-between">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-royal-soft] text-[--color-royal]">
          <Icon size={15} />
        </div>
        {ok !== undefined && (
          <span className={`h-2 w-2 rounded-full ${ok ? 'bg-[--color-emerald]' : 'bg-[--color-hot]'}`} />
        )}
      </div>
      <div className="mt-3 text-[13.5px] font-medium text-[--color-navy]">{value}</div>
      <div className="mt-0.5 text-[12px] text-[--color-muted]">{label}</div>
    </div>
  )
}

export function SettingsPage() {
  const { data: settings, error, reload } = useApiData(() => api.settings())

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-navy]">Settings</h1>
      <p className="mt-1 text-sm text-[--color-muted]">System health and connection diagnostics for this FutureGrad workspace.</p>

      {error && <div className="mt-8"><ErrorState message={error} onRetry={reload} /></div>}
      {!error && !settings && <div className="mt-8"><SkeletonCards count={6} /></div>}

      {!error && settings && (
        <>
          <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatusCard
              icon={Radio}
              label="Reddit Connector"
              value={settings.reddit_connector === 'connected' ? 'Connected' : 'Disconnected'}
              ok={settings.reddit_connector === 'connected'}
            />
            <StatusCard icon={Database} label="Database" value="Connected" ok />
            <StatusCard icon={Sparkles} label="AI Provider" value={settings.ai_provider ?? '—'} />
            <StatusCard icon={Globe} label="Environment" value={settings.environment ?? '—'} />
            <StatusCard icon={Hash} label="Post Limit" value={String(settings.post_limit ?? '—')} />
            <StatusCard icon={Tag} label="Validation Limit" value={String(settings.classifier_validation_limit ?? '—')} />
          </div>

          <div className="fg-card mt-4 p-5">
            <div className="mb-2 text-[11px] font-semibold tracking-wider text-[--color-muted]">REDDIT COMMUNITIES</div>
            <div className="flex flex-wrap gap-1.5">
              {(settings.subreddits ?? []).map((s) => (
                <span key={s} className="rounded-md bg-[--color-royal-soft] px-2 py-0.5 text-[12px] font-medium text-[--color-royal]">
                  r/{s}
                </span>
              ))}
              {(!settings.subreddits || settings.subreddits.length === 0) && (
                <span className="text-[13px] text-[--color-muted]">—</span>
              )}
            </div>
          </div>

          <p className="mt-4 text-[12.5px] text-[--color-muted]">
            API tokens and keys are read only by the backend from its environment configuration and are never sent to this dashboard.
          </p>
        </>
      )}
    </div>
  )
}
