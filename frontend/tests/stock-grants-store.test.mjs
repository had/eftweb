import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia } from 'pinia'
import axios from 'axios'
import { useStockGrantsStore } from '../src/stores/stockGrants.js'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
const apiGrant = (id, stockId = 1) => ({
  id,
  stock_id: stockId,
  title: `Grant ${id}`,
  grant_date: '2026-10-25',
  quantity: 100,
  vesting_start_date: '2025-01-31',
  schedule_type: 'quarterly',
  customized: true,
  vestings: [{ id: id * 10, date: '2027-01-31', quantity: 100 }],
})
const draft = () => ({
  creationToken: '63f9e069-3cfa-4052-a5ac-845b29064b48',
  title: 'Draft',
  grantDate: '2026-10-25',
  quantity: 100,
  startDate: '2025-01-31',
  scheduleType: 'quarterly',
  customized: true,
  vestings: [{ id: 'local-row', date: '2027-01-31', quantity: 100 }],
})
function mockHttp(t, overrides = {}) {
  const originals = { get: axios.get, post: axios.post, delete: axios.delete }
  t.after(() => Object.assign(axios, originals))
  Object.assign(axios, {
    get: async (url) => ({
      data: url.endsWith('/grants')
        ? []
        : { id: Number(url.split('/').at(-1)), name: 'Canonical stock', symbol: 'REAL' },
    }),
    post: async () => ({ data: apiGrant(1) }),
    delete: async () => ({}),
    ...overrides,
  })
  return useStockGrantsStore(createPinia())
}

test('loads canonical metadata, maps fields, and retains stable colors across reloads', async (t) => {
  const store = mockHttp(t, {
    get: async (url) => ({
      data: url.endsWith('/grants')
        ? [apiGrant(4), apiGrant(2)]
        : { id: 1, name: 'Real stock', symbol: 'REAL' },
    }),
  })
  const pending = store.load(1)
  assert.equal(store.forStock(1).loading, true)
  assert.equal(await pending, true)
  const entry = store.forStock(1)
  assert.equal(entry.stock.name, 'Real stock')
  assert.equal(entry.grants[0].id, 2)
  assert.equal(entry.grants[0].startDate, '2025-01-31')
  assert.equal(entry.grants[0].scheduleType, 'quarterly')
  const color = entry.grants[1].color
  await store.load(1)
  assert.equal(entry.grants[1].color, color)
  assert.equal(entry.loaded, true)
})

test('failed loads are errors rather than empty portfolios, and retry can recover', async (t) => {
  const store = mockHttp(t, {
    get: async () => {
      throw { response: { data: { error: 'Stock is archived' } } }
    },
  })
  assert.equal(await store.load(1), false)
  assert.equal(store.forStock(1).loaded, false)
  assert.equal(store.forStock(1).loadError, 'Stock is archived')
  axios.get = async (url) => ({ data: url.endsWith('/grants') ? [] : { id: 1, symbol: 'AAPL' } })
  assert.equal(await store.load(1), true)
  assert.equal(store.forStock(1).loadError, '')
  assert.deepEqual(store.forStock(1).grants, [])
  assert.equal(await store.load(NaN), false)
})

test('older loads cannot overwrite a refreshed stock and separate stocks retain separate state', async (t) => {
  const old = deferred()
  let first = true
  const store = mockHttp(t, {
    get: (url) => {
      if (url === '/api/stocks/1/grants' && first) {
        first = false
        return old.promise
      }
      return Promise.resolve({
        data: url.endsWith('/grants')
          ? [apiGrant(2, Number(url.split('/')[3]))]
          : { id: Number(url.split('/').at(-1)), symbol: 'REAL' },
      })
    },
  })
  const slow = store.load(1)
  await store.load(2)
  await store.load(1)
  old.resolve({ data: [apiGrant(99)] })
  await slow
  assert.equal(store.forStock(1).grants[0].id, 2)
  assert.equal(store.forStock(2).grants[0].stockId, 2)
  assert.equal(store.forStock(1).loading, false)
})

test('failed saves preserve existing data and retry with the same token does not duplicate saved grants', async (t) => {
  const requests = []
  let fail = true
  const store = mockHttp(t, {
    post: async (...args) => {
      requests.push(args)
      if (fail) throw new Error('Network failed')
      return { data: apiGrant(5) }
    },
  })
  await store.load(1)
  const data = draft()
  assert.equal(await store.createGrant(1, data), null)
  assert.match(store.forStock(1).saveError, /draft is still here/)
  assert.deepEqual(store.forStock(1).grants, [])
  assert.equal(data.vestings[0].id, 'local-row')
  fail = false
  await store.createGrant(1, data)
  await store.createGrant(1, data)
  assert.equal(store.forStock(1).grants.length, 1)
  assert.ok(
    requests.every(([, , options]) => options.headers['Idempotency-Key'] === data.creationToken),
  )
  assert.deepEqual(requests[0][1].vestings, [{ date: '2027-01-31', quantity: 100 }])
  assert.equal(store.forStock(1).saveError, '')
})

test('mutations stay scoped while switching stocks, and repeated pending saves are blocked', async (t) => {
  const pending = deferred()
  let posts = 0
  const store = mockHttp(t, {
    post: () => {
      posts += 1
      return pending.promise
    },
  })
  await store.load(1)
  const save = store.createGrant(1, draft())
  assert.equal(store.forStock(1).saving, true)
  assert.equal(await store.createGrant(1, draft()), null)
  await store.load(2)
  pending.resolve({ data: apiGrant(5) })
  await save
  assert.equal(posts, 1)
  assert.equal(store.forStock(1).grants[0].id, 5)
  assert.deepEqual(store.forStock(2).grants, [])
})

test('delete only updates data after success and failed deletion remains retryable', async (t) => {
  const pending = deferred()
  const store = mockHttp(t, { delete: () => pending.promise })
  await store.load(1)
  await store.createGrant(1, draft())
  const entry = store.forStock(1)
  const deletion = store.deleteGrant(1, 1)
  assert.equal(entry.deletingId, 1)
  assert.equal(entry.grants.length, 1)
  pending.reject({ response: { data: { error: 'Could not delete' } } })
  assert.equal(await deletion, false)
  assert.equal(entry.grants.length, 1)
  assert.equal(entry.deleteError, 'Could not delete')
  assert.equal(entry.deletingId, null)
  axios.delete = async () => ({})
  assert.equal(await store.deleteGrant(1, 1), true)
  assert.deepEqual(entry.grants, [])
  assert.equal(entry.deleteError, '')
})

test('refresh waits for pending writes so an older snapshot cannot resurrect deleted grants', async (t) => {
  const pending = deferred()
  let gets = 0
  const store = mockHttp(t, {
    get: async (url) => {
      gets += 1
      return { data: url.endsWith('/grants') ? [] : { id: 1 } }
    },
    delete: () => pending.promise,
  })
  await store.load(1)
  await store.createGrant(1, draft())
  const deleting = store.deleteGrant(1, 1)
  const loading = store.load(1)
  assert.equal(gets, 2)
  pending.resolve({})
  await deleting
  await loading
  assert.equal(gets, 4)
  assert.deepEqual(store.forStock(1).grants, [])
})
