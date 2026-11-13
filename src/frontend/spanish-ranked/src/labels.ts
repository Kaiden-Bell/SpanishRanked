import type { Outcome } from './api'

export const OUTCOME_LABEL: Record<Outcome, string> = { HIT: 'Correct', PARTIAL: 'Partly right', MISS: 'Missed' }

export const SKILL_LABEL: Record<string, string> = {
  VOCABULARY: 'Vocabulary',
  GRAMMAR: 'Grammar',
  COMPREHENSION: 'Reading',
  LISTENING: 'Listening',
  WRITING: 'Writing',
}
