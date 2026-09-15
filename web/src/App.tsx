import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { Sidebar } from './components/Sidebar'
import { Dashboard } from './pages/Dashboard'
import { Leads } from './pages/Leads'
import { LeadDetail } from './pages/LeadDetail'
import { Pipeline } from './pages/Pipeline'
import { Analytics } from './pages/Analytics'
import { ScanPage } from './pages/ScanPage'
import { Validation } from './pages/Validation'
import { ActivityPage } from './pages/ActivityPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-[--color-paper]">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile-only top bar — the sidebar is a slide-out drawer below lg */}
        <div className="flex items-center gap-3 border-b border-[--color-line] bg-[--color-paper-raised] px-4 py-3 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
            className="rounded-md p-1.5 text-[--color-ink] hover:bg-[--color-paper]"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[--color-ink] text-[--color-gold] font-display text-[13px]">
              F
            </div>
            <span className="font-display text-[14px] text-[--color-ink]">FutureGrad</span>
          </div>
        </div>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/validation" element={<Validation />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
