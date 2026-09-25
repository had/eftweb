<script setup>
import { computed, ref, watch } from 'vue'
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
  donationStatement: Object,
  donationTypes: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:open', 'saved'])

const name = ref('')
const amount = ref('')
const donationType = ref('')
const error = ref('')
const loading = ref(false)

const selectedType = computed(() => props.donationTypes.find((type) => type.code === donationType.value))

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    name.value = props.donationStatement?.name || ''
    amount.value = props.donationStatement?.amount ?? ''
    donationType.value = props.donationStatement?.donation_type || props.donationTypes[0]?.code || ''
    error.value = ''
  },
)

const close = () => {
  if (!loading.value) {
    emit('update:open', false)
    error.value = ''
  }
}

const submit = async () => {
  error.value = ''
  const parsedAmount = Number(amount.value)
  if (!name.value.trim()) {
    error.value = 'Donation name is required.'
    return
  }
  if (!donationType.value) {
    error.value = 'Select a donation type.'
    return
  }
  if (amount.value === '' || !Number.isFinite(parsedAmount) || parsedAmount < 0) {
    error.value = 'Enter a non-negative donation amount.'
    return
  }

  loading.value = true
  try {
    const statementData = {
      name: name.value.trim(),
      amount: parsedAmount,
      donation_type: donationType.value,
    }
    if (props.donationStatement) {
      await axios.put(`/api/donation-statements/${props.donationStatement.id}`, statementData)
    } else {
      await axios.post(`/api/tax-returns/${props.taxReturnId}/donation-statements`, statementData)
    }
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    error.value = requestError.response?.data?.error || 'Failed to save the donation statement. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="sm:max-w-[560px]">
      <DialogHeader><DialogTitle>{{ donationStatement ? 'Edit donation statement' : 'Add donation statement' }}</DialogTitle></DialogHeader>
      <form class="space-y-4 py-4" @submit.prevent="submit">
        <div class="space-y-2"><Label for="donation-name">Organization or donation name *</Label><Input id="donation-name" v-model="name" required /></div>
        <div class="space-y-2"><Label for="donation-amount">Amount *</Label><Input id="donation-amount" v-model="amount" min="0" step="0.01" type="number" required /></div>
        <div class="space-y-2">
          <Label for="donation-type">Donation type *</Label>
          <select id="donation-type" v-model="donationType" class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm">
            <option v-for="type in donationTypes" :key="type.code" :value="type.code">{{ type.label }}</option>
          </select>
        </div>
        <div v-if="selectedType" class="rounded-md bg-muted p-3 text-sm"><p><span class="font-medium">Tax reduction:</span> {{ selectedType.tax_reduction }}</p><p class="mt-1"><span class="font-medium">Tax return box:</span> {{ selectedType.tax_return_box }}</p><p class="mt-1"><span class="font-medium">Ceiling:</span> {{ selectedType.ceiling ? `€${selectedType.ceiling.toLocaleString('en-GB')}` : 'No ceiling' }}</p></div>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
      </form>
      <DialogFooter><Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button><Button :disabled="loading" @click="submit">{{ loading ? 'Saving...' : donationStatement ? 'Save changes' : 'Add donation statement' }}</Button></DialogFooter>
    </DialogContent>
  </Dialog>
</template>
