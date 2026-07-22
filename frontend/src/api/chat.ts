const BASE = '/api'

export interface CitedFact {
  fact_id:     string
  content:     string
  source_span: string
  doc_id:      string
  confidence:  number
}

export interface HistoryMessage {
  role: 'user' | 'assistant'
  text: string
}

export interface ChatResponse {
  answer:  string
  sources: CitedFact[]
}

export async function askChat(
  question: string,
  history:  HistoryMessage[] = [],
): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ question, history }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}
