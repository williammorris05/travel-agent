import type { Changes } from './types.ts'

export const demoChanges = (kind: 'cheap' | 'adventure' | 'private'): Changes => ({
  origin: 'Chicago', dates: { mode: 'flexible', start: null, end: null }, nights: 2, adults: 1,
  budget: { amount: '500', currency: 'USD', basis: 'party', covers: ['transport', 'stay', 'activities', 'food', 'gear', 'fees'] },
  interests: [],
  controls: { savings: kind === 'cheap' ? 100 : 30, adventure: kind === 'cheap' ? 0 : 100, transit_tolerance: 100 },
  constraints: { private_room: kind === 'private', shared_room_allowed: kind !== 'private',
    camping_allowed: kind !== 'private', overnight_transport_allowed: false, max_exertion: null,
    accessibility: [], excluded_transport: [] },
})

export type Command = { kind: 'patch'; changes: Changes } | { kind: 'plan' } | {kind: 'activities'}
export const commandHelp = [
  '/budget 200', '/nights 3', '/adults 2', '/origin Chicago', '/dates 2027-06-01 2027-06-04',
  '/flexible 2', '/adventure 80', '/savings 100', '/time 90', '/private yes', '/shared yes',
  '/camping yes', '/overnight no', '/exertion low', '/interests nature, food', '/plan', '/activities',
]

export function parseCommand(text: string): Command {
  const [name, ...parts] = text.trim().split(/\s+/)
  const value = parts.join(' ')
  const patch = (changes: Changes): Command => ({ kind: 'patch', changes })
  const integer = (min: number, max: number) => {
    if (!/^\d+$/.test(value) || Number(value) < min || Number(value) > max) throw new Error(`Use a whole number from ${min} to ${max}.`)
    return Number(value)
  }
  if (name === '/plan' && !value) return { kind: 'plan' }
  if (name === '/activities' && !value) return { kind: 'activities' }
  if (name === '/budget' && /^\d+(\.\d{1,2})?$/.test(value)) return patch({ budget: { amount: value } })
  if (name === '/nights') return patch({ nights: integer(1, 60) })
  if (name === '/adults') return patch({ adults: integer(1, 2) })
  if (name === '/origin' && value) return patch({ origin: value })
  if (name === '/dates' && parts.length === 2 && parts.every(part => /^\d{4}-\d{2}-\d{2}$/.test(part))) {
    return patch({ dates: { mode: 'fixed', start: parts[0], end: parts[1] }, nights: null })
  }
  if (name === '/flexible') return patch({ dates: { mode: 'flexible', start: null, end: null }, nights: integer(1, 60) })
  const control = { '/adventure': 'adventure', '/savings': 'savings', '/time': 'transit_tolerance' }[name]
  if (control) return patch({ controls: { [control]: integer(0, 100) } })
  const constraint = { '/private': 'private_room', '/shared': 'shared_room_allowed', '/camping': 'camping_allowed', '/overnight': 'overnight_transport_allowed' }[name]
  if (constraint && ['yes', 'no', 'unknown'].includes(value)) return patch({ constraints: { [constraint]: value === 'unknown' ? null : value === 'yes' } })
  if (name === '/exertion' && ['low', 'moderate', 'high', 'unknown'].includes(value)) return patch({ constraints: { max_exertion: value === 'unknown' ? null : value } })
  if (name === '/interests' && value) return patch({ interests: value.split(',').map(item => item.trim()).filter(Boolean) })
  if (name === '/set') {
    try {
      const changes = JSON.parse(value)
      if (changes && typeof changes === 'object' && !Array.isArray(changes) && Object.keys(changes).length) return patch(changes)
    } catch { /* Report the supported syntax below. */ }
    throw new Error('Use /set followed by a JSON object of preference changes.')
  }
  throw new Error('Unknown command. Try /budget 200 or choose an example. Natural-language chat requires a configured model.')
}
