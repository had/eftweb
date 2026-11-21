<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import axios from 'axios'
import { Info, Plus, Trash2 } from 'lucide-vue-next'
import {
  TooltipContent,
  TooltipPortal,
  TooltipProvider,
  TooltipRoot,
  TooltipTrigger,
} from 'reka-ui'
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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  SCHEDULES,
  createId,
  formatDate,
  formatShares,
  generateVestings,
  isCalendarDate,
  isWholeQuantity,
  localDate,
  scheduledTotal,
  validateGrantDetails,
  validateVestings,
} from './vesting.js'

const props = defineProps({
  open: Boolean,
  familyId: Number,
  ticker: { type: String, default: 'STOCK' },
  saving: Boolean,
  saveError: { type: String, default: '' },
})
const emit = defineEmits(['update:open', 'confirmed'])
const taxpayers = ref([{ role: 'taxpayer1', label: 'Taxpayer 1' }])
watch(
  () => props.open,
  async (open) => {
    if (!open || !props.familyId) return
    taxpayers.value = []
    try {
      const { data } = await axios.get(`/api/families/${props.familyId}`)
      taxpayers.value = ['taxpayer1', 'taxpayer2']
        .filter((role) => data[role])
        .map((role) => ({
          role,
          label: `${data[role].first_name} ${data[role].last_name} (${role === 'taxpayer1' ? 'taxpayer 1' : 'taxpayer 2'})`,
        }))
    } catch {
      error.value = 'Could not load family taxpayers. Close and reopen the form to retry.'
    }
  },
)
const validateTaxGrantDetails = (draft) => {
  const result = validateGrantDetails(draft)
  if (!isCalendarDate(draft.approvalDate) || draft.approvalDate < '2015-08-08')
    result.approvalDate = 'Enter a shareholder approval date on or after 8 August 2015.'
  if (!taxpayers.value.some((t) => t.role === draft.taxpayerRole))
    result.taxpayerRole = 'Select a taxpayer in this family.'
  return result
}
const step = ref(1)
const details = ref({})
const vestings = ref([])
const dateEdited = ref(false)
const fieldErrors = ref({})
const error = ref('')
const regenerationNeeded = ref(false)
const generatedParameters = ref('')
const generatedRows = ref('')
const submitted = ref(false)
const creationToken = ref('')
const body = ref(null)
const stepHeading = ref(null)
const stepLabels = ['Grant details', 'Adjust vesting', 'Review & confirm']

const parameters = () =>
  JSON.stringify([
    Number(details.value.quantity),
    details.value.startDate,
    details.value.scheduleType,
  ])
const rowSignature = () =>
  JSON.stringify(vestings.value.map((release) => [release.date, Number(release.quantity)]))
const customized = computed(
  () => Boolean(generatedRows.value) && rowSignature() !== generatedRows.value,
)
const effectiveTitle = computed(
  () => details.value.title?.trim() || `${props.ticker}-${details.value.grantDate}`,
)
const total = computed(() => scheduledTotal(vestings.value))
const difference = computed(() => Number(details.value.quantity) - total.value)
const reviewRows = computed(() => [...vestings.value].sort((a, b) => a.date.localeCompare(b.date)))
const scheduleLabel = computed(
  () => SCHEDULES.find((schedule) => schedule.value === details.value.scheduleType)?.label,
)

const reset = () => {
  const today = localDate()
  details.value = {
    grantDate: today,
    approvalDate: '',
    taxpayerRole: 'taxpayer1',
    title: '',
    grantNumber: '',
    quantity: '',
    startDate: today,
    scheduleType: SCHEDULES[0].value,
  }
  vestings.value = []
  step.value = 1
  dateEdited.value = false
  fieldErrors.value = {}
  error.value = ''
  regenerationNeeded.value = false
  generatedParameters.value = ''
  generatedRows.value = ''
  submitted.value = false
  creationToken.value = createId()
}

watch(() => props.open, reset, { immediate: true })
watch(
  () => props.saving,
  (saving) => {
    if (!saving) submitted.value = false
  },
)
watch(
  () => props.saveError,
  async (message) => {
    if (message) {
      submitted.value = false
      await nextTick()
      body.value?.scrollTo({ top: 0 })
    }
  },
)
watch(step, async () => {
  await nextTick()
  body.value?.scrollTo({ top: 0 })
  stepHeading.value?.focus()
})
watch(error, async (message) => {
  if (message) {
    await nextTick()
    body.value?.scrollTo({ top: 0 })
  }
})

const setGrantDate = (value) => {
  details.value.grantDate = value
  if (!dateEdited.value) details.value.startDate = value
}
const setStartDate = (value) => {
  dateEdited.value = true
  details.value.startDate = value
}
const close = () => {
  if (props.saving || submitted.value) return
  reset()
  emit('update:open', false)
}
const generate = () => {
  vestings.value = generateVestings(details.value)
  generatedParameters.value = parameters()
  generatedRows.value = rowSignature()
  regenerationNeeded.value = false
  error.value = ''
  step.value = 2
}

const next = () => {
  error.value = ''
  if (step.value === 1) {
    fieldErrors.value = validateTaxGrantDetails(details.value)
    if (Object.keys(fieldErrors.value).length) return
    if (generatedParameters.value && generatedParameters.value === parameters()) {
      regenerationNeeded.value = false
      step.value = 2
    } else if (customized.value) {
      regenerationNeeded.value = true
    } else {
      generate()
    }
  } else if (step.value === 2) {
    error.value = validateVestings(vestings.value, details.value.quantity)
    if (!error.value) step.value = 3
  }
}

const regenerate = () => {
  fieldErrors.value = validateTaxGrantDetails(details.value)
  if (!Object.keys(fieldErrors.value).length) generate()
}
const back = () => {
  error.value = ''
  regenerationNeeded.value = false
  step.value -= 1
}
const insertAfter = async (index) => {
  const id = createId()
  vestings.value.splice(index + 1, 0, { id, date: '', quantity: '' })
  await nextTick()
  body.value?.querySelector(`[data-vesting-date="${id}"]`)?.focus()
}
const confirm = () => {
  if (!props.open || props.saving || submitted.value || step.value !== 3) return
  fieldErrors.value = validateTaxGrantDetails(details.value)
  error.value = validateVestings(vestings.value, details.value.quantity)
  if (Object.keys(fieldErrors.value).length || error.value) return
  submitted.value = true
  emit('confirmed', {
    creationToken: creationToken.value,
    title: effectiveTitle.value,
    ...(details.value.grantNumber?.trim() ? { grantNumber: details.value.grantNumber.trim() } : {}),
    grantDate: details.value.grantDate,
    approvalDate: details.value.approvalDate,
    taxpayerRole: details.value.taxpayerRole,
    quantity: Number(details.value.quantity),
    startDate: details.value.startDate,
    scheduleType: details.value.scheduleType,
    customized: customized.value,
    vestings: reviewRows.value.map((release) => ({
      ...release,
      quantity: Number(release.quantity),
    })),
  })
}
const preventDismiss = (event) => {
  if (props.saving || submitted.value) event.preventDefault()
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
      class="flex max-h-[90dvh] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl"
      :show-close-button="!saving && !submitted"
      @escape-key-down="preventDismiss"
      @interact-outside="preventDismiss"
    >
      <DialogHeader class="shrink-0 p-6 pb-4">
        <DialogTitle>Add grant · {{ ticker }}</DialogTitle>
        <DialogDescription
          >Define your grant, adjust each release, then review before adding.</DialogDescription
        >
      </DialogHeader>
      <ol class="mx-6 mb-5 flex shrink-0 gap-3" aria-label="Grant creation steps">
        <li
          v-for="(label, index) in stepLabels"
          :key="label"
          :aria-current="step === index + 1 ? 'step' : undefined"
          class="flex flex-1 items-center gap-2 border-b-2 pb-3 text-xs sm:text-sm"
          :class="
            step >= index + 1
              ? 'border-primary text-primary'
              : 'border-border text-muted-foreground'
          "
        >
          <span
            class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium"
            :class="step === index + 1 && 'border-primary bg-primary text-primary-foreground'"
            >{{ index + 1 }}</span
          >
          <span>{{ label }}</span>
        </li>
      </ol>

      <div ref="body" class="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
        <h3 ref="stepHeading" tabindex="-1" class="mb-4 text-lg font-semibold outline-none">
          Step {{ step }}: {{ stepLabels[step - 1] }}
        </h3>
        <form id="add-grant-form" novalidate @submit.prevent="step === 3 ? confirm() : next()">
          <p v-if="saveError" role="alert" class="mb-4 text-sm text-destructive">{{ saveError }}</p>
          <p v-if="error" role="alert" class="mb-4 text-sm text-destructive">{{ error }}</p>
          <div v-if="step === 1" class="space-y-5">
            <div class="grid gap-4 sm:grid-cols-2">
              <div class="space-y-2">
                <Label for="approval-date">Shareholder approval date *</Label>
                <Input
                  id="approval-date"
                  v-model="details.approvalDate"
                  type="date"
                  min="2015-08-08"
                  required
                />
                <p class="text-xs text-muted-foreground">
                  The plan approval date, separate from your individual grant date.
                </p>
                <p v-if="fieldErrors.approvalDate" role="alert" class="text-xs text-destructive">
                  {{ fieldErrors.approvalDate }}
                </p>
              </div>
              <div class="space-y-2">
                <Label for="grant-taxpayer">Taxpayer *</Label>
                <select
                  id="grant-taxpayer"
                  v-model="details.taxpayerRole"
                  class="w-full rounded-md border bg-background p-2 text-sm"
                >
                  <option v-for="person in taxpayers" :key="person.role" :value="person.role">
                    {{ person.label }}
                  </option>
                </select>
                <p v-if="fieldErrors.taxpayerRole" role="alert" class="text-xs text-destructive">
                  {{ fieldErrors.taxpayerRole }}
                </p>
              </div>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <div class="space-y-2">
                <Label for="grant-date">Grant date *</Label>
                <Input
                  id="grant-date"
                  :model-value="details.grantDate"
                  type="date"
                  required
                  :aria-invalid="Boolean(fieldErrors.grantDate)"
                  aria-describedby="grant-date-error"
                  @update:model-value="setGrantDate"
                />
                <p
                  v-if="fieldErrors.grantDate"
                  id="grant-date-error"
                  role="alert"
                  class="text-xs text-destructive"
                >
                  {{ fieldErrors.grantDate }}
                </p>
              </div>
              <div class="space-y-2">
                <Label for="grant-quantity">Granted shares *</Label>
                <Input
                  id="grant-quantity"
                  v-model="details.quantity"
                  type="number"
                  min="1"
                  step="1"
                  required
                  :aria-invalid="Boolean(fieldErrors.quantity)"
                  aria-describedby="grant-quantity-error"
                />
                <p
                  v-if="fieldErrors.quantity"
                  id="grant-quantity-error"
                  role="alert"
                  class="text-xs text-destructive"
                >
                  {{ fieldErrors.quantity }}
                </p>
              </div>
            </div>
            <div class="space-y-2">
              <Label for="grant-title"
                >Grant title
                <span class="font-normal text-muted-foreground">(optional)</span></Label
              >
              <Input
                id="grant-title"
                v-model="details.title"
                :placeholder="`${ticker}-${details.grantDate}`"
                :maxlength="256"
                :aria-invalid="Boolean(fieldErrors.title)"
                aria-describedby="grant-title-hint"
              />
              <p id="grant-title-hint" class="text-xs text-muted-foreground">
                Leave blank to use {{ ticker }}-{{ details.grantDate }}.
              </p>
              <p v-if="fieldErrors.title" role="alert" class="text-xs text-destructive">
                {{ fieldErrors.title }}
              </p>
            </div>
            <div class="space-y-2">
              <Label for="grant-number">Broker grant number (optional)</Label>
              <Input
                id="grant-number"
                v-model="details.grantNumber"
                :maxlength="256"
                aria-describedby="grant-number-hint"
              />
              <p id="grant-number-hint" class="text-xs text-muted-foreground">
                Enter the exact grant number, including any leading zeros, to match E*TRADE sales.
              </p>
            </div>
            <div class="space-y-2">
              <Label for="vesting-start">Vesting reference date (T) *</Label>
              <Input
                id="vesting-start"
                :model-value="details.startDate"
                type="date"
                required
                :aria-invalid="Boolean(fieldErrors.startDate)"
                aria-describedby="vesting-start-hint vesting-start-error"
                @update:model-value="setStartDate"
              />
              <p id="vesting-start-hint" class="text-xs text-muted-foreground">
                All release dates are calculated from T. This can differ from the grant date.
              </p>
              <p
                v-if="fieldErrors.startDate"
                id="vesting-start-error"
                role="alert"
                class="text-xs text-destructive"
              >
                {{ fieldErrors.startDate }}
              </p>
            </div>
            <fieldset class="space-y-3">
              <legend class="mb-2 text-sm font-medium">Vesting schedule *</legend>
              <TooltipProvider :delay-duration="150">
                <RadioGroup v-model="details.scheduleType" aria-label="Vesting schedule">
                  <div
                    v-for="schedule in SCHEDULES"
                    :key="schedule.value"
                    class="flex items-center gap-3 rounded-lg border p-4"
                    :class="
                      details.scheduleType === schedule.value && 'border-primary bg-primary/5'
                    "
                  >
                    <RadioGroupItem :id="`schedule-${schedule.value}`" :value="schedule.value" />
                    <Label :for="`schedule-${schedule.value}`" class="flex-1 cursor-pointer">{{
                      schedule.label
                    }}</Label>
                    <TooltipRoot>
                      <TooltipTrigger as-child
                        ><button
                          type="button"
                          class="rounded text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                          :aria-label="`Details about ${schedule.label}`"
                        >
                          <Info class="h-4 w-4" /></button
                      ></TooltipTrigger>
                      <TooltipPortal
                        ><TooltipContent
                          side="top"
                          :side-offset="6"
                          class="z-[60] max-w-xs rounded-md border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md"
                          >{{ schedule.description }}</TooltipContent
                        ></TooltipPortal
                      >
                    </TooltipRoot>
                  </div>
                </RadioGroup>
              </TooltipProvider>
              <p v-if="fieldErrors.scheduleType" role="alert" class="text-xs text-destructive">
                {{ fieldErrors.scheduleType }}
              </p>
            </fieldset>
            <div
              v-if="regenerationNeeded"
              role="alert"
              class="space-y-3 rounded-lg border border-primary/40 bg-primary/5 p-4"
            >
              <p class="text-sm">
                These schedule settings have changed. Regenerating will replace your customized
                release rows.
              </p>
              <div class="flex flex-wrap gap-2">
                <Button type="button" @click="regenerate">Regenerate schedule</Button
                ><Button type="button" variant="outline" @click="regenerationNeeded = false"
                  >Keep editing</Button
                >
              </div>
            </div>
          </div>

          <div v-else-if="step === 2" class="space-y-4">
            <div class="rounded-lg bg-muted/60 p-3 text-sm" aria-live="polite">
              <p>
                <span class="font-medium tabular-nums">{{ formatShares(total) }}</span> /
                {{ formatShares(Number(details.quantity)) }} shares scheduled
              </p>
              <p
                class="mt-1 text-xs"
                :class="difference === 0 ? 'text-primary' : 'text-destructive'"
              >
                {{
                  difference === 0
                    ? 'All granted shares are accounted for.'
                    : difference > 0
                      ? `${formatShares(difference)} shares remaining to schedule.`
                      : `${formatShares(-difference)} excess shares. Reduce the schedule total.`
                }}
              </p>
            </div>
            <p class="text-xs text-muted-foreground">
              Edit dates and whole-share quantities. The final schedule will be sorted by date.
            </p>
            <div class="overflow-x-auto">
              <table class="w-full min-w-[410px] text-sm">
                <thead>
                  <tr class="border-b text-left text-xs text-muted-foreground">
                    <th scope="col" class="py-2 pr-2 font-medium">Release date</th>
                    <th scope="col" class="py-2 pr-2 font-medium">Shares</th>
                    <th scope="col" class="py-2 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(release, index) in vestings" :key="release.id" class="border-b">
                    <td class="py-2 pr-2">
                      <Input
                        v-model="release.date"
                        type="date"
                        :data-vesting-date="release.id"
                        :aria-label="`Release ${index + 1} date`"
                        :aria-invalid="Boolean(error) && !isCalendarDate(release.date)"
                        required
                      />
                    </td>
                    <td class="w-28 py-2 pr-2">
                      <Input
                        v-model="release.quantity"
                        type="number"
                        min="1"
                        step="1"
                        :aria-label="`Release ${index + 1} shares`"
                        :aria-invalid="Boolean(error) && !isWholeQuantity(release.quantity)"
                        required
                      />
                    </td>
                    <td class="py-2">
                      <div class="flex justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          :aria-label="`Insert after release ${index + 1}`"
                          title="Insert a release after this row"
                          @click="insertAfter(index)"
                          ><Plus class="h-4 w-4" /></Button
                        ><Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          class="text-destructive"
                          :aria-label="`Delete release ${index + 1}`"
                          title="Delete release"
                          @click="vestings.splice(index, 1)"
                          ><Trash2 class="h-4 w-4"
                        /></Button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <Button type="button" variant="outline" @click="insertAfter(vestings.length - 1)"
              ><Plus class="h-4 w-4" /> Add vesting</Button
            >
          </div>

          <div v-else class="space-y-5">
            <div class="rounded-lg border bg-muted/30 p-4">
              <h4 class="break-words text-lg font-semibold">{{ effectiveTitle }}</h4>
              <dl class="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt class="text-xs text-muted-foreground">Shareholder approval date</dt>
                  <dd>{{ formatDate(details.approvalDate) }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">Taxpayer</dt>
                  <dd>{{ taxpayers.find((t) => t.role === details.taxpayerRole)?.label }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">Grant date</dt>
                  <dd class="mt-1">{{ formatDate(details.grantDate) }}</dd>
                </div>
                <div v-if="details.grantNumber?.trim()">
                  <dt class="text-xs text-muted-foreground">Broker grant number</dt>
                  <dd class="mt-1">{{ details.grantNumber.trim() }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">Granted quantity</dt>
                  <dd class="mt-1">{{ formatShares(Number(details.quantity)) }} shares</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">Vesting reference date (T)</dt>
                  <dd class="mt-1">{{ formatDate(details.startDate) }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">Schedule</dt>
                  <dd class="mt-1">{{ scheduleLabel }}{{ customized ? ' · Customized' : '' }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">First release</dt>
                  <dd class="mt-1">{{ formatDate(reviewRows[0].date) }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-muted-foreground">Final release</dt>
                  <dd class="mt-1">{{ formatDate(reviewRows.at(-1).date) }}</dd>
                </div>
              </dl>
            </div>
            <div>
              <h4 class="mb-3 font-medium">
                {{ vestings.length }} releases · {{ formatShares(total) }} shares total
              </h4>
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b text-xs text-muted-foreground">
                    <th scope="col" class="py-2 text-left font-medium">Release date</th>
                    <th scope="col" class="py-2 text-right font-medium">Shares</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="release in reviewRows" :key="release.id" class="border-b">
                    <td class="py-2">{{ formatDate(release.date) }}</td>
                    <td class="py-2 text-right tabular-nums">
                      {{ formatShares(Number(release.quantity)) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="text-xs text-muted-foreground">
              Confirm to save this grant and its vesting releases.
            </p>
          </div>
        </form>
      </div>

      <DialogFooter class="shrink-0 gap-2 border-t bg-background p-4 sm:justify-between">
        <Button type="button" variant="outline" :disabled="saving || submitted" @click="close"
          >Cancel</Button
        >
        <div class="flex justify-end gap-2">
          <Button
            v-if="step > 1"
            type="button"
            variant="outline"
            :disabled="saving || submitted"
            @click="back"
            >Back</Button
          >
          <Button type="submit" form="add-grant-form" :disabled="saving || submitted">{{
            saving || submitted ? 'Saving...' : step === 3 ? 'Add grant' : 'Next'
          }}</Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
