import { useEffect, useState } from 'react'

/** The browser's own text-to-speech, used for listening questions. Nothing is sent anywhere by the app;
 * some browsers use an online voice, which is their choice. Without a Spanish voice, the quiz simply
 * asks for no listening questions.
 *
 * Voice and speed are kept per device (Settings › Practice): the voices on offer differ between
 * phones, laptops and browsers, so this is a per-viewer convenience in localStorage. */

const VOICE_KEY = 'languageai.voice'
const RATE_KEY = 'languageai.rate'
export const DEFAULT_RATE = 0.9

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* private mode: the choice lasts for this visit */
  }
}

export function spanishVoices(): SpeechSynthesisVoice[] {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return []
  return window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith('es'))
}

function pick(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const chosen = read(VOICE_KEY)
  return (
    voices.find((v) => v.voiceURI === chosen) ??
    voices.find((v) => /es-(ES|MX|US)/i.test(v.lang) && v.localService) ??
    voices[0] ??
    null
  )
}

function storedRate(): number {
  const r = Number(read(RATE_KEY))
  return r >= 0.5 && r <= 1.3 ? r : DEFAULT_RATE
}

export function useSpanishVoice() {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(() => spanishVoices())
  const [voice, setVoiceState] = useState<SpeechSynthesisVoice | null>(() => pick(spanishVoices()))
  const [rate, setRateState] = useState(storedRate)
  const [checked, setChecked] = useState(() => !('speechSynthesis' in window) || spanishVoices().length > 0)

  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const update = () => {
      const list = spanishVoices()
      setVoices(list)
      setVoiceState(pick(list))
      setChecked(true)
    }
    window.speechSynthesis.addEventListener('voiceschanged', update)
    // Some browsers never fire voiceschanged when the list is already loaded or empty.
    const timer = setTimeout(update, 1200)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', update)
      clearTimeout(timer)
    }
  }, [])

  function speak(text: string, slow = false, override?: { voice?: SpeechSynthesisVoice | null; rate?: number }) {
    const v = override?.voice ?? voice
    if (!v) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.voice = v
    u.lang = v.lang
    const base = override?.rate ?? rate
    u.rate = slow ? Math.max(0.4, base * 0.65) : base
    window.speechSynthesis.speak(u)
  }

  function setVoice(uri: string | null) {
    write(VOICE_KEY, uri)
    setVoiceState(voices.find((v) => v.voiceURI === uri) ?? pick(voices))
  }

  function setRate(r: number) {
    write(RATE_KEY, String(r))
    setRateState(r)
  }

  return { available: voice !== null, checked, speak, voices, voice, rate, setVoice, setRate }
}
