<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { Plus } from 'lucide-vue-next'
import { useFamilyStore } from '@/stores/family'
import EftLayout from '@/components/EftLayout.vue'
import TaxReturnFormModal from '@/components/TaxReturnFormModal.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const familyStore = useFamilyStore()
const taxReturns = ref([])
const loading = ref(true)
const error = ref('')
const showTaxReturnModal = ref(false)

const loadTaxReturns = async () => {
  if (!familyStore.familyId) { taxReturns.value = []; loading.value = false; return }
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get(`/api/families/${familyStore.familyId}/tax-returns`)
    taxReturns.value = response.data
  } catch (requestError) {
    error.value = 'Failed to load tax returns. Please try again.'
  } finally {
    loading.value = false
  }
}

watch([() => familyStore.familyId, () => familyStore.taxReturnsVersion], loadTaxReturns, { immediate: true })
const taxReturnSaved = () => familyStore.refreshTaxReturns()
</script>

<template>
  <EftLayout :title="familyStore.familyName || 'Family'">
    <Card class="max-w-2xl">
      <CardHeader><CardTitle>Tax Returns</CardTitle></CardHeader>
      <CardContent>
        <div v-if="loading" class="space-y-3"><div v-for="index in 2" :key="index" class="h-16 animate-pulse rounded-lg bg-muted" /></div>
        <div v-else-if="error" class="text-center py-4"><p class="text-destructive">{{ error }}</p><Button class="mt-4" variant="outline" @click="loadTaxReturns">Retry</Button></div>
        <div v-else class="grid gap-3 sm:grid-cols-2">
          <Card class="cursor-pointer border-2 border-dashed transition-shadow hover:shadow-lg" @click="showTaxReturnModal = true"><CardContent class="flex min-h-24 flex-col items-center justify-center gap-2 p-4 text-center"><Plus class="h-6 w-6 text-muted-foreground" /><span class="font-medium">Add a New Tax Return</span></CardContent></Card>
          <Card v-for="taxReturn in taxReturns" :key="taxReturn.id"><CardContent class="flex min-h-24 items-center p-4"><span class="text-lg font-medium">{{ taxReturn.year }}</span></CardContent></Card>
          <p v-if="taxReturns.length === 0" class="text-sm text-muted-foreground sm:col-span-2">No tax returns found.</p>
        </div>
      </CardContent>
    </Card>
    <TaxReturnFormModal v-model:open="showTaxReturnModal" :family-id="familyStore.familyId" @saved="taxReturnSaved" />
  </EftLayout>
</template>
