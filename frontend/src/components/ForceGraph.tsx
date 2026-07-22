/**
 * ForceGraph.tsx — React wrapper around `force-graph` vanilla JS.
 *
 * Key facts about force-graph (v1.51.4):
 *   - Default export is a CLASS → requires `new ForceGraph(domElement)`
 *   - Methods are chainable when called with args
 *   - d3Force('charge') returns the d3 force object, NOT the graph instance
 *     so .strength() must be called on the force separately, not in the chain
 */
import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import type { GraphNode, SubgraphResponse } from '../types/graph'
import { nodeColor, nodeRadius, EDGE_COLORS } from '../types/graph'

interface FGNode extends GraphNode { x?: number; y?: number }
interface FGLink { source: string | FGNode; target: string | FGNode; relation: string; weight: number }

export interface ForceGraphHandle {
  zoomIn():  void
  zoomOut(): void
  zoomFit(): void
}

interface Props {
  data:        SubgraphResponse
  width:       number
  height:      number
  onNodeClick: (node: FGNode) => void
  selectedId?: string
}

const ForceGraph = forwardRef<ForceGraphHandle, Props>(
  ({ data, width, height, onNodeClick, selectedId }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const gRef = useRef<any>(null)

    useImperativeHandle(ref, () => ({
      zoomIn()  { if (gRef.current) { const z = gRef.current.zoom(); gRef.current.zoom(z * 1.5, 300) } },
      zoomOut() { if (gRef.current) { const z = gRef.current.zoom(); gRef.current.zoom(z * 0.67, 300) } },
      zoomFit() { gRef.current?.zoomToFit(500, 60) },
    }))

    useEffect(() => {
      const el = containerRef.current
      if (!el) return
      let alive = true

      import('force-graph').then(mod => {
        if (!alive || !containerRef.current) return

        // ── Destroy old instance cleanly ──────────────────────────────
        if (gRef.current) {
          try { gRef.current._destructor() } catch { /* ok */ }
          containerRef.current.innerHTML = ''
        }

        // ── Instantiate — MUST use `new` ─────────────────────────────
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const FG    = (mod.default ?? mod) as any
        const graph = new FG(containerRef.current)
        gRef.current = graph

        // ── Physics: tune d3 forces BEFORE setting graphData ─────────
        // Note: d3Force() returns the force object, not the graph —
        // do NOT chain .strength() in the main fluent chain.
        const chargeForce = graph.d3Force('charge')
        if (chargeForce?.strength) chargeForce.strength(-350)

        const linkForce = graph.d3Force('link')
        if (linkForce?.distance) {
          linkForce.distance((link: FGLink) => {
            if (link.relation === 'ASSET_IN_DOCUMENT')  return 120
            if (link.relation === 'SHARES_ASSET')        return 200
            if (link.relation === 'CAUSAL_SEQUENCE')     return 170
            return 150
          })
        }

        // ── Configure and load data ───────────────────────────────────
        graph
          .width(width)
          .height(height)
          .backgroundColor('#030712')
          .cooldownTicks(200)
          .warmupTicks(80)

          // Node rendering
          .nodeCanvasObject((node: FGNode, ctx: CanvasRenderingContext2D, gs: number) => {
            const isRoot   = node.id === data.root_id
            const isSelect = node.id === selectedId
            const r   = nodeRadius(node, isRoot)
            const col = nodeColor(node)
            const x   = node.x ?? 0
            const y   = node.y ?? 0

            // Shadow/glow
            if (isRoot || isSelect) {
              ctx.shadowBlur  = isRoot ? 16 : 8
              ctx.shadowColor = isRoot ? '#60a5fa' : '#ffffff'
            } else {
              ctx.shadowBlur = 0
            }

            // Alert ring
            if ((node.alert_ids?.length ?? 0) > 0) {
              ctx.beginPath()
              ctx.arc(x, y, r + 3, 0, 2 * Math.PI)
              ctx.strokeStyle = '#ef4444'
              ctx.lineWidth   = 2
              ctx.stroke()
            }

            // Main fill
            ctx.shadowBlur = 0
            ctx.beginPath()
            ctx.arc(x, y, r, 0, 2 * Math.PI)
            ctx.fillStyle = col
            ctx.fill()
            ctx.strokeStyle = isSelect ? '#fff' : isRoot ? '#93c5fd' : 'rgba(0,0,0,0.35)'
            ctx.lineWidth   = isSelect ? 2.5 : isRoot ? 2 : 0.8
            ctx.stroke()

            // Label (assets always, docs when zoomed in)
            const showLabel =
              node.node_type === 'asset' ||
              (node.node_type === 'document' && gs > 0.65) ||
              isSelect

            if (showLabel) {
              const lbl = node.node_type === 'asset'
                ? node.id
                : node.id.replace(/VSP-|LGP-/g, '')
              const fs = Math.max(9, 11 / gs)
              const tw = ctx.measureText(lbl).width

              ctx.font = `${isRoot ? 'bold ' : ''}${fs}px system-ui,sans-serif`

              // Pill background for readability over edges
              ctx.fillStyle = 'rgba(3,7,18,0.72)'
              ctx.fillRect(x - tw / 2 - 3, y + r + 2, tw + 6, fs + 4)

              ctx.fillStyle    = isRoot ? '#93c5fd' : node.node_type === 'document' ? '#86efac' : '#e5e7eb'
              ctx.textAlign    = 'center'
              ctx.textBaseline = 'top'
              ctx.fillText(lbl, x, y + r + 4)
            }
          })
          .nodeCanvasObjectMode(() => 'replace')

          // Pointer hit area slightly larger than visual circle
          .nodePointerAreaPaint((node: FGNode, paintColor: string, ctx: CanvasRenderingContext2D) => {
            ctx.beginPath()
            ctx.arc(node.x ?? 0, node.y ?? 0, nodeRadius(node, node.id === data.root_id) + 5, 0, 2 * Math.PI)
            ctx.fillStyle = paintColor
            ctx.fill()
          })

          // Link styling
          .linkColor((link: FGLink)  => EDGE_COLORS[link.relation] ?? '#374151')
          .linkWidth((link: FGLink) => {
            if (link.relation === 'CAUSAL_SEQUENCE')   return 2.2
            if (link.relation === 'ASSET_IN_DOCUMENT') return 1.8
            if (link.relation === 'SHARES_ASSET')      return 1.2
            return 0.8
          })
          .linkLineDash((link: FGLink) => link.relation === 'FACT_IN_DOCUMENT' ? [4, 4] : null)
          .linkDirectionalArrowLength((link: FGLink) => link.relation === 'CAUSAL_SEQUENCE' ? 6 : 0)
          .linkDirectionalArrowRelPos(1)
          .linkDirectionalParticles((link: FGLink) => link.relation === 'CAUSAL_SEQUENCE' ? 3 : 0)
          .linkDirectionalParticleSpeed(0.003)
          .linkDirectionalParticleWidth(2)
          .linkDirectionalParticleColor(() => '#fca5a5')

          // Tooltip on hover
          .nodeLabel((node: FGNode) => {
            const lines = [`[${node.node_type}] ${node.id}`]
            if (node.content)            lines.push(node.content.slice(0, 90))
            if (node.fact_type)          lines.push(`Type: ${node.fact_type}`)
            if (node.timestamp)          lines.push(`Date: ${String(node.timestamp).slice(0, 10)}`)
            if (node.alert_ids?.length)  lines.push(`⚠ ${node.alert_ids.length} alert(s)`)
            return lines.join('\n')
          })

          // Callbacks
          .onNodeClick(onNodeClick)
          .onEngineStop(() => graph.zoomToFit(500, 60))

          // Data — set last so forces are configured before simulation starts
          .graphData({
            nodes: data.nodes.map(n => ({ ...n })),
            links: data.edges.map(e => ({
              source: e.source, target: e.target,
              relation: e.relation, weight: e.weight,
            })),
          })
      })

      return () => {
        alive = false
        if (gRef.current) {
          try { gRef.current._destructor() } catch { /* ok */ }
          gRef.current = null
        }
      }
    // Rebuild when data or dimensions change
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data, width, height])

    // Sync dimensions without full rebuild
    useEffect(() => {
      if (gRef.current) gRef.current.width(width).height(height)
    }, [width, height])

    return (
      <div
        ref={containerRef}
        style={{ width, height, display: 'block' }}
      />
    )
  }
)

ForceGraph.displayName = 'ForceGraph'
export default ForceGraph
