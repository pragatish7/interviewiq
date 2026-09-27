import { useState } from 'react'
import { formatTimecode } from '../utils'

const FILLER_WORDS = ['um', 'uh', 'like', 'basically', 'actually', 'you know', 'i mean', 'so', 'hmm', 'er']

function renderSegmentText(text, fillersInWindow) {
  // fillersInWindow: [{word}] ordered by occurrence
  if (!fillersInWindow?.length) return text
  let out = text
  for (const f of fillersInWindow) {
    const word = f.word?.toLowerCase()
    if (!word) continue
    // Replace the first case-insensitive occurrence of the full phrase
    const re = new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
    out = out.replace(re, (m) => `<mark>${m}</mark>`)
  }
  return out
}

export default function TranscriptViewer({ segments = [], fillerInstances = [], onSeek, activeTime }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? segments : segments.slice(0, 12)

  if (!segments?.length) {
    return (
      <div className="py-8 text-center text-[13px] text-[var(--text-3)]">No transcript available for this interview.</div>
    )
  }

  return (
    <div>
      <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
        {shown.map((seg, idx) => {
          const windowFillers = (fillerInstances || []).filter(
            (f) => f.start >= (seg.start || 0) - 1 && f.start <= (seg.end || seg.start || 0) + 1
          )
          const html = renderSegmentText(seg.text || '', windowFillers)
          const isActive = activeTime != null && (seg.start || 0) <= activeTime && activeTime <= (seg.end || seg.start || 0)
          return (
            <button
              key={idx}
              onClick={() => onSeek?.(seg.start || 0)}
              className={`w-full text-left flex gap-3 rounded-lg px-3 py-2 transition-colors cursor-pointer border ${
                isActive
                  ? 'border-[var(--accent)]/30 bg-[var(--accent-bg)]'
                  : 'border-transparent hover:bg-[var(--surface-2)]'
              }`}
            >
              <span className={`text-[11px] font-bold tabular-nums pt-1 shrink-0 ${isActive ? 'text-[var(--accent)]' : 'text-[var(--text-3)]'}`}>
                {formatTimecode(seg.start)}
              </span>
              <span className="text-[13px] leading-relaxed text-[var(--text-2)]"
                dangerouslySetInnerHTML={{ __html: html.replace(/\n/g, ' ').replace(/<mark>/g, '<mark class="bg-[var(--warn-bg)] text-[var(--warn)] font-semibold rounded px-1 border border-[var(--warn)]/25">') }}
              />
            </button>
          )
        })}
      </div>
      {segments.length > 12 && (
        <button className="btn btn-ghost btn-sm w-full mt-2 justify-center" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show less' : `Show all ${segments.length} segments`}
        </button>
      )}
      <p className="text-[11px] text-[var(--text-3)] mt-2 flex items-center gap-1.5">
        <span className="inline-block w-2 h-2 rounded-sm bg-[var(--warn)]" /> Highlighted words are detected filler words · click a segment to jump the video
      </p>
    </div>
  )
}
