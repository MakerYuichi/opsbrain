import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Clock, AlertTriangle, Activity, BookOpen, Loader2, Network } from 'lucide-react'
import { format } from 'date-fns'
import { fetchAssets, fetchTimeline } from '../api/timeline'
import type { AssetItem, TimelineResponse, EvidenceFact } from '../types/timeline'
import { FACT_TYPE_PRIORITY } from '../types/timeline'
import type { NavContext } from '../App'
import AssetPicker    from '../components/AssetPicker'
import TimelineSlider from '../components/TimelineSlider'
import EvidenceCard   from '../components/EvidenceCard'
import SensorChart    from '../components/SensorChart'

const DEMO_ASSET = 'APS-3'
const DEMO_DATE  = '2025-06-06'
type Tab = 'facts' | 'sensors' | 'oem'

export default function TimeMachine({ navCtx }: { navCtx: NavContext }) {
  const [sp, setSp]       = useSearchParams()
  const [assets, setAssets] = useState<AssetItem[]>([])
  const [data,   setData]   = useState<TimelineResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [tab, setTab]         = useState<Tab>('facts')

  const assetId = sp.get('asset') ?? DEMO_ASSET
  const date    = sp.get('date')  ?? DEMO_DATE
  const setAsset = (id: string) => setSp(p => { p.set('asset', id); return p })
  const setDate  = (d: string)  => setSp(p => { p.set('date',  d);  return p })

  useEffect(() => { fetchAssets().then(setAssets).catch(console.error) }, [])

  const load = useCallback(async () => {
    if (!assetId || !date) return
    setLoading(true); setError(null)
    try { setData(await fetchTimeline(assetId, date)) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Error') }
    finally { setLoading(false) }
  }, [assetId, date])

  useEffect(() => { load() }, [load])

  const sorted: EvidenceFact[] = data
    ? [...data.facts].sort((a, b) => {
        const pa = FACT_TYPE_PRIORITY[a.fact_type] ?? 99
        const pb = FACT_TYPE_PRIORITY[b.fact_type] ?? 99
        return pa !== pb ? pa - pb : (a.timestamp ?? '').localeCompare(b.timestamp ?? '')
      })
    : []

  const highCount = sorted.filter(f => (FACT_TYPE_PRIORITY[f.fact_type] ?? 99) <= 4).length

  const tabs = [
    { id: 'facts'   as Tab, label: 'Evidence',     Icon: AlertTriangle, count: sorted.length },
    { id: 'sensors' as Tab, label: 'Sensor Reads', Icon: Activity,      count: data?.sensor_readings.length ?? 0 },
    { id: 'oem'     as Tab, label: 'OEM Manuals',  Icon: BookOpen,      count: data?.oem_references.length ?? 0 },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background:'var(--bg)' }}>

      {/* Header */}
      <div className="section-header shrink-0">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                 style={{ background:'rgba(59,130,246,0.1)', border:'1px solid rgba(59,130,246,0.25)' }}>
              <Clock size={17} style={{ color:'#3b82f6' }} />
            </div>
            <div>
              <h1 className="font-semibold text-base t-primary">Time Machine</h1>
              <p className="text-xs t-3">Drag the slider to see every signal on any given date</p>
            </div>
          </div>
          {assetId && (
            <button onClick={() => navCtx.goToGraph(assetId)} className="btn">
              <Network size={13} /> View in graph
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div>
            <label className="block text-[11px] font-semibold t-3 uppercase tracking-wider mb-1.5">Asset</label>
            <AssetPicker assets={assets} value={assetId} onChange={setAsset} disabled={loading} />
          </div>
          <div>
            <label className="block text-[11px] font-semibold t-3 uppercase tracking-wider mb-1.5">Date</label>
            <TimelineSlider value={date} onChange={setDate} assetId={assetId} disabled={loading} />
          </div>
        </div>
      </div>

      {/* Status bar */}
      {data && !loading && (
        <div className="shrink-0 px-6 py-2.5 flex items-center gap-4 text-xs border-b border-base"
             style={{ background: highCount > 0 ? 'rgba(239,68,68,0.04)' : 'var(--bg-2)' }}>
          <span className="t-3">
            Window: <span className="t-2 font-mono font-medium">
              {format(new Date(data.window_start),'d MMM HH:mm')} → {format(new Date(data.window_end),'d MMM HH:mm yyyy')}
            </span>
          </span>
          {highCount > 0 && (
            <span className="flex items-center gap-1.5 font-semibold text-red-500">
              <AlertTriangle size={12} /> {highCount} high-risk signal{highCount>1?'s':''}
            </span>
          )}
          <span className="t-3 ml-auto">{data.asset_name}</span>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 size={24} className="animate-spin t-3" />
          </div>
        )}
        {!loading && error && (
          <div className="m-6 p-4 rounded-xl text-red-600 dark:text-red-400 text-sm
                          bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
            {error}
          </div>
        )}
        {!loading && !error && data && sorted.length === 0 && data.sensor_readings.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-2 t-3">
            <Clock size={28} className="opacity-30" />
            <p className="text-sm t-2">No records in this window.</p>
            <p className="text-xs">Try a different date or asset.</p>
          </div>
        )}
        {!loading && !error && data && (
          <div className="px-6 py-5 space-y-4">
            {/* Tabs */}
            <div className="flex border-b border-base gap-0">
              {tabs.map(({ id, label, Icon, count }) => (
                <button key={id} onClick={() => setTab(id)}
                  className="flex items-center gap-2 px-4 py-3 text-[13px] font-medium
                             border-b-2 -mb-px transition-all"
                  style={tab===id
                    ? { borderColor:'var(--brand)', color:'var(--brand)' }
                    : { borderColor:'transparent', color:'var(--text-3)' }}>
                  <Icon size={14} />
                  {label}
                  <span className="text-[11px] px-1.5 py-0.5 rounded-md font-semibold"
                        style={{ background: tab===id ? 'var(--brand-light)' : 'var(--bg-2)',
                                 color: tab===id ? 'var(--brand)' : 'var(--text-3)' }}>
                    {count}
                  </span>
                </button>
              ))}
            </div>

            {tab === 'facts' && (
              <div className="space-y-2.5">
                {sorted.length === 0
                  ? <p className="text-sm t-3 py-4 text-center">No facts in this window.</p>
                  : sorted.map(fact => (
                      <EvidenceCard key={fact.fact_id} fact={fact}
                        highlight={(FACT_TYPE_PRIORITY[fact.fact_type]??99) <= 1} />
                    ))
                }
              </div>
            )}

            {tab === 'sensors' && <SensorChart readings={data.sensor_readings} />}

            {tab === 'oem' && (
              <div className="space-y-4">
                {data.oem_references.length === 0
                  ? <p className="text-sm t-3 py-4 text-center">No OEM references for this asset.</p>
                  : data.oem_references.map((ref, i) => (
                      <div key={i} className="card p-4 space-y-2">
                        <div className="flex items-center gap-2 text-xs t-3">
                          <BookOpen size={12} />
                          <span className="font-mono font-semibold" style={{ color:'var(--brand)' }}>
                            {ref.doc_id}
                          </span>
                          <span className="t-3">—</span>
                          <span>{ref.relevance_note}</span>
                        </div>
                        <pre className="text-xs t-2 whitespace-pre-wrap font-mono leading-relaxed
                                        rounded-lg p-3 border border-base"
                             style={{ background:'var(--bg-2)' }}>
                          {ref.excerpt}
                        </pre>
                      </div>
                    ))
                }
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
