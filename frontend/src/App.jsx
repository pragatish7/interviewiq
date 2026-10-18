import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { createContext, useContext, useEffect, useState } from 'react'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import AnalyzeInterview from './pages/AnalyzeInterview'
import InterviewHistory from './pages/InterviewHistory'
import InterviewReport from './pages/InterviewReport'
import ProgressPage from './pages/ProgressPage'
import SettingsPage from './pages/SettingsPage'
import LiveInterviewPage from './pages/LiveInterviewPage'
import CoachPage from './pages/CoachPage'

export const ThemeContext = createContext()
export function useTheme() { return useContext(ThemeContext) }

function resolveTheme(pref, systemDark) {
  if (pref === 'dark') return true
  if (pref === 'light') return false
  return systemDark
}

function App() {
  // Red Noir is the native surface — dark unless the user opts into light.
  // New key because the system flipped from light-first to dark-first.
  const [preference, setPreference] = useState(() => localStorage.getItem('iq-theme-v2') || 'dark')
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const onChange = (e) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const dark = resolveTheme(preference, systemDark)
  useEffect(() => {
    document.documentElement.classList.toggle('light', !dark)
    document.body.classList.toggle('light', !dark)
    localStorage.setItem('iq-theme-v2', preference)
  }, [dark, preference])

  return (
    <ThemeContext.Provider value={{ dark, preference, setPreference }}>
      <Router>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/analyze" element={<AnalyzeInterview />} />
            <Route path="/live-interview" element={<LiveInterviewPage />} />
            <Route path="/coach" element={<CoachPage />} />
            <Route path="/history" element={<InterviewHistory />} />
            <Route path="/progress" element={<ProgressPage />} />
            <Route path="/interview/:id" element={<InterviewReport />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </ThemeContext.Provider>
  )
}

export default App
