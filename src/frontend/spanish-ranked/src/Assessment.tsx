import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type Assessment as AssessmentData, type Outcome, type QuizFocus } from './api'
import { OUTCOME_LABEL, SKILL_LABEL } from './labels'
import Question from './Question'
import { useSpanishVoice } from './speech'

const FOCUS: { value: QuizFocus; label: string; hint: string }[] = [
  { value: 'MIXED', label: 'Mixed', hint: 'Meanings, conjugations, sentences and listening' },
  { value: 'VOCABULARY', label: 'Vocabulary', hint: 'What words mean, both ways' },
  { value: 'GRAMMAR', label: 'Grammar', hint: 'Who and when, conjugating, word order' },
  { value: 'READING', label: 'Reading', hint: 'Understanding real sentences' },
  { value: 'LISTENING', label: 'Listening', hint: 'Hear it, pick it, type it' },
  { value: 'WRITING', label: 'Writing', hint: 'Typed answers and one free sentence' },
  { value: 'SENTENCES', label: 'Sentence practice', hint: 'Write your own sentences; the local model grades them' },
]

function OutcomePill({ outcome }: { outcome: Outcome }) {
  return <span className={`outcome ${outcome.toLowerCase()}`}>{OUTCOME_LABEL[outcome]}</span>
}

function awardLine(quiz: AssessmentData) {
  const award = quiz.award
  if (!award) return null
  if (award.awarded_xp > 0) return <>+{award.awarded_xp} XP{award.capped && ' (today’s limit reached)'}</>
  if (award.base_xp === 0 && (quiz.correct ?? 0) > 0) {
    return quiz.kind === 'WARMUP' ? 'Only the first warm-up of the day earns XP. It still counts toward your streak.' : 'This repeated a quiz you already took, so it earned no XP.'
  }
  return award.capped ? 'You have reached today’s XP limit for this.' : 'No XP this time.'
}

type RunnerProps = {
  quiz: AssessmentData
  onChange: (q: AssessmentData) => void
  onDone: () => void
  onAgain?: () => void
  onOpenWord?: (entryId: number) => void
  title?: string
}

/** Answers one question at a time: code-checked questions show their result straight away. */
export function QuizRunner({ quiz, onChange, onDone, onAgain, onOpenWord, title = 'Quiz' }: RunnerProps) {
  const { speak } = useSpanishVoice()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState<number | null>(null) // item whose feedback is showing
  const nextRef = useRef<HTMLButtonElement>(null)

  const total = quiz.items.length
  const pendingIndex = quiz.items.findIndex((i) => i.response_text === null)
  const shown = reviewing !== null ? quiz.items.find((i) => i.id === reviewing) : null

  useEffect(() => {
    if (shown) nextRef.current?.focus()
  }, [shown])

  async function answer(text: string) {
    const item = quiz.items[pendingIndex]
    setBusy(true)
    setError(null)
    try {
      const updated = await api.answerItem(quiz.id, item.id, text)
      onChange(updated)
      if (updated.status === 'GENERATED' || item.item_type !== 'WRITE') setReviewing(item.id)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) onChange(await api.getAssessment(quiz.id).catch(() => quiz))
      else setError(err instanceof ApiError ? err.message : 'Could not save your answer.')
    }
    setBusy(false)
  }

  async function retry() {
    setBusy(true)
    setError(null)
    try {
      onChange(await api.gradeAssessment(quiz.id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not grade the quiz.')
    }
    setBusy(false)
  }

  const errorBox = error && <p className="error" role="alert">{error}</p>

  // ---------- feedback for the question just answered ----------
  if (shown) {
    const last = pendingIndex === -1
    return (
      <>
        <header className="page-head">
          <p className="q-progress num">Question {quiz.items.indexOf(shown) + 1} of {total}</p>
        </header>
        <section className={`card q-card q-result ${shown.outcome?.toLowerCase() ?? 'saved'}`} aria-live="polite">
          <p className="q-prompt">{shown.prompt}</p>
          {shown.outcome ? <OutcomePill outcome={shown.outcome} /> : <span className="outcome partial">Saved</span>}
          <p className="q-your">You answered: <span lang="es">{shown.response_text}</span></p>
          {shown.feedback !== 'Correct.' && (
            <p className="quiz-feedback">{shown.feedback ?? 'Your sentence is graded when you finish the quiz.'}</p>
          )}
          <div className="actions">
            <button ref={nextRef} className="btn primary" onClick={() => setReviewing(null)}>
              {last ? 'See results' : 'Next question'}
            </button>
            {shown.entry_id && onOpenWord && shown.outcome && shown.outcome !== 'HIT' && (
              <button className="btn ghost" onClick={() => onOpenWord(shown.entry_id!)}>Open the word</button>
            )}
          </div>
        </section>
      </>
    )
  }

  // ---------- answering ----------
  if (quiz.status === 'GENERATED' && pendingIndex >= 0) {
    const item = quiz.items[pendingIndex]
    return (
      <>
        <header className="page-head">
          <p className="q-progress num">
            {title} · Question {pendingIndex + 1} of {total}
            <span className="q-skill">
              {item.stage ? `${item.stage.charAt(0) + item.stage.slice(1).toLowerCase()} stage` : SKILL_LABEL[item.skill] ?? item.skill}
            </span>
          </p>
          <div className="q-steps" aria-hidden="true">
            {quiz.items.map((i, k) => (
              <span key={i.id} className={`q-step ${i.outcome?.toLowerCase() ?? (i.response_text !== null ? 'saved' : k === pendingIndex ? 'now' : '')}`} />
            ))}
          </div>
        </header>
        <section className="card q-card">
          <Question key={item.id} item={item} busy={busy} speak={speak} onAnswer={answer} />
          {busy && item.item_type === 'WRITE' && pendingIndex === total - 1 && (
            <p className="status" role="status">Grading your sentence. The local model can take a little while…</p>
          )}
          {errorBox}
        </section>
      </>
    )
  }

  // ---------- answers saved, grading pending (the model was down) ----------
  if (quiz.status === 'SUBMITTED') {
    return (
      <>
        <header className="page-head">
          <h1>{busy ? 'Grading your answers…' : 'Grading is pending'}</h1>
          <p className="lede">
            {busy ? 'The local model is reading your sentences.' : 'Your answers are saved. No XP is awarded until the quiz has been graded.'}
          </p>
        </header>
        {!busy && (
          <>
            {quiz.grading_error && <p className="error" role="alert">{quiz.grading_error}</p>}
            <div className="actions">
              <button className="btn primary" onClick={retry}>Try grading again</button>
              <button className="btn ghost" onClick={onDone}>Back to dashboard</button>
            </div>
          </>
        )}
        {errorBox}
      </>
    )
  }

  // ---------- results ----------
  return (
    <>
      <header className="page-head">
        <h1>{quiz.correct} of {total} correct</h1>
        <p className="lede num">{awardLine(quiz)}</p>
      </header>
      {quiz.grammar_hints_unavailable && (
        <p className="notice" role="status">The grammar checker was unavailable, so your sentences were graded without its hints.</p>
      )}
      <ol className="quiz-list">
        {quiz.items.map((item) => (
          <li className="card quiz-item" key={item.id}>
            <div className="quiz-item-head">
              <span className="cap">{SKILL_LABEL[item.skill] ?? item.skill}</span>
              {item.outcome && <OutcomePill outcome={item.outcome} />}
            </div>
            <p className="quiz-prompt">{item.prompt}</p>
            {item.payload.spanish && <p className="q-spanish small" lang="es">{item.payload.spanish}</p>}
            {item.payload.cloze && (
              <p className="q-spanish small" lang="es">{item.payload.cloze.before}<span className="gap">___</span>{item.payload.cloze.after}</p>
            )}
            <blockquote className="quiz-answer" lang="es">{item.response_text}</blockquote>
            {item.feedback && item.feedback !== 'Correct.' && <p className="quiz-feedback">{item.feedback}</p>}
            {item.entry_id && onOpenWord && (
              <button className="linkish small" onClick={() => onOpenWord(item.entry_id!)}>
                Open <span lang="es">{item.concepts[0]}</span> in Words
              </button>
            )}
          </li>
        ))}
      </ol>
      <div className="actions">
        <button className="btn primary" onClick={onDone}>Back to dashboard</button>
        {onAgain && <button className="btn" onClick={onAgain}>Another quiz</button>}
      </div>
    </>
  )
}

type Props = { onStudy: () => void; onDone: () => void; onOpenWord: (entryId: number) => void }

export default function Assessment({ onStudy, onDone, onOpenWord }: Props) {
  const voice = useSpanishVoice()
  const [quiz, setQuiz] = useState<AssessmentData | null>(null)
  const [focus, setFocus] = useState<QuizFocus>('MIXED')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ message: string; needsStudy?: boolean } | null>(null)

  // A quiz whose answers were saved but never graded (the model was down) is picked up again here.
  useEffect(() => {
    const controller = new AbortController()
    api
      .listAssessments(0, 1, controller.signal)
      .then(async (page) => {
        if (page.items[0]?.status === 'SUBMITTED') setQuiz(await api.getAssessment(page.items[0].id, controller.signal))
      })
      .catch(() => {})
      .finally(() => !controller.signal.aborted && setLoading(false))
    return () => controller.abort()
  }, [])

  async function start() {
    setBusy(true)
    setError(null)
    try {
      setQuiz(await api.createAssessment({ focus, listening: voice.available }))
    } catch (err) {
      setError({
        message: err instanceof ApiError ? err.message : 'Could not create a quiz.',
        needsStudy: err instanceof ApiError && err.status === 409 && err.message.includes('study session'),
      })
    }
    setBusy(false)
  }

  if (loading) return <p className="status">Loading…</p>
  if (quiz) {
    return <QuizRunner quiz={quiz} onChange={setQuiz} onDone={onDone} onOpenWord={onOpenWord}
      onAgain={() => setQuiz(null)} />
  }

  const chosen = FOCUS.find((f) => f.value === focus)!
  return (
    <>
      <header className="page-head">
        <h1>Quiz</h1>
        <p className="lede">Five short questions from your word bank. Most are checked instantly; the words you miss come back sooner.</p>
      </header>
      <div className="form">
        <label className="field">
          <span>Practise</span>
          <select value={focus} onChange={(e) => setFocus(e.target.value as QuizFocus)}>
            {FOCUS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
        <p className="hint">{chosen.hint}.</p>
        {voice.checked && !voice.available && (
          <p className="hint">This browser has no Spanish voice, so quizzes here skip listening questions.</p>
        )}
        <div className="actions">
          <button className="btn primary" onClick={start} disabled={busy}>{busy ? 'Building your quiz…' : 'Start quiz'}</button>
        </div>
        {error && (
          <div className="error" role="alert">
            <p>{error.message}</p>
            {error.needsStudy && (
              <div className="actions">
                <button className="btn primary" onClick={onStudy}>Start Study Session</button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
