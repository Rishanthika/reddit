import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, Search, RadarIcon, Bell, User } from 'lucide-react'
import { api } from '../lib/api'

interface Props {
  onOpenSidebar: () => void
}

export function Topbar({ onOpenSidebar }: Props) {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [aiProvider, setAiProvider] = useState<string | null>(null)
  const [backendUp, setBackendUp] = useState<boolean | null>(null)

  useEffect(() => {
    api.settings().then((s) => setAiProvider(s.ai_provider)).catch(() => setAiProvider(null))
    api.health().then(() => setBackendUp(true)).catch(() => setBackendUp(false))
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (search.trim()) navigate(`/leads?search=${encodeURIComponent(search.trim())}`)
  }

  return (
    <header className="flex h-[72px] shrink-0 items-center gap-3 border-b border-[--color-border] bg-[--color-surface] px-4 sm:px-6">
      <button
        onClick={onOpenSidebar}
        aria-label="Open navigation"
        className="rounded-md p-1.5 text-[--color-text] hover:bg-[--color-bg] lg:hidden"
      >
        <Menu size={20} />
      </button>

      <form onSubmit={handleSearch} className="hidden min-w-0 max-w-sm flex-1 sm:block">
        <label htmlFor="global-search" className="sr-only">
          Search leads
        </label>
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[--color-muted]" />
          <input
            id="global-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search leads…"
            className="w-full rounded-[--radius-input] border border-[--color-border] bg-[--color-bg] py-2 pl-9 pr-3 text-[13.5px] outline-none transition-colors focus:border-[--color-royal] focus:bg-[--color-surface]"
          />
        </div>
      </form>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => navigate('/scan')}
          className="fg-gradient hidden items-center gap-1.5 rounded-lg px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm transition-transform hover:-translate-y-px sm:flex"
        >
          <RadarIcon size={14} />
          Quick Scan
        </button>

        <span
          title={aiProvider ? `AI provider: ${aiProvider}` : undefined}
          className="hidden items-center gap-1.5 rounded-full border border-[--color-border] bg-[--color-bg] px-2.5 py-1 text-[11.5px] font-medium text-[--color-text-soft] md:inline-flex"
        >
          <Sparkle />
          {aiProvider ?? '—'}
        </span>

        <span
          title={backendUp === false ? 'Backend unreachable' : 'Backend connected'}
          className="hidden items-center gap-1.5 rounded-full border border-[--color-border] bg-[--color-bg] px-2.5 py-1 text-[11.5px] font-medium text-[--color-text-soft] md:inline-flex"
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              backendUp ? 'bg-[--color-emerald]' : backendUp === false ? 'bg-[--color-rose]' : 'bg-[--color-muted]'
            }`}
          />
          {backendUp === false ? 'Offline' : 'Live'}
        </span>

        <button
          aria-label="Notifications"
          className="rounded-full p-2 text-[--color-text-soft] hover:bg-[--color-bg] hover:text-[--color-text]"
        >
          <Bell size={17} />
        </button>

        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[--color-royal-soft] text-[--color-royal]">
          <User size={15} />
        </div>
      </div>
    </header>
  )
}

function Sparkle() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" className="text-[--color-violet]">
      <path
        d="M12 2l1.8 5.6L19.4 9.4 13.8 11.2 12 16.8 10.2 11.2 4.6 9.4 10.2 7.6z"
        fill="currentColor"
      />
    </svg>
  )
}
