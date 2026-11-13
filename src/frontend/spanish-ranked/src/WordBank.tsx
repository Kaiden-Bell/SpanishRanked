import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type BankDetail, type BankSummary, type Conjugation, type Strength } from './api'

const PAGE = 50

const STRENGTH_LABEL: Record<Strength, string> = {
  new: 'Not tested yet',
  weak: 'Needs practice',
  learning: 'Learning',
  strong: 'Strong',
}

type Kind = 'WORD' | 'PHRASE'
type Sort = 'recent' | 'alpha' | 'weak'

function when(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function LookupNote({ status, kind }: { status: BankSummary['lookup_status']; kind: BankSummary['kind'] }) {
  if (status === 'ok') return null
  const what = kind === 'PHRASE' ? 'translation' : 'dictionary meaning'
  const text = {
    pending: `Looking up the ${what}…`,
    offline: `Online lookups are turned off, so there is no ${what}. You can add your own translation.`,
    unavailable: `The dictionary could not be reached. It will try again later.`,
    not_found: `No ${what} was found. You can add your own translation.`,
  }[status]
  return <p className="cap" role="status">{text}</p>
}

export default function WordBank({ initialId, onStudy }: { initialId?: number | null; onStudy: () => void }) {
  const [openId, setOpenId] = useState<number | null>(initialId ?? null)
  if (openId !== null) return <WordDetail key={openId} id={openId} onBack={() => setOpenId(null)} onOpen={setOpenId} />
  return <WordList onOpen={setOpenId} onStudy={onStudy} />
}

function WordList({ onOpen, onStudy }: { onOpen: (id: number) => void; onStudy: () => void }) {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState<Kind>('WORD')
  const [counts, setCounts] = useState<{ WORD: number; PHRASE: number } | null>(null)
  const [sort, setSort] = useState<Sort>('recent')
  const [items, setItems] = useState<BankSummary[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)

  const params = { q: q.trim(), kind, sort } as const

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api
        .listBank({ ...params, limit: PAGE }, controller.signal)
        .then((page) => {
          setItems(page.items)
          setTotal(page.total)
          setCounts(page.counts)
          setError(null)
        })
        .catch((err) => {
          if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load your words.')
        })
    }, q ? 250 : 0)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, kind, sort])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const page = await api.listBank({ ...params, offset: items.length, limit: PAGE })
      setItems((prev) => [...prev, ...page.items])
      setTotal(page.total)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load more.')
    }
    setLoadingMore(false)
  }

  const filtering = q.trim() !== ''
  const empty = counts !== null && counts.WORD + counts.PHRASE === 0

  return (
    <>
      <header className="page-head">
        <h1>Words</h1>
        <p className="lede">Every word and phrase from your study sessions, with its meaning, the forms you met and how to conjugate it.</p>
      </header>

      <div className="bank-tabs" role="tablist" aria-label="Word bank">
        {(['WORD', 'PHRASE'] as Kind[]).map((k) => (
          <button key={k} role="tab" aria-selected={kind === k} className="bank-tab" onClick={() => setKind(k)}>
            {k === 'WORD' ? 'Words' : 'Phrases'}
            {counts && <span className="num"> {counts[k]}</span>}
          </button>
        ))}
      </div>

      <div className="bank-tools">
        <label className="field bank-search">
          <span>Search</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder={kind === 'WORD' ? 'A word, a form or a meaning' : 'Any word in a phrase, or its meaning'} maxLength={100} lang="es" />
        </label>
        <label className="field">
          <span>Order</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="recent">Recently studied</option>
            <option value="alpha">A to Z</option>
            <option value="weak">Needs practice first</option>
          </select>
        </label>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {total === null && !error && <p className="status">Loading…</p>}
      {empty && (
        <div className="empty">
          <p>Your word bank is empty. Words and phrases you log in a study session appear here.</p>
          <button className="btn primary" onClick={onStudy}>Start Study Session</button>
        </div>
      )}
      {total === 0 && !empty && (
        <p className="status">
          {filtering ? 'Nothing matches.' : kind === 'PHRASE'
            ? 'No phrases yet. Type a phrase as one term in a study session to keep it here as a whole.'
            : 'No words yet.'}
        </p>
      )}

      <ul className="bank-list">
        {items.map((e) => (
          <li key={e.id}>
            <button className="bank-row" onClick={() => onOpen(e.id)}>
              <span className="bank-head" lang="es">{e.headword}</span>
              <span className="bank-tr">
                {e.translation ?? <em>{e.lookup_status === 'pending' ? 'looking up…' : 'no meaning yet'}</em>}
              </span>
              <span className="bank-meta">
                {e.kind === 'PHRASE' ? 'Phrase' : e.pos ? e.pos.charAt(0) + e.pos.slice(1).toLowerCase() : 'Word'}
                {e.forms_seen.length > 0 && <> · seen as <span lang="es">{e.forms_seen.join(', ')}</span></>}
              </span>
              <span className={`strength ${e.strength}`}>{STRENGTH_LABEL[e.strength]}</span>
            </button>
          </li>
        ))}
      </ul>
      {total !== null && items.length < total && (
        <div className="actions">
          <button className="btn" onClick={loadMore} disabled={loadingMore}>{loadingMore ? 'Loading…' : 'Load more'}</button>
        </div>
      )}
    </>
  )
}

function ConjugationTable({ table }: { table: Conjugation }) {
  const [all, setAll] = useState(false)
  const seen = new Set(table.seen)
  const rows = all ? table.rows : table.rows.filter((r) => r.core)
  const persons = all ? table.persons : table.persons.filter((p) => p.key !== 'vos' && p.key !== 'vosotros')
  return (
    <section className="card word-section">
      <div className="card-head">
        <h2>Conjugation</h2>
        <button className="btn ghost" onClick={() => setAll(!all)} aria-pressed={all}>
          {all ? 'Main tenses only' : 'All tenses and persons'}
        </button>
      </div>
      <div className="conj-scroll" tabIndex={0} aria-label={`Conjugation of ${table.infinitive}`}>
        <table className="conj" lang="es">
          <thead>
            <tr>
              <th scope="col"><span className="sr">Tense</span></th>
              {persons.map((p) => <th scope="col" key={p.key} title={p.who}>{p.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.tense}>
                <th scope="row" lang="en">
                  {r.label}
                  <span className="conj-when">{r.when}</span>
                </th>
                {persons.map((p) => (
                  <td key={p.key}>
                    {(r.cells[p.key] ?? []).map((f) =>
                      seen.has(f) ? <mark key={f} title="You have met this form">{f}</mark> : <span key={f}>{f}</span>,
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="foot">
        Gerund <span lang="es">{table.gerund.join(', ')}</span> · past participle <span lang="es">{table.participle.join(', ')}</span>.
        {seen.size > 0 && ' Highlighted forms are ones you have logged.'}
      </p>
    </section>
  )
}

function WordDetail({ id, onBack, onOpen }: { id: number; onBack: () => void; onOpen: (id: number) => void }) {
  const [entry, setEntry] = useState<BankDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mine, setMine] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    let tries = 0
    let timer: ReturnType<typeof setTimeout>
    const load = () =>
      api
        .getBankEntry(id, controller.signal)
        .then((e) => {
          setEntry(e)
          setMine(e.user_translation ?? '')
          // The meaning is fetched in the background right after a session is saved; check back briefly.
          if (e.lookup_status === 'pending' && tries++ < 6) timer = setTimeout(load, 1500)
        })
        .catch((err) => {
          if (err.name !== 'AbortError') setError(err instanceof ApiError ? err.message : 'Could not load this word.')
        })
    load()
    window.scrollTo({ top: 0 })
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [id])

  async function save(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await api.patchBankEntry(id, { user_translation: mine.trim() })
      setEntry(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save.')
    }
    setSaving(false)
  }

  const back = <button className="btn ghost back" onClick={onBack}>← All words</button>
  if (error) return <>{back}<p className="error" role="alert">{error}</p></>
  if (!entry) return <>{back}<p className="status">Loading…</p></>

  const results = entry.stats.hits + entry.stats.partials + entry.stats.misses
  return (
    <>
      {back}
      <header className="page-head word-head">
        <h1 lang="es">{entry.headword}</h1>
        <p className="lede">
          {entry.translation ?? <em>No meaning yet</em>}
          <span className="word-kind">
            {entry.kind === 'PHRASE' ? 'Phrase' : entry.pos ? entry.pos.toLowerCase() : 'word'} · {STRENGTH_LABEL[entry.strength]}
          </span>
        </p>
        <LookupNote status={entry.lookup_status} kind={entry.kind} />
      </header>

      <div className="word-grid">
        <div className="word-main">
          {entry.breakdown.length > 0 && (
            <section className="card word-section">
              <div className="card-head"><h2>Word by word</h2></div>
              <ol className="breakdown">
                {entry.breakdown.map((w, i) => (
                  <li key={`${w.surface}-${i}`} className={w.pos === 'FUNCTION' || w.pos === 'ENGLISH' ? 'minor' : ''}>
                    <span className="form-word" lang="es">{w.surface}</span>
                    <div className="bd-body">
                      {w.entry_id ? (
                        <button className="linkish" onClick={() => onOpen(w.entry_id!)}>
                          <span lang="es">{w.lemma}</span>
                        </button>
                      ) : w.lemma !== w.surface ? <span lang="es">{w.lemma}</span> : null}
                      <span className="bd-tr">
                        {w.translation ?? (w.pos === 'FUNCTION' ? 'grammar word' : w.pos === 'ENGLISH' ? 'English' : 'meaning not looked up yet')}
                      </span>
                      {w.readings.slice(0, 2).map((a) => (
                        <span key={`${a.tense}-${a.person}`} className="bd-reading">
                          <strong>{a.summary}</strong>{a.who && <> · who: {a.who}</>}{a.when && <> · when: {a.when}</>}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {entry.forms.some((f) => f.analyses.length > 0 || f.meaning) && (
            <section className="card word-section">
              <div className="card-head"><h2>The form you met</h2></div>
              <ul className="form-list">
                {entry.forms.map((f) => (
                  <li key={f.form}>
                    <span className="form-word" lang="es">{f.form}</span>
                    {f.meaning && <span className="form-mine">Your note: “{f.meaning}”</span>}
                    {f.analyses.length === 0 ? (
                      <span className="cap">The dictionary form.</span>
                    ) : (
                      <ul className="form-readings">
                        {f.analyses.map((a) => (
                          <li key={`${a.tense}-${a.person}`}>
                            <strong>{a.summary}</strong>
                            {a.who && <> · <span>who: {a.who}</span></>}
                            {a.when && <> · <span>when: {a.when}</span></>}
                          </li>
                        ))}
                      </ul>
                    )}
                    {f.clitics.length > 0 && (
                      <span className="cap">With the pronoun{f.clitics.length > 1 ? 's' : ''} <span lang="es">{f.clitics.join(' + ')}</span> attached.</span>
                    )}
                    {f.also.length > 0 && <span className="cap">The same spelling is also a form of <span lang="es">{f.also.join(', ')}</span>.</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {entry.conjugation && <ConjugationTable table={entry.conjugation} />}

          {(entry.examples.length > 0 || entry.your_sentences.length > 0) && (
            <section className="card word-section">
              <div className="card-head"><h2>In sentences</h2></div>
              {entry.your_sentences.length > 0 && (
                <>
                  <h3 className="sub">Yours</h3>
                  <ul className="sentences" lang="es">
                    {entry.your_sentences.map((s) => <li key={s.sentence_text + s.session_id}>{s.sentence_text}</li>)}
                  </ul>
                </>
              )}
              {entry.examples.length > 0 && (
                <>
                  <h3 className="sub">Examples</h3>
                  <ul className="examples">
                    {entry.examples.map((x) => (
                      <li key={x.es}>
                        <span lang="es">{x.es}</span>
                        <span className="ex-en">{x.en}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}
        </div>

        <aside className="word-side">
          <form className="card word-section" onSubmit={save}>
            <div className="card-head"><h2>Your translation</h2></div>
            <label className="field">
              <span className="sr">Your translation</span>
              <input value={mine} onChange={(e) => setMine(e.target.value)} maxLength={200}
                placeholder={entry.translation ?? 'What it means to you'} />
            </label>
            <div className="actions">
              <button className="btn" type="submit" disabled={saving || mine.trim() === (entry.user_translation ?? '')}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              {saved && <span className="cap" role="status">Saved</span>}
            </div>
          </form>

          {entry.senses.length > 0 && (
            <section className="card word-section">
              <div className="card-head"><h2>Meanings</h2></div>
              {entry.senses.map((block) => (
                <div key={block.pos} className="sense-block">
                  <h3 className="sub">{block.pos}</h3>
                  <ol className="senses">{block.senses.map((s) => <li key={s.gloss}>{s.gloss}</li>)}</ol>
                </div>
              ))}
            </section>
          )}

          {(entry.words.length > 0 || entry.phrases.length > 0) && (
            <section className="card word-section">
              <div className="card-head"><h2>{entry.kind === 'PHRASE' ? 'Words in this phrase' : 'Phrases with it'}</h2></div>
              <ul className="link-list">
                {[...entry.words, ...entry.phrases].map((w) => (
                  <li key={w.id}>
                    <button className="linkish" onClick={() => onOpen(w.id)}>
                      <span lang="es">{w.headword}</span>
                      {w.translation && <span className="cap"> {w.translation}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="card word-section">
            <div className="card-head"><h2>Your history</h2></div>
            <p className="meta">
              Logged in {entry.sessions_count} {entry.sessions_count === 1 ? 'session' : 'sessions'}
              {entry.last_seen_at && <>, last on {when(entry.last_seen_at)}</>}.
            </p>
            <p className="meta">
              {results === 0
                ? 'Not tested in a quiz yet.'
                : `Quiz results: ${entry.stats.hits} correct, ${entry.stats.partials} partly right, ${entry.stats.misses} missed.`}
            </p>
            {entry.sessions.length > 0 && (
              <ul className="recent-list">
                {entry.sessions.slice(0, 5).map((s) => (
                  <li key={s.id}>
                    <span className="recent-terms">{s.context_text}</span>
                    <span className="recent-when">{when(s.created_at)} · {s.activity_type.toLowerCase()}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
      {entry.attribution.length > 0 && <p className="foot">{entry.attribution.join(' · ')}</p>}
    </>
  )
}
