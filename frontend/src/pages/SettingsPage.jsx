import { useState } from 'react'
import { Sun, Moon, Monitor, Trash2, Check, Palette, SlidersHorizontal, Database, Shield } from 'lucide-react'
import { useTheme } from '../App'
import { getInterviews, deleteInterview } from '../api'

/* ---------- Shared settings building blocks ---------- */

function Panel({ icon: Icon, title, desc, children, tone }) {
  return (
    <section className="panel overflow-hidden">
      <header className="flex items-center gap-3 px-5 py-4 border-b border-[var(--border-2)]">
        <span
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border"
          style={{
            background: tone === 'danger' ? 'var(--error-bg)' : 'var(--accent-bg)',
            borderColor: tone === 'danger' ? 'rgba(239,106,95,.3)' : 'rgba(194,20,79,.26)',
            color: tone === 'danger' ? 'var(--error)' : 'var(--accent)',
          }}
        >
          <Icon size={17} />
        </span>
        <div className="min-w-0">
          <h2 className="text-[14.5px] font-bold text-[var(--text)] leading-tight">{title}</h2>
          <p className="text-[12px] text-[var(--text-3)] mt-0.5">{desc}</p>
        </div>
      </header>
      <div className="px-5 divide-y divide-[var(--border-2)]">{children}</div>
    </section>
  )
}

function Row({ title, desc, children }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-4 min-w-0">
      <div className="min-w-0">
        <p className="text-[13.5px] font-semibold text-[var(--text)]">{title}</p>
        <p className="text-[12px] text-[var(--text-3)] mt-0.5 max-w-md leading-relaxed">{desc}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

function Segmented({ value, onChange, options }) {
  return (
    <div className="flex rounded-[11px] border border-[var(--border)] bg-[var(--surface-2)] p-1 gap-1">
      {options.map((o) => {
        const active = value === o.value
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            aria-pressed={active}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[12.5px] font-bold transition-all duration-150 cursor-pointer ${
              active
                ? 'text-[#fff7f0]'
                : 'text-[var(--text-3)] hover:text-[var(--text-2)]'
            }`}
            style={active ? { background: 'var(--grad)', boxShadow: '0 4px 14px rgba(129,11,56,.35)' } : undefined}
          >
            <o.icon size={14} /> {o.label}
          </button>
        )
      })}
    </div>
  )
}

/* ---------- Page ---------- */

const DEFAULTS_KEY = 'iq-defaults'

export default function SettingsPage() {
  const { preference, setPreference } = useTheme()
  const [defaults, setDefaults] = useState(() => {
    try { return JSON.parse(localStorage.getItem(DEFAULTS_KEY) || '{}') } catch { return {} }
  })
  const [busy, setBusy] = useState(false)
  const [cleared, setCleared] = useState(false)

  const saveDefaults = (next) => {
    const merged = { ...defaults, ...next }
    setDefaults(merged)
    localStorage.setItem(DEFAULTS_KEY, JSON.stringify(merged))
  }

  const clearHistory = async () => {
    if (!window.confirm('Delete ALL interviews and analysis history? This cannot be undone.')) return
    setBusy(true)
    setCleared(false)
    try {
      const { interviews } = await getInterviews(0, 500)
      for (const i of interviews || []) { try { await deleteInterview(i.id) } catch {} }
      setCleared(true)
      setTimeout(() => setCleared(false), 3000)
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-6 anim-fade-up">
      <header>
        <p className="kicker mb-2">Preferences</p>
        <h1 className="display text-[28px] sm:text-[34px] text-[var(--text)]">
          Settings<span className="text-[var(--accent)]">.</span>
        </h1>
        <p className="text-[13.5px] text-[var(--text-2)] mt-2">Appearance, analysis defaults and your data.</p>
      </header>

      <div className="grid gap-5 items-start lg:grid-cols-2">
        <Panel icon={Palette} title="Appearance" desc="Choose how InterviewIQ looks on this device.">
          <Row
            title="Theme"
            desc="Red Noir is the native surface. Light is the warm studio variant of the same system."
          >
            <Segmented
              value={preference}
              onChange={setPreference}
              options={[
                { value: 'dark', label: 'Red Noir', icon: Moon },
                { value: 'light', label: 'Light', icon: Sun },
                { value: 'system', label: 'System', icon: Monitor },
              ]}
            />
          </Row>
        </Panel>

        <Panel icon={SlidersHorizontal} title="Analysis Defaults" desc="Pre-filled values when you open the Analyze page.">
          <Row title="Default interview type" desc="Applied to each new analysis.">
            <select
              className="!w-auto min-w-[180px]"
              value={defaults.interview_type || 'General'}
              onChange={(e) => saveDefaults({ interview_type: e.target.value })}
              aria-label="Default interview type"
            >
              {['General', 'HR', 'Behavioral', 'Technical', 'Mixed'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </Row>
          <Row title="Default experience level" desc="Used to calibrate expectations.">
            <select
              className="!w-auto min-w-[180px]"
              value={defaults.experience_level || 'Mid Level'}
              onChange={(e) => saveDefaults({ experience_level: e.target.value })}
              aria-label="Default experience level"
            >
              {['Student', 'Entry Level', 'Mid Level', 'Experienced'].map((l) => <option key={l}>{l}</option>)}
            </select>
          </Row>
        </Panel>
      </div>

      <Panel icon={Database} title="Data" desc="Manage stored interview recordings and analyses." tone="danger">
        <Row
          title="Delete interview history"
          desc="Permanently removes every interview, video and analysis from this machine. This cannot be undone."
        >
          <button className="btn btn-danger min-w-[130px] justify-center" onClick={clearHistory} disabled={busy}>
            {busy ? (
              <span className="inline-flex items-center gap-1.5"><Trash2 size={13} /> Deleting…</span>
            ) : cleared ? (
              <span className="inline-flex items-center gap-1.5"><Check size={13} /> History cleared</span>
            ) : (
              <span className="inline-flex items-center gap-1.5"><Trash2 size={13} /> Delete all</span>
            )}
          </button>
        </Row>
      </Panel>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12px] text-[var(--text-3)] px-1">
        <span className="inline-flex items-center gap-2"><Database size={13} /> Settings are stored locally on this device.</span>
        <span className="inline-flex items-center gap-2"><Shield size={13} /> Recordings never leave your machine.</span>
      </div>
    </div>
  )
}
