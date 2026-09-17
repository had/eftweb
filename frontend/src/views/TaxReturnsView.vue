<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { useFamilyStore } from '@/stores/family'

const familyStore = useFamilyStore()
const taxReturns = ref([])

watch(
  [() => familyStore.familyId, () => familyStore.taxReturnsVersion],
  async ([familyId]) => {
    if (!familyId) { taxReturns.value = []; return }
    try {
      const response = await axios.get(`/api/families/${familyId}/tax-returns`)
      taxReturns.value = response.data
    } catch (error) {
      console.error('Failed to load tax returns:', error)
      taxReturns.value = []
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="ml-8 flex-col"><h1 class="logo px-3 py-5 mx-auto my-3">Tax Returns</h1><section><ul class="flex flex-col"><li v-for="taxReturn in taxReturns" :key="taxReturn.id" class="p-2">{{ taxReturn.year }}</li><li v-if="taxReturns.length === 0" class="p-2 text-muted-foreground">No tax returns found.</li></ul></section></div>
</template>
