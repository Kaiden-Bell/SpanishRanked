import { useEffect, useState } from 'react'
import { api, type LookupPreview } from './api'

/** What a typed term means, looked up a moment after typing stops. Advisory only: saving never waits for it. */
export function useTermPreview(value: string, delay = 600): LookupPreview | null {
  const [result, setResult] = useState<{ term: string; preview: LookupPreview } | null>(null)
  const term = value.trim()

  useEffect(() => {
    if (term.length < 2) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api.lookup(term, controller.signal).then((p) => setResult({ term, preview: p })).catch(() => {})
    }, delay)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [term, delay])

  return result?.term === term ? result.preview : null
}
