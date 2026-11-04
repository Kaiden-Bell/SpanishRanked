import { useEffect, useState } from 'react'
import './App.css'

type Health = { status: string; schema_version: number }

function App() {
  const [health, setHealth] = useState<Health | 'error' | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/health', { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then(setHealth)
      .catch((err) => {
        if (err.name !== 'AbortError') setHealth('error')
      })
    return () => controller.abort()
  }, [])

  return (
    <main className="shell">
      <h1>Language AI</h1>
      <p className="tagline">Study something, log it, take a short assessment, see your progress.</p>
      <section className="card" aria-live="polite">
        <h2>Backend</h2>
        {health === null && <p>Checking…</p>}
        {health === 'error' && <p className="bad">Cannot reach the backend.</p>}
        {health && health !== 'error' && (
          <p className="good">
            Connected · database schema v{health.schema_version}
          </p>
        )}
      </section>
    </main>
  )
}

export default App
