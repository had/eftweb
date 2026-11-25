<script setup>
import { formatCurrency, formatPercent } from '@/lib/numberFormat.js'
import { computed } from 'vue'
import { TooltipContent, TooltipPortal, TooltipRoot, TooltipTrigger } from 'reka-ui'

const props = defineProps({
  bands: { type: Array, required: true },
  taxableIncome: { type: Number, required: true },
  colors: { type: Array, required: true },
})

const formatAmount = formatCurrency
const formatRate = formatPercent
const fill = (amount, limit) => (limit > 0 ? Math.min(100, Math.max(0, (amount / limit) * 100)) : 0)
const chartBands = computed(() => {
  // At an exact boundary the library still reports the preceding band's rate.
  const current = props.bands.findIndex(
    (band) => band.upper_bound === null || props.taxableIncome <= band.upper_bound,
  )
  return props.bands.slice(0, current + 1)
})
const chartLimit = computed(() => {
  const band = chartBands.value.at(-1)
  if (!band) return 1
  // The top band has no capacity: give it visible space without inventing a cap.
  return band.upper_bound ?? Math.max(props.taxableIncome, band.lower_bound * 1.2, 1)
})
const bandLimit = (band) => band.upper_bound ?? chartLimit.value
const bandRange = (band) =>
  band.upper_bound === null
    ? `Over ${formatAmount(band.lower_bound)}`
    : `${formatAmount(band.lower_bound)} – ${formatAmount(band.upper_bound)}`
const bandFill = (band) =>
  band.upper_bound === null
    ? 'No upper limit'
    : formatRate(fill(band.income, band.upper_bound - band.lower_bound) / 100)
const bandDescription = (band, index) =>
  `${formatRate(band.rate)} band, ${bandRange(band)}. Income in band ${formatAmount(band.income)}. Filled ${bandFill(band)}. Tax contribution ${formatAmount(band.tax)}.${index === chartBands.value.length - 1 ? ' Current band.' : ''}`
</script>

<template>
  <div>
    <div class="flex h-8 overflow-hidden rounded-md">
      <TooltipRoot v-for="(band, index) in chartBands" :key="band.lower_bound">
        <TooltipTrigger as-child>
          <button
            type="button"
            class="relative h-full shrink-0 cursor-help border-r border-background p-0 last:border-r-0 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
            :style="{
              width: `${((bandLimit(band) - band.lower_bound) / chartLimit) * 100}%`,
              backgroundColor: colors[index],
            }"
            :aria-label="bandDescription(band, index)"
          >
            <span class="absolute inset-0 bg-card/85" aria-hidden="true" />
            <span
              class="absolute inset-y-0 left-0"
              :style="{
                width: `${fill(band.income, bandLimit(band) - band.lower_bound)}%`,
                backgroundColor: colors[index],
              }"
              aria-hidden="true"
            />
          </button>
        </TooltipTrigger>
        <TooltipPortal>
          <TooltipContent
            side="top"
            :side-offset="6"
            class="z-[60] min-w-56 max-w-xs space-y-3 rounded-md border bg-popover px-3 py-3 text-sm text-popover-foreground shadow-md"
          >
            <div>
              <p class="font-semibold">
                {{ formatRate(band.rate) }} band
                <span
                  v-if="index === chartBands.length - 1"
                  class="ml-2 text-xs font-normal text-muted-foreground"
                  >Current band</span
                >
              </p>
              <p class="mt-1 text-xs text-muted-foreground">{{ bandRange(band) }}</p>
            </div>
            <dl class="space-y-2">
              <div class="flex justify-between gap-4">
                <dt class="text-muted-foreground">Income in band</dt>
                <dd class="tabular-nums">{{ formatAmount(band.income) }}</dd>
              </div>
              <div class="flex justify-between gap-4">
                <dt class="text-muted-foreground">Filled</dt>
                <dd class="tabular-nums">{{ bandFill(band) }}</dd>
              </div>
              <div class="flex justify-between gap-4 border-t pt-2">
                <dt class="text-muted-foreground">Tax contribution</dt>
                <dd class="font-medium tabular-nums">{{ formatAmount(band.tax) }}</dd>
              </div>
            </dl>
          </TooltipContent>
        </TooltipPortal>
      </TooltipRoot>
    </div>
    <div class="relative mt-1 h-4 text-xs text-muted-foreground tabular-nums">
      <span class="absolute left-0">€0</span>
      <span
        v-for="band in chartBands.slice(0, -1)"
        :key="band.upper_bound"
        class="absolute -translate-x-1/2 whitespace-nowrap"
        :style="{ left: `${(band.upper_bound / chartLimit) * 100}%` }"
        >{{ formatAmount(band.upper_bound) }}</span
      >
      <span class="absolute right-0">{{
        chartBands.at(-1)?.upper_bound === null
          ? `${formatRate(chartBands.at(-1).rate)} band has no upper limit`
          : formatAmount(chartLimit)
      }}</span>
    </div>
  </div>
</template>
