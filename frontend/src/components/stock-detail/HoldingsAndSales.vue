<script setup>
import { computed, ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatShares, localDate } from './vesting.js'
import { buildHoldings } from './sales.js'

const props = defineProps({
  grants: { type: Array, default: () => [] },
  sales: { type: Array, default: () => [] },
  today: { type: String, default: () => localDate() },
  busy: Boolean,
})
defineEmits(['delete-sale'])
const portfolio = computed(() => buildHoldings(props.grants, props.sales, props.today))
const selectedYear = ref(props.today.slice(0, 4))
const years = computed(() =>
  [
    ...new Set([
      props.today.slice(0, 4),
      ...portfolio.value.events.map((event) => event.date.slice(0, 4)),
    ]),
  ]
    .sort()
    .reverse(),
)
const ledger = computed(() =>
  [...portfolio.value.events]
    .reverse()
    .filter(
      (event) => selectedYear.value === 'all' || event.date.startsWith(`${selectedYear.value}-`),
    ),
)
const time = (date) => Date.parse(`${date}T00:00:00Z`)
const end = computed(() => time(props.today))
const start = computed(() =>
  Math.min(time(portfolio.value.events[0]?.date || props.today), end.value - 86400000),
)
const x = (date) => 55 + ((time(date) - start.value) / (end.value - start.value)) * 930
const tickStep = computed(() => {
  const maximum = Math.max(1, ...portfolio.value.events.map((event) => event.balance))
  const raw = maximum / 4
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  return Math.max(1, [1, 2, 5, 10].find((step) => step * magnitude >= raw) * magnitude)
})
const ticks = computed(() => Array.from({ length: 5 }, (_, index) => index * tickStep.value))
const y = (balance) => 255 - (balance / (tickStep.value * 4)) * 220
const points = computed(() =>
  portfolio.value.events.map((event) => ({ ...event, x: x(event.date), y: y(event.balance) })),
)
const line = computed(
  () => `M 55 255 ${points.value.map((point) => `H ${point.x} V ${point.y}`).join(' ')} H 985`,
)
const area = computed(() => `${line.value} L 985 255 L 55 255 Z`)
const axisDates = computed(() => [
  ...new Set(
    Array.from({ length: 6 }, (_, index) =>
      new Date(start.value + ((end.value - start.value) * index) / 5).toISOString().slice(0, 10),
    ),
  ),
])
const dateLabel = (date) =>
  new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(`${date}T00:00:00Z`))
const firstDate = computed(() => new Date(start.value).toISOString().slice(0, 10))
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-xl font-semibold">What you held, and when</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          Vesting adds shares. Sales reduce your available balance.
        </p>
      </div>
      <slot name="actions" />
    </div>
    <Card class="gap-0 py-0">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3 p-5 pb-0">
        <CardTitle class="text-base">Vested, unsold shares</CardTitle>
        <div class="flex gap-4 text-xs text-muted-foreground">
          <span class="inline-flex items-center gap-2"
            ><span class="h-0.5 w-4 bg-primary" /> Shares held</span
          >
          <span class="inline-flex items-center gap-2"
            ><span class="h-2.5 w-2.5 rounded-full border-2 border-destructive" /> Sale</span
          >
        </div>
      </CardHeader>
      <CardContent class="p-5">
        <div class="overflow-x-auto">
          <svg
            viewBox="0 0 1100 310"
            class="min-w-[700px] w-full"
            role="img"
            aria-labelledby="holdings-chart-title holdings-chart-description"
          >
            <title id="holdings-chart-title">
              Holdings from {{ formatDate(firstDate) }} to {{ formatDate(today) }}
            </title>
            <desc id="holdings-chart-description">
              {{ formatShares(portfolio.held) }} vested, unsold shares as of
              {{ formatDate(today) }}. Upward steps are vesting events and downward steps are sales.
              Exact dates and balances are in the activity ledger below.
            </desc>
            <g v-for="tick in ticks" :key="tick">
              <line
                x1="55"
                x2="985"
                :y1="y(tick)"
                :y2="y(tick)"
                class="stroke-border"
                stroke-dasharray="3 4"
              />
              <text
                x="44"
                :y="y(tick) + 4"
                text-anchor="end"
                class="fill-muted-foreground text-[11px]"
              >
                {{ formatShares(tick) }}
              </text>
            </g>
            <text x="55" y="18" class="fill-muted-foreground text-[11px]">Shares held</text>
            <path :d="area" class="fill-primary/10" />
            <path
              :d="line"
              fill="none"
              class="stroke-primary"
              stroke-width="2.5"
              stroke-linejoin="round"
            />
            <g v-for="point in points.filter((event) => event.type === 'sale')" :key="point.id">
              <circle
                :cx="point.x"
                :cy="point.y"
                r="5"
                class="fill-card stroke-destructive"
                stroke-width="2"
              />
              <title>
                {{ formatDate(point.date) }}: sold {{ formatShares(-point.change) }} shares;
                {{ formatShares(point.balance) }} held
              </title>
            </g>
            <circle :cx="x(today)" :cy="y(portfolio.held)" r="4" class="fill-primary" />
            <text x="1000" :y="y(portfolio.held) - 3" class="fill-primary text-sm font-semibold">
              {{ formatShares(portfolio.held) }}
            </text>
            <text x="1000" :y="y(portfolio.held) + 14" class="fill-muted-foreground text-[11px]">
              held today
            </text>
            <text
              v-for="date in axisDates"
              :key="date"
              :x="x(date)"
              y="283"
              text-anchor="middle"
              class="fill-muted-foreground text-[11px]"
            >
              {{ dateLabel(date) }}
            </text>
          </svg>
        </div>
        <div class="mt-2 flex flex-wrap gap-x-8 gap-y-2 border-t pt-4 text-sm">
          <p>
            <span class="text-muted-foreground">Lifetime vested</span>
            <span class="ml-2 font-medium tabular-nums">{{ formatShares(portfolio.vested) }}</span>
          </p>
          <p>
            <span class="text-muted-foreground">Lifetime sold</span>
            <span class="ml-2 font-medium tabular-nums">{{ formatShares(portfolio.sold) }}</span>
          </p>
          <p>
            <span class="text-muted-foreground">Still held</span>
            <span class="ml-2 font-medium tabular-nums text-primary">{{
              formatShares(portfolio.held)
            }}</span>
          </p>
        </div>
      </CardContent>
    </Card>

    <Card class="gap-0 overflow-hidden py-0">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <CardTitle class="text-base">Activity ledger</CardTitle>
          <p class="mt-2 text-xs text-muted-foreground">
            Newest first · Gross sale proceeds in USD
          </p>
        </div>
        <label class="flex items-center gap-2 text-sm">
          Year
          <select
            v-model="selectedYear"
            class="rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option v-for="year in years" :key="year" :value="year">{{ year }}</option>
            <option value="all">All years</option>
          </select>
        </label>
      </CardHeader>
      <CardContent class="overflow-x-auto px-0">
        <table class="w-full min-w-[860px] text-sm">
          <caption class="sr-only">
            Vesting and sale activity with full-history share balances
          </caption>
          <thead class="border-y bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th scope="col" class="px-5 py-3 text-left font-medium">Date</th>
              <th scope="col" class="px-5 py-3 text-left font-medium">Event</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Share change</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Balance</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Sale proceeds</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!ledger.length">
              <td colspan="6" class="px-5 py-10 text-center text-muted-foreground">
                {{
                  portfolio.events.length
                    ? 'No activity in this year.'
                    : 'No vested shares or sales yet.'
                }}
              </td>
            </tr>
            <tr
              v-for="event in ledger"
              :key="event.id"
              class="border-b last:border-0"
              :class="event.type === 'sale' && 'bg-destructive/5'"
            >
              <td class="whitespace-nowrap px-5 py-3 text-muted-foreground">
                {{ formatDate(event.date) }}
              </td>
              <td class="min-w-64 px-5 py-3">
                <span
                  class="inline-flex items-center gap-2"
                  :class="event.type === 'sale' && 'font-semibold'"
                  ><span
                    class="h-2 w-2 rounded-full"
                    :class="
                      event.type === 'sale'
                        ? 'bg-destructive'
                        : event.type === 'vesting'
                          ? 'bg-primary'
                          : 'bg-muted-foreground'
                    "
                  />{{ event.label }}</span
                >
                <p v-if="event.type === 'vesting'" class="mt-1 text-xs text-muted-foreground">
                  {{ event.grantTitle }}
                </p>
                <template v-else>
                  <p class="mt-1 text-xs text-muted-foreground">
                    {{ formatShares(-event.change) }} shares ×
                    {{ event.sale.proceedsPerShare.replace(/0+$/, '').replace(/\.$/, '') }} USD
                  </p>
                  <details class="mt-2 text-xs text-muted-foreground">
                    <summary class="cursor-pointer">
                      {{ event.allocations.length }}
                      {{ event.allocations.length === 1 ? 'pocket' : 'pockets' }} sold
                    </summary>
                    <ul class="mt-2 space-y-1">
                      <li v-for="allocation in event.allocations" :key="allocation.vestingId">
                        {{ allocation.grantTitle }} · Acquired {{ formatDate(allocation.date) }} ·
                        {{ formatShares(allocation.quantity) }} shares
                      </li>
                    </ul>
                  </details>
                </template>
              </td>
              <td
                class="px-5 py-3 text-right font-medium tabular-nums"
                :class="
                  event.change < 0
                    ? 'text-destructive'
                    : event.change > 0
                      ? 'text-primary'
                      : 'text-muted-foreground'
                "
              >
                {{
                  event.change === 0
                    ? '—'
                    : `${event.change > 0 ? '+' : '−'}${formatShares(Math.abs(event.change))}`
                }}
              </td>
              <td class="px-5 py-3 text-right tabular-nums">{{ formatShares(event.balance) }}</td>
              <td
                class="px-5 py-3 text-right tabular-nums"
                :class="event.type === 'sale' ? 'font-semibold' : 'text-muted-foreground'"
              >
                {{ event.proceeds || '—' }}
              </td>
              <td class="px-5 py-3 text-right">
                <Button
                  v-if="event.type === 'sale'"
                  variant="ghost"
                  size="sm"
                  class="text-destructive"
                  :disabled="busy"
                  :aria-label="`Delete sale on ${formatDate(event.date)}`"
                  @click="$emit('delete-sale', event.sale)"
                  ><Trash2 class="h-4 w-4" /> Delete</Button
                >
              </td>
            </tr>
          </tbody>
        </table>
      </CardContent>
    </Card>
  </div>
</template>
