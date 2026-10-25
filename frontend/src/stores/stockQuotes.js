import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { isUSDPrice } from '../lib/stockQuotes.js'

const hour = 60 * 60 * 1000
const cooldown = 5 * 60 * 1000
const normalize = (symbol) => (symbol || '').trim().toUpperCase()

export const useStockQuotesStore = defineStore('stockQuotes', () => {
  const quotes = ref({})
  const pending = new Map()

  function forSymbol(symbol) {
    const key = normalize(symbol)
    if (!quotes.value[key])
      quotes.value[key] = { quote: null, loading: false, error: '', nextCheckAt: 0 }
    return quotes.value[key]
  }

  function load(stock) {
    const symbol = normalize(stock?.symbol)
    if (!symbol || !Number.isSafeInteger(stock?.id) || stock.id <= 0) return Promise.resolve(null)
    const entry = forSymbol(symbol)
    if (pending.has(symbol)) return pending.get(symbol)
    if (Date.now() < entry.nextCheckAt) return Promise.resolve(entry.quote)
    entry.loading = true
    const request = (async () => {
      await Promise.resolve()
      try {
        const response = await axios.get(`/api/stocks/${stock.id}/quote`)
        const quote = response.data
        if (
          quote?.symbol !== symbol ||
          quote.currency !== 'USD' ||
          (quote.price !== null && !isUSDPrice(quote.price))
        ) {
          throw new Error('Invalid quote response')
        }
        entry.quote = quote
        entry.error = quote.error || ''
        const fetched = Date.parse(quote.fetched_at)
        entry.nextCheckAt =
          quote.price !== null && !quote.stale && Number.isFinite(fetched)
            ? Math.min(Date.now() + hour, fetched + hour)
            : Date.now() + cooldown
        return quote
      } catch {
        entry.error = 'Price unavailable. Please try again later.'
        if (entry.quote?.price !== null && isUSDPrice(entry.quote?.price)) {
          entry.quote = { ...entry.quote, stale: true, error: entry.error }
        }
        entry.nextCheckAt = Date.now() + cooldown
        return entry.quote
      } finally {
        entry.loading = false
        pending.delete(symbol)
      }
    })()
    pending.set(symbol, request)
    return request
  }

  return { quotes, forSymbol, load }
})
