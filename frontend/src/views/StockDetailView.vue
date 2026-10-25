<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, Plus } from 'lucide-vue-next'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import VestingTimeline from '@/components/stock-detail/VestingTimeline.vue'
import HoldingsAndSales from '@/components/stock-detail/HoldingsAndSales.vue'
import GrantsOverview from '@/components/stock-detail/GrantsOverview.vue'
import AddGrantWizardModal from '@/components/stock-detail/AddGrantWizardModal.vue'
import DeleteConfirmModal from '@/components/DeleteConfirmModal.vue'
import { useStockGrantsStore } from '@/stores/stockGrants'
import {
  formatDate,
  formatShares,
  localDate,
  summarizeGrants,
} from '@/components/stock-detail/vesting.js'

const activeTab = ref('vesting')
const route = useRoute()
const grantsStore = useStockGrantsStore()
const stockId = computed(() => Number(route.params.stockId))
const entry = computed(() => grantsStore.forStock(stockId.value))
const grants = computed(() => entry.value.grants)
const stockName = computed(() => entry.value.stock?.name || 'Stock')
const stockSymbol = computed(() => entry.value.stock?.symbol || '')
const ready = computed(() => entry.value.loaded && !entry.value.loading && !entry.value.loadError)
const showAddGrant = ref(false)
const grantToDelete = ref(null)
let viewGeneration = 0
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
})
watch(
  () => route.params.stockId,
  () => {
    viewGeneration += 1
    showAddGrant.value = false
    grantToDelete.value = null
    activeTab.value = 'vesting'
    void grantsStore.load(stockId.value)
  },
  { flush: 'sync', immediate: true },
)
watch(showAddGrant, (open) => {
  if (open) entry.value.saveError = ''
})
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
  if (!ready.value || entry.value.saving || entry.value.deletingId !== null) return
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
  { value: 'vesting', label: 'Vesting timeline' },
  { value: 'holdings', label: 'Holdings & sales' },
  { value: 'grants', label: 'By grant' },
]
const portfolio = computed(() => summarizeGrants(grants.value, today.value))
const summaries = computed(() => [
  {
    label: 'Total awarded',
    value: portfolio.value.awarded,
    detail: `Across ${grants.value.length} ${grants.value.length === 1 ? 'grant' : 'grants'}`,
  },
  {
    label: 'Vested so far',
    value: portfolio.value.vested,
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
      <RouterLink
        to="/stocks"
        class="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft class="h-4 w-4" /> All stocks
      </RouterLink>

      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="mb-2 flex items-center gap-3">
            <h1 class="text-3xl font-bold tracking-tight">{{ stockName }}</h1>
            <span class="rounded-md border bg-card px-2 py-1 text-xs font-medium">{{
              stockSymbol
            }}</span>
          </div>
          <p class="text-sm text-muted-foreground">Employee equity · Grants, vesting and sales</p>
        </div>
        <div class="flex gap-2" aria-label="Portfolio actions">
          <Button disabled title="Recording sales is coming soon"
            ><ArrowUpRight class="h-4 w-4" /> Record sale</Button
          >
          <Button
            variant="outline"
            :disabled="!ready || entry.saving || entry.deletingId !== null"
            @click="showAddGrant = true"
            ><Plus class="h-4 w-4" /> Add grant</Button
          >
        </div>
      </header>

      <div
        v-if="entry.loading"
        role="status"
        aria-label="Loading stock and grants"
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
        <p class="text-xs text-muted-foreground">As of {{ formatDate(today) }}</p>

        <section aria-label="Portfolio summary" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Card
            v-for="summary in summaries"
            :key="summary.label"
            class="py-0"
            :class="summary.emphasized && 'border-primary/40 bg-primary/5'"
          >
            <CardContent class="p-5">
              <h2 class="text-sm text-muted-foreground">{{ summary.label }}</h2>
              <p
                class="my-2 text-3xl font-semibold tracking-tight tabular-nums"
                :class="summary.emphasized && 'text-primary'"
              >
                {{ formatShares(summary.value)
                }}<span class="ml-2 text-xs font-normal text-muted-foreground">shares</span>
              </p>
              <p class="text-xs text-muted-foreground">{{ summary.detail }}</p>
            </CardContent>
          </Card>
        </section>

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
            ><VestingTimeline :grants="grants" :today="today"
          /></TabsContent>
          <TabsContent
            value="holdings"
            class="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            ><p
              class="mb-4 rounded-lg border border-dashed bg-muted/40 px-4 py-3 text-sm text-muted-foreground"
            >
              Sample preview · This tab does not reflect the grants entered above.
            </p>
            <HoldingsAndSales
          /></TabsContent>
          <TabsContent
            value="grants"
            class="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <GrantsOverview :grants="grants" :today="today" @delete="requestDeleteGrant" />
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
