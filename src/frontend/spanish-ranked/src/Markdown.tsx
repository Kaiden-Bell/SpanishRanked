import type { ReactNode } from 'react'
import { spanishLine } from './spanishText'

/**
 * The small Markdown subset content packs use: headings, paragraphs, nested lists, tables,
 * blockquotes, rules, **bold**, *italic*, `code`. Builds React elements only (never raw HTML), so
 * text from a user-installed pack cannot inject markup.
 *
 * Given `speak`, every paragraph, list item, quote and table cell that reads as Spanish gets a play
 * button (spanishText.ts decides which, and what is said).
 */

type Speak = (text: string) => void

function Play({ md, speak }: { md: string; speak?: Speak }) {
  if (!speak) return null
  const said = spanishLine(md)
  if (!said) return null
  return (
    <button type="button" className="md-play" aria-label={`Hear in Spanish: ${said}`} title="Hear in Spanish" onClick={() => speak(said)}>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.5v9l7-4.5z" /></svg>
    </button>
  )
}

type Block =
  | { t: 'h'; level: number; text: string }
  | { t: 'p'; text: string }
  | { t: 'hr' }
  | { t: 'quote'; lines: string[] }
  | { t: 'table'; rows: string[][] }
  | { t: 'list'; items: ListItem[]; ordered: boolean; start: number }

type ListItem = { text: string; children: { items: ListItem[]; ordered: boolean; start: number } | null }

const LIST_RE = /^(\s*)([-*+]|\d+\.)\s+(.*)$/

function parseList(lines: string[], from: number, indent: number): { list: { items: ListItem[]; ordered: boolean; start: number }; next: number } {
  const items: ListItem[] = []
  let ordered = false
  let start = 1
  let i = from
  while (i < lines.length) {
    const m = LIST_RE.exec(lines[i])
    if (!m) break
    const depth = m[1].length
    if (depth < indent) break
    if (depth > indent) {
      const last = items[items.length - 1]
      const sub = parseList(lines, i, depth)
      if (last) last.children = sub.list
      i = sub.next
      continue
    }
    if (items.length === 0) {
      ordered = /\d/.test(m[2])
      if (ordered) start = parseInt(m[2], 10) // a list interrupted by a table continues its numbering
    }
    items.push({ text: m[3], children: null })
    i++
  }
  return { list: { items, ordered, start }, next: i }
}

function splitRow(line: string): string[] {
  const cells: string[] = []
  let cur = ''
  const body = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  for (let i = 0; i < body.length; i++) {
    if (body[i] === '\\' && body[i + 1] === '|') {
      cur += '|'
      i++
    } else if (body[i] === '|') {
      cells.push(cur.trim())
      cur = ''
    } else cur += body[i]
  }
  cells.push(cur.trim())
  return cells
}

function parse(md: string): Block[] {
  const lines = md.replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line)
    if (h) {
      blocks.push({ t: 'h', level: h[1].length, text: h[2] })
      i++
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      blocks.push({ t: 'hr' })
      i++
    } else if (line.trimStart().startsWith('|')) {
      const rows: string[][] = []
      while (i < lines.length && lines[i].trimStart().startsWith('|')) {
        if (!/^\s*\|(\s*:?-{2,}:?\s*\|)+\s*$/.test(lines[i])) rows.push(splitRow(lines[i]))
        i++
      }
      blocks.push({ t: 'table', rows })
    } else if (line.startsWith('>')) {
      const quote: string[] = []
      while (i < lines.length && lines[i].startsWith('>')) quote.push(lines[i++].replace(/^>\s?/, ''))
      blocks.push({ t: 'quote', lines: quote })
    } else if (LIST_RE.test(line)) {
      const { list, next } = parseList(lines, i, LIST_RE.exec(line)![1].length)
      blocks.push({ t: 'list', ...list })
      i = next
    } else {
      const para: string[] = []
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|>|\s*\|)/.test(lines[i]) && !LIST_RE.test(lines[i])) para.push(lines[i++])
      blocks.push({ t: 'p', text: para.join('\n') })
    }
  }
  return blocks
}

/** **bold**, *italic*, `code`, backslash escapes and hard line breaks. */
function inline(text: string, key = 'i'): ReactNode[] {
  const out: ReactNode[] = []
  let buf = ''
  let n = 0
  const flush = () => {
    if (buf) out.push(buf)
    buf = ''
  }
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '\\' && i + 1 < text.length && /[\\`*_{}[\]()#+\-.!|>]/.test(text[i + 1])) {
      buf += text[++i]
      continue
    }
    if (c === '\n') {
      buf = buf.trimEnd()
      flush()
      out.push(<br key={`${key}-${n++}`} />)
      continue
    }
    const marker = text.startsWith('**', i) ? '**' : c === '*' ? '*' : c === '`' ? '`' : null
    if (marker) {
      const end = text.indexOf(marker, i + marker.length)
      // A marker only opens when it hugs its text: "* note" is a literal asterisk.
      if (end > i + marker.length && text[i + marker.length] !== ' ') {
        flush()
        const inner = text.slice(i + marker.length, end)
        const k = `${key}-${n++}`
        if (marker === '`') out.push(<code key={k}>{inner}</code>)
        else if (marker === '**') out.push(<strong key={k}>{inline(inner, k)}</strong>)
        else out.push(<em key={k}>{inline(inner, k)}</em>)
        i = end + marker.length - 1
        continue
      }
    }
    buf += c
  }
  flush()
  return out
}

function List({ items, ordered, start, k, speak }: { items: ListItem[]; ordered: boolean; start: number; k: string; speak?: Speak }) {
  const children = items.map((item, i) => (
    <li key={i}>
      {inline(item.text, `${k}-${i}`)}
      <Play md={item.text} speak={speak} />
      {item.children && <List {...item.children} k={`${k}-${i}`} speak={speak} />}
    </li>
  ))
  return ordered ? <ol start={start !== 1 ? start : undefined}>{children}</ol> : <ul>{children}</ul>
}

/** headingOffset shifts "##" in the source to a lower heading level so it nests under the page's own. */
export default function Markdown({ source, headingOffset = 1, skipTitle = false, speak }: {
  source: string
  headingOffset?: number
  skipTitle?: boolean
  speak?: Speak
}) {
  let blocks = parse(source)
  if (skipTitle && blocks[0]?.t === 'h' && blocks[0].level === 1) blocks = blocks.slice(1)
  return (
    <div className="md">
      {blocks.map((b, i) => {
        const k = `b${i}`
        switch (b.t) {
          case 'h': {
            const level = Math.min(6, b.level + headingOffset) as 1 | 2 | 3 | 4 | 5 | 6
            const H = `h${level}` as const
            return <H key={k}>{inline(b.text, k)}</H>
          }
          case 'hr':
            return <hr key={k} />
          case 'quote':
            return <blockquote key={k}>{inline(b.lines.join('\n'), k)}<Play md={b.lines.join(' ')} speak={speak} /></blockquote>
          case 'list':
            return <List key={k} items={b.items} ordered={b.ordered} start={b.start} k={k} speak={speak} />
          case 'table': {
            const [head, ...rows] = b.rows
            return (
              <div className="md-table" key={k}>
                <table>
                  <thead><tr>{head.map((c, j) => <th key={j}>{inline(c, `${k}h${j}`)}<Play md={c} speak={speak} /></th>)}</tr></thead>
                  <tbody>
                    {rows.map((r, ri) => <tr key={ri}>{r.map((c, j) => <td key={j}>{inline(c, `${k}r${ri}c${j}`)}<Play md={c} speak={speak} /></td>)}</tr>)}
                  </tbody>
                </table>
              </div>
            )
          }
          default:
            return <p key={k}>{inline(b.text, k)}<Play md={b.text.replace(/\n/g, ' ')} speak={speak} /></p>
        }
      })}
    </div>
  )
}
