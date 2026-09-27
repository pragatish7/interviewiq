import { formatTimecode, formatDuration } from '../utils'

const TYPE_META = {
  filler: { color: '#e2a552', label: 'Filler', chip: 'badge-amber' },
  pause: { color: '#dcc3aa', label: 'Pause', chip: 'badge-cyan' },
  answer: { color: '#4bbd79', label: 'Answer', chip: 'badge-green' },
  pace: { color: '#c2144f', label: 'Pace', chip: 'badge-indigo' },
}

export default function Timeline({ events = [], duration, onSeek, activeTime }) {
  if (!events?.length) {
    return <div className="py-6 text-center text-[13px] text-[var(--text-3)]">No timestamped events detected.</div>
  }
  const dur = duration || events[events.length - 1]?.timestamp + 10 || 60
  const sorted = [...events].sort((a, b) => a.timestamp - b.timestamp)

  return (
    <div>
      {/* Scaled track */}
      <div className="relative h-10 rounded-lg overflow-hidden border border-[var(--border)] bg-[var(--surface-2)]">
        <div className="absolute inset-0 flex">
          {[0.25, 0.5, 0.75].map((p) => (
            <div key={p} className="border-l border-dashed border-[var(--border)] h-full" style={{ marginLeft: `${p * 100}%` }} />
          ))}
        </div>
        <div
          className="absolute inset-x-0 bottom-0 h-[3px]"
          style={{ background: 'linear-gradient(90deg, rgba(129,11,56,.75), rgba(194,20,79,.35), transparent)' }}
        />
        {sorted.map((ev, i) => {
          const meta = TYPE_META[ev.type] || { color: 'var(--text-3)', label: ev.type }
          const left = Math.min(96, Math.max(1, (ev.timestamp / dur) * 100))
          const isActive = activeTime != null && Math.abs(activeTime - ev.timestamp) < 2
          return (
            <button
              key={i}
              title={ev.description}
              onClick={() => onSeek?.(ev.timestamp)}
              aria-label={ev.description}
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-[var(--surface)] hover:scale-125 transition-transform cursor-pointer"
              style={{ left: `${left}%`, background: meta.color, boxShadow: isActive ? `0 0 0 4px ${meta.color}44` : undefined }}
            />
          )
        })}
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10.5px] font-semibold tabular-nums text-[var(--text-3)]">
          {formatDuration(dur)}
        </span>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2 mt-3 mb-3">
        {Object.entries(TYPE_META).filter(([k]) => events.some((e) => e.type === k)).map(([k, m]) => (
          <span key={k} className={`badge ${m.chip}`}><span className="w-1.5 h-1.5 rounded-full" style={{ background: m.color }} />{m.label}</span>
        ))}
      </div>

      {/* Event list */}
      <div className="space-y-1 max-h-[300px] overflow-y-auto pr-1">
        {sorted.map((ev, i) => {
          const meta = TYPE_META[ev.type] || { color: 'var(--text-3)', chip: 'badge-gray', label: ev.type }
          const isActive = activeTime != null && Math.abs(activeTime - ev.timestamp) < 2
          return (
            <button
              key={i}
              onClick={() => onSeek?.(ev.timestamp)}
              className={`w-full flex items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors cursor-pointer border ${
                isActive ? 'border-[var(--accent)]/30 bg-[var(--accent-bg)]' : 'border-transparent hover:bg-[var(--surface-2)]'
              }`}
            >
              <span className="text-[12px] font-bold tabular-nums text-[var(--text)] w-12">{formatTimecode(ev.timestamp)}</span>
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: meta.color, boxShadow: `0 0 8px ${meta.color}77` }} />
              <span className="text-[13px] text-[var(--text-2)] flex-1 truncate">{ev.description}</span>
              <span className={`badge ${meta.chip} shrink-0`}>{meta.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
