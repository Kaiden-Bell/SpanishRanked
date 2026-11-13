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

export type BossStage = { key: string; label: string; score: number; correct: number; total: number; passed: boolean }

export type BossResult = {
  stages: BossStage[]
  overall: number
  skipped: { key: string; label: string; reason: string }[]
  stage_pass: number
  overall_pass: number
}

export type BossState = {
  rank: string | null
  status: 'NONE' | 'READY' | 'IN_PROGRESS' | 'COOLDOWN' | 'NEEDS_WORDS'
  cooldown_until: string | null
  words_needed: number
  attempt_id?: number | null
  assessment_id?: number | null
  latest?: ({ id: number; rank: string; status: 'PASSED' | 'FAILED'; assessment_id: number; cooldown_until: string | null } & BossResult) | null
}

export type Progress = {
  total_xp: number
  rank: { name: string; min_xp: number }
  next_rank: { name: string; min_xp: number } | null
  xp_to_next: number | null
  streak: { current: number; active_today: boolean; next_multiplier: number }
  today: { date: string; study_xp: number; study_xp_cap: number }
  boss: Omit<BossState, 'latest'>
}

export type Outcome = 'HIT' | 'PARTIAL' | 'MISS'

export type ItemPayload = {
  input: 'choice' | 'text' | 'order'
  options?: string[]
  options_lang?: 'es'
  spanish?: string
  tts?: string
  hint?: string | null
  translation?: string | null
  cloze?: { before: string; after: string }
  tiles?: string[]
  long?: boolean
}

export type Modality = 'READING' | 'WRITING' | 'LISTENING' | 'SPEAKING'

export type AssessmentItem = {
  id: number
  prompt: string
  concepts: string[]
  response_text: string | null
  feedback: string | null
  evidence: { concept_token: string; outcome: Outcome; issue: string }[]
  item_type: string
  modality: Modality
  skill: string
  stage: string | null
  payload: ItemPayload
  entry_id: number | null
  answer: string | null
  outcome: Outcome | null
}

export type QuizFocus = 'MIXED' | 'SENTENCES' | 'READING' | 'LISTENING' | 'WRITING' | 'VOCABULARY' | 'GRAMMAR'

export type Assessment = {
  id: number
  kind: 'QUICK' | 'WARMUP' | 'BOSS'
  focus: QuizFocus
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

export type LookupStatus = 'pending' | 'ok' | 'not_found' | 'unavailable' | 'offline'
export type Strength = 'new' | 'weak' | 'learning' | 'strong'

export type BankSummary = {
  id: number
  kind: 'WORD' | 'PHRASE'
  headword: string
  pos: string | null
  translation: string | null
  lookup_status: LookupStatus
  forms_seen: string[]
  strength: Strength
  sessions_count: number
  created_at: string
  last_seen_at: string | null
  due_at: string | null
}

export type FormAnalysis = {
  tense: string
  tense_label: string
  mood?: string
  person: string | null
  person_label: string | null
  who: string | null
  when: string | null
  summary: string
}

export type ConjugationRow = {
  tense: string
  label: string
  mood: string
  when: string
  core: boolean
  cells: Record<string, string[]>
}

export type Conjugation = {
  infinitive: string
  persons: { key: string; label: string; who: string }[]
  rows: ConjugationRow[]
  gerund: string[]
  participle: string[]
  seen: string[]
}

export type BankDetail = BankSummary & {
  forms: { form: string; meaning: string | null; analyses: FormAnalysis[]; clitics: string[]; also: string[] }[]
  breakdown: { surface: string; lemma: string; pos: string | null; entry_id: number | null; translation: string | null; readings: FormAnalysis[] }[]
  senses: { pos: string; senses: { gloss: string }[] }[]
  user_translation: string | null
  note: string | null
  auto_translation: string | null
  conjugation: Conjugation | null
  examples: { es: string; en: string; source: string }[]
  your_sentences: { sentence_text: string; session_id: number; created_at: string }[]
  sessions: { id: number; created_at: string; activity_type: string; context_text: string }[]
  words: BankSummary[]
  phrases: BankSummary[]
  results: { outcome: Outcome; modality: string; created_at: string }[]
  stats: { hits: number; partials: number; misses: number; box: number }
  attribution: string[]
}

export type LookupPreview = {
  kind: 'WORD' | 'PHRASE'
  text: string
  translation: string | null
  words: { surface: string; lemma: string; pos: string | null; translation: string | null; forms: FormAnalysis[] }[]
  meaning: string | null
  english_only: boolean
  english: string[]
}

export type EntryBrief = Pick<BankSummary, 'id' | 'kind' | 'headword' | 'translation' | 'strength'>

export type Recap =
  | { empty: true; warmup_done_today: boolean }
  | {
      empty: false
      previous_day: string | null
      sessions: { id: number; created_at: string; local_date: string; activity_type: string; context_text: string; entries: EntryBrief[] }[]
      weak: EntryBrief[]
      due_count: number
      untested_count: number
      bank_size: number
      last_quiz: { id: number; kind: string; graded_at: string; correct: number; total: number } | null
      streak: Progress['streak']
      warmup_done_today: boolean
      warmup_items: number
    }

export type SkillScore = {
  key: string
  label: string
  status: 'ASSESSED' | 'NOT_ASSESSED'
  score: number | null
  answers: number
  answers_needed: number
  trend: number | null
  weakest?: { label: string; correct: number; total: number }[]
}

export type Skills = { skills: SkillScore[]; areas: SkillScore[]; min_answers: number }

export type UserSettings = {
  quiz_items: number
  warmup_items: number
  listening: boolean
  motion: 'system' | 'reduce'
}

export type StudySessionInput = {
  mode: StudySession['mode']
  activity_type: string
  duration_minutes: number
  context_text: string
  terms: string[]
  sentences: string[]
  words_only?: string[]
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
  settings: (signal?: AbortSignal) => request<UserSettings>('GET', '/api/settings', undefined, signal),
  saveSettings: (patch: Partial<UserSettings>) => request<UserSettings>('PATCH', '/api/settings', patch),
  signOutOthers: () => request<{ signed_out: number }>('POST', '/api/settings/sign-out-others'),
  resetAll: (password: string, confirm: string) =>
    request<{ deleted: { study_sessions: number; words: number; quizzes: number } }>('POST', '/api/settings/reset', { password, confirm }),
  boss: (signal?: AbortSignal) => request<BossState>('GET', '/api/boss', undefined, signal),
  startBoss: (listening: boolean) =>
    request<{ boss: BossState; assessment: Assessment }>('POST', '/api/boss', { listening }),
  recap: (signal?: AbortSignal) => request<Recap>('GET', '/api/recap', undefined, signal),
  skills: (signal?: AbortSignal) => request<Skills>('GET', '/api/progress/skills', undefined, signal),
  createWarmup: (listening: boolean) => request<Assessment>('POST', '/api/warmups', { listening }),
  createAssessment: (body: { focus?: QuizFocus; listening?: boolean } = {}) =>
    request<Assessment>('POST', '/api/assessments', body),
  answerItem: (id: number, item_id: number, text: string) =>
    request<Assessment>('POST', `/api/assessments/${id}/answers`, { item_id, text }),
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
  listBank: (params: { q?: string; kind?: 'WORD' | 'PHRASE'; sort?: 'recent' | 'alpha' | 'weak'; offset?: number; limit?: number }, signal?: AbortSignal) => {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') qs.set(k, String(v))
    return request<{ total: number; items: BankSummary[]; counts: { WORD: number; PHRASE: number } }>('GET', `/api/bank?${qs}`, undefined, signal)
  },
  getBankEntry: (id: number, signal?: AbortSignal) => request<BankDetail>('GET', `/api/bank/${id}`, undefined, signal),
  patchBankEntry: (id: number, body: { user_translation?: string; note?: string }) =>
    request<BankDetail>('PATCH', `/api/bank/${id}`, body),
  lookup: (term: string, signal?: AbortSignal) =>
    request<LookupPreview>('GET', `/api/lookup?term=${encodeURIComponent(term)}`, undefined, signal),
  deleteSession: (id: number) =>
    request<{ deleted: number; xp_removed: number; entries_removed: number }>('DELETE', `/api/study-sessions/${id}`),
  listSessions: (offset: number, limit = 20, signal?: AbortSignal) =>
    request<{ total: number; items: StudySession[] }>(
      'GET',
      `/api/study-sessions?limit=${limit}&offset=${offset}`,
      undefined,
      signal,
    ),
}
