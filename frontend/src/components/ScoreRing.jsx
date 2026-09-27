import { useEffect, useState } from 'react'
import { scoreLabel, scoreLabelTone, scoreTone } from '../utils'

export default function ScoreRing({ score, size = 168, stroke = 12, label, sublabel, showLabel = true }) {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => setProgress(Math.max(0, Math.min(100, score ?? 0))), 80)
    return () => clearTimeout(t)
  }, [score])

  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = progress / 100
  const id = `ring-${size}-${stroke}`.replace(/\./g, 'x')
  const tone = score != null ? scoreTone(score) : 'var(--accent)'

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      {/* burgundy bloom behind the ring */}
      <span
        className="absolute inset-[14%] rounded-full pointer-events-none"
        style={{ background: `radial-gradient(closest-side, ${score != null ? tone : '#810b38'}2e, transparent 75%)` }}
        aria-hidden
      />
      <svg width={size} height={size} className="-rotate-90 relative">
        <defs>
          <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#810b38" />
            <stop offset="52%" stopColor="#c2144f" />
            <stop offset="100%" stopColor="#f1e2d1" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle
          className="score-ring"
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={score != null ? tone : `url(#${id})`}
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          style={{ filter: `drop-shadow(0 0 10px ${score != null ? tone : '#810b38'}55)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <div className="flex items-baseline gap-0.5">
          <span
            className="font-extrabold tracking-tight text-[var(--text)]"
            style={{ fontSize: size * 0.3, lineHeight: 1, fontFamily: 'var(--font-display)' }}
          >
            {score != null ? Math.round(score) : '—'}
          </span>
          <span className="text-[var(--text-3)] font-semibold" style={{ fontSize: size * 0.105 }}>/100</span>
        </div>
        {label && <p className="text-[11px] font-semibold text-[var(--text-2)] mt-1">{label}</p>}
        {sublabel && <p className="text-[10.5px] text-[var(--text-3)] mt-0.5">{sublabel}</p>}
        {showLabel && score != null && (() => {
          const t = scoreLabelTone(score)
          return (
            <span
              className="mt-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-[10.5px] font-bold border"
              style={{ background: t.bg, color: t.color, borderColor: 'currentColor' }}
            >
              {scoreLabel(score)}
            </span>
          )
        })()}
      </div>
    </div>
  )
}
