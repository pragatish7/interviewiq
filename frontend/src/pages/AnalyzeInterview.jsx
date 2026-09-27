import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ArrowRight, Check, Sparkles, Microscope, MessagesSquare, ListChecks, Gauge, Volume2, Timer,
  Mic, FileText, Eye, Video as VideoIcon, AlertCircle, ChevronRight, ClipboardList, Wand2,
} from 'lucide-react'
import { uploadInterview, analyzeInterview, getInterviews } from '../api'
import UploadPanel from '../components/UploadPanel'
import { takePendingFile } from '../uploadStore'
import { timeAgo, scoreTone } from '../utils'

const TYPES = ['General', 'HR', 'Behavioral', 'Technical', 'Mixed']
const ROLES = ['Software Engineer', 'Data Analyst', 'ML Engineer', 'Cybersecurity Analyst', 'Product Manager', 'Other']
const LEVELS = ['Student', 'Entry Level', 'Mid Level', 'Experienced']

const SCOPE = [
  { icon: Mic, label: 'Speech' },
  { icon: MessagesSquare, label: 'Communication' },
  { icon: ListChecks, label: 'Answers' },
  { icon: Gauge, label: 'Pacing' },
  { icon: Volume2, label: 'Filler Words' },
  { icon: Timer, label: 'Pauses' },
  { icon: Sparkles, label: 'Vocabulary' },
  { icon: Eye, label: 'Delivery' },
]

const PIPELINE = [
  { label: 'Video Processing', desc: 'Validating & decoding your recording' },
  { label: 'Audio Extraction', desc: 'Isolating the audio track' },
  { label: 'Transcription', desc: 'Converting speech to text with timestamps' },
  { label: 'Speech Analysis', desc: 'Measuring pace, fillers & pauses' },
  { label: 'NLP Analysis', desc: 'Evaluating vocabulary, clarity & structure' },
  { label: 'Answer Analysis', desc: 'Scoring question responses & STAR structure' },
  { label: 'Video Analysis', desc: 'Reviewing observable delivery signals' },
  { label: 'Generating Insights', desc: 'Building your personalized report' },
]

export default function AnalyzeInterview() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [meta, setMeta] = useState(() => {
    let def = {}
    try { def = JSON.parse(localStorage.getItem('iq-defaults') || '{}') } catch {}
    return {
      interview_type: def.interview_type || 'General',
      target_role: 'Software Engineer',
      experience_level: def.experience_level || 'Mid Level',
      job_description: '',
    }
  })
  const [phase, setPhase] = useState('setup') // setup | uploading | processing | done | error
  const [error, setError] = useState('')
  const [stageIdx, setStageIdx] = useState(0)
  const [recent, setRecent] = useState([])
  const timerRef = useRef(null)

  useEffect(() => {
    const pending = takePendingFile()
    if (pending) setFile(pending)
    getInterviews(0, 4).then((d) => setRecent((d.interviews || []).filter((i) => i.status === 'completed'))).catch(() => {})
    return () => clearInterval(timerRef.current)
  }, [])

  const canStart = !!file && (phase === 'setup')

  const startAnalysis = async () => {
    setError('')
    setPhase('uploading')
    try {
      const up = await uploadInterview(file, { title: file.name.replace(/\.[^.]+$/, ''), ...meta })
      setPhase('processing')
      setStageIdx(0)
      // Advance the pipeline display while the real analysis runs server-side.
      timerRef.current = setInterval(() => {
        setStageIdx((s) => {
          if (s < PIPELINE.length - 1) return s + 1
          clearInterval(timerRef.current)
          return s
        })
      }, 4000)
      const res = await analyzeInterview(up.id)
      clearInterval(timerRef.current)
      setPhase('done')
      navigate(`/interview/${up.id}`)
    } catch (e) {
      clearInterval(timerRef.current)
      setError(e?.response?.data?.detail || e?.message || 'Analysis failed. Please check that ffmpeg is installed and try again.')
      setPhase('error')
    }
  }

  /* ---------- Processing screen ---------- */
  if (phase === 'uploading' || phase === 'processing') {
    const pct = phase === 'uploading' ? 6 : Math.round(((stageIdx + 0.5) / PIPELINE.length) * 100)
    return (
      <div className="max-w-3xl mx-auto anim-fade-up py-4">
        <div className="text-center mb-8">
          <span className="badge badge-indigo mb-4 px-3.5 py-1.5">
            <span className="relative flex w-2 h-2">
              <span className="absolute inset-0 rounded-full bg-[var(--accent)]" style={{ animation: 'pulseRing 1.6s infinite' }} />
              <span className="relative w-2 h-2 rounded-full bg-[var(--accent)]" style={{ animation: 'pulseDot 1.2s infinite' }} />
            </span>
            {phase === 'uploading' ? 'Uploading video' : 'Analysis in progress'}
          </span>
          <h1 className="display text-[30px] sm:text-[38px] text-[var(--text)]">
            {phase === 'uploading' ? 'Uploading your interview' : 'Analyzing interview'}
            <span className="text-[var(--accent)]">.</span>
          </h1>
          <p className="text-[13.5px] text-[var(--text-3)] mt-3">
            This may take a few moments depending on the video length.
          </p>
        </div>

        <div className="panel-focus p-5 sm:p-6">
          <div className="flex items-center gap-4 pb-5 mb-4 border-b border-[var(--border-2)]">
            <div className="flex items-end gap-1 h-8 shrink-0" aria-hidden>
              {[0, 1, 2, 3, 4].map((i) => (
                <span key={i} className="eq-bar h-full" style={{ animationDelay: `${i * 0.12}s` }} />
              ))}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] font-semibold text-[var(--text)] truncate">
                {phase === 'uploading' ? 'Uploading video file…' : PIPELINE[stageIdx]?.label || 'Finalizing…'}
              </p>
              <p className="text-[12px] text-[var(--text-3)] truncate">
                {phase === 'uploading' ? 'Preparing the recording for analysis' : PIPELINE[stageIdx]?.desc}
              </p>
            </div>
            <span className="text-[13px] font-bold tabular-nums text-[var(--accent)] shrink-0">{pct}%</span>
          </div>

          {/* progress meter */}
          <div className="bar-track mb-5" style={{ height: 6 }}>
            <div
              className="bar-fill"
              style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #810b38, #c2144f)', boxShadow: '0 0 16px rgba(194,20,79,.55)' }}
            />
          </div>

          <ul className="space-y-1">
            {PIPELINE.map((step, i) => {
              const state = phase === 'uploading'
                ? 'pending'
                : i < stageIdx ? 'done' : i === stageIdx ? 'active' : 'pending'
              return (
                <li
                  key={step.label}
                  className={`flex items-start gap-3 px-3.5 py-2.5 rounded-lg transition-colors border ${
                    state === 'active' ? 'border-[var(--accent)]/30 bg-[var(--accent-bg)]' : 'border-transparent'
                  }`}
                >
                  <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                    state === 'done' ? 'bg-[var(--success-bg)] text-[var(--success)]'
                    : state === 'active' ? 'bg-[var(--accent)] text-white'
                    : 'bg-[var(--surface-3)] text-[var(--text-3)]'
                  }`}>
                    {state === 'done' ? <Check size={12} strokeWidth={3} />
                      : state === 'active' ? <span className="w-2 h-2 rounded-full bg-white" style={{ animation: 'pulseDot 1s infinite' }} />
                      : <span className="w-1.5 h-1.5 rounded-full bg-current opacity-40" />}
                  </span>
                  <div className="min-w-0">
                    <p className={`text-[13.5px] font-semibold ${state === 'pending' ? 'text-[var(--text-3)]' : 'text-[var(--text)]'}`}>{step.label}</p>
                    {state === 'active' && <p className="text-[12px] text-[var(--accent)] mt-0.5">{step.desc}</p>}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>

        <p className="text-center text-[12px] text-[var(--text-3)] mt-5 flex items-center justify-center gap-1.5">
          <ClipboardList size={13} /> Real analysis running on your uploaded video — results open automatically.
        </p>
      </div>
    )
  }

  /* ---------- Setup + upload workspace ---------- */
  const readiness = [
    { icon: VideoIcon, label: 'Video', state: file ? 'ready' : 'waiting' },
    { icon: Mic, label: 'Audio', state: file ? 'ready' : 'waiting' },
    { icon: FileText, label: 'Transcript', state: file ? 'ready' : 'waiting' },
    { icon: Wand2, label: 'Analysis', state: file ? 'ready' : 'waiting' },
  ]

  return (
    <div className="space-y-6 anim-fade-up">
      {/* Page purpose */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker mb-2">New Analysis</p>
          <h1 className="display text-[28px] sm:text-[34px] text-[var(--text)]">
            Analyze an interview<span className="text-[var(--accent)]">.</span>
          </h1>
          <p className="text-[13.5px] text-[var(--text-2)] mt-2 max-w-xl">
            Upload a recorded mock interview and add context so the analysis can judge relevance and structure properly.
          </p>
        </div>
        <span className="badge badge-gray">MP4 · MOV · WebM · up to 500 MB</span>
      </header>

      {error && (
        <div
          className="rounded-xl px-4 py-3.5 text-[13px] flex items-start gap-3 border"
          style={{ borderColor: 'rgba(239,106,95,.35)', background: 'var(--error-bg)', color: 'var(--error)' }}
        >
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-bold">Analysis could not be completed</p>
            <p className="mt-0.5 opacity-90">{error}</p>
          </div>
          <button className="btn btn-secondary btn-sm shrink-0" onClick={() => setPhase('setup')}>Back</button>
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-5 items-start">
        {/* LEFT — upload workspace */}
        <div className="lg:col-span-3 space-y-5">
          <div className="panel-focus p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <h2 className="text-[17px] font-bold text-[var(--text)] tracking-tight">
                  {file ? 'Video Preview' : 'Upload Workspace'}
                </h2>
                <p className="text-[12.5px] text-[var(--text-3)] mt-1">
                  {file ? 'Review your recording before starting the analysis.' : 'Drop in the recording you want analyzed.'}
                </p>
              </div>
              {file && (
                <button onClick={() => setFile(null)} className="btn btn-secondary btn-sm shrink-0">Replace Video</button>
              )}
            </div>

            <UploadPanel file={file} onFile={setFile} onClear={() => setFile(null)} />

            {/* Readiness strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-5">
              {readiness.map((s) => (
                <div
                  key={s.label}
                  className={`flex items-center gap-2.5 rounded-xl border px-3 py-2.5 transition-all ${
                    s.state === 'ready'
                      ? 'border-[var(--accent)]/30 bg-[var(--accent-bg)]'
                      : 'border-[var(--border)] bg-[var(--surface-2)] opacity-60'
                  }`}
                >
                  <span
                    className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border"
                    style={s.state === 'ready'
                      ? { background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.3)', color: 'var(--accent)' }
                      : { background: 'var(--surface-3)', borderColor: 'var(--border-2)', color: 'var(--text-3)' }}
                  >
                    <s.icon size={14} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[11.5px] font-bold text-[var(--text)] leading-tight">{s.label}</span>
                    <span className={`block text-[10.5px] font-semibold leading-tight ${s.state === 'ready' ? 'text-[var(--success)]' : 'text-[var(--text-3)]'}`}>
                      {s.state === 'ready' ? 'Ready' : 'Waiting'}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Analysis scope */}
          <div className="panel p-5">
            <h2 className="text-[14px] font-bold text-[var(--text)] mb-1">What gets analyzed</h2>
            <p className="text-[12px] text-[var(--text-3)] mb-4">Every dimension below is measured from your recording and transcript.</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {SCOPE.map((s) => (
                <div key={s.label} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12.5px] font-medium text-[var(--text-2)] border border-[var(--border-2)] bg-[var(--surface-2)]">
                  <s.icon size={14} className="text-[var(--accent)] shrink-0" />
                  <span className="truncate">{s.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT — configuration */}
        <div className="lg:col-span-2 space-y-5 lg:sticky lg:top-24">
          <div className="panel p-5">
            <h2 className="text-[15px] font-bold text-[var(--text)] flex items-center gap-2 mb-1">
              <Microscope size={16} className="text-[var(--accent)]" /> Interview Configuration
            </h2>
            <p className="text-[12.5px] text-[var(--text-3)] mb-5">Context helps the analysis evaluate relevance and structure.</p>

            <div className="space-y-4">
              <div>
                <label className="field-label" htmlFor="it-type">Interview Type</label>
                <select id="it-type" value={meta.interview_type} onChange={(e) => setMeta({ ...meta, interview_type: e.target.value })}>
                  {TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="field-label" htmlFor="it-role">Target Role</label>
                <select id="it-role" value={ROLES.includes(meta.target_role) ? meta.target_role : 'Other'} onChange={(e) => setMeta({ ...meta, target_role: e.target.value === 'Other' ? '' : e.target.value })}>
                  {ROLES.map((r) => <option key={r}>{r}</option>)}
                  <option value="">Custom…</option>
                </select>
                {!ROLES.includes(meta.target_role) && (
                  <input
                    type="text"
                    placeholder="Enter target role (e.g. DevOps Engineer)"
                    value={meta.target_role}
                    onChange={(e) => setMeta({ ...meta, target_role: e.target.value })}
                    className="mt-2"
                  />
                )}
              </div>
              <div>
                <label className="field-label" htmlFor="it-level">Experience Level</label>
                <select id="it-level" value={meta.experience_level} onChange={(e) => setMeta({ ...meta, experience_level: e.target.value })}>
                  {LEVELS.map((l) => <option key={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="field-label" htmlFor="it-jd">
                  Job Description <span className="normal-case tracking-normal text-[var(--text-3)] font-medium">(optional)</span>
                </label>
                <textarea
                  id="it-jd"
                  placeholder="Paste the job description — relevant skills in your answers will be detected."
                  value={meta.job_description}
                  onChange={(e) => setMeta({ ...meta, job_description: e.target.value })}
                  rows={3}
                />
              </div>
            </div>

            <button className="btn btn-primary btn-lg w-full justify-center mt-6" disabled={!canStart} onClick={startAnalysis}>
              Start Analysis <ArrowRight size={17} />
            </button>
            {!file && (
              <p className="text-center text-[12px] text-[var(--text-3)] mt-3">Upload a video to enable analysis</p>
            )}
            {phase === 'error' && file && (
              <p className="text-center text-[12px] text-[var(--error)] mt-3 cursor-pointer hover:underline" onClick={startAnalysis}>
                Retry analysis
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Recent interviews */}
      {recent.length > 0 && (
        <div className="panel overflow-hidden">
          <div className="flex items-center justify-between gap-4 px-5 py-4 border-b border-[var(--border-2)]">
            <div>
              <h2 className="text-[15px] font-bold text-[var(--text)]">Recent Interviews</h2>
              <p className="text-[12px] text-[var(--text-3)] mt-0.5">Pick up where you left off.</p>
            </div>
            <Link to="/history" className="btn btn-ghost btn-sm">View history <ArrowRight size={14} /></Link>
          </div>
          <div className="divide-y divide-[var(--border-2)]">
            {recent.map((i) => (
              <Link key={i.id} to={`/interview/${i.id}`} className="flex items-center gap-4 px-5 py-3.5 hover:bg-[var(--accent-bg)] transition-colors group">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: i.overall_score != null ? scoreTone(i.overall_score) : 'var(--border)', boxShadow: i.overall_score != null ? `0 0 8px ${scoreTone(i.overall_score)}88` : undefined }}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-semibold text-[var(--text)] truncate">{i.title}</p>
                  <p className="text-[12px] text-[var(--text-3)] mt-0.5">{i.target_role || 'General'} · {timeAgo(i.created_at)}</p>
                </div>
                {i.overall_score != null && (
                  <span className="font-bold text-[var(--text)] tabular-nums">
                    {Math.round(i.overall_score)}<span className="text-[var(--text-3)] text-[12px] font-medium">/100</span>
                  </span>
                )}
                <ChevronRight size={15} className="text-[var(--text-3)] group-hover:text-[var(--accent)] transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
