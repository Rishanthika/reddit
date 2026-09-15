export interface Lead {
  id: number
  reddit_post_id: string
  username: string
  subreddit: string
  title: string
  post_url: string
  post_text: string
  created_at: string
  destination: string | null
  course: string | null
  intent: string | null
  service_needed: string[]
  ai_is_lead: boolean | null
  ai_confidence: number | null
  ai_reason: string | null
  pre_filter_score: number | null
  lead_score: number | null
  lead_classification: 'HOT' | 'WARM' | 'COLD' | null
  lead_status: string
  assigned_counsellor: string | null
  processed_at: string
  notes?: Note[]
}

export interface Note {
  id: number
  lead_id: number
  note_text: string
  created_at: string
}

export interface DashboardStats {
  total_leads: number
  hot: number
  warm: number
  cold: number
  new_today: number
}

export interface LeadsResponse {
  items: Lead[]
  total: number
}

export interface PipelineCard {
  id: number
  title: string
  subreddit: string
  lead_score: number | null
  lead_classification: string | null
  destination: string | null
  course: string | null
}

export interface PipelineResponse {
  statuses: string[]
  board: Record<string, PipelineCard[]>
}

export interface Analytics {
  total_leads: number
  priority_distribution: Record<string, number>
  pipeline_distribution: Record<string, number>
  subreddit_distribution: Record<string, number>
  destination_distribution: Record<string, number>
  course_distribution: Record<string, number>
  service_demand: Record<string, number>
}

export interface ActivityItem {
  id: number
  event_type: string
  message: string
  lead_id: number | null
  created_at: string
}

export interface SettingsStatus {
  reddit_connector: string
  ai_provider: string
  database: string
  environment: string
  subreddits?: string[]
  post_limit?: number
  classifier_validation_limit?: number
}

export interface ScanState {
  status: 'idle' | 'starting' | 'running' | 'done' | 'error'
  stage: string
  scan_id: number | null
  discovered: number
  filtered: number
  analyzed: number
  hot: number
  warm: number
  cold: number
  sources: string[]
  post_limit: number | null
  started_at: string | null
  finished_at: string | null
  error: string | null
}

export interface ScanRun {
  id: number
  status: string
  sources: string[]
  post_limit: number
  discovered: number | null
  filtered: number | null
  analyzed: number | null
  hot: number | null
  warm: number | null
  cold: number | null
  error: string | null
  started_at: string | null
  finished_at: string | null
}

export interface ValidationResult {
  reddit_post_id: string
  subreddit: string
  title: string
  already_in_db?: boolean
  is_lead?: boolean
  intent?: string
  destination?: string | null
  course?: string | null
  service_needed?: string[]
  reason?: string
  confidence?: number
  score?: number
  classification?: string
  error?: string
}

export interface ValidationSummary {
  retrieved: number
  filtered_out: number
  sent_to_classifier: number
  ai_errors: number
  hot: number
  warm: number
  cold: number
}

export interface ValidationState {
  status: 'idle' | 'running' | 'done' | 'error'
  results: ValidationResult[]
  summary: ValidationSummary | null
  finished_at: string | null
  error: string | null
}
