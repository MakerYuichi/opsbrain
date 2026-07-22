import { useState } from 'react'
import { ChevronDown, ChevronRight, FileText, AlertTriangle, ShieldAlert, Info } from 'lucide-react'
import { format } from 'date-fns'
import type { EvidenceFact } from '../types/timeline'
import { FACT_TYPE_COLORS, FACT_TYPE_PRIORITY } from '../types/timeline'
import type { SupportingFact } from '../types/patterns'

export function adaptSupportingFact(f: SupportingFact): EvidenceFact {
  return {
    fact_id: f.fact_id, doc_id: f.doc_id, doc_type: f.doc_type ?? null,
    asset_id: f.asset_id ?? null, fact_type: f.fact_type,
    timestamp: f.timestamp ?? null, content: f.content,
    source_span: { start: -1, end: -1, text: f.source_span_text ?? '' },
    confidence: f.confidence, raw_text_excerpt: null,
  }
}

export function ConfidenceDots({ score }: { score: number }) {
  const filled = Math.round(score * 5)
  const pct = Math.round(score * 100)
  const dotColor = pct >= 90 ? '#22c55e' : pct >= 70 ? '#f59e0b' : '#ef4444'
  return (
    <span className="flex items-center gap-0.5" title={`${pct}% confidence`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <span key={i} className="w-1.5 h-1.5 rounded-full"
              style={{ background: i < filled ? dotColor : 'var(--border-2)' }} />
      ))}
    </span>
  )
}

function SourceSpanView({ fact }: { fact: EvidenceFact }) {
  const { source_span, raw_text_excerpt, doc_id, doc_type } = fact
  const hasSpan = (source_span.text?.length ?? 0) > 0
  if (!hasSpan && !raw_text_excerpt)
    return <p className="text-xs t-3 italic">No source trace available.</p>

  const renderExcerpt = (text: string) =>
    text.split(/(>>>.*?<<<)/s).map((part, i) => {
      if (part.startsWith('>>>') && part.endsWith('<<<'))
        return <mark key={i} className="bg-amber-100 dark:bg-amber-400/20 text-amber-800 dark:text-amber-200 rounded px-0.5 not-italic">{part.slice(3,-3)}</mark>
      return <span key={i}>{part}</span>
    })

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[12px] t-3">
        <FileText size={11} className="shrink-0" />
        <span className="font-mono font-semibold" style={{ color:'var(--brand)' }}>{doc_id}</span>
        {doc_type && <span className="t-3">({doc_type.replace(/_/g,' ')})</span>}
      </div>
      {hasSpan && (
        <div className="rounded-lg p-3 border border-base" style={{ background:'var(--bg-2)' }}>
          <p className="text-[10px] font-semibold t-3 uppercase tracking-wider mb-1.5">
            Verbatim source{source_span.start >= 0 && <span className="ml-2 t-3">chars {source_span.start}–{source_span.end}</span>}
          </p>
          <blockquote className="text-[12px] italic border-l-3 border-amber-400 pl-3 leading-relaxed
                                  text-amber-800 dark:text-amber-200">
            "{source_span.text}"
          </blockquote>
        </div>
      )}
      {raw_text_excerpt && (
        <div className="rounded-lg p-3 border border-base" style={{ background:'var(--bg-2)' }}>
          <p className="text-[10px] font-semibold t-3 uppercase tracking-wider mb-1.5">Document context</p>
          <pre className="text-[12px] t-2 whitespace-pre-wrap font-mono leading-relaxed">
            {renderExcerpt(raw_text_excerpt)}
          </pre>
        </div>
      )}
    </div>
  )
}

interface Props { fact: EvidenceFact; highlight?: boolean; compact?: boolean }

export default function EvidenceCard({ fact, highlight, compact }: Props) {
  const [expanded, setExpanded] = useState(false)
  const priority   = FACT_TYPE_PRIORITY[fact.fact_type] ?? 99
  const isHighRisk = priority <= 4
  const badgeClass = FACT_TYPE_COLORS[fact.fact_type] ?? 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-white/10'

  const cardBorder = isHighRisk || highlight
    ? 'border-orange-300 dark:border-orange-500/25 bg-orange-50/50 dark:bg-orange-500/[0.04]'
    : 'border-base'

  const formattedTs = fact.timestamp
    ? (() => { try { return format(new Date(fact.timestamp!), 'd MMM yyyy HH:mm') } catch { return fact.timestamp } })()
    : null

  const pad = compact ? 'px-3 py-2.5' : 'px-4 py-3.5'

  return (
    <div className={`rounded-xl border transition-all overflow-hidden ${cardBorder} ${expanded ? 'shadow-md' : ''}`}>
      <div className={`flex items-start gap-3 ${pad} cursor-pointer
                       hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors`}
           onClick={() => setExpanded(e => !e)}>

        <div className={`mt-0.5 shrink-0
          ${priority <= 1 ? 'text-red-500' : priority <= 3 ? 'text-orange-500' : 't-3'}`}>
          {priority <= 1 ? <ShieldAlert size={15} /> : priority <= 4 ? <AlertTriangle size={15} /> : <Info size={15} />}
        </div>

        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={`pill ${badgeClass}`}>{fact.fact_type.replace(/_/g,' ')}</span>
            {fact.asset_id && (
              <span className="pill font-mono normal-case"
                    style={{ background:'var(--brand-light)', color:'var(--brand)', borderColor:'var(--brand)' + '44' }}>
                {fact.asset_id}
              </span>
            )}
            {formattedTs && <span className="text-[11px] t-3">{formattedTs}</span>}
          </div>
          <p className={`${compact ? 'text-[12px]' : 'text-[13px]'} t-primary leading-snug`}>{fact.content}</p>
          <div className="flex items-center gap-2.5">
            <ConfidenceDots score={fact.confidence} />
            <span className="text-[11px] t-3">{Math.round(fact.confidence*100)}%</span>
            <span className="text-[11px] t-3 ml-auto">{expanded ? 'Hide ↑' : 'Source →'}</span>
          </div>
        </div>

        <div className="shrink-0 t-3 mt-0.5">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>
      {expanded && (
        <div className={`${compact?'px-3 pb-3':'px-4 pb-4'} pt-2 border-t border-base`}
             style={{ background:'var(--bg)' }}>
          <SourceSpanView fact={fact} />
        </div>
      )}
    </div>
  )
}
