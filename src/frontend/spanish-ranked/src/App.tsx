import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { api, QUIZ_GRADING_EVENT, setCsrfToken, setSignedOutHandler, type Award, type GradedNotice, type Theme, type User } from './api'
import Assessment from './Assessment'
import Dashboard from './Dashboard'
import ChangePassword from './ChangePassword'
import Guided from './Guided'
import History from './History'
import Login from './Login'
import NewSession from './NewSession'
import Scene from './Scene'
import Boss from './Boss'
import Settings from './Settings'
import Toast from './Toast'
import Warmup from './Warmup'
import WordBank from './WordBank'

type View = 'dashboard' | 'history' | 'new' | 'guided' | 'quiz' | 'words' | 'warmup' | 'boss' | 'settings'

const NAV: { view: View; label: string }[] = [
  { view: 'dashboard', label: 'Dashboard' },
  { view: 'new', label: 'Study' },
  { view: 'guided', label: 'Guided' },
  { view: 'quiz', label: 'Quiz' },
  { view: 'words', label: 'Words' },
  { view: 'history', label: 'History' },
]

const KIND_LABEL: Record<GradedNotice['kind'], string> = { QUICK: 'Quiz', WARMUP: 'Warm-up', BOSS: 'Boss battle' }
const POLL_MS = 5000

function awardMessage(a: Award): string {
  if (a.awarded_xp === 0) return 'Session saved. You have reached today’s study XP limit, but it still counts toward your streak.'
  const bonus = a.multiplier > 1 ? ` (${a.base_xp} × ${a.multiplier.toFixed(2)} streak bonus)` : ''
  const capped = a.capped ? ' — today’s study XP limit reached' : ''
  return `Session saved: +${a.awarded_xp} XP${bonus}${capped}.`
}

function applyMotion(motion: 'system' | 'reduce') {
  if (motion === 'reduce') document.documentElement.dataset.motion = 'reduce'
  else delete document.documentElement.dataset.motion
}

function applyTheme(theme: string) {
  if (theme && theme !== 'alhambra') document.documentElement.dataset.theme = theme
  else delete document.documentElement.dataset.theme
}

/** Quizzes grading in the background: which are still going, and a notice when one finishes. */
function useGradingWatch(signedIn: boolean, onGraded: (n: GradedNotice) => void) {
  const [grading, setGrading] = useState<number[]>([])
  const ids = useRef<number[]>([])
  const since = useRef('')
  const graded = useRef(onGraded)
  useEffect(() => {
    graded.current = onGraded
  })

  const update = useCallback((next: number[]) => {
    ids.current = next
    setGrading(next)
  }, [])

  const check = useCallback((signal?: AbortSignal) => {
    return api.assessmentActivity(since.current, signal).then((a) => {
      for (const n of a.graded) if (ids.current.includes(n.id)) graded.current(n)
      update(a.grading)
      since.current = a.now
    })
  }, [update])

  // Quizzes left grading from an earlier visit are picked up at sign-in.
  useEffect(() => {
    if (!signedIn) return
    const controller = new AbortController()
    check(controller.signal).catch(() => {})
    const started = (e: Event) => {
      const id = (e as CustomEvent<{ id: number }>).detail.id
      if (!ids.current.includes(id)) update([...ids.current, id])
    }
    window.addEventListener(QUIZ_GRADING_EVENT, started)
    return () => {
      controller.abort()
      window.removeEventListener(QUIZ_GRADING_EVENT, started)
      ids.current = []
      since.current = '' // the next sign-in starts fresh; its first check replaces the list
    }
  }, [signedIn, check, update])

  const busy = grading.length > 0
  useEffect(() => {
    if (!busy) return
    const controller = new AbortController()
    const timer = setInterval(() => check(controller.signal).catch(() => {}), POLL_MS)
    return () => {
      clearInterval(timer)
      controller.abort()
    }
  }, [busy, check])

  return grading
}

function App() {
  // undefined = still checking for an existing session, null = signed out.
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [unreachable, setUnreachable] = useState(false)
  const [view, setView] = useState<View>('dashboard')
  const [notice, setNotice] = useState<string>()
  const [wordId, setWordId] = useState<number | null>(null)
  const [quizId, setQuizId] = useState<number | null>(null)
  const [toast, setToast] = useState<GradedNotice | null>(null)
  const [refresh, setRefresh] = useState(0)
  const [theme, setTheme] = useState('alhambra')
  const [themes, setThemes] = useState<Theme[]>([])

  const signedOut = useCallback(() => {
    applyMotion('system')
    applyTheme('alhambra')
    setTheme('alhambra')
    setCsrfToken('')
    setUser(null)
  }, [])

  useEffect(() => {
    setSignedOutHandler(signedOut)
    const controller = new AbortController()
    api
      .me(controller.signal)
      .then((u) => {
        setCsrfToken(u.csrf_token)
        setUser(u)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        // A 401 already routed us to the sign-in form via the handler; anything else is a real outage.
        if (err.status === 0) setUnreachable(true)
        setUser(null)
      })
    return () => controller.abort()
  }, [signedOut])

  async function logout() {
    await api.logout().catch(() => {})
    signedOut()
    setView('dashboard')
    setNotice(undefined)
    setToast(null)
  }

  const openWord = (id: number) => {
    go('words')
    setWordId(id)
  }

  function go(next: View) {
    setNotice(undefined)
    setWordId(null)
    setQuizId(null)
    setView(next)
    window.scrollTo({ top: 0 })
  }

  const openQuiz = (id: number) => {
    go('quiz')
    setQuizId(id)
    setToast(null)
  }

  const signedIn = !!user && !user.must_change_password

  const grading = useGradingWatch(signedIn, (n) => {
    setToast(n)
    setRefresh((r) => r + 1) // the dashboard's XP, rank and skills changed
  })

  // Reduced motion and the theme from Settings apply on every device the learner signs in on.
  useEffect(() => {
    if (!signedIn) return
    const controller = new AbortController()
    api.settings(controller.signal).then((s) => {
      applyMotion(s.motion)
      applyTheme(s.theme)
      setTheme(s.theme)
    }).catch(() => {})
    api.themes(controller.signal).then(setThemes).catch(() => {})
    return () => controller.abort()
  }, [signedIn, refresh])

  const changeTheme = (id: string) => {
    applyTheme(id)
    setTheme(id)
  }
  const sceneId = themes.find((t) => t.id === theme)?.scene ?? null

  let body
  if (user === undefined) body = <p className="status">Loading…</p>
  else if (user === null) body = <Login onSignedIn={setUser} />
  else if (user.must_change_password) body = <ChangePassword onChanged={setUser} />
  else if (view === 'new')
    body = (
      <NewSession
        onSaved={(award) => {
          setNotice(awardMessage(award))
          setView('dashboard')
          window.scrollTo({ top: 0 })
        }}
      />
    )
  else if (view === 'guided') body = <Guided onOpenWord={openWord} />
  else if (view === 'words') body = <WordBank key={wordId ?? 'list'} initialId={wordId} onStudy={() => go('new')} />
  else if (view === 'history') body = <History onStart={() => go('new')} />
  else if (view === 'quiz')
    body = (
      <Assessment
        key={quizId ?? 'new'}
        initialId={quizId}
        onStudy={() => go('new')}
        onDone={() => go('dashboard')}
        onOpenWord={openWord}
        onThemes={() => go('settings')}
      />
    )
  else if (view === 'settings')
    body = (
      <Settings
        onMotion={applyMotion}
        onTheme={changeTheme}
        onReset={(message) => {
          go('dashboard')
          setNotice(message)
          changeTheme('alhambra')
        }}
      />
    )
  else if (view === 'boss')
    body = <Boss onDone={() => go('dashboard')} onPractice={() => go('warmup')} onOpenWord={openWord} onThemes={() => go('settings')} />
  else if (view === 'warmup') body = <Warmup onDone={() => go('dashboard')} onStudy={() => go('new')} onOpenWord={openWord} />
  else
    body = (
      <Dashboard
        key={refresh}
        name={user.username}
        notice={notice}
        onStart={() => go('new')}
        onQuiz={() => go('quiz')}
        onHistory={() => go('history')}
        onWarmup={() => go('warmup')}
        onBoss={() => go('boss')}
        onOpenWord={openWord}
      />
    )

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-name">Language AI</span>
          <span className="brand-sub">Learn Spanish</span>
        </div>
        {signedIn && (
          <>
            <nav className="nav" aria-label="Primary">
              {NAV.map((n) => (
                <button key={n.view} aria-current={view === n.view ? 'page' : undefined} onClick={() => go(n.view)}>
                  {n.label}
                  {n.view === 'quiz' && signedIn && grading.length > 0 && (
                    <span className="nav-badge" title="A quiz is being graded in the background">
                      <span className="pulse" aria-hidden="true" />Grading
                    </span>
                  )}
                </button>
              ))}
            </nav>
            <div className="rail-foot">
              <span className="who">Signed in as {user.username}</span>
              <button className="btn ghost" aria-current={view === 'settings' ? 'page' : undefined} onClick={() => go('settings')}>Settings</button>
              <button className="btn ghost" onClick={logout}>Sign out</button>
            </div>
          </>
        )}
      </aside>
      <main className="stage" data-view={signedIn ? view : 'signin'}>
        <Scene sceneId={signedIn ? sceneId : null} />
        <div className="view">
          {unreachable && <p className="error" role="alert">Cannot reach the backend.</p>}
          {body}
        </div>
      </main>
      {toast && (
        <Toast onClose={() => setToast(null)} action={{ label: 'View results', onClick: () => openQuiz(toast.id) }}>
          <strong>{KIND_LABEL[toast.kind] ?? 'Quiz'} graded</strong>
          <span className="num">
            {toast.correct ?? 0} of {toast.total} correct{toast.awarded_xp > 0 && <> · +{toast.awarded_xp} XP</>}
          </span>
        </Toast>
      )}
    </div>
  )
}

export default App
