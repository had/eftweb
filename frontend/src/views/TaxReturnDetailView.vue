<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { Pencil, Settings, Trash2 } from 'lucide-vue-next'
import { useFamilyStore } from '@/stores/family'
import IncomeStatementFormModal from '@/components/IncomeStatementFormModal.vue'
import TaxReturnFormModal from '@/components/TaxReturnFormModal.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const route = useRoute()
const familyStore = useFamilyStore()
const taxReturn = ref(null)
const family = ref(null)
const incomeStatements = ref([])
const loading = ref(true)
const unavailable = ref(false)
const showSettings = ref(false)
const showIncomeStatementForm = ref(false)
const editingIncomeStatement = ref(null)

const loadTaxReturn = async () => {
  const taxReturnId = Number(route.params.taxReturnId)
  taxReturn.value = null
  family.value = null
  incomeStatements.value = []
  unavailable.value = false

  if (!familyStore.familyId || !Number.isInteger(taxReturnId)) {
    loading.value = false
    unavailable.value = true
    return
  }

  loading.value = true
  try {
    const response = await axios.get(`/api/families/${familyStore.familyId}/tax-returns`)
    taxReturn.value = response.data.find((item) => item.id === taxReturnId) || null
    unavailable.value = !taxReturn.value
    if (!taxReturn.value) return

    const [familyResponse, incomeStatementsResponse] = await Promise.all([
      axios.get(`/api/families/${familyStore.familyId}`),
      taxReturn.value.has_income_statements
        ? axios.get(`/api/tax-returns/${taxReturnId}/income-statements`)
        : Promise.resolve({ data: [] }),
    ])
    family.value = familyResponse.data
    incomeStatements.value = incomeStatementsResponse.data
  } catch {
    unavailable.value = true
  } finally {
    loading.value = false
  }
}

watch(
  [() => route.params.taxReturnId, () => familyStore.familyId, () => familyStore.taxReturnsVersion],
  loadTaxReturn,
  { immediate: true },
)

const settingsSaved = () => {
  familyStore.refreshTaxReturns()
  loadTaxReturn()
}

const otherStatementGroups = (returnValue) => [
  { enabled: returnValue.has_donation_statements, title: 'Donation statements' },
  { enabled: returnValue.has_investment_statements, title: 'Investment statements (GFI forests and life insurance)' },
].filter((group) => group.enabled)

const taxpayers = computed(() => [
  family.value?.taxpayer1 && {
    role: 'taxpayer1',
    label: `${family.value.taxpayer1.first_name} ${family.value.taxpayer1.last_name} (taxpayer 1)`,
  },
  family.value?.taxpayer2 && {
    role: 'taxpayer2',
    label: `${family.value.taxpayer2.first_name} ${family.value.taxpayer2.last_name} (taxpayer 2)`,
  },
].filter(Boolean))

const incomeRows = computed(() => {
  const taxpayer1 = incomeStatements.value.filter((statement) => statement.taxpayer_role === 'taxpayer1')
  const taxpayer2 = incomeStatements.value.filter((statement) => statement.taxpayer_role === 'taxpayer2')
  return Array.from({ length: Math.max(taxpayer1.length, taxpayer2.length) }, (_, index) => ({
    taxpayer1: taxpayer1[index],
    taxpayer2: taxpayer2[index],
  }))
})

const incomeStatementSaved = async () => {
  editingIncomeStatement.value = null
  await loadTaxReturn()
}

const openIncomeStatementForm = () => {
  editingIncomeStatement.value = null
  showIncomeStatementForm.value = true
}

const editIncomeStatement = (statement) => {
  editingIncomeStatement.value = statement
  showIncomeStatementForm.value = true
}

const deleteIncomeStatement = async (statement) => {
  await axios.delete(`/api/income-statements/${statement.id}`)
  await loadTaxReturn()
}
</script>

<template>
  <main class="p-8">
    <div v-if="loading" class="space-y-4">
      <div class="h-10 w-64 animate-pulse rounded bg-muted" />
      <div class="h-48 animate-pulse rounded-lg bg-muted" />
    </div>

    <div v-else-if="unavailable" class="max-w-xl space-y-2">
      <h1 class="text-3xl font-bold">Tax return unavailable</h1>
      <p class="text-muted-foreground">Select an active family tax return to view it.</p>
    </div>

    <template v-else>
      <div class="mb-8 flex items-center justify-between gap-4">
        <h1 class="text-3xl font-bold">Tax return {{ taxReturn.year }}</h1>
        <Button variant="outline" size="icon" aria-label="Edit tax return settings" @click="showSettings = true">
          <Settings class="h-4 w-4" />
        </Button>
      </div>

      <Card class="mb-6 w-full">
        <CardHeader><CardTitle>Tax summary</CardTitle></CardHeader>
        <CardContent class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div><p class="text-sm text-muted-foreground">Net income</p><p class="mt-1 text-lg font-medium">—</p></div>
          <div><p class="text-sm text-muted-foreground">Reference taxable revenue</p><p class="mt-1 text-lg font-medium">—</p></div>
          <div><p class="text-sm text-muted-foreground">Average tax rate</p><p class="mt-1 text-lg font-medium">—</p></div>
          <div><p class="text-sm text-muted-foreground">Marginal tax rate</p><p class="mt-1 text-lg font-medium">— % from next bucket</p></div>
        </CardContent>
      </Card>

      <section class="space-y-4">
        <Card v-if="taxReturn.has_income_statements" class="w-full">
          <CardHeader class="flex flex-row items-center justify-between gap-4">
            <CardTitle>Income statements</CardTitle>
            <Button @click="openIncomeStatementForm">Add income statement</Button>
          </CardHeader>
          <CardContent>
            <div v-if="incomeRows.length === 0" class="text-sm text-muted-foreground">No income statements added yet.</div>
            <div v-else class="overflow-x-auto">
              <table class="w-full border-collapse text-left text-sm">
                <thead><tr class="border-b"><th class="p-3 font-medium">{{ family.taxpayer1.first_name }} {{ family.taxpayer1.last_name }} <span class="text-xs font-normal text-muted-foreground">taxpayer 1</span></th><th v-if="family.taxpayer2" class="p-3 font-medium">{{ family.taxpayer2.first_name }} {{ family.taxpayer2.last_name }} <span class="text-xs font-normal text-muted-foreground">taxpayer 2</span></th></tr></thead>
                <tbody><tr v-for="(row, index) in incomeRows" :key="index" class="border-b last:border-0"><td class="p-3"><div v-if="row.taxpayer1" class="flex items-center justify-between gap-2"><span>{{ row.taxpayer1.employer_name }}</span><span class="flex shrink-0 gap-1"><Button variant="ghost" size="icon" aria-label="Edit income statement" @click="editIncomeStatement(row.taxpayer1)"><Pencil class="h-4 w-4" /></Button><Button variant="ghost" size="icon" class="text-destructive" aria-label="Delete income statement" @click="deleteIncomeStatement(row.taxpayer1)"><Trash2 class="h-4 w-4" /></Button></span></div></td><td v-if="family.taxpayer2" class="p-3"><div v-if="row.taxpayer2" class="flex items-center justify-between gap-2"><span>{{ row.taxpayer2.employer_name }}</span><span class="flex shrink-0 gap-1"><Button variant="ghost" size="icon" aria-label="Edit income statement" @click="editIncomeStatement(row.taxpayer2)"><Pencil class="h-4 w-4" /></Button><Button variant="ghost" size="icon" class="text-destructive" aria-label="Delete income statement" @click="deleteIncomeStatement(row.taxpayer2)"><Trash2 class="h-4 w-4" /></Button></span></div></td></tr></tbody>
              </table>
            </div>
          </CardContent>
        </Card>
        <Card v-for="group in otherStatementGroups(taxReturn)" :key="group.title" class="w-full">
          <CardHeader><CardTitle>{{ group.title }}</CardTitle></CardHeader>
        </Card>
      </section>

      <TaxReturnFormModal v-model:open="showSettings" :family-id="familyStore.familyId" :tax-return="taxReturn" @saved="settingsSaved" />
      <IncomeStatementFormModal v-model:open="showIncomeStatementForm" :tax-return-id="taxReturn.id" :income-statement="editingIncomeStatement" :taxpayers="taxpayers" @saved="incomeStatementSaved" />
    </template>
  </main>
</template>
