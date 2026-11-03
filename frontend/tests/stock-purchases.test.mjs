import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import { createPinia } from 'pinia'
import axios from 'axios'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'
import * as acquisitions from '../src/components/stock-detail/acquisitions.js'
import * as vesting from '../src/components/stock-detail/vesting.js'
import * as sales from '../src/components/stock-detail/sales.js'
import { useStockGrantsStore } from '../src/stores/stockGrants.js'
import { useStockQuotesStore } from '../src/stores/stockQuotes.js'

const today = '2026-11-02'
const purchases = () => [
  { id: 1, planName: 'ESPP', purchaseDate: '2026-06-01', quantity: 20 },
  { id: 2, planName: 'ESPP', purchaseDate: today, quantity: 10 },
]
const grants = () => [
  {
    id: 1,
    title: 'Retention',
    color: '#426b5a',
    quantity: 150,
    vestings: [
      { id: 1, date: today, quantity: 100 },
      { id: 2, date: '2027-01-01', quantity: 50 },
    ],
  },
]
const mixedSale = () => ({
  id: 1,
  transactionDate: today,
  quantity: 15,
  proceedsPerShare: '100.000000',
  allocations: [
    { purchaseId: 1, quantity: 5 },
    { vestingId: 1, quantity: 10 },
  ],
})
const apiPurchase = (id = 1, stockId = 1) => ({
  id,
  stock_id: stockId,
  purchase_date: today,
  quantity: 20,
  plan_name: 'ESPP',
})
const draft = () => ({ purchaseDate: today, quantity: 20, creationToken: crypto.randomUUID() })
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}

function setup(t, path, props, exposed, dependencies = {}) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const script = descriptor.scriptSetup.content.replace(
    /^import[\s\S]*?from ['"][^'"]+['"]\n/gm,
    '',
  )
  const events = []
  const bindings = {
    ref: Vue.ref,
    computed: Vue.computed,
    watch: Vue.watch,
    ...acquisitions,
    ...vesting,
    ...sales,
    defineProps: () => props,
    defineEmits:
      () =>
      (...args) => {
        events.push(args)
        if (args[0] === 'update:open') props.open = args[1]
      },
    ...dependencies,
  }
  const scope = Vue.effectScope()
  t.after(() => scope.stop())
  return {
    events,
    view: scope.run(() =>
      new Function(...Object.keys(bindings), `${script}\nreturn { ${exposed} }`)(
        ...Object.values(bindings),
      ),
    ),
  }
}

function mockStore(t, overrides = {}) {
  const original = { get: axios.get, post: axios.post, delete: axios.delete }
  t.after(() => Object.assign(axios, original))
  Object.assign(axios, {
    get: async (url) => ({
      data: /\/(grants|purchases|sales)$/.test(url)
        ? []
        : { id: Number(url.split('/').at(-1)), name: 'Apple', symbol: 'AAPL' },
    }),
    post: async () => ({ data: apiPurchase() }),
    delete: async () => ({}),
    ...overrides,
  })
  return useStockGrantsStore(createPinia())
}

test('mixed summaries include purchases without inflating future RSU vestings', () => {
  const summary = vesting.summarizePortfolio(grants(), purchases(), today)
  assert.deepEqual(
    [summary.total, summary.acquired, summary.unvested, summary.nextTwelveMonths],
    [180, 130, 50, 50],
  )
  assert.deepEqual(summary.nextRelease, { date: '2027-01-01', quantity: 50 })
  assert.equal(vesting.summarizePortfolio([], purchases(), today).acquired, 30)
})

test('quarterly chart groups ESPP purchases into one plan and keeps lots distinct', () => {
  const rows = [
    ...purchases(),
    { id: 3, planName: 'ESPP', purchaseDate: '2026-11-01', quantity: 5 },
  ]
  const quarters = vesting.buildQuarters(grants(), today, rows)
  const quarter = quarters.find((item) => item.id === '2026-Q4')
  assert.equal(quarter.vested, 115)
  assert.equal(quarter.segments.length, 2)
  assert.equal(quarter.segments.find((item) => item.id === 'purchase-plan:ESPP-false').quantity, 15)
  assert.equal(new Set(quarter.releases.map((item) => item.key)).size, 3)
  assert.equal(
    acquisitions.acquisitionPlans(grants(), rows).filter((item) => item.title === 'ESPP').length,
    1,
  )
})

test('mixed sale lots do not collide and all recorded sales reduce availability', () => {
  const lots = sales.availablePockets(grants(), [mixedSale()], today, purchases())
  assert.equal(lots.find((lot) => lot.key === 'purchase:1').remaining, 15)
  assert.equal(lots.find((lot) => lot.key === 'vesting:1').remaining, 90)
  assert.equal(sales.availablePockets(grants(), [mixedSale()], '2026-06-01', purchases()).length, 1)
  assert.deepEqual(sales.validateSale(mixedSale(), lots, today), {})
  const duplicateSource = {
    ...mixedSale(),
    allocations: [{ purchaseId: 1, vestingId: 1, quantity: 15 }],
  }
  assert.ok(sales.validateSale(duplicateSource, lots, today).allocations)
  const holding = sales.buildHoldings(grants(), [mixedSale()], today, purchases())
  assert.deepEqual([holding.acquired, holding.sold, holding.held], [130, 15, 115])
  assert.deepEqual(
    holding.events.map((item) => item.balance),
    [20, 30, 130, 115],
  )
  assert.equal(holding.events.at(-1).allocations[0].grantTitle, 'ESPP')
  assert.equal(sales.buildHoldings([], [], today, purchases()).held, 30)
  assert.equal(
    sales.availablePockets(grants(), [], today, purchases()).find((lot) => lot.key === 'purchase:1')
      .remaining,
    20,
  )
})

test('purchase modal validates, prevents duplicate saves, preserves failed drafts and resets on reopen', async (t) => {
  const props = Vue.reactive({ open: true, ticker: 'AAPL', today, saving: false, saveError: '' })
  const { view, events } = setup(
    t,
    '../src/components/stock-detail/AddPurchaseModal.vue',
    props,
    'details, errors, creationToken, confirm, close, preventDismiss',
  )
  assert.equal(view.details.value.purchaseDate, today)
  view.confirm()
  assert.ok(view.errors.value.quantity)
  view.details.value = { purchaseDate: '2026-11-03', quantity: 2 }
  view.confirm()
  assert.ok(view.errors.value.purchaseDate)
  view.details.value = { purchaseDate: today, quantity: 1.5 }
  view.confirm()
  assert.ok(view.errors.value.quantity)
  view.details.value.quantity = '20'
  view.confirm()
  view.confirm()
  assert.equal(events.length, 1)
  assert.equal(events[0][1].quantity, 20)
  let prevented = false
  view.preventDismiss({
    preventDefault: () => {
      prevented = true
    },
  })
  view.close()
  assert.equal(prevented, true)
  assert.equal(props.open, true)
  props.saving = true
  await flush()
  props.saving = false
  props.saveError = 'Offline'
  await flush()
  view.confirm()
  assert.deepEqual(events[1][1], events[0][1])
  props.saveError = 'Still offline'
  await flush()
  view.close()
  await flush()
  props.open = true
  await flush()
  assert.equal(view.details.value.quantity, '')
  assert.notEqual(view.creationToken.value, events[0][1].creationToken)
})

test('sale modal emits purchase and vesting allocations and clears choices before acquisition dates', async (t) => {
  const props = Vue.reactive({
    open: true,
    today,
    grants: grants(),
    purchases: purchases(),
    sales: [],
    saving: false,
    saveError: '',
  })
  const { view, events } = setup(
    t,
    '../src/components/stock-detail/RecordSaleModal.vue',
    props,
    'details, quantities, confirm, errors',
  )
  view.details.value = { transactionDate: today, quantity: 15, proceedsPerShare: '100' }
  view.quantities.value = { 'purchase:1': 5, 'vesting:1': 10 }
  view.confirm()
  assert.deepEqual(events[0][1].allocations, mixedSale().allocations)
  view.details.value.transactionDate = '2026-06-01'
  await flush()
  assert.deepEqual(view.quantities.value, { 'purchase:1': 5 })
})

test('purchase store retries, maps records, serializes mutations and waits before refresh', async (t) => {
  const pending = deferred()
  const requests = []
  const store = mockStore(t, {
    post: (...args) => {
      requests.push(args)
      return pending.promise
    },
  })
  await store.load(1)
  const data = draft()
  const saving = store.createPurchase(1, data)
  assert.equal(await store.createGrant(1, {}), null)
  assert.equal(await store.createSale(1, {}), null)
  assert.equal(await store.deletePurchase(1, 1), false)
  pending.reject(new Error('Offline'))
  assert.equal(await saving, null)
  assert.match(store.forStock(1).purchaseSaveError, /draft is still here/)
  axios.post = async (...args) => {
    requests.push(args)
    return { data: apiPurchase() }
  }
  await store.createPurchase(1, data)
  await store.createPurchase(1, data)
  assert.equal(store.forStock(1).purchases.length, 1)
  assert.equal(store.forStock(1).purchases[0].planName, 'ESPP')
  assert.ok(
    requests.every(([, , options]) => options.headers['Idempotency-Key'] === data.creationToken),
  )
  axios.delete = async () => {
    throw { response: { data: { error: 'Recorded sales' } } }
  }
  assert.equal(await store.deletePurchase(1, 1), false)
  assert.equal(store.forStock(1).purchases.length, 1)
  assert.equal(store.forStock(1).purchaseDeleteError, 'Recorded sales')
  const deletion = deferred()
  axios.delete = () => deletion.promise
  let reads = 0
  axios.get = async (url) => {
    reads++
    return { data: /\/(grants|purchases|sales)$/.test(url) ? [] : { id: 1 } }
  }
  const deleting = store.deletePurchase(1, 1)
  const refreshing = store.load(1)
  assert.equal(reads, 0)
  deletion.resolve({})
  await deleting
  await refreshing
  assert.equal(reads, 4)
  assert.deepEqual(store.forStock(1).purchases, [])
})

test('store round-trips mixed source allocations with the existing sale API', async (t) => {
  let body
  const store = mockStore(t, {
    post: async (url, data) => {
      body = data
      return { data: { id: 1, stock_id: 1, ...data, currency: 'USD' } }
    },
  })
  await store.load(1)
  const saved = await store.createSale(1, { ...mixedSale(), creationToken: crypto.randomUUID() })
  assert.deepEqual(body.allocations, [
    { purchase_id: 1, quantity: 5 },
    { vesting_id: 1, quantity: 10 },
  ])
  assert.deepEqual(saved.allocations, mixedSale().allocations)
})

test('purchase-only timeline and ledger render data, and navigation isolates late saves', async (t) => {
  const props = Vue.reactive({ grants: [], purchases: purchases(), sales: [], today })
  const { view: timeline } = setup(
    t,
    '../src/components/stock-detail/VestingTimeline.vue',
    props,
    'quarters, plans, summary, bars',
  )
  assert.equal(timeline.plans.value[0].title, 'ESPP')
  assert.equal(timeline.summary.value.acquired, 30)
  assert.equal(timeline.bars.value.length, 3)
  const { view: ledger } = setup(
    t,
    '../src/components/stock-detail/HoldingsAndSales.vue',
    props,
    'portfolio, ledger, line',
  )
  assert.equal(ledger.ledger.value[0].label, 'Purchase')
  assert.equal(ledger.portfolio.value.held, 30)
  assert.ok(!/NaN|Infinity/.test(ledger.line.value))
  const store = mockStore(t)
  const route = Vue.reactive({ params: { stockId: '1' } })
  const { view } = setup(
    t,
    '../src/views/StockDetailView.vue',
    {},
    'addPurchase, showAddPurchase, entry',
    {
      useRoute: () => route,
      useStockGrantsStore: () => store,
      useStockQuotesStore: () => useStockQuotesStore(createPinia()),
      onMounted: () => {},
      onBeforeUnmount: () => {},
    },
  )
  await flush()
  const pending = deferred()
  axios.post = () => pending.promise
  const saving = view.addPurchase(draft())
  route.params.stockId = '2'
  await flush()
  view.showAddPurchase.value = true
  pending.resolve({ data: apiPurchase() })
  await saving
  assert.equal(view.showAddPurchase.value, true)
  assert.deepEqual(view.entry.value.purchases, [])
  assert.equal(store.forStock(1).purchases.length, 1)
})
