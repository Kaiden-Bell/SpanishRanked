import { useEffect, useState, type CSSProperties } from 'react'
import { api, ApiError, type Progress, type StudySession, type SystemStatus } from './api'

type Props = { name: string; notice?: string; onStart: () => void; onQuiz: () => void; onHistory: () => void }

// Level 1 has no assessments yet, so every skill is honestly unmeasured.
const SKILLS = ['Reading', 'Writing', 'Listening', 'Speaking']

function when(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

export default function Dashboard({ name, notice, onStart, onQuiz, onHistory }: Props) {
  const [progress, setProgress] = useState<Progress | null>(null)
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [recent, setRecent] = useState<StudySession[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([api.progress(controller.signal), api.listSessions(0, 3, controller.signal)])
      .then(([p, page]) => {
        setProgress(p)
        setRecent(page.items)
        setTotal(page.total)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load progress.')
      })
    // Advisory only: if the status call fails, the dashboard simply shows no banner.
    api.systemStatus(controller.signal).then(setSystem).catch(() => {})
    return () => controller.abort()
  }, [])

  const modelDown = system !== null && system.model !== 'ok'
  const hintsDown = system !== null && system.languagetool !== 'ok'

  const isNew = !!progress && total === 0 && progress.total_xp === 0

  const hello = (
    <header className="hello">
      <h1>¡Hola, {name}!</h1>
      <p className="hello-sub">{isNew ? 'Log your first session to begin.' : 'Ready to keep learning Spanish?'}</p>
      <div className="actions">
        <button className="btn primary" onClick={onStart}>Start Study Session</button>
        <button className="btn" onClick={onQuiz}>Quick Assessment</button>
        {total > 0 && <button className="btn ghost" onClick={onHistory}>View history</button>}
      </div>
    </header>
  )

  if (error)
    return (
      <>
        {hello}
        <p className="error" role="alert">{error}</p>
      </>
    )
  if (!progress)
    return (
      <>
        {hello}
        <p className="status">Loading progress…</p>
      </>
    )

  const { rank, next_rank: next, streak, today } = progress
  const span = next ? next.min_xp - rank.min_xp : 1
  const into = progress.total_xp - rank.min_xp
  const ratio = next ? Math.min(1, Math.max(0, into / span)) : 1
  const streakHead =
    streak.current === 0 ? 'No streak yet' : `${streak.current} ${streak.current === 1 ? 'day' : 'days'} running`
  const streakNote =
    streak.current === 0
      ? 'Log a study session to start a streak.'
      : streak.active_today
        ? 'Done for today.'
        : 'Log a session today to keep it going.'
  const bonus =
    streak.next_multiplier > 1
      ? `+${Math.round((streak.next_multiplier - 1) * 100)}% XP on your next session`
      : 'Streak bonus starts at 3 days'

  return (
    <>
      {notice && <p className="notice" role="status">{notice}</p>}
      {(modelDown || hintsDown) && (
        <p className="notice warn" role="status">
          {modelDown
            ? 'Quizzes are unavailable: the local language model is not reachable. Logging study sessions still works.'
            : 'The grammar checker is offline. Quizzes still work, but are graded without its hints.'}
        </p>
      )}
      {hello}

      <div className="grid">
        <section className="card rank-card" aria-labelledby="rk">
          <h2 id="rk">{rank.name}</h2>
          <p className="cap">Current rank</p>
          <span
            className="bar"
            role="progressbar"
            aria-label={next ? `Progress to ${next.name}` : 'Highest rank reached'}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(ratio * 100)}
          >
            <span className="fill" style={{ '--w': ratio } as CSSProperties} />
          </span>
          <p className="meta num">
            {next ? `${into} / ${span} XP to ${next.name}` : 'Highest rank reached'} · {progress.total_xp} XP total
          </p>
        </section>

        <section className="card streak-card" aria-labelledby="sk">
          <h2 id="sk">{streakHead}</h2>
          <p className="cap">{streakNote}</p>
          <div className="meta-group">
            <p className="meta">{bonus}</p>
            <p className="meta num">
              {today.study_xp} / {today.study_xp_cap} study XP today
            </p>
          </div>
        </section>

        <section className="card" aria-labelledby="sp">
          <div className="card-head">
            <h2 id="sp">Skill profile</h2>
            <p className="cap">Each skill stands alone</p>
          </div>
          <ul className="skill-list">
            {SKILLS.map((s) => (
              <li className="skill" key={s}>
                <span>{s}</span>
                <span className="bar empty-track" aria-hidden="true" />
                <span className="skill-val">Not yet assessed</span>
              </li>
            ))}
          </ul>
          <p className="foot">Scored only from your own assessments. No CEFR level is guessed.</p>
        </section>

        <section className="card" aria-labelledby="rs">
          <div className="card-head">
            <h2 id="rs">Recent sessions</h2>
            <p className="cap num">{total} total</p>
          </div>
          {recent.length === 0 ? (
            <p className="meta">No study sessions yet.</p>
          ) : (
            <ul className="recent-list">
              {recent.map((s) => (
                <li key={s.id}>
                  <span className="recent-terms">{s.terms.join(', ')}</span>
                  <span className="recent-mins num">{s.duration_minutes} min</span>
                  <time className="recent-when" dateTime={s.created_at}>{when(s.created_at)}</time>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  )
}
