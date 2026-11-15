/**
 * Which lesson lines to offer as audio. Lessons mix English explanation with Spanish dialogue,
 * vocabulary and examples, and a Spanish voice reading English is useless, so only lines that look
 * Spanish get a play button. A heuristic, tuned on the bundled pack; anything it misses can still be
 * heard by selecting it.
 */

const ES_WORDS = new Set(
  ('el la los las un una unos unas de del al que y o en es son está están por para con sin se me te le ' +
    'lo nos les mi mis tu tus su sus yo tú él ella usted nosotros nosotras vosotros ellos ellas ustedes ' +
    'muy pero como cómo qué quién dónde cuándo cuál hay soy eres estoy tengo tiene bien gracias hola ' +
    'sí no también este esta estos estas ese esa eso aquí allí más mucho mucha ya hoy')
    .split(' '),
)

const EN_WORDS = new Set(
  ('the and is are was were of to you your in on this that these those with for it its be as at by ' +
    'from or an a which what when where who how can do does not have has will would should their they ' +
    'we he she his her there here if but about into than then also used use means like i my name word words ' +
    'verb verbs sentence example examples following each all one two some more other')
    .split(' '),
)

// "a", "no", "me", "he" and "son" are words in both languages; they count for neither side.
const BOTH = new Set(['a', 'no', 'me', 'he', 'son'])

const WORD_RE = /[a-záéíóúüñ]+/gi

function words(text: string): string[] {
  return text.toLowerCase().match(WORD_RE) ?? []
}

/** A score per language: function words, plus Spanish spelling (accents, ñ, ¿ ¡, typical endings). */
function score(text: string): { es: number; en: number; n: number } {
  const ws = words(text)
  let es = /[¿¡]/.test(text) ? 2 : 0
  let en = 0
  for (const w of ws) {
    if (ES_WORDS.has(w) && !BOTH.has(w)) es += 1
    else if (EN_WORDS.has(w) && !BOTH.has(w)) en += 1
    else if (/[áéíóúñ]/.test(w)) es += 1
    else if (/(ción|mente|mos)$/.test(w) && w.length > 4) es += 1
    else if (/(dad|[aeiou]s|[ao]|ar|ir)$/.test(w) && w.length > 2) es += 0.5
    else if (/(ing|tion|ed|ly|th|ck|w)$/.test(w) || /[wk]/.test(w)) en += 0.5
  }
  return { es, en, n: ws.length }
}

export function looksSpanish(text: string): boolean {
  const { es, en, n } = score(text)
  if (n === 0 || n > 150) return false
  // A lone vocabulary word ("comprar", "ibas") carries a single weak signal.
  // Endings such as -er, -en, -se are too common in English to count inside a sentence.
  if (n <= 2 && en === 0) return es >= 0.5 || /(er|en|an|se|ron)$/i.test(text.trim().replace(/[^\p{L}]+$/u, ''))
  return es >= 1 && es > en * 1.5
}

function looksEnglish(text: string): boolean {
  const { es, en } = score(text)
  return en >= 1 && en >= es
}

// "**Juana**:", "Marta:", "Prof. Rivera:" at the start of a dialogue line.
const SPEAKER_RE = /^\s*(\*\*[^*]{1,30}\*\*|[A-ZÁÉÍÓÚÑ][\wáéíóúñ.]*(?: [A-ZÁÉÍÓÚÑ][\wáéíóúñ.]*){0,2})\s*:\s*/

/**
 * What to say for a line of lesson Markdown: no Markdown markers, list numbering, speaker label
 * ("**Juana**: ¡Hola!" says "¡Hola!") or English gloss in parentheses ("la mochila (*backpack*)").
 * A Spanish parenthesis such as "(yo)" in a conjugation table is kept.
 */
export function speakable(markdown: string): string {
  let t = markdown
    .replace(/\\([\\`*_{}[\]()#+\-.!|>])/g, '$1')
    .replace(/^\s*\d+\.\s*/, '')
    .replace(/`/g, '')
    .replace(/\s+Note:.*$/s, '') // "Te dije la fecha. Note: la fecha is the direct object."
  const label = SPEAKER_RE.exec(t)
  if (label && t.slice(label[0].length).trim()) t = t.slice(label[0].length)
  t = t
    .replace(/\(([^()]*)\)/g, (_, inner: string) => (looksSpanish(inner.replace(/\*/g, '')) ? inner : ' '))
    // An English gloss in italics without brackets: "**Me llamo…** *My name is…*".
    .replace(/(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)/g, (whole, inner: string) => (looksEnglish(inner) ? ' ' : whole))
  return t
    .replace(/\*/g, '')
    .replace(/[“”"]/g, '')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/\s+/g, ' ')
    .replace(/^[\s,;:–—-]+|[\s,;:–—-]+$/g, '')
    .trim()
}

/** The text to play for a block, or null when it shouldn't get a play button. */
export function spanishLine(markdown: string): string | null {
  if (/^\s*\**[^:*]{1,30}\**\s*:\s*\**\s*$/.test(markdown)) return null // a speaker or field label alone
  const said = speakable(markdown)
  return said && looksSpanish(said) ? said : null
}
