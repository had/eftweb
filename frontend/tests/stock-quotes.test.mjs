import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import { createPinia } from 'pinia'
import axios from 'axios'
import * as Vue from 'vue'
import { compileScript, parse } from 'vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import { useStockQuotesStore } from '../src/stores/stockQuotes.js'
import { formatQuoteTimestamp, formatStockValue, isUSDPrice } from '../src/lib/stockQuotes.js'
import { formatDate } from '../src/components/stock-detail/vesting.js'

const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}
const deferred = () => {
  let resolve, reject
  const promise = new Promise((accept, fail) => {
    resolve = accept
    reject = fail
  })
  return { promise, resolve, reject }
}
const quote = (overrides = {}) => ({
  symbol: 'AAPL',
  currency: 'USD',
  price: '123.45',
  fetched_at: new Date(Date.now()).toISOString(),
  quote_date: '2026-10-23',
  stale: false,
  error: null,
  ...overrides,
})
function setupStore(t, get) {
  const originalGet = axios.get
  const originalNow = Date.now
  let now = Date.parse('2026-10-25T12:00:00Z')
  Date.now = () => now
  axios.get = get || (async () => ({ data: quote() }))
  t.after(() => {
    axios.get = originalGet
    Date.now = originalNow
  })
  return {
    store: useStockQuotesStore(createPinia()),
    advance: (ms) => {
      now += ms
    },
  }
}

test('USD values multiply in exact cents and format zero and large quantities correctly', () => {
  assert.equal(formatStockValue(3, '0.10'), '$0.30')
  assert.equal(formatStockValue(99, '19.99'), '$1,979.01')
  assert.equal(formatStockValue(0, '123.45'), '$0.00')
  assert.equal(formatStockValue(Number.MAX_SAFE_INTEGER, '1.01'), '$9,097,271,247,288,400.91')
  for (const price of [undefined, null, 'NaN', 'Infinity', '-1.00', '0.00', '1.2'])
    assert.equal(formatStockValue(10, price), '—')
  assert.equal(formatStockValue(Number.MAX_SAFE_INTEGER + 1, '1.00'), '—')
  assert.equal(isUSDPrice('123.45'), true)
})

test('list and detail reuse one in-flight quote request and its cache across stock IDs', async (t) => {
  const pending = deferred()
  let calls = 0
  const { store } = setupStore(t, () => {
    calls += 1
    return pending.promise
  })
  const first = store.load({ id: 1, symbol: 'aapl' })
  const second = store.load({ id: 2, symbol: 'AAPL' })
  await flush()
  assert.equal(calls, 1)
  assert.equal(store.forSymbol('AAPL').loading, true)
  pending.resolve({ data: quote() })
  assert.deepEqual(await first, await second)
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(calls, 1)
  assert.equal(store.forSymbol('AAPL').loading, false)
})

test('frontend cache expiry respects the actual retrieval age, not just the last page visit', async (t) => {
  let calls = 0
  const { store, advance } = setupStore(t, async () => {
    calls += 1
    return { data: quote({ fetched_at: new Date(Date.now() - 50 * 60 * 1000).toISOString() }) }
  })
  await store.load({ id: 1, symbol: 'AAPL' })
  advance(9 * 60 * 1000)
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(calls, 1)
  advance(2 * 60 * 1000)
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(calls, 2)
})

test('stale provider quotes keep values visible and use a five-minute retry cooldown', async (t) => {
  let calls = 0
  const { store, advance } = setupStore(t, async () => {
    calls += 1
    return {
      data: quote({ stale: true, error: 'Rate limited', fetched_at: '2026-10-20T12:00:00Z' }),
    }
  })
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(store.forSymbol('AAPL').quote.price, '123.45')
  advance(4 * 60 * 1000)
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(calls, 1)
  advance(60 * 1000)
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(calls, 2)
})

test('network failures preserve a previous quote as stale, with no fabricated zero price', async (t) => {
  const { store, advance } = setupStore(t)
  await store.load({ id: 1, symbol: 'AAPL' })
  advance(61 * 60 * 1000)
  axios.get = async () => {
    throw new Error('Network')
  }
  await store.load({ id: 1, symbol: 'AAPL' })
  assert.equal(store.forSymbol('AAPL').quote.price, '123.45')
  assert.equal(store.forSymbol('AAPL').quote.stale, true)
  await store.load({ id: 2, symbol: 'MSFT' })
  assert.equal(store.forSymbol('MSFT').quote, null)
  assert.ok(store.forSymbol('MSFT').error)
})

test('ticker changes and late responses cannot display a different symbol under the requested ticker', async (t) => {
  const old = deferred()
  const { store } = setupStore(t, (url) =>
    url.includes('/1/')
      ? old.promise
      : Promise.resolve({ data: quote({ symbol: 'MSFT', price: '50.00' }) }),
  )
  const pending = store.load({ id: 1, symbol: 'AAPL' })
  await store.load({ id: 2, symbol: 'MSFT' })
  old.resolve({ data: quote({ symbol: 'MSFT', price: '99.00' }) })
  await pending
  assert.equal(store.forSymbol('AAPL').quote, null)
  assert.equal(store.forSymbol('MSFT').quote.price, '50.00')
})

const { descriptor } = parse(
  readFileSync(new URL('../src/components/StockQuote.vue', import.meta.url), 'utf8'),
)
const code = compileScript(descriptor, { id: 'quote-display-test', inlineTemplate: true })
  .content.replace(
    /^import \{([^}]+)\} from ['"]vue['"];?$/gm,
    (_, names) => `const {${names.replace(/ as /g, ': ')}} = Vue`,
  )
  .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n/gm, '')
  .replace('export default', 'return')
async function renderQuote(entry, props = {}) {
  const component = new Function(
    'Vue',
    'useStockQuotesStore',
    'formatDate',
    'formatQuoteTimestamp',
    'formatStockValue',
    code,
  )(
    Vue,
    () => ({ forSymbol: () => entry, load: async () => {} }),
    formatDate,
    formatQuoteTimestamp,
    formatStockValue,
  )
  return renderToString(Vue.createSSRApp(component, { stock: { id: 1, symbol: 'AAPL' }, ...props }))
}

test('quote display renders latest close, cached timestamp, loading and unavailable states', async () => {
  const available = await renderQuote({
    quote: quote({ fetched_at: '2026-10-25T12:00:00Z' }),
    loading: false,
    error: '',
  })
  assert.match(available, /\$123\.45 USD/)
  assert.match(available, /Latest close/)
  assert.match(available, /23 Oct 2026/)
  const stale = await renderQuote({
    quote: quote({ stale: true, fetched_at: '2026-10-20T12:00:00Z' }),
    loading: false,
    error: '',
  })
  assert.match(stale, /Cached price/)
  assert.match(stale, /Cached quote retrieved/)
  assert.match(stale, /20 Oct 2026/)
  const compact = await renderQuote(
    { quote: quote({ fetched_at: '2026-10-20T12:00:00Z' }), loading: false },
    { compact: true },
  )
  assert.match(compact, /\$123\.45 USD/)
  assert.match(compact, /Latest close/)
  assert.match(compact, /23 Oct 2026/)
  assert.doesNotMatch(compact, /Retrieved|retrieved|20 Oct 2026/)
  assert.match(await renderQuote({ quote: null, loading: true }), /Loading price/)
  assert.match(
    await renderQuote({ quote: null, loading: false, error: 'No key configured' }),
    /Price unavailable/,
  )
})
