<script setup>
import { ref, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const props = defineProps({
  grant: { type: Object, default: null },
  saving: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['close', 'save'])
const number = ref('')
watch(
  () => props.grant,
  (grant) => {
    number.value = grant?.grantNumber || ''
  },
  { immediate: true },
)
const close = () => {
  if (!props.saving) emit('close')
}
</script>

<template>
  <Dialog
    :open="Boolean(grant)"
    @update:open="
      (open) => {
        if (!open) close()
      }
    "
  >
    <DialogContent
      :show-close-button="!saving"
      @interact-outside="
        (event) => {
          if (saving) event.preventDefault()
        }
      "
      @escape-key-down="
        (event) => {
          if (saving) event.preventDefault()
        }
      "
    >
      <DialogHeader>
        <DialogTitle>Edit grant number</DialogTitle>
        <DialogDescription
          >Set the broker grant number for {{ grant?.title }}. Leave blank to remove
          it.</DialogDescription
        >
      </DialogHeader>
      <form class="space-y-4" @submit.prevent="emit('save', number)">
        <Label for="edit-grant-number">Broker grant number</Label>
        <Input id="edit-grant-number" v-model="number" :maxlength="256" :disabled="saving" />
        <p class="text-xs text-muted-foreground">
          Numbers must be unique for this stock. Leading zeros are preserved.
        </p>
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
        <DialogFooter>
          <Button type="button" variant="outline" :disabled="saving" @click="close">Cancel</Button>
          <Button type="submit" :disabled="saving">{{
            saving ? 'Saving…' : 'Save grant number'
          }}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
