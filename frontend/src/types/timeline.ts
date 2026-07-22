export interface SourceSpan {
  start: number
  end: number
  text: string
}

export interface EvidenceFact {
  fact_id: string
  doc_id: string
  doc_type: string | null
  asset_id: string | null
  fact_type: string
  timestamp: string | null
  content: string
  source_span: SourceSpan
  confidence: number
  raw_text_excerpt: string | null
}

export interface SensorPoint {
  sensor_id: string
  timestamp: string
  metric: string
  value: number | null
  unit: string
  status: string
  notes: string
}

export interface OEMReference {
  doc_id: string
  excerpt: string
  relevance_note: string
}

export interface TimelineResponse {
  asset_id: string
  asset_name: string
  window_start: string
  window_end: string
  facts: EvidenceFact[]
  sensor_readings: SensorPoint[]
  oem_references: OEMReference[]
}

export interface AssetItem {
  asset_id: string
  name: string
  type: string
  location: string | null
}

// Fact type → colour mapping for badges
export const FACT_TYPE_COLORS: Record<string, string> = {
  INCIDENT_EVENT:          'bg-red-900 text-red-200 border-red-700',
  SAFETY_VIOLATION:        'bg-orange-900 text-orange-200 border-orange-700',
  DEFERRED_MAINTENANCE:    'bg-yellow-900 text-yellow-200 border-yellow-700',
  INSTRUMENT_FAULT:        'bg-amber-900 text-amber-200 border-amber-700',
  RISK_OBSERVATION:        'bg-purple-900 text-purple-200 border-purple-700',
  SHIFT_OBSERVATION:       'bg-blue-900 text-blue-200 border-blue-700',
  ALARM_RESPONSE:          'bg-pink-900 text-pink-200 border-pink-700',
  MAINTENANCE_ACTION:      'bg-teal-900 text-teal-200 border-teal-700',
  WORK_ORDER:              'bg-cyan-900 text-cyan-200 border-cyan-700',
  PROCESS_PARAMETER:       'bg-slate-700 text-slate-200 border-slate-500',
  TEMPERATURE_READING:     'bg-green-900 text-green-200 border-green-700',
  INHIBITOR_DOSING:        'bg-lime-900 text-lime-200 border-lime-700',
  DISSOLVED_OXYGEN_READING:'bg-emerald-900 text-emerald-200 border-emerald-700',
  QUALITY_READING:         'bg-indigo-900 text-indigo-200 border-indigo-700',
  PERMIT_STATUS:           'bg-violet-900 text-violet-200 border-violet-700',
}

export const FACT_TYPE_PRIORITY: Record<string, number> = {
  INCIDENT_EVENT: 0,
  SAFETY_VIOLATION: 1,
  DEFERRED_MAINTENANCE: 2,
  INSTRUMENT_FAULT: 3,
  ALARM_RESPONSE: 4,
  RISK_OBSERVATION: 5,
  SHIFT_OBSERVATION: 6,
  WORK_ORDER: 7,
  MAINTENANCE_ACTION: 8,
  PERMIT_STATUS: 9,
  PROCESS_PARAMETER: 10,
  QUALITY_READING: 11,
  TEMPERATURE_READING: 12,
  INHIBITOR_DOSING: 13,
  DISSOLVED_OXYGEN_READING: 14,
}
