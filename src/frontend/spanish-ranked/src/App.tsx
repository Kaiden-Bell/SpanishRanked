import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { api, setCsrfToken, setSignedOutHandler, type User } from './api'
import ChangePassword from './ChangePassword'
import History from './History'
import Login from './Login'
import NewSession from './NewSession'

type View = 'history' | 'new'

function App() {
  // undefined = still checking for an existing session, null = signed out.
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [unreachable, setUnreachable] = useState(false)
  const [view, setView] = useState<View>('history')
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
    setView('history')
    setNotice(undefined)
  }

  function go(next: View) {
    setNotice(undefined)
    setView(next)
  }

  let body
  if (user === undefined) body = <p>Loading…</p>
  else if (user === null) body = <Login onSignedIn={setUser} />
  else if (user.must_change_password) body = <ChangePassword onChanged={setUser} />
  else if (view === 'new')
    body = (
      <NewSession
        onSaved={() => {
          setNotice('Session saved.')
          setView('history')
        }}
      />
    )
  else body = <History notice={notice} onStart={() => go('new')} />

  return (
    <main className="shell">
      <header className="topbar">
        <h1>Language AI</h1>
        {user && !user.must_change_password && (
          <nav aria-label="Main">
            <button className={view === 'history' ? 'active' : ''} onClick={() => go('history')}>History</button>
            <button className={view === 'new' ? 'active' : ''} onClick={() => go('new')}>Start study session</button>
            <button onClick={logout}>Sign out</button>
          </nav>
        )}
      </header>
      {unreachable && <p className="bad" role="alert">Cannot reach the backend.</p>}
      {body}
    </main>
  )
}

export default App
