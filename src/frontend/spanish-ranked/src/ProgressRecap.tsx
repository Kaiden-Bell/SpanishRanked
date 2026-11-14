import type { CSSProperties } from 'react'
import type { QuizProgress, SkillSnapshot } from './api'

const pct = (v: number) => `${Math.round(v * 100)}%`

/** A bar whose fill grows from where it was before the quiz to where it is now (scaleX only). */
function DeltaBar({ from, to, label }: { from: number; to: number; label: string }) {
  const lo = Math.min(from, to)
  return (
    <span className="bar delta" role="img" aria-label={label}>
      <span className="fill gain" style={{ '--from': lo, '--w': to } as CSSProperties} />
      {to < from && <span className="fill loss" style={{ '--w': from } as CSSProperties} />}
      <span className="fill prior" style={{ '--w': lo } as CSSProperties} />
    </span>
  )
}

function skillText(before: SkillSnapshot, after: SkillSnapshot): string {
  if (after.status !== 'ASSESSED' || after.score === null) {
    return `${after.answers_needed} more ${after.answers_needed === 1 ? 'answer' : 'answers'} to assess`
  }
  if (before.status !== 'ASSESSED' || before.score === null) return `${pct(after.score)} · now assessed`
  const change = Math.round((after.score - before.score) * 100)
  return `${pct(after.score)} · ${change === 0 ? 'no change' : change > 0 ? `+${change}` : `${change}`}`
}

export default function ProgressRecap({ progress, onThemes }: { progress: QuizProgress; onThemes?: () => void }) {
  const { xp, skills, rank_up } = progress
  const span = xp.band_max !== null ? xp.band_max - xp.band_min : null
  const ratio = (v: number) => (span ? Math.min(1, Math.max(0, (v - xp.band_min) / span)) : 1)

  return (
    <section className="card recap-progress" aria-labelledby="rp">
      <div className="card-head">
        <h2 id="rp">Your progress</h2>
        <span className="cap num">{xp.gained > 0 ? `+${xp.gained} XP` : 'No XP this time'}</span>
      </div>

      {rank_up && (
        <div className="rank-up" role="status">
          <p><strong>Rank up: {rank_up.rank}.</strong> You won the boss battle.</p>
          {rank_up.theme && (
            <p>
              New theme unlocked: <strong>{rank_up.theme.label}</strong>.
              {onThemes && <> <button className="linkish" onClick={onThemes}>Try it in Settings</button></>}
            </p>
          )}
        </div>
      )}

      <div className="rp-xp">
        <DeltaBar from={ratio(xp.before)} to={ratio(xp.after)}
          label={xp.next_rank ? `${xp.after - xp.band_min} of ${span} XP toward ${xp.next_rank}` : 'Highest rank reached'} />
        <p className="meta num">
          {xp.next_rank && span !== null
            ? <>{Math.min(xp.after, xp.band_max!) - xp.band_min} / {span} XP to {xp.next_rank}</>
            : <>{xp.rank} · highest rank</>}
          {xp.boss_ready && <> · <strong>boss battle unlocked</strong></>}
        </p>
      </div>

      {skills.length > 0 && (
        <ul className="skill-list rp-skills">
          {skills.map((s) => {
            const assessed = s.after.status === 'ASSESSED' && s.after.score !== null
            const was = s.before.status === 'ASSESSED' && s.before.score !== null ? s.before.score : assessed ? s.after.score! : 0
            return (
              <li className="skill" key={s.key}>
                <span>{s.label}</span>
                {assessed ? (
                  <DeltaBar from={was} to={s.after.score!} label={`${s.label}: ${skillText(s.before, s.after)}`} />
                ) : (
                  <span className="bar empty-track" aria-hidden="true" />
                )}
                <span className="skill-val num">{skillText(s.before, s.after)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
