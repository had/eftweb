<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useFamilyStore } from '@/stores/family'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import EftLayout from '@/components/EftLayout.vue'

const familyStore = useFamilyStore()
const router = useRouter()
const taxReturns = ref([])
const showArchived = ref(false)

watch(
  [() => familyStore.familyId, () => familyStore.taxReturnsVersion],
  async ([familyId]) => {
    if (!familyId) { taxReturns.value = []; return }
    try {
      const response = await axios.get(`/api/families/${familyId}/tax-returns`, { params: { archived: showArchived.value } })
      taxReturns.value = response.data
    } catch (error) {
      console.error('Failed to load tax returns:', error)
      taxReturns.value = []
    }
  },
  { immediate: true },
)

const configurationLabels = (taxReturn) => [
  taxReturn.has_income_statements && 'Income',
  taxReturn.has_donation_statements && 'Donations',
  taxReturn.has_investment_statements && 'Investments',
].filter(Boolean)

const toggleArchived = () => {
  showArchived.value = !showArchived.value
  familyStore.refreshTaxReturns()
}

const selectTaxReturn = (taxReturn) => router.push(`/tax-returns/${taxReturn.id}`)
</script>

<template>
  <EftLayout :title="familyStore.familyName || 'Family'">
    <div class="flex items-center justify-between gap-4 mb-6">
      <h2 class="text-2xl font-semibold">{{ showArchived ? 'Archived Tax Returns' : 'Tax Returns' }}</h2>
      <Button variant="outline" @click="toggleArchived">{{ showArchived ? 'Show Active' : 'Show Archived' }}</Button>
    </div>
    <section class="grid gap-3 sm:grid-cols-2">
      <Card v-for="taxReturn in taxReturns" :key="taxReturn.id" :class="!showArchived && 'cursor-pointer transition-shadow hover:shadow-lg'" @click="!showArchived && selectTaxReturn(taxReturn)">
        <CardContent class="flex min-h-24 flex-col items-start justify-center gap-2 p-4">
          <span class="text-lg font-medium">{{ taxReturn.year }}</span>
          <div class="flex flex-wrap gap-1">
            <span v-for="label in configurationLabels(taxReturn)" :key="label" class="rounded bg-muted px-2 py-0.5 text-xs">{{ label }}</span>
            <span v-if="configurationLabels(taxReturn).length === 0" class="text-xs text-muted-foreground">No groups selected</span>
          </div>
        </CardContent>
      </Card>
      <p v-if="taxReturns.length === 0" class="text-muted-foreground">No {{ showArchived ? 'archived' : 'active' }} tax returns found.</p>
    </section>
  </EftLayout>
</template>
