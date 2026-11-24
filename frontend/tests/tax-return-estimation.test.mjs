import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import test from 'node:test'
import * as Vue from 'vue'
import * as icons from 'lucide-vue-next'
import * as reka from 'reka-ui'
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

const card = Vue.defineComponent({ setup: (_, { slots }) => () => Vue.h('div', slots.default?.()) })
const cards = { Card: card, CardContent: card, CardHeader: card, CardTitle: card }
function compileComponent(descriptor, InfoTooltip, ProgressiveTaxRuler, tooltipComponents = reka) {
  const compiled = compileScript(descriptor, { id: 'summary-test', inlineTemplate: true }).content
  const code = compiled
  .replace(/^import \{([^}]+)\} from ["']vue["']$/gm,
    (_, names) => `const {${names.replace(/ as /g, ': ')}} = Vue`)
  .replace(/^import \{([^}]+)\} from ["']@\/components\/ui\/card["']$/gm,
    (_, names) => `const {${names}} = cards`)
  .replace(/^import \{([^}]+)\} from ["']lucide-vue-next["']$/gm,
    (_, names) => `const {${names}} = icons`)
  .replace(/^import \{([^}]+)\} from ["']reka-ui["']$/gm,
    (_, names) => `const {${names}} = reka`)
  .replace(/^import InfoTooltip from ["']@\/components\/InfoTooltip.vue["']$/gm, '')
  .replace(/^import ProgressiveTaxRuler from ["']@\/components\/tax-return-detail\/ProgressiveTaxRuler.vue["']$/gm, '')
  .replace('export default', 'return')
  return new Function('Vue', 'cards', 'icons', 'reka', 'InfoTooltip', 'ProgressiveTaxRuler', code)(Vue, cards, icons, tooltipComponents, InfoTooltip, ProgressiveTaxRuler)
}
const InfoTooltip = compileComponent(readComponent('../src/components/InfoTooltip.vue'))
const ProgressiveTaxRuler = compileComponent(readComponent('../src/components/tax-return-detail/ProgressiveTaxRuler.vue'))
const Summary = compileComponent(readComponent('../src/components/tax-return-detail/TaxReturnSummary.vue'), InfoTooltip, ProgressiveTaxRuler)

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
  assert.match(loading, /Loading estimated rfr/)
  assert.match(loading, /Loading parts fiscales/)
  assert.match(loading, /Loading marginal tax rate/)
  const error = await renderToString(Vue.createSSRApp(Summary, { estimationError: 'Unavailable for 2026' }))
  assert.match(error, /Unavailable for 2026/)
  assert.match(error, /—/)
  assert.doesNotMatch(error, /€0\.00/)
})

const detailedEstimate = {
  net_taxes: 9316,
  net_social_taxes: 155,
  reference_fiscal_income: 55000,
  household_shares: 1,
  marginal_tax_rate: 0.3,
  progressive_tax: {
    taxable_income: 54000,
    scale_tax: 9304,
    brackets: [
      { lower_bound: 0, upper_bound: 11600, rate: 0, income: 11600, tax: 0 },
      { lower_bound: 11600, upper_bound: 29579, rate: 0.11, income: 17979, tax: 1977.69 },
      { lower_bound: 29579, upper_bound: 84577, rate: 0.3, income: 24421, tax: 7326.3 },
      { lower_bound: 84577, upper_bound: 181917, rate: 0.41, income: 0, tax: 0 },
      { lower_bound: 181917, upper_bound: null, rate: 0.45, income: 0, tax: 0 },
    ],
  },
  donation_buckets: [
    { rate: 0.75, donated: 1500, eligible: 1000, limit: 1000, reduction: 750, overflow: 500 },
    { rate: 0.66, donated: 1500, eligible: 1500, limit: 10800, reduction: 990, overflow: 0 },
  ],
  fiscal_advantages: { limit: 10000, used: 0, excess: 0 },
}

test('summary keeps RFR, shares and marginal rate outside expandable details', async () => {
  const html = await renderToString(Vue.createSSRApp(Summary, { estimate: detailedEstimate }))
  const visible = html.split('aria-controls=')[0]
  assert.match(visible, /Estimated RFR/)
  assert.match(visible, /€55,000\.00/)
  assert.match(visible, /Parts fiscales/)
  assert.match(visible, /Marginal tax rate/)
  assert.match(visible, /30%/)
  assert.match(visible, /Partial estimate/)
  assert.ok(html.indexOf('Partial estimate') < html.indexOf('class="border-t'))
  assert.match(html, /aria-expanded="false"/)
  assert.match(html, /aria-label="Show calculation details"/)
  assert.match(html, /aria-hidden="true" inert/)
})

test('expanded view shows bucket fill and tax contributions with accessible donation meters', async () => {
  const html = await renderToString(Vue.createSSRApp(Summary, { estimate: detailedEstimate }))
  assert.match(html, /Scale tax €9,304\.00/)
  assert.match(html, /€24,421\.00/)
  assert.match(html, /€7,326\.30/)
  assert.match(html, /44\.4%/)
  assert.match(html, /Current band/)
  assert.doesNotMatch(html, /<table/)
  assert.match(html, /aria-label="11% band, €11,600\.00 – €29,579\.00\. Income in band €17,979\.00\. Filled 100%\. Tax contribution €1,977\.69\."/)
  assert.match(html, /aria-label="75% donation bucket" aria-valuenow="100"/)
  assert.match(html, /aria-label="Annual tax advantage ceiling" aria-valuenow="0"/)
  assert.match(html, /aria-label="About progressive income tax"/)
  assert.match(html, /aria-label="About donation buckets"/)
  assert.match(html, /aria-label="About the annual tax advantage ceiling"/)
  assert.doesNotMatch(html, /Only supported donations|Filled colours|Partial coverage|transferred to the 66% bucket/)
})

test('empty chart values and zero donation limits render without invalid widths', async () => {
  const estimate = structuredClone(detailedEstimate)
  estimate.progressive_tax.taxable_income = 0
  estimate.progressive_tax.scale_tax = 0
  estimate.progressive_tax.brackets.forEach((band) => { band.income = 0; band.tax = 0 })
  estimate.donation_buckets.forEach((bucket) => {
    bucket.donated = 0; bucket.eligible = 0; bucket.reduction = 0; bucket.overflow = 0
  })
  estimate.donation_buckets[1].limit = 0
  const html = await renderToString(Vue.createSSRApp(Summary, { estimate }))
  assert.doesNotMatch(html, /NaN|Infinity|width:-/)
  assert.match(html, /aria-label="66% donation bucket" aria-valuenow="0"/)
})

test('top band is open ended and stale details stay hidden during loading or error', async () => {
  const estimate = structuredClone(detailedEstimate)
  estimate.progressive_tax.taxable_income = 200000
  estimate.progressive_tax.brackets.at(-1).income = 18083
  const html = await renderToString(Vue.createSSRApp(Summary, { estimate }))
  assert.match(html, /45% band has no upper limit/)
  assert.doesNotMatch(html, /NaN|Infinity/)
  for (const state of [{ estimationLoading: true }, { estimationError: 'Unavailable' }]) {
    const hidden = await renderToString(Vue.createSSRApp(Summary, { estimate, ...state }))
    assert.doesNotMatch(hidden, /aria-label="Show calculation details"/)
  }
})

test('an exact threshold keeps the fully filled preceding band current', async () => {
  const estimate = structuredClone(detailedEstimate)
  estimate.progressive_tax.taxable_income = 29579
  estimate.progressive_tax.brackets[2].income = 0
  estimate.progressive_tax.brackets[2].tax = 0
  const html = await renderToString(Vue.createSSRApp(Summary, { estimate }))
  const current = html.match(/aria-label="([^"]*Current band\.)"/)?.[1]
  assert.match(current, /11%/)
  assert.match(current, /100%/)
})

test('ruler tooltips preserve the former table details, including the open-ended band', async () => {
  // Open the real tooltip content for SSR, with its portal rendered inline.
  const Ruler = compileComponent(
    readComponent('../src/components/tax-return-detail/ProgressiveTaxRuler.vue'),
    undefined, undefined, {
      ...reka,
      TooltipRoot: Vue.defineComponent({
        setup: (_, { slots }) => () => Vue.h(reka.TooltipRoot, { defaultOpen: true }, slots),
      }),
      TooltipPortal: Vue.defineComponent({ setup: (_, { slots }) => () => slots.default?.() }),
    },
  )
  const renderRuler = (bands, taxableIncome) => renderToString(Vue.createSSRApp({
    setup: () => () => Vue.h(reka.TooltipProvider, null, {
      default: () => Vue.h(Ruler, { bands, taxableIncome, colors: ['red', 'blue', 'green', 'purple', 'teal'] }),
    }),
  }))
  const html = await renderRuler(detailedEstimate.progressive_tax.brackets, 54000)
  assert.match(html, /Income in band<\/dt><dd[^>]*>€17,979\.00/)
  assert.match(html, /Filled<\/dt><dd[^>]*>100%/)
  assert.match(html, /Tax contribution<\/dt><dd[^>]*>€1,977\.69/)
  assert.match(html, /€11,600\.00 – €29,579\.00/)

  const highest = structuredClone(detailedEstimate.progressive_tax.brackets)
  highest.at(-1).income = 18083
  highest.at(-1).tax = 8137.35
  const top = await renderRuler(highest, 200000)
  assert.match(top, /Over €181,917\.00/)
  assert.match(top, /Filled<\/dt><dd[^>]*>No upper limit/)
  assert.match(top, /Tax contribution<\/dt><dd[^>]*>€8,137\.35/)
})
