import { useEffect, useState } from 'react'
import { api, ApiError, type StudySession } from './api'

const PAGE = 20

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function History({ onStart }: { onStart: () => void }) {
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
    <>
      <header className="page-head">
        <h1>History</h1>
        {!!total && (
          <p className="lede num">
            {total} study {total === 1 ? 'session' : 'sessions'} logged
          </p>
        )}
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      {total === null && !error && <p className="status">Loading…</p>}
      {total === 0 && (
        <div className="empty">
          <p>No study sessions yet. Your logged sessions will appear here.</p>
          <button className="btn primary" onClick={onStart}>Start Study Session</button>
        </div>
      )}
      <div className="entries">
        {items.map((s) => (
          <article className="card entry" key={s.id}>
            <header>
              <span className="entry-mode">{s.mode === 'SELF_STUDY' ? 'Self-study' : 'Guided study'}</span>
              <span className="entry-what num">
                {s.activity_type.charAt(0) + s.activity_type.slice(1).toLowerCase()} · {s.duration_minutes} min
              </span>
              <time dateTime={s.created_at}>{when(s.created_at)}</time>
            </header>
            <p className="entry-context">{s.context_text}</p>
            <ul className="tags" aria-label="Words and phrases">
              {s.terms.map((t) => <li key={t}>{t}</li>)}
            </ul>
            <ul className="sentences" aria-label="Sentences" lang="es">
              {s.sentences.map((x) => <li key={x}>{x}</li>)}
            </ul>
          </article>
        ))}
      </div>
      {total !== null && items.length < total && (
        <div className="actions">
          <button className="btn" onClick={loadMore} disabled={loadingMore}>{loadingMore ? 'Loading…' : 'Load more'}</button>
        </div>
      )}
    </>
  )
}
