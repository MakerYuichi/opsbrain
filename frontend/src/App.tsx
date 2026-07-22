import { useEffect, useState, useRef } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { Clock, TrendingUp, Network, LayoutDashboard,
         Activity, MessageSquare, Send, Loader2, Bot, User, X, Brain, Smartphone } from 'lucide-react'
import TimeMachine    from './pages/TimeMachine'
import PatternBreaker from './pages/PatternBreaker'
import GraphExplorer  from './pages/GraphExplorer'
import Dashboard      from './pages/Dashboard'
import Chat           from './pages/Chat'
import Agents         from './pages/Agents'
import MobileField    from './pages/MobileField'
import { fetchAlerts } from './api/patterns'
import { askChat, type ChatResponse } from './api/chat'

export interface NavContext {
  goToTimeMachine: (assetId: string, date?: string) => void
  goToGraph:       (assetId: string) => void
}

const NAV = [
  { to: '/',         end: true,  label: 'Dashboard',       Icon: LayoutDashboard },
  { to: '/timeline', end: false, label: 'Time Machine',    Icon: Clock           },
  { to: '/patterns', end: false, label: 'Pattern Breaker', Icon: TrendingUp      },
  { to: '/graph',    end: false, label: 'Graph Explorer',  Icon: Network         },
  { to: '/agents',   end: false, label: 'AI Agents',       Icon: Brain           },
  { to: '/mobile',   end: false, label: 'Field Mobile',    Icon: Smartphone      },
  { to: '/chat',     end: false, label: 'Chat',            Icon: MessageSquare    },
]

const SUGGESTIONS = [
  'What warnings preceded the APS-3 explosion?',
  'Why was ST-11 at risk before the leak?',
  'Show deferred maintenance on ladle furnace',
]

// ── Floating chat bubble + panel ──────────────────────────────────────────────
interface ChatMsg { role: 'user'|'assistant'; text: string; sources?: ChatResponse['sources'] }

function ChatBubble() {
  const [open,     setOpen]     = useState(false)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input,    setInput]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  async function send(q: string) {
    if (!q.trim() || loading) return
    setMessages(m => [...m, { role: 'user', text: q }])
    setInput('')
    setLoading(true)
    try {
      const res = await askChat(q)
      setMessages(m => [...m, { role: 'assistant', text: res.answer, sources: res.sources }])
    } catch {
      setMessages(m => [...m, { role: 'assistant', text: 'Backend unavailable.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* ── Chat panel ── */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-[380px] flex flex-col rounded-2xl shadow-2xl overflow-hidden"
             style={{ height: '520px', background: 'var(--bg-1)', border: '1px solid var(--border-2)' }}>

          {/* Panel header */}
          <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-base"
               style={{ background: 'var(--bg-2)' }}>
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                   style={{ background: 'linear-gradient(135deg,#6366f1,#3b82f6)' }}>
                KI
              </div>
              <div>
                <p className="text-[13px] font-semibold t-primary">OpsBrain Assistant</p>
                <p className="text-[10px] t-3">Answers grounded in cited facts</p>
              </div>
            </div>
            <button onClick={() => setOpen(false)}
              className="w-7 h-7 rounded-full flex items-center justify-center t-3 hover:t-primary transition-colors"
              style={{ background: 'var(--bg)' }}>
              <X size={14} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="space-y-2">
                <p className="text-[12px] t-3">Try asking:</p>
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)}
                    className="block text-left text-[12px] hover:underline transition-colors"
                    style={{ color: 'var(--brand)' }}>
                    → {s}
                  </button>
                ))}
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex gap-2.5 ${m.role==='user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                       style={{ background: 'var(--brand-light)', color: 'var(--brand)' }}>
                    <Bot size={12} />
                  </div>
                )}
                <div className="max-w-[280px] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed"
                     style={m.role === 'user'
                       ? { background: 'var(--brand)', color: 'white', borderRadius: '18px 4px 18px 18px' }
                       : { background: 'var(--bg-2)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: '4px 18px 18px 18px' }
                     }>
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-2 pt-2 border-t space-y-1" style={{ borderColor: 'var(--border)' }}>
                      <p className="text-[10px] font-semibold t-3 uppercase tracking-wider">Sources</p>
                      {m.sources.slice(0, 3).map(s => (
                        <div key={s.fact_id} className="text-[11px] t-3">
                          <span className="font-mono font-semibold" style={{ color: 'var(--brand)' }}>[{s.fact_id}]</span>{' '}
                          "{s.source_span.slice(0, 60)}{s.source_span.length > 60 ? '…' : ''}"
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {m.role === 'user' && (
                  <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 bg-slate-200 dark:bg-slate-700">
                    <User size={12} className="t-2" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-[12px] t-3">
                <Loader2 size={13} className="animate-spin" /> Thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="shrink-0 p-3 border-t border-base" style={{ background: 'var(--bg-2)' }}>
            <div className="flex gap-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
                placeholder="Ask about any asset or incident…"
                className="input flex-1 text-[13px]"
                style={{ borderRadius: '10px', padding: '8px 12px' }}
              />
              <button onClick={() => send(input)} disabled={loading || !input.trim()}
                className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all disabled:opacity-40"
                style={{ background: 'var(--brand)', color: 'white' }}>
                <Send size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Floating bubble button ── */}
      <button
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-xl
                   flex items-center justify-center transition-all duration-200
                   hover:scale-110 active:scale-95"
        style={{ background: 'linear-gradient(135deg, #6366f1, #3b82f6)' }}
        title="Ask OpsBrain"
      >
        {open
          ? <X size={22} className="text-white" />
          : <MessageSquare size={22} className="text-white" />
        }
        {/* Unread dot — shows when there are messages and panel is closed */}
        {!open && messages.length > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-red-500 rounded-full border-2 border-white" />
        )}
      </button>
    </>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
function Sidebar({ criticalCount }: { criticalCount: number }) {
  return (
    <aside className="w-56 shrink-0 flex flex-col border-r border-base"
           style={{ background: 'var(--bg-1)' }}>

      {/* Brand */}
      <div className="px-4 py-5 border-b border-base">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 text-white font-black text-xs shadow-lg"
               style={{ background: 'linear-gradient(135deg, #6366f1, #3b82f6)' }}>
            KI
          </div>
          <div>
            <p className="font-bold text-[14px] t-primary">OpsBrain</p>
            <p className="text-[10px] t-3 leading-tight">Industrial Intelligence</p>
          </div>
        </div>

        {criticalCount > 0 && (
          <div className="mt-3 flex items-center gap-2 text-[11px] font-semibold text-red-600
                          bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            <Activity size={12} className="shrink-0 animate-pulse" />
            {criticalCount} critical pattern{criticalCount > 1 ? 's' : ''} active
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5">
        <p className="text-[10px] font-semibold t-3 uppercase tracking-widest px-3 mb-2 mt-1">
          Modules
        </p>
        {NAV.map(({ to, end, label, Icon }) => (
          <NavLink key={to} to={to} end={end}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all
               ${isActive ? 'bg-indigo-50 text-indigo-600' : 't-2 hover:bg-slate-50 hover:t-primary'}`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={15} className={isActive ? 'text-indigo-500' : 't-3'} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-base">
        <p className="text-[10px] t-3">ET AI Hackathon 2.0 · PS#8</p>
      </div>
    </aside>
  )
}

// ── Inner app ─────────────────────────────────────────────────────────────────
function InnerApp() {
  const navigate = useNavigate()
  const [criticalCount, setCriticalCount] = useState(0)

  useEffect(() => {
    const refresh = () =>
      fetchAlerts()
        .then(a => setCriticalCount(a.filter(x => x.risk_level === 'CRITICAL').length))
        .catch(() => {})
    refresh()
    const id = setInterval(refresh, 15000)
    return () => clearInterval(id)
  }, [])

  const navCtx: NavContext = {
    goToTimeMachine: (assetId, date) => {
      fetch(`/api/assets/${encodeURIComponent(assetId)}/last-date`)
        .then(r => r.ok ? r.json() : null)
        .then(d => navigate(`/timeline?asset=${assetId}&date=${date ?? d?.date ?? '2025-06-06'}`))
        .catch(() => navigate(`/timeline?asset=${assetId}&date=${date ?? '2025-06-06'}`))
    },
    goToGraph: (assetId) => navigate(`/graph?asset=${assetId}&selected=${assetId}`),
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      <Sidebar criticalCount={criticalCount} />
      <main className="flex-1 min-w-0 overflow-hidden relative" style={{ background: 'var(--bg)' }}>
        <Routes>
          <Route path="/"         element={<Dashboard     navCtx={navCtx} />} />
          <Route path="/timeline" element={<TimeMachine   navCtx={navCtx} />} />
          <Route path="/patterns" element={<PatternBreaker navCtx={navCtx} />} />
          <Route path="/graph"    element={<GraphExplorer  navCtx={navCtx} />} />
          <Route path="/agents"   element={<Agents        navCtx={navCtx} />} />
          <Route path="/mobile"   element={<MobileField   navCtx={navCtx} />} />
          <Route path="/chat"     element={<Chat />} />
        </Routes>
        {/* Floating chat bubble — always visible, on top of everything */}
        <ChatBubble />
      </main>
    </div>
  )
}

export default function App() {
  return <BrowserRouter><InnerApp /></BrowserRouter>
}
