import type {
  Analytics,
  ActivityItem,
  DashboardStats,
  Lead,
  LeadsResponse,
  Note,
  PipelineResponse,
  ScanRun,
  ScanState,
  SettingsStatus,
  ValidationState,
} from './types'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  dashboard: () => request<DashboardStats>('/api/dashboard'),
  leads: (params: {
    classification?: string
    status?: string
    subreddit?: string
    search?: string
    limit?: number
    offset?: number
  } = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') qs.set(k, String(v))
    })
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return request<LeadsResponse>(`/api/leads${suffix}`)
  },
  lead: (id: number) => request<Lead>(`/api/leads/${id}`),
  updateStatus: (id: number, status: string) =>
    request<Lead>(`/api/leads/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  addNote: (id: number, text: string) =>
    request<Note>(`/api/leads/${id}/notes`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  pipeline: () => request<PipelineResponse>('/api/pipeline'),
  analytics: () => request<Analytics>('/api/analytics'),
  activity: (limit = 50) => request<ActivityItem[]>(`/api/activity?limit=${limit}`),
  settings: () => request<SettingsStatus>('/api/settings'),
  startScan: (postLimit?: number) =>
    request<{ started: boolean }>('/api/scan', {
      method: 'POST',
      body: JSON.stringify({ post_limit: postLimit }),
    }),
  scanStatus: () => request<ScanState>('/api/scan/status'),
  scanLimits: () => request<{ allowed: number[] }>('/api/scan/limits'),
  recentScans: (limit = 10) => request<ScanRun[]>(`/api/scan/recent?limit=${limit}`),
  startValidation: () => request<{ started: boolean }>('/api/validation', { method: 'POST' }),
  validationStatus: () => request<ValidationState>('/api/validation/status'),
}
