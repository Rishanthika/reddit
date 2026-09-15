import { AlertTriangle } from 'lucide-react'

interface Props {
  message?: string | null
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-[--color-hot]/25 bg-[--color-hot-soft] px-8 py-12 text-center">
      <AlertTriangle size={22} className="text-[--color-hot]" />
      <h3 className="mt-3 font-display text-lg text-[--color-ink]">Couldn't load this page.</h3>
      <p className="mt-1.5 max-w-sm text-sm text-[--color-ink-soft]">
        {message || "The backend isn't responding. Make sure it's running on port 8000."}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-[--color-ink] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[--color-ink]/90"
        >
          Try again
        </button>
      )}
    </div>
  )
}
