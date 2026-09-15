import { NavLink } from 'react-router-dom'
import clsx from 'clsx'
import {
  LayoutDashboard,
  Flame,
  KanbanSquare,
  BarChart3,
  RadarIcon,
  ShieldCheck,
  Activity as ActivityIcon,
  Settings as SettingsIcon,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard }],
  },
  {
    label: 'Lead Intelligence',
    items: [
      { to: '/leads', label: 'Leads', icon: Flame },
      { to: '/pipeline', label: 'Pipeline', icon: KanbanSquare },
      { to: '/analytics', label: 'Analytics', icon: BarChart3 },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/scan', label: 'Scan Reddit', icon: RadarIcon },
      { to: '/validation', label: 'Validation', icon: ShieldCheck },
      { to: '/activity', label: 'Activity', icon: ActivityIcon },
    ],
  },
  {
    label: 'System',
    items: [{ to: '/settings', label: 'Settings', icon: SettingsIcon }],
  },
]

interface Props {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  const [dbOk, setDbOk] = useState<boolean | null>(null)

  useEffect(() => {
    api
      .health()
      .then(() => setDbOk(true))
      .catch(() => setDbOk(false))
  }, [])

  return (
    <>
      {/* Mobile backdrop — only rendered (and only intercepts clicks) while open */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-[--color-navy]/40 backdrop-blur-[1px] lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 flex h-screen w-64 shrink-0 flex-col border-r border-[--color-line] bg-[--color-paper-raised] transition-transform duration-200 lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between px-5 pt-6 pb-5">
          <div className="flex items-center gap-2.5">
            <div className="fg-gradient flex h-8 w-8 items-center justify-center rounded-lg text-[--color-gold] font-display text-base shadow-[0_2px_8px_-1px_rgba(37,71,208,0.45)]">
              F
            </div>
            <div className="leading-tight">
              <div className="font-display text-[15px] text-[--color-navy]">FutureGrad</div>
              <div className="text-[11px] text-[--color-ink-faint]">Reddit Intelligence</div>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="rounded-md p-1 text-[--color-ink-faint] hover:bg-[--color-paper] hover:text-[--color-ink] lg:hidden"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-5">
              <div className="px-2.5 pb-1.5 text-[10.5px] font-semibold tracking-wider text-[--color-ink-faint]">
                {group.label.toUpperCase()}
              </div>
              <div className="space-y-0.5">
                {group.items.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    onClick={onClose}
                    className={({ isActive }) =>
                      clsx(
                        'relative flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors',
                        isActive
                          ? 'bg-[--color-royal-soft] font-medium text-[--color-royal]'
                          : 'text-[--color-ink-soft] hover:bg-[--color-paper] hover:text-[--color-ink]'
                      )
                    }
                  >
                    {({ isActive }: { isActive: boolean }) => (
                      <>
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-[--color-royal]" />
                        )}
                        <Icon size={16} strokeWidth={2} />
                        {label}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-[--color-line] px-4 py-3.5 text-[11.5px] text-[--color-ink-faint]">
          <div className="flex items-center gap-1.5">
            <span
              className={clsx(
                'h-1.5 w-1.5 rounded-full',
                dbOk ? 'bg-emerald-500' : dbOk === false ? 'bg-[--color-hot]' : 'bg-[--color-ink-faint]'
              )}
            />
            {dbOk === null ? 'Checking system…' : dbOk ? 'System operational' : 'Backend unreachable'}
          </div>
          <div className="mt-1 pl-3">SQLite connected</div>
          <div className="mt-2 inline-flex items-center gap-1 rounded-md bg-[--color-royal-soft] px-1.5 py-0.5 text-[10.5px] font-medium text-[--color-royal]">
            Local mode
          </div>
        </div>
      </aside>
    </>
  )
}
