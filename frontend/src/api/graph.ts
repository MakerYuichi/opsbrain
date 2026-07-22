import type { SubgraphResponse } from '../types/graph'

const BASE = '/api'

export async function fetchSubgraph(
  assetId:   string,
  depth      = 2,
  showFacts  = false,
): Promise<SubgraphResponse> {
  const params = new URLSearchParams({
    asset_id:   assetId,
    depth:      String(depth),
    show_facts: String(showFacts),
  })
  const res = await fetch(`${BASE}/graph?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Graph API error ${res.status}`)
  }
  return res.json()
}
