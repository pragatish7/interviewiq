export function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function timeAgo(iso) {
  if (!iso) return ''
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`
  return formatDate(iso)
}

export function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}h ${m % 60}m`
  }
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export function formatBytes(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatTimecode(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

// Semantic color for a score value — green (good), amber (average), red (low).
// Tuned to stay legible on the near-black Red Noir canvas.
export function scoreTone(score) {
  if (score >= 70) return '#4bbd79'
  if (score >= 60) return '#e2a552'
  return '#ef6a5f'
}

export function scoreLabel(score) {
  if (score == null) return ''
  if (score >= 90) return 'Excellent'
  if (score >= 80) return 'Strong'
  if (score >= 70) return 'Good'
  if (score >= 60) return 'Needs Improvement'
  return 'Requires Practice'
}

export function scoreLabelTone(score) {
  if (score == null) return { bg: 'var(--cream-bg)', color: 'var(--text-2)' }
  const label = scoreLabel(score)
  if (label === 'Needs Improvement') return { bg: 'var(--warn-bg)', color: 'var(--warn)' }
  if (label === 'Requires Practice') return { bg: 'var(--error-bg)', color: 'var(--error)' }
  return { bg: 'var(--success-bg)', color: 'var(--success)' }
}

export function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}
