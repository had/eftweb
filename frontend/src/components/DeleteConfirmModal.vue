<script setup>
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const props = defineProps({
  open: Boolean,
  familyName: String,
  title: { type: String, default: 'Archive Family' },
  description: String,
  confirmLabel: { type: String, default: 'Archive' },
  busy: Boolean,
  error: { type: String, default: '' },
})

const emit = defineEmits(['update:open', 'confirm', 'cancel'])

const handleConfirm = () => {
  if (!props.busy) emit('confirm')
}

const handleCancel = () => {
  if (!props.busy) emit('cancel')
}
const preventDismiss = (event) => {
  if (props.busy) event.preventDefault()
}
</script>

<template>
  <Dialog
    :open="open"
    @update:open="
      (val) => {
        if (!busy) emit('update:open', val)
      }
    "
  >
    <DialogContent
      class="sm:max-w-[425px]"
      :show-close-button="!busy"
      @escape-key-down="preventDismiss"
      @interact-outside="preventDismiss"
    >
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>
          {{
            description ||
            `Are you sure you want to archive "${familyName}"? It will be hidden from the active-family list.`
          }}
        </DialogDescription>
      </DialogHeader>

      <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
      <DialogFooter>
        <Button type="button" variant="outline" :disabled="busy" @click="handleCancel">
          Cancel
        </Button>
        <Button variant="destructive" :disabled="busy" @click="handleConfirm">
          {{ busy ? 'Deleting...' : confirmLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
