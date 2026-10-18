import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Mic, MicOff, Video, VideoOff, Play, Square, ArrowRight, Timer, Keyboard,
  Volume2, AlertCircle, CheckCircle2, ListChecks, MessageSquareText, Sparkles,
  RotateCcw, Home as HomeIcon, Gauge, PauseCircle,
} from 'lucide-react'
import { scoreTone, formatTimecode, formatDuration } from '../utils'
import {
  getLiveDatasetInfo, startLiveSession, submitLiveAnswer,
  finishLiveSession, abandonLiveSession,
} from '../api/live'
import useSpeechRecognition from '../components/live/useSpeechRecognition'
import ScoreRing from '../components/ScoreRing'
import MetricCard from '../components/MetricCard'
import EmptyState from '../components/EmptyState'

const QUESTION_SECONDS = 120

/* ------------------------------ Setup screen ----------------------------- */

function DevicePill({ ok, icon: Icon, label, detail }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
      <span
        className="w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0 border"
        style={{ background: ok ? 'var(--success-bg)' : 'var(--error-bg)', borderColor: 'transparent', color: ok ? 'var(--success)' : 'var(--error)' }}
      >
        <Icon size={16} />
      </span>
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-[var(--text)]">{label}</p>
        <p className="text-[11.5px] text-[var(--text-3)] truncate">{detail}</p>
      </div>
      <span className={`ml-auto badge ${ok ? 'badge-green' : 'badge-red'}`}>{ok ? 'Ready' : 'Blocked'}</span>
    </div>
  )
}

function SetupScreen({ dataset, onStart, starting, error }) {
  const [camState, setCamState] = useState('idle') // idle | ok | denied
  const [micState, setMicState] = useState('idle')
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  // When Start is pressed the probe stream is handed to the interview page so
  // the whole session uses exactly ONE camera stream (no second getUserMedia).
  const transferredRef = useRef(false)

  const probe = useCallback(async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      streamRef.current = s
      if (videoRef.current) videoRef.current.srcObject = s
      setCamState('ok')
      setMicState('ok')
    } catch {
      setCamState('denied')
      setMicState('denied')
    }
  }, [])

  useEffect(() => {
    probe()
    return () => {
      if (!transferredRef.current) streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [probe])

  const questions = dataset?.total_questions ?? 0

  return (
    <div className="grid lg:grid-cols-5 gap-5 items-stretch anim-fade-up">
      <div className="lg:col-span-3 panel-focus p-5 sm:p-7 relative overflow-hidden">
        <span className="glow-burgundy -top-20 -right-16 w-64 h-64 opacity-60" aria-hidden />
        <p className="kicker mb-2">Live Session</p>
        <h1 className="display text-[28px] sm:text-[36px] text-[var(--text)]">
          Live AI Interview<span className="text-[var(--accent)]">.</span>
        </h1>
        <p className="text-[13.5px] text-[var(--text-2)] mt-3 leading-relaxed max-w-md">
          Answer real dataset questions with your microphone. Each spoken answer is transcribed
          and recorded — after the final question, all answers are evaluated together into a
          full performance report.
        </p>

        <div className="mt-6 rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border-2)', background: 'black' }}>
          <video ref={videoRef} autoPlay muted playsInline className="w-full aspect-video object-cover" />
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <span className={`badge ${camState === 'ok' ? 'badge-green' : camState === 'denied' ? 'badge-red' : 'badge-gray'}`}>
            <Video size={11} /> Camera {camState === 'ok' ? 'detected' : camState === 'denied' ? 'blocked' : 'checking…'}
          </span>
          <span className={`badge ${micState === 'ok' ? 'badge-green' : micState === 'denied' ? 'badge-red' : 'badge-gray'}`}>
            <Mic size={11} /> Microphone {micState === 'ok' ? 'detected' : micState === 'denied' ? 'blocked' : 'checking…'}
          </span>
        </div>

        <div className="mt-6 grid sm:grid-cols-3 gap-3">
          <div className="p-3.5 rounded-xl border" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
            <p className="kicker mb-1">Questions</p>
            <p className="text-[20px] font-extrabold text-[var(--text)]" style={{ fontFamily: 'var(--font-display)' }}>6</p>
          </div>
          <div className="p-3.5 rounded-xl border" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
            <p className="kicker mb-1">Per answer</p>
            <p className="text-[20px] font-extrabold text-[var(--text)]" style={{ fontFamily: 'var(--font-display)' }}>{QUESTION_SECONDS / 60} min</p>
          </div>
          <div className="p-3.5 rounded-xl border" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
            <p className="kicker mb-1">Estimated</p>
            <p className="text-[20px] font-extrabold text-[var(--text)]" style={{ fontFamily: 'var(--font-display)' }}>~15 min</p>
          </div>
        </div>
      </div>

      <div className="lg:col-span-2 panel p-5 sm:p-6 flex flex-col">
        <h2 className="text-[15px] font-bold text-[var(--text)]">How it works</h2>
        <ol className="mt-4 space-y-3.5 flex-1">
          {[
            'A question from the dataset appears — read it aloud or press "Read question" to hear it.',
            { text: 'Answer with your microphone; live transcription appears as you speak.', icon: Mic },
            'Press "Finish answer" — your answer is recorded and the next question begins. Nothing is scored yet.',
            'After Question 6, all six answers are evaluated together into the full report: scores, keywords, speech metrics.',
          ].map((step, i) => {
            const icon = typeof step === 'object' ? step.icon : null
            const text = typeof step === 'object' ? step.text : step
            return (
              <li key={i} className="flex items-start gap-3">
                <span className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[11px] font-bold border" style={{ borderColor: 'rgba(194,20,79,.35)', background: 'var(--accent-bg)', color: 'var(--accent)' }}>{i + 1}</span>
                <p className="text-[13px] text-[var(--text-2)] leading-relaxed">
                  {text}
                  {icon && <icon size={12} className="inline mx-1 -mt-0.5" />}
                </p>
              </li>
            )
          })}
        </ol>

        {error && (
          <p className="text-[12.5px] text-[var(--error)] flex items-center gap-1.5 mt-4">
            <AlertCircle size={13} /> {error}
          </p>
        )}

        <button
          onClick={() => { transferredRef.current = true; onStart(streamRef.current) }}
          disabled={starting}
          className="btn btn-primary btn-lg w-full justify-center mt-6"
        >
          {starting ? 'Preparing questions…' : <><Play size={16} /> Start Interview</>}
        </button>
        <p className="text-[11.5px] text-[var(--text-3)] mt-3 text-center">
          {questions > 0 ? `${questions} questions available in the dataset` : 'Loading question dataset…'}
        </p>
      </div>
    </div>
  )
}

/* ------------------------------ Live screen ------------------------------ */

function LiveScreen({ session, index, question, videoRef, answerText, interim, listening, elapsed, camError, typedMode, onToggleTyping, onTypedChange, speechError, onReadAloud, onFinishAnswer, onEnd }) {
  const qNum = index + 1
  const total = session.questions.length

  return (
    <div className="grid lg:grid-cols-5 gap-5 items-stretch anim-fade-up">
      {/* Camera + controls */}
      <div className="lg:col-span-3 panel-focus p-4 sm:p-5 flex flex-col relative overflow-hidden">
        <div className="flex items-center justify-between gap-3 mb-3">
          <span className="badge badge-red"><span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" /> LIVE</span>
          <span className="badge badge-gray tabular-nums"><Timer size={11} /> {formatTimecode(elapsed)}</span>
          <span className={`badge ${listening ? 'badge-green' : 'badge-gray'}`}>
            {listening ? <Mic size={11} /> : <MicOff size={11} />} {listening ? 'Listening' : 'Mic idle'}
          </span>
        </div>

        <div className="rounded-xl overflow-hidden border flex-1 min-h-[240px]" style={{ borderColor: 'var(--border-2)', background: 'black' }}>
          {camError ? (
            <div className="w-full h-full min-h-[240px] flex flex-col items-center justify-center gap-3 text-center p-6">
              <VideoOff size={28} className="text-[var(--text-3)]" />
              <p className="text-[13px] text-[var(--text-2)] max-w-xs">{camError}</p>
            </div>
          ) : (
            <video ref={videoRef} id="live-cam" autoPlay muted playsInline className="w-full aspect-video object-cover" />
          )}
        </div>

        {/* Transcript */}
        <div className="mt-3 rounded-xl border p-3.5 min-h-[86px]" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
          <p className="kicker mb-1.5">Live transcript</p>
          {typedMode ? (
            <textarea
              value={answerText}
              onChange={(e) => onTypedChange(e.target.value)}
              placeholder="Type your answer here…"
              className="input w-full min-h-[64px] text-[13.5px]"
              autoFocus
            />
          ) : (
            <p className="text-[13.5px] text-[var(--text)] leading-relaxed">
              {answerText || <span className="text-[var(--text-3)]">Start speaking…</span>}
              {interim && <span className="text-[var(--text-3)]"> {interim}</span>}
            </p>
          )}
          {speechError && (
            <p className="text-[11.5px] text-[var(--warn)] mt-2 flex items-center gap-1.5">
              <AlertCircle size={12} /> {speechError}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-4">
          <button onClick={onFinishAnswer} className="btn btn-primary flex-1 justify-center min-w-[180px]">
            <CheckCircle2 size={16} /> Finish answer
          </button>
          <button onClick={onToggleTyping} className="btn btn-secondary" title="Toggle typing mode">
            <Keyboard size={15} /> {typedMode ? 'Speak' : 'Type'}
          </button>
          <button onClick={onEnd} className="btn btn-ghost text-[var(--error)]">End interview</button>
        </div>
      </div>

      {/* Question panel */}
      <div className="lg:col-span-2 panel p-5 sm:p-6 flex flex-col">
        <div className="flex items-center justify-between gap-3">
          <p className="kicker">Question {qNum} of {total}</p>
          <span className="badge badge-violet">{question.category}</span>
        </div>

        <blockquote className="mt-5 relative pl-4 border-l-2" style={{ borderColor: 'var(--accent)' }}>
          <p className="text-[19px] sm:text-[21px] font-bold text-[var(--text)] leading-snug" style={{ fontFamily: 'var(--font-display)' }}>
            {question.question}
          </p>
        </blockquote>
        <p className="text-[11.5px] text-[var(--text-3)] mt-2">Difficulty: {question.difficulty}</p>

        <button onClick={onReadAloud} className="btn btn-secondary btn-sm mt-4 self-start">
          <Volume2 size={14} /> Read question aloud
        </button>

        {/* progress dots */}
        <div className="mt-auto pt-6">
          <div className="flex items-center gap-1.5">
            {session.questions.map((_, i) => (
              <span
                key={i}
                className="h-1.5 rounded-full transition-all duration-300"
                style={{
                  flex: 1,
                  background: i < qNum ? 'var(--accent)' : 'var(--surface-3)',
                  boxShadow: i < qNum ? '0 0 8px rgba(194,20,79,.5)' : 'none',
                }}
              />
            ))}
          </div>
          <p className="text-[11.5px] text-[var(--text-3)] mt-3">
            Your answer is being transcribed live — press “Finish answer” when you're done.
          </p>
        </div>
      </div>
    </div>
  )
}

/* ------------------------- Answer recorded screen ------------------------ */

/**
 * Shown between questions instead of a per-answer score: answers are only
 * recorded here — the full evaluation runs once, after the last question.
 */
function AnswerRecorded({ index, total, category, answeredCount, onNext, onEnd }) {
  const qNum = index + 1
  const isLast = qNum >= total
  return (
    <div className="max-w-3xl mx-auto anim-fade-up">
      <div className="panel-focus p-5 sm:p-7 relative overflow-hidden">
        <span className="glow-burgundy -top-20 -right-20 w-64 h-64 opacity-50" aria-hidden />
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <span
            className="w-[140px] h-[140px] rounded-full flex items-center justify-center shrink-0 border-4"
            style={{ borderColor: 'var(--success)', background: 'var(--success-bg)', color: 'var(--success)' }}
          >
            <CheckCircle2 size={56} />
          </span>
          <div className="flex-1 text-center sm:text-left">
            <p className="kicker mb-1.5">Answer {qNum} of {total} recorded</p>
            <h2 className="text-[22px] font-extrabold text-[var(--text)] tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
              {isLast ? 'All questions answered.' : 'Answer saved.'}
            </h2>
            <p className="text-[13px] text-[var(--text-2)] mt-2 leading-relaxed">
              {isLast
                ? 'That was the final question. All six answers will now be evaluated together into your complete interview report.'
                : 'Scores are withheld until the end — after the last question, all your answers are evaluated together into one complete report.'}
            </p>
            <div className="flex flex-wrap gap-2 mt-3 justify-center sm:justify-start">
              <span className="badge badge-green"><CheckCircle2 size={11} /> {answeredCount} of {total} answers recorded</span>
              <span className="badge badge-violet">{category}</span>
            </div>
          </div>
        </div>

        {/* progress dots */}
        <div className="mt-6 flex items-center gap-1.5">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className="h-1.5 rounded-full transition-all duration-300"
              style={{
                flex: 1,
                background: i < qNum ? 'var(--accent)' : 'var(--surface-3)',
                boxShadow: i < qNum ? '0 0 8px rgba(194,20,79,.5)' : 'none',
              }}
            />
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-6">
          <button onClick={onNext} className="btn btn-primary btn-lg flex-1 justify-center min-w-[180px]">
            {isLast ? <>Evaluate interview <Sparkles size={15} /></> : <>Next question <ArrowRight size={15} /></>}
          </button>
          <button onClick={onEnd} className="btn btn-ghost text-[var(--error)]">End interview</button>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------ Results view ----------------------------- */

function ResultsView({ report, onRestart }) {
  const tone = (s) => scoreTone(s)
  return (
    <div className="space-y-5 anim-fade-up">
      {/* Hero */}
      <div className="panel-focus p-5 sm:p-8 relative overflow-hidden">
        <span className="glow-burgundy -top-24 -right-16 w-72 h-72 opacity-60" aria-hidden />
        <div className="flex flex-col md:flex-row items-center gap-8">
          <ScoreRing score={report.overall_score} size={190} label="Overall score" />
          <div className="flex-1 min-w-0">
            <p className="kicker mb-2">Live Interview Report</p>
            <h1 className="display text-[28px] sm:text-[38px] text-[var(--text)]">Session complete<span className="text-[var(--accent)]">.</span></h1>
            <p className="text-[14px] text-[var(--text-2)] mt-3 leading-relaxed max-w-xl">{report.overall_feedback}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              {report.categories.map((c) => <span key={c} className="badge badge-violet">{c}</span>)}
            </div>
          </div>
        </div>
      </div>

      {/* Dimension cards */}
      <div className="grid sm:grid-cols-3 gap-4">
        <MetricCard title="Technical Answer" value={report.technical_score} icon={ListChecks} caption="How closely answers matched the reference content" />
        <MetricCard title="Communication" value={report.communication_score} icon={MessageSquareText} caption="Structure, clarity and confident phrasing" />
        <MetricCard title="Speech Delivery" value={report.speech_score} icon={Gauge} caption="Filler words and speaking pace" />
      </div>

      {/* Speech metrics strip */}
      <div className="panel p-5">
        <h2 className="text-[15px] font-bold text-[var(--text)] mb-4">Speech metrics</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Speaking speed', value: `${report.words_per_minute ?? 0} WPM` },
            { label: 'Filler words', value: report.fillers_total ?? 0 },
            { label: 'Pauses', value: report.pauses_total ?? 0 },
            { label: 'Answer time', value: formatDuration(report.duration_s) },
          ].map((m) => (
            <div key={m.label} className="p-3.5 rounded-xl border" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
              <p className="kicker mb-1.5">{m.label}</p>
              <p className="text-[20px] font-extrabold text-[var(--text)]" style={{ fontFamily: 'var(--font-display)' }}>{m.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Strengths & improvements */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="panel p-5">
          <h2 className="text-[15px] font-bold text-[var(--text)] mb-3 flex items-center gap-2"><CheckCircle2 size={16} className="text-[var(--success)]" /> Strengths</h2>
          <ul className="space-y-2.5">
            {report.strengths.map((s, i) => (
              <li key={i} className="text-[13px] text-[var(--text-2)] flex items-start gap-2.5">
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: 'var(--success)' }} /> {s}
              </li>
            ))}
          </ul>
        </div>
        <div className="panel p-5">
          <h2 className="text-[15px] font-bold text-[var(--text)] mb-3 flex items-center gap-2"><AlertCircle size={16} className="text-[var(--warn)]" /> Areas for improvement</h2>
          <ul className="space-y-2.5">
            {report.areas_for_improvement.map((s, i) => (
              <li key={i} className="text-[13px] text-[var(--text-2)] flex items-start gap-2.5">
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: 'var(--warn)' }} /> {s}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Question-by-question */}
      <div className="panel overflow-hidden">
        <div className="px-5 py-4 border-b border-[var(--border-2)]">
          <h2 className="text-[15px] font-bold text-[var(--text)]">Question-by-question</h2>
          <p className="text-[12px] text-[var(--text-3)] mt-0.5">Your answer vs the dataset reference</p>
        </div>
        <div className="divide-y" style={{ borderColor: 'var(--border-2)' }}>
          {report.results.map((r, i) => (
            <details key={i} className="group">
              <summary className="flex items-center gap-3.5 px-5 py-4 cursor-pointer list-none hover:bg-[var(--accent-bg-2)] transition-colors">
                <span className="w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0 border" style={{ borderColor: 'var(--border-2)', color: tone(r.answer_score), background: 'var(--surface-2)' }}>
                  {i + 1}
                </span>
                <p className="text-[13.5px] font-semibold text-[var(--text)] flex-1 min-w-0 truncate">{r.question}</p>
                <span className="badge badge-gray hidden sm:inline-flex">{r.category}</span>
                <span className="font-extrabold tabular-nums" style={{ color: tone(r.answer_score) }}>{r.answer_score.toFixed(0)}</span>
                <ArrowRight size={14} className="text-[var(--text-3)] rotate-90 group-open:-rotate-90 transition-transform" />
              </summary>
              <div className="px-5 pb-5 pt-1 grid md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border" style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
                  <p className="kicker mb-2">Your answer</p>
                  <p className="text-[13px] text-[var(--text-2)] leading-relaxed">{r.candidate_answer || <span className="italic text-[var(--text-3)]">(no answer captured)</span>}</p>
                </div>
                <div className="p-4 rounded-xl border" style={{ borderColor: 'rgba(194,20,79,.25)', background: 'var(--accent-bg)' }}>
                  <p className="kicker mb-2">Expected answer</p>
                  <p className="text-[13px] text-[var(--text-2)] leading-relaxed">{r.expected_answer}</p>
                </div>
                <div className="md:col-span-2 flex flex-wrap gap-2">
                  {r.keywords_hit?.map((k) => <span key={k} className="badge badge-green">{k}</span>)}
                  {r.keywords_missed?.map((k) => <span key={k} className="badge badge-gray">{k}</span>)}
                </div>
                <p className="md:col-span-2 text-[12.5px] text-[var(--text-2)] leading-relaxed">{r.feedback}</p>
              </div>
            </details>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 justify-center pt-2">
        <button onClick={onRestart} className="btn btn-primary"><RotateCcw size={15} /> New live interview</button>
        <Link to="/" className="btn btn-secondary"><HomeIcon size={15} /> Back to dashboard</Link>
      </div>
    </div>
  )
}

/* --------------------------------- Page ---------------------------------- */

export default function LiveInterviewPage() {
  const [phase, setPhase] = useState('setup') // setup | live | recorded | loading | results
  const [dataset, setDataset] = useState(null)
  const [session, setSession] = useState(null)
  const [qIndex, setQIndex] = useState(0)
  const [answeredCount, setAnsweredCount] = useState(0)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)

  // live state
  const [typedMode, setTypedMode] = useState(false)
  const [typedValue, setTypedValue] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [camError, setCamError] = useState('')
  const [loadingMsg, setLoadingMsg] = useState('Working…')
  // Bumped whenever the shared stream is (re)acquired so the video-attach
  // effect re-runs even if phase/qIndex did not change (async getUserMedia).
  const [streamRev, setStreamRev] = useState(0)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const startAtRef = useRef(0)
  const timerRef = useRef(null)
  const pausesAtStartRef = useRef({ count: 0, seconds: 0 })

  useEffect(() => {
    getLiveDatasetInfo().then(setDataset).catch(() => setDataset({ available: false, total_questions: 0, categories: [] }))
  }, [])

  const question = session?.questions?.[qIndex]

  /**
   * ONE MediaStream for the whole session.
   *
   * - Acquired once (or adopted from the setup screen's probe) and kept in
   *   streamRef — never re-requested per question, never released between
   *   questions.
   * - Kept alive across live → recorded → live phase transitions; only
   *   stopped after the final evaluation completes, on explicit exit, or on
   *   unmount.
   */
  const ensureCamera = useCallback(async () => {
    if (streamRef.current?.active) return streamRef.current
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      streamRef.current = s
      // If the user revokes the camera mid-session (browser UI), degrade
      // gracefully instead of showing a frozen preview.
      s.getVideoTracks().forEach((t) => {
        t.addEventListener('ended', () => {
          if (streamRef.current === s) setCamError('Camera was disconnected — the session continues with audio and transcript only.')
        })
      })
      setCamError('')
      setStreamRev((v) => v + 1)
      return s
    } catch (e) {
      const name = e?.name || ''
      setCamError(
        name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError'
          ? 'No camera was found — the session continues with audio and transcript only.'
          : name === 'NotAllowedError' || name === 'SecurityError'
            ? 'Camera access was blocked — the session continues with audio and transcript only. Re-enable the camera in your browser settings to appear on video.'
            : 'Camera unavailable — the session continues with audio and transcript only.'
      )
      return null
    }
  }, [])

  // Keep the <video> element connected to the ONE shared stream across
  // re-renders, question changes and phase transitions (live ↔ recorded).
  // React remounts the element when these views swap; srcObject does not
  // survive that, so reattach it here.
  useEffect(() => {
    const el = videoRef.current
    const stream = streamRef.current
    if (el && stream && stream.active && el.srcObject !== stream) {
      el.srcObject = stream
      el.play?.().catch(() => { /* autoplay guard — muted+playsInline is allowed */ })
    }
  }, [phase, qIndex, streamRev])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  // Final safety net: never leak the camera when leaving the page.
  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    clearInterval(timerRef.current)
  }, [])

  const handleStart = useCallback(async (probeStream) => {
    setStarting(true)
    setError('')
    try {
      const s = await startLiveSession({ totalQuestions: 6 })
      setSession(s)
      setQIndex(0)
      setTypedValue('')
      setTypedMode(false)
      sr.reset()
      setReport(null)
      setAnsweredCount(0)
      setPhase('live')
      startAtRef.current = Date.now()
      pausesAtStartRef.current = { count: 0, seconds: 0 }
      setElapsed(0)
      clearInterval(timerRef.current)
      timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startAtRef.current) / 1000)), 1000)
      // Adopt the setup screen's probe stream when it is still alive — exactly
      // one camera stream for the entire session. Otherwise request one.
      if (probeStream && probeStream.active) {
        streamRef.current = probeStream
        probeStream.getVideoTracks().forEach((t) => {
          t.addEventListener('ended', () => {
            if (streamRef.current === probeStream) setCamError('Camera was disconnected — the session continues with audio and transcript only.')
          })
        })
        setCamError('')
        setStreamRev((v) => v + 1)
      } else {
        await ensureCamera()
      }
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not start the session. Is the backend running?')
    } finally {
      setStarting(false)
    }
  }, [ensureCamera])

  // Records the finished answer. NO evaluation happens here — per-answer
  // scoring was removed on purpose; everything is evaluated once after Q6.
  const finishAnswer = useCallback(async () => {
    if (!session || !question) return
    setPhase('loading')
    setLoadingMsg('Recording your answer…')
    const finalText = (typedMode ? typedValue : srTextRef.current).trim()
    try {
      const res = await submitLiveAnswer(session.session_id, {
        questionId: question.question_id,
        transcript: finalText,
        durationS: elapsed,
        pauseCount: Math.max(0, sr.pauses.current.count - pausesAtStartRef.current.count),
        pauseSecondsTotal: Math.max(0, sr.pauses.current.seconds - pausesAtStartRef.current.seconds),
      })
      // Server-confirmed record count (includes this answer).
      setAnsweredCount(res?.answered_count ?? qIndex + 1)
      setPhase('recorded')
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not record the answer. Please try again.')
      setPhase('live')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, question, typedMode, typedValue, elapsed, qIndex])

  const startEvaluation = useCallback(async () => {
    if (!session) return
    // The last answer (Q6) was already persisted server-side before the
    // "recorded" screen appeared (finishAnswer awaited submitLiveAnswer), so
    // /finish always evaluates the complete set — no React state races.
    setPhase('loading')
    setLoadingMsg(`Evaluating all ${session.questions.length} answers…`)
    try {
      const rep = await finishLiveSession(session.session_id)
      setReport(rep)
      setPhase('results')
      // Camera + mic are released ONLY now — after the complete evaluation.
      stopCamera()
      clearInterval(timerRef.current)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not evaluate the interview. Please try again.')
      setPhase('recorded')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, stopCamera])

  const nextQuestion = useCallback(() => {
    if (!session) return
    const isLast = qIndex + 1 >= session.questions.length
    if (isLast) {
      startEvaluation()
    } else {
      setQIndex((i) => i + 1)
      setTypedValue('')
      setTypedMode(false)
      sr.reset()
      pausesAtStartRef.current = { ...sr.pauses.current }
      setPhase('live')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, qIndex, startEvaluation])

  const endInterview = useCallback(async () => {
    stopCamera()
    clearInterval(timerRef.current)
    sr.stop()
    if (session) {
      try { await abandonLiveSession(session.session_id) } catch { /* best effort */ }
    }
    setPhase('setup')
    setSession(null)
    setQIndex(0)
    setTypedValue('')
    setReport(null)
    setAnsweredCount(0)
  }, [session, stopCamera])

  // Speech recognition for the whole live phase (rules of hooks: called
  // unconditionally at the top level of the component).
  const sr = useSpeechRecognition()
  // Latest transcript via ref so memoized callbacks never read a stale sr.
  const srTextRef = useRef('')
  srTextRef.current = sr.text

  useEffect(() => {
    if (phase === 'live' && !typedMode) sr.start()
    if (phase !== 'live') sr.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, typedMode])

  const readAloud = useCallback(() => {
    if (!question || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(question.question)
    u.rate = 0.95
    window.speechSynthesis.speak(u)
  }, [question])

  if (phase === 'setup') {
    return <SetupScreen dataset={dataset} onStart={handleStart} starting={starting} error={error} />
  }

  if (!session || !question) {
    return (
      <div className="panel p-10 flex flex-col items-center justify-center gap-4 min-h-[300px]">
        <span className="skeleton w-10 h-10 rounded-full" />
        <p className="text-[13px] text-[var(--text-3)]">Preparing your session…</p>
      </div>
    )
  }

  if (phase === 'live') {
    return (
      <LiveScreen
        session={session}
        index={qIndex}
        question={question}
        videoRef={videoRef}
        answerText={typedMode ? typedValue : sr.text}
        interim={sr.interim}
        listening={sr.listening}
        elapsed={elapsed}
        camError={camError}
        typedMode={typedMode}
        onToggleTyping={() => setTypedMode(!typedMode)}
        onTypedChange={setTypedValue}
        speechError={sr.error}
        onReadAloud={readAloud}
        onFinishAnswer={finishAnswer}
        onEnd={endInterview}
      />
    )
  }

  if (phase === 'recorded') {
    return (
      <AnswerRecorded
        index={qIndex}
        total={session.questions.length}
        category={question.category}
        answeredCount={answeredCount}
        onNext={nextQuestion}
        onEnd={endInterview}
      />
    )
  }

  if (phase === 'results' && report) {
    return <ResultsView report={report} onRestart={endInterview} />
  }

  // loading (recording an answer / evaluating the whole interview)
  return (
    <div className="panel p-10 flex flex-col items-center justify-center gap-4 min-h-[300px]">
      <span className="skeleton w-10 h-10 rounded-full" />
      <p className="text-[13px] text-[var(--text-3)]">{loadingMsg}</p>
      {phase === 'loading' && loadingMsg.startsWith('Evaluating') && (
        <p className="text-[11.5px] text-[var(--text-3)]">This runs once, over every recorded answer.</p>
      )}
    </div>
  )
}
