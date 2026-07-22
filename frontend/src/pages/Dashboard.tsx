import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, TrendingUp, Network, AlertOctagon,
         Database, GitBranch, Loader2, ArrowRight, ShieldAlert } from 'lucide-react'
import { fetchStats, type PlatformStats } from '../api/stats'
import { fetchAlerts } from '../api/patterns'
import type { AlertSummary } from '../types/patterns'
import type { NavContext } from '../App'
import AlertCard from '../components/AlertCard'

function StatTile({ icon: Icon, label, value, color, sub }: {
  icon: React.ElementType; label: string; value: number | string; color: string; sub?: string
}) {
  return (
    <div className="card p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-3xl font-bold t-primary tabular-nums leading-none">{value}</p>
          <p className="text-[11px] font-semibold t-3 uppercase tracking-wider mt-2">{label}</p>
          {sub && <p className="text-[11px] t-3 mt-0.5">{sub}</p>}
        </div>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
             style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
          <Icon size={18} style={{ color }} />
        </div>
      </div>
    </div>
  )
}

function FeatureCard({ icon: Icon, title, pitch, onClick, color }: {
  icon: React.ElementType; title: string; pitch: string; onClick: () => void; color: string
}) {
  return (
    <button onClick={onClick}
      className="card card-hover text-left p-5 space-y-3 transition-all
                 hover:-translate-y-0.5 hover:shadow-lg group">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center"
           style={{ background: `${color}15`, border: `1px solid ${color}25` }}>
        <Icon size={18} style={{ color }} />
      </div>
      <h3 className="font-semibold text-[14px] t-primary">{title}</h3>
      <p className="text-[12px] t-3 leading-relaxed">{pitch}</p>
      <span className="flex items-center gap-1 text-[12px] font-medium group-hover:gap-2 transition-all"
            style={{ color }}>
        Open <ArrowRight size={12} />
      </span>
    </button>
  )
}

export default function Dashboard({ navCtx }: { navCtx: NavContext }) {
  const navigate = useNavigate()
  const [stats,          setStats]          = useState<PlatformStats | null>(null)
  const [criticalAlerts, setCriticalAlerts] = useState<AlertSummary[]>([])
  const [loading,        setLoading]        = useState(true)
  const [err,            setErr]            = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchStats(), fetchAlerts()])
      .then(([s, alerts]) => {
        setStats(s)
        setCriticalAlerts(alerts.filter(a => a.risk_level === 'CRITICAL').slice(0, 3))
      })
      .catch(e => setErr(e instanceof Error ? e.message : 'Failed'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="h-full overflow-y-auto" style={{ background: 'var(--bg)' }}>

      {/* Hero */}
      <div className="px-8 py-8 border-b border-base" style={{ background: 'var(--bg-1)' }}>
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest mb-3"
             style={{ color: 'var(--brand)' }}>
          <ShieldAlert size={13} /> Predictive Operations Brain
        </div>
        <h1 className="text-2xl font-bold t-primary max-w-2xl leading-tight">
          Industrial Knowledge Intelligence
        </h1>
        <p className="text-[13px] t-3 max-w-2xl mt-2.5 leading-relaxed">
          Fragmented maintenance logs, permits, shift logs, and sensor data unified into one
          knowledge graph. Grounded in two real incidents — the{' '}
          <span className="t-2 font-medium">LG Polymers Vizag gas leak (2020)</span> and the{' '}
          <span className="t-2 font-medium">Vizag Steel Plant ladle explosion (2025)</span>,
          where warning signals existed but nothing connected them in time.
        </p>
      </div>

      <div className="px-8 py-7 space-y-8">
        {err && (
          <div className="rounded-xl p-4 text-[13px] text-red-600
                          bg-red-50 border border-red-200">
            Backend unavailable: {err}. Is the backend running on port 8000?
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 text-[13px] t-3">
            <Loader2 size={15} className="animate-spin" /> Loading…
          </div>
        ) : stats && (
          <>
            {/* Stats grid */}
            <div>
              <h2 className="text-[11px] font-semibold t-3 uppercase tracking-widest mb-3">
                Knowledge Graph
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <StatTile icon={Database}     label="Assets"    value={stats.asset_count}    color="#6366f1" sub="Equipment tracked" />
                <StatTile icon={Database}     label="Documents" value={stats.document_count} color="#0ea5e9" sub="Sources ingested" />
                <StatTile icon={GitBranch}    label="Facts"     value={stats.fact_count}     color="#22c55e" sub="Signals extracted" />
                <StatTile icon={GitBranch}    label="Edges"     value={stats.edge_count}     color="#a855f7" sub="Graph connections" />
                <StatTile icon={AlertOctagon} label="Alerts"    value={stats.alert_count}    color="#f97316" sub="Patterns detected" />
                <StatTile icon={AlertOctagon} label="Critical"  value={stats.critical_alert_count} color="#ef4444" sub="Needs attention" />
              </div>
            </div>

            {/* Critical alerts */}
            {criticalAlerts.length > 0 && (
              <div>
                <h2 className="text-[11px] font-semibold uppercase tracking-widest mb-3 flex items-center gap-2 text-red-500">
                  <AlertOctagon size={13} /> Active Critical Alerts
                </h2>
                <div className="space-y-2">
                  {criticalAlerts.map(a => <AlertCard key={a.alert_id} alert={a} />)}
                </div>
              </div>
            )}
          </>
        )}

        {/* Feature cards */}
        <div>
          <h2 className="text-[11px] font-semibold t-3 uppercase tracking-widest mb-3">Explore</h2>
          <div className="grid md:grid-cols-3 gap-4">
            <FeatureCard
              icon={Clock} title="Time Machine" color="#3b82f6"
              onClick={() => navCtx.goToTimeMachine('APS-3', '2025-06-06')}
              pitch="Drag to any date and see every log, permit, and sensor reading relevant to that moment."
            />
            <FeatureCard
              icon={TrendingUp} title="Pattern Breaker" color="#f97316"
              onClick={() => navigate('/patterns')}
              pitch="Surfaces recurring risk patterns across incidents with confidence scores and cited evidence."
            />
            <FeatureCard
              icon={Network} title="Graph Explorer" color="#a855f7"
              onClick={() => navCtx.goToGraph('APS-3')}
              pitch="Visualize how equipment, documents, and incidents connect — trace the full causal chain."
            />
          </div>
        </div>

        {/* Chat hint */}
        <div className="card p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0 text-white text-xs font-bold"
               style={{ background: 'linear-gradient(135deg,#6366f1,#3b82f6)' }}>
            KI
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-medium t-primary">Ask OpsBrain</p>
            <p className="text-[12px] t-3">
              Questions? Click the chat bubble in the bottom-right corner to ask about any asset, incident, or pattern.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
