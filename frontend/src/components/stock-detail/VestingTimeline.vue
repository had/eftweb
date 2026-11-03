<script setup>
import { computed, ref, watch } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import GrantsEmptyState from './GrantsEmptyState.vue'
import { acquisitionPlans } from './acquisitions.js'
import {
  addMonths,
  buildQuarters,
  formatDate,
  formatShares,
  localDate,
  summarizePortfolio,
} from './vesting.js'

const props = defineProps({
  grants: { type: Array, default: () => [] },
  purchases: { type: Array, default: () => [] },
  today: { type: String, default: () => localDate() },
})
const quarters = computed(() => buildQuarters(props.grants, props.today, props.purchases))
const summary = computed(() => summarizePortfolio(props.grants, props.purchases, props.today))
const plans = computed(() => acquisitionPlans(props.grants, props.purchases))
const selectedId = ref('')
watch(
  quarters,
  (items) => {
    if (!items.some((quarter) => quarter.id === selectedId.value)) {
      selectedId.value = (items.find((quarter) => quarter.scheduled > 0) || items.at(-1))?.id || ''
    }
  },
  { immediate: true },
)
const selectedQuarter = computed(() =>
  quarters.value.find((quarter) => quarter.id === selectedId.value),
)

const left = 58
const baseline = 254
const step = computed(() => Math.max(49, 1030 / Math.max(quarters.value.length, 1)))
const chartWidth = computed(() => left + step.value * quarters.value.length + 20)
const tickStep = computed(() => {
  const rough = Math.max(1, Math.max(0, ...quarters.value.map((quarter) => quarter.total)) / 4)
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  return Math.ceil(rough / magnitude) * magnitude
})
const ticks = computed(() => Array.from({ length: 5 }, (_, index) => index * tickStep.value))
const scale = computed(() => 204 / (tickStep.value * 4))
const bars = computed(() =>
  quarters.value.map((quarter, index) => {
    let stacked = 0
    return {
      ...quarter,
      x: left + index * step.value,
      segments: quarter.segments.map((segment) => {
        stacked += segment.quantity
        return {
          ...segment,
          y: baseline - stacked * scale.value,
          height: segment.quantity * scale.value,
        }
      }),
    }
  }),
)
const todayX = computed(() => {
  const year = Number(props.today.slice(0, 4))
  const quarter = Math.floor((Number(props.today.slice(5, 7)) - 1) / 3)
  const index = quarters.value.findIndex(
    (item) => item.year === year && item.quarter === `Q${quarter + 1}`,
  )
  const start = `${String(year).padStart(4, '0')}-${String(quarter * 3 + 1).padStart(2, '0')}-01`
  const time = (date) => Date.parse(`${date}T00:00:00Z`)
  const fraction = (time(props.today) - time(start)) / (time(addMonths(start, 3)) - time(start))
  return left + (index + fraction) * step.value
})
const yearLabels = computed(() =>
  [...new Set(quarters.value.map((quarter) => quarter.year))].map((year) => {
    const index = quarters.value.findIndex((quarter) => quarter.year === year)
    const count = quarters.value.filter((quarter) => quarter.year === year).length
    return { year, x: left + (index + count / 2) * step.value }
  }),
)
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">When shares become yours</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          RSU vestings and stock purchases, grouped by quarter.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-4">
        <p v-if="summary.nextRelease" class="text-sm text-muted-foreground">
          Next release
          <span class="font-medium text-foreground"
            >{{ formatShares(summary.nextRelease.quantity) }} shares</span
          >
          · {{ formatDate(summary.nextRelease.date) }}
        </p>
        <p v-else-if="plans.length" class="text-sm text-muted-foreground">
          All entered shares have been acquired.
        </p>
        <slot name="actions" />
      </div>
    </div>

    <GrantsEmptyState v-if="!plans.length" />
    <Card v-else class="gap-0 py-0">
      <CardHeader class="gap-3 p-5 pb-0">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <CardTitle class="text-base">Acquisitions by quarter</CardTitle>
          <div class="flex gap-4 text-xs text-muted-foreground">
            <span class="inline-flex items-center gap-2"
              ><span class="h-3 w-3 rounded-sm bg-primary" /> Acquired</span
            ><span class="inline-flex items-center gap-2"
              ><span class="h-3 w-3 rounded-sm border-2 border-primary" /> Scheduled</span
            >
          </div>
        </div>
        <div
          class="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"
          aria-label="Plan legend"
        >
          <span
            v-for="plan in plans"
            :key="plan.key"
            class="inline-flex max-w-full items-center gap-2 break-words"
            ><span
              class="h-2.5 w-2.5 shrink-0 rounded-full"
              :style="{ backgroundColor: plan.color }"
            />{{ plan.title }}</span
          >
        </div>
      </CardHeader>
      <CardContent class="min-w-0 p-5">
        <div class="overflow-x-auto pb-2">
          <svg
            :viewBox="`0 0 ${chartWidth} 318`"
            :style="{ minWidth: `${chartWidth}px` }"
            class="w-full"
            role="group"
            aria-labelledby="vesting-chart-title vesting-chart-description"
          >
            <title id="vesting-chart-title">Quarterly acquisition timeline</title>
            <desc id="vesting-chart-description">
              Filled segments have been acquired; outlined segments are scheduled after today. A
              quarter may contain both. Select a quarter for exact dates and plan contributions, or
              use the quarter selector below.
            </desc>
            <rect
              :x="todayX"
              y="29"
              :width="Math.max(0, chartWidth - 20 - todayX)"
              height="225"
              rx="4"
              class="fill-muted/40"
            />
            <g v-for="tick in ticks" :key="tick">
              <line
                :x1="left"
                :x2="chartWidth - 20"
                :y1="baseline - tick * scale"
                :y2="baseline - tick * scale"
                class="stroke-border"
                stroke-dasharray="3 4"
              />
              <text
                :x="left - 10"
                :y="baseline - tick * scale + 4"
                text-anchor="end"
                class="fill-muted-foreground text-[11px]"
              >
                {{ formatShares(tick) }}
              </text>
            </g>
            <text :x="left" y="18" class="fill-muted-foreground text-[11px]">Shares</text>
            <g
              v-for="bar in bars"
              :key="bar.id"
              class="cursor-pointer"
              @click="selectedId = bar.id"
            >
              <title>
                {{ bar.quarter }} {{ bar.year }}: {{ formatShares(bar.vested) }} acquired,
                {{ formatShares(bar.scheduled) }} scheduled shares
              </title>
              <rect
                :x="bar.x + 2"
                y="30"
                :width="step - 4"
                height="229"
                rx="4"
                :class="
                  bar.id === selectedId ? 'fill-primary/10' : 'fill-transparent hover:fill-muted'
                "
              />
              <rect
                v-for="segment in bar.segments"
                :key="segment.id"
                :x="bar.x + step / 2 - 16"
                :y="segment.y"
                width="32"
                :height="Math.max(segment.height - 1, 0.5)"
                rx="1"
                :fill="segment.color"
                :fill-opacity="segment.scheduled ? 0.08 : 1"
                :stroke="segment.color"
                :stroke-width="segment.scheduled ? 1.5 : 0"
              />
              <text
                :x="bar.x + step / 2"
                y="277"
                text-anchor="middle"
                class="fill-muted-foreground text-[11px]"
              >
                {{ bar.quarter }}
              </text>
            </g>
            <line
              :x1="todayX"
              :x2="todayX"
              y1="30"
              y2="260"
              class="stroke-foreground"
              stroke-width="1.5"
              stroke-dasharray="4 4"
            />
            <text
              :x="todayX + (todayX < chartWidth - 85 ? 8 : -8)"
              y="41"
              :text-anchor="todayX < chartWidth - 85 ? 'start' : 'end'"
              class="fill-foreground text-[11px] font-semibold"
            >
              Today
            </text>
            <text
              v-for="label in yearLabels"
              :key="label.year"
              :x="label.x"
              y="306"
              text-anchor="middle"
              class="fill-foreground text-xs font-medium"
            >
              {{ label.year }}
            </text>
          </svg>
        </div>
        <div v-if="selectedQuarter" class="mt-4 grid gap-5 border-t pt-5 lg:grid-cols-[1fr_2fr]">
          <div>
            <label
              for="vesting-quarter"
              class="text-xs font-medium uppercase tracking-wide text-muted-foreground"
              >Explore a quarter</label
            >
            <select
              id="vesting-quarter"
              v-model="selectedId"
              class="mt-2 block rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
            >
              <option v-for="quarter in quarters" :key="quarter.id" :value="quarter.id">
                {{ quarter.quarter }} {{ quarter.year }}
              </option>
            </select>
            <div aria-live="polite" class="mt-3">
              <p class="text-2xl font-semibold tabular-nums">
                {{ formatShares(selectedQuarter.total) }}
                <span class="text-sm font-normal text-muted-foreground">shares</span>
              </p>
              <p class="mt-1 text-xs text-muted-foreground">
                {{ formatShares(selectedQuarter.vested) }} acquired ·
                {{ formatShares(selectedQuarter.scheduled) }} scheduled
              </p>
            </div>
          </div>
          <div v-if="selectedQuarter.releases.length" class="overflow-x-auto">
            <table class="w-full min-w-[400px] text-sm">
              <caption class="sr-only">
                Selected quarter acquisitions by plan
              </caption>
              <thead>
                <tr class="border-b text-xs text-muted-foreground">
                  <th scope="col" class="py-2 pr-3 text-left font-medium">Date / plan</th>
                  <th scope="col" class="py-2 pr-3 text-right font-medium">Shares</th>
                  <th scope="col" class="py-2 text-right font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="release in selectedQuarter.releases"
                  :key="release.key"
                  class="border-b last:border-0"
                >
                  <td class="py-3 pr-3">
                    <p class="text-xs text-muted-foreground">{{ formatDate(release.date) }}</p>
                    <span class="mt-1 inline-flex items-center gap-2"
                      ><span
                        class="h-2.5 w-2.5 shrink-0 rounded-full"
                        :style="{ backgroundColor: release.color }"
                      />{{ release.title }}</span
                    >
                  </td>
                  <td class="py-3 pr-3 text-right tabular-nums">
                    {{ formatShares(release.quantity) }}
                  </td>
                  <td class="py-3 text-right text-xs text-muted-foreground">
                    {{ release.scheduled ? 'Scheduled' : 'Acquired' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="text-sm text-muted-foreground">No acquisitions in this quarter.</p>
        </div>
      </CardContent>
    </Card>
    <p v-if="plans.length" class="text-xs text-muted-foreground">
      Acquisitions show when shares become available. Totals do not subtract sales.
    </p>
  </div>
</template>
