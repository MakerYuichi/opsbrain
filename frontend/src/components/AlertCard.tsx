import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, Zap, AlertTriangle, AlertOctagon, Info, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
import type { AlertSummary, AlertDetail } from '../types/patterns'
import { fetchAlert } from '../api/patterns'
import EvidenceCard, { ConfidenceDots, adaptSupportingFact } from './EvidenceCard'

// Risk level → visual style (works in both light and dark)
const RISK_STYLES: Record<string, { card: string; pill: string }> = {
  CRITICAL: {
    card: 'border-red-300 dark:border-red-500/30 bg-red-50 dark:bg-red-500/[0.06]',
    pill: 'bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-300 border-red-300 dark:border-red-500/30',
  },
  HIGH: {
    card: 'border-orange-300 dark:border-orange-500/30 bg-orange-50 dark:bg-orange-500/[0.06]',
    pill: 'bg-orange-100 dark:bg-orange-500/15 text-orange-700 dark:text-orange-300 border-orange-300 dark:border-orange-500/30',
  },
  MEDIUM: {
    card: 'border-yellow-300 dark:border-yellow-500/25 bg-yellow-50 dark:bg-yellow-500/[0.04]',
    pill: 'bg-yellow-100 dark:bg-yellow-500/15 text-yellow-700 dark:text-yellow-300 border-yellow-300 dark:border-yellow-500/25',
  },
  LOW:    { card: 'border-base', pill: 'bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-white/10' },
  UNKNOWN:{ card: 'border-base', pill: 'bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-white/10' },
}

function RiskIcon({ level }: { level: string }) {
  if (level === 'CRITICAL') return <AlertOctagon size={15} className="text-red-500 shrink-0" />
  if (level === 'HIGH')     return <AlertTriangle size={15} className="text-orange-500 shrink-0" />
  return <Info size={15} className="t-3 shrink-0" />
}

function splitDesc(desc: string) {
  const clean = desc.replace(/^\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*/, '')
  const i = clean.indexOf('Recommendation:')
  if (i < 0) return { body: clean, rec: '' }
  return { body: clean.slice(0, i).trim(), rec: clean.slice(i + 15).trim() }
}

export default function AlertCard({ alert }: { alert: AlertSummary }) {
  const [expanded, setExpanded] = useState(false)
  const [detail,   setDetail]   = useState<AlertDetail | null>(null)
  const [loading,  setLoading]  = useState(false)

  useEffect(() => {
    if (!expanded || detail) return
    setLoading(true)
    fetchAlert(alert.alert_id).then(setDetail).catch(console.error).finally(() => setLoading(false))
  }, [expanded, alert.alert_id, detail])

  const ts = (() => { try { return format(new Date(alert.created_at), 'd MMM yyyy') } catch { return '' } })()
  const { body, rec } = splitDesc(alert.description)
  const styles = RISK_STYLES[alert.risk_level] ?? RISK_STYLES.UNKNOWN

  return (
    <div className={`rounded-xl border transition-all overflow-hidden ${styles.card} ${expanded ? 'shadow-md' : ''}`}>

      {/* Header */}
      <div className="flex items-start gap-3 px-4 py-4 cursor-pointer hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors"
           onClick={() => setExpanded(e => !e)}>
        <RiskIcon level={alert.risk_level} />
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`pill ${styles.pill}`}>{alert.risk_level}</span>
            <span className="text-[12px] font-mono font-semibold t-2 px-2 py-0.5 rounded-lg border border-base"
                  style={{ background:'var(--bg-2)' }}>
              {alert.pattern_type.replace(/_/g,' ')}
            </span>
            {alert.asset_id && (
              <span className="pill font-mono normal-case"
                    style={{ background:'var(--brand-light)', color:'var(--brand)', borderColor:'var(--brand)' + '44' }}>
                {alert.asset_id}
              </span>
            )}
          </div>
          <p className="text-[13px] t-primary leading-snug">{body}</p>
          {rec && (
            <p className="text-[12px] text-teal-700 dark:text-teal-300
                          bg-teal-50 dark:bg-teal-500/10 border border-teal-200 dark:border-teal-500/20
                          rounded-lg px-3 py-2 leading-relaxed">
              ↪ {rec}
            </p>
          )}
          <div className="flex items-center gap-3 flex-wrap">
            <ConfidenceDots score={alert.confidence} />
            <span className="text-[11px] t-3">{Math.round(alert.confidence*100)}% confidence</span>
            <span className="text-[11px] t-3 flex items-center gap-1">
              <Zap size={9} />{alert.source_fact_count} facts
            </span>
            {ts && <span className="text-[11px] t-3">{ts}</span>}
            <span className="text-[11px] t-3 ml-auto">{expanded ? 'Hide ↑' : 'Evidence →'}</span>
          </div>
        </div>
        <div className="shrink-0 t-3 mt-0.5">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-base px-4 pb-4 pt-3 space-y-2" style={{ background:'var(--bg)' }}>
          {loading && (
            <div className="flex items-center gap-2 text-xs t-3">
              <Loader2 size={13} className="animate-spin" /> Loading facts…
            </div>
          )}
          {detail && (
            <>
              <p className="text-[11px] font-semibold t-3 uppercase tracking-wider mb-2">
                {detail.supporting_facts.length} supporting facts — each traced to source
              </p>
              {detail.supporting_facts.map(f => (
                <EvidenceCard key={f.fact_id} fact={adaptSupportingFact(f)} compact />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
