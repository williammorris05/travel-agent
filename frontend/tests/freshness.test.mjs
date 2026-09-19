import test from 'node:test'
import assert from 'node:assert/strict'
import { evidenceExpired } from '../src/freshness.ts'

test('live evidence expires by source age, synthetic trip prices do not', () => {
  const now = Date.now()
  const snapshot = (kind, age) => ({ options: [{ kind, costs: [{ evidence: { retrieved_at: new Date(now - age).toISOString() } }] }] })
  assert.equal(evidenceExpired(snapshot('hotel', 299000), now), false)
  assert.equal(evidenceExpired(snapshot('hotel', 301000), now), true)
  assert.equal(evidenceExpired(snapshot('activity', 31 * 86400000), now), true)
  assert.equal(evidenceExpired(snapshot('trip', 31 * 86400000), now), false)
  assert.equal(evidenceExpired(snapshot('hotel', -1000), now), true)
  assert.equal(evidenceExpired(null, now), false)
})
