/**
 * AI Coach API client — free-form conversation with an interview mentor.
 */
import api from '../api'

export async function createCoachSession() {
  const res = await api.post('/coach/sessions')
  return res.data
}

export async function listCoachSessions() {
  const res = await api.get('/coach/sessions')
  return res.data
}

export async function getCoachSession(id) {
  const res = await api.get(`/coach/sessions/${id}`)
  return res.data
}

export async function deleteCoachSession(id) {
  const res = await api.delete(`/coach/sessions/${id}`)
  return res.data
}

export async function coachTalk(sessionId, message) {
  const res = await api.post(`/coach/sessions/${sessionId}/talk`, { message })
  return res.data
}

export async function attachCoachAnalysis(sessionId, kind, id) {
  const res = await api.post(`/coach/sessions/${sessionId}/attach`, { kind, id })
  return res.data
}

export async function getCoachContext() {
  const res = await api.get('/coach/context')
  return res.data
}
