export const MAX_ANSWER_ENTITIES = 5
export const MAX_ANSWER_EVIDENCE = 12
export const MAX_ANSWER_CITATIONS = 5

export function shouldCallModel(evidenceCount: number): boolean {
  return evidenceCount > 0
}
