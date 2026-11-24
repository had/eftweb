<script setup>
import { computed, ref, useId } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { TooltipProvider } from 'reka-ui'
import InfoTooltip from '@/components/InfoTooltip.vue'
import ProgressiveTaxRuler from '@/components/tax-return-detail/ProgressiveTaxRuler.vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const props = defineProps({
  estimate: { type: Object, default: null },
  estimationLoading: Boolean,
  estimationError: { type: String, default: '' },
})
const detailsOpen = ref(false)
const detailsId = useId()

const currency = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const formatAmount = (amount) => (amount == null ? '—' : currency.format(amount))
const percent = new Intl.NumberFormat('en-GB', { style: 'percent', maximumFractionDigits: 1 })
const formatRate = (rate) => (rate == null ? '—' : percent.format(rate))
const fill = (amount, limit) => (limit > 0 ? Math.min(100, Math.max(0, (amount / limit) * 100)) : 0)
const colors = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
]
const metrics = computed(() => [
  { label: 'Net taxes', value: formatAmount(props.estimate?.net_taxes) },
  { label: 'Net social taxes', value: formatAmount(props.estimate?.net_social_taxes) },
  { label: 'Estimated RFR', value: formatAmount(props.estimate?.reference_fiscal_income) },
  {
    label: 'Parts fiscales',
    value:
      props.estimate?.household_shares == null
        ? '—'
        : new Intl.NumberFormat('en-GB').format(props.estimate.household_shares),
  },
  { label: 'Marginal tax rate', value: formatRate(props.estimate?.marginal_tax_rate) },
])
const progressive = computed(() => props.estimate?.progressive_tax)
</script>

<template>
  <Card class="mb-6 w-full">
    <CardHeader><CardTitle>Tax summary</CardTitle></CardHeader>
    <CardContent class="space-y-4" aria-live="polite" :aria-busy="estimationLoading">
      <p v-if="estimationError" class="text-sm text-destructive">{{ estimationError }}</p>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <div v-for="metric in metrics" :key="metric.label">
          <p class="text-sm text-muted-foreground">{{ metric.label }}</p>
          <div
            v-if="estimationLoading"
            class="mt-1 h-7 w-28 animate-pulse rounded bg-muted"
            :aria-label="`Loading ${metric.label.toLowerCase()}`"
          />
          <p v-else class="mt-1 text-lg font-medium tabular-nums">{{ metric.value }}</p>
        </div>
      </div>
      <p class="text-sm text-muted-foreground">
        Partial estimate using supported statement fields only. Salary withholding and supplementary
        pension contributions are excluded.
      </p>
      <div v-if="progressive && !estimationLoading && !estimationError" class="border-t pt-2">
        <div class="flex justify-center">
          <button
            type="button"
            :aria-expanded="detailsOpen"
            :aria-controls="detailsId"
            :aria-label="detailsOpen ? 'Hide calculation details' : 'Show calculation details'"
            class="inline-flex h-8 w-12 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            @click="detailsOpen = !detailsOpen"
          >
            <ChevronDown
              class="size-5 transition-transform duration-300 ease-in-out motion-reduce:transition-none"
              :class="{ 'rotate-180': detailsOpen }"
              aria-hidden="true"
            />
          </button>
        </div>
        <div
          :id="detailsId"
          :aria-hidden="!detailsOpen"
          :inert="!detailsOpen"
          class="grid transition-[grid-template-rows,opacity] duration-300 ease-in-out motion-reduce:transition-none"
          :class="detailsOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
        >
          <div class="min-h-0 overflow-hidden">
            <TooltipProvider :delay-duration="150">
              <div class="space-y-8 pt-4 pb-2">
                <section aria-label="Progressive income tax" class="space-y-4">
                  <div class="flex flex-wrap items-start justify-between gap-2">
                    <div class="flex items-center gap-1">
                      <h3 class="text-sm font-semibold">Progressive income tax</h3>
                      <InfoTooltip label="About progressive income tax">
                        <p>
                          {{ formatAmount(progressive.taxable_income) }} subject to the scale ·
                          household thresholds for {{ estimate.household_shares }} parts
                        </p>
                        <p>
                          Filled colours show income in each band; the pale area is the unused part
                          of the current band. Scale tax is before family quotient capping,
                          investment taxes, reductions and credits. Totals are rounded by the
                          simulator.
                        </p>
                      </InfoTooltip>
                    </div>
                    <p class="text-sm font-medium tabular-nums">
                      Scale tax {{ formatAmount(progressive.scale_tax) }}
                    </p>
                  </div>
                  <ProgressiveTaxRuler
                    :bands="progressive.brackets"
                    :taxable-income="progressive.taxable_income"
                    :colors="colors"
                  />
                </section>

                <section aria-label="Donation buckets" class="space-y-4 border-t pt-6">
                  <div class="flex items-center gap-1">
                    <h3 class="text-sm font-semibold">Donation buckets</h3>
                    <InfoTooltip label="About donation buckets">
                      <p>
                        Only supported donations in boxes 7UD and 7UF are included. Calculated
                        reductions may be limited by the tax due.
                      </p>
                      <p>75% bucket: 7UD · people in need · €1,000 ceiling.</p>
                      <p>66% bucket: 7UF + overflow from 7UD · ceiling of 20% of taxable income.</p>
                      <p
                        v-for="bucket in estimate.donation_buckets.filter(
                          (bucket) => bucket.overflow > 0,
                        )"
                        :key="bucket.rate"
                      >
                        {{ formatAmount(bucket.overflow) }}
                        {{
                          bucket.rate === 0.75
                            ? 'transferred to the 66% bucket.'
                            : "above the 66% bucket's limit; excluded from the estimate."
                        }}
                      </p>
                    </InfoTooltip>
                  </div>
                  <div class="grid gap-6 lg:grid-cols-2">
                    <div
                      v-for="bucket in estimate.donation_buckets"
                      :key="bucket.rate"
                      class="space-y-2"
                    >
                      <div class="flex flex-wrap justify-between gap-2 text-sm">
                        <h4 class="font-medium">{{ formatRate(bucket.rate) }} reduction</h4>
                        <span class="tabular-nums"
                          >{{ formatAmount(Math.min(bucket.donated, bucket.limit)) }} /
                          {{ formatAmount(bucket.limit) }}</span
                        >
                      </div>
                      <div
                        role="progressbar"
                        :aria-label="`${formatRate(bucket.rate)} donation bucket`"
                        :aria-valuenow="fill(bucket.donated, bucket.limit)"
                        aria-valuemin="0"
                        aria-valuemax="100"
                        :aria-valuetext="`${formatAmount(bucket.donated)} donated; ${formatAmount(bucket.limit)} limit`"
                        class="h-3 overflow-hidden rounded-full bg-muted"
                      >
                        <div
                          class="h-full rounded-full"
                          :style="{
                            width: `${fill(bucket.donated, bucket.limit)}%`,
                            backgroundColor: bucket.rate === 0.75 ? colors[0] : colors[1],
                          }"
                        />
                      </div>
                      <p class="text-sm">
                        Calculated reduction:
                        <span class="font-medium tabular-nums">{{
                          formatAmount(bucket.reduction)
                        }}</span>
                      </p>
                    </div>
                  </div>
                </section>

                <section
                  v-if="estimate.fiscal_advantages"
                  aria-label="Annual tax advantage ceiling"
                  class="space-y-3 border-t pt-6"
                >
                  <div class="flex flex-wrap justify-between gap-2 text-sm">
                    <div class="flex items-center gap-1">
                      <h3 class="font-semibold">Annual tax advantage ceiling</h3>
                      <InfoTooltip label="About the annual tax advantage ceiling">
                        <p>
                          Partial coverage: eligible expenses such as home services and childcare
                          are not collected yet, so tracked usage is currently zero. Donations do
                          not use this ceiling.
                        </p>
                        <p v-if="estimate.fiscal_advantages.excess > 0">
                          {{ formatAmount(estimate.fiscal_advantages.excess) }} exceeds the ceiling.
                        </p>
                      </InfoTooltip>
                    </div>
                    <span class="tabular-nums"
                      >{{ formatAmount(estimate.fiscal_advantages.used) }} /
                      {{ formatAmount(estimate.fiscal_advantages.limit) }}</span
                    >
                  </div>
                  <div
                    role="progressbar"
                    aria-label="Annual tax advantage ceiling"
                    :aria-valuenow="estimate.fiscal_advantages.used"
                    aria-valuemin="0"
                    :aria-valuemax="estimate.fiscal_advantages.limit"
                    class="h-3 overflow-hidden rounded-full bg-muted"
                  >
                    <div
                      class="h-full rounded-full bg-primary"
                      :style="{
                        width: `${fill(estimate.fiscal_advantages.used, estimate.fiscal_advantages.limit)}%`,
                      }"
                    />
                  </div>
                  <p class="text-sm tabular-nums">
                    {{
                      formatAmount(
                        estimate.fiscal_advantages.limit - estimate.fiscal_advantages.used,
                      )
                    }}
                    remaining within the tracked estimate.
                  </p>
                </section>
              </div>
            </TooltipProvider>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
