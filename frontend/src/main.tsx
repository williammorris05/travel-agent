import { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ApiError, request } from './api'
import { commandHelp, demoChanges, parseCommand } from './commands'
import { PreferenceControls } from './Controls'
import { money, Results } from './Results'
import { evidenceExpired } from './freshness'
import type { Changes, Controls, Health, Trip } from './types'
import './styles.css'

type Message = { role: 'you' | 'guide'; text: string }
const emptyControls: Controls = { adventure: null, savings: null, transit_tolerance: null }
const storageKey = 'travel-agent-trip'
const missingLabels: Record<string, string> = { origin: 'departure city', dates: 'dates or flexibility', adults: 'number of adults', budget: 'budget', nights: 'number of nights', 'budget.basis': 'whether the budget is per person or for the party', 'budget.covers': 'what your budget covers' }
const intro: Message = { role: 'guide', text: 'What kind of vacation do you have in mind? Choose a sample trip to explore the demo, then refine it with the controls or commands below.' }

function rememberedId() { try { return sessionStorage.getItem(storageKey) } catch { return null } }
function remember(id: string) { try { sessionStorage.setItem(storageKey, id) } catch { /* In-memory state still works. */ } }

function App() {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer) }, [])
  const [trip, setTrip] = useState<Trip | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [busy, setBusy] = useState('Connecting…')
  const locked = useRef(false)
  const current = useRef<Trip | null>(null)
  const [problem, setProblem] = useState('')
  const [needsReload, setNeedsReload] = useState(false)
  const [expired, setExpired] = useState(false)
  const [messages, setMessages] = useState<Message[]>([intro])
  const [input, setInput] = useState('')
  const [dirty, setDirty] = useState<Record<string, boolean>>({})
  const [controlEpoch, setControlEpoch] = useState(0)
  const [announcement, setAnnouncement] = useState('')
  const composer = useRef<HTMLTextAreaElement>(null)
  const transcript = useRef<HTMLDivElement>(null)
  const restoreFocus = useRef<string | null>(null)
  useEffect(() => { if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight }, [messages])
  useEffect(() => {
    if (!busy && restoreFocus.current) {
      const target = document.getElementById(restoreFocus.current)
      if (document.activeElement === document.body || document.activeElement?.id === restoreFocus.current) target?.focus()
      restoreFocus.current = null
    }
  }, [busy])
  const save = (next: Trip) => { current.current = next; setTrip(next); remember(next.id) }
  const say = (text: string, role: Message['role'] = 'guide') => setMessages(previous => [...previous, { role, text }])

  async function run(label: string, action: () => Promise<void>) {
    if (locked.current) return
    if (document.activeElement?.id) restoreFocus.current = document.activeElement.id
    locked.current = true; setBusy(label); setProblem('')
    try { await action() }
    catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setExpired(true); setNeedsReload(true)
        setProblem('This trip is no longer available. The local server may have restarted. Start a new trip to continue.')
      } else if (error instanceof ApiError && error.status === 409) {
        setNeedsReload(true)
        setProblem('Your trip changed elsewhere. Reload trip state, review the preferences, then try the change again.')
      } else {
        if (!(error instanceof ApiError) || error.status >= 500) setNeedsReload(true)
        setProblem(error instanceof ApiError && error.status === 422
          ? 'That change could not be saved. Check the command, date order, nights and budget details; your saved preferences are unchanged.'
          : error instanceof Error ? error.message : 'The request failed. Please retry.')
      }
      setControlEpoch(value => value + 1)
    } finally { locked.current = false; setBusy(''); setDirty({}) }
  }

  async function connect() {
    await run('Connecting…', async () => {
      const status = await request<Health>('/health'); setHealth(status)
      if (status.data_mode === 'fixture' && !status.planning_available) throw new Error('The backend is running an older version. Restart it to load the trip planner.')
      const id = current.current?.id || rememberedId()
      const restored = id ? await request<Trip>(`/trips/${id}`) : await request<Trip>('/trips', 'POST', {})
      save(restored)
      if (restored.messages?.length) setMessages(restored.messages.map(item => ({ role: item.role === 'user' ? 'you' : 'guide', text: item.text })))
      else if (status.chat_available) setMessages([{role:'guide', text: status.data_mode === 'live' ? 'Tell me your dates, number of adults and budget. This pilot searches hotel prices in Milwaukee; other trip costs remain unknown.' : 'What kind of vacation do you have in mind? Tell me your departure city, timing and budget, and I’ll help compare synthetic trip options.'}])
      setNeedsReload(false); setExpired(false); setControlEpoch(value => value + 1)
      setAnnouncement('Trip state loaded.')
    })
  }
  useEffect(() => { void connect() }, [])

  async function patch(changes: Changes, source: 'chat' | 'slider' | 'form') {
    const state = current.current
    if (!state) throw new Error('Connect to the service first.')
    const next = await request<Trip>(`/trips/${state.id}/preferences`, 'PATCH', { expected_revision: state.revision, source, changes })
    save(next); setControlEpoch(value => value + 1)
    setAnnouncement('Preferences saved. Update options to use them.')
    return next
  }
  async function generate() {
    const state = current.current
    if (!state) return
    const next = await request<Trip>(`/trips/${state.id}/plan`, 'POST', { expected_revision: state.revision }, 25000)
    save(next)
    const text = next.missing_fields.length ? `Still needed: ${next.missing_fields.map(field => missingLabels[field] || field).join(', ')}.`
      : next.result?.status === 'options' ? next.result.options[0]?.kind === 'hotel' ? 'Hotel leads are ready. Compare observed stay prices below; whole-trip costs and requirements remain unverified.' : `${next.result.options.length} synthetic options are ready. Compare the full cost and tradeoffs below.`
      : next.result?.status === 'no_match' ? 'No usable options were returned. Review the coverage details; your constraints have been kept.'
      : 'This request is outside the available demo coverage. See the details below.'
    say(text); setAnnouncement(text)
  }
  const blocked = !!busy || needsReload || !trip
  async function exploreActivities() {
    const state = current.current
    if (!state) return
    const next = await request<Trip>(`/trips/${state.id}/activities`, 'POST', { expected_revision: state.revision })
    save(next)
    say('The researched Milwaukee activity guide is below. Admission and rental rates are separate from your trip total; availability remains unverified.')
  }
  const hasDraft = Object.values(dirty).some(Boolean)
  const stale = !!trip?.results_stale || evidenceExpired(trip?.result, now) || hasDraft || needsReload
  async function refreshAll() {
    const state = current.current
    if (!state) return
    const next = await request<Trip>(`/trips/${state.id}/refresh`, 'POST', {
      expected_revision: state.revision, request_id: crypto.randomUUID(),
    }, 25000)
    save(next)
    say(Object.keys(next.source_issues).length ? 'Refresh finished with source limitations. Review the notices and available results below.' : 'Trip options and the separate researched activity guide are updated. Check each source’s price and availability limits.')
  }

  function chooseDemo(kind: 'cheap' | 'adventure' | 'private') {
    void run('Loading example…', async () => {
      say(`Load the ${kind === 'private' ? 'private-room adventure' : kind + ' weekend'} example: Chicago, 2 nights, 1 adult, $500 party cap covering all costs.`, 'you')
      await patch(demoChanges(kind), 'form')
      await generate()
    })
  }
  function send() {
    if (!input.trim() || blocked || hasDraft) return
    if (!input.trim().startsWith('/')) {
      if (!health?.chat_available) { setProblem('Natural-language chat needs a model key. Gemini free-tier setup is documented in docs/model-setup.md. You can still use demo commands.'); return }
      const text = input.trim()
      void run('Understanding your trip…', async () => {
        const state = current.current!
        const next = await request<Trip>(`/trips/${state.id}/messages`, 'POST', {
          expected_revision: state.revision, expected_conversation_revision: state.conversation_revision, message: text,
        }, 55000)
        save(next); setControlEpoch(value => value + 1)
        setMessages(next.messages.map(item => ({role: item.role === 'user' ? 'you' : 'guide', text: item.text})))
        setAnnouncement(next.messages.at(-1)?.text || 'Trip updated.'); setInput('')
      })
      return
    }
    let command
    try { command = parseCommand(input) }
    catch (error) { setProblem((error as Error).message); return }
    const text = input.trim()
    void run(command.kind === 'plan' ? 'Comparing options…' : 'Saving preferences…', async () => {
      say(text, 'you')
      if (command.kind === 'plan') await generate()
      else if (command.kind === 'activities') await exploreActivities()
      else { await patch(command.changes, 'chat'); say('Saved your change. Your other preferences are unchanged. Select Update options to compare again.') }
      setInput('')
    })
  }
  const p = trip?.preferences
  const nights = p?.nights ?? (p?.dates?.start && p.dates.end ? Math.round((Date.parse(p.dates.end) - Date.parse(p.dates.start)) / 86400000) : null)
  return <main>
    <a className="skip" href="#composer">Skip to conversation</a>
    <header><a className="brand" href="/" aria-label="Travel Agent home"><span className="mark">↗</span> Travel Agent</a>
      <div className="header-actions"><span className="tag">{health?.data_mode === 'live' ? health.planning_available ? 'Hotel search' : 'Hotel search · setup pending' : 'Fixture demo'}</span>
        <button className="text-button" disabled={!!busy} onClick={() => void run('Starting a new trip…', async () => {
          save(await request<Trip>('/trips', 'POST', {})); setMessages([intro]); setNeedsReload(false); setExpired(false); setInput(''); setControlEpoch(value => value + 1)
        })}>New trip</button></div>
    </header>
    <section className="intro"><p className="eyebrow">LESS ORDINARY. MORE POSSIBLE.</p><h1>Take the <em>interesting</em> route.</h1><p>A longer ride. A simpler stay. Find the tradeoff that’s worth it.</p></section>
    <div className="workspace">
      <aside className="trip-summary" aria-label="Current trip summary"><p className="eyebrow">YOUR FIELD NOTES</p><h2>The trip so far.</h2>
        <dl><div><dt>From</dt><dd>{p?.origin || 'Not chosen'}</dd></div>
          <div><dt>When</dt><dd>{p?.dates ? p.dates.mode === 'flexible' ? `Flexible${p.dates.start ? ` within ${p.dates.start}–${p.dates.end}` : ''}` : `${p.dates.start} → ${p.dates.end}` : 'Not chosen'}</dd></div>
          <div><dt>Travelers & stay</dt><dd>{p?.adults ? `${p.adults} adult${p.adults === 1 ? '' : 's'}` : 'Adults unknown'} · {nights ? `${nights} nights` : 'Nights unknown'}</dd></div>
          <div><dt>Budget cap</dt><dd>{p?.budget ? `${money(p.budget.amount)} USD ${p.budget.basis === 'party' ? 'for the party' : p.budget.basis === 'per_person' ? 'per person' : '— basis unknown'}` : 'Not chosen'}</dd></div>
          <div><dt>Budget includes</dt><dd>{p?.budget?.covers?.join(', ') || 'Not chosen'}</dd></div>
          <div><dt>Interests</dt><dd>{p?.interests.length ? p.interests.join(', ') : 'Open to ideas'}</dd></div></dl>
        <details className="constraints" open><summary>Comfort & requirements</summary>
          <ul>{(['private_room', 'shared_room_allowed', 'camping_allowed', 'overnight_transport_allowed'] as const).map(key => <li key={key}>{({ private_room: 'Private room required', shared_room_allowed: 'Shared rooms', camping_allowed: 'Camping', overnight_transport_allowed: 'Overnight transport' })[key]}: <strong>{p?.constraints[key] == null ? 'Not specified' : p.constraints[key] ? 'Yes' : 'No'}</strong></li>)}
            <li>Maximum exertion: <strong>{p?.constraints.max_exertion || 'Not specified'}</strong></li>
            <li>Accessibility: {p?.constraints.accessibility.join(', ') || 'Not specified'}</li><li>Avoid transport: {p?.constraints.excluded_transport.join(', ') || 'Not specified'}</li></ul>
        </details><p className="small">{health?.data_mode === 'live' ? 'Hotel pilot: Milwaukee, Wisconsin. Fixed dates and one room for one or two adults. Other trip costs and requirements remain unverified.' : 'Chicago → Milwaukee, Indiana Dunes or Starved Rock. Synthetic prices and routes; no availability checked.'}</p>
      </aside>
      <div className="conversation-column">
        <PreferenceControls resetToken={controlEpoch} values={p?.controls || emptyControls} disabled={blocked}
          onDirty={(name, value) => setDirty(previous => ({ ...previous, [name]: value }))}
          onSave={(name, value) => { if (!blocked) void run('Saving preference…', async () => { await patch({ controls: { [name]: value } }, 'slider') }) }} />
        <section className="conversation" aria-labelledby="conversation-title">
          <div className="section-heading"><h2 id="conversation-title">Your travel conversation</h2><span className="tag">{health?.chat_available ? 'AI chat' : 'Trip commands'}</span></div>
          <p className="demo-notice">{health?.data_mode === 'live' ? 'Hotel-only search for Milwaukee. Choose fixed dates; final fees, room type and availability must be checked on the source site.' : health?.chat_available ? 'Describe your trip naturally. Trip comparison prices are synthetic.' : 'Model setup is pending. Use commands to explore synthetic trip comparisons.'} The activity guide is separately researched from official sources; it does not check booking slots.</p>
          <div ref={transcript} className="transcript" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions">{messages.map((message, index) => <div key={index} className={`message ${message.role}`}><span className="speaker">{message.role === 'you' ? 'YOU' : 'TRAVEL GUIDE · DEMO'}</span><p>{message.text}</p></div>)}</div>
          <div className="examples" aria-label="Load sample trip"><button disabled={blocked || hasDraft} onClick={() => chooseDemo('cheap')}>↗ Cheap weekend</button><button disabled={blocked || hasDraft} onClick={() => chooseDemo('adventure')}>↗ Adventure weekend</button><button disabled={blocked || hasDraft} onClick={() => chooseDemo('private')}>↗ Adventure + private room</button></div>
          <p className="small">Examples replace the trip with a solo, two-night Chicago getaway and a $500 all-cost cap. Cheap/adventure examples accept dorms and camping; the private-room example does not.</p>
          <form onSubmit={event => { event.preventDefault(); send() }}>
            <label htmlFor="composer">{health?.chat_available ? 'Tell me about your trip' : 'Refine your trip with a demo command'}</label>
            <div className="composer-row"><textarea id="composer" ref={composer} rows={2} maxLength={3000} value={input} disabled={blocked} placeholder={health?.chat_available ? 'A cheap weekend from Chicago, with time to explore…' : 'Try /budget 200 or /adventure 90'} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send() } }} /><button className="primary" type="submit" disabled={blocked || hasDraft || !input.trim()}>Send ↗</button></div>
          </form>
          <details className="command-help"><summary>Supported commands</summary><p>Choose a command to edit it. For all contract fields, use <code>/set {`{"budget":{"basis":"party"}}`}</code>. Changes are validated by the backend.</p><div className="command-list">{commandHelp.map(command => <button key={command} disabled={blocked} onClick={() => { setInput(command); composer.current?.focus() }}>{command}</button>)}</div><p>A fixed date change clears the separate night count; /nights must match fixed dates. Use /flexible to remove the fixed window.</p></details>
          {trip?.missing_fields.length ? <p className="notice">Still needed: {trip.missing_fields.map(field => missingLabels[field] || field).join(', ')}.</p> : null}
          <div className="plan-row"><p>{hasDraft ? 'Release the slider to save your preference.' : trip?.results_stale ? 'Preferences saved. Your options need an update.' : 'Compare when your preferences are ready.'}</p><button className="primary" disabled={blocked || hasDraft || !trip?.planning_available || !!trip?.missing_fields.length} onClick={() => void run('Comparing options…', generate)}>{busy === 'Comparing options…' ? 'Comparing…' : trip?.result ? 'Update options' : 'Find options'} ↗</button></div>
          <button disabled={blocked || hasDraft || !p?.adults} onClick={() => void run('Comparing activities…', exploreActivities)}>Explore Milwaukee activities ↗</button>
          <button disabled={blocked || hasDraft || !p?.adults} onClick={() => void run('Refreshing sources…', refreshAll)}>Refresh options + activity guide ↗</button>
        </section>
        <div role="status" className="status-line" aria-live="polite">{busy || announcement}</div>
        {problem && <div className="error-panel" role="alert"><strong>Couldn’t complete that request.</strong><p>{problem}</p><p>Any displayed options are from the last successful search.</p></div>}
        {needsReload && !expired && <button onClick={() => void connect()} disabled={!!busy}>Reload trip state</button>}
        {Object.entries(trip?.source_issues || {}).map(([source, issue]) => <p className="notice" role="status" key={source}>{issue}</p>)}
        {trip?.result && <Results result={trip.result} stale={stale} />}
        {trip?.activity_result && <Results result={trip.activity_result} activities stale={trip.activities_stale || evidenceExpired(trip.activity_result, now) || hasDraft || needsReload} />}
        {!trip?.result && <section className="empty-results"><span aria-hidden="true">↗</span><h2>Leave room for a different route.</h2><p>{health?.data_mode === 'live' ? 'Hotel prices will appear here after a configured search. No whole-trip cost is promised.' : 'Your options will appear here, with the real tradeoffs behind each synthetic price.'}</p></section>}
      </div>
    </div>
    <footer><span><span className="dot" />{busy === 'Connecting…' ? 'Connecting…' : health ? health.data_mode === 'fixture' ? 'Fixture service · no live bookings' : health.planning_available ? 'Hotel search configured · no bookings' : 'Hotel service · setup pending' : 'Service unavailable'}</span><button onClick={() => void connect()} disabled={!!busy}>Check connection</button><span>Local demo · trips reset when the server restarts</span></footer>
  </main>
}

createRoot(document.getElementById('root')!).render(<App />)
