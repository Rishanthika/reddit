import { Link } from 'react-router-dom'
import { X, ExternalLink, ArrowRight } from 'lucide-react'
import type { Lead } from '../lib/types'
import { PriorityBadge } from './PriorityBadge'

interface Props {
  lead: Lead | null
  onClose: () => void
}

export function LeadDrawer({ lead, onClose }: Props) {
  if (!lead) return null

  return (
    <>
      <div className="fixed inset-0 z-40 bg-[--color-navy]/30" onClick={onClose} aria-hidden="true" />
      <aside
        role="dialog"
        aria-label="Lead preview"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[--color-border] bg-[--color-surface] shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-[--color-border] px-5 py-4">
          <PriorityBadge classification={lead.lead_classification} score={lead.lead_score} />
          <button onClick={onClose} aria-label="Close preview" className="rounded-md p-1 text-[--color-muted] hover:bg-[--color-bg] hover:text-[--color-text]">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <h2 className="font-display text-lg leading-snug text-[--color-navy]">{lead.title}</h2>
          <div className="mt-1.5 text-[12.5px] text-[--color-muted]">
            u/{lead.username} · r/{lead.subreddit}
          </div>

          <div className="mt-5 grid grid-cols-2 gap-4 border-t border-[--color-border] pt-4">
            <Field label="Intent" value={lead.intent ?? '—'} />
            <Field label="Status" value={lead.lead_status} />
            <Field label="Destination" value={lead.destination ?? '—'} />
            <Field label="Course" value={lead.course ?? '—'} />
          </div>

          {lead.service_needed.length > 0 && (
            <div className="mt-4">
              <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">Service Needed</div>
              <div className="flex flex-wrap gap-1.5">
                {lead.service_needed.map((s) => (
                  <span key={s} className="rounded-md bg-[--color-royal-soft] px-2 py-0.5 text-[11.5px] font-medium text-[--color-royal]">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {lead.ai_reason && (
            <div className="mt-4">
              <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">AI Reasoning</div>
              <p className="text-[13px] leading-relaxed text-[--color-text-soft]">{lead.ai_reason}</p>
            </div>
          )}

          {lead.post_text && (
            <div className="mt-4">
              <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">Reddit Post</div>
              <p className="line-clamp-6 text-[13px] leading-relaxed text-[--color-text-soft]">{lead.post_text}</p>
            </div>
          )}

          <a
            href={lead.post_url}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex items-center gap-1.5 text-[12.5px] text-[--color-royal] hover:underline"
          >
            View on Reddit <ExternalLink size={12} />
          </a>
        </div>

        <div className="border-t border-[--color-border] px-5 py-4">
          <Link
            to={`/leads/${lead.id}`}
            className="flex items-center justify-center gap-2 rounded-lg bg-[--color-royal] py-2.5 text-[13.5px] font-semibold text-white hover:bg-[--color-royal]/90"
          >
            View Full Profile <ArrowRight size={14} />
          </Link>
        </div>
      </aside>
    </>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-[--color-muted]">{label}</div>
      <div className="mt-0.5 text-[13.5px] text-[--color-text]">{value}</div>
    </div>
  )
}
