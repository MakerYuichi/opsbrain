import { useState, useRef, useEffect } from 'react'
import { MessageSquareText, Send, Loader2, User, Bot } from 'lucide-react'
import { askChat, type ChatResponse } from '../api/chat'

interface Message {
  role: 'user' | 'assistant'
  text: string
  sources?: ChatResponse['sources']
}

const SUGGESTIONS = [
  'What warnings preceded the APS-3 explosion?',
  'Why was ST-11 at risk before the leak?',
  'Was there a deferred maintenance pattern on the ladle furnace?',
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function send(question: string) {
    if (!question.trim() || loading) return
    setMessages(m => [...m, { role: 'user', text: question }])
    setInput('')
    setLoading(true)
    try {
      const res = await askChat(question)
      setMessages(m => [...m, { role: 'assistant', text: res.answer, sources: res.sources }])
    } catch {
      setMessages(m => [...m, { role: 'assistant', text: "Something went wrong reaching the backend." }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="shrink-0 border-b border-gray-800 bg-gray-900/80 backdrop-blur px-6 py-4">
        <div className="flex items-center gap-3">
          <MessageSquareText size={20} className="text-emerald-400" />
          <div>
            <h2 className="font-semibold text-white">Ask the Brain</h2>
            <p className="text-xs text-gray-400">Answers are grounded in cited facts from the knowledge graph — not free-form guesses.</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-gray-500">Try asking:</p>
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => send(s)}
                className="block text-left text-sm text-blue-400 hover:text-blue-300 hover:underline">
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
            {m.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-emerald-900/60 flex items-center justify-center shrink-0">
                <Bot size={14} className="text-emerald-400" />
              </div>
            )}
            <div className={`max-w-xl rounded-2xl px-4 py-2.5 text-sm ${
              m.role === 'user' ? 'bg-blue-700 text-white' : 'bg-gray-900 border border-gray-800 text-gray-200'
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
              {m.sources && m.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-800 space-y-1.5">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wide">Sources</p>
                  {m.sources.slice(0, 4).map(s => (
                    <div key={s.fact_id} className="text-[11px] text-gray-500">
                      <span className="font-mono text-blue-400">[{s.fact_id}]</span>{' '}
                      "{s.source_span}"
                    </div>
                  ))}
                </div>
              )}
            </div>
            {m.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-blue-900/60 flex items-center justify-center shrink-0">
                <User size={14} className="text-blue-300" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-gray-500 text-sm">
            <Loader2 size={14} className="animate-spin" /> Thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 border-t border-gray-800 p-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send(input)}
            placeholder="Ask about any asset, incident, or pattern…"
            className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white
                       placeholder-gray-600 focus:outline-none focus:border-blue-600"
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 rounded-xl bg-blue-700 text-white disabled:opacity-40 hover:bg-blue-600 transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}