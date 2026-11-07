import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import test from 'node:test'
import axios from 'axios'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'
import { downloadStockExport } from '../src/lib/stockExport.js'
import { localDate, summarizePortfolio } from '../src/components/stock-detail/vesting.js'

const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

function mockDownload(t, get) {
  t.mock.method(axios, 'get', get)
  const events = []
  let download
  const link = {
    click() {
      download = { href: this.href, filename: this.download }
      events.push('click')
    },
    remove: () => events.push('remove'),
  }
  t.mock.method(URL, 'createObjectURL', (data) => {
    assert.ok(data instanceof Blob)
    events.push('create URL')
    return 'blob:export'
  })
  t.mock.method(URL, 'revokeObjectURL', (url) => {
    assert.equal(url, 'blob:export')
    events.push('revoke URL')
  })
  const oldDocument = globalThis.document
  globalThis.document = {
    createElement: (tag) => {
      assert.equal(tag, 'a')
      return link
    },
    body: { appendChild: (child) => assert.equal(child, link) },
  }
  t.after(() => {
    if (oldDocument === undefined) delete globalThis.document
    else globalThis.document = oldDocument
  })
  return { events, download: () => download }
}

for (const [disposition, expected] of [
  ['attachment; filename=AAPL-export.xlsx', 'AAPL-export.xlsx'],
  ['attachment; filename="AAPL-export.xlsx"', 'AAPL-export.xlsx'],
  [
    "attachment; filename=fallback.xlsx; filename*=UTF-8''%C3%89pargne-export.xlsx",
    'Épargne-export.xlsx',
  ],
  ["attachment; filename=fallback.xlsx; filename*=UTF-8''%invalid", 'fallback.xlsx'],
  [undefined, 'stock-7-export.xlsx'],
]) {
  test(`downloads the backend workbook using filename ${disposition}`, async (t) => {
    const controller = new AbortController()
    const mock = mockDownload(t, async (url, options) => {
      assert.equal(url, '/api/stocks/7/export')
      assert.equal(options.responseType, 'blob')
      assert.equal(options.signal, controller.signal)
      return {
        data: new Blob(['xlsx bytes']),
        headers: { 'content-disposition': disposition },
      }
    })
    await downloadStockExport(7, controller.signal)
    assert.deepEqual(mock.download(), { href: 'blob:export', filename: expected })
    await new Promise((resolve) => setTimeout(resolve, 5))
    assert.deepEqual(mock.events, ['create URL', 'click', 'remove', 'revoke URL'])
  })
}

for (const [data, message] of [
  [
    new Blob([JSON.stringify({ error: 'Stock or family is archived' })]),
    'Stock or family is archived',
  ],
  [{ error: 'Stock not found' }, 'Stock not found'],
  [new Blob(['<html>Proxy error</html>']), 'Could not export the stock. Please try again.'],
  [undefined, 'Could not export the stock. Please try again.'],
]) {
  test(`export failures expose a retryable message: ${message}`, async (t) => {
    const mock = mockDownload(t, async () => {
      throw { response: { data } }
    })
    await assert.rejects(downloadStockExport(1, new AbortController().signal), { message })
    assert.deepEqual(mock.events, [])
  })
}

for (const outcome of ['success', 'failure']) {
  test(`canceled export ignores a late ${outcome} response`, async (t) => {
    const pending = deferred()
    const mock = mockDownload(t, () => pending.promise)
    const controller = new AbortController()
    const request = downloadStockExport(1, controller.signal)
    controller.abort()
    if (outcome === 'success') pending.resolve({ data: new Blob(['bytes']), headers: {} })
    else pending.reject(new Error('Canceled'))
    await request
    assert.deepEqual(mock.events, [])
  })
}

function mountDetail(t, download) {
  const route = Vue.reactive({ params: { stockId: '1' } })
  const entries = new Map()
  const store = {
    forStock(id) {
      if (!entries.has(id))
        entries.set(
          id,
          Vue.reactive({
            stock: { id, name: 'Apple', symbol: 'AAPL' },
            loaded: true,
            loading: false,
            loadError: '',
            grants: [],
            purchases: [],
            sales: [],
            saving: false,
            savingSale: false,
            savingPurchase: false,
            deletingId: null,
            deletingSaleId: null,
            deletingPurchaseId: null,
          }),
        )
      return entries.get(id)
    },
    load: async () => {},
  }
  let unmount
  const dependencies = {
    ref: Vue.ref,
    computed: Vue.computed,
    watch: Vue.watch,
    onMounted: () => {},
    onBeforeUnmount: (callback) => {
      unmount = callback
    },
    useRoute: () => route,
    useStockGrantsStore: () => store,
    useStockQuotesStore: () => ({ forSymbol: () => ({}) }),
    localDate,
    summarizePortfolio,
    downloadStockExport: download,
  }
  const { descriptor } = parse(
    readFileSync(new URL('../src/views/StockDetailView.vue', import.meta.url), 'utf8'),
  )
  const script = descriptor.scriptSetup.content.replace(
    /^import[\s\S]*?from ['"][^'"]+['"]\n/gm,
    '',
  )
  const scope = Vue.effectScope()
  t.after(() => {
    unmount()
    scope.stop()
  })
  const view = scope.run(() =>
    new Function(
      ...Object.keys(dependencies),
      `${script}\nreturn { exportStock, exporting, exportError, entry, activeTab }`,
    )(...Object.values(dependencies)),
  )
  return { view, route, unmount: () => unmount(), template: descriptor.template.content }
}

test('detail exports the current stock once, regardless of tab, and permits another download', async (t) => {
  const pending = deferred()
  const requests = []
  const { view, template } = mountDetail(t, (...args) => {
    requests.push(args)
    return pending.promise
  })
  assert.match(template, /justify-between[\s\S]*All stocks[\s\S]*@click="exportStock"/)
  assert.match(template, /:disabled="!ready \|\| busy \|\| exporting"/)
  assert.match(template, /role="alert"/)
  view.activeTab.value = 'holdings'
  const exporting = view.exportStock()
  assert.equal(view.exporting.value, true)
  await view.exportStock()
  assert.equal(requests.length, 1)
  assert.equal(requests[0][0], 1)
  assert.ok(requests[0][1] instanceof AbortSignal)
  pending.resolve()
  await exporting
  assert.equal(view.exporting.value, false)
  await view.exportStock()
  assert.equal(requests.length, 2)
})

test('detail blocks export while loading or saving and exposes errors until a successful retry', async (t) => {
  let fail = true
  let requests = 0
  const { view } = mountDetail(t, async () => {
    requests += 1
    if (fail) throw new Error('Stock not found')
  })
  view.entry.value.loading = true
  await view.exportStock()
  assert.equal(requests, 0)
  view.entry.value.loading = false
  view.entry.value.savingPurchase = true
  await view.exportStock()
  assert.equal(requests, 0)
  view.entry.value.savingPurchase = false
  await view.exportStock()
  assert.equal(view.exportError.value, 'Stock not found')
  assert.equal(view.exporting.value, false)
  fail = false
  await view.exportStock()
  assert.equal(view.exportError.value, '')
  assert.equal(requests, 2)
})

for (const navigation of ['stock', 'unmount']) {
  test(`detail cancels export on ${navigation} and ignores stale failures`, async (t) => {
    const pending = deferred()
    let signal
    const { view, route, unmount } = mountDetail(t, (_, abortSignal) => {
      signal = abortSignal
      return pending.promise
    })
    const exporting = view.exportStock()
    if (navigation === 'stock') route.params.stockId = '2'
    else unmount()
    await flush()
    assert.equal(signal.aborted, true)
    assert.equal(view.exporting.value, false)
    pending.reject(new Error('Old export failed'))
    await exporting
    assert.equal(view.exportError.value, '')
  })
}

test('old export completion cannot clear the next stock’s pending export', async (t) => {
  const old = deferred()
  const current = deferred()
  const { view, route } = mountDetail(t, (id) => (id === 1 ? old.promise : current.promise))
  const first = view.exportStock()
  route.params.stockId = '2'
  const second = view.exportStock()
  old.resolve()
  await first
  assert.equal(view.exporting.value, true)
  current.resolve()
  await second
  assert.equal(view.exporting.value, false)
})
