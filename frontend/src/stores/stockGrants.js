import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { grantColor } from '../components/stock-detail/vesting.js'

const errorMessage = (error, fallback) => error.response?.data?.error || fallback
const fromApi = (grant) => ({
  id: grant.id,
  stockId: grant.stock_id,
  title: grant.title,
  grantNumber: grant.grant_number || '',
  grantDate: grant.grant_date,
  quantity: grant.quantity,
  startDate: grant.vesting_start_date,
  scheduleType: grant.schedule_type,
  customized: grant.customized,
  vestings: grant.vestings,
  color: grantColor(grant.id - 1),
})
const saleFromApi = (sale) => ({
  id: sale.id,
  stockId: sale.stock_id,
  transactionDate: sale.transaction_date,
  quantity: sale.quantity,
  proceedsPerShare: sale.proceeds_per_share,
  currency: sale.currency,
  allocations: sale.allocations.map(({ vesting_id, purchase_id, quantity }) => ({
    ...(purchase_id !== undefined ? { purchaseId: purchase_id } : { vestingId: vesting_id }),
    quantity,
  })),
})
const purchaseFromApi = (purchase) => ({
  id: purchase.id,
  stockId: purchase.stock_id,
  purchaseDate: purchase.purchase_date,
  quantity: purchase.quantity,
  planName: purchase.plan_name,
})
const purchaseOrder = (a, b) => a.purchaseDate.localeCompare(b.purchaseDate) || a.id - b.id
const saleOrder = (a, b) => a.transactionDate.localeCompare(b.transactionDate) || a.id - b.id
const busy = (entry) =>
  entry.saving ||
  entry.deletingId !== null ||
  entry.savingSale ||
  entry.deletingSaleId !== null ||
  entry.savingPurchase ||
  entry.deletingPurchaseId !== null
const byDate = (a, b) => a.grantDate.localeCompare(b.grantDate) || a.id - b.id

export const useStockGrantsStore = defineStore('stockGrants', () => {
  const stocks = ref({})
  const pendingWrites = new Map()

  function forStock(stockId) {
    if (!stocks.value[stockId])
      stocks.value[stockId] = {
        stock: null,
        grants: [],
        purchases: [],
        savingPurchase: false,
        purchaseSaveError: '',
        deletingPurchaseId: null,
        purchaseDeleteError: '',
        sales: [],
        savingSale: false,
        saleSaveError: '',
        deletingSaleId: null,
        saleDeleteError: '',
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
      const [stock, grants, sales, purchases] = await Promise.all([
        axios.get(`/api/stocks/${stockId}`),
        axios.get(`/api/stocks/${stockId}/grants`),
        axios.get(`/api/stocks/${stockId}/sales`),
        axios.get(`/api/stocks/${stockId}/purchases`),
      ])
      if (generation !== entry.loadGeneration) return false
      entry.stock = stock.data
      entry.grants = grants.data.map(fromApi).sort(byDate)
      entry.sales = sales.data.map(saleFromApi).sort(saleOrder)
      entry.purchases = purchases.data.map(purchaseFromApi).sort(purchaseOrder)
      entry.loaded = true
      return true
    } catch (error) {
      if (generation === entry.loadGeneration) {
        entry.loaded = false
        entry.loadError = errorMessage(
          error,
          'Could not load this stock, its grants, purchases and sales. Please try again.',
        )
      }
      return false
    } finally {
      if (generation === entry.loadGeneration) entry.loading = false
    }
  }

  async function createGrant(stockId, draft) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || busy(entry)) return null
    entry.saving = true
    entry.saveError = ''
    let request
    try {
      const payload = {
        title: draft.title,
        ...(draft.grantNumber?.trim() ? { grant_number: draft.grantNumber.trim() } : {}),
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
    if (!entry.loaded || entry.loading || busy(entry)) return false
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

  async function updateGrantNumber(stockId, grantId, number) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || busy(entry)) return null
    entry.saving = true
    entry.saveError = ''
    let request
    try {
      request = axios.patch(`/api/stocks/${stockId}/grants/${grantId}`, {
        grant_number: number.trim() || null,
      })
      pendingWrites.set(stockId, request)
      const saved = fromApi((await request).data)
      entry.grants = entry.grants.map((grant) => (grant.id === saved.id ? saved : grant))
      return saved
    } catch (error) {
      entry.saveError = errorMessage(error, 'Could not update the grant number. Please try again.')
      return null
    } finally {
      entry.saving = false
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  async function createSale(stockId, draft) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || busy(entry)) return null
    entry.savingSale = true
    entry.saleSaveError = ''
    let request
    try {
      request = axios.post(
        `/api/stocks/${stockId}/sales`,
        {
          transaction_date: draft.transactionDate,
          quantity: draft.quantity,
          proceeds_per_share: draft.proceedsPerShare,
          allocations: draft.allocations.map(({ vestingId, purchaseId, quantity }) => ({
            ...(purchaseId !== undefined ? { purchase_id: purchaseId } : { vesting_id: vestingId }),
            quantity,
          })),
        },
        { headers: { 'Idempotency-Key': draft.creationToken } },
      )
      pendingWrites.set(stockId, request)
      const response = await request
      const saved = saleFromApi(response.data)
      entry.sales = [...entry.sales.filter((sale) => sale.id !== saved.id), saved].sort(saleOrder)
      return saved
    } catch (error) {
      entry.saleSaveError = errorMessage(
        error,
        'Could not save the sale. Your draft is still here; please try again.',
      )
      return null
    } finally {
      entry.savingSale = false
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  async function deleteSale(stockId, saleId) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || busy(entry)) return false
    entry.deletingSaleId = saleId
    entry.saleDeleteError = ''
    let request
    try {
      request = axios.delete(`/api/stocks/${stockId}/sales/${saleId}`)
      pendingWrites.set(stockId, request)
      await request
      entry.sales = entry.sales.filter((sale) => sale.id !== saleId)
      return true
    } catch (error) {
      entry.saleDeleteError = errorMessage(error, 'Could not delete the sale. Please try again.')
      return false
    } finally {
      entry.deletingSaleId = null
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  async function createPurchase(stockId, draft) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || busy(entry)) return null
    entry.savingPurchase = true
    entry.purchaseSaveError = ''
    let request
    try {
      request = axios.post(
        `/api/stocks/${stockId}/purchases`,
        {
          purchase_date: draft.purchaseDate,
          quantity: draft.quantity,
          plan_name: 'ESPP',
        },
        { headers: { 'Idempotency-Key': draft.creationToken } },
      )
      pendingWrites.set(stockId, request)
      const response = await request
      const saved = purchaseFromApi(response.data)
      entry.purchases = [
        ...entry.purchases.filter((purchase) => purchase.id !== saved.id),
        saved,
      ].sort(purchaseOrder)
      return saved
    } catch (error) {
      entry.purchaseSaveError = errorMessage(
        error,
        'Could not save the purchase. Your draft is still here; please try again.',
      )
      return null
    } finally {
      entry.savingPurchase = false
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  async function deletePurchase(stockId, purchaseId) {
    const entry = forStock(stockId)
    if (!entry.loaded || entry.loading || busy(entry)) return false
    entry.deletingPurchaseId = purchaseId
    entry.purchaseDeleteError = ''
    let request
    try {
      request = axios.delete(`/api/stocks/${stockId}/purchases/${purchaseId}`)
      pendingWrites.set(stockId, request)
      await request
      entry.purchases = entry.purchases.filter((purchase) => purchase.id !== purchaseId)
      return true
    } catch (error) {
      entry.purchaseDeleteError = errorMessage(
        error,
        'Could not delete the purchase. Please try again.',
      )
      return false
    } finally {
      entry.deletingPurchaseId = null
      if (pendingWrites.get(stockId) === request) pendingWrites.delete(stockId)
    }
  }

  return {
    stocks,
    forStock,
    load,
    createGrant,
    updateGrantNumber,
    deleteGrant,
    createSale,
    deleteSale,
    createPurchase,
    deletePurchase,
  }
})
