import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Clock, TrendingUp, Network } from 'lucide-react'

// Placeholder pages — implementations come in later phases
const TimeMachine  = () => <div className="p-8 text-gray-400">Time Machine — coming in Phase 2</div>
const PatternBreaker = () => <div className="p-8 text-gray-400">Pattern Breaker — coming in Phase 2</div>
const GraphExplorer  = () => <div className="p-8 text-gray-400">Graph Explorer — coming in Phase 2</div>

const navItems = [
  { to: '/',         label: 'Time Machine',   Icon: Clock        },
  { to: '/patterns', label: 'Pattern Breaker', Icon: TrendingUp   },
  { to: '/graph',    label: 'Graph Explorer',  Icon: Network      },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-950">
        {/* Sidebar */}
        <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
          <div className="p-5 border-b border-gray-800">
            <h1 className="text-sm font-bold text-industrial-500 uppercase tracking-widest">
              Industrial KI
            </h1>
            <p className="text-xs text-gray-500 mt-1">Knowledge Intelligence</p>
          </div>
          <nav className="flex-1 p-3 space-y-1">
            {navItems.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'bg-industrial-700 text-white'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                  }`
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
            ET AI Hackathon 2.0 · PS#8
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/"         element={<TimeMachine />} />
            <Route path="/patterns" element={<PatternBreaker />} />
            <Route path="/graph"    element={<GraphExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
