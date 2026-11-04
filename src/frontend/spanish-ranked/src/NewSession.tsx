import { useState, type FormEvent } from 'react'
import { ACTIVITY_TYPES, api, ApiError, type Award, type StudySession } from './api'

const MAX_TERMS = 5
const MAX_SENTENCES = 3

const label = (s: string) => s.charAt(0) + s.slice(1).toLowerCase()

export default function NewSession({ onSaved }: { onSaved: (award: Award) => void }) {
  const [mode, setMode] = useState<StudySession['mode']>('SELF_STUDY')
  const [activity, setActivity] = useState<string>('READING')
  const [minutes, setMinutes] = useState('20')
  const [context, setContext] = useState('')
  const [terms, setTerms] = useState<string[]>(Array(MAX_TERMS).fill(''))
  const [sentences, setSentences] = useState<string[]>(Array(MAX_SENTENCES).fill(''))
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const setAt = (list: string[], set: (l: string[]) => void, i: number, v: string) =>
    set(list.map((x, j) => (j === i ? v : x)))

  async function submit(e: FormEvent) {
    e.preventDefault()
    const cleanTerms = terms.map((t) => t.trim()).filter(Boolean)
    const cleanSentences = sentences.map((s) => s.trim()).filter(Boolean)
    // The server is the authority; these checks just save a round trip.
    const problems: string[] = []
    if (cleanTerms.length < 3) problems.push('Enter at least 3 words or phrases.')
    if (cleanSentences.length < 2) problems.push('Write at least 2 sentences.')
    if (problems.length) return setErrors(problems)

    setBusy(true)
    setErrors([])
    try {
      const saved = await api.createSession({
        mode,
        activity_type: activity,
        duration_minutes: Number(minutes),
        context_text: context,
        terms: cleanTerms,
        sentences: cleanSentences,
      })
      onSaved(saved.award)
    } catch (err) {
      setErrors(err instanceof ApiError ? err.messages : ['Something went wrong.'])
      setBusy(false)
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h2>Log a study session</h2>

      <div className="row">
        <label>
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as StudySession['mode'])}>
            <option value="SELF_STUDY">Self-study</option>
            <option value="GUIDED_STUDY">Guided study</option>
          </select>
        </label>
        <label>
          Activity
          <select value={activity} onChange={(e) => setActivity(e.target.value)}>
            {ACTIVITY_TYPES.map((a) => (
              <option key={a} value={a}>{label(a)}</option>
            ))}
          </select>
        </label>
        <label>
          Minutes
          <input type="number" min={1} max={1440} step={1} value={minutes} onChange={(e) => setMinutes(e.target.value)} required />
        </label>
      </div>

      <label>
        What did you study?
        <textarea value={context} onChange={(e) => setContext(e.target.value)} maxLength={2000} rows={3} required
          placeholder="e.g. Read a news article about travel" />
      </label>

      <fieldset>
        <legend>Words or phrases you learned (3–5)</legend>
        {terms.map((t, i) => (
          <input key={i} value={t} maxLength={100} aria-label={`Word or phrase ${i + 1}`}
            onChange={(e) => setAt(terms, setTerms, i, e.target.value)} />
        ))}
      </fieldset>

      <fieldset>
        <legend>Your own sentences in Spanish (2–3)</legend>
        {sentences.map((s, i) => (
          <input key={i} value={s} maxLength={300} aria-label={`Sentence ${i + 1}`}
            onChange={(e) => setAt(sentences, setSentences, i, e.target.value)} />
        ))}
      </fieldset>

      {errors.length > 0 && (
        <ul className="bad errors" role="alert">
          {errors.map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
      <button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save session'}</button>
    </form>
  )
}
