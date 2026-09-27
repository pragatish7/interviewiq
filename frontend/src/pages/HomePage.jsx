import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Award, Target, Clapperboard, TrendingUp, TrendingDown, Minus, Video, Upload, Mic, FileVideo, History, Sparkles } from 'lucide-react'
import { getDashboard, getInterviews } from '../api'
import { greeting, timeAgo, scoreTone } from '../utils'
import EmptyState from '../components/EmptyState'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

/* One statistic, sitting directly on the panel grid rather than in its own card. */
function StatCell({ label, value, icon: Icon, tone, hint }) {
  return (
    <div className="relative p-4 sm:p-5 flex flex-col justify-center">
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <p className="kicker">{label}</p>
        <Icon size={15} style={{ color: tone || 'var(--accent-2)' }} />
      </div>
      <p
        className="text-[30px] leading-none font-extrabold tracking-tight"
        style={{ fontFamily: 'var(--font-display)', color: tone || 'var(--text)' }}
      >
        {value}
      </p>
      {hint && <p className="text-[11.5px] text-[var(--text-3)] mt-2">{hint}</p>}
    </div>
  )
}

function OverviewSkeleton() {
  return (
    <div className="grid grid-cols-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="p-4 sm:p-5">
          <div className="skeleton h-2.5 w-20 mb-4" />
          <div className="skeleton h-7 w-16" />
        </div>
      ))}
    </div>
  )
}

export default function HomePage() {
  const [dash, setDash] = useState(null)
  const [interviews, setInterviews] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [d, list] = await Promise.all([getDashboard(), getInterviews(0, 10)])
      setDash(d)
      setInterviews(list.interviews || [])
    } catch (e) {
      setDash(null)
      setInterviews([])
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const hasData = (dash?.total_interviews || 0) > 0
  const trend = (interviews.filter((i) => i.overall_score != null && i.status === 'completed') || [])
    .slice()
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .map((i) => ({ name: new Date(i.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), score: Math.round(i.overall_score) }))

  const recent = (interviews || []).slice(0, 6)

  const imp = dash?.improvement ?? null
  const ImpIcon = imp > 0 ? TrendingUp : imp < 0 ? TrendingDown : Minus
  const impTone = imp > 0 ? 'var(--success)' : imp < 0 ? 'var(--error)' : undefined
  const latestTone = dash?.latest_score != null ? scoreTone(dash.latest_score) : undefined

  return (
    <div className="space-y-6 anim-fade-up">
      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden rounded-[20px] border border-[var(--border)] px-5 sm:px-8 py-8 sm:py-10"
        style={{
          background:
            'radial-gradient(760px 300px at 88% -30%, var(--hero-glow), transparent 62%),' +
            'radial-gradient(500px 260px at 0% 120%, var(--hero-glow-2), transparent 66%),' +
            'linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,0) 45%), var(--surface)',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <span className="glow-burgundy -top-24 -right-16 w-72 h-72 opacity-70" aria-hidden />
        <div className="relative flex flex-col lg:flex-row lg:items-end justify-between gap-6">
          <div className="max-w-2xl">
            <p className="kicker mb-3">Interview Intelligence</p>
            <h1 className="display text-[34px] sm:text-[44px] lg:text-[50px] text-[var(--text)]">
              {greeting().replace('.', '')}
              <span className="text-[var(--accent)]">.</span>
            </h1>
            <p className="text-[14.5px] text-[var(--text-2)] mt-3 max-w-lg leading-relaxed">
              Analyze a recorded mock interview across speech, communication, answer quality and delivery —
              then get a specific plan for what to fix next.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Link to="/analyze" className="cta-shine inline-flex items-center gap-2">
              <Sparkles size={15} /> Start New Analysis
            </Link>
            {hasData && (
              <Link to="/progress" className="btn btn-secondary">
                View Progress <ArrowRight size={15} />
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* ---------- Bento: start workflows + overview ---------- */}
      <div className="grid lg:grid-cols-5 gap-5 items-stretch">
        <div className="lg:col-span-3">
          <div className="panel-focus p-5 sm:p-6 h-full relative overflow-hidden">
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <h2 className="text-[17px] font-bold text-[var(--text)] tracking-tight">Start New Analysis</h2>
                <p className="text-[12.5px] text-[var(--text-3)] mt-1">Choose how you want to practice — record now or analyze an existing recording.</p>
              </div>
              <span
                className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0 border"
                style={{ background: 'var(--grad)', borderColor: 'rgba(255,255,255,.14)', color: '#fff7f0', boxShadow: '0 8px 22px rgba(129,11,56,.4)' }}
              >
                <Video size={18} />
              </span>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              {/* ---- OPTION 1: existing video upload (unchanged workflow) ---- */}
              <div className="rounded-xl border p-4 flex flex-col" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center border mb-3"
                  style={{ background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.28)', color: 'var(--accent)' }}
                >
                  <Upload size={17} />
                </span>
                <h3 className="text-[14.5px] font-bold text-[var(--text)]">Upload Video</h3>
                <p className="text-[12.5px] text-[var(--text-3)] mt-1 mb-4 leading-relaxed flex-1">
                  Analyze an existing interview recording.
                </p>
                <Link to="/analyze" className="btn btn-secondary btn-sm w-full justify-center">
                  Upload Video <ArrowRight size={14} />
                </Link>
              </div>

              {/* ---- OPTION 2: NEW — Live AI Interview ---- */}
              <div
                className="rounded-xl border p-4 flex flex-col relative overflow-hidden group"
                style={{
                  borderColor: 'rgba(194,20,79,.32)',
                  background: 'linear-gradient(160deg, rgba(129,11,56,.20), rgba(84,26,26,.16))',
                }}
              >
                <span className="glow-burgundy -top-12 -right-8 w-40 h-40 opacity-40 group-hover:opacity-70 transition-opacity" aria-hidden />
                <span
                  className="w-10 h-10 rounded-xl flex items-center justify-center border mb-3 relative"
                  style={{ background: 'var(--grad)', borderColor: 'rgba(255,255,255,.16)', color: '#fff7f0', boxShadow: '0 6px 18px rgba(129,11,56,.45)' }}
                >
                  <Mic size={17} />
                </span>
                <h3 className="text-[14.5px] font-bold text-[var(--text)] relative">Live Interview</h3>
                <p className="text-[12.5px] text-[var(--text-3)] mt-1 mb-4 leading-relaxed flex-1 relative">
                  Take an AI-powered live interview with your microphone.
                </p>
                <Link to="/live-interview" className="btn btn-primary btn-sm w-full justify-center relative">
                  Start Live <ArrowRight size={14} />
                </Link>
              </div>
            </div>

          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="panel h-full overflow-hidden flex flex-col">
            <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[var(--border-2)]">
              <div>
                <h2 className="text-[15px] font-bold text-[var(--text)]">Performance Overview</h2>
                <p className="text-[11.5px] text-[var(--text-3)] mt-0.5">Across every completed analysis</p>
              </div>
              {hasData && <Link to="/progress" className="text-[12px] font-semibold text-[var(--accent)] hover:underline">Details</Link>}
            </div>

            {loading ? (
              <OverviewSkeleton />
            ) : hasData ? (
              <div className="grid grid-cols-2 divide-x divide-y divide-[var(--border-2)] [&>*:nth-child(1)]:border-t-0 [&>*:nth-child(2)]:border-t-0 flex-1">
                <StatCell
                  label="Average Score"
                  value={dash.average_score != null ? Math.round(dash.average_score) : '—'}
                  icon={Award}
                  hint="Across all analyses"
                />
                <StatCell label="Interviews" value={dash.total_interviews ?? 0} icon={Clapperboard} hint="Completed recordings" />
                <StatCell
                  label="Latest Score"
                  value={dash.latest_score != null ? Math.round(dash.latest_score) : '—'}
                  icon={Target}
                  tone={latestTone}
                  hint="Most recent result"
                />
                <StatCell
                  label="Improvement"
                  value={imp != null ? `${imp > 0 ? '+' : ''}${imp}` : '—'}
                  icon={ImpIcon}
                  tone={impTone}
                  hint={imp != null ? (imp > 0 ? 'Trending up' : imp < 0 ? 'Trending down' : 'Holding steady') : undefined}
                />
              </div>
            ) : (
              <EmptyState
                compact
                icon={Award}
                title="No interview data yet"
                description="Complete your first analysis to start tracking performance."
                action={<Link to="/analyze" className="btn btn-primary btn-sm">Start Analysis <ArrowRight size={14} /></Link>}
              />
            )}
          </div>
        </div>
      </div>

      {/* ---------- Recent activity ---------- */}
      <div className="panel overflow-hidden">
        <div className="flex items-center justify-between gap-4 px-5 py-4 border-b border-[var(--border-2)]">
          <div className="flex items-center gap-3">
            <span className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border"
              style={{ background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.26)', color: 'var(--accent)' }}>
              <History size={16} />
            </span>
            <div>
              <h2 className="text-[15px] font-bold text-[var(--text)]">Recent Interviews</h2>
              {!loading && recent.length > 0 && (
                <p className="text-[11.5px] text-[var(--text-3)] mt-0.5">
                  {recent.length === 1 ? 'Your latest analysis' : `${recent.length} most recent analyses`}
                </p>
              )}
            </div>
          </div>
          <Link to="/history" className="btn btn-ghost btn-sm">
            View all <ArrowRight size={14} />
          </Link>
        </div>

        {loading ? (
          <div className="p-5 space-y-3">
            {[0, 1, 2].map((i) => <div key={i} className="skeleton h-11" />)}
          </div>
        ) : recent.length === 0 ? (
          <EmptyState
            compact
            icon={FileVideo}
            title="No interviews yet"
            description="Your completed analyses will appear here."
            action={<Link to="/analyze" className="btn btn-primary btn-sm">Analyze Interview <ArrowRight size={14} /></Link>}
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Interview</th>
                  <th>Role</th>
                  <th>Date</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((i) => (
                  <tr key={i.id}>
                    <td className="font-semibold text-[var(--text)] max-w-[240px] truncate">{i.title}</td>
                    <td className="text-[var(--text-2)]">{i.target_role || '—'}</td>
                    <td className="text-[var(--text-3)] whitespace-nowrap">{timeAgo(i.created_at)}</td>
                    <td>
                      {i.overall_score != null ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="font-bold text-[var(--text)] tabular-nums">{Math.round(i.overall_score)}</span>
                          <span className="w-2 h-2 rounded-full" style={{ background: scoreTone(i.overall_score), boxShadow: `0 0 8px ${scoreTone(i.overall_score)}88` }} />
                        </span>
                      ) : <span className="text-[var(--text-3)]">—</span>}
                    </td>
                    <td>
                      <span className={`badge ${i.status === 'completed' ? 'badge-green' : i.status === 'processing' ? 'badge-indigo' : i.status === 'failed' ? 'badge-red' : 'badge-gray'}`}>
                        {i.status === 'completed' ? 'Completed' : i.status}
                      </span>
                    </td>
                    <td className="text-right">
                      {i.status === 'completed' ? (
                        <Link to={`/interview/${i.id}`} className="btn btn-secondary btn-sm">View Report</Link>
                      ) : (
                        <span className="text-[12px] text-[var(--text-3)]">Pending</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ---------- Trend ---------- */}
      {hasData && trend.length > 1 && (
        <div className="panel p-5">
          <div className="flex items-center justify-between gap-4 mb-5">
            <div>
              <h2 className="text-[15px] font-bold text-[var(--text)]">Performance Trend</h2>
              <p className="text-[12px] text-[var(--text-3)] mt-0.5">Overall score across your analyses</p>
            </div>
            {(() => {
              const up = trend[trend.length - 1].score > trend[0].score
              const down = trend[trend.length - 1].score < trend[0].score
              return (
                <span className={`badge ${up ? 'badge-green' : down ? 'badge-red' : 'badge-gray'}`}>
                  {up ? <TrendingUp size={11} /> : down ? <TrendingDown size={11} /> : <Minus size={11} />}
                  {up ? 'Improving' : down ? 'Declining' : 'Stable'}
                </span>
              )
            })()}
          </div>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={trend} margin={{ top: 5, right: 10, bottom: 0, left: -25 }}>
              <defs>
                <linearGradient id="homeTrend" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#c2144f" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#c2144f" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-2)" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11.5 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-3)', fontSize: 11.5 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 12, fontSize: 12.5, boxShadow: 'var(--shadow-md)' }}
                labelStyle={{ color: 'var(--text-2)', fontWeight: 600 }}
                itemStyle={{ color: 'var(--text)' }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#c2144f"
                strokeWidth={2.5}
                dot={{ r: 4, fill: 'var(--surface)', stroke: '#c2144f', strokeWidth: 2 }}
                activeDot={{ r: 5.5, fill: '#c2144f', stroke: 'var(--surface)', strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
