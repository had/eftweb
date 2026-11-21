import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import axios from 'axios'
import * as Vue from 'vue'
import { parse } from 'vue/compiler-sfc'
import { isCalendarDate } from '../src/components/stock-detail/vesting.js'

const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}
const grant = () => ({
  id: 1,
  title: 'Retention',
  grantNumber: '00123',
  grantDate: '2020-01-01',
  approvalDate: '2019-01-01',
  taxpayerRole: 'taxpayer1',
})
const family = {
  taxpayer1: { first_name: 'Ada', last_name: 'Example' },
  taxpayer2: { first_name: 'Boris', last_name: 'Example' },
}
function setup(t, get = async () => ({ data: family })) {
  t.mock.method(axios, 'get', get)
  const props = Vue.reactive({ grant: grant(), familyId: 1, saving: false, error: '' })
  const events = []
  const { descriptor } = parse(
    readFileSync(
      new URL('../src/components/stock-detail/EditGrantModal.vue', import.meta.url),
      'utf8',
    ),
  )
  const script = descriptor.scriptSetup.content.replace(
    /^import[\s\S]*?from ['"][^'"]+['"]\n/gm,
    '',
  )
  const bindings = {
    ref: Vue.ref,
    computed: Vue.computed,
    watch: Vue.watch,
    axios,
    isCalendarDate,
    defineProps: () => props,
    defineEmits:
      () =>
      (...args) =>
        events.push(args),
  }
  const scope = Vue.effectScope()
  t.after(() => scope.stop())
  const view = scope.run(() =>
    new Function(
      ...Object.keys(bindings),
      `${script}\nreturn { details, errors, taxpayers, loadingTaxpayers, changes, save, close }`,
    )(...Object.values(bindings)),
  )
  return { view, props, events }
}

test('editor loads existing metadata and emits only edited fields without mutating the grant', async (t) => {
  const { view, props, events } = setup(t)
  await flush()
  assert.deepEqual(view.changes.value, {})
  assert.equal(view.taxpayers.value[1].label, 'Boris Example (taxpayer 2)')
  view.details.value.title = '  Updated award  '
  view.details.value.grant_date = '2020-02-02'
  view.details.value.approval_date = '2016-12-31'
  view.details.value.taxpayer_role = 'taxpayer2'
  view.save()
  assert.deepEqual(events, [
    [
      'save',
      {
        title: 'Updated award',
        grant_date: '2020-02-02',
        approval_date: '2016-12-31',
        taxpayer_role: 'taxpayer2',
      },
    ],
  ])
  assert.deepEqual(props.grant, grant())
  props.error = 'Could not save'
  assert.equal(view.details.value.grant_date, '2020-02-02')
})

test('editor validates dates and family taxpayer, permits clearing unknown metadata, and blocks writes while saving', async (t) => {
  const { view, props, events } = setup(t)
  await flush()
  view.details.value.grant_date = '2026-02-30'
  view.details.value.approval_date = '2015-08-07'
  view.details.value.taxpayer_role = 'child'
  view.save()
  assert.ok(
    view.errors.value.grant_date &&
      view.errors.value.approval_date &&
      view.errors.value.taxpayer_role,
  )
  assert.equal(events.length, 0)
  view.details.value.grant_date = props.grant.grantDate
  view.details.value.approval_date = ''
  view.details.value.taxpayer_role = ''
  view.details.value.grant_number = ''
  props.saving = true
  view.save()
  view.close()
  assert.equal(events.length, 0)
  props.saving = false
  view.save()
  assert.deepEqual(events[0], [
    'save',
    { grant_number: null, approval_date: null, taxpayer_role: null },
  ])
})

test('a late family response cannot change the reopened editor', async (t) => {
  const requests = []
  const { view, props } = setup(
    t,
    (url, options) => new Promise((resolve) => requests.push({ url, options, resolve })),
  )
  props.grant = null
  await flush()
  props.familyId = 2
  props.grant = { ...grant(), id: 2, title: 'Another grant' }
  await flush()
  assert.ok(requests[0].options.signal.aborted)
  requests[1].resolve({ data: { taxpayer1: family.taxpayer1 } })
  await flush()
  requests[0].resolve({ data: family })
  await flush()
  assert.equal(view.details.value.title, 'Another grant')
  assert.equal(view.taxpayers.value.length, 1)
})
