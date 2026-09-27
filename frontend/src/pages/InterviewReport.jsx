import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Download, Brain, Mic, MessageSquareText, ListChecks, Sparkles, Check, AlertTriangle,
  ChevronDown, Film, FileText, Loader2, BadgeCheck, Target, TrendingUp, Eye, Gauge, Lightbulb,
} from 'lucide-react'
import { getInterview, getVideoUrl, getPdfUrl } from '../api'
import ScoreRing from '../components/ScoreRing'
import MetricCard from '../components/MetricCard'
import RadarChart from '../components/RadarChart'
import TranscriptViewer from '../components/TranscriptViewer'
import Timeline from '../components/Timeline'
import { formatDateTime, formatDuration, scoreLabel, scoreTone } from '../utils'
import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const METRIC_DEFS = [
  { key: 'communication_score', title: 'Communication', icon: MessageSquareText },
  { key: 'answer_quality_score', title: 'Answer Quality', icon: ListChecks },
  { key: 'clarity_score', title: 'Clarity', icon: Sparkles },
  { key: 'fluency_score', title: 'Fluency', icon: Gauge },
  { key: 'speaking_pace_score', title: 'Speaking Pace', icon: Mic },
  { key: 'vocabulary_score', title: 'Vocabulary', icon: FileText },
  { key: 'relevance_score', title: 'Relevance', icon: Target },
  { key: 'nonverbal_score', title: 'Delivery', icon: Eye },
]

function captionFor(key, d) {
  const S = d.detailed_scores || {}
  const v = S[key]
  const r = d.repetition_rate
  switch (key) {
    case 'communication_score':
      return v >= 80 ? 'Clear and well-structured responses'
        : v >= 65 ? 'Solid clarity with room for more depth' : 'Responses need clearer structure'
    case 'answer_quality_score':
      return (d.qa_analysis?.length ? `${d.qa_analysis.length} questions evaluated` : 'Based on transcript responses')
    case 'clarity_score':
      return r != null && r > 0.15 ? 'Some repeated phrasing detected' : 'Easy to follow throughout'
    case 'fluency_score':
      return d.filler_rate != null && d.filler_rate > 0 ? `${d.filler_rate}/min filler rate` : 'Smooth, low filler usage'
    case 'speaking_pace_score':
      return d.words_per_minute ? `${Math.round(d.words_per_minute)} words per minute` : 'Pace evaluated from speech'
    case 'vocabulary_score':
      return d.vocabulary_diversity != null ? `Vocabulary diversity ${d.vocabulary_diversity.toFixed(2)}` : 'Range of expression measured'
    case 'relevance_score':
      return 'Answer relevance to the questions asked'
    case 'nonverbal_score':
      return d.face_visibility != null ? `Face visible ${Math.round(d.face_visibility)}% of the time` : 'Observable camera presence'
    default:
      return ''
  }
}

function MetricRow({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2.5 border-b border-[var(--border-2)] last:border-b-0">
      <span className="text-[12.5px] font-medium text-[var(--text-3)]">{label}</span>
      <span className="text-[13.5px] font-bold text-[var(--text)] tabular-nums">{value}</span>
    </div>
  )
}

function HeroStat({ label, value }) {
  return (
    <div className="px-4 py-3">
      <p className="kicker mb-1.5">{label}</p>
      <p className="text-[19px] font-extrabold text-[var(--text)] tabular-nums leading-none" style={{ fontFamily: 'var(--font-display)' }}>
        {value}
      </p>
    </div>
  )
}

function StarRow({ star }) {
  const parts = [
    { key: 'situation', label: 'Situation', desc: 'Context' },
    { key: 'task', label: 'Task', desc: 'Responsibility' },
    { key: 'action', label: 'Action', desc: 'What you did' },
    { key: 'result', label: 'Result', desc: 'Outcome' },
  ]
  return (
    <div className="flex flex-wrap gap-2">
      {parts.map((p) => {
        const ok = !!star?.[p.key]
        return (
          <span
            key={p.key}
            className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] font-semibold"
            style={ok
              ? { borderColor: 'rgba(75,189,121,.3)', background: 'var(--success-bg)', color: 'var(--success)' }
              : { borderColor: 'rgba(226,165,82,.3)', background: 'var(--warn-bg)', color: 'var(--warn)' }}
          >
            {ok ? <Check size={13} strokeWidth={3} /> : <AlertTriangle size={13} />}
            {p.label}
          </span>
        )
      })}
    </div>
  )
}

export default function InterviewReport() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTime, setActiveTime] = useState(null)
  const [openQa, setOpenQa] = useState(0)
  const videoRef = useRef(null)

  useEffect(() => {
    setLoading(true)
    getInterview(id)
      .then((d) => { setData(d); setLoading(false) })
      .catch((e) => { setError(e?.response?.data?.detail || 'Could not load this interview'); setLoading(false) })
  }, [id])

  const seek = (t) => {
    setActiveTime(t)
    const v = videoRef.current
    if (v && t != null) {
      v.currentTime = t
      v.play().catch(() => {})
    }
  }

  const fillers = useMemo(() => {
    const freq = data?.filler_words_detail?.frequent
    if (Array.isArray(freq) && freq.length) return freq
    const inst = data?.filler_words_detail?.instances
    if (Array.isArray(inst)) {
      const m = {}
      inst.forEach((i) => { m[i.word] = (m[i.word] || 0) + 1 })
      return Object.entries(m).map(([word, count]) => ({ word, count }))
    }
    return []
  }, [data])

  if (loading) {
    return (
      <div className="space-y-5 py-2">
        <div className="skeleton h-8 w-64" />
        <div className="skeleton h-64 w-full" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-28" />)}
        </div>
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="max-w-lg mx-auto text-center py-20 anim-fade-up">
        <p className="text-[16px] font-bold text-[var(--text)] mb-1.5">Report unavailable</p>
        <p className="text-[13px] text-[var(--text-3)] mb-6">{error}</p>
        <Link to="/history" className="btn btn-primary">Back to History</Link>
      </div>
    )
  }

  const d = data
  const S = d.detailed_scores || {}
  const overall = S.overall_score ?? d.overall_score
  const coaching = d.coaching_feedback || {}
  const plan = d.improvement_plan || []
  const qa = d.qa_analysis || []
  const segments = d.speech_segments || []
  const events = d.timeline_events || []
  const radarData = [
    { subject: 'Communication', score: S.communication_score ?? 0 },
    { subject: 'Answers', score: S.answer_quality_score ?? 0 },
    { subject: 'Clarity', score: S.clarity_score ?? 0 },
    { subject: 'Fluency', score: S.fluency_score ?? 0 },
    { subject: 'Pace', score: S.speaking_pace_score ?? 0 },
    { subject: 'Vocabulary', score: S.vocabulary_score ?? 0 },
    { subject: 'Delivery', score: S.nonverbal_score ?? 0 },
  ]
  const behavioral = qa.some((q) => q.category === 'behavioral')
  const inProgress = d.status === 'processing'

  // Weakest real dimension — drives the "Your Next Focus" panel
  let focus = null
  const scored = METRIC_DEFS
    .map(({ key, title }) => ({ key, title, v: S[key] }))
    .filter((x) => x.v != null)
  if (scored.length) {
    const min = scored.reduce((a, b) => (b.v < a.v ? b : a))
    focus = { ...min, caption: captionFor(min.key, d), tone: scoreTone(min.v), label: scoreLabel(min.v) }
  }

  const tooltipStyle = {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    fontSize: 12.5,
    boxShadow: 'var(--shadow-md)',
  }

  return (
    <div className="space-y-5 anim-fade-up">
      {/* ---------- Header ---------- */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/history" className="btn btn-ghost btn-sm -ml-2 mb-2">
            <ArrowLeft size={15} /> History
          </Link>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="display text-[26px] sm:text-[30px] text-[var(--text)]">Interview Analysis</h1>
            {d.is_demo && (
              <span className="badge badge-amber"><AlertTriangle size={11} /> Demo Mode — sample data</span>
            )}
          </div>
          <p className="text-[13px] text-[var(--text-3)] mt-1.5 truncate max-w-xl">{d.title}</p>
        </div>
        <a href={getPdfUrl(d.id)} target="_blank" rel="noreferrer" className="btn btn-secondary">
          <Download size={14} /> Download PDF
        </a>
      </div>

      {/* ---------- Meta ---------- */}
      <div className="flex flex-wrap gap-2">
        {d.target_role && <span className="badge badge-indigo">Role · {d.target_role}</span>}
        {d.interview_type && <span className="badge badge-violet">Type · {d.interview_type}</span>}
        {d.experience_level && <span className="badge badge-gray">Experience · {d.experience_level}</span>}
        <span className="badge badge-gray">Analyzed {formatDateTime(d.created_at)}</span>
        <span className="badge badge-gray">Duration · {formatDuration(d.duration)}</span>
        {d.ml_predicted_score != null && (
          <span className="badge badge-cyan">
            <Brain size={11} /> ML score {Math.round(d.ml_predicted_score)} ± {Math.round((d.ml_confidence || 0) * 100)}%
          </span>
        )}
      </div>

      {inProgress && (
        <div className="rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-bg)] px-4 py-3 text-[13px] text-[var(--text-2)] flex items-center gap-2.5">
          <Loader2 size={15} className="animate-spin text-[var(--accent)]" /> This interview is still being processed. Check back shortly.
        </div>
      )}

      {/* ---------- Summary hero ---------- */}
      <section className="panel-focus overflow-hidden">
        <div className="grid lg:grid-cols-5">
          <div className="lg:col-span-2 flex flex-col items-center justify-center text-center px-6 py-8 border-b lg:border-b-0 lg:border-r border-[var(--border-2)]">
            <p className="kicker mb-5">Overall Performance</p>
            <ScoreRing score={overall} size={196} stroke={14} />
          </div>

          <div className="lg:col-span-3 flex flex-col">
            {/* quick facts */}
            <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-[var(--border-2)] border-b border-[var(--border-2)]">
              <HeroStat label="Words / min" value={d.words_per_minute ? Math.round(d.words_per_minute) : '—'} />
              <HeroStat label="Fillers" value={d.filler_count ?? '—'} />
              <HeroStat label="Questions" value={qa.length || '—'} />
              <HeroStat label="Duration" value={formatDuration(d.duration)} />
            </div>

            <div className="p-5 sm:p-6 flex-1 flex flex-col gap-4">
              {coaching.overall_assessment && (
                <div>
                  <p className="kicker mb-2">Assessment</p>
                  <p className="text-[13.5px] text-[var(--text-2)] leading-relaxed">{coaching.overall_assessment}</p>
                </div>
              )}
              {focus ? (
                <div
                  className="relative overflow-hidden rounded-xl border px-4 py-4 flex flex-wrap items-center gap-4"
                  style={{ borderColor: 'rgba(194,20,79,.28)', background: 'linear-gradient(180deg, rgba(129,11,56,.16), rgba(129,11,56,.04))' }}
                >
                  <span
                    className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0 border"
                    style={{ background: 'rgba(194,20,79,.16)', borderColor: 'rgba(194,20,79,.3)', color: 'var(--accent)' }}
                  >
                    <Target size={19} />
                  </span>
                  <div className="flex-1 min-w-[200px]">
                    <p className="kicker mb-1">Your Next Focus</p>
                    <h2 className="text-[16px] font-bold text-[var(--text)]">{focus.title}</h2>
                    <p className="text-[12.5px] text-[var(--text-2)] mt-1 leading-relaxed">
                      {focus.caption}{' '}
                      <span className="font-bold" style={{ color: focus.tone }}>Score {Math.round(focus.v)} · {focus.label}</span>
                    </p>
                  </div>
                  <button
                    className="btn btn-primary btn-sm shrink-0"
                    onClick={() => {
                      const el = document.getElementById('practice-plan') || document.getElementById('answer-analysis')
                      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                    }}
                  >
                    Practice This <ArrowRight size={14} />
                  </button>
                </div>
              ) : (
                <p className="text-[13px] text-[var(--text-3)]">
                  Dimension-level scores were not available for this recording.
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Metric grid ---------- */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
        {METRIC_DEFS.map(({ key, title, icon }) => (
          <MetricCard key={key} title={title} value={S[key]} caption={captionFor(key, d)} icon={icon} />
        ))}
      </div>

      {/* ---------- Profile + speech ---------- */}
      <div className="grid lg:grid-cols-5 gap-5">
        <div className="lg:col-span-2 panel p-5">
          <h2 className="text-[15px] font-bold text-[var(--text)]">Performance Profile</h2>
          <p className="text-[12px] text-[var(--text-3)] mt-0.5 mb-3">Scores across analysis dimensions</p>
          <RadarChart data={radarData} height={272} />
        </div>

        <div className="lg:col-span-3 panel p-5">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <h2 className="text-[15px] font-bold text-[var(--text)] flex items-center gap-2">
                <Mic size={15} className="text-[var(--accent)]" /> Speech Metrics
              </h2>
              <p className="text-[12px] text-[var(--text-3)] mt-0.5">Measured from the audio track</p>
            </div>
            {d.filler_rate != null && (
              <span className={`badge ${d.filler_rate > 4 ? 'badge-amber' : 'badge-green'}`}>{d.filler_rate}/min fillers</span>
            )}
          </div>
          <div className="grid sm:grid-cols-2 gap-x-8">
            <MetricRow label="Speaking rate" value={d.words_per_minute ? `${Math.round(d.words_per_minute)} WPM` : '—'} />
            <MetricRow label="Total words" value={d.total_words ?? '—'} />
            <MetricRow label="Sentences" value={d.total_sentences ?? '—'} />
            <MetricRow label="Filler words" value={d.filler_count ?? 0} />
            <MetricRow label="Pauses detected" value={d.pause_count ?? '—'} />
            <MetricRow label="Avg pause length" value={d.avg_pause_duration != null ? `${d.avg_pause_duration.toFixed(1)}s` : '—'} />
          </div>
        </div>
      </div>

      {/* ---------- Fillers + coaching ---------- */}
      <div className="grid lg:grid-cols-5 gap-5">
        <div className="lg:col-span-2 panel p-5">
          <h2 className="text-[15px] font-bold text-[var(--text)] mb-3">Filler Words</h2>
          {fillers.length ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={fillers} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-2)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="word" width={72} tick={{ fill: 'var(--text-2)', fontSize: 12, fontWeight: 600 }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: 'var(--accent-bg)' }} contentStyle={tooltipStyle} formatter={(v) => [`${v} times`, 'Occurrences']} />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={16}>
                    {fillers.map((_, i) => <Cell key={i} fill={i === 0 ? '#c2144f' : '#810b38'} fillOpacity={i === 0 ? 1 : 0.7} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[11.5px] text-[var(--text-3)] mt-3">Most frequent filler words detected in your responses</p>
            </>
          ) : (
            <div className="py-12 text-center text-[13px] text-[var(--text-3)]">No filler words detected — clean delivery.</div>
          )}
        </div>

        <div className="lg:col-span-3 grid sm:grid-cols-2 gap-5">
          <div className="panel p-5">
            <h2 className="text-[15px] font-bold text-[var(--text)] flex items-center gap-2 mb-4">
              <BadgeCheck size={16} className="text-[var(--success)]" /> What You Did Well
            </h2>
            <ul className="space-y-3">
              {(coaching.strengths || []).map((s, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px] text-[var(--text-2)] leading-relaxed">
                  <Check size={15} strokeWidth={2.5} className="text-[var(--success)] mt-0.5 shrink-0" /> {s}
                </li>
              ))}
              {!coaching.strengths?.length && <li className="text-[13px] text-[var(--text-3)]">No strengths recorded.</li>}
            </ul>
          </div>
          <div className="panel p-5">
            <h2 className="text-[15px] font-bold text-[var(--text)] flex items-center gap-2 mb-4">
              <Lightbulb size={16} className="text-[var(--warn)]" /> What You Can Improve
            </h2>
            <ul className="space-y-3">
              {(coaching.improvements || []).map((s, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px] text-[var(--text-2)] leading-relaxed">
                  <AlertTriangle size={15} className="text-[var(--warn)] mt-0.5 shrink-0" /> {s}
                </li>
              ))}
              {!coaching.improvements?.length && <li className="text-[13px] text-[var(--text-3)]">No improvement notes recorded.</li>}
            </ul>
          </div>
        </div>
      </div>

      {/* ---------- Answer analysis ---------- */}
      <div id="answer-analysis" className="panel overflow-hidden">
        <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-2)]">
          <div>
            <h2 className="text-[16px] font-bold text-[var(--text)]">Answer Analysis</h2>
            <p className="text-[12.5px] text-[var(--text-3)] mt-0.5">
              {qa.length ? `${qa.length} question${qa.length > 1 ? 's' : ''} evaluated for relevance, structure and completeness` : 'Questions detected from your transcript'}
            </p>
          </div>
          {behavioral && <span className="badge badge-indigo">STAR framework applied</span>}
        </div>

        {qa.length === 0 ? (
          <p className="px-5 py-6 text-[13px] text-[var(--text-3)]">
            No distinct question-answer segments were detected in this transcript. Add a longer recording with clearer questions to enable answer-level analysis.
          </p>
        ) : (
          <div className="divide-y divide-[var(--border-2)]">
            {qa.map((q, idx) => {
              const open = openQa === idx
              const isBehavioral = q.category === 'behavioral'
              return (
                <div key={idx}>
                  <button
                    className={`w-full flex items-center gap-3 px-5 py-4 text-left transition-colors cursor-pointer ${open ? 'bg-[var(--accent-bg)]' : 'hover:bg-[var(--surface-2)]'}`}
                    onClick={() => setOpenQa(open ? -1 : idx)}
                    aria-expanded={open}
                  >
                    <span
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-[11.5px] font-bold shrink-0 border"
                      style={{ background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.26)', color: 'var(--accent)' }}
                    >
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13.5px] font-semibold text-[var(--text)] truncate">{q.question || `Question ${idx + 1}`}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1">
                        <span className={`badge ${q.category === 'behavioral' ? 'badge-violet' : q.category === 'technical' ? 'badge-cyan' : 'badge-gray'}`}>{q.category || 'general'}</span>
                        {q.overall_answer_score != null && (
                          <span className="text-[12px] font-semibold text-[var(--text-2)]">Quality {Math.round(q.overall_answer_score)}/100</span>
                        )}
                      </div>
                    </div>
                    <ChevronDown size={16} className={`text-[var(--text-3)] transition-transform shrink-0 ${open ? 'rotate-180' : ''}`} />
                  </button>

                  {open && (
                    <div className="px-5 pb-6 pt-1 sm:pl-[68px] anim-fade-in grid lg:grid-cols-2 gap-5">
                      <div>
                        <p className="kicker mb-2">Candidate Answer</p>
                        <p className="text-[13px] text-[var(--text-2)] leading-relaxed bg-[var(--surface-2)] rounded-lg p-3.5 border border-[var(--border)]">
                          “{q.answer}”
                        </p>
                        {isBehavioral && (
                          <div className="mt-4">
                            <p className="kicker mb-2">STAR Structure</p>
                            <StarRow star={q.star} />
                          </div>
                        )}
                        <div className="flex flex-wrap gap-2 mt-4">
                          {[
                            ['Relevance', q.relevance_score],
                            ['Completeness', q.completeness_score],
                            ['Clarity', q.clarity_score],
                            ['Conciseness', q.conciseness_score],
                            ['STAR', q.star_score],
                          ].filter(([, v]) => v != null).map(([l, v]) => (
                            <span key={l} className="badge badge-gray">
                              {l}: <b className="text-[var(--text)] ml-0.5">{Math.round(v)}</b>
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-4">
                        {q.strengths?.length > 0 && (
                          <div>
                            <p className="kicker mb-2" style={{ color: 'var(--success)' }}>Strengths</p>
                            <ul className="space-y-1.5">
                              {q.strengths.map((s, i) => (
                                <li key={i} className="flex items-start gap-2 text-[12.5px] text-[var(--text-2)]">
                                  <Check size={13} className="text-[var(--success)] mt-1 shrink-0" />{s}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {q.missing?.length > 0 && (
                          <div>
                            <p className="kicker mb-2" style={{ color: 'var(--warn)' }}>Missing Elements</p>
                            <ul className="space-y-1.5">
                              {q.missing.map((s, i) => (
                                <li key={i} className="flex items-start gap-2 text-[12.5px] text-[var(--text-2)]">
                                  <AlertTriangle size={13} className="text-[var(--warn)] mt-1 shrink-0" />{s}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {q.improvement && (
                          <div className="rounded-lg border border-[var(--accent)]/25 bg-[var(--accent-bg)] p-3.5 text-[12.5px] text-[var(--text-2)]">
                            <span className="font-bold text-[var(--accent)]">Suggested improvement: </span>{q.improvement}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ---------- Recording + transcript ---------- */}
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="panel overflow-hidden flex flex-col">
          <div className="px-5 py-4 flex items-center justify-between gap-3 border-b border-[var(--border-2)]">
            <div>
              <h2 className="text-[15px] font-bold text-[var(--text)]">Interview Recording</h2>
              <p className="text-[12px] text-[var(--text-3)] mt-0.5">Click timeline markers or transcript lines to jump</p>
            </div>
            <span className="badge badge-gray"><Film size={11} /> Video</span>
          </div>
          <div className="p-5 pb-3">
            <div className="rounded-xl overflow-hidden border border-[var(--border)] bg-black aspect-video flex items-center justify-center">
              {d.is_demo ? (
                <div className="text-center px-6">
                  <Film size={26} className="mx-auto mb-2 text-[var(--text-3)]" />
                  <p className="text-[13px] font-semibold text-[var(--text-2)]">Demo interview</p>
                  <p className="text-[12px] text-[var(--text-3)] mt-1">Timeline events below are generated from the sample transcript.</p>
                </div>
              ) : (
                <video ref={videoRef} controls className="w-full h-full object-contain" src={getVideoUrl(d.id)} onTimeUpdate={(e) => setActiveTime(e.target.currentTime)} />
              )}
            </div>
          </div>
          <div className="flex-1 px-5 pb-5">
            <Timeline events={events} duration={d.duration} onSeek={seek} activeTime={activeTime} />
          </div>
        </div>

        <div className="panel overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-[var(--border-2)]">
            <h2 className="text-[15px] font-bold text-[var(--text)]">Transcript</h2>
            <p className="text-[12px] text-[var(--text-3)] mt-0.5">What was said, with detected issues highlighted</p>
          </div>
          <div className="flex-1 p-5">
            <TranscriptViewer
              segments={segments}
              fillerInstances={d.filler_words_detail?.instances || []}
              onSeek={seek}
              activeTime={activeTime}
            />
          </div>
        </div>
      </div>

      {/* ---------- 7-day plan ---------- */}
      {plan.length > 0 && (
        <div id="practice-plan" className="panel p-5">
          <div className="flex items-center gap-2.5 mb-5">
            <span
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border"
              style={{ background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.26)', color: 'var(--accent)' }}
            >
              <TrendingUp size={16} />
            </span>
            <div>
              <h2 className="text-[16px] font-bold text-[var(--text)]">Recommended 7-Day Practice Plan</h2>
              <p className="text-[12px] text-[var(--text-3)] mt-0.5">Built from the weakest dimensions in this analysis</p>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {plan.map((p) => (
              <div key={p.day} className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4 flex flex-col tile">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span
                    className="w-7 h-7 rounded-lg text-white text-[12px] font-bold flex items-center justify-center"
                    style={{ background: 'var(--grad)', boxShadow: '0 4px 14px rgba(129,11,56,.4)' }}
                  >
                    D{p.day}
                  </span>
                  {p.duration && <span className="badge badge-gray">{p.duration}</span>}
                </div>
                <p className="text-[13.5px] font-bold text-[var(--text)] leading-snug">{p.title}</p>
                {p.focus && <p className="text-[11.5px] text-[var(--accent)] font-semibold mt-1">{p.focus}</p>}
                <p className="text-[12px] text-[var(--text-3)] mt-2 flex-1 leading-relaxed">{p.exercise}</p>
                {p.target && (
                  <p className="text-[11.5px] font-semibold text-[var(--success)] mt-3 border-t border-[var(--border)] pt-2.5">
                    Target: {p.target}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[11.5px] text-[var(--text-3)] text-center pt-1 flex items-center justify-center gap-1.5">
        <FileText size={12} /> Report generated {formatDateTime(d.updated_at || d.created_at)} from this recording only.
      </p>
    </div>
  )
}
