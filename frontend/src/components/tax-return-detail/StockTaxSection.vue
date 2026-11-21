<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import StockTaxHelper from './StockTaxHelper.vue'

const props = defineProps({
  taxReturnId: { type: Number, required: true },
  filingYear: { type: Number, required: true },
})
const emit = defineEmits(['count'])
const saved = ref({ statements: [], aggregate: {} })
const preview = ref(null)
const drafts = ref({})
const rates = ref([])
const replaceExisting = ref(false)
const loading = ref(false)
const error = ref('')
const message = ref('')
const editing = ref(null)
const editingTitle = ref('')
const opened = ref(null)
const manual = ref(null)
const receiptToken = ref('')
const submittedSignature = ref('')
let generation = 0
onBeforeUnmount(() => {
  generation += 1
})
const labels = {
  capital_result: 'Capital gain / loss (EUR, signed)',
  '1TZ': '1TZ · Taxable acquisition gain',
  '1UZ': '1UZ · Holding-period allowance',
  '1WZ': '1WZ · 50% allowance',
  '1TT': '1TT · Acquisition gain excess, taxpayer 1',
  '1UT': '1UT · Acquisition gain excess, taxpayer 2',
}
const base = computed(() => `/api/tax-returns/${props.taxReturnId}`)
const failure = (e) =>
  e.response?.data?.error || 'Could not complete this request. Please try again.'
const refresh = async () => {
  const current = generation
  const response = await axios.get(`${base.value}/capital-gain-statements`)
  if (current !== generation) return
  saved.value = response.data
  emit('count', response.data.statements.length)
}
watch(
  () => props.taxReturnId,
  async () => {
    const current = ++generation
    loading.value = true
    preview.value = null
    opened.value = null
    editing.value = null
    manual.value = null
    error.value = ''
    rates.value = []
    drafts.value = {}
    try {
      const response = await axios.get(`${base.value}/capital-gain-statements`)
      if (current !== generation) return
      saved.value = response.data
      emit('count', response.data.statements.length)
    } catch (e) {
      if (current === generation) error.value = failure(e)
    } finally {
      if (current === generation) loading.value = false
    }
  },
  { immediate: true },
)
const overrides = () => {
  const result = {}
  for (const row of rates.value) {
    if (!row.date || !row.rate)
      throw new Error('Each manual rate needs an event date and an EUR per USD rate.')
    if (result[row.date] !== undefined) throw new Error('Enter only one override per event date.')
    result[row.date] = row.rate
  }
  return result
}
const prepare = async () => {
  const current = generation
  loading.value = true
  error.value = ''
  message.value = ''
  replaceExisting.value = false
  try {
    const { data } = await axios.post(`${base.value}/stock-tax/preview`, {
      fx_overrides: overrides(),
    })
    if (current !== generation) return
    const previous = drafts.value
    const previousComputed = Object.fromEntries(
      (preview.value?.statements || []).map((s) => [String(s.stock_id), s.computed]),
    )
    drafts.value = Object.fromEntries(
      data.statements.map((s) => [
        String(s.stock_id),
        Object.fromEntries(
          Object.entries(s.reported).map(([field, value]) => [
            field,
            previous[s.stock_id]?.[field] !== undefined &&
            previous[s.stock_id][field] !== previousComputed[s.stock_id]?.[field]
              ? previous[s.stock_id][field]
              : value,
          ]),
        ),
      ]),
    )
    preview.value = data
  } catch (e) {
    if (current === generation) error.value = e.response ? failure(e) : e.message
  } finally {
    if (current === generation) loading.value = false
  }
}
const accept = async () => {
  const current = generation
  loading.value = true
  error.value = ''
  try {
    const body = {
      source_revision: preview.value.source_revision,
      fx_overrides: overrides(),
      reported: drafts.value,
      replace_existing: replaceExisting.value,
    }
    const signature = JSON.stringify(body)
    if (signature !== submittedSignature.value) {
      receiptToken.value = crypto.randomUUID()
      submittedSignature.value = signature
    }
    const { data } = await axios.post(`${base.value}/stock-tax/accept`, body, {
      headers: { 'Idempotency-Key': receiptToken.value },
    })
    if (current !== generation) return
    saved.value = data
    emit('count', data.statements.length)
    preview.value = null
    drafts.value = {}
    opened.value = null
    editing.value = null
    message.value = 'Stock statements and 2074 helper details saved.'
  } catch (e) {
    if (current === generation) error.value = failure(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
const open = async (statement) => {
  const current = generation
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get(`${base.value}/capital-gain-statements/${statement.id}`)
    if (current !== generation) return
    opened.value = data
    editing.value = { ...data.reported }
    editingTitle.value = data.title
  } catch (e) {
    if (current === generation) error.value = failure(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
const saveEdit = async () => {
  const current = generation
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.put(`${base.value}/capital-gain-statements/${opened.value.id}`, {
      ...(!opened.value.source_key ? { title: editingTitle.value } : {}),
      reported: opened.value.source_key
        ? editing.value
        : { capital_result: editing.value.capital_result },
    })
    if (current !== generation) return
    opened.value = data
    await refresh()
    if (current !== generation) return
    preview.value = null
    message.value = 'Reported contributions saved. Computed helper details are unchanged.'
  } catch (e) {
    if (current === generation) error.value = failure(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
const saveManual = async () => {
  const current = generation
  loading.value = true
  error.value = ''
  try {
    await axios.post(`${base.value}/capital-gain-statements`, manual.value)
    if (current !== generation) return
    manual.value = null
    await refresh()
    if (current !== generation) return
    preview.value = null
  } catch (e) {
    if (current === generation) error.value = failure(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
const deleting = ref(null)
const remove = async () => {
  const current = generation
  loading.value = true
  error.value = ''
  try {
    await axios.delete(`${base.value}/capital-gain-statements/${deleting.value.id}`)
    if (current !== generation) return
    deleting.value = null
    opened.value = null
    editing.value = null
    await refresh()
    if (current !== generation) return
    preview.value = null
  } catch (e) {
    if (current === generation) error.value = failure(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
</script>

<template>
  <div class="space-y-6" :aria-busy="loading">
    <Card>
      <CardHeader
        ><CardTitle>Stock gains/losses</CardTitle>
        <p class="text-sm text-muted-foreground">
          {{ filingYear }} tax return · {{ filingYear - 1 }} stock sales
        </p></CardHeader
      >
      <CardContent class="space-y-4">
        <p v-if="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
        <p v-if="message" role="status" class="text-sm">{{ message }}</p>
        <div class="flex flex-wrap gap-2">
          <Button :disabled="loading" @click="prepare">{{
            loading ? 'Working…' : 'Prepare stock sales'
          }}</Button
          ><Button
            variant="outline"
            :disabled="loading"
            @click="manual = { title: '', capital_result: '' }"
            >Add gain/loss source</Button
          >
        </div>
        <dl class="grid gap-3 sm:grid-cols-3">
          <div v-for="(value, box) in saved.aggregate" :key="box" class="rounded border p-3">
            <dt class="text-sm text-muted-foreground">{{ box }}</dt>
            <dd class="font-mono">€{{ value }}</dd>
          </div>
        </dl>
        <p class="text-xs text-muted-foreground">
          Declaration boxes aggregate reported contributions from every source. Stock statements are
          excluded from the partial tax estimate.
        </p>
        <form v-if="manual" class="space-y-3 rounded border p-4" @submit.prevent="saveManual">
          <Label for="capital-source-name">Source name</Label
          ><Input
            id="capital-source-name"
            v-model="manual.title"
            maxlength="256"
            required
            :disabled="loading"
          />
          <Label for="capital-source-result"
            >Capital gain / loss (EUR, whole amount; negative for a loss)</Label
          ><Input
            id="capital-source-result"
            v-model="manual.capital_result"
            inputmode="text"
            required
            :disabled="loading"
          />
          <div class="flex gap-2">
            <Button type="submit" :disabled="loading">Save source</Button
            ><Button type="button" variant="outline" :disabled="loading" @click="manual = null"
              >Cancel</Button
            >
          </div>
        </form>
        <div
          v-for="statement in saved.statements"
          :key="statement.id"
          class="flex flex-wrap items-center justify-between gap-3 rounded border p-3"
        >
          <div>
            <p class="font-medium">{{ statement.title }}</p>
            <p class="text-sm text-muted-foreground">
              {{ statement.source_key ? 'Stock statement' : 'Manual source' }} · capital gain/loss
              €{{ statement.reported.capital_result }}
            </p>
          </div>
          <div class="flex gap-2">
            <Button variant="outline" size="sm" :disabled="loading" @click="open(statement)"
              >View / edit</Button
            ><Button variant="ghost" size="sm" :disabled="loading" @click="deleting = statement"
              >Delete</Button
            >
          </div>
        </div>
        <p v-if="!saved.statements.length && !loading" class="text-sm text-muted-foreground">
          No gain/loss statements saved yet.
        </p>
        <div v-if="deleting" class="space-y-3 rounded border border-destructive p-4">
          <p>Delete “{{ deleting.title }}” and its saved helper details?</p>
          <Button variant="destructive" :disabled="loading" @click="remove">Confirm deletion</Button
          ><Button variant="outline" :disabled="loading" @click="deleting = null">Cancel</Button>
        </div>
      </CardContent>
    </Card>

    <Card v-if="preview">
      <CardHeader
        ><CardTitle>Review {{ preview.income_year }} stock sales</CardTitle>
        <p class="text-sm text-muted-foreground">
          Nothing is saved until you accept all stock statements. Editable contributions are
          preserved when recalculating this preview.
        </p></CardHeader
      >
      <CardContent class="space-y-5">
        <ul
          v-if="preview.errors.length"
          role="alert"
          class="list-inside list-disc text-sm text-destructive"
        >
          <li v-for="issue in preview.errors" :key="issue">{{ issue }}</li>
        </ul>
        <div class="space-y-3 rounded border p-3">
          <p class="text-sm font-medium">Optional manual conversion rates · EUR per USD</p>
          <div v-for="(rate, i) in rates" :key="i" class="flex flex-wrap gap-2">
            <Input
              v-model="rate.date"
              type="date"
              class="w-44"
              :aria-label="`FX event date ${i + 1}`"
              :disabled="loading"
            /><Input
              v-model="rate.rate"
              inputmode="decimal"
              placeholder="EUR per USD"
              class="w-44"
              :aria-label="`EUR per USD ${i + 1}`"
              :disabled="loading"
            /><Button variant="ghost" :disabled="loading" @click="rates.splice(i, 1)"
              >Remove rate</Button
            >
          </div>
          <div class="flex gap-2">
            <Button
              variant="outline"
              :disabled="loading"
              @click="rates.push({ date: '', rate: '' })"
              >Add manual rate</Button
            ><Button variant="outline" :disabled="loading" @click="prepare"
              >Recalculate preview</Button
            >
          </div>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <p
            v-for="(usage, taxpayer) in preview.threshold"
            :key="taxpayer"
            class="rounded border p-3 text-sm"
          >
            {{ taxpayer }} · annual threshold used €{{ usage.used }} · remaining €{{
              usage.remaining
            }}
          </p>
        </div>
        <section
          v-for="statement in preview.statements"
          :key="statement.stock_id"
          class="space-y-4 rounded-lg border p-4"
        >
          <h3 class="text-lg font-semibold">{{ statement.title }}</h3>
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div v-for="(label, field) in labels" :key="field" class="space-y-1">
              <Label :for="`preview-${statement.stock_id}-${field}`">{{ label }}</Label
              ><Input
                :id="`preview-${statement.stock_id}-${field}`"
                v-model="drafts[statement.stock_id][field]"
                :disabled="loading"
              />
              <p class="text-xs text-muted-foreground">
                Computed: €{{ statement.computed[field] }}
              </p>
            </div>
          </div>
          <StockTaxHelper :lines="statement.lines" />
        </section>
        <p v-if="!preview.statements.length && !preview.errors.length" class="text-sm">
          No recorded sales in this income year.
        </p>
        <div
          v-if="preview.replacements.length"
          class="space-y-3 rounded border border-amber-500 p-4"
        >
          <p class="font-medium">
            Existing stock statements will be replaced or removed, including reported edits:
          </p>
          <ul class="list-inside list-disc text-sm">
            <li v-for="old in preview.replacements" :key="old.id">
              {{ old.title }} · reported capital gain/loss €{{ old.reported.capital_result }} ·
              {{
                preview.statements.some((s) => s.stock_id === old.stock_id)
                  ? 'replace'
                  : 'remove (no remaining sales)'
              }}
            </li>
          </ul>
          <label class="flex items-center gap-2 text-sm"
            ><input v-model="replaceExisting" type="checkbox" :disabled="loading" /> I confirm
            replacing/removing these stock statements. Manual sources stay unchanged.</label
          >
        </div>
        <div class="flex gap-2">
          <Button
            :disabled="
              loading ||
              !preview.can_accept ||
              (preview.replacements.length > 0 && !replaceExisting) ||
              (!preview.statements.length && !preview.replacements.length)
            "
            @click="accept"
            >Accept all stock statements</Button
          ><Button variant="outline" :disabled="loading" @click="preview = null"
            >Discard preview</Button
          >
        </div>
      </CardContent>
    </Card>

    <Card v-if="opened && editing">
      <CardHeader
        ><CardTitle>{{ opened.title }}</CardTitle>
        <p class="text-sm text-muted-foreground">
          Saved helper values remain unchanged when you edit reported contributions.
        </p></CardHeader
      >
      <CardContent class="space-y-4">
        <form class="space-y-4" @submit.prevent="saveEdit">
          <div v-if="!opened.source_key" class="space-y-2">
            <Label for="saved-source-name">Source name</Label>
            <Input
              id="saved-source-name"
              v-model="editingTitle"
              maxlength="256"
              required
              :disabled="loading"
            />
          </div>
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <template v-for="(label, field) in labels" :key="field"
              ><div v-if="opened.source_key || field === 'capital_result'" class="space-y-1">
                <Label :for="`saved-${field}`">{{ label }}</Label
                ><Input :id="`saved-${field}`" v-model="editing[field]" :disabled="loading" />
                <p
                  v-if="opened.computed[field] !== undefined"
                  class="text-xs text-muted-foreground"
                >
                  Computed: €{{ opened.computed[field] }}
                </p>
              </div></template
            >
          </div>
          <Button type="submit" :disabled="loading">Save reported contributions</Button
          ><Button
            type="button"
            variant="outline"
            :disabled="loading"
            class="ml-2"
            @click="opened = null"
            >Close</Button
          >
        </form>
        <StockTaxHelper :lines="opened.lines" />
      </CardContent>
    </Card>
  </div>
</template>
