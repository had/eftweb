import { formatUSDCents } from './numberFormat.js'

export const isUSDPrice = (price) =>
  typeof price === 'string' && /^\d+\.\d{2}$/.test(price) && BigInt(price.replace('.', '')) > 0n

// Multiplication stays in integer cents, even for large valid share quantities.
export function formatStockValue(quantity, price) {
  if (!Number.isSafeInteger(quantity) || quantity < 0 || !isUSDPrice(price)) return '—'
  const cents = BigInt(quantity) * BigInt(price.replace('.', ''))
  return formatUSDCents(cents)
}

export function formatQuoteTimestamp(value) {
  const date = new Date(value)
  return value && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
    : ''
}
