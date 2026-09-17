<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { Plus } from 'lucide-vue-next'
import { useProjectStore } from '@/stores/project'
import EftLayout from '@/components/EftLayout.vue'
import TaxReturnFormModal from '@/components/TaxReturnFormModal.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const projectStore = useProjectStore()

const taxReturns = ref([])
const loadingTaxReturns = ref(true)
const taxReturnsError = ref('')
const showTaxReturnModal = ref(false)

const loadTaxReturns = async () => {
  if (!projectStore.projectId) {
    taxReturns.value = []
    loadingTaxReturns.value = false
    return
  }

  loadingTaxReturns.value = true
  taxReturnsError.value = ''
  try {
    const response = await axios.get(`/api/projects/${projectStore.projectId}/tax-statements`)
    taxReturns.value = response.data
  } catch (error) {
    console.error('Failed to fetch tax returns:', error)
    taxReturnsError.value = 'Failed to load tax returns. Please try again.'
  } finally {
    loadingTaxReturns.value = false
  }
}

watch(
  [() => projectStore.projectId, () => projectStore.taxStatementsVersion],
  loadTaxReturns,
  { immediate: true },
)

const taxReturnSaved = () => {
  projectStore.refreshTaxStatements()
}

// Mock data for stock events
const stockEvents = ref([
  { id: 1, date: '2024-03-15', type: 'Sale', ticker: 'AAPL', shares: 50, amount: '€8,450' },
  { id: 2, date: '2024-02-28', type: 'Purchase', ticker: 'GOOGL', shares: 20, amount: '€2,840' },
  { id: 3, date: '2024-01-12', type: 'Dividend', ticker: 'MSFT', shares: 100, amount: '€320' },
  { id: 4, date: '2023-12-05', type: 'Sale', ticker: 'TSLA', shares: 15, amount: '€3,210' },
  { id: 5, date: '2023-11-20', type: 'Purchase', ticker: 'NVDA', shares: 30, amount: '€9,150' },
])
</script>

<template>
  <EftLayout :title="projectStore.projectName || 'Family'">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Tax Returns</CardTitle>
        </CardHeader>
        <CardContent>
          <div v-if="loadingTaxReturns" class="space-y-3">
            <div v-for="index in 2" :key="index" class="h-16 animate-pulse rounded-lg bg-muted" />
          </div>
          <div v-else-if="taxReturnsError" class="text-center py-4">
            <p class="text-destructive">{{ taxReturnsError }}</p>
            <Button class="mt-4" variant="outline" @click="loadTaxReturns">Retry</Button>
          </div>
          <div v-else class="grid gap-3 sm:grid-cols-2">
            <Card
              class="cursor-pointer border-2 border-dashed transition-shadow hover:shadow-lg"
              @click="showTaxReturnModal = true"
            >
              <CardContent class="flex min-h-24 flex-col items-center justify-center gap-2 p-4 text-center">
                <Plus class="h-6 w-6 text-muted-foreground" />
                <span class="font-medium">Add a New Tax Return</span>
              </CardContent>
            </Card>
            <Card v-for="taxReturn in taxReturns" :key="taxReturn.id">
              <CardContent class="flex min-h-24 items-center p-4">
                <span class="text-lg font-medium">{{ taxReturn.year }}</span>
              </CardContent>
            </Card>
            <p v-if="taxReturns.length === 0" class="text-sm text-muted-foreground sm:col-span-2">
              No tax returns found.
            </p>
          </div>
        </CardContent>
      </Card>

      <!-- Stock Events List -->
      <Card>
        <CardHeader>
          <CardTitle>Stock Events</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-3">
            <div
              v-for="event in stockEvents"
              :key="event.id"
              class="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors cursor-pointer"
            >
              <div class="flex flex-col">
                <div class="flex items-center gap-2">
                  <span class="font-medium">{{ event.ticker }}</span>
                  <span
                    :class="[
                      'text-xs px-2 py-0.5 rounded',
                      event.type === 'Sale'
                        ? 'bg-red-100 text-red-800'
                        : event.type === 'Purchase'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-blue-100 text-blue-800',
                    ]"
                  >
                    {{ event.type }}
                  </span>
                </div>
                <span class="text-sm text-muted-foreground">
                  {{ event.date }} • {{ event.shares }} shares
                </span>
              </div>
              <div class="text-right">
                <span class="font-semibold">{{ event.amount }}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <TaxReturnFormModal
      v-model:open="showTaxReturnModal"
      :project-id="projectStore.projectId"
      @saved="taxReturnSaved"
    />
  </EftLayout>
</template>
