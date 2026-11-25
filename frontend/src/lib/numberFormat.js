import { ref } from 'vue'

export const DEFAULT_NUMBER_LOCALE = 'en-GB'
export const NUMBER_LOCALES = [
  { id: 'en-GB', name: 'English (United Kingdom)' },
  { id: 'en-US', name: 'English (United States)' },
  { id: 'fr-FR', name: 'Français (France)' },
  { id: 'de-DE', name: 'Deutsch (Deutschland)' },
  { id: 'es-ES', name: 'Español (España)' },
  { id: 'it-IT', name: 'Italiano (Italia)' },
]
export const isNumberLocale = (value) => NUMBER_LOCALES.some((locale) => locale.id === value)

// Shared with the settings store so helpers also track locale changes inside Vue effects.
export const numberLocale = ref(DEFAULT_NUMBER_LOCALE)

export function formatNumber(value, options = {}, locale = numberLocale.value) {
  return value == null ? '—' : new Intl.NumberFormat(locale, options).format(value)
}

export const formatCurrency = (value, currency = 'EUR') =>
  formatNumber(value, { style: 'currency', currency })

export const formatPercent = (value) =>
  formatNumber(value, { style: 'percent', maximumFractionDigits: 1 })

// Decimal strings from tax calculations retain their displayed precision.
export const formatDecimal = (value) =>
  formatNumber(value, {
    minimumFractionDigits:
      typeof value === 'string' ? Math.min(value.split('.')[1]?.length || 0, 20) : 0,
    maximumFractionDigits: 20,
  })

// Keep integer cents exact, including totals beyond Number.MAX_SAFE_INTEGER.
export function formatUSDCents(cents) {
  const formatter = new Intl.NumberFormat(numberLocale.value, {
    style: 'currency',
    currency: 'USD',
    currencyDisplay: 'narrowSymbol',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return formatter
    .formatToParts(cents / 100n)
    .map((part) => (part.type === 'fraction' ? String(cents % 100n).padStart(2, '0') : part.value))
    .join('')
}
