import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { api } from '../lib/api'
import type { Lead } from '../lib/types'
import { PriorityBadge } from '../components/PriorityBadge'
import { ErrorState } from '../components/ErrorState'

const PIPELINE_STAGES = ['NEW', 'CONTACTED', 'RESPONDED', 'COUNSELLING', 'APPLICATION', 'CONVERTED']

const INTENT_WEIGHTS: Record<string, number> = { high: 80, medium: 50, low: 10, none: 0 }

export function LeadDetail() {
  const { id } = useParams()
  const [lead, setLead] = useState<Lead | null>(null)
  const [noteText, setNoteText] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

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
  }

  useEffect(load, [id])

  if (loadError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <Link to="/leads" className="mb-6 inline-flex items-center gap-1.5 text-sm text-[--color-ink-faint] hover:text-[--color-ink]">
          <ArrowLeft size={14} /> Back to leads
        </Link>
        <ErrorState message={loadError} onRetry={load} />
      </div>
    )
  }

  if (!lead) {
    return <div className="px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10 text-sm text-[--color-ink-faint]">Loading…</div>
  }

  const intentBase = lead.intent ? INTENT_WEIGHTS[lead.intent] ?? 0 : 0
  const destBonus = lead.destination ? 10 : 0
  const courseBonus = lead.course ? 10 : 0
  const serviceBonus = lead.service_needed.length ? 15 : 0
  const currentStageIndex = PIPELINE_STAGES.indexOf(lead.lead_status)

  const handleStatusChange = async (status: string) => {
    setActionError(null)
    try {
      await api.updateStatus(lead.id, status)
      load()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update status.')
    }
  }

  const handleAddNote = async () => {
    if (!noteText.trim()) return
    setSavingNote(true)
    setActionError(null)
    try {
      await api.addNote(lead.id, noteText.trim())
      setNoteText('')
      load()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to save note.')
    } finally {
      setSavingNote(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
      <Link to="/leads" className="mb-6 inline-flex items-center gap-1.5 text-sm text-[--color-ink-faint] hover:text-[--color-ink]">
        <ArrowLeft size={14} /> Back to leads
      </Link>

      <div className="flex items-start gap-4">
        <PriorityBadge classification={lead.lead_classification} score={lead.lead_score} size="lg" />
      </div>
      <h1 className="mt-4 font-display text-[28px] leading-snug text-[--color-ink]">{lead.title}</h1>
      <div className="mt-2 text-sm text-[--color-ink-faint]">
        Source:{' '}
        <a href={lead.post_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[--color-ink-soft] hover:text-[--color-ink]">
          r/{lead.subreddit} <ExternalLink size={12} />
        </a>
      </div>

      {actionError && (
        <div className="mt-4 rounded-lg border border-[--color-hot]/25 bg-[--color-hot-soft] px-4 py-2.5 text-[13px] text-[--color-hot]">
          {actionError}
        </div>
      )}

      {/* AI Insight */}
      <section className="mt-8 rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-6">
        <div className="mb-4 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">AI INSIGHT</div>
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          <Field label="Intent" value={lead.intent?.toUpperCase() ?? 'UNKNOWN'} />
          <Field label="Destination" value={lead.destination ?? 'Unknown'} />
          <Field label="Course" value={lead.course ?? 'Unknown'} />
          <Field label="Confidence" value={lead.ai_confidence != null ? `${Math.round(lead.ai_confidence * 100)}%` : '—'} />
        </div>
        <div className="mt-5">
          <div className="mb-1.5 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">SERVICES</div>
          {lead.service_needed.length ? (
            <div className="flex flex-wrap gap-1.5">
              {lead.service_needed.map((s) => (
                <span key={s} className="rounded-md bg-[--color-gold-soft] px-2 py-0.5 text-[12px] font-medium text-[--color-ink]">
                  {s}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-sm text-[--color-ink-faint]">Unknown</span>
          )}
        </div>
        <div className="mt-5">
          <div className="mb-1.5 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">AI REASONING</div>
          <p className="text-[14px] leading-relaxed text-[--color-ink-soft]">{lead.ai_reason ?? '—'}</p>
        </div>
      </section>

      {/* Original post */}
      <section className="mt-6 rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-6">
        <div className="mb-3 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">ORIGINAL REDDIT POST</div>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-[--color-ink]">
          {lead.post_text?.trim() || <span className="text-[--color-ink-faint]">(no body text — title only)</span>}
        </p>
      </section>

      {/* Score intelligence */}
      <section className="mt-6 rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-6">
        <div className="mb-4 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">SCORE INTELLIGENCE</div>
        <div className="space-y-2 font-mono-num text-sm">
          <ScoreRow label={`Intent (${lead.intent ?? 'none'})`} value={intentBase} />
          <ScoreRow label="Destination" value={destBonus} />
          <ScoreRow label="Course" value={courseBonus} />
          <ScoreRow label="Service" value={serviceBonus} />
          <div className="!mt-3 flex items-center justify-between border-t border-[--color-line] pt-3">
            <span className="text-[--color-ink-soft]">Total</span>
            <span className="text-lg font-semibold text-[--color-ink]">{lead.lead_score ?? 0}</span>
          </div>
        </div>
      </section>

      {/* Lead journey */}
      <section className="mt-6 rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-6">
        <div className="mb-4 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">LEAD JOURNEY</div>
        <div className="flex items-center overflow-x-auto pb-1">
          {PIPELINE_STAGES.map((stage, i) => (
            <div key={stage} className="flex flex-1 items-center last:flex-none" style={{ minWidth: i < PIPELINE_STAGES.length - 1 ? '92px' : 'auto' }}>
              <button
                onClick={() => handleStatusChange(stage)}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors ${
                  i <= currentStageIndex
                    ? 'bg-[--color-ink] text-white'
                    : 'bg-[--color-paper] text-[--color-ink-faint] hover:bg-[--color-gold-soft] hover:text-[--color-ink]'
                }`}
              >
                {stage}
              </button>
              {i < PIPELINE_STAGES.length - 1 && (
                <div className={`mx-1.5 h-px flex-1 ${i < currentStageIndex ? 'bg-[--color-ink]' : 'bg-[--color-line]'}`} />
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          {['NO_RESPONSE', 'NOT_QUALIFIED', 'CLOSED'].map((s) => (
            <button
              key={s}
              onClick={() => handleStatusChange(s)}
              className={`rounded-full px-2.5 py-1 text-[11.5px] font-medium transition-colors ${
                lead.lead_status === s
                  ? 'bg-[--color-cold] text-white'
                  : 'bg-[--color-paper] text-[--color-ink-faint] hover:bg-[--color-cold-soft]'
              }`}
            >
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </section>

      {/* Counsellor notes */}
      <section className="mt-6 rounded-xl border border-[--color-line] bg-[--color-paper-raised] p-6">
        <div className="mb-4 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">COUNSELLOR NOTES</div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label htmlFor="note-input" className="sr-only">
            Add a counsellor note
          </label>
          <input
            id="note-input"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
            placeholder="Add a note…"
            aria-label="Add a counsellor note"
            className="flex-1 rounded-lg border border-[--color-line] px-3 py-2 text-sm outline-none focus:border-[--color-gold]"
          />
          <button
            onClick={handleAddNote}
            disabled={savingNote || !noteText.trim()}
            className="rounded-lg bg-[--color-ink] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            Add
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {(lead.notes ?? []).map((n) => (
            <div key={n.id} className="rounded-lg bg-[--color-paper] px-3.5 py-2.5 text-[13.5px] text-[--color-ink-soft]">
              {n.note_text}
              <div className="mt-1 text-[11px] text-[--color-ink-faint]">
                {new Date(n.created_at).toLocaleString()}
              </div>
            </div>
          ))}
          {(!lead.notes || lead.notes.length === 0) && (
            <p className="text-[13px] text-[--color-ink-faint]">No notes yet.</p>
          )}
        </div>
      </section>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold tracking-wider text-[--color-ink-faint]">{label.toUpperCase()}</div>
      <div className="text-[14.5px] text-[--color-ink]">{value}</div>
    </div>
  )
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[--color-ink-soft]">{label}</span>
      <span className="text-[--color-ink]">{value > 0 ? `+${value}` : value}</span>
    </div>
  )
}
