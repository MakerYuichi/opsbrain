import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Network, Loader2, Info, ZoomIn, ZoomOut, Maximize2, Eye, EyeOff, Clock, TrendingUp } from 'lucide-react'
import { format } from 'date-fns'

import { fetchSubgraph } from '../api/graph'
import { fetchAssets }   from '../api/timeline'
import type { GraphNode, SubgraphResponse } from '../types/graph'
import type { AssetItem } from '../types/timeline'
import { EDGE_COLORS } from '../types/graph'
import type { NavContext } from '../App'
import AssetPicker from '../components/AssetPicker'
import ForceGraph, { type ForceGraphHandle } from '../components/ForceGraph'

interface Props { navCtx: NavContext }

function NodeDetail({ node, navCtx, onNavigate }: {
  node: GraphNode
  navCtx: NavContext
  onNavigate: (id: string) => void
}) {
  const isAsset = node.node_type === 'asset'
  const isDoc   = node.node_type === 'document'
  const ts = node.timestamp
    ? (() => { try { return format(new Date(node.timestamp!), 'd MMM yyyy') } catch { return node.timestamp } })()
    : null

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wide
          ${isAsset ? 'bg-blue-900 text-blue-200 border-blue-700'
          : isDoc   ? 'bg-green-900 text-green-200 border-green-700'
          :           'bg-gray-800 text-gray-300 border-gray-700'}`}>
          {node.node_type}
        </span>
        {isAsset && node.asset_type && (
          <span className="text-[10px] text-gray-500 capitalize">{node.asset_type.replace(/_/g, ' ')}</span>
        )}
        {isDoc && node.doc_type && (
          <span className="text-[10px] text-gray-500 capitalize">{node.doc_type.replace(/_/g, ' ')}</span>
        )}
        {node.fact_type && (
          <span className="text-[10px] font-semibold text-orange-300">{node.fact_type.replace(/_/g, ' ')}</span>
        )}
      </div>

      <p className="font-mono text-sm text-white break-all">{node.id}</p>
      {node.label !== node.id && <p className="text-sm text-gray-300">{node.label}</p>}
      {node.location && <p className="text-xs text-gray-500">{node.location}</p>}
      {ts && <p className="text-xs text-gray-500">{ts}</p>}
      {node.content && (
        <p className="text-xs text-gray-300 leading-relaxed bg-gray-800/60 rounded p-2 border border-gray-700">
          {node.content}
        </p>
      )}
      {(node.alert_ids?.length ?? 0) > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Linked alerts</p>
          <div className="flex flex-wrap gap-1">
            {node.alert_ids.map(aid => (
              <span key={aid} className="text-[10px] font-mono px-1.5 py-0.5 rounded
                                         bg-red-950/60 text-red-300 border border-red-800">{aid}</span>
            ))}
          </div>
        </div>
      )}

      {/* Asset actions */}
      {isAsset && (
        <div className="space-y-1.5 pt-1">
          <button onClick={() => onNavigate(node.id)}
            className="w-full text-xs py-1.5 rounded-lg bg-blue-800/60 border border-blue-700
                       text-blue-200 hover:bg-blue-700/60 transition-colors">
            Re-center graph on {node.id} →
          </button>
          <button onClick={() => navCtx.goToTimeMachine(node.id)}
            className="w-full flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg
                       bg-gray-800 border border-gray-700 text-gray-300 hover:text-white transition-colors">
            <Clock size={12} /> Open in Time Machine
          </button>
          {(node.alert_ids?.length ?? 0) > 0 && (
            <button onClick={() => navCtx.goToGraph(node.id)}
              className="w-full flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg
                         bg-orange-900/30 border border-orange-800 text-orange-300 hover:bg-orange-900/50 transition-colors">
              <TrendingUp size={12} /> View patterns
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function GraphExplorer({ navCtx }: Props) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [assets,    setAssets]    = useState<AssetItem[]>([])
  const [depth,     setDepth]     = useState(2)
  const [showFacts, setShowFacts] = useState(false)
  const [graphData, setGraphData] = useState<SubgraphResponse | null>(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState<string | null>(null)
  const [selected,  setSelected]  = useState<GraphNode | null>(null)
  const [dims,      setDims]      = useState({ w: 0, h: 0 })

  const assetId  = searchParams.get('asset') ?? 'APS-3'
  const autoSelectId = searchParams.get('selected') ?? null
  const setAsset = (id: string) => setSearchParams(p => { p.set('asset', id); p.delete('selected'); return p })

  const fgRef     = useRef<ForceGraphHandle>(null)
  const canvasRef = useRef<HTMLDivElement>(null)

  useEffect(() => { fetchAssets().then(setAssets).catch(console.error) }, [])

  useEffect(() => {
    const el = canvasRef.current
    if (!el) return
    const measure = () => setDims({ w: el.clientWidth, h: el.clientHeight })
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const load = useCallback(async (id: string, d: number, sf: boolean) => {
    if (!id) return
    setLoading(true); setError(null); setSelected(null)
    try { setGraphData(await fetchSubgraph(id, d, sf)) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Unknown error') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load(assetId, depth, showFacts) }, [assetId, depth, showFacts, load])

  // Auto-select node when arriving via deep-link (?selected=APS-3)
  // Use a ref so this survives the setSelected(null) inside load()
  const pendingSelectRef = useRef<string | null>(null)

  // Capture autoSelectId into ref whenever it changes
  useEffect(() => {
    if (autoSelectId) pendingSelectRef.current = autoSelectId
  }, [autoSelectId])

  // Apply selection once graphData is ready and we have a pending select
  useEffect(() => {
    const targetId = pendingSelectRef.current
    if (!graphData || !targetId) return
    const node = graphData.nodes.find(n => n.id === targetId)
    if (node) {
      setSelected(node)
      pendingSelectRef.current = null  // consume it
    }
  }, [graphData])

  const handleNodeClick = useCallback((node: GraphNode) => setSelected(node), [])
  const navigateTo      = useCallback((id: string)      => { setAsset(id); setSelected(null) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 shrink-0 border-r border-base flex flex-col overflow-hidden" style={{ background: 'var(--bg-1)' }}>
        <div className="shrink-0 p-4 border-b border-base space-y-3">
          <div className="flex items-center gap-2">
            <Network size={16} className="text-blue-500" />
            <h2 className="font-semibold text-sm t-primary">Graph Explorer</h2>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-medium t-3 uppercase tracking-wide">Root Asset</label>
            <AssetPicker assets={assets} value={assetId} onChange={setAsset} disabled={loading} />
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 space-y-1">
              <label className="text-[10px] font-medium t-3 uppercase tracking-wide">Depth</label>
              <div className="flex gap-1">
                {[1, 2, 3].map(d => (
                  <button key={d} onClick={() => setDepth(d)}
                    className={`flex-1 py-1 text-xs rounded border transition-colors
                      ${depth === d ? 'bg-blue-500 border-blue-400 text-white' : 'bg-white border-gray-200 t-2 hover:t-primary'}`}>
                    {d}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-medium t-3 uppercase tracking-wide">Facts</label>
              <button onClick={() => setShowFacts(f => !f)}
                className={`flex items-center justify-center w-full py-1 px-2 text-xs rounded border transition-colors
                  ${showFacts ? 'bg-orange-500 border-orange-400 text-white' : 'bg-white border-gray-200 t-2 hover:t-primary'}`}>
                {showFacts ? <Eye size={13} /> : <EyeOff size={13} />}
              </button>
            </div>
          </div>
        </div>

        {graphData && !loading && (
          <div className="shrink-0 px-4 py-2 border-b border-base flex gap-4 text-xs t-3">
            <span>{graphData.total_nodes} nodes</span>
            <span>{graphData.total_edges} edges</span>
          </div>
        )}

        {/* Legend */}
        <div className="shrink-0 px-4 py-3 border-b border-base space-y-1.5">
          <p className="text-[10px] uppercase tracking-wide t-3">Nodes</p>
          {[
            { color: '#8b5cf6', label: 'Purging / process asset' },
            { color: '#f97316', label: 'Ladle / furnace' },
            { color: '#3b82f6', label: 'Other asset' },
            { color: '#16a34a', label: 'Document' },
            { color: '#f87171', label: 'High-risk fact' },
          ].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-2 text-xs t-2">
              <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
              {label}
            </div>
          ))}
          <p className="text-[10px] uppercase tracking-wide t-3 mt-2">Edges</p>
          {Object.entries(EDGE_COLORS).filter(([k]) => k !== 'RELATED').map(([rel, color]) => (
            <div key={rel} className="flex items-center gap-2 text-[10px] t-2">
              <span className="w-5 h-0.5 shrink-0 rounded" style={{ background: color }} />
              {rel.replace(/_/g, ' ')}
            </div>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {selected
            ? <NodeDetail node={selected} navCtx={navCtx} onNavigate={navigateTo} />
            : (
              <div className="flex flex-col items-center justify-center h-full t-3 gap-2">
                <Info size={20} className="opacity-40" />
                <p className="text-xs text-center">Click any node to inspect it</p>
              </div>
            )
          }
        </div>
      </div>

      {/* Canvas */}
      <div ref={canvasRef} className="flex-1 relative overflow-hidden" style={{ background: 'var(--bg)' }}>
        <div className="absolute top-3 right-3 z-10 flex flex-col gap-1">
          {[
            { Icon: ZoomIn,    fn: () => fgRef.current?.zoomIn(),  tip: 'Zoom in'   },
            { Icon: ZoomOut,   fn: () => fgRef.current?.zoomOut(), tip: 'Zoom out'  },
            { Icon: Maximize2, fn: () => fgRef.current?.zoomFit(), tip: 'Fit graph' },
          ].map(({ Icon, fn, tip }) => (
            <button key={tip} onClick={fn} title={tip}
              className="p-1.5 rounded bg-white border border-gray-200
                         t-2 hover:t-primary transition-colors shadow-sm">
              <Icon size={14} />
            </button>
          ))}
        </div>

        {graphData && !loading && (
          <div className="absolute top-3 left-3 z-10 text-xs bg-white border border-gray-200
                          rounded-lg px-3 py-1.5 shadow-sm t-2 pointer-events-none">
            <span className="font-mono text-blue-500">{graphData.root_id}</span>
            <span className="ml-2 t-3">depth {depth}</span>
            {showFacts && <span className="ml-2 text-orange-500">· facts on</span>}
          </div>
        )}

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-20">
            <Loader2 size={32} className="text-blue-500 animate-spin" />
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600 text-sm max-w-sm text-center">
              {error}
            </div>
          </div>
        )}

        {graphData && dims.w > 0 && dims.h > 0 && !loading && (
          <ForceGraph
            ref={fgRef}
            data={graphData}
            width={dims.w}
            height={dims.h}
            onNodeClick={handleNodeClick}
            selectedId={selected?.id}
          />
        )}
      </div>
    </div>
  )
}
