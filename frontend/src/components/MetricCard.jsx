import { scoreTone } from '../utils'

export default function MetricCard({ title, value, display, caption, tone, bar = true, icon: Icon }) {
  const color = tone || (value != null ? scoreTone(value) : 'var(--accent)')
  return (
    <div className="panel tile p-4 h-full flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="kicker mb-1.5 leading-snug">{title}</p>
          <p className="text-[26px] font-extrabold leading-none tracking-tight text-[var(--text)]" style={{ fontFamily: 'var(--font-display)' }}>
            {display ?? (value != null ? Math.round(value) : '—')}
            {value != null && <span className="text-[12.5px] font-semibold text-[var(--text-3)] ml-1">/100</span>}
          </p>
        </div>
        {Icon && (
          <span
            className="w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0 border"
            style={{ background: 'var(--surface-3)', borderColor: 'var(--border-2)', color }}
          >
            <Icon size={16} strokeWidth={2} />
          </span>
        )}
      </div>
      {bar && value != null && (
        <div className="bar-track mt-3.5">
          <div
            className="bar-fill"
            style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color, boxShadow: `0 0 12px ${color}66` }}
          />
        </div>
      )}
      {caption && <p className="text-[11.5px] text-[var(--text-3)] mt-2 leading-snug">{caption}</p>}
    </div>
  )
}
