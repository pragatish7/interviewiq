import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  MessagesSquare, Send, Plus, Mic, MicOff, Square, Volume2, VolumeX,
  PanelLeftOpen, PanelLeftClose, Trash2, Sparkles, Link2, X, Bot, User,
  Lightbulb, ListChecks, GraduationCap, MessageCircleQuestion, PenLine, RotateCcw,
} from 'lucide-react'
import {
  createCoachSession, listCoachSessions, getCoachSession, deleteCoachSession,
  coachTalk, attachCoachAnalysis, getCoachContext,
} from '../api/coach'
import { timeAgo } from '../utils'
import EmptyState from '../components/EmptyState'

/* ------------------------------ rendering -------------------------------- */

/** Minimal, safe renderer for the coach's markdown-ish replies. */
function RichText({ text }) {
  const blocks = useMemo(() => String(text || '').split('\n'), [text])
  return (
    <div className="space-y-1.5">
      {blocks.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1.5" />
        if (line.trimStart().startsWith('> ')) {
          return (
            <blockquote key={i} className="border-l-2 pl-3 my-2 text-[12.5px] italic leading-relaxed"
              style={{ borderColor: 'var(--accent)', color: 'var(--text-2)' }}>
              {inline(line.trimStart().slice(2))}
            </blockquote>
          )
        }
        return <p key={i} className="leading-relaxed">{inline(line)}</p>
      })}
    </div>
  )
}

function inline(s) {
  const parts = []
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let last = 0, m, k = 0
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) parts.push(<span key={k++}>{s.slice(last, m.index)}</span>)
    const tok = m[0]
    if (tok.startsWith('**')) parts.push(<strong key={k++} className="font-bold">{tok.slice(2, -2)}</strong>)
    else if (tok.startsWith('`')) parts.push(<code key={k++} className="px-1 py-0.5 rounded text-[12px]" style={{ background: 'var(--surface-3)' }}>{tok.slice(1, -1)}</code>)
    else parts.push(<em key={k++}>{tok.slice(1, -1)}</em>)
    last = m.index + tok.length
  }
  if (last < s.length) parts.push(<span key={k++}>{s.slice(last)}</span>)
  return parts
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1.5" aria-label="Coach is typing">
      {[0, 1, 2].map((i) => (
        <span key={i} className="w-1.5 h-1.5 rounded-full" style={{
          background: 'var(--accent-2)',
          animation: `pulseDot 1.2s ease-in-out ${i * 0.18}s infinite`,
        }} />
      ))}
    </span>
  )
}

function Bubble({ msg, onSpeak }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : ''} anim-fade-in`}>
      <span
        className="w-7 h-7 rounded-[9px] flex items-center justify-center shrink-0 mt-0.5 border"
        style={isUser
          ? { background: 'var(--surface-3)', borderColor: 'var(--border)', color: 'var(--text-2)' }
          : { background: 'var(--grad)', borderColor: 'rgba(255,255,255,.16)', color: '#fff7f0', boxShadow: '0 4px 14px rgba(129,11,56,.4)' }}
        aria-hidden
      >
        {isUser ? <User size={13} /> : <Bot size={13} />}
      </span>
      <div className={`max-w-[85%] sm:max-w-[75%] ${isUser ? 'items-end' : ''}`}>
        <div
          className="px-4 py-3 text-[13.5px] rounded-2xl"
          style={isUser
            ? {
                background: 'var(--accent-bg-2)', border: '1px solid var(--border)',
                color: 'var(--text)', borderBottomRightRadius: 6,
              }
            : {
                background: 'var(--surface-2)', border: '1px solid var(--border-2)',
                color: 'var(--text)', borderBottomLeftRadius: 6, boxShadow: 'var(--shadow-xs)',
              }}
        >
          <RichText text={msg.content} />
        </div>
        {!isUser && (
          <button
            onClick={() => onSpeak?.(msg.content)}
            className="mt-1 ml-1 text-[10.5px] text-[var(--text-3)] hover:text-[var(--accent)] inline-flex items-center gap-1 transition-colors"
            title="Read aloud"
          >
            <Volume2 size={11} /> Listen
          </button>
        )}
      </div>
    </div>
  )
}

/* ---------------------------- starter suggestions ------------------------ */

const STARTERS = [
  { icon: MessageCircleQuestion, text: 'How should I answer "tell me about yourself"?' },
  { icon: ListChecks, text: 'Give me an interview question and evaluate my response.' },
  { icon: PenLine, text: 'Can you look at this answer and tell me honestly what\'s wrong?' },
  { icon: GraduationCap, text: 'I\'m applying for a software developer role. What should I prepare?' },
  { icon: Lightbulb, text: 'How do I reduce filler words?' },
  { icon: Sparkles, text: 'Can you interview me like a strict interviewer?' },
]

/* --------------------------------- page ---------------------------------- */

export default function CoachPage() {
  const [sessions, setSessions] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [attachOpen, setAttachOpen] = useState(false)
  const [ctx, setCtx] = useState(null)
  const [snapshot, setSnapshot] = useState(null)
  const [practiceActive, setPracticeActive] = useState(false)
  const [listening, setListening] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(false)
  const [micError, setMicError] = useState('')
  const [error, setError] = useState('')

  const scrollRef = useRef(null)
  const inputRef = useRef(null)
  const recogRef = useRef(null)
  const finalBufRef = useRef('')
  const speakRepliesRef = useRef(false)
  speakRepliesRef.current = speakReplies

  /* ---------- sessions bootstrap ---------- */
  useEffect(() => {
    listCoachSessions()
      .then((d) => {
        const list = d.sessions || []
        setSessions(list)
        if (list.length) loadSession(list[0].id)
      })
      .catch(() => {})
  }, [])

  const loadSession = useCallback(async (id) => {
    try {
      const d = await getCoachSession(id)
      setActiveId(id)
      setMessages(d.messages || [])
      setSnapshot(d.snapshot || null)
      setPracticeActive(!!d.practice_active)
    } catch {
      setError('Could not load that conversation.')
    }
  }, [])

  const newChat = useCallback(async () => {
    setError('')
    try {
      const d = await createCoachSession()
      setActiveId(d.session_id)
      setMessages([])
      setSnapshot(null)
      setPracticeActive(false)
      setSessions((s) => [{ id: d.session_id, title: d.title, updated_at: new Date().toISOString(), message_count: 0 }, ...s])
      inputRef.current?.focus()
    } catch {
      setError('Could not start a new chat. Is the backend running?')
    }
  }, [])

  /* ---------- scroll to bottom ---------- */
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  /* ---------- speech synthesis for replies ---------- */
  const speak = useCallback((text) => {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const clean = String(text).replace(/[*_`#>]/g, '')
    const u = new SpeechSynthesisUtterance(clean.slice(0, 1200))
    u.rate = 1.0
    window.speechSynthesis.speak(u)
  }, [])

  useEffect(() => {
    const last = messages[messages.length - 1]
    if (speakRepliesRef.current && last && last.role === 'coach') speak(last.content)
  }, [messages, speak])

  useEffect(() => () => window.speechSynthesis?.cancel(), [])

  /* ---------- speech recognition (dictate your message) ---------- */
  const toggleMic = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setMicError('Speech recognition is not supported in this browser — please type instead.')
      return
    }
    if (listening) {
      recogRef.current?.stop()
      return
    }
    setError('')
    const r = new SR()
    r.continuous = true
    r.interimResults = true
    r.lang = 'en-US'
    finalBufRef.current = input
    r.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) finalBufRef.current = `${finalBufRef.current} ${t}`.trim()
        else interim += t
      }
      setInput(`${finalBufRef.current}${interim ? ` ${interim}` : ''}`.trimStart())
    }
    r.onerror = (e) => {
      setMicError(e.error === 'not-allowed'
        ? 'Microphone access was blocked. Enable it in your browser settings to dictate.'
        : 'Speech recognition hiccup — please try again.')
      setListening(false)
    }
    r.onend = () => setListening(false)
    recogRef.current = r
    r.start()
    setListening(true)
  }, [listening, input])

  useEffect(() => () => recogRef.current?.stop(), [])

  /* ---------- send ---------- */
  const send = useCallback(async (raw) => {
    const text = (raw ?? input).trim()
    if (!text || sending) return
    recogRef.current?.stop()
    setInput('')
    setSending(true)
    setError('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    try {
      if (!activeId) {
        const d = await createCoachSession()
        setActiveId(d.session_id)
        setSessions((s) => [{ id: d.session_id, title: d.title, updated_at: new Date().toISOString(), message_count: 0 }, ...s])
        const res = await coachTalk(d.session_id, text)
        setMessages((m) => [...m, { role: 'coach', content: res.reply }])
        setPracticeActive(res.practice_active)
        listCoachSessions().then((d2) => setSessions(d2.sessions || [])).catch(() => {})
      } else {
        const res = await coachTalk(activeId, text)
        setMessages((m) => [...m, { role: 'coach', content: res.reply }])
        setPracticeActive(res.practice_active)
      }
    } catch (e) {
      setError(e?.response?.data?.detail || 'The coach could not reply. Please try again.')
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }, [input, sending, activeId])

  /* ---------- attach an existing analysis ---------- */
  useEffect(() => {
    if (attachOpen && !ctx) {
      getCoachContext().then(setCtx).catch(() => setError('Could not load your analyses.'))
    }
  }, [attachOpen, ctx])

  const attach = async (kind, id) => {
    if (!activeId) { await newChat() }
    try {
      const d = await attachCoachAnalysis(activeId, kind, id)
      setMessages(d.messages || [])
      setSnapshot(d.snapshot || null)
      setAttachOpen(false)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not attach that analysis.')
    }
  }

  const removeSession = async (e, id) => {
    e.stopPropagation()
    try {
      await deleteCoachSession(id)
      const remaining = sessions.filter((s) => s.id !== id)
      setSessions(remaining)
      if (activeId === id) {
        if (remaining.length) loadSession(remaining[0].id)
        else newChat()
      }
    } catch { setError('Could not delete that conversation.') }
  }

  const refreshSessions = useCallback(() => {
    listCoachSessions().then((d) => setSessions(d.sessions || [])).catch(() => {})
  }, [])
  useEffect(() => { refreshSessions() }, [refreshSessions])

  const empty = messages.length === 0

  return (
    <div className="anim-fade-up">
      <div className="grid lg:grid-cols-4 gap-5 items-stretch">
        {/* ---------------- Sidebar (desktop) / drawer (mobile) ---------------- */}
        <aside className={`lg:col-span-1 lg:flex flex-col ${sidebarOpen ? 'fixed inset-0 z-50 flex' : 'hidden'}`}>
          {sidebarOpen && <div className="absolute inset-0 bg-black/70" onClick={() => setSidebarOpen(false)} />}
          <div className={`relative flex flex-col w-full max-w-[300px] lg:max-w-none h-full lg:h-auto panel p-3 ${sidebarOpen ? 'ml-auto' : ''}`}>
            <div className="flex items-center justify-between mb-2 px-1">
              <p className="kicker">Conversations</p>
              <button className="lg:hidden p-1.5" onClick={() => setSidebarOpen(false)} aria-label="Close list"><X size={16} /></button>
            </div>
            <button onClick={newChat} className="btn btn-primary btn-sm w-full justify-center mb-3">
              <Plus size={14} /> New chat
            </button>
            <div className="flex-1 lg:max-h-[430px] overflow-y-auto space-y-1 pr-0.5">
              {sessions.length === 0 && (
                <p className="text-[12px] text-[var(--text-3)] px-2 py-4">No conversations yet.</p>
              )}
              {sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => { loadSession(s.id); setSidebarOpen(false) }}
                  className={`group flex items-center gap-2 px-2.5 py-2 rounded-[10px] cursor-pointer border transition-colors ${s.id === activeId ? '' : 'border-transparent hover:bg-[var(--accent-bg-2)]'}`}
                  style={s.id === activeId ? { background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.28)' } : undefined}
                >
                  <MessagesSquare size={13} className="shrink-0 text-[var(--text-3)]" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-semibold text-[var(--text)] truncate">{s.title || 'New chat'}</p>
                    <p className="text-[10.5px] text-[var(--text-3)]">{timeAgo(s.updated_at)} · {s.message_count} msg</p>
                  </div>
                  <button onClick={(e) => removeSession(e, s.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded text-[var(--text-3)] hover:text-[var(--error)] transition-all"
                    aria-label="Delete conversation"><Trash2 size={12.5} /></button>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* ---------------- Chat column ---------------- */}
        <section className="lg:col-span-3 panel-focus relative overflow-hidden flex flex-col min-h-[560px] lg:min-h-[620px]">
          <span className="glow-burgundy -top-20 -right-16 w-64 h-64 opacity-50" aria-hidden />

          {/* Header */}
          <header className="relative z-10 flex items-center gap-2 px-4 sm:px-5 py-3 border-b border-[var(--border-2)]">
            <span className="w-9 h-9 rounded-[10px] flex items-center justify-center border shrink-0"
              style={{ background: 'var(--grad)', borderColor: 'rgba(255,255,255,.16)', color: '#fff7f0' }}>
              <MessagesSquare size={16} />
            </span>
            <div className="min-w-0 mr-auto">
              <h1 className="text-[15.5px] font-extrabold text-[var(--text)] tracking-tight leading-tight" style={{ fontFamily: 'var(--font-display)' }}>
                AI Coach
              </h1>
              <p className="text-[11px] text-[var(--text-3)] leading-tight">
                {sending ? 'typing…' : practiceActive ? 'practice in progress — answer whenever ready' : 'your personal interview mentor'}
              </p>
            </div>
            {snapshot && (
              <span className="hidden sm:inline-flex badge badge-green" title="A completed analysis is attached">
                <Link2 size={10.5} /> Analysis attached
              </span>
            )}
            <button
              onClick={() => setSpeakReplies((v) => !v)}
              className={`p-2 rounded-full transition-colors ${speakReplies ? 'text-[var(--accent)] bg-[var(--accent-bg)]' : 'text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--accent-bg-2)]'}`}
              title={speakReplies ? 'Voice replies on' : 'Read replies aloud'}
              aria-label="Toggle voice replies"
            >
              {speakReplies ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>
            <button onClick={() => setAttachOpen(true)}
              className="hidden sm:inline-flex btn btn-ghost btn-sm"
              title="Discuss one of your completed analyses">
              <Link2 size={14} /> Attach analysis
            </button>
            <button onClick={newChat} className="btn btn-secondary btn-sm" title="Start a new conversation">
              <Plus size={14} /> <span className="hidden sm:inline">New</span>
            </button>
            <button onClick={() => setSidebarOpen(true)} className="lg:hidden p-2 rounded-full text-[var(--text-2)]" aria-label="Conversations">
              <PanelLeftClose size={17} style={{ transform: 'scaleX(-1)' }} />
            </button>
          </header>

          {/* Messages / empty state */}
          <div ref={scrollRef} className="relative z-10 flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-4 chat-scroll">
            {empty ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <div className="relative mb-5">
                  <span className="absolute -inset-4 rounded-full pointer-events-none"
                    style={{ background: 'radial-gradient(closest-side, rgba(129,11,56,.4), transparent 72%)' }} aria-hidden />
                  <span className="relative w-14 h-14 rounded-2xl flex items-center justify-center border"
                    style={{ background: 'var(--grad)', borderColor: 'rgba(255,255,255,.18)', color: '#fff7f0', boxShadow: '0 10px 30px rgba(129,11,56,.45)' }}>
                    <Sparkles size={22} />
                  </span>
                </div>
                <h2 className="text-[20px] font-extrabold text-[var(--text)] tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
                  Talk to your coach<span className="text-[var(--accent)]">.</span>
                </h2>
                <p className="text-[13px] text-[var(--text-2)] mt-2 max-w-md leading-relaxed">
                  Vent about a rough interview, ask how to answer anything, practice questions together,
                  or run a full mock — just say what's on your mind, the way you'd say it to a mentor.
                </p>
                <div className="mt-6 grid sm:grid-cols-2 gap-2 max-w-xl w-full">
                  {STARTERS.map(({ icon: Icon, text }) => (
                    <button key={text} onClick={() => send(text)}
                      className="flex items-start gap-2.5 text-left px-3.5 py-3 rounded-xl border transition-all hover:-translate-y-0.5"
                      style={{ borderColor: 'var(--border-2)', background: 'var(--surface-2)' }}>
                      <Icon size={14} className="shrink-0 mt-0.5 text-[var(--accent)]" />
                      <span className="text-[12.5px] text-[var(--text-2)] leading-snug">{text}</span>
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-[var(--text-3)] mt-4">Type anything below — no categories, no menus, just talk.</p>
              </div>
            ) : (
              messages.map((m, i) => <Bubble key={i} msg={m} onSpeak={speak} />)
            )}
            {sending && (
              <div className="flex gap-2.5">
                <span className="w-7 h-7 rounded-[9px] flex items-center justify-center shrink-0 border"
                  style={{ background: 'var(--grad)', borderColor: 'rgba(255,255,255,.16)', color: '#fff7f0' }}>
                  <Bot size={13} />
                </span>
                <div className="px-4 py-2.5 rounded-2xl border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border-2)', borderBottomLeftRadius: 6 }}>
                  <TypingDots />
                </div>
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="relative z-10 border-t border-[var(--border-2)] px-4 sm:px-5 py-3.5">
            {error && (
              <p className="text-[12px] text-[var(--error)] flex items-center gap-1.5 mb-2">
                <X size={13} /> {error}
              </p>
            )}
            {micError && (
              <p className="text-[11.5px] text-[var(--warn)] flex items-center gap-1.5 mb-2">
                <MicOff size={12} /> {micError}
                <button className="underline ml-1" onClick={() => setMicError('')}>dismiss</button>
              </p>
            )}
            <div className="flex items-end gap-2">
              <button
                onClick={toggleMic}
                className={`p-3 rounded-[10px] border transition-all shrink-0 ${listening ? 'animate-pulse' : ''}`}
                style={listening
                  ? { background: 'var(--accent)', borderColor: 'var(--accent)', color: '#fff', boxShadow: '0 0 18px rgba(194,20,79,.55)' }
                  : { background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--text-2)' }}
                title={listening ? 'Stop dictation' : 'Dictate your message'}
                aria-label={listening ? 'Stop dictation' : 'Dictate message'}
              >
                {listening ? <Square size={15} /> : <Mic size={15} />}
              </button>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send()
                  }
                }}
                placeholder={practiceActive ? 'Type your answer — or ask the coach anything…' : 'Type anything — ask, vent, practice…'}
                rows={1}
                className="flex-1 resize-none min-h-[42px] max-h-[140px] py-2.5"
                aria-label="Message your AI coach"
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || sending}
                className="btn btn-primary px-4 shrink-0"
                aria-label="Send message"
              >
                <Send size={15} />
              </button>
            </div>
            <p className="text-[10.5px] text-[var(--text-3)] mt-2">
              Enter to send · Shift+Enter for a new line · runs locally, nothing leaves your machine
            </p>
          </div>
        </section>
      </div>

      {/* Mobile conversations drawer is rendered inside <aside> above (fixed overlay) */}

      {/* ---------------- Attach-analysis modal ---------------- */}
      {attachOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-[2px]" onClick={() => setAttachOpen(false)} />
          <div className="relative panel p-5 w-full max-w-md max-h-[80vh] overflow-y-auto anim-fade-up">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[15px] font-bold text-[var(--text)]">Discuss an analysis</h3>
              <button onClick={() => setAttachOpen(false)} className="p-1.5 text-[var(--text-3)] hover:text-[var(--text)]" aria-label="Close"><X size={16} /></button>
            </div>
            <p className="text-[12px] text-[var(--text-3)] mb-4">
              The coach will read the results and use them to guide the conversation.
            </p>
            {!ctx ? (
              <div className="py-6 flex justify-center"><span className="spinner w-6 h-6" /></div>
            ) : (
              <div className="space-y-4">
                <div>
                  <p className="kicker mb-2">Video analyses</p>
                  {ctx.video?.length === 0 && <p className="text-[12px] text-[var(--text-3)]">None completed yet.</p>}
                  {ctx.video?.map((v) => (
                    <button key={v.id} onClick={() => attach('video', v.id)}
                      className="w-full flex items-center gap-2 px-3 py-2.5 rounded-[10px] border border-transparent hover:bg-[var(--accent-bg-2)] text-left">
                      <span className="badge badge-gray">#{v.id}</span>
                      <span className="text-[12.5px] font-semibold text-[var(--text)] truncate flex-1">{v.title}</span>
                      {v.overall_score != null && <span className="badge badge-indigo">{Math.round(v.overall_score)}/100</span>}
                    </button>
                  ))}
                </div>
                <div>
                  <p className="kicker mb-2">Live interview reports</p>
                  {ctx.live?.length === 0 && <p className="text-[12px] text-[var(--text-3)]">None completed yet.</p>}
                  {ctx.live?.map((l) => (
                    <button key={l.id} onClick={() => attach('live', l.id)}
                      className="w-full flex items-center gap-2 px-3 py-2.5 rounded-[10px] border border-transparent hover:bg-[var(--accent-bg-2)] text-left">
                      <span className="badge badge-gray">#{l.id}</span>
                      <span className="text-[12.5px] font-semibold text-[var(--text)] flex-1">Live interview · {timeAgo(l.created_at)}</span>
                      {l.overall_score != null && <span className="badge badge-indigo">{Math.round(l.overall_score)}/100</span>}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
