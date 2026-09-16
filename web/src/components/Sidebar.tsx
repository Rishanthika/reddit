import { NavLink, useLocation } from 'react-router-dom'
import clsx from 'clsx'
import {
  LayoutDashboard,
  Flame,
  Sparkles,
  Snowflake,
  KanbanSquare,
  RadarIcon,
  ShieldCheck,
  BarChart3,
  Activity as ActivityIcon,
  Settings as SettingsIcon,
  X,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  match?: (pathname: string, search: string) => boolean
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard }],
  },
  {
    label: 'Leads',
    items: [
      {
        to: '/leads',
        label: 'All Leads',
        icon: Flame,
        match: (p, s) => p === '/leads' && !s,
      },
      {
        to: '/leads?classification=HOT',
        label: 'Hot Leads',
        icon: Flame,
        match: (p, s) => p === '/leads' && s.includes('classification=HOT'),
      },
      {
        to: '/leads?classification=WARM',
        label: 'Warm Leads',
        icon: Sparkles,
        match: (p, s) => p === '/leads' && s.includes('classification=WARM'),
      },
      {
        to: '/leads?classification=COLD',
        label: 'Cold Leads',
        icon: Snowflake,
        match: (p, s) => p === '/leads' && s.includes('classification=COLD'),
      },
      { to: '/pipeline', label: 'Pipeline', icon: KanbanSquare },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/scan', label: 'Scan Reddit', icon: RadarIcon },
      { to: '/validation', label: 'AI Validation', icon: ShieldCheck },
      { to: '/analytics', label: 'Analytics', icon: BarChart3 },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/activity', label: 'Activity', icon: ActivityIcon },
      { to: '/settings', label: 'Settings', icon: SettingsIcon },
    ],
  },
]

interface Props {
  open: boolean
  onClose: () => void
  collapsed: boolean
  onToggleCollapsed: () => void
}

export function Sidebar({ open, onClose, collapsed, onToggleCollapsed }: Props) {
  const [dbOk, setDbOk] = useState<boolean | null>(null)
  const [settings, setSettings] = useState<{ ai_provider?: string } | null>(null)
  const location = useLocation()

  useEffect(() => {
    api.health().then(() => setDbOk(true)).catch(() => setDbOk(false))
    api.settings().then(setSettings).catch(() => setSettings(null))
  }, [])

  const width = collapsed ? 'w-[88px]' : 'w-[260px]'

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-[--color-navy]/40 backdrop-blur-[1px] lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 flex h-screen shrink-0 flex-col border-r border-[--color-border] bg-[--color-surface] transition-[transform,width] duration-200 lg:static lg:translate-x-0',
          width,
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className={clsx('flex items-center pt-6 pb-5', collapsed ? 'justify-center px-2' : 'justify-between px-5')}>
          <div className="flex items-center gap-2.5">
            <div className="fg-gradient flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[--color-gold] font-display text-[13px] font-bold shadow-[0_2px_8px_-1px_rgba(37,71,208,0.45)]">
              FG
            </div>
            {!collapsed && (
              <div className="leading-tight">
                <div className="font-display text-[14.5px] font-semibold text-[--color-navy]">FutureGrad</div>
                <div className="text-[10.5px] text-[--color-muted]">Reddit Intelligence</div>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="rounded-md p-1 text-[--color-muted] hover:bg-[--color-bg] hover:text-[--color-text] lg:hidden"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto overflow-x-hidden px-3 pb-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-5">
              {!collapsed && (
                <div className="px-2.5 pb-1.5 text-[10.5px] font-semibold tracking-wider text-[--color-muted]">
                  {group.label.toUpperCase()}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive = item.match
                    ? item.match(location.pathname, location.search)
                    : location.pathname === item.to
                  return (
                    <NavLink
                      key={item.label}
                      to={item.to}
                      onClick={onClose}
                      title={collapsed ? item.label : undefined}
                      className={clsx(
                        'relative flex items-center gap-2.5 rounded-lg py-1.5 text-[13.5px] transition-colors',
                        collapsed ? 'justify-center px-2' : 'px-2.5',
                        isActive
                          ? 'bg-[--color-royal-soft] font-medium text-[--color-royal]'
                          : 'text-[--color-text-soft] hover:bg-[--color-bg] hover:text-[--color-text]'
                      )}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-[--color-royal]" />
                      )}
                      <item.icon size={16} strokeWidth={2} />
                      {!collapsed && item.label}
                    </NavLink>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        <button
          onClick={onToggleCollapsed}
          className={clsx(
            'mx-3 mb-2 hidden items-center gap-2 rounded-lg py-1.5 text-[12px] text-[--color-muted] hover:bg-[--color-bg] hover:text-[--color-text] lg:flex',
            collapsed ? 'justify-center px-2' : 'px-2.5'
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronsRight size={15} /> : <ChevronsLeft size={15} />}
          {!collapsed && 'Collapse'}
        </button>

        <div className={clsx('border-t border-[--color-border] py-3.5 text-[11.5px] text-[--color-muted]', collapsed ? 'px-2 text-center' : 'px-4')}>
          <div className={clsx('flex items-center gap-1.5', collapsed && 'justify-center')}>
            <span
              className={clsx(
                'h-1.5 w-1.5 rounded-full',
                dbOk ? 'bg-[--color-emerald]' : dbOk === false ? 'bg-[--color-rose]' : 'bg-[--color-muted]'
              )}
            />
            {!collapsed && (dbOk === null ? 'Checking…' : dbOk ? 'Backend Connected' : 'Backend unreachable')}
          </div>
          {!collapsed && (
            <>
              <div className="mt-1 pl-3">Render · SQLite</div>
              <div className="mt-2 inline-flex items-center gap-1 rounded-md bg-[--color-royal-soft] px-1.5 py-0.5 text-[10.5px] font-medium text-[--color-royal]">
                AI: {settings?.ai_provider ?? '—'}
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  )
}
