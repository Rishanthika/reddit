interface Props {
  value: number // 0-100
  size?: number
  thickness?: number
  color: string
  label?: string
}

export function ScoreRing({ value, size = 76, thickness = 7, color, label }: Props) {
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  const dash = (Math.max(0, Math.min(100, value)) / 100) * circumference

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-border)" strokeWidth={thickness} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeDasharray={`${dash} ${circumference - dash}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="font-mono-num text-[18px] font-semibold text-[--color-navy]">{Math.round(value)}</span>
        {label && <span className="text-[9px] text-[--color-muted]">{label}</span>}
      </div>
    </div>
  )
}
