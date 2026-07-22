import type { SensorPoint } from '../types/timeline'
import { format } from 'date-fns'

const STATUS_DOT: Record<string, string> = {
  OK:          'bg-green-500',
  FAULT:       'bg-red-500',
  MANUAL_READ: 'bg-yellow-500',
  WARN:        'bg-orange-500',
  ALERT:       'bg-red-600',
  DEGRADED:    'bg-amber-500',
}

export default function SensorChart({ readings }: { readings: SensorPoint[] }) {
  if (readings.length === 0)
    return <p className="text-sm t-3 py-4 text-center">No sensor readings in this window.</p>

  const byMetric: Record<string, SensorPoint[]> = {}
  for (const r of readings) (byMetric[r.metric] ??= []).push(r)

  return (
    <div className="space-y-5">
      {Object.entries(byMetric).map(([metric, pts]) => (
        <div key={metric}>
          <p className="text-[11px] font-semibold t-3 uppercase tracking-widest mb-2">
            {metric.replace(/_/g,' ')}
          </p>
          <div className="card overflow-hidden">
            {pts.map((pt, i) => {
              const ts = (() => { try { return format(new Date(pt.timestamp), 'dd MMM HH:mm') } catch { return pt.timestamp } })()
              return (
                <div key={i} className={`flex items-center gap-3 px-4 py-2.5 text-[12px]
                                         ${i > 0 ? 'border-t border-base' : ''}`}>
                  <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[pt.status] ?? 'bg-slate-400'}`} />
                  <span className="t-3 w-32 shrink-0 font-mono">{ts}</span>
                  <span className="font-mono t-2 w-24 shrink-0">{pt.sensor_id}</span>
                  <span className="font-semibold t-primary w-24 shrink-0">
                    {pt.value !== null
                      ? `${pt.value} ${pt.unit}`
                      : <span className="text-red-500 font-medium">FAULT</span>
                    }
                  </span>
                  <span className={`pill shrink-0
                    ${pt.status==='FAULT' ? 'bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-300 border-red-300 dark:border-red-500/30'
                    : pt.status==='OK'    ? 'bg-green-100 dark:bg-green-500/15 text-green-700 dark:text-green-300 border-green-300 dark:border-green-500/30'
                    :                       'bg-yellow-100 dark:bg-yellow-500/15 text-yellow-700 dark:text-yellow-300 border-yellow-300 dark:border-yellow-500/25'}`}>
                    {pt.status}
                  </span>
                  {pt.notes && <span className="t-3 truncate">{pt.notes}</span>}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
