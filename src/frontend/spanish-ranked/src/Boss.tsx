import { useEffect, useState } from 'react'
import { api, ApiError, type Assessment, type BossState } from './api'
import { QuizRunner } from './Assessment'
import { useSpanishVoice } from './speech'

const STAGES = [
  ['Listening', 'hear a word or sentence and pick or type it'],
  ['Reading', 'understand real Spanish sentences'],
  ['Grammar', 'who and when, conjugating, word order'],
  ['Writing', 'a short real-life message, graded by the local model'],
]

function pct(x: number) {
  return `${Math.round(x * 100)}%`
}

function time(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

function Outcome({ state, onPractice }: { state: BossState; onPractice: () => void }) {
  const r = state.latest
  if (!r) return null
  const won = r.status === 'PASSED'
  return (
    <section className={`card boss-result ${won ? 'won' : 'lost'}`} aria-live="polite">
      <h2>{won ? `You are now ${r.rank}` : `Not this time`}</h2>
      <p className="meta">
        {won
          ? 'Every stage passed. Your new rank is on the dashboard.'
          : `Each stage needs ${pct(r.stage_pass)} and the whole battle ${pct(r.overall_pass)}. Your missed words are back in your review queue.`}
      </p>
      <ul className="boss-stages">
        {r.stages.map((s) => (
          <li key={s.key} className={s.passed ? 'passed' : 'failed'}>
            <span>{s.label}</span>
            <span className="num">{s.correct}/{s.total} · {pct(s.score)}</span>
            <span>{s.passed ? 'Passed' : 'Not yet'}</span>
          </li>
        ))}
        {r.skipped.map((s) => (
          <li key={s.key} className="skipped">
            <span>{s.label}</span>
            <span>Skipped: {s.reason}</span>
            <span />
          </li>
        ))}
      </ul>
      {!won && r.cooldown_until && (
        <div className="actions">
          <p className="cap">You can try again after {time(r.cooldown_until)}.</p>
          <button className="btn" onClick={onPractice}>Warm up on what you missed</button>
        </div>
      )}
    </section>
  )
}

export default function Boss({ onDone, onPractice, onOpenWord }: { onDone: () => void; onPractice: () => void; onOpenWord: (id: number) => void }) {
  const voice = useSpanishVoice()
  const [state, setState] = useState<BossState | null>(null)
  const [quiz, setQuiz] = useState<Assessment | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    api.boss(controller.signal).then(setState).catch((err) => {
      if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load the boss battle.')
    })
    return () => controller.abort()
  }, [])

  const graded = quiz?.status === 'GRADED'
  useEffect(() => {
    if (graded) api.boss().then(setState).catch(() => {})
  }, [graded])

  async function begin() {
    setBusy(true)
    setError(null)
    try {
      const r = await api.startBoss(voice.available)
      setState(r.boss)
      setQuiz(r.assessment)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start the boss battle.')
    }
    setBusy(false)
  }

  if (quiz) {
    return (
      <>
        {graded && state && <Outcome state={state} onPractice={onPractice} />}
        <QuizRunner quiz={quiz} onChange={setQuiz} onDone={onDone} onOpenWord={onOpenWord} title="Boss battle" />
      </>
    )
  }
  if (!state) return error ? <p className="error" role="alert">{error}</p> : <p className="status">Loading…</p>

  return (
    <>
      <header className="page-head">
        <h1>{state.rank ? `Boss battle: ${state.rank}` : 'Boss battle'}</h1>
        <p className="lede">
          You have the XP for the next rank. Win this battle to earn it. Each stage tests a different skill, using words from your own bank.
        </p>
      </header>
      <section className="card boss-intro">
        <ol className="boss-stage-list">
          {STAGES.map(([name, what]) => (
            <li key={name}><strong>{name}</strong> · {what}</li>
          ))}
        </ol>
        <p className="meta">To win: at least 60% in every stage and 70% overall. If you lose, the words you missed come back in your warm-ups, and you can try again after a short rest.</p>
        {voice.checked && !voice.available && <p className="hint">This browser has no Spanish voice, so the listening stage will be skipped.</p>}
        {state.status === 'COOLDOWN' && state.cooldown_until && <p className="meta">The boss is resting until {time(state.cooldown_until)}.</p>}
        {state.status === 'NEEDS_WORDS' && <p className="meta">Log {state.words_needed} more words to unlock this battle.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="actions">
          {(state.status === 'READY' || state.status === 'IN_PROGRESS') && (
            <button className="btn primary" onClick={begin} disabled={busy}>
              {busy ? 'Preparing…' : state.status === 'IN_PROGRESS' ? 'Continue the battle' : 'Begin'}
            </button>
          )}
          {state.status === 'COOLDOWN' && <button className="btn primary" onClick={onPractice}>Warm up on what you missed</button>}
          <button className="btn ghost" onClick={onDone}>Back to dashboard</button>
        </div>
      </section>
    </>
  )
}
