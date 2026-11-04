import { useEffect, useState } from 'react'
import { api, ApiError, type Progress, type StudySession } from './api'

type Props = { notice?: string; onStart: () => void; onHistory: () => void }

export default function Dashboard({ notice, onStart, onHistory }: Props) {
  const [progress, setProgress] = useState<Progress | null>(null)
  const [recent, setRecent] = useState<StudySession[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([api.progress(controller.signal), api.listSessions(0, 3, controller.signal)])
      .then(([p, page]) => {
        setProgress(p)
        setRecent(page.items)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load progress.')
      })
    return () => controller.abort()
  }, [])

  if (error) return <p className="bad" role="alert">{error}</p>
  if (!progress) return <p>Loading…</p>

  const { rank, next_rank: next, streak, today } = progress
  const span = next ? next.min_xp - rank.min_xp : 1
  const into = progress.total_xp - rank.min_xp
  const streakNote =
    streak.current === 0
      ? 'Log a session today to start a streak.'
      : streak.active_today
        ? 'Done for today.'
        : 'Log a session today to keep it going.'

  return (
    <section>
      {notice && <p className="good" role="status">{notice}</p>}

      <div className="card">
        <p className="eyebrow">Current rank</p>
        <h2 className="rank">{rank.name}</h2>
        <progress
          max={next ? span : 1}
          value={next ? into : 1}
          aria-label={next ? `Progress to ${next.name}` : 'Top rank reached'}
        />
        <p className="hint">
          {progress.total_xp} XP total ·{' '}
          {next ? `${progress.xp_to_next} XP to ${next.name}` : 'highest rank reached'}
        </p>
      </div>

      <div className="stats">
        <div className="card">
          <p className="eyebrow">Streak</p>
          <p className="big">{streak.current} {streak.current === 1 ? 'day' : 'days'}</p>
          <p className="hint">
            {streakNote}
            {streak.next_multiplier > 1 && ` Next session earns ×${streak.next_multiplier.toFixed(2)}.`}
          </p>
        </div>
        <div className="card">
          <p className="eyebrow">Study XP today</p>
          <p className="big">{today.study_xp} / {today.study_xp_cap}</p>
          <progress max={today.study_xp_cap} value={today.study_xp} aria-label="Study XP earned today" />
        </div>
      </div>

      <div className="card">
        <h2>Recent sessions</h2>
        {recent.length === 0 ? (
          <p>No study sessions yet.</p>
        ) : (
          <ul className="recent">
            {recent.map((s) => (
              <li key={s.id}>
                <span>{s.terms.join(', ')}</span>
                <span className="hint">{s.duration_minutes} min</span>
              </li>
            ))}
          </ul>
        )}
        <div className="actions">
          <button className="primary" onClick={onStart}>Start study session</button>
          {recent.length > 0 && <button onClick={onHistory}>View all history</button>}
        </div>
      </div>
    </section>
  )
}
