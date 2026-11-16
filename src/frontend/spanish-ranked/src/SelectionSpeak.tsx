import { useEffect, useState, type RefObject } from 'react'

/** Longest selection read out: a paragraph or two, not a whole lesson. */
const MAX_CHARS = 600

type Spot = { text: string; top: number; left: number }

/**
 * Select any text inside `within` and a "Hear" button appears just below it, for the Spanish the
 * line buttons miss (a word inside an English explanation, say). Below rather than above, so it
 * doesn't sit under a phone's own copy/paste bar. Esc or an empty selection hides it.
 */
export default function SelectionSpeak({ within, speak }: { within: RefObject<HTMLElement | null>; speak: (text: string) => void }) {
  const [spot, setSpot] = useState<Spot | null>(null)

  useEffect(() => {
    function update() {
      const sel = document.getSelection()
      const root = within.current
      if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !root) return setSpot(null)
      const range = sel.getRangeAt(0)
      if (!root.contains(range.commonAncestorContainer)) return setSpot(null)
      const text = sel.toString().replace(/\s+/g, ' ').trim()
      if (!text || text.length > MAX_CHARS) return setSpot(null)
      const rect = range.getBoundingClientRect()
      if (rect.width === 0 && rect.height === 0) return setSpot(null)
      const left = Math.min(Math.max(rect.left + rect.width / 2, 48), window.innerWidth - 48)
      setSpot({ text, top: rect.bottom + 8, left })
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setSpot(null)
    }
    document.addEventListener('selectionchange', update)
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('selectionchange', update)
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
      document.removeEventListener('keydown', onKey)
    }
  }, [within])

  if (!spot) return null
  return (
    <button
      type="button"
      className="btn selection-speak"
      style={{ top: spot.top, left: spot.left }}
      // Keep the selection: a mousedown on the button would otherwise clear it before the click.
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => speak(spot.text)}
      aria-label={`Hear the selected text: ${spot.text}`}
    >
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.5v9l7-4.5z" /></svg>
      Hear
    </button>
  )
}
