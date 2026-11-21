import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import test from 'node:test'
import axios from 'axios'
import { createPinia } from 'pinia'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'
import { editedAllocations, importIssues, lotKey, saleDecision } from '../src/lib/stockImport.js'
import { useStockGrantsStore } from '../src/stores/stockGrants.js'

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
const sale = (overrides = {}) => ({
  key: 'order-1',
  rows: [3],
  transaction_date: '2026-02-12',
  quantity: 20,
  proceeds_per_share: '130.440000',
  currency: 'USD',
  source_order_number: '100',
  status: 'ready',
  skip: false,
  errors: [],
  warnings: [],
  matching_issues: [],
  possible_duplicate_ids: [],
  sources: [{ plan_type: 'RS', date: '2025-03-01', grant_number: '00123', quantity: 20 }],
  allocations: [{ vesting_id: 1, quantity: 20, acquisition_fmv: '100.000000' }],
  ...overrides,
})
const review = (overrides = {}) => ({
  format: 'etrade',
  symbol: 'AAPL',
  stock_name: 'Apple',
  stock_revision: 'revision-1',
  file_digest: 'file-hash',
  counts: { grants: 0, purchases: 0, sales: 1 },
  errors: [],
  ignored: [],
  grants: [],
  purchases: [],
  lots: [
    {
      source: 'vesting_id',
      id: 1,
      date: '2025-03-01',
      quantity: 100,
      available: 100,
      plan_type: 'RS',
    },
  ],
  sales: [sale()],
  ...overrides,
})
const draftsFor = (preview) =>
  Object.fromEntries(
    preview.sales.map((sale) => [
      sale.key,
      {
        skip: sale.skip,
        reviewed: false,
        allocations: sale.allocations.map((row) => ({
          lot: lotKey(row),
          quantity: row.quantity,
          acquisitionFmv: row.acquisition_fmv,
        })),
      },
    ]),
  )

test('unchanged automatic allocations are omitted; edited allocations preserve source types', () => {
  const original = sale()
  const draft = draftsFor(review())[original.key]
  assert.deepEqual(saleDecision(original, draft), { skip: false, reviewed: false })
  draft.allocations = [
    { lot: 'vesting_id:1', quantity: '10' },
    { lot: 'purchase_id:2', quantity: '10' },
  ]
  assert.deepEqual(editedAllocations(draft.allocations), [
    { vesting_id: 1, quantity: 10 },
    { purchase_id: 2, quantity: 10 },
  ])
  assert.equal(saleDecision(original, draft).allocations.length, 2)
})

test('review validates splits, duplicates, dates, whole shares, plan types and batch availability', () => {
  const preview = review()
  const drafts = draftsFor(preview)
  assert.deepEqual(importIssues(preview, drafts), [])
  drafts['order-1'].allocations[0].quantity = '1.5'
  assert.ok(importIssues(preview, drafts).length)
  drafts['order-1'].allocations[0].quantity = 20
  preview.sales[0].warnings = ['Review proceeds']
  assert.ok(importIssues(preview, drafts).some((message) => message.includes('reviewed')))
  drafts['order-1'].reviewed = true
  assert.deepEqual(importIssues(preview, drafts), [])
  preview.lots[0].date = '2027-01-01'
  assert.ok(importIssues(preview, drafts).some((message) => message.includes('acquired')))
  preview.lots[0].date = '2025-03-01'
  preview.sales.push(
    sale({
      key: 'order-2',
      quantity: 90,
      allocations: [{ vesting_id: 1, quantity: 90 }],
      sources: [{ plan_type: 'RS', quantity: 90 }],
    }),
  )
  drafts['order-2'] = draftsFor(preview)['order-2']
  assert.ok(importIssues(preview, drafts).some((message) => message.includes('available')))
  drafts['order-2'].skip = true
  assert.deepEqual(importIssues(preview, drafts), [])
  drafts['order-1'].allocations.push({ lot: 'vesting_id:1', quantity: 1 })
  assert.ok(importIssues(preview, drafts).length)
})

test('known imports are skipped and native restore cannot partially exclude records', () => {
  const preview = review({ sales: [sale({ status: 'duplicate', skip: true })] })
  assert.deepEqual(importIssues(preview, draftsFor(preview)), ['No new sales selected for import.'])
  assert.deepEqual(importIssues(review({ format: 'eftweb', errors: ['Stock is not empty'] }), {}), [
    'Stock is not empty',
  ])
  assert.deepEqual(importIssues(review({ format: 'eftweb' }), {}), [])
})

function mountModal(t, post) {
  const props = Vue.reactive({ open: true, stockId: 7 })
  const events = []
  let unmount
  const dependencies = {
    computed: Vue.computed,
    ref: Vue.ref,
    watch: Vue.watch,
    onBeforeUnmount: (callback) => {
      unmount = callback
    },
    defineProps: () => props,
    defineEmits:
      () =>
      (...args) =>
        events.push(args),
    axios: { post },
    importIssues,
    lotKey,
    saleDecision,
  }
  const { descriptor } = parse(
    readFileSync(
      new URL('../src/components/stock-detail/ImportStockModal.vue', import.meta.url),
      'utf8',
    ),
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
      `${script}\nreturn { file, preview, drafts, loading, saving, error, result, canConfirm, chooseFile, loadPreview, confirmImport, close }`,
    )(...Object.values(dependencies)),
  )
  view.chooseFile({ target: { files: [new File(['xlsx'], 'sample.xlsx')] } })
  return { view, props, events, unmount: () => unmount(), template: descriptor.template.content }
}

test('modal previews, confirms multipart data, blocks double clicks and reports completion', async (t) => {
  const pending = deferred()
  const requests = []
  const { view, events, template } = mountModal(t, async (...args) => {
    requests.push(args)
    return args[0].endsWith('/preview') ? { data: review() } : pending.promise
  })
  assert.match(template, /Preview import/)
  assert.match(template, /Skip sale/)
  assert.match(template, /role="alert"/)
  await view.loadPreview()
  assert.equal(view.canConfirm.value, true)
  const writing = view.confirmImport()
  await view.confirmImport()
  view.close()
  assert.equal(view.saving.value, true)
  assert.equal(requests.length, 2)
  const [url, form, options] = requests[1]
  assert.equal(url, '/api/stocks/7/import')
  assert.equal(form.get('file').name, 'sample.xlsx')
  assert.equal(form.get('stock_revision'), 'revision-1')
  assert.deepEqual(JSON.parse(form.get('decisions')), {
    'order-1': { skip: false, reviewed: false, order_fee: '0' },
  })
  assert.match(options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)
  pending.resolve({
    data: {
      format: 'etrade',
      counts: { grants: 0, vestings: 0, purchases: 0, sales: 1, skipped_sales: 0 },
    },
  })
  await writing
  assert.equal(view.result.value.counts.sales, 1)
  assert.equal(view.saving.value, false)
  assert.ok(events.some(([event]) => event === 'imported'))
  assert.deepEqual(
    events.filter(([event]) => event === 'busy').map(([, value]) => value),
    [true, false],
  )
})

test('failed confirmation keeps decisions and retries with the same key; stale preview can be refreshed', async (t) => {
  const keys = []
  let fail = true
  const { view } = mountModal(t, async (url, _, options) => {
    if (url.endsWith('/preview')) return { data: review() }
    keys.push(options.headers['Idempotency-Key'])
    if (fail)
      throw {
        response: { data: { error: 'Stock data changed after preview. Preview the file again.' } },
      }
    return { data: { counts: { sales: 1 } } }
  })
  await view.loadPreview()
  await view.confirmImport()
  assert.match(view.error.value, /Stock data changed/)
  assert.equal(view.file.value.name, 'sample.xlsx')
  fail = false
  await view.confirmImport()
  assert.equal(keys[0], keys[1])
  assert.equal(view.error.value, '')
  await view.loadPreview()
  await view.confirmImport()
  assert.notEqual(keys[1], keys[2])
})

for (const navigation of ['close', 'unmount', 'file']) {
  test(`preview upload is canceled on ${navigation} and late responses are ignored`, async (t) => {
    const pending = deferred()
    let signal
    const { view, unmount } = mountModal(t, (_, __, options) => {
      signal = options.signal
      return pending.promise
    })
    const reading = view.loadPreview()
    if (navigation === 'close') view.close()
    else if (navigation === 'unmount') unmount()
    else view.chooseFile({ target: { files: [new File(['new'], 'new.xlsx')] } })
    assert.equal(signal.aborted, true)
    pending.resolve({ data: review() })
    await reading
    assert.equal(view.preview.value, null)
    assert.equal(view.error.value, '')
  })
}

test('confirmation finishing after navigation cannot emit into the new stock view', async (t) => {
  const pending = deferred()
  const { view, events, unmount } = mountModal(t, (url) =>
    url.endsWith('/preview') ? Promise.resolve({ data: review() }) : pending.promise,
  )
  await view.loadPreview()
  const saving = view.confirmImport()
  unmount()
  const before = events.length
  pending.resolve({ data: { counts: { sales: 1 } } })
  await saving
  assert.equal(events.length, before)
})

test('native preview is complete, while upload errors and excessive sizes stay retryable', async (t) => {
  let fail = true
  const { view } = mountModal(t, async () => {
    if (fail) throw { response: { data: { error: 'Unsupported workbook' } } }
    return { data: review({ format: 'eftweb' }) }
  })
  await view.loadPreview()
  assert.equal(view.error.value, 'Unsupported workbook')
  fail = false
  await view.loadPreview()
  assert.equal(view.canConfirm.value, true)
  view.chooseFile({ target: { files: [{ name: 'large.xlsx', size: 11 * 1024 * 1024 }] } })
  await view.loadPreview()
  assert.match(view.error.value, /10 MiB/)
})

test('grant numbers map from the API, update only after success, and remain stock scoped', async (t) => {
  const original = {
    id: 1,
    stock_id: 7,
    title: 'Grant',
    grant_number: '00123',
    grant_date: '2020-01-01',
    quantity: 1,
    vesting_start_date: '2020-01-01',
    schedule_type: 'quarterly',
    customized: true,
    vestings: [],
  }
  t.mock.method(axios, 'get', async (url) => ({
    data: url.endsWith('/grants')
      ? [original]
      : url.endsWith('/sales') || url.endsWith('/purchases')
        ? []
        : { id: 7, symbol: 'AAPL' },
  }))
  let fail = true
  const pending = deferred()
  const requests = []
  t.mock.method(axios, 'patch', async (...args) => {
    requests.push(args)
    if (fail) throw { response: { data: { error: 'Duplicate grant number' } } }
    return pending.promise
  })
  const store = useStockGrantsStore(createPinia())
  await store.load(7)
  assert.equal(store.forStock(7).grants[0].grantNumber, '00123')
  assert.equal(await store.updateGrantNumber(7, 1, '00045'), null)
  assert.equal(store.forStock(7).grants[0].grantNumber, '00123')
  assert.equal(store.forStock(7).saveError, 'Duplicate grant number')
  fail = false
  const writing = store.updateGrantNumber(7, 1, ' 00045 ')
  assert.equal(await store.updateGrantNumber(7, 1, 'other'), null)
  pending.resolve({ data: { ...original, grant_number: '00045' } })
  await writing
  assert.equal(store.forStock(7).grants[0].grantNumber, '00045')
  assert.deepEqual(requests.at(-1), ['/api/stocks/7/grants/1', { grant_number: '00045' }])
  await flush()
})
