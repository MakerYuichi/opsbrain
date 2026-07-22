const API_BASE = 'http://localhost:8000'

export interface PlatformStats {
  asset_count: number
  document_count: number
  fact_count: number
  edge_count: number
  sensor_reading_count: number
  alert_count: number
  critical_alert_count: number
  facilities: string[]
}

export async function fetchStats(): Promise<PlatformStats> {
  const res = await fetch(`${API_BASE}/stats`)
  if (!res.ok) throw new Error('Failed to fetch stats')
  return res.json()
}