import { NavLink, Outlet, useLocation, Link } from 'react-router-dom'
import { Home, Upload, History, TrendingUp, Settings, Sun, Moon, Menu, X, Sparkles } from 'lucide-react'
import { useTheme } from '../App'
import { useState, useEffect } from 'react'

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/analyze', label: 'Analyze', icon: Upload },
  { to: '/history', label: 'History', icon: History },
  { to: '/progress', label: 'Progress', icon: TrendingUp },
]

function Brand({ compact }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 min-w-0 shrink-0 group">
      <span
        className="relative w-8 h-8 rounded-[10px] flex items-center justify-center shrink-0"
        style={{
          background: 'linear-gradient(150deg, #c2144f 0%, #810b38 60%, #541a1a 100%)',
          boxShadow: '0 6px 18px rgba(129,11,56,.5), inset 0 1px 0 rgba(255,255,255,.28)',
        }}
      >
        <Sparkles size={15} className="text-[#fdf3e9]" />
      </span>
      {!compact && (
        <span className="min-w-0">
          <span className="block text-[15px] font-extrabold tracking-tight text-[var(--text)] leading-none truncate">
            InterviewIQ
          </span>
          <span className="hidden sm:block text-[9.5px] font-semibold uppercase tracking-[.19em] text-[var(--text-3)] mt-1">
            Performance Intelligence
          </span>
        </span>
      )}
    </Link>
  )
}

export default function Layout() {
  const { dark, setPreference } = useTheme()
  const [open, setOpen] = useState(false)
  const location = useLocation()

  // Close the drawer whenever the route changes
  useEffect(() => { setOpen(false) }, [location.pathname])

  // Lock scroll behind the drawer
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  const toggleTheme = () => setPreference(dark ? 'light' : 'dark')

  const ThemeIcon = dark ? Sun : Moon
  const themeLabel = dark ? 'Switch to light appearance' : 'Switch to dark appearance'

  return (
    <div className="relative min-h-screen flex flex-col">
      {/* Atmosphere — near-black canvas, burgundy bloom, technical grid */}
      <div className="noir-atmosphere" aria-hidden />
      <div className="noir-grid" aria-hidden />

      <header className="sticky top-0 z-40 px-3 sm:px-5 pt-3 sm:pt-4 pb-2">
        <nav className="nav-pill mx-auto max-w-[1180px] flex items-center gap-2 pl-3 pr-2 py-2 sm:pl-4 sm:pr-2.5">
          <Brand />

          {/* Inline navigation — desktop */}
          <div className="hidden md:flex items-center gap-1 mx-auto">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className="nav-link">
                <Icon size={14.5} strokeWidth={2.1} />
                {label}
              </NavLink>
            ))}
          </div>

          <div className="flex items-center gap-1 ml-auto md:ml-0">
            <Link
              to="/analyze"
              className="hidden lg:inline-flex btn btn-primary btn-sm"
            >
              New Analysis
            </Link>
            <Link
              to="/settings"
              className="hidden md:inline-flex p-2 rounded-full text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--accent-bg-2)] transition-colors duration-200"
              aria-label="Settings"
              title="Settings"
            >
              <Settings size={17} />
            </Link>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-full text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--accent-bg-2)] transition-colors duration-200 cursor-pointer"
              aria-label={themeLabel}
              title={themeLabel}
            >
              <ThemeIcon size={17} />
            </button>
            <button
              onClick={() => setOpen(true)}
              className="md:hidden p-2 rounded-full text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--accent-bg-2)] transition-colors duration-200 cursor-pointer"
              aria-label="Open menu"
              aria-expanded={open}
            >
              <Menu size={19} />
            </button>
          </div>
        </nav>
      </header>

      <main className="relative z-10 flex-1 min-w-0">
        <div className="w-full max-w-[1180px] mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-12 lg:pt-8 lg:pb-20">
          <Outlet />
        </div>
      </main>

      <footer className="relative z-10 border-t border-[var(--border-2)]">
        <div className="max-w-[1180px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[11.5px] text-[var(--text-3)]">
            Runs locally · Video, speech and NLP analysis on your own machine.
          </p>
          <p className="text-[11.5px] text-[var(--text-3)] font-semibold tracking-wide uppercase">
            InterviewIQ
          </p>
        </div>
      </footer>

      {/* Slide-in menu — small screens */}
      <div className={`fixed inset-0 z-50 md:hidden ${open ? '' : 'invisible'}`} aria-hidden={!open}>
        <div
          onClick={() => setOpen(false)}
          className={`absolute inset-0 bg-black/70 backdrop-blur-[3px] transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0'}`}
        />
        <div
          className={`drawer-panel absolute inset-y-0 right-0 w-[292px] max-w-[86vw] flex flex-col transition-transform duration-300 ease-out ${open ? 'translate-x-0' : 'translate-x-full'}`}
        >
          <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-[var(--border-2)]">
            <Brand />
            <button
              onClick={() => setOpen(false)}
              className="p-2 rounded-full text-[var(--text-2)] hover:bg-[var(--accent-bg-2)] hover:text-[var(--text)] transition-colors"
              aria-label="Close menu"
            >
              <X size={18} />
            </button>
          </div>

          <nav className="px-3 py-4 flex-1 overflow-y-auto space-y-1">
            <p className="px-3 pb-2 kicker">Navigate</p>
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className="drawer-link">
                <Icon size={17} strokeWidth={2} />
                {label}
              </NavLink>
            ))}
            <div className="pt-3 mt-3 border-t border-[var(--border-2)] space-y-1">
              <p className="px-3 pb-2 kicker">Account</p>
              <NavLink to="/settings" className="drawer-link">
                <Settings size={17} strokeWidth={2} />
                Settings
              </NavLink>
              <button onClick={toggleTheme} className="drawer-link w-full text-left cursor-pointer">
                <ThemeIcon size={17} strokeWidth={2} />
                {dark ? 'Light appearance' : 'Dark appearance'}
              </button>
            </div>
          </nav>

          <div className="px-4 py-4 border-t border-[var(--border-2)]">
            <Link to="/analyze" className="btn btn-primary w-full justify-center">
              Start New Analysis
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
