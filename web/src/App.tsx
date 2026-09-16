import { lazy, Suspense, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { ToastProvider } from './lib/toast'

// Code-split every route so the initial bundle only carries the app shell
// + whichever page is actually visited first — keeps this comfortably
// within Vercel Free's static-hosting model (plain lazy-loaded JS
// chunks, no serverless/edge functions involved).
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Leads = lazy(() => import('./pages/Leads').then((m) => ({ default: m.Leads })))
const LeadDetail = lazy(() => import('./pages/LeadDetail').then((m) => ({ default: m.LeadDetail })))
const Pipeline = lazy(() => import('./pages/Pipeline').then((m) => ({ default: m.Pipeline })))
const Analytics = lazy(() => import('./pages/Analytics').then((m) => ({ default: m.Analytics })))
const ScanPage = lazy(() => import('./pages/ScanPage').then((m) => ({ default: m.ScanPage })))
const Validation = lazy(() => import('./pages/Validation').then((m) => ({ default: m.Validation })))
const ActivityPage = lazy(() => import('./pages/ActivityPage').then((m) => ({ default: m.ActivityPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))

function RouteFallback() {
  return (
    <div className="p-6 sm:p-8 lg:p-10">
      <div className="fg-skeleton mb-4 h-8 w-56 rounded-lg" />
      <div className="fg-skeleton h-40 w-full rounded-2xl" />
    </div>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('fg-sidebar-collapsed') === '1'
    } catch {
      return false
    }
  })

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem('fg-sidebar-collapsed', next ? '1' : '0')
      } catch {
        /* localStorage unavailable — collapse state just won't persist */
      }
      return next
    })
  }

  return (
    <ToastProvider>
      <div className="flex min-h-screen bg-[--color-bg]">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          collapsed={collapsed}
          onToggleCollapsed={toggleCollapsed}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenSidebar={() => setSidebarOpen(true)} />

          <main className="min-w-0 flex-1 overflow-y-auto">
            <Suspense fallback={<RouteFallback />}>
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
            </Suspense>
          </main>
        </div>
      </div>
    </ToastProvider>
  )
}
