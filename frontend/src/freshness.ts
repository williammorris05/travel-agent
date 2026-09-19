import type { Snapshot } from './types'

export function evidenceExpired(snapshot: Snapshot | null | undefined, now = Date.now()): boolean {
  return !!snapshot?.options.some(option => {
    const ttl = option.kind === 'hotel' ? 300000 : option.kind === 'activity' ? 30 * 86400000 : null
    return ttl !== null && [...option.costs.map(cost => cost.evidence), ...(option.supporting_evidence || [])].some(evidence => {
      const age = now - Date.parse(evidence.retrieved_at)
      return !Number.isFinite(age) || age < 0 || age > ttl
    })
  })
}
