import type { Option, Snapshot } from './types'

export const money = (amount: string | null | undefined) => amount == null ? 'Unknown' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(amount))
const duration = (minutes: number) => `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`
const words = (value: string) => value.replaceAll('_', ' ')

function HotelCard({ option }: { option: Option }) {
  const source = option.costs[0]?.evidence
  return <article className="option" aria-labelledby={`title-${option.id}`}>
    <span className="tag">Observed hotel search price</span>
    <h3 id={`title-${option.id}`}>{option.title}</h3>
    <p>{option.destination} · {option.adults} adults · {option.nights} nights</p>
    {source?.search_dates && <p>{source.search_dates.start} → {source.search_dates.end}</p>}
    <div className="price">{money(option.hotel_cost?.total)}<span>USD · displayed whole stay</span></div>
    <p>Whole-trip total: unknown. Room requirements and budget fit have not been verified.</p>
    <div className="tradeoff"><strong>Before choosing</strong>{option.tradeoffs.map(item => <p key={item}>{item}</p>)}</div>
    <details><summary>Source & search assumptions</summary>
      <p>{source?.provider} · Retrieved {source && new Date(source.retrieved_at).toLocaleString()}</p>
      <p>{source?.explanation}</p>
      <ul>{option.assumptions.map(item => <li key={item}>{item}</li>)}</ul>
      <p>Missing cost categories: {option.total_cost?.missing_categories.join(', ')}.</p>
      {source?.url && /^https:\/\//.test(source.url) && <a href={source.url} target="_blank" rel="noopener noreferrer">Check the property’s current prices (opens a new tab)</a>}
    </details>
  </article>
}

function ActivityCard({ option }: { option: Option }) {
  const sources = [...option.costs.map(cost => cost.evidence), ...(option.supporting_evidence || [])]
  return <article className="option" aria-labelledby={`activity-${option.id}`}>
    <span className="tag">Researched activity · published price</span>
    <h3 id={`activity-${option.id}`}>{option.title}</h3>
    <div className="price">{money(option.activity_cost?.total)}<span>USD · activity charge for {option.adults} adult{option.adults === 1 ? '' : 's'}</span></div>
    <p>{option.activity_schedule}</p>
    <p>Whole-trip total unknown. Date-specific availability has not been checked.</p>
    <div className="tradeoff">{option.tradeoffs.map(item => <p key={item}>{item}</p>)}</div>
    <details><summary>Sources, equipment & limits</summary>
      {sources.map((source, index) => <div key={index}><p>{source.provider} · Reviewed {new Date(source.retrieved_at).toISOString().slice(0, 10)}</p><p>{source.explanation}</p>
        {source.url && /^https:\/\//.test(source.url) && <a href={source.url} target="_blank" rel="noopener noreferrer">Check official source (opens a new tab)</a>}</div>)}
      <ul>{option.assumptions.map(item => <li key={item}>{item}</li>)}</ul>
      <p>Unpriced categories: {option.total_cost?.missing_categories.join(', ')}.</p>
    </details>
  </article>
}

function OptionCard({ option, index }: { option: Option; index: number }) {
  return <article className="option" aria-labelledby={`title-${option.id}`}>
    <div className="option-top"><span className="eyebrow">0{index + 1} / {option.destination}</span><span className="tag">Synthetic example</span></div>
    <h3 id={`title-${option.id}`}>{option.title}</h3>
    <div className="price">{money(option.total_cost?.total)}<span>USD · whole party</span></div>
    <p className="option-meta">{option.adults} adult{option.adults === 1 ? '' : 's'} · {option.nights} nights · {words(option.accommodation)}</p>
    <dl className="journey"><div><dt>Round-trip travel</dt><dd>{duration(option.transit_minutes)}</dd></div><div><dt>At destination, incl. sleep</dt><dd>{duration(option.destination_minutes)}</dd></div></dl>
    <p className="budget-line">{money(option.budget_cost?.total)} of your {money(option.budget_cap)} cap for {option.budget_categories.join(', ')}.</p>
    <ul className="fit">{option.fit_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    <div className="tradeoff"><strong>The tradeoff</strong>{option.tradeoffs.map(item => <p key={item}>{item}</p>)}</div>
    <details><summary>Cost breakdown & evidence</summary>
      <ul className="cost-list">{option.costs.map((cost, i) => <li key={i}>
        <strong>{cost.label}</strong>
        <span>{money(cost.amount)} × {cost.quantity} {words(cost.basis)} unit{cost.quantity === 1 ? '' : 's'}</span>
        {cost.unknown_reason && <span>{cost.unknown_reason}</span>}
        <small>{words(cost.evidence.kind)} · {cost.evidence.provider}<br />Recorded {new Date(cost.evidence.retrieved_at).toLocaleDateString()}</small>
        <small>{cost.evidence.explanation}</small>
        {cost.evidence.url && /^https?:\/\//.test(cost.evidence.url) && <a href={cost.evidence.url} target="_blank" rel="noopener noreferrer">View source (opens a new tab)</a>}
      </li>)}</ul>
      <p>Known subtotal: {money(option.total_cost?.known_subtotal)}. {option.total_cost?.missing_categories.length ? `Missing: ${option.total_cost.missing_categories.join(', ')}` : 'All required fixture categories included.'}</p>
    </details>
    <details><summary>Trip outline & assumptions</summary><ol>{option.itinerary.map(item => <li key={item}>{item}</li>)}</ol><ul>{option.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>
  </article>
}

export function Results({ result, stale, activities = false }: { result: Snapshot; stale: boolean; activities?: boolean }) {
  return <section className={stale ? 'results stale' : 'results'} aria-label={activities ? 'Researched activities' : 'Trip options'}>
    <div className="results-heading"><h2>{activities ? 'Milwaukee activity guide.' : result.status === 'options' ? result.options[0]?.kind === 'hotel' ? 'Hotel leads to explore.' : 'A few ways to go.' : result.status === 'no_match' ? 'No usable options returned.' : 'This search is unavailable.'}</h2>
      <p>{stale ? 'Needs review · update to compare again' : 'Based on your saved preferences'}<br />Calculated {new Date(result.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p></div>
    {stale && <p className="notice">Preferences changed, evidence expired, or a refresh was incomplete. These results need review before comparing prices and fit.</p>}
    <div className="option-grid">{result.options.map((option, index) => option.kind === 'activity' ? <ActivityCard key={option.id} option={option} /> : option.kind === 'hotel' ? <HotelCard key={option.id} option={option} /> : <OptionCard key={option.id} option={option} index={index} />)}</div>
    <details className="coverage" open={result.status !== 'options'}><summary>Coverage & excluded options</summary>
      <ul>{result.coverage_gaps.map(gap => <li key={gap}>{gap}</li>)}</ul>
      {result.exclusions.map(item => <div key={item.candidate_id}><strong>{words(item.candidate_id.replaceAll('-', ' '))}</strong><ul>{item.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div>)}
    </details>
  </section>
}
