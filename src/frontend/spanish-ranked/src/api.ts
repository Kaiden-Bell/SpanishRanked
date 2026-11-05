export type User = { username: string; must_change_password: boolean; csrf_token: string }

export type StudySession = {
  id: number
  language_code: string
  mode: 'SELF_STUDY' | 'GUIDED_STUDY'
  activity_type: string
  duration_minutes: number
  context_text: string
  terms: string[]
  sentences: string[]
  created_at: string
  completed_at: string | null
}

export type Award = { base_xp: number; multiplier: number; awarded_xp: number; capped: boolean }

export type Progress = {
  total_xp: number
  rank: { name: string; min_xp: number }
  next_rank: { name: string; min_xp: number } | null
  xp_to_next: number | null
  streak: { current: number; active_today: boolean; next_multiplier: number }
  today: { date: string; study_xp: number; study_xp_cap: number }
}

export type Outcome = 'HIT' | 'PARTIAL' | 'MISS'

export type AssessmentItem = {
  id: number
  prompt: string
  concepts: string[]
  response_text: string | null
  feedback: string | null
  evidence: { concept_token: string; outcome: Outcome; issue: string }[]
}

export type Assessment = {
  id: number
  /** GENERATED = waiting for answers, SUBMITTED = answers saved but not graded yet, GRADED = done. */
  status: 'GENERATED' | 'SUBMITTED' | 'GRADED' | 'FAILED'
  created_at: string
  submitted_at: string | null
  graded_at: string | null
  grading_error: string | null
  grammar_hints_unavailable: boolean
  correct: number | null
  items: AssessmentItem[]
  award: Award | null
}

export type AssessmentSummary = Pick<Assessment, 'id' | 'status' | 'created_at' | 'graded_at' | 'correct'> & { total: number }

export type SystemStatus = {
  database: 'ok' | 'degraded' | 'down'
  languagetool: 'ok' | 'degraded' | 'down'
  model: 'ok' | 'degraded' | 'down'
  checked_at: string
}

export type StudySessionInput = {
  mode: StudySession['mode']
  activity_type: string
  duration_minutes: number
  context_text: string
  terms: string[]
  sentences: string[]
}

export const ACTIVITY_TYPES = [
  'READING',
  'LISTENING',
  'WATCHING',
  'WRITING',
  'SPEAKING',
  'FLASHCARDS',
  'CLASS',
  'OTHER',
] as const

export class ApiError extends Error {
  status: number
  messages: string[]
  constructor(status: number, messages: string[]) {
    super(messages[0] ?? `Request failed (${status})`)
    this.status = status
    this.messages = messages
  }
}

let csrfToken = ''
let onSignedOut: () => void = () => {}

export function setCsrfToken(token: string) {
  csrfToken = token
}

/** Called when an authenticated request comes back 401 (expired or revoked session). */
export function setSignedOutHandler(handler: () => void) {
  onSignedOut = handler
}

function describeDetail(detail: unknown, status: number): string[] {
  if (typeof detail === 'string') return [detail]
  if (Array.isArray(detail)) {
    // FastAPI validation errors: { loc: ['body', 'terms'], msg: '...' }
    return detail.map((d: { loc?: unknown[]; msg?: string }) => {
      const field = (d.loc ?? []).filter((p) => p !== 'body').join(' › ')
      return field ? `${field}: ${d.msg}` : String(d.msg)
    })
  }
  return [`Request failed (${status})`]
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      method,
      signal,
      credentials: 'same-origin',
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(method !== 'GET' ? { 'X-CSRF-Token': csrfToken } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    throw new ApiError(0, ['Cannot reach the backend.'])
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && path !== '/api/auth/login') onSignedOut()
    throw new ApiError(res.status, describeDetail(data?.detail, res.status))
  }
  return data as T
}

export const api = {
  me: (signal?: AbortSignal) => request<User>('GET', '/api/auth/me', undefined, signal),
  login: (username: string, password: string) =>
    request<User>('POST', '/api/auth/login', { username, password }),
  logout: () => request<void>('POST', '/api/auth/logout'),
  changePassword: (current_password: string, new_password: string) =>
    request<User>('POST', '/api/auth/change-password', { current_password, new_password }),
  createSession: (input: StudySessionInput) =>
    request<StudySession & { award: Award }>('POST', '/api/study-sessions', input),
  progress: (signal?: AbortSignal) => request<Progress>('GET', '/api/progress', undefined, signal),
  systemStatus: (signal?: AbortSignal) => request<SystemStatus>('GET', '/api/system/status', undefined, signal),
  createAssessment: () => request<Assessment>('POST', '/api/assessments'),
  listAssessments: (offset: number, limit = 20, signal?: AbortSignal) =>
    request<{ total: number; items: AssessmentSummary[] }>(
      'GET',
      `/api/assessments?limit=${limit}&offset=${offset}`,
      undefined,
      signal,
    ),
  getAssessment: (id: number, signal?: AbortSignal) =>
    request<Assessment>('GET', `/api/assessments/${id}`, undefined, signal),
  submitAssessment: (id: number, answers: { item_id: number; text: string }[]) =>
    request<Assessment>('POST', `/api/assessments/${id}/submit`, { answers }),
  gradeAssessment: (id: number) => request<Assessment>('POST', `/api/assessments/${id}/grade`),
  listSessions: (offset: number, limit = 20, signal?: AbortSignal) =>
    request<{ total: number; items: StudySession[] }>(
      'GET',
      `/api/study-sessions?limit=${limit}&offset=${offset}`,
      undefined,
      signal,
    ),
}
