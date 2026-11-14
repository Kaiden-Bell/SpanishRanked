import { useEffect, useRef, useState, type ReactNode } from 'react'

const SHOW_MS = 10_000

/** One notice in the corner. Stays while hovered or focused, so it can be read and acted on. */
export default function Toast({ children, action, onClose }: {
  children: ReactNode
  action?: { label: string; onClick: () => void }
  onClose: () => void
}) {
  const [held, setHeld] = useState(false)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  })

  useEffect(() => {
    if (held) return
    const timer = setTimeout(() => close.current(), SHOW_MS)
    return () => clearTimeout(timer)
  }, [held])

  return (
    <div className="toast" role="status" aria-live="polite"
      onMouseEnter={() => setHeld(true)} onMouseLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)} onBlur={() => setHeld(false)}>
      <div className="toast-body">{children}</div>
      <div className="toast-actions">
        {action && <button className="btn primary" onClick={action.onClick}>{action.label}</button>}
        <button className="btn ghost toast-close" onClick={onClose} aria-label="Dismiss">×</button>
      </div>
    </div>
  )
}
