import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ExternalLink, Sparkles, UserCheck, PhoneCall, Leaf, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { ActivityItem, Lead } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'
import { ErrorState } from '../components/ErrorState'
import { ScoreRing } from '../components/ScoreRing'
import { useToast } from '../lib/toast'

const PIPELINE_STAGES = ['NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED']

const INTENT_WEIGHTS: Record<string, number> = { high: 80, medium: 50, low: 10, none: 0 }

const PRIORITY_COLOR: Record<string, string> = {
  HOT: 'var(--color-hot)',
  WARM: 'var(--color-warm)',
  COLD: 'var(--color-cold)',
}

const NEXT_ACTIONS = [
  { status: 'CONTACTED', label: 'Needs Follow-up', icon: PhoneCall },
  { status: 'COUNSELLING', label: 'Assign Counsellor', icon: UserCheck },
  { status: 'RESPONDED', label: 'Nurture', icon: Leaf },
  { status: 'NOT_QUALIFIED', label: 'Reject', icon: XCircle },
]

function timeAgo(iso: string | null) {
  if (!iso) return '—'
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function LeadDetail() {
  const { id } = useParams()
  const toast = useToast()
  const [lead, setLead] = useState<Lead | null>(null)
  const [activity, setActivity] = useState<ActivityItem[]>([])
  const [noteText, setNoteText] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const load = () => {
    if (!id) return
    api
      .lead(Number(id))
      .then((result) => {
        setLead(result)
        setLoadError(null)
      })
      .catch((err) => {
        setLoadError(
          err instanceof Error && err.message.startsWith('404')
            ? 'This lead does not exist — it may have been removed, or the link is incorrect.'
            : err instanceof Error
              ? err.message
              : 'Failed to load this lead.'
        )
      })
    api.activity(100).then((items) => setActivity(items.filter((a) => a.lead_id === Number(id)))).catch(() => {})
  }

  useEffect(load, [id])

  if (loadError) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <Link to="/leads" className="mb-6 inline-flex items-center gap-1.5 text-sm text-[--color-muted] hover:text-[--color-text]">
          <ArrowLeft size={14} /> Back to leads
        </Link>
        <ErrorState message={loadError} onRetry={load} />
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <div className="fg-skeleton mb-6 h-6 w-32 rounded" />
        <div className="fg-skeleton h-40 w-full rounded-2xl" />
      </div>
    )
  }

  const intentBase = lead.intent ? INTENT_WEIGHTS[lead.intent] ?? 0 : 0
  const destBonus = lead.destination ? 10 : 0
  const courseBonus = lead.course ? 10 : 0
  const serviceBonus = lead.service_needed.length ? 15 : 0
  const currentStageIndex = PIPELINE_STAGES.indexOf(lead.lead_status)
  const ringColor = PRIORITY_COLOR[lead.lead_classification ?? ''] ?? 'var(--color-cold)'

  const handleStatusChange = async (status: string) => {
    try {
      await api.updateStatus(lead.id, status)
      toast.show(`Status changed to ${status.replace('_', ' ')}`)
      load()
    } catch (err) {
      toast.show(err instanceof Error ? err.message : 'Failed to update status.', 'error')
    }
  }

  const handleAddNote = async () => {
    if (!noteText.trim()) return
    setSavingNote(true)
    try {
      await api.addNote(lead.id, noteText.trim())
      setNoteText('')
      toast.show('Note added')
      load()
    } catch (err) {
      toast.show(err instanceof Error ? err.message : 'Failed to save note.', 'error')
    } finally {
      setSavingNote(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <Link to="/leads" className="mb-6 inline-flex items-center gap-1.5 text-sm text-[--color-muted] hover:text-[--color-text]">
        <ArrowLeft size={14} /> Back to leads
      </Link>

      {/* Header */}
      <div className="fg-card flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
        <ScoreRing value={lead.lead_score ?? 0} color={ringColor} label={lead.lead_classification ?? ''} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <PriorityBadge classification={lead.lead_classification} size="sm" />
            <span className="rounded-md bg-[--color-bg] px-2 py-0.5 text-[11.5px] font-medium text-[--color-text-soft]">
              {lead.lead_status}
            </span>
          </div>
          <h1 className="mt-2 font-display text-[24px] leading-snug text-[--color-navy]">{lead.title}</h1>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[12.5px] text-[--color-muted]">
            <span>u/{lead.username}</span>
            <a href={lead.post_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-[--color-royal]">
              r/{lead.subreddit} <ExternalLink size={11} />
            </a>
            <span>{timeAgo(lead.created_at)}</span>
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* AI Qualification */}
          <section className="fg-card p-6">
            <div className="mb-4 flex items-center gap-2">
              <Sparkles size={14} className="text-[--color-violet]" />
              <span className="text-[11px] font-semibold tracking-wider text-[--color-muted]">AI QUALIFICATION</span>
            </div>
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <ScoreRing
                value={lead.ai_confidence != null ? lead.ai_confidence * 100 : 0}
                color="var(--color-violet)"
                label="confidence"
                size={64}
                thickness={6}
              />
              <div className="flex-1">
                <p className="text-[13.5px] leading-relaxed text-[--color-text-soft]">{lead.ai_reason ?? 'No reasoning recorded.'}</p>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-4 border-t border-[--color-border] pt-4 sm:grid-cols-4">
              <Field label="Intent" value={lead.intent?.toUpperCase() ?? 'UNKNOWN'} />
              <Field label="Destination" value={lead.destination ?? 'Unknown'} />
              <Field label="Course" value={lead.course ?? 'Unknown'} />
              <Field label="Confidence" value={lead.ai_confidence != null ? `${Math.round(lead.ai_confidence * 100)}%` : '—'} />
            </div>
            {lead.service_needed.length > 0 && (
              <div className="mt-4">
                <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">Service Needed</div>
                <div className="flex flex-wrap gap-1.5">
                  {lead.service_needed.map((s) => (
                    <span key={s} className="rounded-md bg-[--color-gold-soft] px-2 py-0.5 text-[12px] font-medium text-[--color-navy]">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Original post */}
          <section className="fg-card p-6">
            <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">REDDIT CONVERSATION</div>
            <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-[--color-text]">
              {lead.post_text?.trim() || <span className="text-[--color-muted]">(no body text — title only)</span>}
            </p>
            <a
              href={lead.post_url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 text-[12.5px] text-[--color-royal] hover:underline"
            >
              View on Reddit <ExternalLink size={12} />
            </a>
          </section>

          {/* Score breakdown */}
          <section className="fg-card p-6">
            <div className="mb-4 text-[11px] font-semibold tracking-wider text-[--color-muted]">CLASSIFICATION BREAKDOWN</div>
            <div className="space-y-2 font-mono-num text-sm">
              <ScoreRow label={`Intent Score (${lead.intent ?? 'none'})`} value={intentBase} />
              <ScoreRow label="Destination Bonus" value={destBonus} />
              <ScoreRow label="Course Bonus" value={courseBonus} />
              <ScoreRow label="Service Bonus" value={serviceBonus} />
              <div className="!mt-3 flex items-center justify-between border-t border-[--color-border] pt-3">
                <span className="text-[--color-text-soft]">Final Score</span>
                <span className="text-lg font-semibold text-[--color-navy]">{lead.lead_score ?? 0}</span>
              </div>
            </div>
          </section>
        </div>

        <div className="space-y-6">
          {/* Next best action */}
          <section className="fg-card p-5">
            <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">NEXT BEST ACTION</div>
            <div className="grid grid-cols-2 gap-2">
              {NEXT_ACTIONS.map((a) => (
                <button
                  key={a.status}
                  onClick={() => handleStatusChange(a.status)}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center text-[11.5px] font-medium transition-colors ${
                    lead.lead_status === a.status
                      ? 'border-[--color-royal] bg-[--color-royal-soft] text-[--color-royal]'
                      : 'border-[--color-border] text-[--color-text-soft] hover:bg-[--color-bg]'
                  }`}
                >
                  <a.icon size={16} />
                  {a.label}
                </button>
              ))}
            </div>
          </section>

          {/* Lead journey */}
          <section className="fg-card p-5">
            <div className="mb-4 text-[11px] font-semibold tracking-wider text-[--color-muted]">LEAD JOURNEY</div>
            <div className="space-y-1.5">
              {PIPELINE_STAGES.map((stage, i) => (
                <button
                  key={stage}
                  onClick={() => handleStatusChange(stage)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[12.5px] transition-colors ${
                    i <= currentStageIndex
                      ? 'bg-[--color-navy] text-white'
                      : 'text-[--color-text-soft] hover:bg-[--color-bg]'
                  }`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${i <= currentStageIndex ? 'bg-white' : 'bg-[--color-border]'}`} />
                  {stage}
                </button>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5 border-t border-[--color-border] pt-3">
              {['NO_RESPONSE', 'NOT_QUALIFIED', 'CLOSED'].map((s) => (
                <button
                  key={s}
                  onClick={() => handleStatusChange(s)}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
                    lead.lead_status === s ? 'bg-[--color-cold] text-white' : 'bg-[--color-bg] text-[--color-muted] hover:bg-[--color-cold-soft]'
                  }`}
                >
                  {s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </section>

          {/* Notes */}
          <section className="fg-card p-5">
            <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">INTERNAL NOTES</div>
            <div className="flex flex-col gap-2">
              <label htmlFor="note-input" className="sr-only">Add a counsellor note</label>
              <input
                id="note-input"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
                placeholder="Add a note…"
                aria-label="Add a counsellor note"
                className="rounded-[--radius-input] border border-[--color-border] px-3 py-2 text-sm outline-none focus:border-[--color-royal]"
              />
              <button
                onClick={handleAddNote}
                disabled={savingNote || !noteText.trim()}
                className="rounded-[--radius-input] bg-[--color-navy] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
              >
                Add Note
              </button>
            </div>
            <div className="mt-4 space-y-2.5 border-t border-[--color-border] pt-4">
              {(lead.notes ?? []).map((n) => (
                <div key={n.id} className="rounded-lg bg-[--color-bg] px-3.5 py-2.5 text-[13px] text-[--color-text-soft]">
                  {n.note_text}
                  <div className="mt-1 text-[10.5px] text-[--color-muted]">{new Date(n.created_at).toLocaleString()}</div>
                </div>
              ))}
              {(!lead.notes || lead.notes.length === 0) && (
                <p className="text-[12.5px] text-[--color-muted]">No notes yet.</p>
              )}
            </div>
          </section>

          {/* Activity timeline for this lead */}
          {activity.length > 0 && (
            <section className="fg-card p-5">
              <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-muted]">ACTIVITY</div>
              <ul className="space-y-3">
                {activity.map((a) => (
                  <li key={a.id} className="text-[12.5px]">
                    <div className="text-[--color-text]">{a.message}</div>
                    <div className="text-[--color-muted]">{timeAgo(a.created_at)}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[10.5px] font-medium uppercase tracking-wide text-[--color-muted]">{label}</div>
      <div className="truncate text-[13.5px] text-[--color-text]">{value}</div>
    </div>
  )
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[--color-text-soft]">{label}</span>
      <span className="text-[--color-text]">{value > 0 ? `+${value}` : value}</span>
    </div>
  )
}
