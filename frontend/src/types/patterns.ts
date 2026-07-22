export interface AlertSummary {
  alert_id: string
  asset_id: string | null
  pattern_type: string
  description: string
  confidence: number
  source_fact_count: number
  created_at: string
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
}

export interface SupportingFact {
  fact_id: string
  doc_id: string
  doc_type: string | null
  asset_id: string | null
  fact_type: string
  timestamp: string | null
  content: string
  source_span_text: string
  confidence: number
}

export interface AlertDetail extends AlertSummary {
  supporting_facts: SupportingFact[]
}

export interface RunStatus {
  running: boolean
  last_run: string | null
  last_count: number
  error: string | null
}

export const RISK_COLORS: Record<string, string> = {
  CRITICAL: 'border-red-700 bg-red-950/30',
  HIGH:     'border-orange-700 bg-orange-950/20',
  MEDIUM:   'border-yellow-700 bg-yellow-950/20',
  LOW:      'border-gray-700 bg-gray-900/40',
  UNKNOWN:  'border-gray-700 bg-gray-900/40',
}

export const RISK_BADGE: Record<string, string> = {
  CRITICAL: 'bg-red-900 text-red-200 border-red-700',
  HIGH:     'bg-orange-900 text-orange-200 border-orange-700',
  MEDIUM:   'bg-yellow-900 text-yellow-200 border-yellow-700',
  LOW:      'bg-gray-800 text-gray-300 border-gray-600',
  UNKNOWN:  'bg-gray-800 text-gray-400 border-gray-700',
}
