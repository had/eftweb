<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, ChevronDown, Download, Plus } from 'lucide-vue-next'
import {
  DropdownMenuRoot,
  DropdownMenuTrigger,
  DropdownMenuPortal,
  DropdownMenuContent,
  DropdownMenuItem,
  TabsContent,
  TabsList,
  TabsRoot,
  TabsTrigger,
} from 'reka-ui'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import VestingTimeline from '@/components/stock-detail/VestingTimeline.vue'
import HoldingsAndSales from '@/components/stock-detail/HoldingsAndSales.vue'
import GrantsOverview from '@/components/stock-detail/GrantsOverview.vue'
import AddGrantWizardModal from '@/components/stock-detail/AddGrantWizardModal.vue'
import AddPurchaseModal from '@/components/stock-detail/AddPurchaseModal.vue'
import RecordSaleModal from '@/components/stock-detail/RecordSaleModal.vue'
import DeleteConfirmModal from '@/components/DeleteConfirmModal.vue'
import { useStockGrantsStore } from '@/stores/stockGrants'
import { useStockQuotesStore } from '@/stores/stockQuotes'
import StockQuote from '@/components/StockQuote.vue'
import { formatStockValue } from '@/lib/stockQuotes.js'
import { downloadStockExport } from '@/lib/stockExport.js'
import { formatShares, localDate, summarizePortfolio } from '@/components/stock-detail/vesting.js'

const activeTab = ref('vesting')
const route = useRoute()
const grantsStore = useStockGrantsStore()
const quotesStore = useStockQuotesStore()
const stockId = computed(() => Number(route.params.stockId))
const entry = computed(() => grantsStore.forStock(stockId.value))
const grants = computed(() => entry.value.grants)
const stockName = computed(() => entry.value.stock?.name || 'Stock')
const stockSymbol = computed(() => entry.value.stock?.symbol || '')
const quoteEntry = computed(() => quotesStore.forSymbol(stockSymbol.value))
const ready = computed(() => entry.value.loaded && !entry.value.loading && !entry.value.loadError)
const showAddGrant = ref(false)
const showAddPurchase = ref(false)
const purchaseToDelete = ref(null)
const showRecordSale = ref(false)
const saleToDelete = ref(null)
const busy = computed(
  () =>
    entry.value.saving ||
    entry.value.deletingId !== null ||
    entry.value.savingSale ||
    entry.value.deletingSaleId !== null ||
    entry.value.savingPurchase ||
    entry.value.deletingPurchaseId !== null,
)
const grantToDelete = ref(null)
let viewGeneration = 0
const exporting = ref(false)
const exportError = ref('')
let exportController
const cancelExport = () => {
  exportController?.abort()
  exportController = null
  exporting.value = false
  exportError.value = ''
}
const exportStock = async () => {
  if (!ready.value || busy.value || exporting.value) return
  const generation = viewGeneration
  const controller = new AbortController()
  exportController = controller
  exporting.value = true
  exportError.value = ''
  try {
    await downloadStockExport(stockId.value, controller.signal)
  } catch (error) {
    if (generation === viewGeneration) exportError.value = error.message
  } finally {
    if (generation === viewGeneration) {
      exporting.value = false
      exportController = null
    }
  }
}
const today = ref(localDate())
let dateTimer
onMounted(() => {
  dateTimer = setInterval(() => {
    today.value = localDate()
  }, 60000)
})
onBeforeUnmount(() => {
  clearInterval(dateTimer)
  viewGeneration += 1
  cancelExport()
})
watch(
  () => route.params.stockId,
  () => {
    viewGeneration += 1
    cancelExport()
    showAddGrant.value = false
    showAddPurchase.value = false
    purchaseToDelete.value = null
    showRecordSale.value = false
    saleToDelete.value = null
    grantToDelete.value = null
    activeTab.value = 'vesting'
    void grantsStore.load(stockId.value)
  },
  { flush: 'sync', immediate: true },
)
watch(showAddGrant, (open) => {
  if (open) entry.value.saveError = ''
})
watch(showRecordSale, (open) => {
  if (open) entry.value.saleSaveError = ''
})
watch(showAddPurchase, (open) => {
  if (open) entry.value.purchaseSaveError = ''
})
const addPurchase = async (draft) => {
  const generation = viewGeneration
  const saved = await grantsStore.createPurchase(stockId.value, draft)
  if (saved && generation === viewGeneration) {
    showAddPurchase.value = false
    activeTab.value = 'vesting'
  }
}
const requestDeletePurchase = (purchase) => {
  if (!ready.value || busy.value) return
  entry.value.purchaseDeleteError = ''
  purchaseToDelete.value = purchase
}
const deletePurchase = async () => {
  if (!purchaseToDelete.value) return
  const generation = viewGeneration
  const deleted = await grantsStore.deletePurchase(stockId.value, purchaseToDelete.value.id)
  if (deleted && generation === viewGeneration) purchaseToDelete.value = null
}
const recordSale = async (draft) => {
  const generation = viewGeneration
  const saved = await grantsStore.createSale(stockId.value, draft)
  if (saved && generation === viewGeneration) showRecordSale.value = false
}
const requestDeleteSale = (sale) => {
  if (!ready.value || busy.value) return
  entry.value.saleDeleteError = ''
  saleToDelete.value = sale
}
const deleteSale = async () => {
  if (!saleToDelete.value) return
  const generation = viewGeneration
  const deleted = await grantsStore.deleteSale(stockId.value, saleToDelete.value.id)
  if (deleted && generation === viewGeneration) saleToDelete.value = null
}
const addGrant = async (grant) => {
  const id = stockId.value
  const generation = viewGeneration
  const saved = await grantsStore.createGrant(id, grant)
  if (saved && generation === viewGeneration) {
    showAddGrant.value = false
    activeTab.value = 'vesting'
  }
}
const requestDeleteGrant = (grant) => {
  if (!ready.value || busy.value) return
  entry.value.deleteError = ''
  grantToDelete.value = grant
}
const deleteGrant = async () => {
  if (!grantToDelete.value) return
  const generation = viewGeneration
  const deleted = await grantsStore.deleteGrant(stockId.value, grantToDelete.value.id)
  if (deleted && generation === viewGeneration) grantToDelete.value = null
}
const tabs = [
  { value: 'vesting', label: 'Acquisition timeline' },
  { value: 'holdings', label: 'Holdings & sales' },
  { value: 'grants', label: 'Plans & purchases' },
]
const portfolio = computed(() =>
  summarizePortfolio(grants.value, entry.value.purchases, today.value),
)
const summaries = computed(() => [
  {
    label: 'Total shares',
    value: portfolio.value.total,
    detail: 'Granted and purchased, including scheduled shares',
  },
  {
    label: 'Acquired shares',
    value: portfolio.value.acquired,
    detail: 'Before any sales',
    emphasized: true,
  },
  { label: 'Still to vest', value: portfolio.value.unvested, detail: 'From entered grants' },
  { label: 'Next 12 months', value: portfolio.value.nextTwelveMonths, detail: 'Scheduled to vest' },
])
</script>

<template>
  <main class="min-w-0 flex-1 p-6 lg:p-8">
    <div class="mx-auto max-w-7xl space-y-6">
      <div class="space-y-2">
        <div class="flex items-center justify-between gap-4">
          <RouterLink
            to="/stocks"
            class="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft class="h-4 w-4" /> All stocks
          </RouterLink>
          <Button
            variant="outline"
            :disabled="!ready || busy || exporting"
            :aria-busy="exporting"
            @click="exportStock"
          >
            <Download class="h-4 w-4" /> {{ exporting ? 'Exporting…' : 'Export' }}
          </Button>
        </div>
        <p v-if="exportError" role="alert" class="text-right text-sm text-destructive">
          {{ exportError }}
        </p>
      </div>

      <header class="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <div class="flex min-w-0 flex-wrap items-center gap-3">
          <h1 class="break-words text-3xl font-bold tracking-tight">{{ stockName }}</h1>
          <span class="shrink-0 rounded-md border bg-card px-2 py-1 text-xs font-medium">{{
            stockSymbol
          }}</span>
        </div>
        <StockQuote
          v-if="entry.stock"
          :stock="entry.stock"
          compact
          class="ml-auto shrink-0 text-right"
        />
      </header>

      <div
        v-if="entry.loading"
        role="status"
        aria-label="Loading stock, grants, purchases and sales"
        class="space-y-4"
      >
        <div class="h-28 animate-pulse rounded-lg bg-muted" />
        <div class="h-64 animate-pulse rounded-lg bg-muted" />
      </div>
      <div v-else-if="entry.loadError" class="space-y-3 rounded-lg border p-5">
        <p role="alert" class="text-destructive">{{ entry.loadError }}</p>
        <Button variant="outline" @click="grantsStore.load(stockId)">Retry</Button>
      </div>
      <template v-else-if="ready">
        <section aria-label="Portfolio summary" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Card
            v-for="summary in summaries"
            :key="summary.label"
            class="py-0"
            :class="summary.emphasized && 'border-primary/40 bg-primary/5'"
          >
            <CardContent class="p-5">
              <h2 class="text-sm text-muted-foreground">{{ summary.label }}</h2>
              <div class="my-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p
                  class="text-3xl font-semibold tracking-tight tabular-nums"
                  :class="summary.emphasized && 'text-primary'"
                >
                  {{ formatShares(summary.value)
                  }}<span class="ml-2 text-xs font-normal text-muted-foreground">shares</span>
                </p>
                <span
                  class="break-all text-sm font-medium tabular-nums text-muted-foreground"
                  :aria-label="`Estimated USD value of ${summary.label}`"
                  >{{
                    quoteEntry.loading && !quoteEntry.quote?.price
                      ? 'Loading…'
                      : formatStockValue(summary.value, quoteEntry.quote?.price)
                  }}</span
                >
              </div>
              <p class="text-xs text-muted-foreground">{{ summary.detail }}</p>
            </CardContent>
          </Card>
        </section>
        <p class="text-xs text-muted-foreground">
          Estimated USD values use
          {{ quoteEntry.quote?.stale ? 'the cached' : 'the latest available' }} stock price. Future
          vesting values are estimates.
        </p>

        <TabsRoot v-model="activeTab" class="w-full">
          <TabsList
            aria-label="Stock portfolio views"
            class="mb-6 flex max-w-full gap-1 overflow-x-auto rounded-lg bg-muted p-1"
          >
            <TabsTrigger
              v-for="tab in tabs"
              :key="tab.value"
              :value="tab.value"
              class="shrink-0 rounded-md px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm"
            >
              {{ tab.label }}
            </TabsTrigger>
          </TabsList>
          <TabsContent
            value="vesting"
            class="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <VestingTimeline :grants="grants" :purchases="entry.purchases" :today="today">
              <template #actions>
                <DropdownMenuRoot>
                  <DropdownMenuTrigger as-child>
                    <Button variant="outline" :disabled="busy"
                      ><Plus class="h-4 w-4" /> Add <ChevronDown class="h-4 w-4"
                    /></Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuPortal>
                    <DropdownMenuContent
                      align="end"
                      :side-offset="6"
                      class="z-50 min-w-44 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
                    >
                      <DropdownMenuItem
                        class="cursor-pointer rounded-sm px-3 py-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                        @select="showAddGrant = true"
                        >RSU grant</DropdownMenuItem
                      >
                      <DropdownMenuItem
                        class="cursor-pointer rounded-sm px-3 py-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                        @select="showAddPurchase = true"
                        >ESPP purchase</DropdownMenuItem
                      >
                    </DropdownMenuContent>
                  </DropdownMenuPortal>
                </DropdownMenuRoot>
              </template>
            </VestingTimeline>
          </TabsContent>
          <TabsContent
            value="holdings"
            class="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <HoldingsAndSales
              :key="stockId"
              :grants="grants"
              :purchases="entry.purchases"
              :sales="entry.sales"
              :today="today"
              :busy="busy"
              @delete-sale="requestDeleteSale"
            >
              <template #actions>
                <Button :disabled="busy" @click="showRecordSale = true"
                  ><ArrowUpRight class="h-4 w-4" /> Record sale</Button
                >
              </template>
            </HoldingsAndSales>
          </TabsContent>
          <TabsContent
            value="grants"
            class="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <GrantsOverview
              :grants="grants"
              :purchases="entry.purchases"
              :today="today"
              :busy="busy"
              @delete="requestDeleteGrant"
              @delete-purchase="requestDeletePurchase"
            />
          </TabsContent>
        </TabsRoot>
        <AddGrantWizardModal
          :key="route.params.stockId"
          v-model:open="showAddGrant"
          :ticker="stockSymbol"
          :saving="entry.saving"
          :save-error="entry.saveError"
          @confirmed="addGrant"
        />
        <RecordSaleModal
          :key="`sale-${stockId}`"
          v-model:open="showRecordSale"
          :ticker="stockSymbol"
          :grants="grants"
          :purchases="entry.purchases"
          :sales="entry.sales"
          :today="today"
          :saving="entry.savingSale"
          :save-error="entry.saleSaveError"
          @confirmed="recordSale"
        />
        <AddPurchaseModal
          :key="`purchase-${stockId}`"
          v-model:open="showAddPurchase"
          :ticker="stockSymbol"
          :today="today"
          :saving="entry.savingPurchase"
          :save-error="entry.purchaseSaveError"
          @confirmed="addPurchase"
        />
        <DeleteConfirmModal
          :open="Boolean(purchaseToDelete)"
          title="Delete purchase"
          :description="
            purchaseToDelete
              ? `Permanently delete the ${purchaseToDelete.planName} purchase of ${formatShares(purchaseToDelete.quantity)} shares on ${purchaseToDelete.purchaseDate}? This cannot be undone.`
              : ''
          "
          confirm-label="Delete purchase"
          :busy="entry.deletingPurchaseId !== null"
          :error="entry.purchaseDeleteError"
          @update:open="
            (open) => {
              if (!open && entry.deletingPurchaseId === null) purchaseToDelete = null
            }
          "
          @cancel="purchaseToDelete = null"
          @confirm="deletePurchase"
        />
        <DeleteConfirmModal
          :open="Boolean(saleToDelete)"
          title="Delete sale"
          :description="
            saleToDelete
              ? `Delete the sale of ${formatShares(saleToDelete.quantity)} shares on ${saleToDelete.transactionDate}? The shares will become available in their original acquisition lots. This cannot be undone.`
              : 'The shares will become available in their original acquisition lots.'
          "
          confirm-label="Delete sale"
          :busy="entry.deletingSaleId !== null"
          :error="entry.saleDeleteError"
          @update:open="
            (open) => {
              if (!open && entry.deletingSaleId === null) saleToDelete = null
            }
          "
          @cancel="saleToDelete = null"
          @confirm="deleteSale"
        />
        <DeleteConfirmModal
          :open="Boolean(grantToDelete)"
          title="Delete grant"
          :description="
            grantToDelete
              ? `Permanently delete “${grantToDelete.title}” (${formatShares(grantToDelete.quantity)} shares)? The grant and all of its vesting releases will be removed. This cannot be undone.`
              : ''
          "
          confirm-label="Delete grant"
          :busy="entry.deletingId !== null"
          :error="entry.deleteError"
          @update:open="
            (open) => {
              if (!open && entry.deletingId === null) grantToDelete = null
            }
          "
          @cancel="grantToDelete = null"
          @confirm="deleteGrant"
        />
      </template>
    </div>
  </main>
</template>
