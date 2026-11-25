<script setup>
import { formatDecimal } from '@/lib/numberFormat.js'
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
import { createId, formatDate, formatShares, localDate } from './vesting.js'
import { availablePockets, saleProceeds, validateSale } from './sales.js'

const props = defineProps({
  open: Boolean,
  ticker: { type: String, default: 'STOCK' },
  grants: { type: Array, default: () => [] },
  purchases: { type: Array, default: () => [] },
  sales: { type: Array, default: () => [] },
  today: { type: String, default: () => localDate() },
  saving: Boolean,
  saveError: { type: String, default: '' },
})
const emit = defineEmits(['update:open', 'confirmed'])
const details = ref({ transactionDate: '', quantity: '', proceedsPerShare: '' })
const quantities = ref({})
const fmvs = ref({})
const errors = ref({})
const creationToken = ref('')
const submitted = ref(false)
const pockets = computed(() =>
  availablePockets(props.grants, props.sales, details.value.transactionDate, props.purchases),
)
const allocations = computed(() =>
  Object.entries(quantities.value)
    .filter(([, quantity]) => quantity !== '' && Number(quantity) !== 0)
    .map(([key, quantity]) => {
      const [type, id] = key.split(':')
      return {
        [type === 'purchase' ? 'purchaseId' : 'vestingId']: Number(id),
        quantity: Number(quantity),
        acquisitionFmv:
          fmvs.value[key] || pockets.value.find((p) => p.key === key)?.acquisition_fmv || '',
      }
    }),
)
const allocated = computed(() => allocations.value.reduce((sum, row) => sum + row.quantity, 0))
const proceeds = computed(() =>
  saleProceeds(details.value.quantity, details.value.proceedsPerShare),
)
const busy = computed(() => props.saving || submitted.value)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    details.value = { transactionDate: props.today, quantity: '', proceedsPerShare: '', fees: '0' }
    fmvs.value = {}
    quantities.value = {}
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
watch(
  () => details.value.transactionDate,
  () => {
    const ids = new Set(pockets.value.map((pocket) => pocket.key))
    quantities.value = Object.fromEntries(
      Object.entries(quantities.value).filter(([id]) => ids.has(id)),
    )
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
  const draft = { ...details.value, allocations: allocations.value }
  errors.value = validateSale(draft, pockets.value, props.today)
  if (
    draft.allocations.some(
      (a) =>
        !/^\d{1,8}(\.\d{1,6})?$/.test(String(a.acquisitionFmv)) || Number(a.acquisitionFmv) <= 0,
    )
  )
    errors.value.allocations = 'Enter a positive USD acquisition FMV for every selected lot.'
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(String(draft.fees || '0')))
    errors.value.fees = 'Enter non-negative USD fees with at most two decimals.'
  if (Object.keys(errors.value).length) return
  submitted.value = true
  emit('confirmed', {
    ...draft,
    quantity: Number(draft.quantity),
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
      class="flex max-h-[90dvh] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl"
      :show-close-button="!busy"
      @escape-key-down="preventDismiss"
      @interact-outside="preventDismiss"
    >
      <DialogHeader class="p-6 pb-4">
        <DialogTitle>Record sale · {{ ticker }}</DialogTitle>
        <DialogDescription
          >Enter the transaction and choose which acquired shares you sold.</DialogDescription
        >
      </DialogHeader>
      <form class="flex min-h-0 flex-1 flex-col" @submit.prevent="confirm">
        <div class="space-y-6 overflow-y-auto px-6 pb-6">
          <p
            v-if="saveError"
            role="alert"
            class="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
          >
            {{ saveError }}
          </p>
          <fieldset :disabled="busy" class="grid gap-4 sm:grid-cols-3">
            <div class="space-y-2">
              <Label for="sale-date">Transaction date</Label>
              <Input
                id="sale-date"
                v-model="details.transactionDate"
                type="date"
                :max="today"
                :aria-invalid="Boolean(errors.transactionDate)"
                :aria-describedby="errors.transactionDate ? 'sale-date-error' : undefined"
              />
              <p
                v-if="errors.transactionDate"
                id="sale-date-error"
                role="alert"
                class="text-xs text-destructive"
              >
                {{ errors.transactionDate }}
              </p>
            </div>
            <div class="space-y-2">
              <Label for="sale-quantity">Quantity</Label>
              <Input
                id="sale-quantity"
                v-model="details.quantity"
                type="number"
                min="1"
                step="1"
                placeholder="Shares sold"
                :aria-invalid="Boolean(errors.quantity)"
                :aria-describedby="errors.quantity ? 'sale-quantity-error' : undefined"
              />
              <p
                v-if="errors.quantity"
                id="sale-quantity-error"
                role="alert"
                class="text-xs text-destructive"
              >
                {{ errors.quantity }}
              </p>
            </div>
            <div class="space-y-2">
              <Label for="sale-price">Proceeds per share (USD)</Label>
              <Input
                id="sale-price"
                v-model="details.proceedsPerShare"
                inputmode="decimal"
                placeholder="0.00"
                :aria-invalid="Boolean(errors.proceedsPerShare)"
                :aria-describedby="errors.proceedsPerShare ? 'sale-price-error' : undefined"
              />
              <p
                v-if="errors.proceedsPerShare"
                id="sale-price-error"
                role="alert"
                class="text-xs text-destructive"
              >
                {{ errors.proceedsPerShare }}
              </p>
            </div>
          </fieldset>
          <div class="max-w-xs space-y-2">
            <Label for="sale-fees">Selling fees (USD, optional)</Label>
            <Input
              id="sale-fees"
              v-model="details.fees"
              type="text"
              inputmode="decimal"
              placeholder="0.00"
              :disabled="busy"
            />
            <p v-if="errors.fees" role="alert" class="text-sm text-destructive">
              {{ errors.fees }}
            </p>
          </div>
          <section aria-labelledby="sale-pockets-heading" class="space-y-3">
            <div>
              <h3 id="sale-pockets-heading" class="font-medium">Shares sold by acquisition lot</h3>
              <p class="mt-1 text-xs text-muted-foreground">
                Acquired by the transaction date, after all recorded sales. Enter part or all of
                each lot.
              </p>
            </div>
            <p
              v-if="!pockets.length"
              class="rounded-md border border-dashed p-5 text-sm text-muted-foreground"
            >
              No unsold acquired shares are available on this date.
            </p>
            <div v-else class="divide-y rounded-md border">
              <div
                v-for="pocket in pockets"
                :key="pocket.key"
                class="flex flex-wrap items-center justify-between gap-3 p-4"
              >
                <div class="min-w-0">
                  <Label :for="`sale-pocket-${pocket.key}`" class="break-words">{{
                    pocket.grantTitle
                  }}</Label>
                  <p class="mt-1 text-xs text-muted-foreground">
                    Acquired {{ formatDate(pocket.date) }}
                  </p>
                  <p class="mt-1 text-xs text-muted-foreground">
                    {{ formatShares(pocket.remaining) }} available ·
                    {{ formatShares(pocket.quantity) }} originally acquired
                  </p>
                </div>
                <div class="space-y-1">
                  <Label :for="`fmv-${pocket.key}`">Acquisition FMV per share (USD)</Label>
                  <Input
                    :id="`fmv-${pocket.key}`"
                    v-model="fmvs[pocket.key]"
                    :placeholder="pocket.acquisition_fmv || 'Required when selling'"
                    :disabled="busy || Number(pocket.acquisition_fmv) > 0"
                    inputmode="decimal"
                    class="w-44"
                  />
                  <p
                    v-if="Number(pocket.acquisition_fmv) > 0"
                    class="text-xs text-muted-foreground"
                  >
                    Recorded FMV: {{ formatDecimal(pocket.acquisition_fmv) }} USD
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <Input
                    :id="`sale-pocket-${pocket.key}`"
                    v-model="quantities[pocket.key]"
                    type="number"
                    min="0"
                    :max="pocket.remaining"
                    step="1"
                    placeholder="0"
                    class="w-28"
                    :disabled="busy"
                    :aria-label="`Shares sold from ${pocket.grantTitle}, acquired ${formatDate(pocket.date)}`"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    :disabled="busy"
                    @click="quantities[pocket.key] = pocket.remaining"
                    >Use all</Button
                  >
                </div>
              </div>
            </div>
            <p v-if="errors.allocations" role="alert" class="text-sm text-destructive">
              {{ errors.allocations }}
            </p>
          </section>
        </div>
        <div
          class="flex shrink-0 flex-wrap justify-between gap-3 border-t bg-muted px-6 py-4 text-sm"
          aria-live="polite"
        >
          <p>
            <span class="text-muted-foreground">Allocated</span>
            <strong class="ml-2 tabular-nums"
              >{{ formatShares(allocated) }} /
              {{ formatShares(details.quantity || 0) }} shares</strong
            >
          </p>
          <p>
            <span class="text-muted-foreground">Gross proceeds</span>
            <strong class="ml-2 tabular-nums">{{ proceeds || '—' }}</strong>
          </p>
        </div>
        <DialogFooter class="border-t p-4 sm:px-6">
          <Button type="button" variant="outline" :disabled="busy" @click="close">Cancel</Button>
          <Button type="submit" :disabled="busy || !pockets.length">{{
            busy ? 'Recording…' : 'Record sale'
          }}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
