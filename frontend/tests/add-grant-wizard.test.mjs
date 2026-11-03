import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import { createPinia } from 'pinia'
import axios from 'axios'
import { useStockGrantsStore } from '../src/stores/stockGrants.js'
import { useStockQuotesStore } from '../src/stores/stockQuotes.js'
import { formatStockValue } from '../src/lib/stockQuotes.js'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'
import * as vesting from '../src/components/stock-detail/vesting.js'
import * as acquisitions from '../src/components/stock-detail/acquisitions.js'

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
    ...acquisitions,
    ...dependencies,
  }
  return scope.run(() =>
    new Function(...Object.keys(bindings), `${script}\nreturn { ${exposed} }`)(
      ...Object.values(bindings),
    ),
  )
}

function mountWizard(t) {
  const props = Vue.reactive({ open: true, ticker: 'AAPL' })
  const events = []
  const wizard = setupComponent(
    t,
    '../src/components/stock-detail/AddGrantWizardModal.vue',
    {
      defineProps: () => props,
      defineEmits:
        () =>
        (...args) => {
          events.push(args)
          if (args[0] === 'update:open') props.open = args[1]
        },
    },
    `step, details, vestings, fieldErrors, error, regenerationNeeded, customized,
    effectiveTitle, total, difference, reviewRows, body, next, back, close, confirm,
    setGrantDate, setStartDate, insertAfter, regenerate`,
  )
  return { wizard, props, events }
}

function fillDetails(wizard, quantity = 1000) {
  wizard.setGrantDate('2026-01-31')
  wizard.details.value.quantity = quantity
  wizard.details.value.scheduleType = 'cliff-quarterly'
}

test('dates follow the grant date until T is independently edited; invalid details block Next', (t) => {
  const { wizard } = mountWizard(t)
  assert.equal(wizard.details.value.scheduleType, 'quarterly')
  wizard.next()
  assert.equal(wizard.step.value, 1)
  assert.ok(wizard.fieldErrors.value.quantity)
  wizard.setGrantDate('2024-02-29')
  assert.equal(wizard.details.value.startDate, '2024-02-29')
  wizard.setStartDate('2023-01-31')
  wizard.setGrantDate('2025-04-01')
  assert.equal(wizard.details.value.startDate, '2023-01-31')
  assert.equal(wizard.effectiveTitle.value, 'AAPL-2025-04-01')
  wizard.details.value.title = '  Retention award  '
  assert.equal(wizard.effectiveTitle.value, 'Retention award')
})

test('confirmation alone emits a sorted, independent grant, and cannot run twice', async (t) => {
  const { wizard, events } = mountWizard(t)
  fillDetails(wizard)
  wizard.next()
  assert.equal(wizard.step.value, 2)
  assert.equal(wizard.vestings.value.length, 13)
  wizard.vestings.value[0].date = '2031-01-01'
  wizard.next()
  assert.equal(wizard.step.value, 3)
  assert.equal(events.length, 0)
  assert.equal(wizard.reviewRows.value.at(-1).date, '2031-01-01')
  wizard.confirm()
  wizard.confirm()
  await Vue.nextTick()
  wizard.confirm()
  const confirmed = events.filter(([type]) => type === 'confirmed')
  assert.equal(confirmed.length, 1)
  assert.equal(confirmed[0][1].title, 'AAPL-2026-01-31')
  assert.equal(confirmed[0][1].quantity, 1000)
  assert.equal(confirmed[0][1].customized, true)
  assert.equal(confirmed[0][1].vestings.at(-1).date, '2031-01-01')
  assert.ok(confirmed[0][1].vestings.every((release) => typeof release.quantity === 'number'))
})

test('insert/delete and quantity mismatches keep the wizard on the editable schedule', async (t) => {
  const { wizard } = mountWizard(t)
  fillDetails(wizard)
  wizard.next()
  const first = wizard.vestings.value[0]
  let focused = false
  wizard.body.value = {
    scrollTo() {},
    querySelector: () => ({
      focus: () => {
        focused = true
      },
    }),
  }
  await wizard.insertAfter(0)
  assert.equal(focused, true)
  assert.equal(wizard.vestings.value[0].id, first.id)
  assert.equal(wizard.vestings.value[1].date, '')
  assert.equal(wizard.vestings.value[1].quantity, '')
  wizard.next()
  assert.equal(wizard.step.value, 2)
  assert.match(wizard.error.value, /date/)
  wizard.vestings.value.splice(1, 1)
  wizard.vestings.value[0].quantity = 249
  wizard.next()
  assert.match(wizard.error.value, /exactly match/)
  assert.equal(wizard.difference.value, 1)
  wizard.vestings.value = []
  wizard.next()
  assert.match(wizard.error.value, /at least one/)
  await wizard.insertAfter(-1)
  assert.equal(wizard.vestings.value.length, 1)
})

test('Back preserves edits; changed schedule parameters require explicit regeneration', async (t) => {
  const { wizard } = mountWizard(t)
  fillDetails(wizard)
  wizard.next()
  wizard.vestings.value[0].date = '2027-02-01'
  const firstId = wizard.vestings.value[0].id
  wizard.next()
  wizard.back()
  assert.equal(wizard.vestings.value[0].date, '2027-02-01')
  wizard.back()
  wizard.details.value.title = 'Updated title'
  // An independently chosen T remains unchanged when only the grant date changes.
  wizard.setStartDate('2026-01-31')
  wizard.setGrantDate('2026-02-01')
  wizard.next()
  assert.equal(wizard.step.value, 2)
  assert.equal(wizard.vestings.value[0].id, firstId)
  wizard.back()
  wizard.details.value.quantity = 1200
  wizard.next()
  assert.equal(wizard.step.value, 1)
  assert.equal(wizard.regenerationNeeded.value, true)
  assert.equal(wizard.vestings.value[0].id, firstId)
  wizard.regenerate()
  assert.equal(wizard.step.value, 2)
  assert.equal(wizard.total.value, 1200)
  assert.equal(wizard.customized.value, false)
  assert.notEqual(wizard.vestings.value[0].id, firstId)
  await Vue.nextTick()
})

test('cancel discards the draft and reopening starts with no quantity or release rows', async (t) => {
  const { wizard, props, events } = mountWizard(t)
  fillDetails(wizard)
  wizard.next()
  wizard.close()
  await Vue.nextTick()
  props.open = true
  await Vue.nextTick()
  assert.equal(wizard.step.value, 1)
  assert.equal(wizard.details.value.quantity, '')
  assert.equal(wizard.details.value.scheduleType, 'quarterly')
  assert.equal(wizard.vestings.value.length, 0)
  assert.equal(events.filter(([type]) => type === 'confirmed').length, 0)
})

const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}
function mountDetail(t) {
  const original = { get: axios.get, post: axios.post, delete: axios.delete }
  t.after(() => Object.assign(axios, original))
  const saved = new Map()
  let id = 0
  axios.get = async (url) => {
    const stockId = Number(url.split('/')[3])
    return {
      data:
        url.endsWith('/sales') || url.endsWith('/purchases')
          ? []
          : url.endsWith('/grants')
            ? saved.get(stockId) || []
            : { id: stockId, name: `Canonical ${stockId}`, symbol: `REAL${stockId}` },
    }
  }
  axios.post = async (url, data) => {
    const stockId = Number(url.split('/')[3])
    const grant = {
      ...data,
      id: ++id,
      stock_id: stockId,
      vestings: data.vestings.map((row, index) => ({ ...row, id: id * 100 + index })),
    }
    saved.set(stockId, [...(saved.get(stockId) || []), grant])
    return { data: grant }
  }
  axios.delete = async (url) => {
    const stockId = Number(url.split('/')[3])
    saved.set(
      stockId,
      saved.get(stockId).filter((grant) => grant.id !== Number(url.split('/').at(-1))),
    )
  }
  const store = useStockGrantsStore(createPinia())
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
    'grants, showAddGrant, today, activeTab, portfolio, summaries, addGrant, entry, stockName, stockSymbol, ready, grantToDelete, requestDeleteGrant, deleteGrant',
  )
  return { view, route, store }
}
const grantDraft = (quantity = 100) => ({
  creationToken: vesting.createId(),
  title: 'Draft grant',
  grantDate: '2026-01-31',
  startDate: '2025-01-31',
  scheduleType: 'quarterly',
  customized: true,
  quantity,
  vestings: [{ id: 'local', date: '2026-10-24', quantity }],
})
test('view loads canonical metadata and saved grants, and navigation reloads persisted data', async (t) => {
  const { view, route } = mountDetail(t)
  assert.equal(view.ready.value, false)
  await flush()
  assert.equal(view.stockName.value, 'Canonical 1')
  assert.equal(view.stockSymbol.value, 'REAL1')
  view.today.value = '2026-10-24'
  view.activeTab.value = 'holdings'
  view.showAddGrant.value = true
  await view.addGrant(grantDraft())
  assert.equal(view.grants.value.length, 1)
  assert.equal(view.portfolio.value.vested, 100)
  assert.equal(view.activeTab.value, 'vesting')
  assert.equal(view.showAddGrant.value, false)
  route.params.stockId = '2'
  await flush()
  assert.deepEqual(view.grants.value, [])
  assert.equal(view.stockName.value, 'Canonical 2')
  route.params.stockId = '1'
  await flush()
  assert.equal(view.grants.value.length, 1)
  assert.equal(view.portfolio.value.awarded, 100)
})

test('timeline handles empty grants and refreshes buckets, scale and selection after additions', async (t) => {
  const props = Vue.reactive({ grants: [], today: '2026-10-24' })
  const timeline = setupComponent(
    t,
    '../src/components/stock-detail/VestingTimeline.vue',
    {
      defineProps: () => props,
      defineEmits: () => () => {},
    },
    'quarters, summary, selectedId, selectedQuarter, tickStep, bars, todayX',
  )
  assert.deepEqual(timeline.quarters.value, [])
  assert.equal(timeline.selectedQuarter.value, undefined)
  props.grants.push({
    id: 'a',
    title: 'Grant A',
    color: '#426b5a',
    quantity: 1000,
    vestings: [
      { id: 'v1', date: '2026-10-24', quantity: 500 },
      { id: 'v2', date: '2026-12-01', quantity: 500 },
    ],
  })
  await Vue.nextTick()
  assert.equal(timeline.selectedQuarter.value.id, '2026-Q4')
  assert.deepEqual(
    timeline.bars.value[0].segments.map((segment) => segment.scheduled),
    [false, true],
  )
  assert.ok(Number.isFinite(timeline.todayX.value))
  const oldStep = timeline.tickStep.value
  props.grants.push({
    id: 'b',
    title: 'Grant B',
    color: '#386f88',
    quantity: 10000,
    vestings: [{ id: 'v3', date: '2027-01-01', quantity: 10000 }],
  })
  await Vue.nextTick()
  assert.ok(timeline.tickStep.value > oldStep)
  assert.equal(timeline.selectedId.value, '2026-Q4')
  assert.equal(timeline.summary.value.awarded, 11000)
  props.grants = []
  await Vue.nextTick()
  assert.equal(timeline.selectedQuarter.value, undefined)
  assert.deepEqual(timeline.bars.value, [])
  assert.equal(timeline.summary.value.awarded, 0)
})

test('grant overview derives progress, release dates and totals entirely from entered grants', (t) => {
  const props = Vue.reactive({ grants: [], today: '2026-10-25' })
  const overview = setupComponent(
    t,
    '../src/components/stock-detail/GrantsOverview.vue',
    {
      defineProps: () => props,
      defineEmits: () => () => {},
    },
    'rows, portfolio',
  )
  assert.deepEqual(overview.rows.value, [])
  assert.equal(overview.portfolio.value.awarded, 0)
  props.grants.push({
    id: 'edited',
    title: 'Custom grant',
    quantity: 100,
    grantDate: '2026-01-01',
    scheduleType: 'quarterly',
    customized: true,
    vestings: [
      { id: 'last', date: '2028-01-01', quantity: 20 },
      { id: 'next-1', date: '2027-01-01', quantity: 25 },
      { id: 'past', date: '2026-10-25', quantity: 25 },
      { id: 'next-2', date: '2027-01-01', quantity: 30 },
    ],
  })
  assert.equal(overview.rows.value[0].vested, 25)
  assert.equal(overview.rows.value[0].remaining, 75)
  assert.deepEqual(overview.rows.value[0].nextRelease, { date: '2027-01-01', quantity: 55 })
  assert.equal(overview.rows.value[0].completion, '2028-01-01')
  assert.equal(overview.rows.value[0].scheduleLabel, 'Quarterly after year one')
  assert.equal(overview.portfolio.value.awarded, 100)
  props.today = '2029-01-01'
  assert.equal(overview.rows.value[0].vested, 100)
  assert.equal(overview.rows.value[0].nextRelease, null)
})

test('view keeps save and delete dialogs open after failure and updates only after server success', async (t) => {
  const { view } = mountDetail(t)
  await flush()
  view.today.value = '2026-10-25'
  const save = axios.post
  axios.post = async () => {
    throw new Error('Offline')
  }
  view.showAddGrant.value = true
  await view.addGrant(grantDraft())
  assert.equal(view.showAddGrant.value, true)
  assert.equal(view.grants.value.length, 0)
  assert.ok(view.entry.value.saveError)
  axios.post = save
  await view.addGrant(grantDraft())
  assert.equal(view.showAddGrant.value, false)
  const target = view.grants.value[0]
  view.activeTab.value = 'grants'
  view.requestDeleteGrant(target)
  view.grantToDelete.value = null
  await view.deleteGrant()
  assert.equal(view.grants.value.length, 1)
  view.requestDeleteGrant(target)
  const remove = axios.delete
  axios.delete = async () => {
    throw new Error('Offline')
  }
  await view.deleteGrant()
  assert.equal(view.grantToDelete.value.id, target.id)
  assert.equal(view.grants.value.length, 1)
  assert.ok(view.entry.value.deleteError)
  axios.delete = remove
  await view.deleteGrant()
  assert.equal(view.grantToDelete.value, null)
  assert.equal(view.portfolio.value.awarded, 0)
  assert.equal(view.activeTab.value, 'grants')
})
test('wizard retains its draft and creation token after a failed save, and blocks pending dismissal', async (t) => {
  const { wizard, props, events } = mountWizard(t)
  fillDetails(wizard)
  wizard.next()
  wizard.next()
  wizard.confirm()
  const first = events.find(([type]) => type === 'confirmed')[1]
  props.saving = true
  await Vue.nextTick()
  wizard.close()
  wizard.confirm()
  assert.equal(props.open, true)
  assert.equal(events.length, 1)
  props.saving = false
  props.saveError = 'Network failed'
  await Vue.nextTick()
  assert.equal(wizard.step.value, 3)
  assert.equal(wizard.details.value.quantity, 1000)
  assert.equal(wizard.vestings.value.length, 13)
  wizard.confirm()
  const second = events.filter(([type]) => type === 'confirmed')[1][1]
  assert.equal(second.creationToken, first.creationToken)
  assert.deepEqual(second.vestings, first.vestings)
  props.open = false
  await Vue.nextTick()
  assert.equal(wizard.step.value, 1)
})
test('late save completion cannot close a newly opened modal on another stock', async (t) => {
  const { view, route } = mountDetail(t)
  await flush()
  let finish
  axios.post = () =>
    new Promise((resolve) => {
      finish = resolve
    })
  const pending = view.addGrant(grantDraft())
  route.params.stockId = '2'
  await flush()
  view.showAddGrant.value = true
  finish({
    data: {
      id: 99,
      stock_id: 1,
      title: 'Old stock',
      grant_date: '2026-10-25',
      quantity: 100,
      vesting_start_date: '2025-01-31',
      schedule_type: 'quarterly',
      customized: true,
      vestings: [{ id: 1, date: '2027-01-01', quantity: 100 }],
    },
  })
  await pending
  assert.equal(view.showAddGrant.value, true)
  assert.deepEqual(view.grants.value, [])
})
