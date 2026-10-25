import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { grantColor } from '../components/stock-detail/vesting.js'

const errorMessage = (error, fallback) => error.response?.data?.error || fallback
const fromApi = (grant) => ({
  id: grant.id,
  stockId: grant.stock_id,
  title: grant.title,
  grantDate: grant.grant_date,
  quantity: grant.quantity,
  startDate: grant.vesting_start_date,
  scheduleType: grant.schedule_type,
  customized: grant.customized,
  vestings: grant.vestings,
  color: grantColor(grant.id - 1),
})
const byDate = (a, b) => a.grantDate.localeCompare(b.grantDate) || a.id - b.id

export const useStockGrantsStore = defineStore('stockGrants', () => {
  const stocks = ref({})
  const pendingWrites = new Map()

  function forStock(stockId) {
    if (!stocks.value[stockId])
      stocks.value[stockId] = {
        stock: null,
        grants: [],
        loading: false,
        loaded: false,
        loadError: '',
        saving: false,
        saveError: '',
        deletingId: null,
        deleteError: '',
        loadGeneration: 0,
      }
    return stocks.value[stockId]
  }

  async function load(stockId) {
    const entry = forStock(stockId)
    const generation = ++entry.loadGeneration
    entry.loading = true
    entry.loadError = ''
    try {
      if (!Number.isSafeInteger(stockId) || stockId <= 0) throw new Error('Invalid stock')
      // A refresh must read after any write already in progress for this stock.
      const pending = pendingWrites.get(stockId)
      if (pending) await pending.catch(() => {})
      if (generation !== entry.loadGeneration) return false
      const [stock, grants] = await Promise.all([
        axios.get(`/api/stocks/${stockId}`),
        axios.get(`/api/stocks/${stockId}/grants`),
      ])
      if (generation !== entry.loadGeneration) return false
      entry.stock = stock.data
      entry.grants = grants.data.map(fromApi).sort(byDate)
      entry.loaded = true
      return true
    } catch (error) {
      if (generation === entry.loadGeneration) {
        entry.loaded = false
        entry.loadError = errorMessage(
          error,
          'Could not load this stock and its grants. Please try again.',
        )
      }
      return false
    } finally {
      if (generation === entry.loadGeneration) entry.loading = false
    }
  }

  async function createGrant(stockId, draft) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || entry.saving || entry.deletingId !== null) return null
    entry.saving = true
    entry.saveError = ''
    let request
    try {
      const payload = {
        title: draft.title,
        grant_date: draft.grantDate,
        quantity: draft.quantity,
        vesting_start_date: draft.startDate,
        schedule_type: draft.scheduleType,
        customized: draft.customized,
        vestings: draft.vestings.map(({ date, quantity }) => ({ date, quantity })),
      }
      request = axios.post(`/api/stocks/${stockId}/grants`, payload, {
        headers: { 'Idempotency-Key': draft.creationToken },
      })
      pendingWrites.set(stockId, request)
      const response = await request
      const saved = fromApi(response.data)
      entry.grants = [...entry.grants.filter((grant) => grant.id !== saved.id), saved].sort(byDate)
      return saved
    } catch (error) {
      entry.saveError = errorMessage(
        error,
        'Could not save the grant. Your draft is still here; please try again.',
      )
      return null
    } finally {
      entry.saving = false
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  async function deleteGrant(stockId, grantId) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || entry.saving || entry.deletingId !== null) return false
    entry.deletingId = grantId
    entry.deleteError = ''
    let request
    try {
      request = axios.delete(`/api/stocks/${stockId}/grants/${grantId}`)
      pendingWrites.set(stockId, request)
      await request
      entry.grants = entry.grants.filter((grant) => grant.id !== grantId)
      return true
    } catch (error) {
      entry.deleteError = errorMessage(error, 'Could not delete the grant. Please try again.')
      return false
    } finally {
      entry.deletingId = null
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  return { stocks, forStock, load, createGrant, deleteGrant }
})
