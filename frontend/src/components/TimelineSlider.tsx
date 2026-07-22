import { useCallback, useMemo } from 'react'
import { format } from 'date-fns'

interface Props {
  value:     string
  onChange:  (date: string) => void
  assetId?:  string
  disabled?: boolean
}

function dateToNum(d: string) { return new Date(d).getTime() }
function numToDate(n: number) { return format(new Date(n), 'yyyy-MM-dd') }

const VSP_MARKERS = [
  { date: '2025-04-14', label: 'PM bypassed',       dot: '#eab308' },
  { date: '2025-05-08', label: 'Purge skips',        dot: '#f97316' },
  { date: '2025-05-15', label: 'WO downgraded',      dot: '#ef4444' },
  { date: '2025-06-06', label: '💥 Explosion',        dot: '#dc2626' },
]
const LGP_MARKERS = [
  { date: '2019-07-14', label: 'Near-miss',           dot: '#eab308' },
  { date: '2019-10-03', label: 'DISH audit',           dot: '#f97316' },
  { date: '2020-03-23', label: 'Shutdown gaps',        dot: '#f97316' },
  { date: '2020-04-19', label: 'Temp >limit',          dot: '#ef4444' },
  { date: '2020-05-07', label: '💥 Gas leak',           dot: '#dc2626' },
]
const LGP_ASSETS = new Set(['ST-11','ST-09','ST-10','CHR-01','RTD-11','FT-11','NV-11',
                             'P-01','P-02','P-03','P-04','FACILITY-LGP','IRIR-PORTABLE'])

function cfg(assetId?: string) {
  return LGP_ASSETS.has(assetId ?? '')
    ? { min:'2019-01-01', max:'2020-06-01', markers: LGP_MARKERS }
    : { min:'2025-04-01', max:'2025-06-10', markers: VSP_MARKERS }
}

export default function TimelineSlider({ value, onChange, assetId, disabled }: Props) {
  const { min, max, markers } = useMemo(() => cfg(assetId), [assetId])
  const minMs = dateToNum(min)
  const maxMs = dateToNum(max)
  const val   = (() => { const v = dateToNum(value||min); return Math.min(Math.max(v,minMs),maxMs) })()

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => onChange(numToDate(Number(e.target.value))),
    [onChange],
  )

  const displayDate = value
    ? (() => { try { return format(new Date(value), 'd MMM yyyy') } catch { return value } })()
    : '—'

  return (
    <div className="w-full space-y-3">
      {/* Date labels + selected date pill */}
      <div className="flex items-center justify-between text-[11px] t-3">
        <span>{format(new Date(min), 'd MMM yyyy')}</span>
        <span className="font-semibold t-primary text-[12px] px-3 py-1 rounded-full border border-base"
              style={{ background: 'var(--bg-2)' }}>
          {displayDate}
        </span>
        <span>{format(new Date(max), 'd MMM yyyy')}</span>
      </div>

      {/* Slider track + markers */}
      <div className="relative pt-1 pb-7">
        <input type="range" min={minMs} max={maxMs} step={86400000} value={val}
          onChange={handleChange} disabled={disabled}
          className="w-full disabled:opacity-50 disabled:cursor-not-allowed" />

        {markers.map(m => {
          const mMs = dateToNum(m.date)
          if (mMs < minMs || mMs > maxMs) return null
          const pct    = ((mMs - minMs) / (maxMs - minMs)) * 100
          const active = value === m.date
          return (
            <button key={m.date} disabled={disabled} onClick={() => onChange(m.date)}
              title={`${m.date}: ${m.label}`}
              style={{ left: `${pct}%`, position:'absolute', top:'2px', transform:'translateX(-50%)' }}
              className={`transition-transform ${active ? 'scale-125' : 'hover:scale-110'}`}>
              <div className="w-1 h-3 mx-auto rounded-full" style={{ background: m.dot }} />
              <div className="absolute top-5 left-1/2 whitespace-nowrap text-[10px] font-medium"
                   style={{ transform:'translateX(-50%)', color: active ? 'var(--text)' : 'var(--text-3)',
                            opacity: active ? 1 : 0.7 }}>
                {m.label}
              </div>
            </button>
          )
        })}
      </div>

      {/* Quick-jump pills */}
      <div className="flex flex-wrap gap-1.5">
        {markers.map(m => (
          <button key={m.date} disabled={disabled} onClick={() => onChange(m.date)}
            className="pill cursor-pointer transition-all"
            style={value === m.date
              ? { background:'var(--brand)', color:'white', borderColor:'var(--brand-2)' }
              : { background:'var(--bg-2)', color:'var(--text-2)', borderColor:'var(--border)' }}>
            {m.label}
          </button>
        ))}
      </div>
    </div>
  )
}
