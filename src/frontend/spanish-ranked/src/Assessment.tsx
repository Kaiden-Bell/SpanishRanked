import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type Assessment as AssessmentData, type Outcome } from './api'

type Props = { onStudy: () => void; onDone: () => void }

const OUTCOME_LABEL: Record<Outcome, string> = { HIT: 'Correct', PARTIAL: 'Partly right', MISS: 'Missed' }

function OutcomeRow({ outcome, concept }: { outcome: Outcome; concept: string }) {
  return (
    <li className={`outcome ${outcome.toLowerCase()}`}>
      <span lang="es">{concept}</span>
      <span>{OUTCOME_LABEL[outcome]}</span>
    </li>
  )
}

export default function Assessment({ onStudy, onDone }: Props) {
  const [quiz, setQuiz] = useState<AssessmentData | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<'generating' | 'grading' | null>(null)
  const [error, setError] = useState<{ message: string; needsStudy?: boolean } | null>(null)

  // If the latest attempt was submitted but never graded (model was down), pick it up so its answers
  // are not stranded: the learner can retry grading from here.
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

  const fail = (err: unknown, fallback: string) =>
    setError({ message: err instanceof ApiError ? err.message : fallback, needsStudy: err instanceof ApiError && err.status === 409 })

  async function generate() {
    setBusy('generating')
    setError(null)
    try {
      setQuiz(await api.createAssessment())
      setAnswers({})
    } catch (err) {
      fail(err, 'Could not create a quiz.')
    }
    setBusy(null)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!quiz) return
    setBusy('grading')
    setError(null)
    try {
      setQuiz(await api.submitAssessment(quiz.id, quiz.items.map((i) => ({ item_id: i.id, text: (answers[i.id] ?? '').trim() }))))
    } catch (err) {
      // A repeat submit means the first one went through: show what is saved instead of an error.
      if (err instanceof ApiError && err.status === 409) setQuiz(await api.getAssessment(quiz.id).catch(() => quiz))
      else fail(err, 'Could not submit your answers.')
    }
    setBusy(null)
  }

  async function retry() {
    if (!quiz) return
    setBusy('grading')
    setError(null)
    try {
      setQuiz(await api.gradeAssessment(quiz.id))
    } catch (err) {
      fail(err, 'Could not grade the quiz.')
    }
    setBusy(null)
  }

  if (loading) return <p className="status">Loading…</p>

  const errorBox = error && (
    <div className="error" role="alert">
      <p>{error.message}</p>
      {error.needsStudy && (
        <div className="actions">
          <button className="btn primary" onClick={onStudy}>Start Study Session</button>
        </div>
      )}
    </div>
  )

  // ---------- start ----------
  if (!quiz) {
    return (
      <>
        <header className="page-head">
          <h1>Quick assessment</h1>
          <p className="lede">Three short prompts built from the words you logged. Write one Spanish sentence for each.</p>
        </header>
        {busy === 'generating' ? (
          <p className="status" role="status">Writing your quiz. This can take a little while on a local model…</p>
        ) : (
          <div className="actions">
            <button className="btn primary" onClick={generate}>Start quiz</button>
          </div>
        )}
        {errorBox}
      </>
    )
  }

  // ---------- answers saved, grading pending ----------
  if (quiz.status === 'SUBMITTED') {
    return (
      <>
        <header className="page-head">
          <h1>{busy === 'grading' ? 'Grading your answers…' : 'Grading is pending'}</h1>
          <p className="lede">
            {busy === 'grading'
              ? 'The local model is reading your sentences. This can take a minute.'
              : 'Your answers are saved. No XP is awarded until the quiz has been graded.'}
          </p>
        </header>
        {busy !== 'grading' && (
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

  // ---------- result ----------
  if (quiz.status === 'GRADED') {
    const total = quiz.items.length
    const award = quiz.award
    return (
      <>
        <header className="page-head">
          <h1>
            {quiz.correct} of {total} correct
          </h1>
          <p className="lede num">
            {award && award.awarded_xp > 0 && <>+{award.awarded_xp} XP{award.capped && ' (today’s quiz XP limit reached)'}</>}
            {award && award.awarded_xp === 0 && (award.base_xp === 0 && (quiz.correct ?? 0) > 0
              ? 'This quiz repeated one you already took, so it earned no XP.'
              : award.capped ? 'You have reached today’s quiz XP limit.' : 'No XP this time.')}
          </p>
        </header>
        {quiz.grammar_hints_unavailable && (
          <p className="notice" role="status">
            The grammar checker was unavailable for this quiz, so it was graded without its hints.
          </p>
        )}
        <ol className="quiz-list">
          {quiz.items.map((item) => (
            <li className="card quiz-item" key={item.id}>
              <p className="quiz-prompt">{item.prompt}</p>
              <blockquote className="quiz-answer" lang="es">{item.response_text}</blockquote>
              <ul className="outcomes" aria-label="Results">
                {item.evidence.map((e) => <OutcomeRow key={e.concept_token} outcome={e.outcome} concept={e.concept_token} />)}
              </ul>
              {item.feedback && <p className="quiz-feedback">{item.feedback}</p>}
            </li>
          ))}
        </ol>
        <div className="actions">
          <button className="btn primary" onClick={onDone}>Back to dashboard</button>
          <button className="btn" onClick={() => { setQuiz(null); setAnswers({}) }}>Take another</button>
        </div>
      </>
    )
  }

  // ---------- answering ----------
  const ready = quiz.items.every((i) => (answers[i.id] ?? '').trim().length > 0)
  return (
    <>
      <header className="page-head">
        <h1>Quick assessment</h1>
        <p className="lede">Write one Spanish sentence for each prompt, using the words shown. Answer from memory.</p>
      </header>
      <form className="form quiz-form" onSubmit={submit}>
        <ol className="quiz-list">
          {quiz.items.map((item) => (
            <li className="card quiz-item" key={item.id}>
              <label className="field">
                <span className="quiz-prompt">{item.prompt}</span>
                <ul className="tags" aria-label="Use these words">
                  {item.concepts.map((c) => <li key={c} lang="es">{c}</li>)}
                </ul>
                <textarea
                  rows={2}
                  maxLength={300}
                  lang="es"
                  value={answers[item.id] ?? ''}
                  onChange={(e) => setAnswers({ ...answers, [item.id]: e.target.value })}
                  disabled={busy === 'grading'}
                />
              </label>
            </li>
          ))}
        </ol>
        {busy === 'grading' && (
          <p className="status" role="status">Grading your answers. The local model can take a minute…</p>
        )}
        {errorBox}
        <div className="actions">
          <button className="btn primary" type="submit" disabled={!ready || busy === 'grading'}>
            {busy === 'grading' ? 'Grading…' : 'Submit answers'}
          </button>
        </div>
      </form>
    </>
  )
}
