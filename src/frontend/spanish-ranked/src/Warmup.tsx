import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type Assessment } from './api'
import { QuizRunner } from './Assessment'
import { useSpanishVoice } from './speech'

/** Today's warm-up: built from due and weak words, checked instantly, no model needed. */
export default function Warmup({ onDone, onStudy, onOpenWord }: { onDone: () => void; onStudy: () => void; onOpenWord: (id: number) => void }) {
  const voice = useSpanishVoice()
  const [quiz, setQuiz] = useState<Assessment | null>(null)
  const [error, setError] = useState<{ message: string; needsStudy: boolean } | null>(null)
  const started = useRef(false)

  useEffect(() => {
    // Wait until we know whether there is a Spanish voice, then build the warm-up once.
    if (!voice.checked || started.current) return
    started.current = true
    api.createWarmup(voice.available).then(setQuiz).catch((err) =>
      setError({
        message: err instanceof ApiError ? err.message : 'Could not start the warm-up.',
        needsStudy: err instanceof ApiError && err.status === 409,
      }),
    )
  }, [voice.checked, voice.available])

  if (error)
    return (
      <div className="error" role="alert">
        <p>{error.message}</p>
        <div className="actions">
          {error.needsStudy && <button className="btn primary" onClick={onStudy}>Start Study Session</button>}
          <button className="btn ghost" onClick={onDone}>Back to dashboard</button>
        </div>
      </div>
    )
  if (!quiz) return <p className="status">Building your warm-up…</p>
  return <QuizRunner quiz={quiz} onChange={setQuiz} onDone={onDone} onOpenWord={onOpenWord} title="Warm-up" />
}
