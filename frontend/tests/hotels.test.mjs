import test from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

test('hotel cards render stay-only evidence, unknown totals and escaped provider text', async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  try {
    const { Results } = await server.ssrLoadModule('/src/Results.tsx')
    const option = { kind: 'hotel', id: 'test', title: '<script>untrusted</script>', destination: 'Milwaukee', adults: 2, nights: 2,
      hotel_cost: { total: '240.00' }, total_cost: { total: null, missing_categories: ['fees', 'transport'] },
      costs: [{ evidence: { provider: 'Google Hotels via SerpApi', kind: 'observed_search_price',
        retrieved_at: '2026-09-15T12:00:00Z', url: 'https://example.com/hotel',
        search_dates: { start: '2027-01-01', end: '2027-01-03' }, explanation: 'Final fees are unverified.' } }],
      tradeoffs: ['Other trip costs are unknown.'], assumptions: ['One room assumed.'] }
    const html = renderToStaticMarkup(React.createElement(Results, { stale: true,
      result: { preference_revision: 0, created_at: '2026-09-15T12:00:00Z', status: 'options', options: [option], coverage_gaps: [], exclusions: [] } }))
    assert.match(html, /Observed hotel search price/)
    assert.match(html, /\$240\.00/)
    assert.match(html, /Whole-trip total: unknown/)
    assert.match(html, /2027-01-01/)
    assert.match(html, /evidence expired, or a refresh was incomplete/)
    assert.match(html, /&lt;script&gt;/)
    assert.doesNotMatch(html, /<script>|Synthetic example|All required fixture categories included/)
    assert.match(html, /href="https:\/\/example.com\/hotel"/)
  } finally { await server.close() }
})
