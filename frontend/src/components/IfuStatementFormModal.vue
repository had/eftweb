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
  ifuStatement: Object,
  fieldGroups: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:open', 'saved'])

const title = ref('')
const amounts = ref({})
const activeTab = ref('')
const error = ref('')
const loading = ref(false)

const fieldKeys = () => props.fieldGroups.flatMap((group) => group.fields.map((field) => field.key))

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    title.value = props.ifuStatement?.title || ''
    amounts.value = Object.fromEntries(
      fieldKeys().map((key) => [key, props.ifuStatement?.[key] ?? '']),
    )
    activeTab.value = props.fieldGroups[0]?.title || ''
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
  if (!title.value.trim()) {
    error.value = 'IFU title is required.'
    return
  }

  const statementAmounts = Object.fromEntries(
    Object.entries(amounts.value).map(([key, value]) => [key, value === '' ? null : Number(value)]),
  )
  const suppliedAmounts = Object.values(statementAmounts).filter((amount) => amount !== null)
  if (suppliedAmounts.length === 0) {
    error.value = 'Enter at least one IFU amount.'
    return
  }
  if (suppliedAmounts.some((amount) => !Number.isFinite(amount) || amount < 0)) {
    error.value = 'Amounts must be non-negative numbers.'
    return
  }

  loading.value = true
  try {
    const statementData = { title: title.value.trim(), ...statementAmounts }
    if (props.ifuStatement) {
      await axios.put(`/api/ifu-statements/${props.ifuStatement.id}`, statementData)
    } else {
      await axios.post(`/api/tax-returns/${props.taxReturnId}/ifu-statements`, statementData)
    }
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    error.value = requestError.response?.data?.error || 'Failed to save the IFU statement. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="sm:max-w-[680px]">
      <DialogHeader><DialogTitle>{{ ifuStatement ? 'Edit investment tax statement (IFU)' : 'Add an investment tax statement (IFU)' }}</DialogTitle></DialogHeader>
      <form class="space-y-4 py-4" @submit.prevent="submit">
        <div class="space-y-2"><Label for="ifu-title">Title *</Label><Input id="ifu-title" v-model="title" placeholder="Acme Inc." required /></div>
        <div class="flex gap-1 border-b" role="tablist" aria-label="IFU fields">
          <button v-for="group in fieldGroups" :key="group.title" type="button" role="tab" :aria-selected="activeTab === group.title" :class="['px-3 py-2 text-sm font-medium', activeTab === group.title ? 'border-b-2 border-primary text-foreground' : 'text-muted-foreground hover:text-foreground']" @click="activeTab = group.title">{{ group.title }}</button>
        </div>
        <div class="grid">
          <section v-for="group in fieldGroups" :key="group.title" :class="['col-start-1 row-start-1 space-y-3', activeTab === group.title ? '' : 'invisible pointer-events-none']"><div v-for="field in group.fields" :key="field.key" class="grid gap-2 sm:grid-cols-[1fr_10rem] sm:items-center"><Label :for="field.key"><span class="font-medium">{{ field.code }}</span> — {{ field.label }}</Label><Input :id="field.key" v-model="amounts[field.key]" min="0" step="0.01" type="number" /></div></section>
        </div>
        <p class="text-sm text-muted-foreground">Enter at least one amount.</p>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
      </form>
      <DialogFooter><Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button><Button :disabled="loading" @click="submit">{{ loading ? 'Saving...' : ifuStatement ? 'Save changes' : 'Add IFU statement' }}</Button></DialogFooter>
    </DialogContent>
  </Dialog>
</template>
