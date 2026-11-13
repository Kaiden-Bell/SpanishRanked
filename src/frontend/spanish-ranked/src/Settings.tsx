import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type UserSettings } from './api'
import { DEFAULT_RATE, useSpanishVoice } from './speech'

type Props = {
  onMotion: (motion: UserSettings['motion']) => void
  onReset: (message: string) => void
}

const LENGTHS = [3, 4, 5, 6, 7, 8, 10]
const SAMPLE = 'Hola. Te extraño mucho, y quiero volver pronto.'

function message(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.messages.join(' ') : fallback
}

function Saved({ show }: { show: boolean }) {
  return <span className="cap saved-flag" role="status">{show ? 'Saved' : ''}</span>
}

function PasswordForm() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) return setError('The new passwords do not match.')
    setBusy(true)
    setError(null)
    try {
      await api.changePassword(current, next)
      setCurrent('')
      setNext('')
      setConfirm('')
      setDone(true)
    } catch (err) {
      setError(message(err, 'Could not change the password.'))
    }
    setBusy(false)
  }

  return (
    <form onSubmit={submit} className="settings-form">
      <h3 className="sub">Change password</h3>
      <label className="field">
        <span>Current password</span>
        <input type="password" value={current} onChange={(e) => { setCurrent(e.target.value); setDone(false) }} autoComplete="current-password" required />
      </label>
      <div className="row2">
        <label className="field">
          <span>New password</span>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={12} maxLength={128} required />
        </label>
        <label className="field">
          <span>Confirm new password</span>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />
        </label>
      </div>
      <p className="hint">At least 12 characters. Changing it signs out your other devices.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {done && <p className="notice" role="status">Password changed. Other devices were signed out.</p>}
      <div className="actions">
        <button className="btn" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button>
      </div>
    </form>
  )
}

function SignOutOthers() {
  const [result, setResult] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function run() {
    setBusy(true)
    try {
      const r = await api.signOutOthers()
      setResult(r.signed_out === 0 ? 'No other devices were signed in.' : `Signed out ${r.signed_out} other ${r.signed_out === 1 ? 'device' : 'devices'}.`)
    } catch (err) {
      setResult(message(err, 'Could not sign out other devices.'))
    }
    setBusy(false)
  }
  return (
    <div className="settings-row">
      <div>
        <h3 className="sub">Other devices</h3>
        <p className="meta">End every sign-in except this one, for example a phone you lost or a shared computer.</p>
        {result && <p className="cap" role="status">{result}</p>}
      </div>
      <button className="btn" onClick={run} disabled={busy}>{busy ? 'Signing out…' : 'Sign out other devices'}</button>
    </div>
  )
}

function ResetAll({ onReset }: { onReset: Props['onReset'] }) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.resetAll(password, confirm)
      const d = r.deleted
      onReset(`All data was reset: ${d.study_sessions} study sessions, ${d.words} words and phrases and ${d.quizzes} quizzes deleted. You are starting fresh.`)
    } catch (err) {
      setError(message(err, 'Could not reset your data.'))
      setBusy(false)
    }
  }

  return (
    <section className="card settings-card danger" aria-labelledby="st-reset">
      <div className="card-head"><h2 id="st-reset">Reset all data</h2></div>
      <p className="meta">
        Deletes every study session, your word bank, all quizzes, warm-ups and boss battles, your XP, rank and streak.
        Your account, these settings and the downloaded dictionary data stay. <strong>This can’t be undone.</strong>
      </p>
      {!open ? (
        <div className="actions">
          <button className="btn danger-btn" onClick={() => setOpen(true)}>Reset all data…</button>
        </div>
      ) : (
        <form onSubmit={submit} className="settings-form">
          <div className="row2">
            <label className="field">
              <span>Your password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </label>
            <label className="field">
              <span>Type RESET to confirm</span>
              <input value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" spellCheck={false} required />
            </label>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="actions">
            <button className="btn danger-btn" type="submit" disabled={busy || confirm.trim() !== 'RESET' || !password}>
              {busy ? 'Deleting…' : 'Delete everything'}
            </button>
            <button className="btn ghost" type="button" onClick={() => { setOpen(false); setPassword(''); setConfirm(''); setError(null) }}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  )
}

export default function Settings({ onMotion, onReset }: Props) {
  const voice = useSpanishVoice()
  const [prefs, setPrefs] = useState<UserSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    api.settings(controller.signal).then(setPrefs).catch((err) => {
      if (err.name !== 'AbortError') setError(message(err, 'Could not load your settings.'))
    })
    return () => controller.abort()
  }, [])

  async function update(patch: Partial<UserSettings>, key: string) {
    if (!prefs) return
    setPrefs({ ...prefs, ...patch })
    setError(null)
    try {
      const next = await api.saveSettings(patch)
      setPrefs(next)
      if (patch.motion) onMotion(next.motion)
      setSaved(key)
      setTimeout(() => setSaved((k) => (k === key ? null : k)), 1800)
    } catch (err) {
      setError(message(err, 'Could not save that setting.'))
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>Settings</h1>
      </header>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="settings">
        <section className="card settings-card" aria-labelledby="st-practice">
          <div className="card-head"><h2 id="st-practice">Practice</h2></div>
          {!prefs ? <p className="status">Loading…</p> : (
            <>
              <div className="row2">
                <label className="field">
                  <span>Questions per quiz <Saved show={saved === 'quiz'} /></span>
                  <select value={prefs.quiz_items} onChange={(e) => update({ quiz_items: Number(e.target.value) }, 'quiz')}>
                    {LENGTHS.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Questions per warm-up <Saved show={saved === 'warmup'} /></span>
                  <select value={prefs.warmup_items} onChange={(e) => update({ warmup_items: Number(e.target.value) }, 'warmup')}>
                    {LENGTHS.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
              </div>
              <p className="hint">Sentence practice always has 3. A small word bank may give a shorter quiz: questions are never padded.</p>
              <label className="toggle">
                <input type="checkbox" checked={prefs.listening} onChange={(e) => update({ listening: e.target.checked }, 'listening')} />
                <span>
                  Listening questions <Saved show={saved === 'listening'} />
                  <span className="hint">Turn off if you practise where you can’t play sound. Boss battles then skip their listening stage.</span>
                </span>
              </label>
            </>
          )}

          <h3 className="sub">Spanish voice on this device</h3>
          {voice.checked && voice.voices.length === 0 ? (
            <p className="meta">This browser has no Spanish voice, so listening questions are skipped here. Installing a Spanish voice in your system settings, or another browser, adds one.</p>
          ) : (
            <>
              <div className="row2">
                <label className="field">
                  <span>Voice</span>
                  <select value={voice.voice?.voiceURI ?? ''} onChange={(e) => voice.setVoice(e.target.value || null)}>
                    {voice.voices.map((v) => <option key={v.voiceURI} value={v.voiceURI}>{v.name} ({v.lang})</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Speed: <span className="num">{voice.rate.toFixed(2)}×</span></span>
                  <input type="range" min={0.5} max={1.3} step={0.05} value={voice.rate}
                    onChange={(e) => voice.setRate(Number(e.target.value))} aria-valuetext={`${voice.rate.toFixed(2)} times`} />
                </label>
              </div>
              <div className="actions">
                <button className="btn" onClick={() => voice.speak(SAMPLE)}>▶ Play a sample</button>
                <button className="btn ghost" onClick={() => voice.speak(SAMPLE, true)}>Slowly</button>
                {voice.rate !== DEFAULT_RATE && <button className="btn ghost" onClick={() => voice.setRate(DEFAULT_RATE)}>Reset speed</button>}
              </div>
              <p className="hint">Kept on this device only, because each phone and browser offers different voices.</p>
            </>
          )}
        </section>

        <section className="card settings-card" aria-labelledby="st-motion">
          <div className="card-head"><h2 id="st-motion">Motion</h2></div>
          {prefs && (
            <div className="field">
              <span id="motion-label">Animations <Saved show={saved === 'motion'} /></span>
              <div className="seg" role="group" aria-labelledby="motion-label">
                <button type="button" aria-pressed={prefs.motion === 'system'} onClick={() => update({ motion: 'system' }, 'motion')}>Follow my device</button>
                <button type="button" aria-pressed={prefs.motion === 'reduce'} onClick={() => update({ motion: 'reduce' }, 'motion')}>Always reduce</button>
              </div>
              <p className="hint">“Always reduce” turns off progress-bar and hover animations on every device you sign in on.</p>
            </div>
          )}
        </section>

        <section className="card settings-card" aria-labelledby="st-account">
          <div className="card-head"><h2 id="st-account">Account</h2></div>
          <PasswordForm />
          <SignOutOthers />
        </section>

        <ResetAll onReset={onReset} />
      </div>
    </>
  )
}
