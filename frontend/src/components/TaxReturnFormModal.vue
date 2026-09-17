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
  familyId: Number,
})

const emit = defineEmits(['update:open', 'saved'])

const year = ref(new Date().getFullYear())
const error = ref('')
const loading = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      year.value = new Date().getFullYear()
      error.value = ''
    }
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
  if (!Number.isInteger(year.value)) {
    error.value = 'Enter a valid tax-return year.'
    return
  }

  loading.value = true
  try {
    await axios.post(`/api/families/${props.familyId}/tax-returns`, { year: year.value })
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    error.value = requestError.response?.data?.error || 'Failed to add the tax return. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>Add a New Tax Return</DialogTitle>
      </DialogHeader>

      <form class="space-y-4 py-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="tax-return-year">Tax-return year *</Label>
          <Input id="tax-return-year" v-model.number="year" type="number" required />
        </div>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
      </form>

      <DialogFooter>
        <Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button>
        <Button :disabled="loading" @click="submit">
          {{ loading ? 'Adding...' : 'Add Tax Return' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
