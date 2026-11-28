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

function setup(t, path, dependencies, exposed) {
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

function mountForm(t, axios, properties = []) {
  const props = Vue.reactive({ open: false, familyId: 7, property: null, properties })
  const events = []
  const form = setup(
    t,
    '../src/components/PropertyFormModal.vue',
    {
      defineProps: () => props,
      defineEmits:
        () =>
        (...args) =>
          events.push(args),
      axios,
    },
    'name, estimatedValue, acquisitionDate, sellDate, isSold, isPrincipalHome, replacementId, principalConflict, error, loading, togglePrincipalHome, cancelReplacement, confirmReplacement, submit, close',
  )
  props.open = true
  return { form, props, events }
}

test('principal-home toggle requires confirmation and cancellation leaves saved homes unchanged', async (t) => {
  const requests = []
  const previous = { id: 3, name: 'Paris apartment', is_principal_home: true }
  const { form, props, events } = mountForm(t, { post: async (...args) => requests.push(args) }, [
    previous,
  ])
  await flush()
  form.name.value = ' Lyon house '
  form.estimatedValue.value = '400000.25'
  form.acquisitionDate.value = '2020-02-29'
  form.togglePrincipalHome()
  assert.equal(form.principalConflict.value.name, 'Paris apartment')
  assert.equal(form.isPrincipalHome.value, false)
  await form.submit()
  assert.equal(requests.length, 0)
  form.cancelReplacement()
  assert.equal(form.isPrincipalHome.value, false)
  form.togglePrincipalHome()
  form.confirmReplacement()
  assert.equal(form.isPrincipalHome.value, true)
  assert.equal(props.properties[0].is_principal_home, true)
  assert.equal(events.length, 0)
  await form.submit()
  assert.deepEqual(requests, [
    [
      '/api/families/7/properties',
      {
        name: 'Lyon house',
        estimated_value: '400000.25',
        acquisition_date: '2020-02-29',
        sell_date: null,
        is_principal_home: true,
        replace_principal_home_id: 3,
      },
    ],
  ])
  assert.deepEqual(events, [['saved'], ['update:open', false]])
})

test('editing prefills fields, validates values, and retries errors without losing inputs', async (t) => {
  let fail = true
  const requests = []
  const { form, props } = mountForm(t, {
    put: async (...args) => {
      requests.push(args)
      if (fail) throw { response: { data: { error: 'Database unavailable' } } }
    },
  })
  await flush()
  props.open = false
  await flush()
  props.property = {
    id: 9,
    name: 'House',
    estimated_value: '123.45',
    is_principal_home: true,
    acquisition_date: '2020-02-29',
    sell_date: '2026-11-28',
  }
  props.open = true
  await flush()
  assert.equal(form.name.value, 'House')
  assert.equal(form.estimatedValue.value, '123.45')
  assert.equal(form.isPrincipalHome.value, true)
  assert.equal(form.acquisitionDate.value, '2020-02-29')
  assert.equal(form.sellDate.value, '2026-11-28')
  assert.equal(form.isSold.value, true)
  for (const value of ['', '-1', '1.234', 'Infinity', '1000000000000']) {
    form.estimatedValue.value = value
    await form.submit()
    assert.match(form.error.value, /estimated value/)
  }
  assert.equal(requests.length, 0)
  form.estimatedValue.value = '0'
  form.togglePrincipalHome()
  await form.submit()
  assert.equal(form.error.value, 'Database unavailable')
  assert.equal(form.name.value, 'House')
  assert.equal(form.loading.value, false)
  assert.equal(form.sellDate.value, '2026-11-28')
  form.acquisitionDate.value = '2021-01-01'
  form.isSold.value = false
  fail = false
  await form.submit()
  assert.deepEqual(requests.at(-1), [
    '/api/families/7/properties/9',
    {
      name: 'House',
      estimated_value: '0',
      acquisition_date: '2021-01-01',
      sell_date: null,
      is_principal_home: false,
      replace_principal_home_id: null,
    },
  ])
})

test('a newer principal home from the API requires fresh confirmation before retrying', async (t) => {
  let fail = true
  const requests = []
  const current = { id: 42, name: 'New principal home' }
  const { form } = mountForm(t, {
    post: async (...args) => {
      requests.push(args)
      if (fail) throw { response: { status: 409, data: { principal_home: current } } }
    },
  })
  await flush()
  form.name.value = 'House'
  form.estimatedValue.value = '200'
  form.acquisitionDate.value = '2020-02-29'
  form.togglePrincipalHome()
  await form.submit()
  assert.deepEqual(form.principalConflict.value, current)
  await form.submit()
  assert.equal(requests.length, 1)
  form.confirmReplacement()
  fail = false
  await form.submit()
  assert.equal(requests.at(-1)[1].replace_principal_home_id, 42)
})

test('property form requires a real acquisition date and rejects invalid or earlier sell dates', async (t) => {
  const requests = []
  const { form, props } = mountForm(t, { post: async (...args) => requests.push(args) })
  await flush()
  form.name.value = 'House'
  form.estimatedValue.value = '100'
  assert.equal(form.acquisitionDate.value, '')
  assert.equal(form.sellDate.value, '')
  assert.equal(form.isSold.value, false)
  for (const invalid of ['', '2021-02-29', '20200229', '0000-01-01']) {
    form.acquisitionDate.value = invalid
    await form.submit()
    assert.match(form.error.value, /valid acquisition date/)
  }
  form.acquisitionDate.value = '2020-02-29'
  form.isSold.value = true
  await form.submit()
  assert.match(form.error.value, /valid sell date/)
  form.sellDate.value = '2023-02-29'
  await form.submit()
  assert.match(form.error.value, /valid sell date/)
  form.sellDate.value = '2020-02-28'
  await form.submit()
  assert.match(form.error.value, /on or after/)
  assert.equal(requests.length, 0)
  form.sellDate.value = '2020-02-29'
  await form.submit()
  assert.equal(requests[0][1].sell_date, '2020-02-29')
  // Reopening a legacy property leaves unknown dates blank instead of guessing.
  props.open = false
  await flush()
  props.property = { id: 3, name: 'Legacy home', estimated_value: '100' }
  props.open = true
  await flush()
  assert.equal(form.acquisitionDate.value, '')
  assert.equal(form.sellDate.value, '')
  assert.equal(form.isSold.value, false)
})

test('unchecked Property sold ignores hidden dates and clears a previously saved sell date', async (t) => {
  const requests = []
  const { form, props } = mountForm(t, {
    post: async (...args) => requests.push(args),
    put: async (...args) => requests.push(args),
  })
  await flush()
  form.name.value = 'House'
  form.estimatedValue.value = '100'
  form.acquisitionDate.value = '2020-02-29'
  form.sellDate.value = '2020-02-28'
  await form.submit()
  assert.equal(requests[0][1].sell_date, null)

  props.open = false
  await flush()
  props.property = {
    id: 9,
    name: 'House',
    estimated_value: '100',
    acquisition_date: '2020-02-29',
    sell_date: '2026-11-28',
  }
  props.open = true
  await flush()
  assert.equal(form.isSold.value, true)
  assert.equal(form.sellDate.value, '2026-11-28')
  // Only unchecking is needed to remove a date entered by mistake.
  form.isSold.value = false
  await form.submit()
  assert.equal(requests.at(-1)[0], '/api/families/7/properties/9')
  assert.equal(requests.at(-1)[1].sell_date, null)
  assert.equal(props.property.sell_date, '2026-11-28')
})

function mountView(t, axios) {
  const familyStore = Vue.reactive({ familyId: 1, familyName: 'Family' })
  const view = setup(
    t,
    '../src/views/RealEstateView.vue',
    { axios, useFamilyStore: () => familyStore },
    'properties, error, loading, showForm, editingProperty, deletingProperty, deleting, deleteError, reload, openCreate, openEdit, openDelete, closeDelete, deleteProperty',
  )
  return { view, familyStore }
}

test('property cards load per family and late responses cannot overwrite the selected family', async (t) => {
  const pending = deferred()
  const { view, familyStore } = mountView(t, {
    get: (url) => (url.includes('/1/') ? pending.promise : Promise.resolve({ data: [{ id: 2 }] })),
  })
  await flush()
  view.openEdit({ id: 1 })
  assert.equal(view.editingProperty.value.id, 1)
  view.openCreate()
  assert.equal(view.editingProperty.value, null)
  familyStore.familyId = 2
  await flush()
  pending.resolve({ data: [{ id: 1 }] })
  await flush()
  assert.deepEqual(view.properties.value, [{ id: 2 }])
  assert.equal(view.showForm.value, false)
  assert.equal(view.error.value, '')
  familyStore.familyId = 0
  await flush()
  assert.deepEqual(view.properties.value, [])
  assert.equal(view.loading.value, false)
})

test('permanent deletion retries failures, prevents duplicate requests, and refreshes cards', async (t) => {
  let fail = true,
    loads = 0
  const requests = [],
    pending = deferred()
  const { view } = mountView(t, {
    get: async () => {
      loads++
      return { data: [{ id: 3 }] }
    },
    delete: async (url) => {
      requests.push(url)
      if (fail) throw new Error('Offline')
      await pending.promise
    },
  })
  await flush()
  view.openDelete({ id: 3 })
  await view.deleteProperty()
  assert.match(view.deleteError.value, /Failed to delete/)
  assert.equal(view.deletingProperty.value.id, 3)
  fail = false
  const saving = view.deleteProperty()
  view.closeDelete()
  await view.deleteProperty()
  assert.equal(view.deletingProperty.value.id, 3)
  assert.equal(requests.length, 2)
  pending.resolve()
  await saving
  await flush()
  assert.equal(view.deletingProperty.value, null)
  assert.equal(loads, 2)
  assert.deepEqual(requests, ['/api/families/1/properties/3', '/api/families/1/properties/3'])
})
