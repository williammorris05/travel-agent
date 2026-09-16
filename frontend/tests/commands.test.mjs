import test from 'node:test'
import assert from 'node:assert/strict'
import { parseCommand, demoChanges } from '../src/commands.ts'
import { request, ApiError } from '../src/api.ts'

test('date correction explicitly clears a conflicting night count', () => {
  assert.deepEqual(parseCommand('/dates 2027-06-01 2027-06-04'), {kind:'patch', changes:{ dates:{mode:'fixed', start:'2027-06-01', end:'2027-06-04'}, nights:null }})
  assert.deepEqual(parseCommand('/flexible 3'), {kind:'patch',changes:{dates:{mode:'flexible',start:null,end:null},nights:3}})
})
test('cost and control commands only update their intended field', () => {
  assert.deepEqual(parseCommand('/budget 200.10'), {kind:'patch',changes:{budget:{amount:'200.10'}}})
  assert.deepEqual(parseCommand('/savings 100'), {kind:'patch',changes:{controls:{savings:100}}})
  assert.deepEqual(parseCommand('/private yes'), {kind:'patch',changes:{constraints:{private_room:true}}})
  assert.deepEqual(parseCommand('/camping unknown'), {kind:'patch',changes:{constraints:{camping_allowed:null}}})
})
test('plain chat and malformed commands are never guessed into preferences', () => {
  for (const text of ['make it cheap', '/budget NaN', '/adults 3', '/adventure 101', '/nights 2.5', '/private maybe', '/set []', '/set null', '/plan now']) assert.throws(() => parseCommand(text))
})
test('advanced patches preserve decimal strings, false and null for server validation', () => {
  assert.deepEqual(parseCommand('/set {"origin":null,"budget":{"amount":"0"},"constraints":{"camping_allowed":false}}'), {kind:'patch',changes:{origin:null,budget:{amount:'0'},constraints:{camping_allowed:false}}})
})
test('examples explicitly encode their different comfort permissions', () => {
  assert.equal(demoChanges('private').constraints.private_room, true)
  assert.equal(demoChanges('private').constraints.camping_allowed, false)
  assert.equal(demoChanges('cheap').constraints.shared_room_allowed, true)
  assert.equal(demoChanges('adventure').controls.adventure, 100)
})
test('API keeps revision data and exposes errors without substituting data', async t => {
  let seen
  t.mock.method(globalThis, 'fetch', async (url, options) => { seen={url,options}; return new Response('{"revision":3}', {status:200}) })
  assert.deepEqual(await request('/trips/one/preferences','PATCH',{expected_revision:2,changes:{adults:2}}), {revision:3})
  assert.equal(seen.url,'/api/trips/one/preferences')
  assert.equal(JSON.parse(seen.options.body).expected_revision,2)
  globalThis.fetch = async () => new Response('{"error":{"message":"Reload state"}}',{status:409})
  await assert.rejects(request('/trips/one'), error => error instanceof ApiError && error.status===409 && error.message==='Reload state')
  globalThis.fetch = async () => { throw new TypeError('offline') }
  await assert.rejects(request('/trips/one'), /Could not reach the service/)
})
