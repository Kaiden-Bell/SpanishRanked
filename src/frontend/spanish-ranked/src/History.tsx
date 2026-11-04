import { useEffect, useState } from 'react'
import { api, ApiError, type StudySession } from './api'

const PAGE = 20

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function History({ notice, onStart }: { notice?: string; onStart: () => void }) {
  const [items, setItems] = useState<StudySession[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    api
      .listSessions(0, PAGE, controller.signal)
      .then((page) => {
        setItems(page.items)
        setTotal(page.total)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load history.')
      })
    return () => controller.abort()
  }, [])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const page = await api.listSessions(items.length, PAGE)
      setItems((prev) => [...prev, ...page.items])
      setTotal(page.total)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load more.')
    }
    setLoadingMore(false)
  }

  return (
    <section>
      {notice && <p className="good" role="status">{notice}</p>}
      <h2>History</h2>
      {error && <p className="bad" role="alert">{error}</p>}
      {total === null && !error && <p>Loading…</p>}
      {total === 0 && (
        <div className="card">
          <p>No study sessions yet.</p>
          <button onClick={onStart}>Start study session</button>
        </div>
      )}
      {items.map((s) => (
        <article className="card entry" key={s.id}>
          <header>
            <strong>{s.mode === 'SELF_STUDY' ? 'Self-study' : 'Guided study'}</strong>
            <span>
              {s.activity_type.charAt(0) + s.activity_type.slice(1).toLowerCase()} · {s.duration_minutes} min
            </span>
            <time dateTime={s.created_at}>{when(s.created_at)}</time>
          </header>
          <p>{s.context_text}</p>
          <ul className="chips">{s.terms.map((t) => <li key={t}>{t}</li>)}</ul>
          <ul className="sentences">{s.sentences.map((x) => <li key={x}>{x}</li>)}</ul>
        </article>
      ))}
      {total !== null && items.length < total && (
        <button onClick={loadMore} disabled={loadingMore}>{loadingMore ? 'Loading…' : 'Load more'}</button>
      )}
    </section>
  )
}
