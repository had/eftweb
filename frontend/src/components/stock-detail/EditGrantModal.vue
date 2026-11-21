<script setup>
import { computed, ref, watch } from 'vue'
import axios from 'axios'
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
import { isCalendarDate } from './vesting.js'

const props = defineProps({
  grant: { type: Object, default: null },
  familyId: Number,
  saving: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['close', 'save'])
const details = ref({})
const errors = ref({})
const taxpayers = ref([])
const loadingTaxpayers = ref(false)
const taxpayerError = ref('')
watch(
  [() => props.grant, () => props.familyId],
  async ([grant, familyId], _, onCleanup) => {
    details.value = {
      title: grant?.title || '',
      grant_number: grant?.grantNumber || '',
      grant_date: grant?.grantDate || '',
      approval_date: grant?.approvalDate || '',
      taxpayer_role: grant?.taxpayerRole || '',
    }
    errors.value = {}
    taxpayers.value = []
    taxpayerError.value = ''
    loadingTaxpayers.value = false
    if (!grant || !familyId) return
    const controller = new AbortController()
    onCleanup(() => controller.abort())
    loadingTaxpayers.value = true
    try {
      const { data } = await axios.get(`/api/families/${familyId}`, { signal: controller.signal })
      if (controller.signal.aborted) return
      taxpayers.value = ['taxpayer1', 'taxpayer2']
        .filter((role) => data[role])
        .map((role) => ({
          role,
          label: `${data[role].first_name} ${data[role].last_name} (${role === 'taxpayer1' ? 'taxpayer 1' : 'taxpayer 2'})`,
        }))
    } catch {
      if (!controller.signal.aborted)
        taxpayerError.value =
          'Could not load taxpayers. Close and reopen the form to retry assigning a taxpayer.'
    } finally {
      if (!controller.signal.aborted) loadingTaxpayers.value = false
    }
  },
  { immediate: true },
)
const changes = computed(() => {
  if (!props.grant) return {}
  const values = {
    title: details.value.title.trim(),
    grant_number: details.value.grant_number.trim() || null,
    grant_date: details.value.grant_date,
    approval_date: details.value.approval_date || null,
    taxpayer_role: details.value.taxpayer_role || null,
  }
  const original = {
    title: props.grant.title,
    grant_number: props.grant.grantNumber || null,
    grant_date: props.grant.grantDate,
    approval_date: props.grant.approvalDate || null,
    taxpayer_role: props.grant.taxpayerRole || null,
  }
  return Object.fromEntries(
    Object.entries(values).filter(([key, value]) => value !== original[key]),
  )
})
const save = () => {
  if (!props.grant || props.saving || loadingTaxpayers.value) return
  const issues = {}
  if (!isCalendarDate(details.value.grant_date)) issues.grant_date = 'Enter a valid grant date.'
  if (
    details.value.approval_date &&
    (!isCalendarDate(details.value.approval_date) || details.value.approval_date < '2015-08-08')
  )
    issues.approval_date = 'Enter a shareholder approval date on or after 8 August 2015.'
  if (details.value.title.trim().length > 256) issues.title = 'Use at most 256 characters.'
  if (details.value.grant_number.trim().length > 256)
    issues.grant_number = 'Use at most 256 characters.'
  if (
    changes.value.taxpayer_role &&
    !taxpayers.value.some((person) => person.role === changes.value.taxpayer_role)
  )
    issues.taxpayer_role = 'Select a taxpayer in this family.'
  errors.value = issues
  if (!Object.keys(issues).length && Object.keys(changes.value).length)
    emit('save', { ...changes.value })
}
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
      class="max-h-[calc(100dvh-2rem)] overflow-y-auto"
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
        <DialogTitle>Edit grant</DialogTitle>
        <DialogDescription
          >Update the details for {{ grant?.title }} used in broker matching and tax
          preparation.</DialogDescription
        >
      </DialogHeader>
      <form class="space-y-4" @submit.prevent="save">
        <div class="space-y-2">
          <Label for="edit-grant-title">Grant title (optional)</Label>
          <Input
            id="edit-grant-title"
            v-model="details.title"
            maxlength="256"
            :disabled="saving"
            :aria-invalid="Boolean(errors.title)"
          />
          <p class="text-xs text-muted-foreground">
            Leave blank to use the stock symbol and grant date.
          </p>
          <p v-if="errors.title" role="alert" class="text-xs text-destructive">
            {{ errors.title }}
          </p>
        </div>
        <div class="space-y-2">
          <Label for="edit-grant-number">Broker grant number (optional)</Label>
          <Input
            id="edit-grant-number"
            v-model="details.grant_number"
            maxlength="256"
            :disabled="saving"
            :aria-invalid="Boolean(errors.grant_number)"
          />
          <p class="text-xs text-muted-foreground">
            Unique for this stock; leading zeros are preserved. Leave blank to remove it.
          </p>
          <p v-if="errors.grant_number" role="alert" class="text-xs text-destructive">
            {{ errors.grant_number }}
          </p>
        </div>
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-2">
            <Label for="edit-grant-date">Grant date</Label>
            <Input
              id="edit-grant-date"
              v-model="details.grant_date"
              type="date"
              required
              :disabled="saving"
              :aria-invalid="Boolean(errors.grant_date)"
            />
            <p class="text-xs text-muted-foreground">
              Individual grant date. Acquisition dates come from the vesting releases.
            </p>
            <p v-if="errors.grant_date" role="alert" class="text-xs text-destructive">
              {{ errors.grant_date }}
            </p>
          </div>
          <div class="space-y-2">
            <Label for="edit-grant-approval">Shareholder approval date</Label>
            <Input
              id="edit-grant-approval"
              v-model="details.approval_date"
              type="date"
              min="2015-08-08"
              :disabled="saving"
              :aria-invalid="Boolean(errors.approval_date)"
            />
            <p class="text-xs text-muted-foreground">
              Plan approval date used to determine the RSU tax regime. Leave blank if unknown.
            </p>
            <p v-if="errors.approval_date" role="alert" class="text-xs text-destructive">
              {{ errors.approval_date }}
            </p>
          </div>
        </div>
        <div class="space-y-2">
          <Label for="edit-grant-taxpayer">Taxpayer</Label>
          <select
            id="edit-grant-taxpayer"
            v-model="details.taxpayer_role"
            class="h-9 w-full rounded-md border bg-background px-3 text-sm"
            :disabled="saving || loadingTaxpayers || Boolean(taxpayerError)"
            :aria-invalid="Boolean(errors.taxpayer_role)"
          >
            <option value="">Not assigned</option>
            <option
              v-if="
                details.taxpayer_role &&
                !taxpayers.some((person) => person.role === details.taxpayer_role)
              "
              :value="details.taxpayer_role"
              disabled
            >
              {{
                details.taxpayer_role === 'taxpayer1' ? 'Taxpayer 1' : 'Taxpayer 2'
              }}
              (unavailable)
            </option>
            <option v-for="person in taxpayers" :key="person.role" :value="person.role">
              {{ person.label }}
            </option>
          </select>
          <p v-if="loadingTaxpayers" class="text-xs text-muted-foreground">
            Loading family taxpayers…
          </p>
          <p v-if="taxpayerError" role="alert" class="text-xs text-destructive">
            {{ taxpayerError }}
          </p>
          <p v-if="errors.taxpayer_role" role="alert" class="text-xs text-destructive">
            {{ errors.taxpayer_role }}
          </p>
        </div>
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
        <DialogFooter>
          <Button type="button" variant="outline" :disabled="saving" @click="close">Cancel</Button>
          <Button
            type="submit"
            :disabled="saving || loadingTaxpayers || !Object.keys(changes).length"
            >{{ saving ? 'Saving…' : 'Save grant' }}</Button
          >
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
