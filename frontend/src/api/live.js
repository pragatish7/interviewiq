/**
 * Live AI Interview API client.
 *
 * A second, separate interview workflow alongside the existing video-upload
 * analysis. Browser speech recognition transcribes the spoken answer; the
 * backend scores it against the Q&A dataset's reference answers.
 */
import api from '../api'

export const LIVE_ROUTE = '/live-interview'

export async function getLiveDatasetInfo() {
  const res = await api.get('/live-interviews/dataset')
  return res.data
}

export async function startLiveSession({ totalQuestions, categories, seed } = {}) {
  const res = await api.post('/live-interviews/start', {
    total_questions: totalQuestions,
    categories: categories || null,
    seed: seed ?? null,
  })
  return res.data
}

export async function submitLiveAnswer(sessionId, payload) {
  const res = await api.post(`/live-interviews/${sessionId}/answer`, {
    question_id: payload.questionId,
    transcript: payload.transcript,
    duration_s: payload.durationS || 0,
    pause_count: payload.pauseCount || 0,
    pause_seconds_total: payload.pauseSecondsTotal || 0,
  })
  return res.data
}

export async function finishLiveSession(sessionId) {
  const res = await api.post(`/live-interviews/${sessionId}/finish`)
  return res.data
}

export async function abandonLiveSession(sessionId) {
  const res = await api.post(`/live-interviews/${sessionId}/abandon`)
  return res.data
}
