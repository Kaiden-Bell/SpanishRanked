import { useState, type FormEvent } from 'react'
import { api, ApiError, type User } from './api'

export default function ChangePassword({ onChanged }: { onChanged: (user: User) => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) return setError('The new passwords do not match.')
    setBusy(true)
    setError(null)
    try {
      onChanged(await api.changePassword(current, next))
    } catch (err) {
      setError(err instanceof ApiError ? err.messages.join(' ') : 'Something went wrong.')
      setBusy(false)
    }
  }

  return (
    <form className="panel form signin" onSubmit={submit}>
      <h1>Choose a new password</h1>
      <p className="hint">Replace the one-time password before you continue. Use at least 12 characters.</p>
      <label className="field">
        <span>Current (one-time) password</span>
        <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required />
      </label>
      <label className="field">
        <span>New password</span>
        <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={12} maxLength={128} required />
      </label>
      <label className="field">
        <span>Confirm new password</span>
        <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions">
        <button className="btn primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button>
      </div>
    </form>
  )
}
