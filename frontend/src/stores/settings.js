import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { DEFAULT_NUMBER_LOCALE, isNumberLocale, numberLocale } from '../lib/numberFormat.js'

const defaultTheme = 'sage-slate'
const validThemes = new Set(['sage-slate', 'mist-blue', 'warm-stone', 'midnight-slate'])

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref(defaultTheme)
  const loadError = ref('')
  const saveError = ref('')
  const saving = ref(false)

  function applyTheme(value) {
    theme.value = value
    document.documentElement.dataset.theme = value
    document.documentElement.classList.toggle('dark', value === 'midnight-slate')
  }

  async function loadSettings() {
    try {
      const response = await axios.get('/api/settings', { timeout: 5000 })
      if (!validThemes.has(response.data?.theme)) throw new Error('Invalid theme setting')
      const locale = response.data.number_locale ?? DEFAULT_NUMBER_LOCALE
      if (!isNumberLocale(locale)) throw new Error('Invalid number locale setting')
      applyTheme(response.data.theme)
      numberLocale.value = locale
      loadError.value = ''
    } catch {
      applyTheme(defaultTheme)
      numberLocale.value = DEFAULT_NUMBER_LOCALE
      loadError.value = 'Could not load saved settings. Using the defaults.'
    }
  }

  async function selectTheme(value) {
    if (saving.value || !validThemes.has(value) || value === theme.value) return
    saving.value = true
    saveError.value = ''
    try {
      const response = await axios.put('/api/settings', { theme: value }, { timeout: 5000 })
      if (response.data?.theme !== value) throw new Error('Unexpected saved theme')
      applyTheme(value)
      loadError.value = ''
    } catch {
      saveError.value = 'Could not save the theme. Please try again.'
    } finally {
      saving.value = false
    }
  }

  async function selectNumberLocale(value) {
    if (saving.value || !isNumberLocale(value) || value === numberLocale.value) return
    saving.value = true
    saveError.value = ''
    try {
      const response = await axios.put('/api/settings', { number_locale: value }, { timeout: 5000 })
      if (response.data?.number_locale !== value) throw new Error('Unexpected saved number locale')
      numberLocale.value = value
      loadError.value = ''
    } catch {
      saveError.value = 'Could not save the number format. Please try again.'
    } finally {
      saving.value = false
    }
  }

  return {
    theme,
    numberLocale,
    loadError,
    saveError,
    saving,
    loadSettings,
    selectTheme,
    selectNumberLocale,
  }
})
