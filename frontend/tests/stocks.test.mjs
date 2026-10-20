import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import test from 'node:test'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'

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

// Exercise the actual component setup with Vue reactivity and a controlled HTTP client.
function setupComponent(t, path, dependencies, exposed) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const script = descriptor.scriptSetup.content.replace(
    /^import[\s\S]*?from ['"][^'"]+['"]\n/gm,
    '',
  )
  const scope = Vue.effectScope()
  t.after(() => scope.stop())
  return scope.run(() =>
    new Function('ref', 'watch', ...Object.keys(dependencies), `${script}\nreturn { ${exposed} }`)(
      Vue.ref,
      Vue.watch,
      ...Object.values(dependencies),
    ),
  )
}

function mountStocks(t, axios) {
  const familyStore = Vue.reactive({ familyId: 1, familyName: 'Family' })
  const view = setupComponent(
    t,
    '../src/views/StocksView.vue',
    {
      useFamilyStore: () => familyStore,
      axios,
    },
    `stocks, showArchived, loading, error, showForm, editingStock, archivingStock,
    archiving, archiveError, reload, openCreate, openEdit, stockSaved, openArchive, archiveStock`,
  )
  return { view, familyStore }
}

test('stocks load for the selected family and refresh after saves and archive filtering', async (t) => {
  const requests = []
  const { view, familyStore } = mountStocks(t, {
    async get(url, options) {
      requests.push({ url, archived: options.params.archived })
      return { data: [{ id: 1, name: 'Apple', symbol: 'AAPL' }] }
    },
  })
  await flush()
  assert.equal(view.stocks.value[0].symbol, 'AAPL')
  view.openEdit(view.stocks.value[0])
  assert.equal(view.editingStock.value.id, 1)
  view.openCreate()
  assert.equal(view.editingStock.value, null)
  assert.equal(view.showForm.value, true)
  view.stockSaved()
  await flush()
  assert.equal(requests.length, 2)
  view.showArchived.value = true
  await flush()
  assert.deepEqual(requests.at(-1), { url: '/api/families/1/stocks', archived: true })
  familyStore.familyId = 0
  await flush()
  assert.deepEqual(view.stocks.value, [])
  assert.equal(view.loading.value, false)
  assert.equal(view.showForm.value, false)
})

for (const outcome of ['success', 'failure']) {
  test(`old stock ${outcome} responses cannot replace the current family's stocks`, async (t) => {
    const old = deferred()
    const { view, familyStore } = mountStocks(t, {
      get: (url) => (url.includes('/1/') ? old.promise : Promise.resolve({ data: [{ id: 2 }] })),
    })
    await flush()
    familyStore.familyId = 2
    await flush()
    if (outcome === 'success') old.resolve({ data: [{ id: 1 }] })
    else old.reject(new Error('Old request failed'))
    await flush()
    assert.deepEqual(view.stocks.value, [{ id: 2 }])
    assert.equal(view.error.value, '')
    assert.equal(view.loading.value, false)
  })
}

test('load and archive failures can be retried without losing the archive target', async (t) => {
  let failLoad = true,
    failArchive = true
  const deleted = []
  const stock = { id: 3, name: 'Apple', symbol: 'AAPL' }
  const { view } = mountStocks(t, {
    async get() {
      if (failLoad) throw new Error('Offline')
      return { data: [stock] }
    },
    async delete(url) {
      deleted.push(url)
      if (failArchive) throw new Error('Offline')
    },
  })
  await flush()
  assert.match(view.error.value, /Failed to load/)
  failLoad = false
  view.reload()
  await flush()
  assert.equal(view.error.value, '')
  view.openArchive(stock)
  await view.archiveStock()
  assert.equal(view.archivingStock.value.id, 3)
  assert.match(view.archiveError.value, /Failed to archive/)
  assert.equal(view.archiving.value, false)
  failArchive = false
  await view.archiveStock()
  await flush()
  assert.equal(view.archivingStock.value, null)
  assert.deepEqual(deleted, ['/api/stocks/3', '/api/stocks/3'])
})

test('stock form creates and edits normalized values and preserves input after API errors', async (t) => {
  const props = Vue.reactive({ open: false, familyId: 7, stock: null })
  const events = [],
    requests = []
  let fail = false
  const save = async (...args) => {
    requests.push(args)
    if (fail) throw { response: { data: { error: 'Duplicate ticker' } } }
  }
  const form = setupComponent(
    t,
    '../src/components/StockFormModal.vue',
    {
      defineProps: () => props,
      defineEmits:
        () =>
        (...args) =>
          events.push(args),
      axios: { post: save, put: save },
    },
    'name, symbol, error, loading, submit',
  )
  props.open = true
  await flush()
  form.name.value = ' Apple '
  form.symbol.value = ' aapl '
  await form.submit()
  assert.deepEqual(requests[0], ['/api/families/7/stocks', { name: 'Apple', symbol: 'AAPL' }])
  assert.deepEqual(events, [['saved'], ['update:open', false]])

  props.open = false
  await flush()
  props.stock = { id: 9, name: 'Microsoft', symbol: 'MSFT' }
  props.open = true
  await flush()
  assert.equal(form.name.value, 'Microsoft')
  form.symbol.value = 'AA PL'
  await form.submit()
  assert.equal(requests.length, 1)
  form.symbol.value = 'AAPL'
  fail = true
  await form.submit()
  assert.equal(form.error.value, 'Duplicate ticker')
  assert.equal(form.name.value, 'Microsoft')
  assert.equal(form.loading.value, false)
  assert.equal(events.length, 2)
  fail = false
  await form.submit()
  assert.deepEqual(requests.at(-1), ['/api/stocks/9', { name: 'Microsoft', symbol: 'AAPL' }])
  assert.equal(events.length, 4)
})
