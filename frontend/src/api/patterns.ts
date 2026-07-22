import type { AlertSummary, AlertDetail, RunStatus } from '../types/patterns'

const BASE = '/api'

export async function fetchAlerts(assetId?: string): Promise<AlertSummary[]> {
  const params = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
  const res = await fetch(`${BASE}/alerts${params}`)
  if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`)
  return res.json()
}

export async function fetchAlert(alertId: string): Promise<AlertDetail> {
  const res = await fetch(`${BASE}/alerts/${encodeURIComponent(alertId)}`)
  if (!res.ok) throw new Error(`Failed to fetch alert: ${res.status}`)
  return res.json()
}

export async function triggerDetection(force = false): Promise<void> {
  const res = await fetch(`${BASE}/alerts/run?force=${force}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Detection trigger failed: ${res.status}`)
  }
}

export async function fetchRunStatus(): Promise<RunStatus> {
  const res = await fetch(`${BASE}/alerts/run/status`)
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`)
  return res.json()
}
