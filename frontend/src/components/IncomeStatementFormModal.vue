<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const props = defineProps({
  open: Boolean,
  taxReturnId: Number,
  taxpayers: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:open', 'saved'])

const taxpayerRole = ref('taxpayer1')
const employerName = ref('')
const amounts = ref({
  known_employment_income: '',
  income_tax_withheld: '',
  supplementary_pension_contributions: '',
})
const error = ref('')
const loading = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    taxpayerRole.value = props.taxpayers[0]?.role || 'taxpayer1'
    employerName.value = ''
    amounts.value = {
      known_employment_income: '',
      income_tax_withheld: '',
      supplementary_pension_contributions: '',
    }
    error.value = ''
  },
)

const close = () => {
  if (!loading.value) {
    emit('update:open', false)
    error.value = ''
  }
}

const payloadAmount = (amount) => (amount === '' ? null : Number(amount))

const submit = async () => {
  error.value = ''
  const payload = Object.fromEntries(
    Object.entries(amounts.value).map(([field, amount]) => [field, payloadAmount(amount)]),
  )
  const suppliedAmounts = Object.values(payload).filter((amount) => amount !== null)
  if (suppliedAmounts.length === 0) {
    error.value = 'Enter at least one monetary amount.'
    return
  }
  if (suppliedAmounts.some((amount) => !Number.isFinite(amount) || amount < 0)) {
    error.value = 'Amounts must be non-negative numbers.'
    return
  }
  if (!employerName.value.trim()) {
    error.value = 'Employer name is required.'
    return
  }

  loading.value = true
  try {
    await axios.post(`/api/tax-returns/${props.taxReturnId}/income-statements`, {
      taxpayer_role: taxpayerRole.value,
      employer_name: employerName.value.trim(),
      ...payload,
    })
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    error.value = requestError.response?.data?.error || 'Failed to add the income statement. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="sm:max-w-[500px]">
      <DialogHeader><DialogTitle>Add income statement</DialogTitle></DialogHeader>
      <form class="space-y-4 py-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="income-taxpayer">Taxpayer *</Label>
          <select id="income-taxpayer" v-model="taxpayerRole" class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm">
            <option v-for="taxpayer in taxpayers" :key="taxpayer.role" :value="taxpayer.role">{{ taxpayer.label }}</option>
          </select>
        </div>
        <div class="space-y-2">
          <Label for="income-employer">Company or employer *</Label>
          <Input id="income-employer" v-model="employerName" required />
        </div>
        <div class="grid gap-4 sm:grid-cols-3">
          <div class="space-y-2"><Label for="known-income">Known employment income</Label><Input id="known-income" v-model="amounts.known_employment_income" min="0" step="0.01" type="number" /></div>
          <div class="space-y-2"><Label for="withheld-tax">Income tax withheld</Label><Input id="withheld-tax" v-model="amounts.income_tax_withheld" min="0" step="0.01" type="number" /></div>
          <div class="space-y-2"><Label for="pension-contributions">Supplementary pension contributions</Label><Input id="pension-contributions" v-model="amounts.supplementary_pension_contributions" min="0" step="0.01" type="number" /></div>
        </div>
        <p class="text-sm text-muted-foreground">Enter at least one amount.</p>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
      </form>
      <DialogFooter>
        <Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button>
        <Button :disabled="loading" @click="submit">{{ loading ? 'Saving...' : 'Add income statement' }}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
