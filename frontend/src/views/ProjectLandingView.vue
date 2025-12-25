<script setup>
import { ref } from 'vue'
import { useProjectStore } from '@/stores/project'
import EftLayout from '@/components/EftLayout.vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const projectStore = useProjectStore()

// Mock data for tax returns
const taxReturns = ref([
  { id: 1, year: 2024, status: 'In Progress', amount: '€45,230' },
  { id: 2, year: 2023, status: 'Completed', amount: '€42,150' },
  { id: 3, year: 2022, status: 'Completed', amount: '€38,900' },
  { id: 4, year: 2021, status: 'Completed', amount: '€35,420' },
])

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
  <EftLayout :title="projectStore.projectName || 'Project'">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Tax Returns List -->
      <Card>
        <CardHeader>
          <CardTitle>Tax Returns</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-3">
            <div
              v-for="taxReturn in taxReturns"
              :key="taxReturn.id"
              class="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors cursor-pointer"
            >
              <div class="flex flex-col">
                <span class="font-medium">{{ taxReturn.year }}</span>
                <span class="text-sm text-muted-foreground">{{ taxReturn.status }}</span>
              </div>
              <div class="text-right">
                <span class="font-semibold">{{ taxReturn.amount }}</span>
              </div>
            </div>
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
  </EftLayout>
</template>
