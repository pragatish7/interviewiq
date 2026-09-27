import { useCallback, useEffect, useRef, useState } from 'react'

const SRClass =
  typeof window !== 'undefined' &&
  (window.SpeechRecognition || window.webkitSpeechRecognition)

/**
 * Live answer dictation via the Web Speech API (Chrome/Chromium).
 *
 * - Streams interim + final transcript while the candidate speaks.
 * - Tracks silent gaps (recognition restarts while still listening) so the
 *   session can report pause count / total pause seconds, mirroring the
 *   speech metrics the video pipeline computes.
 * - Falls back gracefully: `supported=false` callers show a text input so the
 *   live-interview flow never dead-ends.
 */
export default function useSpeechRecognition({ lang = 'en-US' } = {}) {
  const [supported] = useState(() => Boolean(SRClass))
  const [listening, setListening] = useState(false)
  const [finalText, setFinalText] = useState('')
  const [interim, setInterim] = useState('')
  const [error, setError] = useState('')

  const recRef = useRef(null)
  const wantRef = useRef(false)
  const finalRef = useRef('')
  const gapOpenAtRef = useRef(null)
  const pausesRef = useRef({ count: 0, seconds: 0 })
  const restartTimerRef = useRef(null)

  const _closeGap = useCallback(() => {
    if (gapOpenAtRef.current != null) {
      const secs = (Date.now() - gapOpenAtRef.current) / 1000
      if (secs >= 1.5) {
        pausesRef.current.count += 1
        pausesRef.current.seconds += secs
      }
      gapOpenAtRef.current = null
    }
  }, [])

  const _ensureRecognition = useCallback(() => {
    if (!SRClass) return null
    if (recRef.current) return recRef.current
    const rec = new SRClass()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = lang

    rec.onstart = () => {
      _closeGap()
      setListening(true)
      setError('')
    }

    rec.onresult = (event) => {
      _closeGap()
      let interimChunk = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i]
        if (res.isFinal) {
          finalRef.current = `${finalRef.current} ${res[0].transcript}`.trim()
          setFinalText(finalRef.current)
        } else {
          interimChunk += res[0].transcript
        }
      }
      setInterim(interimChunk)
    }

    rec.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        wantRef.current = false
        setListening(false)
        setError('Microphone access was blocked. Type your answer instead.')
      } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setError(`Speech recognition issue (${event.error}). You can type your answer instead.`)
      }
    }

    rec.onend = () => {
      setListening(false)
      setInterim('')
      if (wantRef.current) {
        // A silence gap opened — record it, then restart recognition.
        if (gapOpenAtRef.current == null) gapOpenAtRef.current = Date.now()
        restartTimerRef.current = setTimeout(() => {
          if (wantRef.current) {
            try { rec.start() } catch { /* already started */ }
          }
        }, 250)
      }
    }

    recRef.current = rec
    return rec
  }, [lang, _closeGap])

  const start = useCallback(() => {
    wantRef.current = true
    setError('')
    const rec = _ensureRecognition()
    if (!rec) return
    try { rec.start() } catch { /* already running */ }
  }, [_ensureRecognition])

  const stop = useCallback(() => {
    wantRef.current = false
    _closeGap()
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
    try { recRef.current?.stop() } catch { /* noop */ }
    setListening(false)
    setInterim('')
  }, [_closeGap])

  const reset = useCallback(() => {
    finalRef.current = ''
    pausesRef.current = { count: 0, seconds: 0 }
    gapOpenAtRef.current = null
    setFinalText('')
    setInterim('')
    setError('')
  }, [])

  // Hard cleanup on unmount.
  useEffect(() => () => {
    wantRef.current = false
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current)
    try { recRef.current?.abort() } catch { /* noop */ }
  }, [])

  return {
    supported,
    listening,
    text: finalText,
    interim,
    error,
    pauses: pausesRef,
    start,
    stop,
    reset,
  }
}
