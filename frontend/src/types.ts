export type Controls = { adventure: number | null; savings: number | null; transit_tolerance: number | null }
export type Preferences = {
  origin: string | null
  dates: { mode: 'fixed' | 'flexible'; start: string | null; end: string | null } | null
  nights: number | null
  adults: number | null
  budget: { amount: string; currency: string; basis: 'party' | 'per_person' | null; covers: string[] | null } | null
  interests: string[]
  controls: Controls
  constraints: {
    private_room: boolean | null; shared_room_allowed: boolean | null; camping_allowed: boolean | null
    overnight_transport_allowed: boolean | null; max_exertion: 'low' | 'moderate' | 'high' | null
    accessibility: string[]; excluded_transport: string[]
  }
}
export type Changes = Record<string, unknown>
export type CostSummary = { known_subtotal: string; total: string | null; currency: string; missing_categories: string[] }
export type Cost = {
  label: string; category: string; amount: string | null; quantity: number; basis: string; currency: string
  unknown_reason: string | null
  evidence: { kind: string; provider: string; retrieved_at: string; explanation: string; url: string | null; search_dates?: {start: string; end: string} | null }
}
export type Option = {
  kind: 'trip' | 'hotel' | 'activity'; hotel_cost: CostSummary | null
  activity_cost?: CostSummary | null; activity_schedule?: string | null; supporting_evidence?: Cost['evidence'][]
  id: string; title: string; destination: string; costs: Cost[]; tradeoffs: string[]
  total_cost: CostSummary; budget_cost: CostSummary; budget_cap: string; budget_categories: string[]
  nights: number; adults: number; transit_minutes: number; destination_minutes: number
  exertion: string; accommodation: string; fit_reasons: string[]; assumptions: string[]; itinerary: string[]
}
export type Snapshot = {
  preference_revision: number; created_at: string; status: 'options' | 'no_match' | 'unavailable'
  options: Option[]; coverage_gaps: string[]; exclusions: { candidate_id: string; reasons: string[] }[]
}
export type Trip = {
  activity_result: Snapshot | null; activities_stale: boolean
  conversation_revision: number
  messages: { role: 'user' | 'assistant'; text: string }[]
  id: string; revision: number; preferences: Preferences; result: Snapshot | null
  missing_fields: string[]; status: 'ready' | 'needs_clarification'; results_stale: boolean; planning_available: boolean
}
export type Health = { data_mode: 'fixture' | 'live'; planning_available: boolean; chat_available: boolean }
