import { useCallback, useEffect, useState } from 'react'
import {
  api,
  ApiError,
  type Assessment,
  type Award,
  type GuidedLesson,
  type GuidedOverview,
  type GuidedUnit,
  type LessonSection,
  type UnitStatus,
} from './api'
import { QuizRunner } from './Assessment'
import Markdown from './Markdown'
import NewSession from './NewSession'

const STATUS_LABEL: Record<UnitStatus, string> = { new: 'Not started', started: 'Started', practicing: 'Practising', solid: 'Solid' }
/** Matches progress.WEAK on the server: below this a unit is flagged, not merely in progress. */
const WEAK = 0.7

function statusClass(unit: GuidedUnit): string {
  if (unit.status === 'solid') return 'strong'
  return unit.score !== null && unit.score < WEAK ? 'weak' : ''
}

const KIND_LABEL: Record<LessonSection['kind'], string> = {
  context: 'In context',
  grammar: 'Grammar',
  vocabulary: 'Vocabulary',
  reading: 'Reading',
  culture: 'Culture',
}

function StatusTag({ unit }: { unit: GuidedUnit }) {
  return (
    <span className={`strength ${statusClass(unit)}`}>
      {STATUS_LABEL[unit.status]}
      {unit.score !== null && <span className="num"> · {Math.round(unit.score * 100)}%</span>}
    </span>
  )
}

function UnitRow({ unit, suggested, onOpen }: { unit: GuidedUnit; suggested: boolean; onOpen: () => void }) {
  return (
    <li>
      <button className={`bank-row unit-row${unit.unlocked ? '' : ' locked'}`} onClick={onOpen}
        aria-describedby={suggested ? 'guided-suggestion' : undefined}>
        <span className="bank-head"><span className="unit-n num">{unit.n}</span> {unit.title}</span>
        <span className="bank-tr">{unit.summary}</span>
        <StatusTag unit={unit} />
        <span className="bank-meta">
          {suggested && <strong className="unit-next">Suggested next · </strong>}
          {!unit.unlocked && 'Earlier units first · '}
          {unit.tenses.length > 0 && <>{unit.tenses.join(', ')} · </>}
          {unit.has_lesson ? 'Lesson available' : 'Lesson not written yet'}
        </span>
      </button>
    </li>
  )
}

function Overview({ data, onOpen }: { data: GuidedOverview; onOpen: (id: string) => void }) {
  const next = data.suggestion && data.units.find((u) => u.id === data.suggestion!.unit_id)
  const solid = data.units.filter((u) => u.status === 'solid').length
  return (
    <>
      <header className="page-head">
        <h1>Guided study</h1>
        <p className="lede">
          A path through Spanish in the order learners tend to acquire it. Each unit pairs a short textbook lesson with
          practice built from your own words. Your self-study counts too.
        </p>
      </header>

      {next && (
        <section className="card guided-next" aria-labelledby="guided-next-title">
          <div className="card-head">
            <h2 id="guided-next-title">Up next</h2>
            <span className="cap num">{solid} of {data.units.length} units solid</span>
          </div>
          <p className="guided-next-title"><span className="unit-n num">{next.n}</span> {next.title}</p>
          <p className="meta" id="guided-suggestion">{data.suggestion!.reason}</p>
          <div className="actions">
            <button className="btn primary" onClick={() => onOpen(next.id)}>Open this unit</button>
          </div>
        </section>
      )}

      {data.stages.map((stage) => (
        <section key={stage.n} className="guided-stage" aria-labelledby={`stage-${stage.n}`}>
          <div className="card-head">
            <h2 id={`stage-${stage.n}`}>Stage {stage.n} · {stage.title}</h2>
            <span className="cap num">About {stage.lemma_target.toLocaleString()} words by the end</span>
          </div>
          <ul className="bank-list">
            {data.units.filter((u) => u.stage === stage.n).map((u) => (
              <UnitRow key={u.id} unit={u} suggested={u.id === data.suggestion?.unit_id} onOpen={() => onOpen(u.id)} />
            ))}
          </ul>
        </section>
      ))}

      {data.packs.length > 0 && (
        <p className="cap guided-packs">
          Lessons from {data.packs.map((p) => p.title).join(', ')}.
        </p>
      )}
    </>
  )
}

function Section({ section, open }: { section: LessonSection; open: boolean }) {
  return (
    <details className="card lesson-section" open={open}>
      <summary>
        <span className="cap">{KIND_LABEL[section.kind]}</span>
        <span className="lesson-section-title">{section.title.replace(/^(Gramática|Vocabulario|En contexto|Voces|Cultura)\s*:\s*/, '')}</span>
      </summary>
      <Markdown source={section.markdown} skipTitle headingOffset={1} />
      {(section.extra_attribution.length > 0 || section.license.code !== 'CC BY 4.0') && (
        <p className="cap lesson-credit">
          This section: {section.license.url ? <a href={section.license.url} target="_blank" rel="noreferrer">{section.license.code}</a> : section.license.code}
          {section.extra_attribution.length > 0 && <>. Includes material from {section.extra_attribution.join('; ').replace(/\*/g, '')}</>}.
        </p>
      )}
    </details>
  )
}

type Phase = { kind: 'lesson' } | { kind: 'log' } | { kind: 'quiz'; quiz: Assessment }

function savedMessage(a: Award): string {
  if (a.awarded_xp === 0) return 'Lesson saved. Practise it below.'
  return `Lesson saved: +${a.awarded_xp} XP. Practise it below.`
}

function Unit({ id, onBack, onOpenWord }: {
  id: string
  onBack: () => void
  onOpenWord: (entryId: number) => void
}) {
  const [data, setData] = useState<GuidedLesson | null>(null)
  const [pack, setPack] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const [notice, setNotice] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'lesson' })
  const [error, setError] = useState<{ message: string; needsLesson?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    api.guidedUnit(id, pack, controller.signal).then(setData).catch((err) => {
      if (err.name !== 'AbortError') setError({ message: err instanceof ApiError ? err.message : 'Could not load this unit.' })
    })
    return () => controller.abort()
  }, [id, pack, reload])

  async function practise() {
    setBusy(true)
    setError(null)
    try {
      setPhase({ kind: 'quiz', quiz: await api.unitQuiz(id) })
      window.scrollTo({ top: 0 })
    } catch (err) {
      setError({
        message: err instanceof ApiError ? err.message : 'Could not build a quiz for this unit.',
        needsLesson: err instanceof ApiError && err.status === 409,
      })
    }
    setBusy(false)
  }

  const back = <button className="btn ghost back" onClick={onBack}>← All units</button>
  if (!data) return error ? <>{back}<p className="error" role="alert">{error.message}</p></> : <p className="status">Loading…</p>
  const { unit, lesson } = data

  if (phase.kind === 'log') {
    return (
      <NewSession
        guided={{ unitId: unit.id, n: unit.n, title: unit.title, keyWords: unit.lemmas }}
        onCancel={() => setPhase({ kind: 'lesson' })}
        onSaved={(award) => {
          setNotice(savedMessage(award))
          setPhase({ kind: 'lesson' })
          setReload((n) => n + 1)
          window.scrollTo({ top: 0 })
        }}
      />
    )
  }
  if (phase.kind === 'quiz') {
    return (
      <QuizRunner quiz={phase.quiz} onChange={(q) => setPhase({ kind: 'quiz', quiz: q })} onDone={onBack}
        onOpenWord={onOpenWord} onAgain={practise} title={`Unit ${unit.n}`} />
    )
  }

  const actions = (
    <div className="actions">
      <button className="btn primary" onClick={() => setPhase({ kind: 'log' })}>Log this lesson</button>
      <button className="btn" onClick={practise} disabled={busy}>{busy ? 'Building your quiz…' : 'Practise this unit'}</button>
    </div>
  )

  return (
    <>
      <header className="page-head">
        {back}
        <p className="cap num">Unit {unit.n} · Stage {unit.stage}</p>
        <h1>{unit.title}</h1>
        <p className="lede">{unit.summary}</p>
        <p className="meta">
          <StatusTag unit={unit} />
          {unit.tenses.length > 0 && <> · Tenses: {unit.tenses.join(', ')}</>}
          {unit.lemmas.length > 0 && <> · Key words: <span lang="es">{unit.lemmas.join(', ')}</span></>}
        </p>
      </header>

      {notice && <p className="notice" role="status">{notice}</p>}
      {error && (
        <div className="error" role="alert">
          <p>{error.message}</p>
          {error.needsLesson && (
            <div className="actions"><button className="btn primary" onClick={() => setPhase({ kind: 'log' })}>Log this lesson</button></div>
          )}
        </div>
      )}

      {lesson ? (
        <>
          {data.other_packs.length > 0 && (
            <label className="field lesson-pack">
              <span>Lesson from</span>
              <select value={lesson.pack.id} onChange={(e) => setPack(e.target.value)}>
                <option value={lesson.pack.id}>{lesson.pack.title}</option>
                {data.other_packs.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </label>
          )}
          <div className="lesson">
            {lesson.sections.map((s, i) => (
              <Section key={s.path} section={s} open={i < 2 || s.kind === 'grammar'} />
            ))}
          </div>
          {actions}
          <p className="cap lesson-credit">
            From{' '}
            {lesson.pack.source_url ? <a href={lesson.pack.source_url} target="_blank" rel="noreferrer">{lesson.pack.title}</a> : lesson.pack.title}
            {'. '}
            {lesson.pack.attribution.replace(`${lesson.pack.title}`, '').replace(/^ by /, 'By ')}
          </p>
        </>
      ) : (
        <section className="card">
          <p>
            This unit’s lesson hasn’t been written yet: none of the installed textbooks cover it. You can still log your own
            study of it and practise its words.
          </p>
          {actions}
        </section>
      )}
    </>
  )
}

export default function Guided({ onOpenWord }: { onOpenWord: (entryId: number) => void }) {
  const [data, setData] = useState<GuidedOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)

  const load = useCallback((signal?: AbortSignal) => {
    api.guided(signal).then(setData).catch((err) => {
      if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load guided study.')
    })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  if (open) {
    return (
      <Unit key={open} id={open} onOpenWord={onOpenWord}
        onBack={() => {
          setOpen(null)
          load()
          window.scrollTo({ top: 0 })
        }} />
    )
  }
  if (error) return <p className="error" role="alert">{error}</p>
  if (!data) return <p className="status">Loading…</p>
  return <Overview data={data} onOpen={(id) => { setOpen(id); window.scrollTo({ top: 0 }) }} />
}
