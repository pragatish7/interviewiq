import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 min for large uploads
})

export const uploadInterview = async (file, meta = {}) => {
  const formData = new FormData()
  formData.append('file', file)
  if (meta.title) formData.append('title', meta.title)
  if (meta.interview_type) formData.append('interview_type', meta.interview_type)
  if (meta.target_role) formData.append('target_role', meta.target_role)
  if (meta.experience_level) formData.append('experience_level', meta.experience_level)
  if (meta.job_description) formData.append('job_description', meta.job_description)
  const res = await api.post('/interviews/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export const analyzeInterview = async (id) => {
  const res = await api.post(`/interviews/${id}/analyze`)
  return res.data
}

export const getInterviews = async (skip = 0, limit = 50) => {
  const res = await api.get('/interviews', { params: { skip, limit } })
  return res.data
}

export const getInterview = async (id) => {
  const res = await api.get(`/interviews/${id}`)
  return res.data
}

export const getReport = async (id) => {
  const res = await api.get(`/interviews/${id}/report`)
  return res.data
}

export const getTranscript = async (id) => {
  const res = await api.get(`/interviews/${id}/transcript`)
  return res.data
}

export const getVideoUrl = (id) => `/api/interviews/${id}/video`

export const getPdfUrl = (id) => `/api/interviews/${id}/pdf`

export const getTimeline = async (id) => {
  const res = await api.get(`/interviews/${id}/timeline`)
  return res.data
}

export const deleteInterview = async (id) => {
  const res = await api.delete(`/interviews/${id}`)
  return res.data
}

export const getDashboard = async () => {
  const res = await api.get('/dashboard')
  return res.data
}

export const getProgress = async (limit = 20) => {
  const res = await api.get('/progress', { params: { limit } })
  return res.data
}

export const compareInterviews = async (id1, id2) => {
  const res = await api.get('/interviews/compare', { params: { id1, id2 } })
  return res.data
}

export default api
