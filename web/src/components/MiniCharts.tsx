interface Segment {
  label: string
  value: number
  color: string
}

interface Props {
  segments: Segment[]
  size?: number
  thickness?: number
}

export function MiniDonut({ segments, size = 96, thickness = 14 }: Props) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Priority distribution">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--color-border)"
        strokeWidth={thickness}
      />
      {total > 0 &&
        segments.map((seg) => {
          const fraction = seg.value / total
          const dash = fraction * circumference
          const circle = (
            <circle
              key={seg.label}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              strokeLinecap={dash > 0 && dash < circumference ? 'butt' : undefined}
            />
          )
          offset += dash
          return circle
        })}
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        className="font-mono-num"
        fontSize={size * 0.22}
        fontWeight={600}
        fill="var(--color-text)"
      >
        {total}
      </text>
    </svg>
  )
}

export function MiniBarList({
  items,
  color = 'var(--color-royal)',
}: {
  items: { label: string; value: number }[]
  color?: string
}) {
  const max = Math.max(1, ...items.map((i) => i.value))
  return (
    <div className="space-y-2.5">
      {items.map((item) => (
        <div key={item.label}>
          <div className="mb-1 flex items-center justify-between text-[12.5px]">
            <span className="truncate text-[--color-text-soft]">{item.label}</span>
            <span className="font-mono-num shrink-0 pl-2 text-[--color-text]">{item.value}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[--color-bg]">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${(item.value / max) * 100}%`, background: color }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
