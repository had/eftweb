import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import { createPinia } from 'pinia'
import axios from 'axios'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'
import * as vesting from '../src/components/stock-detail/vesting.js'
import * as sales from '../src/components/stock-detail/sales.js'
import { useStockGrantsStore } from '../src/stores/stockGrants.js'
import { useStockQuotesStore } from '../src/stores/stockQuotes.js'
import { formatStockValue } from '../src/lib/stockQuotes.js'

const grants = () => [
  {
    id: 1,
    title: 'Retention',
    quantity: 150,
    vestings: [
      { id: 10, date: '2024-01-01', quantity: 100 },
      { id: 11, date: '2026-10-29', quantity: 50 },
    ],
  },
  {
    id: 2,
    title: 'New award',
    quantity: 30,
    vestings: [
      { id: 12, date: '2025-01-01', quantity: 20 },
      { id: 13, date: '2030-01-01', quantity: 10 },
    ],
  },
]
const draft = () => ({
  transactionDate: '2026-10-29',
  quantity: 40,
  proceedsPerShare: '123.456789',
  creationToken: '6ecf09ec-1237-49c9-8e73-0139217b9165',
  allocations: [
    { vestingId: 10, quantity: 30 },
    { vestingId: 12, quantity: 10 },
  ],
})
const apiSale = (id = 1, stockId = 1) => ({
  id,
  stock_id: stockId,
  transaction_date: '2026-10-29',
  quantity: 40,
  proceeds_per_share: '123.456789',
  currency: 'USD',
  allocations: [
    { vesting_id: 10, quantity: 30 },
    { vesting_id: 12, quantity: 10 },
  ],
})
const sale = (id = 1) => ({ ...draft(), id, stockId: 1, currency: 'USD' })
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

function setupComponent(t, path, dependencies, exposed) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const script = descriptor.scriptSetup.content.replace(
    /^import[\s\S]*?from ['"][^'"]+['"]\n/gm,
    '',
  )
  const scope = Vue.effectScope()
  t.after(() => scope.stop())
  const bindings = {
    ref: Vue.ref,
    computed: Vue.computed,
    watch: Vue.watch,
    nextTick: Vue.nextTick,
    ...vesting,
    ...sales,
    ...dependencies,
  }
  return scope.run(() =>
    new Function(...Object.keys(bindings), `${script}\nreturn { ${exposed} }`)(
      ...Object.values(bindings),
    ),
  )
}

function mountModal(t) {
  const props = Vue.reactive({
    open: true,
    grants: grants().map((g) => ({
      ...g,
      vestings: g.vestings.map((v) => ({ ...v, acquisition_fmv: '100.000000' })),
    })),
    sales: [],
    today: '2026-10-29',
    saving: false,
    saveError: '',
  })
  const events = []
  const modal = setupComponent(
    t,
    '../src/components/stock-detail/RecordSaleModal.vue',
    {
      defineProps: () => props,
      defineEmits:
        () =>
        (...args) => {
          events.push(args)
          if (args[0] === 'update:open') props.open = args[1]
        },
    },
    'details, quantities, errors, pockets, allocated, proceeds, confirm, close, creationToken',
  )
  return { modal, props, events }
}

test('gross proceeds use exact millionths and round only the final total to cents', () => {
  assert.equal(sales.saleProceeds(3, '0.335'), '$1.01')
  assert.equal(sales.saleProceeds(40, '123.456789'), '$4,938.27')
  assert.equal(sales.saleProceeds(Number.MAX_SAFE_INTEGER, '0.000001'), '$9,007,199,254.74')
  assert.equal(sales.saleProceeds(1, '99999999.999999'), '$100,000,000.00')
  for (const value of ['', '-1', '0', 'NaN', 'Infinity', '1e2', '1.0000001', '100000000'])
    assert.equal(sales.priceMicros(value), null)
})

test('pockets respect transaction dates and subtract even later sales without merging releases', () => {
  const pockets = sales.availablePockets(grants(), [sale()], '2025-01-01')
  assert.deepEqual(
    pockets.map(({ id, remaining }) => [id, remaining]),
    [
      [10, 70],
      [12, 10],
    ],
  )
  assert.equal(pockets[0].grantTitle, 'Retention')
  assert.equal(sales.availablePockets(grants(), [sale()], '2023-12-31').length, 0)
  assert.equal(sales.availablePockets(grants(), [sale()], '2026-10-29').length, 3)
  const exhausted = sale()
  exhausted.allocations = [{ vestingId: 10, quantity: 100 }]
  assert.ok(
    !sales.availablePockets(grants(), [exhausted], '2026-10-29').some((row) => row.id === 10),
  )
})

test('sale validation rejects fractional shares, future dates and invalid allocations', () => {
  const pockets = sales.availablePockets(grants(), [], '2026-10-29')
  assert.deepEqual(sales.validateSale(draft(), pockets, '2026-10-29'), {})
  for (const changes of [
    { quantity: 1.5 },
    { transactionDate: '2026-02-30' },
    { transactionDate: '2026-10-30' },
    { proceedsPerShare: '0' },
    { allocations: [] },
    { allocations: [{ vestingId: 10, quantity: 40.5 }] },
    {
      allocations: [
        { vestingId: 10, quantity: 40 },
        { vestingId: 10, quantity: 0 },
      ],
    },
    { allocations: [{ vestingId: 13, quantity: 40 }] },
    { allocations: [{ vestingId: 10, quantity: 101 }] },
  ])
    assert.ok(
      Object.keys(sales.validateSale({ ...draft(), ...changes }, pockets, '2026-10-29')).length,
    )
})

test('holdings use full history, deterministic same-day order, pocket metadata and no future vesting', () => {
  const second = { ...sale(2), quantity: 20, allocations: [{ vestingId: 11, quantity: 20 }] }
  const result = sales.buildHoldings(grants(), [second, sale()], '2026-10-29')
  assert.deepEqual([result.vested, result.sold, result.held], [170, 60, 110])
  assert.deepEqual(
    result.events.map((event) => event.id),
    ['vesting-10', 'vesting-12', 'vesting-11', 'sale-1', 'sale-2'],
  )
  assert.deepEqual(
    result.events.map((event) => event.balance),
    [100, 120, 170, 130, 110],
  )
  assert.equal(result.events[3].allocations[1].grantTitle, 'New award')
  assert.equal(result.events[3].allocations[1].date, '2025-01-01')
  assert.equal(sales.buildHoldings(grants(), [], '2026-10-29').held, 170)
  assert.deepEqual(sales.buildHoldings([], [], '2026-10-29'), {
    events: [],
    vested: 0,
    acquired: 0,
    sold: 0,
    held: 0,
  })
})

test('modal validates allocations and emits one independent draft only on confirmation', async (t) => {
  const { modal, props, events } = mountModal(t)
  assert.equal(modal.details.value.transactionDate, props.today)
  modal.confirm()
  assert.ok(modal.errors.value.quantity)
  modal.details.value.quantity = '40'
  modal.details.value.proceedsPerShare = '123.456789'
  modal.quantities.value = { 'vesting:10': '30', 'vesting:12': '10' }
  assert.equal(modal.allocated.value, 40)
  assert.equal(modal.proceeds.value, '$4,938.27')
  modal.confirm()
  modal.confirm()
  assert.equal(events.length, 1)
  assert.equal(events[0][0], 'confirmed')
  assert.equal(events[0][1].quantity, 40)
  assert.deepEqual(
    events[0][1].allocations,
    draft().allocations.map((a) => ({ ...a, acquisitionFmv: '100.000000' })),
  )
  props.saving = true
  await Vue.nextTick()
  modal.close()
  assert.equal(props.open, true)
  props.saving = false
  props.saveError = 'Offline'
  await Vue.nextTick()
  modal.confirm()
  assert.equal(events.length, 2)
  assert.equal(events[1][1].creationToken, events[0][1].creationToken)
  assert.deepEqual(events[1][1].allocations, events[0][1].allocations)
})

test('changing transaction date clears ineligible pocket choices; cancel and reopen resets the draft', async (t) => {
  const { modal, props } = mountModal(t)
  modal.quantities.value = { 'vesting:10': '10', 'vesting:11': '20', 'vesting:12': '10' }
  modal.details.value.transactionDate = '2024-12-31'
  await Vue.nextTick()
  assert.deepEqual(modal.quantities.value, { 'vesting:10': '10' })
  const token = modal.creationToken.value
  modal.close()
  await Vue.nextTick()
  props.open = true
  await Vue.nextTick()
  assert.equal(modal.details.value.transactionDate, props.today)
  assert.equal(modal.details.value.quantity, '')
  assert.deepEqual(modal.quantities.value, {})
  assert.notEqual(modal.creationToken.value, token)
})

test('ledger year filtering preserves full-history balances and never filters the chart', (t) => {
  const props = Vue.reactive({ grants: grants(), sales: [sale()], today: '2026-10-29' })
  const view = setupComponent(
    t,
    '../src/components/stock-detail/HoldingsAndSales.vue',
    {
      defineProps: () => props,
      defineEmits: () => () => {},
    },
    'portfolio, selectedYear, years, ledger, points, line, axisDates, y, x, ticks',
  )
  assert.equal(view.selectedYear.value, '2026')
  assert.deepEqual(view.years.value, ['2026', '2025', '2024'])
  assert.deepEqual(
    view.ledger.value.map((event) => event.balance),
    [130, 170],
  )
  const line = view.line.value
  view.selectedYear.value = '2025'
  assert.deepEqual(
    view.ledger.value.map((event) => event.balance),
    [120],
  )
  assert.equal(view.line.value, line)
  view.selectedYear.value = 'all'
  assert.equal(view.ledger.value.length, 4)
  props.sales = []
  assert.equal(view.portfolio.value.held, 170)
  props.grants = []
  assert.equal(view.ledger.value.length, 0)
  assert.ok(!/NaN|Infinity/.test(view.line.value))
  props.grants = [
    { id: 3, title: 'Today', quantity: 1, vestings: [{ id: 30, date: props.today, quantity: 1 }] },
  ]
  assert.ok(!/NaN|Infinity/.test(view.line.value))
  assert.ok(Number.isFinite(view.x(props.today)))
  assert.ok(Number.isFinite(view.y(1)))
})

function mockStore(t, overrides = {}) {
  const original = { get: axios.get, post: axios.post, delete: axios.delete }
  t.after(() => Object.assign(axios, original))
  Object.assign(axios, {
    get: async (url) => ({
      data:
        url.endsWith('/sales') || url.endsWith('/grants') || url.endsWith('/purchases')
          ? []
          : { id: Number(url.split('/').at(-1)), name: 'Apple', symbol: 'AAPL' },
    }),
    post: async () => ({ data: apiSale() }),
    delete: async () => ({}),
    ...overrides,
  })
  return useStockGrantsStore(createPinia())
}

test('store round-trips sales, preserves exact decimal strings, and retries without duplicates', async (t) => {
  let saved = []
  const requests = []
  const store = mockStore(t, {
    get: async (url) => ({
      data: url.endsWith('/sales')
        ? saved
        : url.endsWith('/grants') || url.endsWith('/purchases')
          ? []
          : { id: 1 },
    }),
    post: async (...args) => {
      requests.push(args)
      saved = [apiSale()]
      return { data: apiSale() }
    },
  })
  await store.load(1)
  await store.createSale(1, draft())
  await store.createSale(1, draft())
  assert.equal(store.forStock(1).sales.length, 1)
  assert.equal(store.forStock(1).sales[0].proceedsPerShare, '123.456789')
  assert.deepEqual(requests[0][1].allocations, apiSale().allocations)
  assert.equal(requests[0][2].headers['Idempotency-Key'], draft().creationToken)
  await store.load(1)
  assert.equal(store.forStock(1).sales[0].transactionDate, '2026-10-29')
})

test('sale mutations preserve state on failure and block simultaneous grant and sale mutations', async (t) => {
  const pending = deferred()
  const store = mockStore(t, { post: () => pending.promise })
  await store.load(1)
  const writing = store.createSale(1, draft())
  assert.equal(await store.createSale(1, draft()), null)
  assert.equal(await store.createGrant(1, {}), null)
  assert.equal(await store.deleteGrant(1, 1), false)
  assert.equal(await store.deleteSale(1, 1), false)
  pending.reject(new Error('Offline'))
  assert.equal(await writing, null)
  assert.deepEqual(store.forStock(1).sales, [])
  assert.match(store.forStock(1).saleSaveError, /draft is still here/)
  axios.post = async () => ({ data: apiSale() })
  await store.createSale(1, draft())
  axios.delete = async () => {
    throw { response: { data: { error: 'Delete failed' } } }
  }
  assert.equal(await store.deleteSale(1, 1), false)
  assert.equal(store.forStock(1).sales.length, 1)
  assert.equal(store.forStock(1).saleDeleteError, 'Delete failed')
  axios.delete = async () => ({})
  assert.equal(await store.deleteSale(1, 1), true)
  assert.equal(store.forStock(1).sales.length, 0)
})

test('refresh waits for a sale write, and sale completion remains scoped to its stock', async (t) => {
  const pending = deferred()
  let saved = false,
    gets = 0
  const store = mockStore(t, {
    get: async (url) => {
      gets++
      return {
        data: url.endsWith('/sales')
          ? saved
            ? [apiSale()]
            : []
          : url.endsWith('/grants') || url.endsWith('/purchases')
            ? []
            : { id: 1 },
      }
    },
    post: () => pending.promise,
  })
  await store.load(1)
  const writing = store.createSale(1, draft())
  const reading = store.load(1)
  assert.equal(gets, 4)
  await store.load(2)
  saved = true
  pending.resolve({ data: apiSale() })
  await writing
  await reading
  assert.equal(store.forStock(1).sales.length, 1)
  assert.equal(store.forStock(2).sales.length, 0)
  const removing = deferred()
  axios.delete = () => removing.promise
  const deleting = store.deleteSale(1, 1)
  saved = false
  const refresh = store.load(1)
  removing.resolve({})
  await deleting
  await refresh
  assert.equal(store.forStock(1).sales.length, 0)
})

test('detail keeps failed sale dialogs open and ignores completion after navigation', async (t) => {
  const store = mockStore(t)
  const route = Vue.reactive({ params: { stockId: '1' } })
  const view = setupComponent(
    t,
    '../src/views/StockDetailView.vue',
    {
      useRoute: () => route,
      useStockGrantsStore: () => store,
      useStockQuotesStore: () => useStockQuotesStore(createPinia()),
      formatStockValue,
      onMounted: () => {},
      onBeforeUnmount: () => {},
    },
    'showRecordSale, recordSale, requestDeleteSale, saleToDelete, deleteSale, entry',
  )
  await flush()
  view.showRecordSale.value = true
  axios.post = async () => {
    throw new Error('Offline')
  }
  await view.recordSale(draft())
  assert.equal(view.showRecordSale.value, true)
  assert.ok(view.entry.value.saleSaveError)
  axios.post = async () => ({ data: apiSale() })
  await view.recordSale(draft())
  assert.equal(view.showRecordSale.value, false)
  view.requestDeleteSale(view.entry.value.sales[0])
  axios.delete = async () => {
    throw new Error('Offline')
  }
  await view.deleteSale()
  assert.ok(view.saleToDelete.value)
  axios.delete = async () => ({})
  await view.deleteSale()
  assert.equal(view.saleToDelete.value, null)
  const pending = deferred()
  axios.post = () => pending.promise
  const writing = view.recordSale(draft())
  route.params.stockId = '2'
  await flush()
  view.showRecordSale.value = true
  pending.resolve({ data: apiSale() })
  await writing
  assert.equal(view.showRecordSale.value, true)
  assert.equal(view.entry.value.sales.length, 0)
  assert.equal(store.forStock(1).sales.length, 1)
})

test('bulk deletion requires confirmation, preserves failures and stays scoped during navigation', async (t) => {
  const store = mockStore(t)
  const route = Vue.reactive({ params: { stockId: '1' } })
  const view = setupComponent(
    t,
    '../src/views/StockDetailView.vue',
    {
      useRoute: () => route,
      useStockGrantsStore: () => store,
      useStockQuotesStore: () => useStockQuotesStore(createPinia()),
      formatStockValue,
      onMounted: () => {},
      onBeforeUnmount: () => {},
    },
    'showDeleteAllSales, requestDeleteAllSales, deleteAllSales, entry',
  )
  await flush()
  view.requestDeleteAllSales()
  assert.equal(view.showDeleteAllSales.value, false)
  await store.createSale(1, draft())
  await store.createSale(1, { ...draft(), creationToken: 'another' })
  let requests = 0
  axios.delete = async () => {
    requests++
    throw new Error('Offline')
  }
  view.requestDeleteAllSales()
  assert.equal(view.showDeleteAllSales.value, true)
  assert.equal(requests, 0)
  await view.deleteAllSales()
  assert.equal(view.showDeleteAllSales.value, true)
  assert.equal(view.entry.value.sales.length, 1)
  const pending = deferred()
  const urls = []
  axios.delete = (url) => {
    urls.push(url)
    return pending.promise
  }
  const deleting = view.deleteAllSales()
  assert.equal(store.forStock(1).deletingAllSales, true)
  assert.equal(await store.createSale(1, draft()), null)
  assert.equal(await store.deleteAllSales(1), false)
  assert.equal(await store.deleteSale(1, 1), false)
  route.params.stockId = '2'
  await flush()
  view.showDeleteAllSales.value = true
  pending.resolve({})
  await deleting
  assert.deepEqual(urls, ['/api/stocks/1/sales'])
  assert.equal(store.forStock(1).sales.length, 0)
  assert.equal(view.showDeleteAllSales.value, true)
  assert.equal(store.forStock(1).deletingAllSales, false)
})
