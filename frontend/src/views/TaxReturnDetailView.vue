<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { useFamilyStore } from '@/stores/family'
import DonationStatementFormModal from '@/components/DonationStatementFormModal.vue'
import IfuStatementFormModal from '@/components/IfuStatementFormModal.vue'
import IncomeStatementFormModal from '@/components/IncomeStatementFormModal.vue'
import TaxReturnFormModal from '@/components/TaxReturnFormModal.vue'
import DonationStatementsSection from '@/components/tax-return-detail/DonationStatementsSection.vue'
import IncomeStatementsSection from '@/components/tax-return-detail/IncomeStatementsSection.vue'
import InvestmentStatementsSection from '@/components/tax-return-detail/InvestmentStatementsSection.vue'
import StockTaxSection from '@/components/tax-return-detail/StockTaxSection.vue'
import TaxReturnHeader from '@/components/tax-return-detail/TaxReturnHeader.vue'
import TaxReturnSummary from '@/components/tax-return-detail/TaxReturnSummary.vue'

const route = useRoute()
const familyStore = useFamilyStore()
const taxReturn = ref(null)
const family = ref(null)
const incomeStatements = ref([])
const donationStatements = ref([])
const donationTypes = ref([])
const ifuStatements = ref([])
const ifuFieldGroups = ref([])
const loading = ref(true)
const unavailable = ref(false)
const showSettings = ref(false)
const showIncomeStatementForm = ref(false)
const editingIncomeStatement = ref(null)
const showDonationStatementForm = ref(false)
const editingDonationStatement = ref(null)
const showIfuStatementForm = ref(false)
const editingIfuStatement = ref(null)
const stockStatementCount = ref(0)
const activeStatementTab = ref(null)
const estimate = ref(null)
const estimationLoading = ref(false)
const estimationError = ref('')
let loadGeneration = 0
let estimationGeneration = 0

onBeforeUnmount(() => {
  loadGeneration += 1
})

const loadTaxEstimation = async (taxReturnId, generation) => {
  const requestGeneration = ++estimationGeneration
  const isCurrent = () => generation === loadGeneration && requestGeneration === estimationGeneration
  estimationLoading.value = true
  estimationError.value = ''
  try {
    const response = await axios.get(`/api/tax-returns/${taxReturnId}/estimation`)
    console.log('Raw tax result:', response.data.tax_result)
    console.log('Tax flags:', response.data.flags)
    if (isCurrent()) estimate.value = response.data
  } catch (error) {
    if (isCurrent()) {
      estimationError.value =
        error.response?.data?.error || 'Tax estimation is unavailable. Please try again.'
    }
  } finally {
    if (isCurrent()) estimationLoading.value = false
  }
}

const stockStatementsSaved = () => {
  if (!taxReturn.value) return
  estimate.value = null
  void loadTaxEstimation(taxReturn.value.id, loadGeneration)
}

const loadTaxReturn = async () => {
  const generation = ++loadGeneration
  const familyId = familyStore.familyId
  const taxReturnId = Number(route.params.taxReturnId)
  taxReturn.value = null
  family.value = null
  incomeStatements.value = []
  donationStatements.value = []
  donationTypes.value = []
  ifuStatements.value = []
  ifuFieldGroups.value = []
  stockStatementCount.value = 0
  unavailable.value = false
  estimate.value = null
  estimationLoading.value = false
  estimationError.value = ''

  if (!familyId || !Number.isInteger(taxReturnId)) {
    loading.value = false
    unavailable.value = true
    return
  }

  loading.value = true
  try {
    const response = await axios.get(`/api/families/${familyId}/tax-returns`)
    if (generation !== loadGeneration) return
    taxReturn.value = response.data.find((item) => item.id === taxReturnId) || null
    unavailable.value = !taxReturn.value
    if (!taxReturn.value) return
    void loadTaxEstimation(taxReturnId, generation)

    const [
      familyResponse,
      incomeStatementsResponse,
      donationStatementsResponse,
      donationTypesResponse,
      ifuStatementsResponse,
      ifuFieldsResponse,
      stockStatementsResponse,
    ] = await Promise.all([
      axios.get(`/api/families/${familyId}`),
      taxReturn.value.has_income_statements
        ? axios.get(`/api/tax-returns/${taxReturnId}/income-statements`)
        : Promise.resolve({ data: [] }),
      taxReturn.value.has_donation_statements
        ? axios.get(`/api/tax-returns/${taxReturnId}/donation-statements`)
        : Promise.resolve({ data: [] }),
      taxReturn.value.has_donation_statements
        ? axios.get('/api/donation-types')
        : Promise.resolve({ data: [] }),
      taxReturn.value.has_investment_statements
        ? axios.get(`/api/tax-returns/${taxReturnId}/ifu-statements`)
        : Promise.resolve({ data: [] }),
      taxReturn.value.has_investment_statements
        ? axios.get('/api/ifu-fields')
        : Promise.resolve({ data: [] }),
      taxReturn.value.has_stock_statements
        ? axios.get(`/api/tax-returns/${taxReturnId}/capital-gain-statements`)
        : Promise.resolve({ data: { statements: [] } }),
    ])
    if (generation !== loadGeneration) return
    family.value = familyResponse.data
    incomeStatements.value = incomeStatementsResponse.data
    donationStatements.value = donationStatementsResponse.data
    donationTypes.value = donationTypesResponse.data
    ifuStatements.value = ifuStatementsResponse.data
    ifuFieldGroups.value = ifuFieldsResponse.data
    stockStatementCount.value = stockStatementsResponse.data.statements.length
  } catch {
    if (generation === loadGeneration) unavailable.value = true
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

watch(
  [() => route.params.taxReturnId, () => familyStore.familyId, () => familyStore.taxReturnsVersion],
  loadTaxReturn,
  { immediate: true },
)

const settingsSaved = () => {
  familyStore.refreshTaxReturns()
}

const taxpayers = computed(() =>
  [
    family.value?.taxpayer1 && {
      role: 'taxpayer1',
      label: `${family.value.taxpayer1.first_name} ${family.value.taxpayer1.last_name} (taxpayer 1)`,
    },
    family.value?.taxpayer2 && {
      role: 'taxpayer2',
      label: `${family.value.taxpayer2.first_name} ${family.value.taxpayer2.last_name} (taxpayer 2)`,
    },
  ].filter(Boolean),
)

const statementTabs = computed(() =>
  [
    taxReturn.value?.has_stock_statements && {
      value: 'stocks',
      label: 'Stock gains/losses',
      count: stockStatementCount.value,
    },
    taxReturn.value?.has_income_statements && {
      value: 'income',
      label: 'Income statements',
      count: incomeStatements.value.length,
    },
    taxReturn.value?.has_donation_statements && {
      value: 'donations',
      label: 'Donation statements',
      count: donationStatements.value.length,
    },
    taxReturn.value?.has_investment_statements && {
      value: 'investments',
      label: 'Investment statements',
      count: ifuStatements.value.length,
    },
  ].filter(Boolean),
)

watch(
  statementTabs,
  (tabs) => {
    if (tabs.length && !tabs.some((tab) => tab.value === activeStatementTab.value)) {
      activeStatementTab.value = tabs[0].value
    }
  },
  { immediate: true },
)

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

const donationStatementSaved = async () => {
  editingDonationStatement.value = null
  await loadTaxReturn()
}

const openDonationStatementForm = () => {
  editingDonationStatement.value = null
  showDonationStatementForm.value = true
}

const editDonationStatement = (statement) => {
  editingDonationStatement.value = statement
  showDonationStatementForm.value = true
}

const deleteDonationStatement = async (statement) => {
  await axios.delete(`/api/donation-statements/${statement.id}`)
  await loadTaxReturn()
}

const ifuStatementSaved = async () => {
  editingIfuStatement.value = null
  await loadTaxReturn()
}

const openIfuStatementForm = () => {
  editingIfuStatement.value = null
  showIfuStatementForm.value = true
}

const editIfuStatement = (statement) => {
  editingIfuStatement.value = statement
  showIfuStatementForm.value = true
}

const deleteIfuStatement = async (statement) => {
  await axios.delete(`/api/ifu-statements/${statement.id}`)
  await loadTaxReturn()
}
</script>

<template>
  <main class="min-w-0 flex-1 p-4 sm:p-8">
    <div v-if="loading" class="space-y-4">
      <div class="h-10 w-64 animate-pulse rounded bg-muted" />
      <div class="h-48 animate-pulse rounded-lg bg-muted" />
    </div>

    <div v-else-if="unavailable" class="max-w-xl space-y-2">
      <h1 class="text-3xl font-bold">Tax return unavailable</h1>
      <p class="text-muted-foreground">Select an active family tax return to view it.</p>
    </div>

    <template v-else>
      <TaxReturnHeader :year="taxReturn.year" @edit-settings="showSettings = true" />
      <TaxReturnSummary
        :estimate="estimate"
        :estimation-loading="estimationLoading"
        :estimation-error="estimationError"
      />

      <TabsRoot v-if="statementTabs.length" v-model="activeStatementTab" class="w-full">
        <TabsList
          class="mb-4 flex h-auto max-w-full items-center justify-start gap-1 overflow-x-auto rounded-lg bg-muted p-1"
        >
          <TabsTrigger
            v-for="tab in statementTabs"
            :key="tab.value"
            :value="tab.value"
            class="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
          >
            {{ tab.label }} ({{ tab.count }})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stocks" class="mt-0 focus-visible:outline-none">
          <StockTaxSection
            v-if="taxReturn.has_stock_statements"
            :key="taxReturn.id"
            :tax-return-id="taxReturn.id"
            :filing-year="taxReturn.year"
            @count="stockStatementCount = $event"
            @changed="stockStatementsSaved"
          />
        </TabsContent>
        <TabsContent value="income" class="mt-0 focus-visible:outline-none">
          <IncomeStatementsSection
            :family="family"
            :statements="incomeStatements"
            @add="openIncomeStatementForm"
            @edit="editIncomeStatement"
            @delete="deleteIncomeStatement"
          />
        </TabsContent>
        <TabsContent value="donations" class="mt-0 focus-visible:outline-none">
          <DonationStatementsSection
            :statements="donationStatements"
            :donation-types="donationTypes"
            @add="openDonationStatementForm"
            @edit="editDonationStatement"
            @delete="deleteDonationStatement"
          />
        </TabsContent>
        <TabsContent value="investments" class="mt-0 focus-visible:outline-none">
          <InvestmentStatementsSection
            :statements="ifuStatements"
            @add="openIfuStatementForm"
            @edit="editIfuStatement"
            @delete="deleteIfuStatement"
          />
        </TabsContent>
      </TabsRoot>

      <TaxReturnFormModal
        v-model:open="showSettings"
        :family-id="familyStore.familyId"
        :tax-return="taxReturn"
        @saved="settingsSaved"
      />
      <IncomeStatementFormModal
        v-model:open="showIncomeStatementForm"
        :tax-return-id="taxReturn.id"
        :income-statement="editingIncomeStatement"
        :taxpayers="taxpayers"
        @saved="incomeStatementSaved"
      />
      <DonationStatementFormModal
        v-model:open="showDonationStatementForm"
        :tax-return-id="taxReturn.id"
        :donation-statement="editingDonationStatement"
        :donation-types="donationTypes"
        @saved="donationStatementSaved"
      />
      <IfuStatementFormModal
        v-model:open="showIfuStatementForm"
        :tax-return-id="taxReturn.id"
        :ifu-statement="editingIfuStatement"
        :field-groups="ifuFieldGroups"
        @saved="ifuStatementSaved"
      />
    </template>
  </main>
</template>
