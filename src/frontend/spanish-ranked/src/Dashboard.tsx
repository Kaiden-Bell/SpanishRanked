import { useEffect, useState, type CSSProperties } from 'react'
import { api, ApiError, type Progress, type Recap, type Skills, type SkillScore, type StudySession, type SystemStatus } from './api'

type Props = {
  name: string
  notice?: string
  onStart: () => void
  onQuiz: () => void
  onHistory: () => void
  onWarmup: () => void
  onBoss: () => void
  onOpenWord: (id: number) => void
}

const DISMISS_KEY = 'languageai.recapDismissed'

function when(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

function todayKey() {
  return new Date().toLocaleDateString('en-CA')
}

// Per-browser convenience only: the server decides whether today's warm-up is done.
function dismissedToday(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === todayKey()
  } catch {
    return false
  }
}

function SkillRow({ s }: { s: SkillScore }) {
  const assessed = s.status === 'ASSESSED' && s.score !== null
  const trend = s.trend === null ? null : s.trend > 0.05 ? 'up' : s.trend < -0.05 ? 'down' : 'steady'
  return (
    <li className="skill">
      <span>{s.label}</span>
      {assessed ? (
        <span className="bar" role="img" aria-label={`${s.label}: ${Math.round(s.score! * 100)}%`}>
          <span className="fill" style={{ '--w': s.score } as CSSProperties} />
        </span>
      ) : (
        <span className="bar empty-track" aria-hidden="true" />
      )}
      <span className="skill-val num">
        {assessed
          ? <>{Math.round(s.score! * 100)}%{trend && trend !== 'steady' && <> · {trend === 'up' ? 'improving' : 'slipping'}</>}</>
          : s.key === 'SPEAKING' ? 'Not yet assessed' : s.answers === 0 ? 'Not yet assessed' : `${s.answers_needed} more answers`}
      </span>
    </li>
  )
}

function RecapCard({ recap, onWarmup, onOpenWord, onDismiss }: {
  recap: Extract<Recap, { empty: false }>
  onWarmup: () => void
  onOpenWord: (id: number) => void
  onDismiss: () => void
}) {
  const session = recap.sessions[0]
  const sameDay = recap.sessions.filter((s) => s.local_date === session.local_date)
  const words = sameDay.flatMap((s) => s.entries)
  return (
    <section className="card recap-card" aria-labelledby="rc">
      <div className="card-head">
        <h2 id="rc">Since last time</h2>
        <p className="cap">{when(session.created_at)}</p>
      </div>
      <p className="recap-context">{sameDay.map((s) => s.context_text).join(' · ')}</p>
      {words.length > 0 && (
        <ul className="tags recap-words">
          {words.map((w) => (
            <li key={w.id}>
              <button className="tag-link" onClick={() => onOpenWord(w.id)} lang="es">
                {w.headword}{w.translation && <span className="tag-tr"> · {w.translation}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {recap.weak.length > 0 && (
        <p className="meta">
          Needs practice: <span lang="es">{recap.weak.slice(0, 5).map((w) => w.headword).join(', ')}</span>
        </p>
      )}
      <p className="meta num">
        {recap.due_count} {recap.due_count === 1 ? 'word is' : 'words are'} due for review
        {recap.last_quiz && <> · last quiz {recap.last_quiz.correct} of {recap.last_quiz.total}</>}
      </p>
      {recap.warmup_done_today ? (
        <p className="cap">Warm-up done for today.</p>
      ) : (
        <div className="actions">
          <button className="btn primary" onClick={onWarmup}>Warm up · {recap.warmup_items} questions</button>
          <button className="btn ghost" onClick={onDismiss}>Not now</button>
        </div>
      )}
    </section>
  )
}

function time(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

export default function Dashboard({ name, notice, onStart, onQuiz, onHistory, onWarmup, onBoss, onOpenWord }: Props) {
  const [progress, setProgress] = useState<Progress | null>(null)
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [recent, setRecent] = useState<StudySession[]>([])
  const [total, setTotal] = useState(0)
  const [recap, setRecap] = useState<Recap | null>(null)
  const [skills, setSkills] = useState<Skills | null>(null)
  const [dismissed, setDismissed] = useState(dismissedToday)
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
    // Advisory: if these fail, the dashboard shows the rest.
    api.recap(controller.signal).then(setRecap).catch(() => {})
    api.skills(controller.signal).then(setSkills).catch(() => {})
    api.systemStatus(controller.signal).then(setSystem).catch(() => {})
    return () => controller.abort()
  }, [])

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, todayKey())
    } catch {
      /* private mode: dismiss for this visit only */
    }
    setDismissed(true)
  }

  const modelDown = system !== null && system.model !== 'ok'
  const hintsDown = system !== null && system.languagetool !== 'ok'
  const isNew = !!progress && total === 0 && progress.total_xp === 0
  const showRecap = recap !== null && !recap.empty && (!dismissed || recap.warmup_done_today)
  const warmupFirst = showRecap && !recap.warmup_done_today

  const hello = (
    <header className="hello">
      <h1>¡Hola, {name}!</h1>
      <p className="hello-sub">
        {isNew ? 'Log your first session to begin.' : warmupFirst ? 'Warm up on what you learned last time.' : 'Ready to keep learning Spanish?'}
      </p>
      <div className="actions">
        <button className={warmupFirst ? 'btn' : 'btn primary'} onClick={onStart}>Start Study Session</button>
        <button className="btn" onClick={onQuiz}>Quiz</button>
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

  const { rank, next_rank: next, streak, today, boss } = progress
  const span = next ? next.min_xp - rank.min_xp : 1
  // Can be below the rank's threshold after a deleted session took its XP back; the rank itself stays.
  const into = Math.max(0, progress.total_xp - rank.min_xp)
  const ratio = next ? Math.min(1, Math.max(0, into / span)) : 1
  const streakHead =
    streak.current === 0 ? 'No streak yet' : `${streak.current} ${streak.current === 1 ? 'day' : 'days'} running`
  const streakNote =
    streak.current === 0
      ? 'Log a session, take a quiz or warm up to start a streak.'
      : streak.active_today
        ? 'Done for today.'
        : 'Study, quiz or warm up today to keep it going.'
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
            ? 'The local language model is not reachable. Quizzes and warm-ups still work, without free-sentence questions; sentence practice is unavailable.'
            : 'The grammar checker is offline. Free sentences are graded without its hints.'}
        </p>
      )}
      {hello}

      {showRecap && <RecapCard recap={recap} onWarmup={onWarmup} onOpenWord={onOpenWord} onDismiss={dismiss} />}

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
            {boss.rank
              ? `XP reached for ${boss.rank} · ${progress.total_xp} XP total`
              : <>{next ? `${into} / ${span} XP to ${next.name}` : 'Highest rank reached'} · {progress.total_xp} XP total</>}
          </p>
          {boss.rank && (
            <div className="boss-callout">
              <p className="meta">
                {boss.status === 'READY' && `Win the boss battle to become ${boss.rank}.`}
                {boss.status === 'IN_PROGRESS' && 'Your boss battle is waiting for you.'}
                {boss.status === 'COOLDOWN' && boss.cooldown_until && `The boss is resting until ${time(boss.cooldown_until)}. Your missed words are in your warm-up.`}
                {boss.status === 'NEEDS_WORDS' && `Log ${boss.words_needed} more words to unlock the boss battle for ${boss.rank}.`}
              </p>
              {(boss.status === 'READY' || boss.status === 'IN_PROGRESS') && (
                <button className="btn" onClick={onBoss}>{boss.status === 'READY' ? 'Face the boss' : 'Continue the battle'}</button>
              )}
            </div>
          )}
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
            {(skills?.skills ?? []).map((s) => <SkillRow key={s.key} s={s} />)}
          </ul>
          {skills && (
            <>
              <ul className="skill-list areas">
                {skills.areas.map((s) => <SkillRow key={s.key} s={s} />)}
              </ul>
              {skills.areas.some((a) => a.weakest && a.weakest.length > 0) && (
                <p className="meta weakest">
                  Weakest:{' '}
                  {skills.areas.flatMap((a) => a.weakest ?? []).slice(0, 4).map((w, i) => (
                    <span key={w.label}>{i > 0 && ', '}<span lang="es">{w.label}</span> <span className="num">{w.correct}/{w.total}</span></span>
                  ))}
                </p>
              )}
            </>
          )}
          <p className="foot">
            Scored only from your own recent answers in each skill, once there are {skills?.min_answers ?? 8}. No CEFR level is guessed.
          </p>
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
