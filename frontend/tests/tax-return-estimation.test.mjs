import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import test from 'node:test'
import * as Vue from 'vue'
import { compileScript, parse } from 'vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'

const readComponent = (path) => parse(readFileSync(new URL(path, import.meta.url), 'utf8')).descriptor
const detail = readComponent('../src/views/TaxReturnDetailView.vue')

const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}

const deferred = () => {
  let resolve, reject
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail })
  return { promise, resolve, reject }
}

// Run the actual view setup with Vue's watcher/reactivity system and mocked HTTP.
// No DOM or additional test framework is required for its request lifecycle.
function mountDetail(t, getOverride = () => undefined) {
  const route = Vue.reactive({ params: { taxReturnId: '1' } })
  const familyStore = Vue.reactive({
    familyId: 10,
    taxReturnsVersion: 0,
    refreshTaxReturns() { this.taxReturnsVersion += 1 },
  })
  const requests = []
  const axios = {
    async get(url) {
      requests.push(url)
      const override = getOverride(url, requests.filter((request) => request === url).length)
      if (override !== undefined) return override
      if (url.endsWith('/tax-returns')) return { data: [1, 2].map((id) => ({
        id, year: 2025, has_income_statements: true,
        has_donation_statements: true, has_investment_statements: true,
      })) }
      if (url.endsWith('/estimation')) return { data: { net_taxes: 100, net_social_taxes: 0 } }
      if (url === '/api/families/10') return { data: { taxpayer1: null, children: [] } }
      return { data: [] }
    },
    async delete(url) { requests.push(url) },
  }
  let unmount
  const scope = Vue.effectScope()
  const script = detail.scriptSetup.content.replace(/^import .*$/gm, '')
  const setup = new Function(
    'computed', 'onBeforeUnmount', 'ref', 'watch', 'useRoute', 'useFamilyStore', 'axios',
    `${script}
    return { estimate, estimationLoading, estimationError, loading, unavailable, taxReturn,
      incomeStatements, incomeStatementSaved, donationStatementSaved, ifuStatementSaved,
      deleteIncomeStatement, deleteDonationStatement, deleteIfuStatement, settingsSaved }`,
  )
  const view = scope.run(() => setup(
    Vue.computed, (callback) => { unmount = callback }, Vue.ref, Vue.watch,
    () => route, () => familyStore, axios,
  ))
  t.after(() => { unmount(); scope.stop() })
  return { view, route, familyStore, requests }
}

test('initial load and every saved/deleted statement refresh the estimate', async (t) => {
  const { view, requests } = mountDetail(t)
  await flush()
  const estimateCalls = () => requests.filter((url) => url.endsWith('/estimation')).length
  assert.equal(estimateCalls(), 1)
  assert.deepEqual(view.estimate.value, { net_taxes: 100, net_social_taxes: 0 })
  const actions = [
    view.incomeStatementSaved, view.incomeStatementSaved,
    view.donationStatementSaved, view.donationStatementSaved,
    view.ifuStatementSaved, view.ifuStatementSaved,
    () => view.deleteIncomeStatement({ id: 11 }),
    () => view.deleteDonationStatement({ id: 12 }),
    () => view.deleteIfuStatement({ id: 13 }),
    view.settingsSaved,
  ]
  for (const [index, action] of actions.entries()) {
    await action()
    await flush()
    assert.equal(estimateCalls(), index + 2)
  }
  assert.ok(requests.includes('/api/income-statements/11'))
  assert.ok(requests.includes('/api/donation-statements/12'))
  assert.ok(requests.includes('/api/ifu-statements/13'))
})

test('estimation errors leave the return and its statements available', async (t) => {
  const { view } = mountDetail(t, (url) => {
    if (url.endsWith('/estimation')) return Promise.reject({
      response: { data: { error: 'Tax estimation is unavailable for filing year 2026' } },
    })
    if (url.endsWith('/income-statements')) return { data: [{ id: 11 }] }
  })
  await flush()
  assert.equal(view.unavailable.value, false)
  assert.equal(view.loading.value, false)
  assert.deepEqual(view.incomeStatements.value, [{ id: 11 }])
  assert.equal(view.estimate.value, null)
  assert.equal(view.estimationLoading.value, false)
  assert.match(view.estimationError.value, /2026/)
})

for (const outcome of ['success', 'failure']) {
  test(`an older estimate ${outcome} cannot overwrite the current load`, async (t) => {
    const old = deferred()
    const current = deferred()
    const { view, route } = mountDetail(t, (url) => {
      if (url === '/api/tax-returns/1/estimation') return old.promise
      if (url === '/api/tax-returns/2/estimation') return current.promise
    })
    await flush()
    route.params.taxReturnId = '2'
    await flush()
    assert.equal(view.taxReturn.value.id, 2)
    assert.equal(view.estimate.value, null)
    assert.equal(view.estimationLoading.value, true)
    if (outcome === 'success') old.resolve({ data: { net_taxes: 999, net_social_taxes: 999 } })
    else old.reject(new Error('Old request failed'))
    await flush()
    assert.equal(view.estimate.value, null)
    assert.equal(view.estimationError.value, '')
    assert.equal(view.estimationLoading.value, true)
    current.resolve({ data: { net_taxes: 200, net_social_taxes: 0 } })
    await flush()
    assert.deepEqual(view.estimate.value, { net_taxes: 200, net_social_taxes: 0 })
    assert.equal(view.estimationLoading.value, false)
  })
}

test('older statement responses cannot overwrite the current return', async (t) => {
  const old = deferred()
  const { view, route } = mountDetail(t, (url) => {
    if (url === '/api/tax-returns/1/income-statements') return old.promise
    if (url === '/api/tax-returns/2/income-statements') return { data: [{ id: 22 }] }
  })
  await flush()
  route.params.taxReturnId = '2'
  await flush()
  old.resolve({ data: [{ id: 11 }] })
  await flush()
  assert.equal(view.taxReturn.value.id, 2)
  assert.deepEqual(view.incomeStatements.value, [{ id: 22 }])
  assert.equal(view.loading.value, false)
})

const summary = readComponent('../src/components/tax-return-detail/TaxReturnSummary.vue')
const compiled = compileScript(summary, { id: 'summary-test', inlineTemplate: true }).content
const summaryCode = compiled
  .replace(/^import \{([^}]+)\} from ["']vue["']$/gm,
    (_, names) => `const {${names.replace(/ as /g, ': ')}} = Vue`)
  .replace(/^import \{([^}]+)\} from ["']@\/components\/ui\/card["']$/gm,
    (_, names) => `const {${names}} = cards`)
  .replace('export default', 'return')
const card = Vue.defineComponent({ setup: (_, { slots }) => () => Vue.h('div', slots.default?.()) })
const Summary = new Function('Vue', 'cards', summaryCode)(Vue, {
  Card: card, CardContent: card, CardHeader: card, CardTitle: card,
})

test('summary renders currency values including zero and the partial-estimate note', async () => {
  const html = await renderToString(Vue.createSSRApp(Summary, {
    estimate: { net_taxes: 1234.56, net_social_taxes: 0 },
  }))
  assert.match(html, /Net taxes/)
  assert.match(html, /Net social taxes/)
  assert.match(html, /€1,234\.56/)
  assert.match(html, /€0\.00/)
  assert.match(html, /Partial estimate/)
  assert.match(html, /Salary withholding and supplementary pension contributions are excluded/)
})

test('summary renders loading placeholders and unavailable estimates', async () => {
  const loading = await renderToString(Vue.createSSRApp(Summary, { estimationLoading: true }))
  assert.match(loading, /Loading net taxes/)
  assert.match(loading, /Loading net social taxes/)
  const error = await renderToString(Vue.createSSRApp(Summary, { estimationError: 'Unavailable for 2026' }))
  assert.match(error, /Unavailable for 2026/)
  assert.match(error, /—/)
  assert.doesNotMatch(error, /€0\.00/)
})
