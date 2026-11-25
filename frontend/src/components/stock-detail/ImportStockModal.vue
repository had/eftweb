<script setup>
import { formatNumber } from '@/lib/numberFormat.js'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { Plus, Trash2 } from 'lucide-vue-next'
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
import { importIssues, lotKey, saleDecision } from '@/lib/stockImport.js'

const props = defineProps({ open: Boolean, stockId: { type: Number, required: true } })
const emit = defineEmits(['update:open', 'imported', 'busy'])
const file = ref(null)
const preview = ref(null)
const drafts = ref({})
const orderFees = ref({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const result = ref(null)
let controller
let generation = 0
let disposed = false
let token = ''
let submittedSignature = ''
const issues = computed(() => {
  const result = importIssues(preview.value, drafts.value)
  if (
    Object.values(orderFees.value).some(
      (value) => !/^\d{1,8}(\.\d{1,2})?$/.test(String(value || '0')),
    )
  )
    result.push('Order fees must be non-negative USD amounts with at most two decimals.')
  return result
})
const brokerOrders = computed(() => [
  ...new Set((preview.value?.sales || []).map((sale) => sale.source_order_number).filter(Boolean)),
])
const canConfirm = computed(
  () => preview.value && !loading.value && !saving.value && !result.value && !issues.value.length,
)
const decisions = () =>
  preview.value.format === 'eftweb'
    ? {}
    : Object.fromEntries(
        preview.value.sales.map((sale) => [
          sale.key,
          saleDecision(sale, {
            ...drafts.value[sale.key],
            orderFee: orderFees.value[sale.source_order_number] || '0',
          }),
        ]),
      )

const reset = () => {
  generation += 1
  controller?.abort()
  controller = null
  file.value = null
  preview.value = null
  drafts.value = {}
  orderFees.value = {}
  error.value = ''
  result.value = null
  loading.value = false
  token = ''
  submittedSignature = ''
}
watch(
  () => props.open,
  () => {
    if (!saving.value) reset()
  },
)
watch(
  saving,
  (value) => {
    if (!disposed) emit('busy', value)
  },
  { flush: 'sync' },
)
onBeforeUnmount(() => {
  disposed = true
  generation += 1
  controller?.abort()
})
const close = () => {
  if (saving.value) return
  reset()
  emit('update:open', false)
}
const chooseFile = (event) => {
  reset()
  file.value = event.target.files?.[0] || null
}
const form = () => {
  const data = new FormData()
  data.append('file', file.value)
  return data
}
const loadPreview = async () => {
  if (!file.value || loading.value || saving.value) return
  if (file.value.size > 10 * 1024 * 1024) {
    error.value = 'Choose an XLSX file no larger than 10 MiB.'
    return
  }
  const current = ++generation
  controller?.abort()
  controller = new AbortController()
  const signal = controller.signal
  loading.value = true
  error.value = ''
  preview.value = null
  result.value = null
  token = ''
  submittedSignature = ''
  try {
    const response = await axios.post(`/api/stocks/${props.stockId}/import/preview`, form(), {
      signal,
    })
    if (current !== generation || signal.aborted) return
    preview.value = response.data
    drafts.value = Object.fromEntries(
      response.data.sales.map((sale) => [
        sale.key,
        {
          skip: sale.skip,
          reviewed: false,
          allocations: sale.allocations.length
            ? sale.allocations.map((row) => ({
                lot: lotKey(row),
                quantity: row.quantity,
                acquisitionFmv: Number(row.acquisition_fmv) > 0 ? row.acquisition_fmv : '',
              }))
            : [{ lot: '', quantity: '', acquisitionFmv: '' }],
        },
      ]),
    )
  } catch (failure) {
    if (current === generation && !signal.aborted)
      error.value =
        failure.response?.data?.error || 'Could not preview this file. Please try again.'
  } finally {
    if (current === generation) loading.value = false
  }
}
const confirmImport = async () => {
  if (!canConfirm.value) return
  const choices = decisions()
  const signature = JSON.stringify([
    preview.value.file_digest,
    preview.value.stock_revision,
    choices,
  ])
  if (signature !== submittedSignature) {
    token = crypto.randomUUID()
    submittedSignature = signature
  }
  const data = form()
  data.append('decisions', JSON.stringify(choices))
  data.append('stock_revision', preview.value.stock_revision)
  saving.value = true
  error.value = ''
  try {
    const response = await axios.post(`/api/stocks/${props.stockId}/import`, data, {
      headers: { 'Idempotency-Key': token },
    })
    if (disposed) return
    result.value = response.data
    emit('imported', response.data)
  } catch (failure) {
    if (!disposed)
      error.value =
        failure.response?.data?.error ||
        'Could not save this import. Retry to check or complete the same import.'
  } finally {
    saving.value = false
  }
}
const eligibleLots = (sale) =>
  preview.value.lots.filter(
    (lot) =>
      lot.date <= sale.transaction_date &&
      sale.sources.some((source) => source.plan_type === lot.plan_type),
  )
const selectLot = (allocation) => {
  const lot = preview.value.lots.find((lot) => `${lot.source}:${lot.id}` === allocation.lot)
  allocation.acquisitionFmv = Number(lot?.acquisition_fmv) > 0 ? lot.acquisition_fmv : ''
}
const preventDismiss = (event) => {
  if (saving.value) event.preventDefault()
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
      class="flex max-h-[90dvh] flex-col overflow-hidden p-0 sm:max-w-4xl"
      :show-close-button="!saving"
      @escape-key-down="preventDismiss"
      @interact-outside="preventDismiss"
    >
      <DialogHeader class="border-b p-6">
        <DialogTitle>Import stock data</DialogTitle>
        <DialogDescription
          >Restore an app export into this empty stock, or add E*TRADE sales to existing acquisition
          lots. Review before saving.</DialogDescription
        >
      </DialogHeader>
      <div class="min-h-0 space-y-5 overflow-y-auto p-6" :aria-busy="loading || saving">
        <div v-if="result" role="status" class="space-y-2 rounded-lg border p-4">
          <p class="font-semibold">Import complete</p>
          <p>
            {{ result.counts.grants }} grants, {{ result.counts.vestings }} vestings,
            {{ result.counts.purchases }} purchases, and {{ result.counts.sales }} sales imported.
            {{ result.counts.skipped_sales }} sales skipped.
          </p>
        </div>
        <template v-else>
          <div class="space-y-2">
            <Label for="stock-import-file">Excel workbook (.xlsx, up to 10 MiB)</Label>
            <input
              id="stock-import-file"
              type="file"
              accept=".xlsx"
              :disabled="loading || saving"
              class="block w-full rounded-md border p-2 text-sm"
              @change="chooseFile"
            />
          </div>
          <Button variant="outline" :disabled="!file || loading || saving" @click="loadPreview">{{
            loading ? 'Reading workbook…' : preview ? 'Refresh preview' : 'Preview import'
          }}</Button>
          <p v-if="loading" role="status" class="text-sm text-muted-foreground">
            Reading records and matching acquisition lots…
          </p>
          <template v-if="preview">
            <div class="rounded-lg border p-4 text-sm">
              <p class="font-semibold">
                {{
                  preview.format === 'eftweb'
                    ? 'App export — complete restore'
                    : 'E*TRADE — sales only (USD)'
                }}
                · {{ preview.symbol || 'No sales' }}
              </p>
              <p class="mt-1">
                {{ preview.counts.grants }} grants · {{ preview.counts.purchases }} purchases ·
                {{ preview.counts.sales }} sales
              </p>
              <p v-if="preview.format === 'eftweb'" class="mt-2">
                Restores the name “{{ preview.stock_name }}” and every exported record with new IDs.
                This stock must have no grants, purchases, or sales.
              </p>
              <p v-else class="mt-2">
                No grants or purchases will be created. Resolve lots or skip individual sales below.
                STC shares do not affect balances.
              </p>
            </div>
            <ul
              v-if="preview.errors.length"
              role="alert"
              class="list-inside list-disc text-sm text-destructive"
            >
              <li v-for="message in preview.errors" :key="message">{{ message }}</li>
            </ul>
            <div v-if="preview.format === 'eftweb'" class="space-y-2 text-sm">
              <p v-for="grant in preview.grants" :key="grant.key">
                {{ grant.title }} · {{ formatNumber(grant.quantity) }} shares ·
                {{ grant.vestings.length }} releases<span v-if="grant.grant_number">
                  · Grant {{ grant.grant_number }}</span
                >
              </p>
              <p v-for="purchase in preview.purchases" :key="purchase.key">
                {{ purchase.plan_name }} · {{ purchase.purchase_date }} ·
                {{ formatNumber(purchase.quantity) }} shares
              </p>
              <p v-for="sale in preview.sales" :key="sale.key">
                Sale {{ sale.transaction_date }} · {{ formatNumber(sale.quantity) }} shares at ${{
                  formatNumber(sale.proceeds_per_share, { maximumFractionDigits: 6 })
                }}
                · {{ sale.allocations.length }} allocations
              </p>
            </div>
            <div v-else class="space-y-4">
              <section
                v-if="brokerOrders.length"
                class="space-y-3 rounded-lg border p-4"
                aria-label="Broker order fees"
              >
                <p class="text-sm text-muted-foreground">
                  Enter one total USD fee per order. It is shared across all that order's executions
                  in this workbook, including skipped or previously imported executions.
                </p>
                <div v-for="(order, index) in brokerOrders" :key="order" class="max-w-sm space-y-2">
                  <Label :for="`order-fee-${index}`">Order {{ order }} fee (USD, optional)</Label>
                  <Input
                    :id="`order-fee-${index}`"
                    v-model="orderFees[order]"
                    inputmode="decimal"
                    placeholder="0.00"
                    :disabled="saving"
                  />
                </div>
              </section>
              <section
                v-for="sale in preview.sales"
                :key="sale.key"
                class="space-y-3 rounded-lg border p-4"
                :aria-label="`Sale from broker rows ${sale.rows.join(', ')}`"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p class="font-medium">
                      {{ sale.transaction_date || 'Invalid sale' }} ·
                      {{ sale.quantity == null ? '?' : formatNumber(sale.quantity) }} shares at ${{
                        sale.proceeds_per_share == null
                          ? '?'
                          : formatNumber(sale.proceeds_per_share, { maximumFractionDigits: 6 })
                      }}
                    </p>
                    <p class="text-xs text-muted-foreground">
                      Order {{ sale.source_order_number || 'unavailable' }} · Broker rows
                      {{ sale.rows.join(', ') }} · {{ sale.status.replaceAll('_', ' ') }}
                    </p>
                  </div>
                  <label class="flex items-center gap-2 text-sm"
                    ><input
                      v-model="drafts[sale.key].skip"
                      type="checkbox"
                      :disabled="saving || sale.status === 'duplicate'"
                    />
                    Skip sale</label
                  >
                </div>
                <p v-if="sale.status === 'duplicate'" class="text-sm">
                  Already imported as sale {{ sale.existing_sale_id }}; skipped automatically.
                </p>
                <p
                  v-for="source in sale.sources"
                  :key="JSON.stringify(source)"
                  class="text-xs text-muted-foreground"
                >
                  {{ source.plan_type }} ·
                  {{
                    source.plan_type === 'RS' ? `Grant ${source.grant_number}, vesting` : 'Purchase'
                  }}
                  {{ source.date }} · {{ formatNumber(source.quantity) }} shares · Acquired
                  {{ source.acquired_date }} · Grant date {{ source.grant_date }}
                </p>
                <ul
                  v-if="sale.errors.length || sale.warnings.length || sale.matching_issues?.length"
                  class="list-inside list-disc text-sm"
                >
                  <li
                    v-for="message in [
                      ...sale.errors,
                      ...sale.warnings,
                      ...(sale.matching_issues || []),
                    ]"
                    :key="message"
                  >
                    {{ message }}
                  </li>
                </ul>
                <template
                  v-if="
                    !drafts[sale.key].skip &&
                    !['invalid', 'conflict', 'duplicate'].includes(sale.status)
                  "
                >
                  <fieldset class="space-y-2" :disabled="saving">
                    <legend class="mb-2 text-sm font-medium">
                      Allocate {{ formatNumber(sale.quantity) }} shares to existing lots
                    </legend>
                    <div
                      v-for="(allocation, index) in drafts[sale.key].allocations"
                      :key="index"
                      class="flex items-center gap-2"
                    >
                      <select
                        v-model="allocation.lot"
                        @change="selectLot(allocation)"
                        :aria-label="`Source lot ${index + 1} for order ${sale.source_order_number}`"
                        class="min-w-0 flex-1 rounded-md border bg-background p-2 text-sm"
                      >
                        <option value="">Select an acquisition lot</option>
                        <option
                          v-for="lot in eligibleLots(sale)"
                          :key="`${lot.source}:${lot.id}`"
                          :value="`${lot.source}:${lot.id}`"
                        >
                          {{ lot.label }} · {{ formatNumber(lot.available) }} available
                        </option>
                      </select>
                      <Input
                        v-model="allocation.quantity"
                        type="number"
                        min="1"
                        step="1"
                        class="w-24"
                        :aria-label="`Allocated shares ${index + 1} for order ${sale.source_order_number}`"
                      />
                      <Input
                        v-model="allocation.acquisitionFmv"
                        inputmode="decimal"
                        placeholder="Acquisition FMV (USD)"
                        class="w-44"
                        :aria-label="`Acquisition FMV ${index + 1} for order ${sale.source_order_number}`"
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        :aria-label="`Remove allocation ${index + 1}`"
                        @click="drafts[sale.key].allocations.splice(index, 1)"
                        ><Trash2 class="h-4 w-4"
                      /></Button>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      @click="
                        drafts[sale.key].allocations.push({
                          lot: '',
                          quantity: '',
                          acquisitionFmv: '',
                        })
                      "
                      ><Plus class="h-4 w-4" /> Add allocation</Button
                    >
                  </fieldset>
                  <label class="flex items-start gap-2 text-sm"
                    ><input
                      v-model="drafts[sale.key].reviewed"
                      type="checkbox"
                      :disabled="saving"
                      class="mt-1"
                    />
                    I reviewed the broker facts, selected lots, and any possible duplicate.</label
                  >
                </template>
              </section>
              <details v-if="preview.ignored.length" class="text-sm">
                <summary>
                  {{ preview.ignored.length }} non-sale or sell-to-cover rows ignored
                </summary>
                <p v-for="row in preview.ignored" :key="row.row" class="mt-1">
                  Row {{ row.row }}: {{ row.reason }}
                </p>
              </details>
              <ul
                v-if="issues.length && !preview.errors.length"
                class="list-inside list-disc text-sm text-muted-foreground"
              >
                <li v-for="message in issues" :key="message">{{ message }}</li>
              </ul>
            </div>
          </template>
        </template>
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
      </div>
      <DialogFooter class="border-t p-6">
        <Button variant="outline" :disabled="saving" @click="close">{{
          result ? 'Done' : 'Cancel'
        }}</Button>
        <Button v-if="!result" :disabled="!canConfirm" @click="confirmImport">{{
          saving
            ? 'Importing…'
            : preview?.format === 'eftweb'
              ? 'Restore all records'
              : 'Import selected sales'
        }}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
