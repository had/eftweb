<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { useFamilyStore } from '@/stores/family'
import EftLayout from '@/components/EftLayout.vue'
import TaxReturnFormModal from '@/components/TaxReturnFormModal.vue'
import DeleteConfirmModal from '@/components/DeleteConfirmModal.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const familyStore = useFamilyStore()
const taxReturns = ref([])
const loading = ref(true)
const error = ref('')
const showTaxReturnModal = ref(false)
const showArchived = ref(false)
const editingTaxReturn = ref(null)
const archivingTaxReturn = ref(null)
const showArchiveConfirm = ref(false)

const loadTaxReturns = async () => {
  if (!familyStore.familyId) { taxReturns.value = []; loading.value = false; return }
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get(`/api/families/${familyStore.familyId}/tax-returns`, { params: { archived: showArchived.value } })
    taxReturns.value = response.data
  } catch (requestError) {
    error.value = 'Failed to load tax returns. Please try again.'
  } finally {
    loading.value = false
  }
}

watch([() => familyStore.familyId, () => familyStore.taxReturnsVersion], loadTaxReturns, { immediate: true })
const taxReturnSaved = () => familyStore.refreshTaxReturns()
const openCreate = () => { editingTaxReturn.value = null; showTaxReturnModal.value = true }
const openEdit = (taxReturn) => { editingTaxReturn.value = taxReturn; showTaxReturnModal.value = true }
const openArchive = (taxReturn) => { archivingTaxReturn.value = taxReturn; showArchiveConfirm.value = true }
const archiveTaxReturn = async () => {
  if (!archivingTaxReturn.value) return
  await axios.delete(`/api/tax-returns/${archivingTaxReturn.value.id}`)
  showArchiveConfirm.value = false
  archivingTaxReturn.value = null
  familyStore.refreshTaxReturns()
}
const configurationLabels = (taxReturn) => [
  taxReturn.has_income_statements && 'Income',
  taxReturn.has_donation_statements && 'Donations',
  taxReturn.has_investment_statements && 'Investments',
].filter(Boolean)
</script>

<template>
  <EftLayout :title="familyStore.familyName || 'Family'">
    <Card class="max-w-2xl">
      <CardHeader class="flex flex-row items-center justify-between"><CardTitle>{{ showArchived ? 'Archived Tax Returns' : 'Tax Returns' }}</CardTitle><Button variant="outline" @click="showArchived = !showArchived; loadTaxReturns()">{{ showArchived ? 'Show Active' : 'Show Archived' }}</Button></CardHeader>
      <CardContent>
        <div v-if="loading" class="space-y-3"><div v-for="index in 2" :key="index" class="h-16 animate-pulse rounded-lg bg-muted" /></div>
        <div v-else-if="error" class="text-center py-4"><p class="text-destructive">{{ error }}</p><Button class="mt-4" variant="outline" @click="loadTaxReturns">Retry</Button></div>
        <div v-else class="grid gap-3 sm:grid-cols-2">
          <Card v-if="!showArchived" class="cursor-pointer border-2 border-dashed transition-shadow hover:shadow-lg" @click="openCreate"><CardContent class="flex min-h-24 flex-col items-center justify-center gap-2 p-4 text-center"><Plus class="h-6 w-6 text-muted-foreground" /><span class="font-medium">Add a New Tax Return</span></CardContent></Card>
          <Card v-for="taxReturn in taxReturns" :key="taxReturn.id" class="relative"><CardContent class="flex min-h-24 flex-col items-start justify-center gap-2 p-4"><div v-if="!showArchived" class="absolute right-2 top-2 flex gap-1"><Button variant="ghost" size="icon" @click="openEdit(taxReturn)"><Pencil class="h-4 w-4" /></Button><Button variant="ghost" size="icon" class="text-destructive" @click="openArchive(taxReturn)"><Trash2 class="h-4 w-4" /></Button></div><span class="text-lg font-medium">{{ taxReturn.year }}</span><div class="flex flex-wrap gap-1"><span v-for="label in configurationLabels(taxReturn)" :key="label" class="rounded bg-muted px-2 py-0.5 text-xs">{{ label }}</span><span v-if="configurationLabels(taxReturn).length === 0" class="text-xs text-muted-foreground">No groups selected</span></div></CardContent></Card>
          <p v-if="taxReturns.length === 0" class="text-sm text-muted-foreground sm:col-span-2">No {{ showArchived ? 'archived' : 'active' }} tax returns found.</p>
        </div>
      </CardContent>
    </Card>
    <TaxReturnFormModal v-model:open="showTaxReturnModal" :family-id="familyStore.familyId" :tax-return="editingTaxReturn" @saved="taxReturnSaved" />
    <DeleteConfirmModal v-model:open="showArchiveConfirm" title="Archive Tax Return" :description="archivingTaxReturn ? `Are you sure you want to archive the ${archivingTaxReturn.year} tax return? It will be hidden from the active list.` : ''" confirm-label="Archive" @confirm="archiveTaxReturn" @cancel="showArchiveConfirm = false" />
  </EftLayout>
</template>
