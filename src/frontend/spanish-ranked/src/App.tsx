import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { api, setCsrfToken, setSignedOutHandler, type Award, type User } from './api'
import Dashboard from './Dashboard'
import ChangePassword from './ChangePassword'
import History from './History'
import Login from './Login'
import NewSession from './NewSession'
import Scene from './Scene'

type View = 'dashboard' | 'history' | 'new'

const NAV: { view: View; label: string }[] = [
  { view: 'dashboard', label: 'Dashboard' },
  { view: 'new', label: 'Study' },
  { view: 'history', label: 'History' },
]

function awardMessage(a: Award): string {
  if (a.awarded_xp === 0) return 'Session saved. You have reached today’s study XP limit, but it still counts toward your streak.'
  const bonus = a.multiplier > 1 ? ` (${a.base_xp} × ${a.multiplier.toFixed(2)} streak bonus)` : ''
  const capped = a.capped ? ' — today’s study XP limit reached' : ''
  return `Session saved: +${a.awarded_xp} XP${bonus}${capped}.`
}

function App() {
  // undefined = still checking for an existing session, null = signed out.
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [unreachable, setUnreachable] = useState(false)
  const [view, setView] = useState<View>('dashboard')
  const [notice, setNotice] = useState<string>()

  const signedOut = useCallback(() => {
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
  }

  function go(next: View) {
    setNotice(undefined)
    setView(next)
    window.scrollTo({ top: 0 })
  }

  const signedIn = !!user && !user.must_change_password

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
  else if (view === 'history') body = <History onStart={() => go('new')} />
  else
    body = (
      <Dashboard
        name={user.username}
        notice={notice}
        onStart={() => go('new')}
        onHistory={() => go('history')}
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
                </button>
              ))}
            </nav>
            <div className="rail-foot">
              <span className="who">Signed in as {user.username}</span>
              <button className="btn ghost" onClick={logout}>Sign out</button>
            </div>
          </>
        )}
      </aside>
      <main className="stage" data-view={signedIn ? view : 'signin'}>
        <Scene />
        <div className="view">
          {unreachable && <p className="error" role="alert">Cannot reach the backend.</p>}
          {body}
        </div>
      </main>
    </div>
  )
}

export default App
