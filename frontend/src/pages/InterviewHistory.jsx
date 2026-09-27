import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Trash2, ArrowUpDown, Clapperboard, ArrowRight, Filter } from 'lucide-react'
import { getInterviews, deleteInterview } from '../api'
import EmptyState from '../components/EmptyState'
import { formatDate, timeAgo, scoreTone } from '../utils'

function ScoreCell({ value }) {
  if (value == null) return <span className="text-[var(--text-3)]">—</span>
  const tone = scoreTone(value)
  return (
    <span className="inline-flex items-center gap-2 font-bold text-[var(--text)] tabular-nums">
      {Math.round(value)}
      <span className="w-2 h-2 rounded-full" style={{ background: tone, boxShadow: `0 0 8px ${tone}88` }} />
    </span>
  )
}

export default function InterviewHistory() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [sort, setSort] = useState('date')
  const [deleting, setDeleting] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const d = await getInterviews(0, 100)
      setRows(d.interviews || [])
    } catch { setRows([]) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    let out = rows.filter((i) => {
      const q = query.toLowerCase()
      const matchQ = !q || (i.title || '').toLowerCase().includes(q) || (i.target_role || '').toLowerCase().includes(q)
      const matchS = status === 'all' || i.status === status
      return matchQ && matchS
    })
    const val = (i) => {
      if (sort === 'score') return i.overall_score ?? -1
      if (sort === 'comm') return i.communication_score ?? -1
      if (sort === 'answer') return i.answer_quality_score ?? -1
      return new Date(i.created_at).getTime()
    }
    out = out.sort((a, b) => val(b) - val(a))
    return out
  }, [rows, query, status, sort])

  const remove = async (i) => {
    if (!window.confirm(`Delete "${i.title}" and its analysis?`)) return
    setDeleting(i.id)
    try { await deleteInterview(i.id); await load() } finally { setDeleting(null) }
  }

  const completed = rows.filter((i) => i.status === 'completed').length

  return (
    <div className="space-y-6 anim-fade-up">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">Archive</p>
          <h1 className="display text-[28px] sm:text-[34px] text-[var(--text)]">
            Interview History<span className="text-[var(--accent)]">.</span>
          </h1>
          <p className="text-[13.5px] text-[var(--text-2)] mt-2">
            {rows.length
              ? `${rows.length} recording${rows.length > 1 ? 's' : ''} · ${completed} completed`
              : 'Track every analysis you have run'}
          </p>
        </div>
        <Link to="/analyze" className="btn btn-primary">
          New Analysis <ArrowRight size={15} />
        </Link>
      </header>

      {/* Toolbar */}
      <div className="panel p-3 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-3)]" />
          <input
            type="search"
            placeholder="Search by title or role…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="!pl-10"
            aria-label="Search interviews"
          />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Filter size={14} className="text-[var(--text-3)] hidden sm:block" />
          <select className="!w-auto min-w-[150px]" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
            <option value="all">All statuses</option>
            <option value="completed">Completed</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
            <option value="uploaded">Uploaded</option>
          </select>
          <select className="!w-auto min-w-[160px]" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
            <option value="date">Sort · Newest</option>
            <option value="score">Sort · Overall score</option>
            <option value="comm">Sort · Communication</option>
            <option value="answer">Sort · Answer quality</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="panel overflow-hidden">
        {loading ? (
          <div className="p-5 space-y-3">
            {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-12" />)}
          </div>
        ) : filtered.length === 0 ? (
          rows.length === 0 ? (
            <EmptyState
              icon={Clapperboard}
              title="No interviews yet"
              description="Your interview history will appear here after your first analysis."
              action={<Link to="/analyze" className="btn btn-primary">Analyze Interview <ArrowRight size={15} /></Link>}
            />
          ) : (
            <EmptyState compact icon={Search} title="No matching interviews" description="Try a different search or clear the filters." />
          )
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Interview</th>
                  <th>Role</th>
                  <th>Date</th>
                  <th>
                    <button
                      className="inline-flex items-center gap-1 cursor-pointer hover:text-[var(--text-2)] transition-colors"
                      onClick={() => setSort(sort === 'score' ? 'date' : 'score')}
                    >
                      Score <ArrowUpDown size={11} />
                    </button>
                  </th>
                  <th>Communication</th>
                  <th>Answer Quality</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((i) => (
                  <tr key={i.id}>
                    <td className="max-w-[240px]">
                      <p className="font-semibold text-[var(--text)] truncate">{i.title}</p>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                        <span className={`badge ${i.status === 'completed' ? 'badge-green' : i.status === 'processing' ? 'badge-indigo' : i.status === 'failed' ? 'badge-red' : 'badge-gray'}`}>
                          {i.status === 'completed' ? 'Completed' : i.status}
                        </span>
                        {i.is_demo && <span className="badge badge-amber">Demo</span>}
                      </div>
                    </td>
                    <td className="text-[var(--text-2)] whitespace-nowrap">{i.target_role || '—'}</td>
                    <td className="text-[var(--text-3)] whitespace-nowrap" title={formatDate(i.created_at)}>{timeAgo(i.created_at)}</td>
                    <td><ScoreCell value={i.overall_score} /></td>
                    <td><ScoreCell value={i.communication_score} /></td>
                    <td><ScoreCell value={i.answer_quality_score} /></td>
                    <td>
                      <div className="flex items-center justify-end gap-1.5">
                        {i.status === 'completed' && (
                          <Link to={`/interview/${i.id}`} className="btn btn-secondary btn-sm">View</Link>
                        )}
                        <button
                          className="btn btn-ghost btn-sm text-[var(--text-3)] hover:text-[var(--error)] hover:bg-[var(--error-bg)]"
                          disabled={deleting === i.id}
                          onClick={() => remove(i)}
                          aria-label="Delete interview"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
