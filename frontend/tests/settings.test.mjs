import assert from 'node:assert/strict'
import test from 'node:test'
import { createPinia } from 'pinia'
import axios from 'axios'
import { useSettingsStore } from '../src/stores/settings.js'
import { numberLocale } from '../src/lib/numberFormat.js'

function setup(t) {
  const originalGet = axios.get
  const originalPut = axios.put
  const originalDocument = globalThis.document
  const root = { dataset: {}, classList: { toggle() {} } }
  globalThis.document = { documentElement: root }
  numberLocale.value = 'en-GB'
  t.after(() => {
    axios.get = originalGet
    axios.put = originalPut
    globalThis.document = originalDocument
    numberLocale.value = 'en-GB'
  })
  return { store: useSettingsStore(createPinia()), root }
}

test('saved settings load the locale and theme; theme-only installations use en-GB', async (t) => {
  const { store, root } = setup(t)
  axios.get = async () => ({ data: { theme: 'mist-blue', number_locale: 'fr-FR' } })
  await store.loadSettings()
  assert.equal(store.numberLocale, 'fr-FR')
  assert.equal(numberLocale.value, 'fr-FR')
  assert.equal(root.dataset.theme, 'mist-blue')
  axios.get = async () => ({ data: { theme: 'warm-stone' } })
  await store.loadSettings()
  assert.equal(store.numberLocale, 'en-GB')
  assert.equal(store.theme, 'warm-stone')
})

test('failed or invalid settings loads restore defaults with an error', async (t) => {
  const { store } = setup(t)
  for (const data of [{ theme: 'mist-blue', number_locale: 'invalid' }, null]) {
    numberLocale.value = 'fr-FR'
    axios.get = async () => ({ data })
    await store.loadSettings()
    assert.equal(store.numberLocale, 'en-GB')
    assert.equal(store.theme, 'sage-slate')
    assert.ok(store.loadError)
  }
  axios.get = async () => {
    throw new Error('Offline')
  }
  await store.loadSettings()
  assert.ok(store.loadError)
})

test('locale changes apply after persistence, block concurrent saves and retain the theme', async (t) => {
  const { store } = setup(t)
  let resolve,
    calls = 0
  axios.put = (url, body) => {
    calls++
    assert.equal(url, '/api/settings')
    assert.deepEqual(body, { number_locale: 'fr-FR' })
    return new Promise((done) => {
      resolve = done
    })
  }
  const pending = store.selectNumberLocale('fr-FR')
  assert.equal(store.saving, true)
  assert.equal(store.numberLocale, 'en-GB')
  await store.selectTheme('mist-blue')
  await store.selectNumberLocale('en-US')
  assert.equal(calls, 1)
  resolve({ data: { theme: 'sage-slate', number_locale: 'fr-FR' } })
  await pending
  assert.equal(store.numberLocale, 'fr-FR')
  assert.equal(store.theme, 'sage-slate')
  assert.equal(store.saving, false)
  axios.put = async (url, body) => ({ data: { ...body, number_locale: 'fr-FR' } })
  await store.selectTheme('mist-blue')
  assert.equal(store.theme, 'mist-blue')
  assert.equal(store.numberLocale, 'fr-FR')
})

test('failed or unexpected locale saves preserve the saved format and permit retry', async (t) => {
  const { store } = setup(t)
  axios.put = async () => {
    throw new Error('Offline')
  }
  await store.selectNumberLocale('fr-FR')
  assert.equal(store.numberLocale, 'en-GB')
  assert.ok(store.saveError)
  assert.equal(store.saving, false)
  axios.put = async () => ({ data: { number_locale: 'en-US' } })
  await store.selectNumberLocale('fr-FR')
  assert.equal(store.numberLocale, 'en-GB')
  assert.ok(store.saveError)
  axios.put = async () => ({ data: { number_locale: 'fr-FR' } })
  await store.selectNumberLocale('fr-FR')
  assert.equal(store.numberLocale, 'fr-FR')
  assert.equal(store.saveError, '')
  axios.put = () => {
    assert.fail('Invalid or unchanged settings must not be sent')
  }
  await store.selectNumberLocale('invalid')
  await store.selectNumberLocale('fr-FR')
})
