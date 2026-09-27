import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, TrendingDown, Clapperboard, Award, ArrowRight, LineChart as LineChartIcon, Minus } from 'lucide-react'
import { getProgress } from '../api'
import EmptyState from '../components/EmptyState'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

function Kpi({ label, value, sub, icon: Icon, tone }) {
  return (
    <div className="px-5 py-4">
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <p className="kicker">{label}</p>
        <Icon size={15} style={{ color: tone || 'var(--accent-2)' }} />
      </div>
      <p className="text-[28px] font-extrabold tracking-tight leading-none" style={{ fontFamily: 'var(--font-display)', color: tone || 'var(--text)' }}>
        {value}
      </p>
      {sub && <p className="text-[11.5px] text-[var(--text-3)] mt-2 truncate">{sub}</p>}
    </div>
  )
}

const tooltipStyle = {
  background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 12, fontSize: 12.5, boxShadow: 'var(--shadow-md)',
}

function TrendCard({ title, subtitle, data, lines, domain, height = 190 }) {
  return (
    <div className="panel p-5">
      <p className="text-[14px] font-bold text-[var(--text)]">{title}</p>
      <p className="text-[11.5px] text-[var(--text-3)] mt-0.5 mb-3">{subtitle}</p>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -22 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-2)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis domain={domain || [0, 100]} tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-2)', fontWeight: 600 }} itemStyle={{ color: 'var(--text)' }} />
          {lines.map((l) => (
            <Line
              key={l.key}
              type="monotone"
              dataKey={l.key}
              name={l.name}
              stroke={l.color}
              strokeWidth={2.2}
              dot={{ r: 3.5, strokeWidth: 0, fill: l.color }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function ProgressPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getProgress(30).then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="space-y-6 py-2">
        <div className="skeleton h-9 w-56" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-72 w-full" />
      </div>
    )
  }

  const list = (data?.interviews || []).filter((i) => i.overall_score != null)
  if (!list.length) {
    return (
      <div className="max-w-xl mx-auto anim-fade-up">
        <header className="mb-6">
          <p className="kicker mb-2">Progress</p>
          <h1 className="display text-[28px] sm:text-[34px] text-[var(--text)]">Your Progress<span className="text-[var(--accent)]">.</span></h1>
          <p className="text-[13.5px] text-[var(--text-2)] mt-2">See how your interview performance changes over time.</p>
        </header>
        <div className="panel">
          <EmptyState
            icon={LineChartIcon}
            title="No progress data yet"
            description="Complete your first interview analysis to start tracking your performance across every dimension."
            action={<Link to="/analyze" className="btn btn-primary">Analyze Interview <ArrowRight size={15} /></Link>}
          />
        </div>
      </div>
    )
  }

  const scores = list.map((i) => i.overall_score)
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length
  const best = Math.max(...scores)
  const first = scores[0]
  const last = scores[scores.length - 1]
  const improvement = last - first
  const ImpIcon = improvement > 0 ? TrendingUp : improvement < 0 ? TrendingDown : Minus
  const impTone = improvement > 0 ? 'var(--success)' : improvement < 0 ? 'var(--error)' : undefined

  const series = list.map((i, idx) => ({
    name: `#${idx + 1}`,
    full: i.title,
    score: i.overall_score != null ? Math.round(i.overall_score) : null,
    comm: i.communication_score != null ? Math.round(i.communication_score) : null,
    answer: i.answer_quality_score != null ? Math.round(i.answer_quality_score) : null,
    filler: i.filler_rate != null ? Math.round(i.filler_rate * 10) / 10 : null,
    pace: i.words_per_minute != null ? Math.round(i.words_per_minute) : null,
  }))

  return (
    <div className="space-y-6 anim-fade-up">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">Progress</p>
          <h1 className="display text-[28px] sm:text-[34px] text-[var(--text)]">
            Your Progress<span className="text-[var(--accent)]">.</span>
          </h1>
          <p className="text-[13.5px] text-[var(--text-2)] mt-2">
            Performance across your {list.length} completed {list.length === 1 ? 'analysis' : 'analyses'}
          </p>
        </div>
        <Link to="/history" className="btn btn-secondary">
          Full history <ArrowRight size={15} />
        </Link>
      </header>

      {/* Metric band */}
      <div className="panel overflow-hidden">
        <div className="grid grid-cols-2 xl:grid-cols-4 divide-x divide-y xl:divide-y-0 divide-[var(--border-2)] [&>*]:border-t-0">
          <Kpi label="Interviews" value={list.length} sub="Completed analyses" icon={Clapperboard} />
          <Kpi label="Average Score" value={Math.round(avg)} sub={`Across ${list.length} interviews`} icon={TrendingUp} />
          <Kpi label="Best Score" value={Math.round(best)} sub={series.find((s) => Math.round(s.score ?? 0) === Math.round(best))?.full || ''} icon={Award} tone="var(--success)" />
          <Kpi
            label="Improvement"
            value={`${improvement > 0 ? '+' : ''}${Math.round(improvement)}`}
            sub={`First ${Math.round(first)} → Latest ${Math.round(last)}`}
            icon={ImpIcon}
            tone={impTone}
          />
        </div>
      </div>

      {/* Main trend — the page's focal visual */}
      <div className="panel-focus p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div>
            <h2 className="text-[16px] font-bold text-[var(--text)]">Overall Performance Trend</h2>
            <p className="text-[12px] text-[var(--text-3)] mt-0.5">Overall score by interview — first analysis on the left</p>
          </div>
          <span className={`badge ${improvement > 0 ? 'badge-green' : improvement < 0 ? 'badge-red' : 'badge-gray'}`}>
            <ImpIcon size={11} />
            {improvement > 0 ? 'Improving' : improvement < 0 ? 'Declining' : 'Stable'}
          </span>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={series} margin={{ top: 5, right: 12, bottom: 0, left: -22 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-2)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 11.5 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-3)', fontSize: 11.5 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: 'var(--text-2)', fontWeight: 600 }} itemStyle={{ color: 'var(--text)' }} />
            <Line
              type="monotone"
              dataKey="score"
              name="Overall"
              stroke="#c2144f"
              strokeWidth={2.6}
              dot={{ r: 4, fill: 'var(--surface)', stroke: '#c2144f', strokeWidth: 2 }}
              activeDot={{ r: 5.5, fill: '#c2144f' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Secondary trends */}
      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
        <TrendCard title="Communication" subtitle="Score per interview" data={series} lines={[{ key: 'comm', name: 'Communication', color: '#c2144f' }]} />
        <TrendCard title="Answer Quality" subtitle="Score per interview" data={series} lines={[{ key: 'answer', name: 'Answers', color: '#dcc3aa' }]} />
        <TrendCard
          title="Filler Words"
          subtitle="Fillers per minute — lower is better"
          data={series}
          lines={[{ key: 'filler', name: 'Filler rate (/min)', color: '#e2a552' }]}
          domain={[0, 'auto']}
        />
        <TrendCard
          title="Speaking Pace"
          subtitle="Words per minute"
          data={series}
          lines={[{ key: 'pace', name: 'WPM', color: '#b08963' }]}
          domain={[0, 'auto']}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed border-[var(--border-strong)] px-5 py-4">
        <p className="text-[12.5px] text-[var(--text-2)]">Want to compare two interviews side by side?</p>
        <Link to="/history" className="btn btn-secondary btn-sm">Open History <ArrowRight size={14} /></Link>
      </div>
    </div>
  )
}
