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
  property: Object,
  properties: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:open', 'saved'])
const name = ref('')
const estimatedValue = ref('')
const isPrincipalHome = ref(false)
const replacementId = ref(null)
const principalConflict = ref(null)
const error = ref('')
const loading = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    name.value = props.property?.name ?? ''
    estimatedValue.value = props.property?.estimated_value ?? ''
    isPrincipalHome.value = props.property?.is_principal_home ?? false
    replacementId.value = null
    principalConflict.value = null
    error.value = ''
  },
)

const close = () => {
  if (!loading.value) emit('update:open', false)
}
const togglePrincipalHome = () => {
  if (isPrincipalHome.value) {
    isPrincipalHome.value = false
    replacementId.value = null
    return
  }
  const previous = props.properties.find(
    (item) => item.is_principal_home && item.id !== props.property?.id,
  )
  if (previous) principalConflict.value = previous
  else isPrincipalHome.value = true
}
const cancelReplacement = () => {
  principalConflict.value = null
  isPrincipalHome.value = false
  replacementId.value = null
}
const confirmReplacement = () => {
  replacementId.value = principalConflict.value.id
  isPrincipalHome.value = true
  principalConflict.value = null
  error.value = ''
}

const submit = async () => {
  if (loading.value || principalConflict.value) return
  error.value = ''
  if (!name.value.trim() || name.value.trim().length > 256) {
    error.value = 'Enter a property name of at most 256 characters.'
    return
  }
  const amount = String(estimatedValue.value).trim()
  if (!/^\d+(\.\d{1,2})?$/.test(amount) || Number(amount) >= 1_000_000_000_000) {
    error.value =
      'Enter a non-negative estimated value below 1 trillion, with at most two decimals.'
    return
  }
  const payload = {
    name: name.value.trim(),
    estimated_value: amount,
    is_principal_home: isPrincipalHome.value,
    replace_principal_home_id: isPrincipalHome.value ? replacementId.value : null,
  }
  loading.value = true
  try {
    const endpoint = `/api/families/${props.familyId}/properties`
    if (props.property) await axios.put(`${endpoint}/${props.property.id}`, payload)
    else await axios.post(endpoint, payload)
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    if (requestError.response?.status === 409 && requestError.response.data.principal_home) {
      principalConflict.value = requestError.response.data.principal_home
      isPrincipalHome.value = false
      replacementId.value = null
    } else {
      error.value =
        requestError.response?.data?.error || 'Failed to save the property. Please try again.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>{{ property ? 'Edit Property' : 'Add a New Property' }}</DialogTitle>
        <DialogDescription
          >Enter the property's name and estimated value in euros.</DialogDescription
        >
      </DialogHeader>
      <form id="property-form" class="space-y-4 py-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="property-name">Name *</Label>
          <Input
            id="property-name"
            v-model="name"
            :maxlength="256"
            :disabled="loading"
            placeholder="e.g. Paris apartment"
            required
          />
        </div>
        <div class="flex items-center justify-between gap-4">
          <Label for="property-principal-home">Principal home</Label>
          <button
            id="property-principal-home"
            type="button"
            role="switch"
            :aria-checked="isPrincipalHome"
            :disabled="loading"
            class="inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50"
            :class="isPrincipalHome ? 'bg-primary' : 'bg-input'"
            @click="togglePrincipalHome"
          >
            <span
              class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-sm transition-transform"
              :class="isPrincipalHome ? 'translate-x-5' : 'translate-x-0'"
            />
          </button>
        </div>
        <div class="space-y-2">
          <Label for="property-value">Estimated value (€) *</Label>
          <Input
            id="property-value"
            v-model="estimatedValue"
            type="number"
            min="0"
            max="999999999999.99"
            step="0.01"
            :disabled="loading"
            placeholder="e.g. 350000"
            required
          />
        </div>
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
      </form>
      <DialogFooter>
        <Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button>
        <Button type="submit" form="property-form" :disabled="loading">
          {{ loading ? 'Saving...' : property ? 'Save Changes' : 'Add Property' }}
        </Button>
      </DialogFooter>
      <Dialog :open="Boolean(principalConflict)" @update:open="cancelReplacement">
        <DialogContent class="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Replace Principal Home</DialogTitle>
            <DialogDescription>
              {{ principalConflict?.name }} is already principal home, do you want to replace it
              with {{ name.trim() || 'this property' }}?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" @click="cancelReplacement">Cancel</Button>
            <Button type="button" @click="confirmReplacement">Replace</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DialogContent>
  </Dialog>
</template>
