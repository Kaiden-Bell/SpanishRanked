import type { LookupPreview } from './api'

/** One line under a term box: its dictionary form, meaning and grammar, or a warning that it is English. */
export function PreviewChip({ preview }: { preview: LookupPreview | null }) {
  if (!preview) return null
  const word = preview.words[0]
  let chip
  if (preview.english_only) {
    chip = <span className="term-warn">That looks like English, so it won’t be added to your words. Type the Spanish, and add the meaning after a dash: <span lang="es">extrañar</span> - to miss</span>
  } else if (preview.kind === 'PHRASE') {
    chip = <>
      {preview.meaning ? <>Your meaning: “{preview.meaning}”</> : preview.translation && <>“{preview.translation}”</>}
      {preview.words.length > 0 && <> · words: <span lang="es">{preview.words.map((w) => w.lemma).join(', ')}</span></>}
    </>
  } else if (word && (word.translation || word.lemma !== word.surface || word.forms.length || preview.meaning)) {
    chip = (
      <>
        {word.lemma !== word.surface && <strong lang="es">{word.lemma}</strong>}
        {word.lemma !== word.surface && (word.translation || preview.meaning) && ' · '}
        {preview.meaning ? <>your meaning “{preview.meaning}”</> : word.translation}
        {word.forms[0] && word.forms[0].person_label && <> · {word.forms[0].summary}</>}
      </>
    )
  }
  return chip ? <span className="term-chip" aria-live="polite">{chip}</span> : null
}
