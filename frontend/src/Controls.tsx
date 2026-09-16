import { useEffect, useState } from 'react'
import type { Controls as Values } from './types'

const labels = {
  adventure: { title: 'Adventure', left: 'Easygoing', right: 'Exploratory', initial: 0 },
  savings: { title: 'Price', left: 'Lowest cost', right: 'Spend more', initial: 50 },
  transit_tolerance: { title: 'Travel time', left: 'Less transit', right: 'Longer is okay', initial: 100 },
}
function describe(key: keyof Values, value: number) {
  if (key === 'adventure') return value < 34 ? 'Easygoing exploration' : value < 67 ? 'A little adventure' : 'Adventure first'
  if (key === 'savings') return value < 34 ? 'Lowest cost first' : value < 67 ? 'Balance cost and experience' : 'Open to spending more'
  return value < 34 ? 'Minimize travel time' : value < 67 ? 'Some longer journeys' : 'Long journeys are okay'
}

function Slider({ name, value, disabled, resetToken, onSave, onDirty }: {
  name: keyof Values; value: number | null; disabled: boolean; resetToken: number
  onSave: (name: keyof Values, value: number) => void; onDirty: (name: keyof Values, dirty: boolean) => void
}) {
  const label = labels[name]
  const saved = value === null ? label.initial : name === 'savings' ? 100 - value : value
  const [draft, setDraft] = useState(saved)
  useEffect(() => { setDraft(saved) }, [saved, resetToken])
  const commit = (position: number) => {
    if (position !== saved || value === null) onSave(name, name === 'savings' ? 100 - position : position)
    onDirty(name, false)
  }
  return <div className="slider">
    <div className="slider-heading"><label htmlFor={name}>{label.title}</label><span>{value === null ? 'Suggested' : 'Selected'}</span></div>
    <p id={`${name}-meaning`}>{describe(name, draft)}</p>
    <input id={name} type="range" min="0" max="100" value={draft} disabled={disabled}
      aria-valuetext={`${describe(name, draft)}${value === null ? ', suggested until selected' : ''}`}
      aria-describedby={`${name}-meaning`}
      onChange={event => { setDraft(Number(event.target.value)); onDirty(name, true) }}
      onPointerUp={event => commit(Number(event.currentTarget.value))}
      onKeyUp={event => { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown'].includes(event.key)) commit(Number(event.currentTarget.value)) }}
      onBlur={event => { if (Number(event.currentTarget.value) !== saved) commit(Number(event.currentTarget.value)) }} />
    <div className="slider-ends"><span>{label.left}</span><span>{label.right}</span></div>
  </div>
}

export function PreferenceControls({ values, disabled, resetToken, onSave, onDirty }: {
  values: Values; disabled: boolean; resetToken: number; onSave: (name: keyof Values, value: number) => void
  onDirty: (name: keyof Values, dirty: boolean) => void
}) {
  return <section className="controls" aria-label="Travel preferences">
    {(Object.keys(labels) as (keyof Values)[]).map(name => <Slider key={name} name={name} value={values[name]} disabled={disabled} resetToken={resetToken} onSave={onSave} onDirty={onDirty} />)}
    <p className="controls-note">These preferences keep your budget cap and comfort requirements intact. Release a slider to save; update options when you’re ready.</p>
  </section>
}
