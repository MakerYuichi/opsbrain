export interface GraphNode {
  id: string
  label: string
  node_type: 'asset' | 'document' | 'fact'
  asset_type?: string | null
  doc_type?: string | null
  location?: string | null
  fact_type?: string | null
  timestamp?: string | null
  content?: string | null
  alert_ids: string[]
  depth: number
  is_root?: boolean
}

export interface GraphEdge {
  source: string
  target: string
  relation: string
  weight: number
}

export interface SubgraphResponse {
  root_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

// ── Visual styling ────────────────────────────────────────────────────────────

export const NODE_COLORS: Record<string, string> = {
  tank:              '#3b82f6',
  chiller:           '#06b6d4',
  purging_station:   '#8b5cf6',
  ladle_furnace:     '#f97316',
  ladle:             '#fb923c',
  coke_oven_battery: '#a16207',
  blast_furnace:     '#dc2626',
  crane:             '#6b7280',
  process_unit:      '#4b5563',
  casting_machine:   '#7c3aed',
  facility:          '#1d4ed8',
  sensor:            '#0ea5e9',
  valve:             '#64748b',
  pump:              '#475569',
  instrument:        '#0284c7',
  unknown:           '#374151',
  document:          '#16a34a',
  fact:              '#475569',
}

export const EDGE_COLORS: Record<string, string> = {
  ASSET_IN_DOCUMENT:  '#22c55e',
  SHARES_ASSET:       '#3b82f6',
  CAUSAL_SEQUENCE:    '#ef4444',
  CROSS_REFERENCE:    '#a855f7',
  FACT_IN_DOCUMENT:   '#6b7280',
  RELATED:            '#374151',
}

export function nodeColor(node: GraphNode): string {
  if (node.node_type === 'asset') {
    return NODE_COLORS[node.asset_type ?? 'unknown'] ?? NODE_COLORS.unknown
  }
  if (node.node_type === 'document') return NODE_COLORS.document
  const highRisk = ['INCIDENT_EVENT','SAFETY_VIOLATION','DEFERRED_MAINTENANCE','INSTRUMENT_FAULT','ALARM_RESPONSE']
  if (node.fact_type && highRisk.includes(node.fact_type)) return '#f87171'
  return NODE_COLORS.fact
}

export function nodeRadius(node: GraphNode, isRoot: boolean): number {
  if (isRoot)                        return 16
  if (node.node_type === 'asset')    return 10
  if (node.alert_ids?.length > 0)   return 9
  if (node.node_type === 'document') return 7
  return 4   // fact
}
