import { useState, useRef, useEffect } from 'react'
import { Search, ChevronDown, X } from 'lucide-react'
import type { AssetItem } from '../types/timeline'

const TYPE_ICONS: Record<string,string> = {
  tank:'🛢',chiller:'❄️',sensor:'📡',valve:'🔧',pump:'⚙️',
  ladle_furnace:'🔥',ladle:'🪣',purging_station:'💨',
  coke_oven_battery:'🏭',blast_furnace:'⚡',crane:'🏗',
  process_unit:'🏗',casting_machine:'⚙️',facility:'🏢',
  instrument:'📏',unknown:'◦',
}

export default function AssetPicker({ assets, value, onChange, disabled }: {
  assets: AssetItem[]; value: string; onChange: (id:string) => void; disabled?: boolean
}) {
  const [open,  setOpen]  = useState(false)
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const wrapRef  = useRef<HTMLDivElement>(null)
  const selected = assets.find(a => a.asset_id === value)

  const filtered = query.trim()
    ? assets.filter(a =>
        a.name.toLowerCase().includes(query.toLowerCase()) ||
        a.asset_id.toLowerCase().includes(query.toLowerCase()))
    : assets

  useEffect(() => { if (open) inputRef.current?.focus() }, [open])
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) { setOpen(false); setQuery('') }
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  return (
    <div ref={wrapRef} className="relative w-full">
      <button disabled={disabled} onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2
                   rounded-lg border border-base text-[13px] transition-all
                   hover:border-[var(--border-2)] focus:outline-none disabled:opacity-50"
        style={{ background:'var(--bg-1)', color:'var(--text)' }}>
        <span className="flex items-center gap-2 truncate min-w-0">
          {selected ? (
            <>
              <span className="text-base shrink-0">{TYPE_ICONS[selected.type]??'◦'}</span>
              <span className="font-mono text-[12px] font-semibold shrink-0" style={{ color:'var(--brand)' }}>
                {selected.asset_id}
              </span>
              <span className="t-2 truncate text-[12px]">{selected.name}</span>
            </>
          ) : (
            <span className="t-3 text-[12px]">Select an asset…</span>
          )}
        </span>
        {value
          ? <X size={13} className="shrink-0 t-3" onClick={e => { e.stopPropagation(); onChange('') }} />
          : <ChevronDown size={13} className="shrink-0 t-3" />}
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-xl shadow-xl border"
             style={{ background:'var(--bg-1)', borderColor:'var(--border-2)' }}>
          <div className="sticky top-0 px-3 py-2 border-b border-base" style={{ background:'var(--bg-1)' }}>
            <div className="flex items-center gap-2 rounded-lg px-2.5 border border-base" style={{ background:'var(--bg-2)' }}>
              <Search size={12} className="t-3 shrink-0" />
              <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)}
                placeholder="Search assets…"
                className="w-full bg-transparent py-1.5 text-[12px] focus:outline-none t-primary placeholder:t-3" />
            </div>
          </div>
          {filtered.length === 0
            ? <p className="px-4 py-3 text-[12px] t-3">No results</p>
            : filtered.map(a => (
                <button key={a.asset_id} onClick={() => { onChange(a.asset_id); setOpen(false); setQuery('') }}
                  className={`w-full flex items-start gap-3 px-4 py-2.5 text-left transition-colors
                              hover:bg-[var(--bg-2)]
                              ${a.asset_id===value ? 'bg-[var(--brand-light)]' : ''}`}>
                  <span className="text-base mt-0.5 shrink-0">{TYPE_ICONS[a.type]??'◦'}</span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] font-semibold" style={{ color:'var(--brand)' }}>{a.asset_id}</span>
                      <span className="text-[10px] t-3 capitalize">{a.type.replace(/_/g,' ')}</span>
                    </div>
                    <p className="text-[12px] t-2 truncate">{a.name}</p>
                  </div>
                </button>
              ))
          }
        </div>
      )}
    </div>
  )
}
