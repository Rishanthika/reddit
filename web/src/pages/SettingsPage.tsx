import { api } from '../lib/api'
import { ErrorState } from '../components/ErrorState'
import { useApiData } from '../hooks/useApiData'

function StatusRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-[--color-line] py-3.5 last:border-none">
      <span className="text-sm text-[--color-ink-soft]">{label}</span>
      <span className="flex items-center gap-1.5 text-sm font-medium text-[--color-ink]">
        {ok !== undefined && (
          <span className={`h-1.5 w-1.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-[--color-hot]'}`} />
        )}
        {value}
      </span>
    </div>
  )
}

export function SettingsPage() {
  const { data: settings, error, reload } = useApiData(() => api.settings())

  return (
    <div className="mx-auto max-w-xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <h1 className="font-display text-3xl text-[--color-ink]">Settings</h1>
      <p className="mt-1 text-sm text-[--color-ink-faint]">System status for this local FutureGrad workspace.</p>

      {error && (
        <div className="mt-8">
          <ErrorState message={error} onRetry={reload} />
        </div>
      )}

      {!error && (
        <>
          <div className="mt-8 rounded-xl border border-[--color-line] bg-[--color-paper-raised] px-5">
            <StatusRow
              label="Reddit connector"
              value={settings?.reddit_connector === 'connected' ? 'Connected' : 'Disconnected'}
              ok={settings?.reddit_connector === 'connected'}
            />
            <StatusRow label="AI provider" value={settings?.ai_provider ?? '—'} />
            <StatusRow label="Database" value="Connected" ok />
            <StatusRow label="Environment" value="Local" />
            <StatusRow label="Configured subreddits" value={(settings?.subreddits ?? []).join(', ') || '—'} />
            <StatusRow label="Post limit" value={String(settings?.post_limit ?? '—')} />
            <StatusRow label="Validation limit" value={String(settings?.classifier_validation_limit ?? '—')} />
          </div>

          <p className="mt-4 text-[12.5px] text-[--color-ink-faint]">
            API tokens and keys are read from your local{' '}
            <code className="rounded bg-[--color-paper-raised] px-1 py-0.5">.env</code> file and are
            never sent to this dashboard.
          </p>
        </>
      )}
    </div>
  )
}
