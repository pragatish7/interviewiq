import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, FileVideo, X, AlertCircle, Check } from 'lucide-react'
import { formatBytes } from '../utils'

const MAX_MB = 500

const CHIPS = ['MP4', 'MOV', 'WebM']

export default function UploadPanel({ file, onFile, onClear, compact }) {
  const videoRef = useRef(null)
  const [duration, setDuration] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')

  const onDrop = useCallback((accepted, rejected) => {
    setDragOver(false)
    setError('')
    if (rejected?.length) {
      setError(rejected[0].errors?.[0]?.message?.includes('type') || rejected[0].file?.type?.startsWith('video') === false
        ? 'Unsupported format. Please upload an MP4, MOV, or WebM file.'
        : 'File too large. Maximum size is 500 MB.')
      return
    }
    const f = accepted?.[0]
    if (!f) return
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File too large (${MAX_MB} MB max).`)
      return
    }
    onFile(f)
    setDuration(null)
  }, [onFile])

  const { getRootProps, getInputProps, open } = useDropzone({
    onDrop,
    accept: { 'video/*': ['.mp4', '.mov', '.webm'] },
    maxFiles: 1,
    noClick: true,
    onDragEnter: () => setDragOver(true),
    onDragLeave: () => setDragOver(false),
  })

  const handleLoaded = () => {
    if (videoRef.current?.duration && isFinite(videoRef.current.duration)) {
      setDuration(videoRef.current.duration)
    }
  }

  if (file) {
    const url = file.preview
    return (
      <div>
        <div className="grid md:grid-cols-2 gap-5">
          {/* Video preview inside a burgundy-lit frame */}
          <div
            className="rounded-xl p-[1.5px]"
            style={{ background: 'linear-gradient(150deg, #c2144f, #541a1a)', boxShadow: '0 14px 40px rgba(129,11,56,.32)' }}
          >
            <div className="rounded-[10px] overflow-hidden bg-black">
              <video
                ref={videoRef}
                key={url}
                src={url}
                controls
                className="w-full aspect-video object-contain"
                onLoadedMetadata={handleLoaded}
              />
            </div>
          </div>
          <div className="flex flex-col justify-center">
            <div className="flex items-start gap-3">
              <span
                className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0 border"
                style={{ background: 'var(--accent-bg)', borderColor: 'rgba(194,20,79,.3)', color: 'var(--accent)' }}
              >
                <FileVideo size={19} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-bold text-[var(--text)] truncate">{file.name}</p>
                <div className="flex flex-wrap gap-x-2 gap-y-1.5 mt-2">
                  <span className="badge badge-gray">{formatBytes(file.size)}</span>
                  {duration ? <span className="badge badge-gray">{(duration / 60).toFixed(1)} min</span> : <span className="badge badge-indigo">Ready</span>}
                  <span className="badge badge-green"><Check size={11} /> Valid video</span>
                </div>
              </div>
              <button
                onClick={() => { onClear(); setDuration(null) }}
                className="p-1.5 rounded-md text-[var(--text-3)] hover:text-[var(--error)] hover:bg-[var(--error-bg)] transition-colors cursor-pointer"
                aria-label="Remove video"
              >
                <X size={15} />
              </button>
            </div>
            <p className="text-[12px] text-[var(--text-3)] mt-4 leading-relaxed">
              The recording is processed on this machine. Nothing is uploaded to a third-party service.
            </p>
          </div>
        </div>
        {error && <p className="text-[12px] text-[var(--error)] flex items-center gap-1.5 mt-3"><AlertCircle size={13} /> {error}</p>}
      </div>
    )
  }

  return (
    <div
      {...getRootProps()}
      onClick={open}
      className="relative rounded-2xl cursor-pointer transition-all duration-200 overflow-hidden group"
      style={{
        border: dragOver ? '1.5px solid rgba(194,20,79,.9)' : '1.5px dashed var(--border-strong)',
        background: dragOver
          ? 'linear-gradient(180deg, rgba(129,11,56,.22), rgba(129,11,56,.06))'
          : 'linear-gradient(180deg, rgba(255,255,255,.022), rgba(255,255,255,0))',
        boxShadow: dragOver ? '0 0 0 4px rgba(194,20,79,.16), 0 20px 60px rgba(129,11,56,.35)' : 'inset 0 1px 0 rgba(255,255,255,.04)',
      }}
    >
      {/* corner ticks — quiet technical detail */}
      {['top-3 left-3 border-t border-l', 'top-3 right-3 border-t border-r', 'bottom-3 left-3 border-b border-l', 'bottom-3 right-3 border-b border-r'].map((c) => (
        <span key={c} className={`absolute w-4 h-4 ${c} pointer-events-none`} style={{ borderColor: dragOver ? 'rgba(194,20,79,.8)' : 'var(--border-strong)' }} aria-hidden />
      ))}

      <div className={`relative ${compact ? 'px-6 py-8' : 'px-6 py-11 sm:py-14'} text-center`}>
        <input {...getInputProps()} />
        <div
          className={`mx-auto rounded-2xl flex items-center justify-center transition-all duration-200 border ${dragOver ? 'w-16 h-16' : 'w-14 h-14'}`}
          style={{
            background: 'linear-gradient(160deg, rgba(194,20,79,.24), rgba(84,26,26,.3))',
            borderColor: 'rgba(194,20,79,.34)',
            boxShadow: dragOver ? '0 0 34px rgba(194,20,79,.5), inset 0 1px 0 rgba(255,255,255,.1)' : 'inset 0 1px 0 rgba(255,255,255,.08)',
            color: 'var(--accent)',
          }}
        >
          <UploadCloud size={dragOver ? 25 : 21} />
        </div>

        <h3 className="mt-5 text-[16px] font-bold text-[var(--text)] tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
          {dragOver ? 'Drop to load the recording' : 'Upload Interview Video'}
        </h3>
        <p className="text-[13px] text-[var(--text-3)] mt-1.5">Drag &amp; drop your recording here, or</p>

        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); open() }}
          className="btn btn-primary mt-5"
        >
          Browse Files
        </button>

        <div className="flex items-center justify-center flex-wrap gap-2 mt-6">
          {CHIPS.map((c) => (
            <span key={c} className="badge badge-violet">{c}</span>
          ))}
          <span className="text-[11.5px] text-[var(--text-3)] font-medium">· up to {MAX_MB} MB</span>
        </div>

        {error && <p className="text-[12px] text-[var(--error)] flex items-center justify-center gap-1.5 mt-4"><AlertCircle size={13} /> {error}</p>}
      </div>
    </div>
  )
}
