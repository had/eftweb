<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { useFamilyStore } from '@/stores/family'
import { Button } from '@/components/ui/button'

const familyStore = useFamilyStore()
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
</script>

<template>
  <div class="ml-8 flex-col"><div class="flex items-center gap-4"><h1 class="logo px-3 py-5 mx-auto my-3">{{ showArchived ? 'Archived Tax Returns' : 'Tax Returns' }}</h1><Button variant="outline" @click="toggleArchived">{{ showArchived ? 'Show Active' : 'Show Archived' }}</Button></div><section><ul class="flex flex-col"><li v-for="taxReturn in taxReturns" :key="taxReturn.id" class="flex gap-2 p-2"><span>{{ taxReturn.year }}</span><span v-for="label in configurationLabels(taxReturn)" :key="label" class="rounded bg-muted px-2 py-0.5 text-xs">{{ label }}</span></li><li v-if="taxReturns.length === 0" class="p-2 text-muted-foreground">No {{ showArchived ? 'archived' : 'active' }} tax returns found.</li></ul></section></div>
</template>
