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
import {
  createId,
  formatDate,
  formatShares,
  grantColor,
  localDate,
  summarizeGrants,
} from '@/components/stock-detail/vesting.js'

defineProps({
  stockName: { type: String, default: 'Employee equity' },
  stockSymbol: { type: String, default: 'STOCK' },
})

const activeTab = ref('vesting')
const route = useRoute()
const grants = ref([])
const showAddGrant = ref(false)
const grantToDelete = ref(null)
let nextGrantColor = 0
const today = ref(localDate())
let dateTimer
onMounted(() => {
  dateTimer = setInterval(() => {
    today.value = localDate()
  }, 60000)
})
onBeforeUnmount(() => clearInterval(dateTimer))
watch(
  () => route.params.stockId,
  () => {
    grants.value = []
    showAddGrant.value = false
    grantToDelete.value = null
    nextGrantColor = 0
    activeTab.value = 'vesting'
  },
  { flush: 'sync' },
)
const addGrant = (grant) => {
  grants.value.push({ ...grant, id: createId(), color: grantColor(nextGrantColor++) })
  showAddGrant.value = false
  activeTab.value = 'vesting'
}
const deleteGrant = () => {
  if (!grantToDelete.value) return
  grants.value = grants.value.filter((grant) => grant.id !== grantToDelete.value.id)
  grantToDelete.value = null
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
          <Button variant="outline" @click="showAddGrant = true"
            ><Plus class="h-4 w-4" /> Add grant</Button
          >
        </div>
      </header>

      <div
        class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed bg-muted/50 px-4 py-3 text-sm"
      >
        <p>
          <span class="font-medium">Temporary grants</span
          ><span class="text-muted-foreground">
            · Grants are kept only while this stock view is open. Navigating away or reloading
            discards them.</span
          >
        </p>
        <span class="text-xs text-muted-foreground">As of {{ formatDate(today) }}</span>
      </div>

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
          <GrantsOverview :grants="grants" :today="today" @delete="grantToDelete = $event" />
        </TabsContent>
      </TabsRoot>
      <AddGrantWizardModal
        :key="route.params.stockId"
        v-model:open="showAddGrant"
        :ticker="stockSymbol"
        @confirmed="addGrant"
      />
      <DeleteConfirmModal
        :open="Boolean(grantToDelete)"
        title="Delete grant"
        :description="
          grantToDelete
            ? `Delete “${grantToDelete.title}” (${formatShares(grantToDelete.quantity)} shares)? The grant and all of its vesting releases will be removed from this view.`
            : ''
        "
        confirm-label="Delete grant"
        @update:open="
          (open) => {
            if (!open) grantToDelete = null
          }
        "
        @cancel="grantToDelete = null"
        @confirm="deleteGrant"
      />
    </div>
  </main>
</template>
