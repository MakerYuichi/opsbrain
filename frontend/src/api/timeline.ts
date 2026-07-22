import type { AssetItem, TimelineResponse } from '../types/timeline'

const BASE = '/api'

export async function fetchAssets(): Promise<AssetItem[]> {
  const res = await fetch(`${BASE}/assets`)
  if (!res.ok) throw new Error(`Failed to fetch assets: ${res.status}`)
  return res.json()
}

export async function fetchTimeline(
  assetId: string,
  date: string,
  windowHours = 24,
): Promise<TimelineResponse> {
  const params = new URLSearchParams({
    asset_id: assetId,
    date,
    window_hours: String(windowHours),
  })
  const res = await fetch(`${BASE}/timeline?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Timeline API error ${res.status}`)
  }
  return res.json()
}
