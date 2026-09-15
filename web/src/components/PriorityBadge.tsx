import clsx from 'clsx'

interface Props {
  classification: string | null
  score?: number | null
  size?: 'sm' | 'md' | 'lg'
}

const STYLES: Record<string, string> = {
  HOT: 'bg-[--color-hot-soft] text-[--color-hot] ring-1 ring-[--color-hot]/20',
  WARM: 'bg-[--color-warm-soft] text-[--color-warm] ring-1 ring-[--color-warm]/20',
  COLD: 'bg-[--color-cold-soft] text-[--color-cold] ring-1 ring-[--color-cold]/15',
}

export function PriorityBadge({ classification, score, size = 'md' }: Props) {
  const cls = classification ? STYLES[classification] ?? STYLES.COLD : STYLES.COLD
  const isHot = classification === 'HOT'

  const pad = size === 'sm' ? 'px-2 py-0.5 text-[11px] gap-1' : size === 'lg' ? 'px-3.5 py-1.5 text-sm gap-2' : 'px-2.5 py-1 text-xs gap-1.5'

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full font-semibold tracking-wide',
        cls,
        pad,
        isHot && 'shadow-[0_0_0_1px_rgba(184,64,42,0.08),0_2px_10px_-2px_rgba(184,64,42,0.35)]'
      )}
    >
      {typeof score === 'number' && (
        <span className="font-mono-num tabular-nums">{score}</span>
      )}
      <span>{classification ?? 'COLD'}</span>
    </span>
  )
}
