<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const props = defineProps({
  open: Boolean,
  familyId: Number,
  stock: Object,
})
const emit = defineEmits(['update:open', 'saved'])
const name = ref('')
const symbol = ref('')
const error = ref('')
const loading = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      name.value = props.stock?.name ?? ''
      symbol.value = props.stock?.symbol ?? ''
      error.value = ''
    }
  },
)

const close = () => {
  if (!loading.value) emit('update:open', false)
}

const submit = async () => {
  if (loading.value) return
  error.value = ''
  const payload = { name: name.value.trim(), symbol: symbol.value.trim().toUpperCase() }
  if (!payload.name || payload.name.length > 256) {
    error.value = 'Enter a stock name of at most 256 characters.'
    return
  }
  if (!payload.symbol || payload.symbol.length > 16 || /\s/.test(payload.symbol)) {
    error.value = 'Enter a ticker symbol of at most 16 characters without spaces.'
    return
  }

  loading.value = true
  try {
    if (props.stock) {
      await axios.put(`/api/stocks/${props.stock.id}`, payload)
    } else {
      await axios.post(`/api/families/${props.familyId}/stocks`, payload)
    }
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    error.value =
      requestError.response?.data?.error || 'Failed to save the stock. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>{{ stock ? 'Edit Stock' : 'Add a New Stock' }}</DialogTitle>
        <DialogDescription>
          Enter a name and ticker symbol. Use the name to distinguish brokers or owners; multiple
          stocks can share the same ticker.
        </DialogDescription>
      </DialogHeader>
      <form id="stock-form" class="space-y-4 py-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="stock-name">Stock name *</Label>
          <Input
            id="stock-name"
            v-model="name"
            :maxlength="256"
            :disabled="loading"
            placeholder="e.g. Apple — Ada’s brokerage"
            required
          />
        </div>
        <div class="space-y-2">
          <Label for="stock-symbol">Ticker symbol *</Label>
          <Input
            id="stock-symbol"
            v-model="symbol"
            :maxlength="16"
            :disabled="loading"
            class="uppercase"
            placeholder="e.g. AAPL"
            required
          />
        </div>
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
      </form>
      <DialogFooter>
        <Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button>
        <Button type="submit" form="stock-form" :disabled="loading">
          {{ loading ? 'Saving...' : stock ? 'Save Changes' : 'Add Stock' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
