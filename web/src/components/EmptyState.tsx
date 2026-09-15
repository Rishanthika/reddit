import type { ReactNode } from 'react'

interface Props {
  title: string
  description: string
  action?: ReactNode
  icon?: ReactNode
}

export function EmptyState({ title, description, action, icon }: Props) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-24 px-6">
      {icon && (
        <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-[--color-gold-soft] text-[--color-gold]">
          {icon}
        </div>
      )}
      <h3 className="font-display text-2xl text-[--color-ink]">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-[--color-ink-soft]">
        {description}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
