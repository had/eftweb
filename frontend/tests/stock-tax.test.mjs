import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import axios from 'axios'
import * as Vue from 'vue'
import { parse, compileScript } from 'vue/compiler-sfc'

const flush = async () => {
  await Vue.nextTick()
  await setImmediate()
}
const fields = (value = '100') => ({
  capital_result: value,
  '1TZ': '50',
  '1UZ': '0',
  '1WZ': '50',
  '1TT': '0',
  '1UT': '0',
})
const detail = () => ({
  id: 4,
  stock_id: 1,
  source_key: 'stock:1',
  title: 'ABC',
  computed: fields(),
  reported: fields(),
  lines: [{ fields: { 515: '10' } }],
})
const preparation = () => ({
  income_year: 2024,
  source_revision: 'revision',
  statements: [{ ...detail(), reported: fields() }],
  errors: [],
  can_accept: true,
  replacements: [detail()],
  threshold: {},
})
function setup(t, handler) {
  const original = { get: axios.get, post: axios.post, put: axios.put, delete: axios.delete }
  t.after(() => Object.assign(axios, original))
  for (const method of Object.keys(original)) axios[method] = (...args) => handler(method, ...args)
  const { descriptor } = parse(
    readFileSync(
      new URL('../src/components/tax-return-detail/StockTaxSection.vue', import.meta.url),
      'utf8',
    ),
  )
  const script = descriptor.scriptSetup.content.replace(
    /^import[\s\S]*?from ['"][^'"]+['"]\n/gm,
    '',
  )
  const scope = Vue.effectScope()
  t.after(() => scope.stop())
  const props = Vue.reactive({ taxReturnId: 1, filingYear: 2025 })
  const emitted = []
  const bindings = {
    ref: Vue.ref,
    computed: Vue.computed,
    watch: Vue.watch,
    axios,
    defineProps: () => props,
    defineEmits:
      () =>
      (...args) =>
        emitted.push(args),
    onBeforeUnmount: () => {},
  }
  const view = scope.run(() =>
    new Function(
      ...Object.keys(bindings),
      `${script}\nreturn { preview, drafts, saved, rates, error, message, opened, editing, manual, replaceExisting, prepare, accept, open, saveEdit, saveManual, remove, deleting }`,
    )(...Object.values(bindings)),
  )
  return { view, props, emitted }
}

test('preview is temporary, preserves edits, requires all-stock acceptance and sends explicit replacement', async (t) => {
  const calls = []
  const { view, emitted } = setup(t, async (method, url, body, options) => {
    calls.push({ method, url, body, options })
    if (url.endsWith('/preview')) return { data: preparation() }
    return { data: { statements: [detail()], aggregate: { '3VG': '100' } } }
  })
  await flush()
  await view.prepare()
  assert.equal(calls.filter((c) => c.method === 'post' && c.url.endsWith('/accept')).length, 0)
  assert.equal(emitted.filter(([event]) => event === 'changed').length, 0)
  view.drafts.value['1'].capital_result = '123'
  view.rates.value = [{ date: '2024-01-10', rate: '0.9' }]
  await view.prepare()
  assert.equal(view.drafts.value['1'].capital_result, '123')
  view.replaceExisting.value = true
  await view.accept()
  const request = calls.find((c) => c.url.endsWith('/accept'))
  assert.equal(request.body.reported['1'].capital_result, '123')
  assert.equal(request.body.replace_existing, true)
  assert.deepEqual(request.body.fx_overrides, { '2024-01-10': '0.9' })
  assert.match(request.options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)
  assert.equal(view.preview.value, null)
  assert.equal(view.saved.value.statements.length, 1)
  assert.equal(emitted.filter(([event]) => event === 'changed').length, 1)
})

test('recalculation updates untouched suggestions and retains only user overrides', async (t) => {
  let calculation = 0
  const { view } = setup(t, async (method, url) => {
    if (!url.endsWith('/preview')) return { data: { statements: [], aggregate: {} } }
    const data = preparation()
    if (calculation++) {
      data.statements[0].reported = { ...fields('200'), '1TZ': '150' }
      data.statements[0].computed = { ...data.statements[0].reported }
    }
    return { data }
  })
  await flush()
  await view.prepare()
  view.drafts.value['1'].capital_result = '123'
  await view.prepare()
  assert.equal(view.drafts.value['1'].capital_result, '123')
  assert.equal(view.drafts.value['1']['1TZ'], '150')
})

test('acceptance errors preserve the draft and retry with the same key', async (t) => {
  const tokens = []
  const { view, emitted } = setup(t, async (method, url, body, options) => {
    if (url.endsWith('/preview')) return { data: preparation() }
    if (url.endsWith('/accept')) {
      tokens.push(options.headers['Idempotency-Key'])
      throw { response: { data: { error: 'Prepare again: source changed' } } }
    }
    return { data: { statements: [], aggregate: {} } }
  })
  await flush()
  await view.prepare()
  view.replaceExisting.value = true
  await view.accept()
  await view.accept()
  assert.equal(tokens[0], tokens[1])
  assert.match(view.error.value, /source changed/)
  assert.ok(view.preview.value)
  assert.equal(emitted.filter(([event]) => event === 'changed').length, 0)
})

test('saved helper details are reopened, contribution edits and manual sources use independent endpoints', async (t) => {
  const requests = []
  const { view, emitted } = setup(t, async (method, url, body) => {
    requests.push({ method, url, body })
    if (url.endsWith('/4')) return { data: { ...detail(), reported: body?.reported || fields() } }
    return { data: { statements: [detail()], aggregate: { '3VG': '100' } } }
  })
  await flush()
  await view.open(detail())
  assert.deepEqual(view.opened.value.lines, detail().lines)
  view.editing.value.capital_result = '-50'
  await view.saveEdit()
  assert.equal(requests.find((r) => r.method === 'put').body.reported.capital_result, '-50')
  assert.deepEqual(view.opened.value.lines, detail().lines)
  view.manual.value = { title: 'Other broker', capital_result: '-30' }
  await view.saveManual()
  assert.deepEqual(requests.find((r) => r.method === 'post').body, {
    title: 'Other broker',
    capital_result: '-30',
  })
  view.deleting.value = detail()
  await view.remove()
  assert.ok(requests.some((r) => r.method === 'delete' && r.url.endsWith('/4')))
  assert.equal(emitted.filter(([event]) => event === 'changed').length, 3)
})

test('helper template renders every 2074 line and copy controls without hiding conversions', () => {
  const source = readFileSync(
    new URL('../src/components/tax-return-detail/StockTaxHelper.vue', import.meta.url),
    'utf8',
  )
  const { descriptor } = parse(source)
  const { content } = compileScript(descriptor, { id: 'helper' })
  assert.match(content, /navigator.clipboard.writeText/)
  for (const code of [
    '511',
    '512',
    '514',
    '515',
    '516',
    '517',
    '518',
    '520',
    '521',
    '522',
    '523',
    '524',
  ])
    assert.match(content, new RegExp(code))
  assert.match(descriptor.template.content, /rate_date/)
  assert.match(descriptor.template.content, /absorbed_loss/)
  assert.match(descriptor.template.content, /line.fields/)
})
