<script setup>
import { computed, ref, watch } from 'vue'
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
import { createId, localDate, validatePurchase } from './vesting.js'

const props = defineProps({
  open: Boolean,
  ticker: { type: String, default: 'STOCK' },
  today: { type: String, default: () => localDate() },
  saving: Boolean,
  saveError: { type: String, default: '' },
})
const emit = defineEmits(['update:open', 'confirmed'])
const details = ref({ purchaseDate: '', quantity: '' })
const errors = ref({})
const creationToken = ref('')
const submitted = ref(false)
const busy = computed(() => props.saving || submitted.value)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    details.value = { purchaseDate: props.today, quantity: '' }
    errors.value = {}
    creationToken.value = createId()
    submitted.value = false
  },
  { immediate: true },
)
watch(
  () => props.saving,
  (saving) => {
    if (!saving) submitted.value = false
  },
)
watch(
  () => props.saveError,
  (error) => {
    if (error) submitted.value = false
  },
)

const close = () => {
  if (!busy.value) emit('update:open', false)
}
const preventDismiss = (event) => {
  if (busy.value) event.preventDefault()
}
const confirm = () => {
  if (!props.open || busy.value) return
  errors.value = validatePurchase(details.value, props.today)
  if (Object.keys(errors.value).length) return
  submitted.value = true
  emit('confirmed', {
    ...details.value,
    quantity: Number(details.value.quantity),
    creationToken: creationToken.value,
  })
}
</script>

<template>
  <Dialog
    :open="open"
    @update:open="
      (value) => {
        if (!value) close()
      }
    "
  >
    <DialogContent
      :show-close-button="!busy"
      @escape-key-down="preventDismiss"
      @interact-outside="preventDismiss"
    >
      <DialogHeader>
        <DialogTitle>Add ESPP purchase · {{ ticker }}</DialogTitle>
        <DialogDescription
          >Record shares acquired through your employee stock purchase plan.</DialogDescription
        >
      </DialogHeader>
      <form class="space-y-6" novalidate @submit.prevent="confirm">
        <p v-if="saveError" role="alert" class="text-sm text-destructive">{{ saveError }}</p>
        <fieldset :disabled="busy" class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-2">
            <Label for="purchase-date">Purchase date</Label>
            <Input
              id="purchase-date"
              v-model="details.purchaseDate"
              type="date"
              :max="today"
              :aria-invalid="Boolean(errors.purchaseDate)"
              :aria-describedby="errors.purchaseDate ? 'purchase-date-error' : undefined"
            />
            <p
              v-if="errors.purchaseDate"
              id="purchase-date-error"
              role="alert"
              class="text-xs text-destructive"
            >
              {{ errors.purchaseDate }}
            </p>
          </div>
          <div class="space-y-2">
            <Label for="purchase-quantity">Quantity purchased</Label>
            <Input
              id="purchase-quantity"
              v-model="details.quantity"
              type="number"
              min="1"
              step="1"
              placeholder="Shares purchased"
              :aria-invalid="Boolean(errors.quantity)"
              :aria-describedby="errors.quantity ? 'purchase-quantity-error' : undefined"
            />
            <p
              v-if="errors.quantity"
              id="purchase-quantity-error"
              role="alert"
              class="text-xs text-destructive"
            >
              {{ errors.quantity }}
            </p>
          </div>
        </fieldset>
        <DialogFooter>
          <Button type="button" variant="outline" :disabled="busy" @click="close">Cancel</Button>
          <Button type="submit" :disabled="busy">{{ busy ? 'Saving…' : 'Add purchase' }}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
