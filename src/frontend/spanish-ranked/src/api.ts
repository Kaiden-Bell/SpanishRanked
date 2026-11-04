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
    request<StudySession>('POST', '/api/study-sessions', input),
  listSessions: (offset: number, limit = 20, signal?: AbortSignal) =>
    request<{ total: number; items: StudySession[] }>(
      'GET',
      `/api/study-sessions?limit=${limit}&offset=${offset}`,
      undefined,
      signal,
    ),
}
