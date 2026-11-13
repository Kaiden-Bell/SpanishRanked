import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { AssessmentItem } from './api'

const ACCENTS = ['á', 'é', 'í', 'ó', 'ú', 'ñ', 'ü', '¿', '¡']

type Props = {
  item: AssessmentItem
  busy: boolean
  speak: (text: string, slow?: boolean) => void
  onAnswer: (text: string) => void
}

function Listen({ text, speak }: { text: string; speak: Props['speak'] }) {
  useEffect(() => {
    speak(text)
    // Play once when the question appears; the buttons replay it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text])
  return (
    <div className="q-listen">
      <button type="button" className="btn" onClick={() => speak(text)}>▶ Play</button>
      <button type="button" className="btn ghost" onClick={() => speak(text, true)}>Slowly</button>
    </div>
  )
}

function TextAnswer({ item, busy, onAnswer }: Omit<Props, 'speak'>) {
  const [value, setValue] = useState('')
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null)
  const p = item.payload

  useEffect(() => ref.current?.focus(), [])

  function insert(ch: string) {
    const el = ref.current
    if (!el) return setValue((v) => v + ch)
    const start = el.selectionStart ?? value.length
    const end = el.selectionEnd ?? value.length
    const next = value.slice(0, start) + ch + value.slice(end)
    setValue(next)
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(start + ch.length, start + ch.length)
    })
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (value.trim()) onAnswer(value.trim())
  }

  const field = p.long ? (
    <textarea ref={ref} rows={2} maxLength={300} lang="es" value={value} disabled={busy}
      aria-label="Your sentence" onChange={(e) => setValue(e.target.value)} />
  ) : (
    <input ref={ref} maxLength={300} lang="es" value={value} disabled={busy} autoComplete="off"
      autoCapitalize="off" spellCheck={false} aria-label="Your answer" onChange={(e) => setValue(e.target.value)} />
  )

  return (
    <form onSubmit={submit} className="q-form">
      {p.cloze ? (
        <p className="q-cloze" lang="es">
          <span>{p.cloze.before}</span>
          {field}
          <span>{p.cloze.after}</span>
        </p>
      ) : (
        field
      )}
      <div className="accent-bar" role="group" aria-label="Insert a special character">
        {ACCENTS.map((ch) => (
          <button type="button" key={ch} onClick={() => insert(ch)} disabled={busy} aria-label={`Insert ${ch}`}>{ch}</button>
        ))}
      </div>
      <div className="actions">
        <button className="btn primary" type="submit" disabled={busy || !value.trim()}>{busy ? 'Checking…' : 'Check'}</button>
      </div>
    </form>
  )
}

function OrderAnswer({ item, busy, onAnswer }: Omit<Props, 'speak'>) {
  const tiles = item.payload.tiles ?? []
  const [picked, setPicked] = useState<number[]>([])
  const left = tiles.map((t, i) => ({ t, i })).filter(({ i }) => !picked.includes(i))
  return (
    <div className="q-form">
      <p className="tiles answer-row" lang="es" aria-label="Your sentence" aria-live="polite">
        {picked.length === 0 && <span className="cap">Tap the words in order.</span>}
        {picked.map((i, k) => (
          <button type="button" key={`${i}-${k}`} className="tile" disabled={busy}
            onClick={() => setPicked(picked.filter((x) => x !== i))} aria-label={`Remove ${tiles[i]}`}>{tiles[i]}</button>
        ))}
      </p>
      <p className="tiles" lang="es">
        {left.map(({ t, i }) => (
          <button type="button" key={i} className="tile" disabled={busy} onClick={() => setPicked([...picked, i])}>{t}</button>
        ))}
      </p>
      <div className="actions">
        <button className="btn primary" disabled={busy || left.length > 0} onClick={() => onAnswer(picked.map((i) => tiles[i]).join(' '))}>
          {busy ? 'Checking…' : 'Check'}
        </button>
        {picked.length > 0 && <button className="btn ghost" type="button" onClick={() => setPicked([])} disabled={busy}>Start over</button>}
      </div>
    </div>
  )
}

export default function Question({ item, busy, speak, onAnswer }: Props) {
  const p = item.payload
  return (
    <div className="q-body">
      <p className="q-prompt">{item.prompt}</p>
      {p.spanish && <p className="q-spanish" lang="es">{p.spanish}</p>}
      {p.tts && <Listen text={p.tts} speak={speak} />}
      {(p.hint || (p.translation && p.input !== 'choice')) && (
        <p className="q-hints">
          {p.hint && <span>Hint: <span lang={p.cloze && /^[a-zñáéíóú]+$/i.test(p.hint) ? 'es' : undefined}>{p.hint}</span></span>}
          {p.translation && <span>Meaning: “{p.translation}”</span>}
        </p>
      )}
      {p.input === 'choice' && (
        <div className="q-options" role="group" aria-label="Choices">
          {(p.options ?? []).map((o) => (
            <button key={o} className="q-option" disabled={busy} lang={p.options_lang} onClick={() => onAnswer(o)}>{o}</button>
          ))}
        </div>
      )}
      {p.input === 'text' && <TextAnswer key={item.id} item={item} busy={busy} onAnswer={onAnswer} />}
      {p.input === 'order' && <OrderAnswer key={item.id} item={item} busy={busy} onAnswer={onAnswer} />}
    </div>
  )
}
