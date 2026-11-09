import axios from 'axios'

const AUTH_URL      = 'http://127.0.0.1:8000/api/v1'
const INTERVIEW_URL = 'http://127.0.0.1:8001'

// ── Auth client ───────────────────────────────────────────────────────────────
const authClient = axios.create({ baseURL: AUTH_URL })

authClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Interview client ──────────────────────────────────────────────────────────
const interviewClient = axios.create({ baseURL: INTERVIEW_URL })

// ── Helper ────────────────────────────────────────────────────────────────────
const getUserId = () => {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  return user.id || 'default'
}

// ── Auth exports ──────────────────────────────────────────────────────────────
export const register = (data) => authClient.post('/register', data)
export const login    = (data) => authClient.post('/login', data)
export const getMe    = ()     => authClient.get('/me')

// ── Emotion exports ───────────────────────────────────────────────────────────
export const analyzeEmotionFrame = (imageBase64, frameNumber, questionContext = '') =>
  authClient.post('/emotion/analyze-frame', {
    image_base64:     imageBase64,
    frame_number:     frameNumber,
    question_context: questionContext,
  })

export const getEmotionStats = (frames) =>
  authClient.post('/emotion/session-stats', { frames })

// ── Interview exports ─────────────────────────────────────────────────────────
export const analyzeFile = (file, crimeType) => {
  const form = new FormData()
  form.append('file', file)
  form.append('crime_type', crimeType)
  form.append('user_id', getUserId())
  return interviewClient.post('/analyze', form)
}

export const analyzeText = (crimeType, textDescription) => {
  const form = new FormData()
  form.append('crime_type', crimeType)
  form.append('text_description', textDescription)
  form.append('user_id', getUserId())
  return interviewClient.post('/analyze/text', form)
}

export const respondToQuestion = (sessionId, answer) => {
  const form = new FormData()
  form.append('answer', answer)
  return interviewClient.post(`/respond/${sessionId}`, form)
}

export const getSessionData = (sessionId) =>
  interviewClient.get(`/session/${sessionId}`)

export const getAllSessions = () =>
  interviewClient.get(`/sessions?user_id=${getUserId()}`)

export const generateReport = (sessionId) =>
  interviewClient.post(`/report/${sessionId}`)

export const downloadPDF = (sessionId) =>
  interviewClient.get(`/report/${sessionId}/pdf`, { responseType: 'blob' })

export const deleteInterviewSession = (sessionId) =>
  interviewClient.delete(`/session/${sessionId}`)

export const getCredibility = (sessionId) =>
  interviewClient.get(`/credibility/${sessionId}`)

export const getCBCA = (sessionId) =>
  interviewClient.get(`/cbca/${sessionId}`)

export default authClient